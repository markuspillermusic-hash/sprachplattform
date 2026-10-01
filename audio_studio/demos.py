"""One generated reference set, independent editable copies for each user."""
import json
import shutil
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from projects.models import Project, ScriptSegment, Speaker
from .media import StudioError, normalize, render_mix
from .models import StudioAsset, StudioDemoEnrollment, StudioJob, StudioSession, empty_state
from .services import asset_folder, save_state, validate_state

DEMO_KEY = "clockwork-v1"
DEMO_TITLE = "Demo · Hörspiel · Das Geheimnis der alten Uhr"
SEGMENTS = (
    (1, "In der verlassenen Bahnhofshalle tickt eine alte Uhr. Alex und Mira suchen den letzten Zug.", "serious"),
    (0, "Hörst du das? Die Uhr schlägt, obwohl die Zeiger stillstehen.", "surprised"),
    (1, "Warte. Unter dem Zifferblatt steckt ein kleiner Schlüssel.", "whispering"),
    (0, "Dann gehört er bestimmt zu dieser Tür. Ich probiere es.", "serious"),
    (1, "Sie ist offen! Dahinter führt eine Treppe direkt zum Bahnsteig.", "cheerfully"),
    (0, "Manchmal reicht ein leises Geräusch, um ein großes Geheimnis zu entdecken.", "friendly"),
)
SAMPLES = {f"speech-{i}": (f"{('Alex', 'Mira')[speaker]} · Abschnitt {i}", "speech")
           for i, (speaker, _, _) in enumerate(SEGMENTS, start=1)}
SAMPLES.update(music=("Jingle und geheimnisvolle Hintergrundmusik", "music"),
               clock=("Alte Bahnhofsuhr · Tick-Tack", "effects"),
               bell=("Glockenschlag der Bahnhofsuhr", "effects"),
               door=("Schlüssel und knarrende Tür", "effects"))


def bundle_folder():
    return Path(settings.AUDIO_STORAGE_ROOT).resolve() / "demos" / DEMO_KEY


def read_bundle():
    path = bundle_folder() / "manifest.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("key") != DEMO_KEY or not all(
            name in data["samples"] and (bundle_folder() / f"{name}.mp3").is_file()
            for name in (*SAMPLES, "mix")
        ):
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def demo_state(samples):
    state = empty_state()
    state.update(speech_compression=True, effects_ducking=False)
    def clip(name, track, start, trim_start, length, gain, fade_in=.1, fade_out=.1):
        length = round(min(length, samples[name]["duration"] - trim_start), 6)
        state["clips"].append({"id": str(uuid.uuid4()), "asset_id": name, "track": track,
                               "start": round(start, 6), "trim_start": trim_start,
                               "trim_end": round(trim_start + length, 6), "gain_db": gain,
                               "fade_in": min(fade_in, length / 2), "fade_out": min(fade_out, length / 2)})
    cursor, starts = 4.0, []
    for i in range(1, 7):
        name = f"speech-{i}"
        starts.append(cursor)
        length = samples[name]["duration"]
        clip(name, "speech", cursor, 0, length, 0, .035, .08)
        cursor += length + .55
    end = cursor + 2.5
    clip("music", "music", 0, 0, 3.5, -8, .2, .8)
    clip("music", "music", 3, 3, end - 3, -13, 1, 3)
    clip("music", "music", end - 3, 0, 3, -10, .4, 1.2)
    cursor = .7
    while cursor < end - 1:
        length = min(samples["clock"]["duration"], end - 1 - cursor)
        clip("clock", "effects", cursor, 0, length, -9, .1, .2)
        cursor += length
    clip("bell", "effects", starts[1] + .4, 0, samples["bell"]["duration"], -3, .03, .7)
    clip("door", "effects", starts[3] + max(0, samples["speech-4"]["duration"] - 1),
         0, samples["door"]["duration"], -3, .05, .6)
    return state


