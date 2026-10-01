import math
import shutil
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from projects.models import Project

from usage_control.models import UsageEvent
from usage_control.services import commit_usage, reserve_usage, release_usage
from .media import StudioError, audible_tracks, normalize, render_mix, stored_path
from .models import StudioAsset, StudioConfiguration, StudioJob, StudioRevision, StudioSession
from .mixing import MIX_RANGES, mix_settings
from .providers import ElevenLabsAudioProvider, ProviderRejected, provider_ready

TRACKS = ("speech", "music", "effects")


class RevisionConflict(StudioError):
    pass


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise StudioError("Zeit- und Lautstärkewerte liegen außerhalb des zulässigen Bereichs.")
    return round(value, 6)


def identifier(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise StudioError("Ungültiger Clip oder ungültige Audiodatei.") from None


def live_assets(project):
    return StudioAsset.objects.filter(project=project, deleted_at__isnull=True).filter(
        Q(is_demo_sample=True) | Q(expires_at__gt=timezone.now()))


def validate_state(project, state):
    if not isinstance(state, dict) or not isinstance(state.get("clips"), list) or not isinstance(state.get("tracks"), dict):
        raise StudioError("Der Bearbeitungsstand ist unvollständig.")
    if len(state["clips"]) > settings.AUDIO_STUDIO_MAX_CLIPS:
        raise StudioError("Pro Bearbeitungsstand sind höchstens 60 Clips möglich.")
    if type(state.get("ducking")) is not bool:
        raise StudioError("Die Musikabsenkung muss ein- oder ausgeschaltet sein.")
    options = {}
    for key in ("effects_ducking", "speech_compression"):
        value = state.get(key, False)
        if type(value) is not bool:
            raise StudioError("Die Klangoptionen müssen ein- oder ausgeschaltet sein.")
        options[key] = value
    if not isinstance(state.get("mix", {}), dict):
        raise StudioError("Die Klangregler sind ungültig.")
    mix = {key: number(value, *MIX_RANGES[key]) for key, value in mix_settings(state).items()
           if key in MIX_RANGES}
    tracks = {}
    for name in TRACKS:
        track = state["tracks"].get(name)
        if not isinstance(track, dict) or type(track.get("mute")) is not bool or type(track.get("solo")) is not bool:
            raise StudioError("Die Spureinstellungen sind unvollständig.")
        tracks[name] = {"mute": track["mute"], "solo": track["solo"], "gain_db": number(track.get("gain_db"), -60, 12)}
    assets = {str(a.pk): a for a in live_assets(project)}
    clips, ids = [], set()
    for item in state["clips"]:
        if not isinstance(item, dict):
            raise StudioError("Ungültiger Audioclip.")
        clip_id, asset_id = identifier(item.get("id")), identifier(item.get("asset_id"))
        if clip_id in ids or asset_id not in assets or item.get("track") not in TRACKS:
            raise StudioError("Ein Clip ist doppelt oder seine Audiodatei ist abgelaufen. Entfernen Sie ihn oder fügen Sie die Datei erneut hinzu.")
        ids.add(clip_id)
        clip = {"id": clip_id, "asset_id": asset_id, "track": item["track"]}
        for key in ("start", "trim_start", "trim_end", "fade_in", "fade_out"):
            clip[key] = number(item.get(key), 0, settings.AUDIO_STUDIO_MAX_DURATION)
        clip["gain_db"] = number(item.get("gain_db"), -60, 12)
        length = clip["trim_end"] - clip["trim_start"]
        if (length < .01 or clip["trim_end"] > assets[asset_id].duration + .001
                or clip["start"] + length > settings.AUDIO_STUDIO_MAX_DURATION
                or clip["fade_in"] + clip["fade_out"] > length + .000001):
            raise StudioError("Schnittgrenzen und Fades müssen innerhalb des Clips liegen. Die Gesamtdauer darf 30 Minuten nicht überschreiten.")
        clips.append(clip)
    return {"clips": clips, "tracks": tracks, "ducking": mix["music_duck_db"] > 0,
            **options, "effects_ducking": mix["effects_duck_db"] > 0,
            "speech_compression": mix["compression"] > 0, "mix": mix}


@transaction.atomic
def save_state(project, user, revision, state):
    Project.objects.select_for_update().get(pk=project.pk)
    session, _ = StudioSession.objects.get_or_create(project=project)
    session = StudioSession.objects.select_for_update().get(pk=session.pk)
    if type(revision) is not int or revision != session.revision:
        raise RevisionConflict("Der Hörtext wurde in einem anderen Fenster bearbeitet. Laden Sie den aktuellen Stand neu; Ihre Änderungen bleiben bis dahin im Fenster.")
    session.state = validate_state(project, state)
    session.revision += 1
    session.save()
    StudioRevision.objects.create(session=session, number=session.revision, state=session.state, created_by=user)
    return session


def asset_folder(project):
    root = Path(settings.AUDIO_STORAGE_ROOT).resolve() / "studio" / str(project.pk)
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_asset(project, source, title, kind, source_audio=None):
    asset_id = uuid.uuid4()
    target = asset_folder(project) / f"{asset_id}.mp3"
    original = asset_folder(project) / f"{asset_id}-original{Path(source).suffix.lower()}"
    try:
        shutil.copyfile(source, original)
        duration, peaks = normalize(original, target, target_peak=.6 if kind == "effects" else None)
        expires = timezone.now() + timedelta(days=settings.AUDIO_RETENTION_DAYS)
        if source_audio:
            expires = min(expires, source_audio.expires_at)
        return StudioAsset.objects.create(project=project, title=title[:120], kind=kind,
                                          file_path=str(target), original_path=str(original), duration=duration, waveform=peaks,
                                          size_bytes=target.stat().st_size, expires_at=expires, source_audio=source_audio)
    except Exception:
        target.unlink(missing_ok=True)
        original.unlink(missing_ok=True)
        raise


@transaction.atomic
def create_generation(project, user, data):
    Project.objects.select_for_update().get(pk=project.pk)
    config = StudioConfiguration.objects.order_by("pk").first()
    kind = data.get("kind")
    if kind not in ("music", "effects") or not provider_ready(config, kind):
        raise StudioError("Diese Audioerzeugung ist noch nicht freigegeben. Die Administration muss Zugang, Tarifwert und Kontingent einrichten.")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4100:
        raise StudioError("Beschreiben Sie das gewünschte Audio mit höchstens 4.100 Zeichen.")
    duration = number(data.get("duration"), 3 if kind == "music" else .5, 600 if kind == "music" else 30)
    loop = data.get("loop", False)
    if type(loop) is not bool:
        raise StudioError("Ungültige Loop-Einstellung.")
    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
    month = timezone.localdate().replace(day=1)
    used = StudioJob.objects.filter(requested_by=user, kind=kind,
                                    usage_event__status__in=(UsageEvent.Status.RESERVED, UsageEvent.Status.COMMITTED),
                                    created_at__date__gte=month).aggregate(total=Sum("duration"))["total"] or 0
    if used + duration > getattr(config, f"{kind}_seconds_per_user_month"):
        raise StudioError("Ihr monatliches Kontingent für diese Audioart ist erreicht.")
    if project.studio_jobs.filter(status__in=("queued", "running")).count() >= 3:
        raise StudioError("Bitte warten Sie, bis ein laufender Audioauftrag fertig ist.")
    model = config.music_model if kind == "music" else "eleven_text_to_sound_v2"
    cost = (Decimal(str(duration)) / 60 * getattr(config, f"{kind}_eur_per_minute")).quantize(Decimal("0.000001"))
    event = reserve_usage(user=locked_user, provider=UsageEvent.Provider.ELEVENLABS,
                          feature=UsageEvent.Feature.MUSIC if kind == "music" else UsageEvent.Feature.SOUND_EFFECTS,
                          model=model, estimated_cost=cost, currency="EUR",
                          estimated_credits=Decimal(str(duration)) / 60 * config.music_credits_per_minute
                          if kind == "music" else Decimal(str(duration)) * config.effects_credits_per_second)
    job = StudioJob.objects.create(project=project, requested_by=user, kind=kind, duration=duration, usage_event=event,
                                   input_data={"prompt": prompt.strip(), "duration": duration, "loop": loop,
                                               "model": model, "configuration_id": config.pk})
    event.reference = f"studio:{job.pk}"
    event.save(update_fields=("reference",))
    return job


@transaction.atomic
def create_export(project, user, revision, output_format):
    Project.objects.select_for_update().get(pk=project.pk)
    session = StudioSession.objects.select_for_update().filter(project=project).first()
    if not session or type(revision) is not int or revision != session.revision:
        raise RevisionConflict("Speichern Sie den aktuellen Bearbeitungsstand vor dem Export.")
    if output_format not in ("mp3", "wav"):
        raise StudioError("Wählen Sie MP3 oder WAV als Exportformat.")
    state = validate_state(project, session.state)
    if not any(c["track"] in audible_tracks(state) for c in state["clips"]):
        raise StudioError("Fügen Sie zuerst mindestens einen hörbaren Clip hinzu.")
    if project.studio_jobs.filter(kind="export", status__in=("queued", "running")).exists():
        raise StudioError("Für dieses Projekt läuft bereits ein Export.")
    return StudioJob.objects.create(project=project, requested_by=user, kind="export",
                                   input_data={"state": state, "revision": revision, "format": output_format})


def queue_failed(job):
    # A broker error may occur after acceptance. Cancel only still-queued jobs;
    # a worker that already claimed the job must retain its reservation.
    with transaction.atomic():
        locked = StudioJob.objects.select_for_update().get(pk=job.pk)
        if locked.status != StudioJob.Status.QUEUED:
            return
        locked.status = StudioJob.Status.FAILED
        locked.error_message = "Die Hintergrundverarbeitung ist nicht erreichbar. Starten Sie den Auftrag später erneut."
        locked.finished_at = timezone.now()
        locked.save()
        if locked.usage_event_id:
            release_usage(locked.usage_event)


def run_job(job_id, provider=None):
    with transaction.atomic():
        job = StudioJob.objects.select_for_update().get(pk=job_id)
        if job.status != StudioJob.Status.QUEUED:
            return
        job.status = StudioJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=("status", "started_at"))
    temporary, target = None, None
    attempted = False
    try:
        folder = asset_folder(job.project)
        if job.kind == "export":
            state = validate_state(job.project, job.input_data["state"])
            assets = {str(a.pk): a for a in live_assets(job.project)}
            fmt = job.input_data["format"]
            target = folder / f"mix-{job.pk}.{fmt}"
            duration, peaks = render_mix(state, assets, target, fmt)
            asset = StudioAsset.objects.create(project=job.project, kind="mix", title=f"Mix · Stand {job.input_data['revision']}",
                                               file_path=str(target), format=fmt, duration=duration, waveform=peaks,
                                               size_bytes=target.stat().st_size,
                                               expires_at=timezone.now() + timedelta(days=settings.AUDIO_RETENTION_DAYS))
        else:
            config = StudioConfiguration.objects.get(pk=job.input_data["configuration_id"])
            if not provider_ready(config, job.kind):
                raise ProviderRejected("Diese Audioerzeugung wurde inzwischen deaktiviert.")
            provider = provider or ElevenLabsAudioProvider(config)
            attempted = True
            job.provider_attempted = True
            job.save(update_fields=("provider_attempted",))
            result = provider.generate(job.kind, job.input_data)
            job.provider_received = True
            job.provider_request_id = result.request_id
            job.save(update_fields=("provider_received", "provider_request_id"))
            # Generation is billable even if local normalization later fails.
            commit_usage(job.usage_event, provider_credit_count=result.credits or 0,
                         provider_request_id=result.request_id)
            temporary = folder / f"source-{job.pk}.mp3"
            temporary.write_bytes(result.audio)
            asset = create_asset(job.project, temporary, job.input_data["prompt"], job.kind)
        job.asset = asset
        job.status = StudioJob.Status.SUCCEEDED
        job.error_message = ""
    except Exception as exc:
        job.status = StudioJob.Status.FAILED
        job.error_message = (str(exc) if isinstance(exc, StudioError)
                             else "Die Audioverarbeitung ist fehlgeschlagen. Prüfen Sie die Serverkonfiguration.")[:500]
        if job.usage_event_id and not job.provider_received:
            if not attempted or isinstance(exc, ProviderRejected):
                release_usage(job.usage_event)
            else:
                # Unknown completion after a timeout: conservatively account
                # for the request, never automatically send it twice.
                commit_usage(job.usage_event)
        if target:
            target.unlink(missing_ok=True)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
        job.finished_at = timezone.now()
        job.save(update_fields=("asset", "status", "error_message", "finished_at"))


def recover_stale_jobs():
    """Called by periodic maintenance after the 15-minute worker time limit."""
    stale = StudioJob.objects.filter(status=StudioJob.Status.RUNNING,
                                    started_at__lt=timezone.now() - timedelta(minutes=20))
    for job_id in stale.values_list("pk", flat=True):
        with transaction.atomic():
            job = StudioJob.objects.select_for_update().get(pk=job_id)
            if job.status != StudioJob.Status.RUNNING:
                continue
            job.status = StudioJob.Status.FAILED
            job.error_message = "Die Hintergrundverarbeitung wurde unterbrochen. Prüfen Sie den Anbieterstatus vor einer neuen Generierung."
            job.finished_at = timezone.now()
            job.save(update_fields=("status", "error_message", "finished_at"))
            if job.usage_event_id and job.usage_event.status == UsageEvent.Status.RESERVED:
                if job.provider_attempted:
                    commit_usage(job.usage_event)
                else:
                    release_usage(job.usage_event)