def prepare_bundle(*, refresh=False):
    existing = read_bundle()
    if existing and not refresh:
        return existing
    folder = bundle_folder()
    try:
        progress = json.loads((folder / "generation-progress.json").read_text(encoding="utf-8"))
        samples = {}
        for name, (title, kind) in SAMPLES.items():
            item = progress[name]
            if item["status"] != "ready" or not (folder / f"{name}.mp3").is_file():
                raise KeyError(name)
            if refresh and kind == "effects":
                source = folder / f"{name}-raw.mp3"
                if not source.is_file():
                    source = folder / f"{name}.mp3"
                temporary = folder / f"{name}-leveled.mp3"
                item["duration"], item["waveform"] = normalize(source, temporary, target_peak=.6)
                temporary.replace(folder / f"{name}.mp3")
            samples[name] = {"title": title, "kind": kind, "duration": item["duration"],
                             "waveform": item["waveform"], "source": item.get("source", "ElevenLabs KI")}
    except (OSError, ValueError, KeyError, TypeError):
        raise StudioError("Die Hörspiel-Hörbeispiele sind noch nicht vollständig vorbereitet.") from None
    state = demo_state(samples)
    assets = {name: SimpleNamespace(file_path=str(folder / f"{name}.mp3")) for name in samples}
    target = folder / "mix-refresh.mp3"
    duration, peaks = render_mix(state, assets, target, "mp3")
    target.replace(folder / "mix.mp3")
    samples["mix"] = {"title": "Hörspiel-Demo · Referenzmix mit Geräuschen", "kind": "mix", "duration": duration,
                       "waveform": peaks, "source": "Mix der Demo-Hörbeispiele"}
    data = {"key": DEMO_KEY, "title": DEMO_TITLE, "samples": samples, "state": state}
    temporary = folder / "manifest.tmp"
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temporary.replace(folder / "manifest.json")
    return data


def repair_demo_effect_samples(user, bundle):
    """Repair reference audio without touching users' clip edits or export files."""
    enrollment = StudioDemoEnrollment.objects.filter(user=user).first()
    if not enrollment or not enrollment.project_id:
        return
    for name, (title, kind) in SAMPLES.items():
        if kind != "effects":
            continue
        for asset in StudioAsset.objects.filter(project_id=enrollment.project_id, title=title, kind=kind,
                                               is_demo_sample=True, deleted_at__isnull=True):
            target = Path(asset.file_path).resolve()
            if not target.is_relative_to(Path(settings.AUDIO_STORAGE_ROOT).resolve() / "studio"):
                raise StudioError("Die Demo-Audiodatei liegt außerhalb des Audioordners.")
            temporary = target.with_suffix(".repair.mp3")
            try:
                shutil.copyfile(bundle_folder() / f"{name}.mp3", temporary)
                temporary.replace(target)
                data = bundle["samples"][name]
                asset.duration, asset.waveform, asset.size_bytes = data["duration"], data["waveform"], target.stat().st_size
                asset.save(update_fields=["duration", "waveform", "size_bytes"])
            finally:
                temporary.unlink(missing_ok=True)


def refresh_demo_preview(user, bundle):
    """The shared preview uses the repaired reference, independently of user edits."""
    enrollment = StudioDemoEnrollment.objects.filter(user=user).select_related("project").first()
    if not enrollment or not enrollment.project_id:
        return
    project = enrollment.project
    data = bundle["samples"]["mix"]
    latest = project.studio_assets.filter(kind="mix", is_demo_sample=True, deleted_at__isnull=True).first()
    if latest and latest.title == data["title"]:
        return
    target = asset_folder(project) / f"{uuid.uuid4()}.mp3"
    try:
        shutil.copyfile(bundle_folder() / "mix.mp3", target)
        StudioAsset.objects.create(project=project, title=data["title"], kind="mix", file_path=str(target),
            duration=data["duration"], waveform=data["waveform"], size_bytes=target.stat().st_size,
            is_demo_sample=True, expires_at=timezone.now() + timedelta(days=settings.AUDIO_RETENTION_DAYS))
    except Exception:
        target.unlink(missing_ok=True)
        raise


@transaction.atomic
def refresh_unedited_demo(user, bundle):
    """Replace only the untouched first edition; retain the old export and history."""
    enrollment = StudioDemoEnrollment.objects.filter(user=user).select_related("project").first()
    if not enrollment or not enrollment.project_id:
        return False
    project = enrollment.project
    session = StudioSession.objects.select_for_update().get(project=project)
    if session.revision != 1:
        return False
    assets = {name: project.studio_assets.filter(title=title, kind=kind, is_demo_sample=True,
                                               deleted_at__isnull=True).first()
              for name, (title, kind) in SAMPLES.items()}
    if not all(assets.values()):
        return False
    state = json.loads(json.dumps(bundle["state"]))
    for clip in state["clips"]:
        clip["id"] = str(uuid.uuid4())
        clip["asset_id"] = str(assets[clip["asset_id"]].pk)
    def without_clip_ids(value):
        value = json.loads(json.dumps(value))
        for clip in value["clips"]:
            clip.pop("id", None)
        return value
    if without_clip_ids(validate_state(project, session.state)) == without_clip_ids(validate_state(project, state)):
        return False
    saved = save_state(project, user, 1, state)
    asset_id = uuid.uuid4()
    target = asset_folder(project) / f"{asset_id}.mp3"
    try:
        shutil.copyfile(bundle_folder() / "mix.mp3", target)
        data = bundle["samples"]["mix"]
        mix = StudioAsset.objects.create(id=asset_id, project=project, title=data["title"],
            kind="mix", file_path=str(target), duration=data["duration"], waveform=data["waveform"],
            size_bytes=target.stat().st_size, is_demo_sample=True,
            expires_at=timezone.now() + timedelta(days=settings.AUDIO_RETENTION_DAYS))
        StudioJob.objects.create(project=project, requested_by=user, kind="export", status="succeeded",
            asset=mix, input_data={"state": saved.state, "revision": saved.revision, "format": "mp3"},
            started_at=timezone.now(), finished_at=timezone.now())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return True


@transaction.atomic
def ensure_audio_drama_demo(user, *, bundle=None, restore=False):
    if not user.pk:
        return None
    enrollment = StudioDemoEnrollment.objects.filter(user=user).select_related("project").first()
    if enrollment and (enrollment.project_id or not restore):
        return enrollment.project
    bundle = bundle or read_bundle()
    if not bundle:
        return None
    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
    enrollment, enrolled = StudioDemoEnrollment.objects.get_or_create(user=locked_user)
    if enrollment.project_id or (not enrolled and not restore):
        return enrollment.project
    project = Project.objects.create(owner=locked_user, demo_key=DEMO_KEY, title=DEMO_TITLE, language="de", level="B1")
    from tts.providers import get_tts_configuration
    configuration = get_tts_configuration()
    speech_model = configuration.model if configuration else settings.ELEVENLABS_MODEL_ID
    speakers = []
    for name, color, voice in (("Alex", "forest", "DbwWo4rVEd5NrejHYUnm"), ("Mira", "berry", "JiW03c2Gt43XNUQAumRP")):
        speakers.append(Speaker.objects.create(project=project, name=name, color=color, provider="elevenlabs",
                                               model=speech_model, voice_id=voice, position=len(speakers) + 1))
    ScriptSegment.objects.bulk_create([
        ScriptSegment(project=project, speaker=speakers[speaker], text=text, direction=direction,
                      position=i, pause_after_ms=550)
        for i, (speaker, text, direction) in enumerate(SEGMENTS, start=1)
    ])
    created_files = []
    try:
        folder, assets = asset_folder(project), {}
        for name in (*SAMPLES, "mix"):
            data = bundle["samples"][name]
            asset_id = uuid.uuid4()
            target = folder / f"{asset_id}.mp3"
            created_files.append(target)
            shutil.copyfile(bundle_folder() / f"{name}.mp3", target)
            assets[name] = StudioAsset.objects.create(
                id=asset_id, project=project, title=data["title"], kind=data["kind"], file_path=str(target),
                duration=data["duration"], waveform=data["waveform"], size_bytes=target.stat().st_size,
                is_demo_sample=True, expires_at=timezone.now() + timedelta(days=settings.AUDIO_RETENTION_DAYS))
        state = json.loads(json.dumps(bundle["state"]))
        for clip in state["clips"]:
            clip["id"] = str(uuid.uuid4())
            clip["asset_id"] = str(assets[clip["asset_id"]].pk)
        session = save_state(project, locked_user, 0, state)
        StudioJob.objects.create(project=project, requested_by=locked_user, kind="export", status="succeeded",
                                  asset=assets["mix"], input_data={"state": state, "revision": session.revision, "format": "mp3"},
                                  started_at=timezone.now(), finished_at=timezone.now())
        enrollment.project = project
        enrollment.save(update_fields=["project"])
        project.refresh_from_db()
        return project
    except Exception:
        for path in created_files:
            path.unlink(missing_ok=True)
        raise
