import logging
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from audio_studio.media import StudioError, stored_path
from audio_studio.models import StudioConfiguration, StudioJob, StudioSession
from audio_studio.services import create_asset, create_export, create_generation, live_assets, run_job, save_state
from generation.models import AudioAsset, GenerationJob
from generation.services import GenerationValidationError, create_generation_job, run_generation_job
from generation.services import build_project_snapshot
from projects.models import Project
from script_assistant.models import AssistantProposal
from script_assistant.providers import AssistantProviderError
from script_assistant.schema import ProposalValidationError, validate_script_proposal
from script_assistant.services import apply_proposal, create_proposal, editable_project_snapshot
from script_assistant.workflows import _provider_request, project_payload
from usage_control.services import QuotaExceeded
from tts.providers.base import ProviderError
from tts.models import ProviderVoice

from .models import Production, ProductionRun
from .planning import ProductionError, available_material, build_state, material_key, validate_plan

logger = logging.getLogger(__name__)


def authorize(project, user):
    from projects.views import visible_projects
    if not user.is_active or user.role == user.Role.STUDENT or not visible_projects(user).filter(pk=project.pk).exists():
        raise PermissionDenied


def busy(production):
    return production.project.production_runs.filter(status__in=("queued", "running")).first()


def check_revision(production, revision):
    if busy(production):
        raise ProductionError("Der Assistent arbeitet gerade. Bitte warten Sie auf das Ergebnis.")
    if revision != production.revision:
        raise ProductionError("Der Produktionsstand hat sich geändert. Laden Sie die Seite neu und prüfen Sie den aktuellen Stand.")


def speech_is_current(production):
    return bool(production.approved_script and not production.draft
                and production.approved_script == editable_project_snapshot(production.project))


def _spoken_content(snapshot):
    speakers = {speaker["id"]: speaker for speaker in snapshot.get("speakers", [])}
    return snapshot.get("language"), [(speakers.get(item["speaker_id"], {}).get("voice_id"), item["text"],
            item["direction"], item["pause_after_ms"], float(item.get("speed", 1)),
            speakers.get(item["speaker_id"], {}).get("accent", "")) for item in snapshot.get("segments", [])]


@transaction.atomic
def select_speech(project, user, revision, audio_id):
    project = Project.objects.select_for_update().get(pk=project.pk)
    authorize(project, user)
    production = Production.objects.select_for_update().get(project=project)
    check_revision(production, revision)
    audio = AudioAsset.objects.filter(pk=audio_id, version__project=project, deleted_at__isnull=True, expires_at__gt=timezone.now()).first()
    if not audio or production.draft or _spoken_content(audio.version.snapshot) != _spoken_content(build_project_snapshot(project)):
        raise ProductionError("Diese Sprachfassung passt nicht zum aktuellen Skript und den Stimmen. Bitte übernehmen und erzeugen Sie den gewünschten Stand zuerst.")
    stored_path(audio.file_path)
    production.approved_script = editable_project_snapshot(project)
    production.speech_job = audio.job
    production.approved_audio = None
    production.stage = Production.Stage.SPEECH
    production.mixed_revision = None
    production.revision += 1
    production.save()


def approved_audio(production):
    if not speech_is_current(production):
        raise ProductionError("Das Skript oder eine Stimme wurde geändert. Bitte prüfen und erzeugen Sie zuerst die passende Sprachfassung.")
    audio = production.approved_audio
    if (not audio or audio.version.project_id != production.project_id
            or audio.deleted_at is not None or audio.expires_at <= timezone.now()):
        raise ProductionError("Die freigegebene Sprachfassung ist nicht mehr verfügbar. Bitte erzeugen und prüfen Sie den Hörtext erneut.")
    stored_path(audio.file_path)
    return audio


def speech_asset(production):
    audio = approved_audio(production)
    existing = live_assets(production.project).filter(source_audio=audio).first()
    if existing:
        return existing
    asset = create_asset(production.project, stored_path(audio.file_path), f"Freigegebene Sprache · Version {audio.version.number}", "speech", audio)
    AudioAsset.objects.filter(pk=audio.pk).update(duration_seconds=Decimal(str(asset.duration)))
    return asset


def _apply_draft(production, user):
    if not production.draft:
        return
    old = {speaker.name: speaker for speaker in production.project.speakers.all()}
    old_language = production.project.language
    proposal = create_proposal(production.project, user, production.draft)
    apply_proposal(proposal, AssistantProposal.ApplyMode.REPLACE)
    production.project.refresh_from_db()
    # Retain a teacher's chosen voices when a role keeps its name and language.
    for speaker in production.project.speakers.all():
        previous = old.get(speaker.name)
        selected = production.brief.get("voice_choices", {}).get(speaker.name)
        if selected:
            voice = ProviderVoice.objects.filter(pk=selected, active=True).first()
            if not voice or voice.languages and production.project.language not in voice.languages:
                raise ProductionError("Eine ausgewählte Stimme ist nicht mehr für diese Sprache verfügbar. Bitte wählen Sie die Stimme erneut.")
            speaker.provider, speaker.model, speaker.voice_id = voice.provider, voice.model, voice.voice_id
            speaker.save(update_fields=["provider", "model", "voice_id"])
        elif speaker.name not in production.brief.get("voice_choices", {}) and previous and previous.voice_id and production.draft["language"] == old_language:
            speaker.provider, speaker.model, speaker.voice_id = previous.provider, previous.model, previous.voice_id
            speaker.save(update_fields=["provider", "model", "voice_id"])
    proposal.applied_snapshot = editable_project_snapshot(production.project)
    proposal.save(update_fields=["applied_snapshot"])
    production.draft = {}


@transaction.atomic
def save_draft(project, user, revision, payload, *, apply=False, voice_choices=None):
    project = Project.objects.select_for_update().get(pk=project.pk)
    authorize(project, user)
    production = Production.objects.select_for_update().get(project=project)
    check_revision(production, revision)
    production.draft = validate_script_proposal(payload)
    if voice_choices is not None:
        if set(voice_choices) != {speaker["name"] for speaker in production.draft["speakers"]}:
            raise ProductionError("Die Stimmenauswahl passt nicht zu den Rollen des Entwurfs.")
        for voice_id in voice_choices.values():
            if voice_id:
                voice = ProviderVoice.objects.filter(pk=voice_id, active=True).first()
                if not voice or voice.languages and production.draft["language"] not in voice.languages:
                    raise ProductionError("Eine ausgewählte Stimme ist für die Zielsprache nicht freigegeben.")
        production.brief["voice_choices"] = voice_choices
    if apply:
        _apply_draft(production, user)
    production.stage = Production.Stage.SCRIPT
    production.revision += 1
    production.save()
    return production


@transaction.atomic
def save_plan(project, user, revision, plan):
    project = Project.objects.select_for_update().get(pk=project.pk)
    authorize(project, user)
    production = Production.objects.select_for_update().get(project=project)
    check_revision(production, revision)
    audio = approved_audio(production)
    duration = float(audio.duration_seconds or speech_asset(production).duration)
    plan = validate_plan(project, plan, duration)
    if plan != production.plan:
        production.mixed_revision = None
    production.plan = plan
    production.stage = Production.Stage.PLAN
    production.revision += 1
    production.save()
    return production


def estimate_mix(production):
    config = StudioConfiguration.objects.order_by("pk").first()
    new_items = [item for item in production.plan.get("items", []) if not available_material(production, item)]
    credits = sum(item["duration"] * (config.music_credits_per_minute / 60 if item["kind"] == "music"
                                      else config.effects_credits_per_second) for item in new_items) if config else 0
    return {"credits": round(credits), "new": len(new_items), "reused": len(production.plan.get("items", [])) - len(new_items)}


def _dispatch(run):
    from .tasks import process_production
    try:
        process_production.delay(str(run.pk))
    except Exception:
        ProductionRun.objects.filter(pk=run.pk, status="queued").update(
            status="failed", error_message="Die Hintergrundverarbeitung ist derzeit nicht erreichbar. Bitte starten Sie die Phase erneut.", finished_at=timezone.now())


@transaction.atomic
def start_run(project, user, kind, revision, data=None):
    project = Project.objects.select_for_update().get(pk=project.pk)
    authorize(project, user)
    production = Production.objects.select_for_update().get(project=project)
    check_revision(production, revision)
    if (GenerationJob.objects.filter(version__project=project, status__in=("queued", "running")).exists()
            or project.studio_jobs.filter(status__in=("queued", "running")).exists()):
        raise ProductionError("Für diesen Hörtext läuft bereits ein Audioauftrag. Bitte warten Sie bis zum Abschluss.")
    data = deepcopy(data or {})
    if kind not in dict(ProductionRun._meta.get_field("kind").choices):
        raise ProductionError("Diese Produktionsaktion ist nicht verfügbar.")
    if kind in ("script", "refine"):
        if kind == "script" and project.segments.exists():
            raise ProductionError("Für vorhandene Skripte verwenden Sie bitte den Änderungswunsch.")
        if kind == "refine" and not str(data.get("instruction", "")).strip():
            raise ProductionError("Beschreiben Sie bitte die gewünschte Skriptänderung.")
        if kind == "refine" and not production.draft:
            production.brief["voice_choices"] = {}
            for speaker in project.speakers.all():
                voice = ProviderVoice.objects.filter(provider=speaker.provider, model=speaker.model, voice_id=speaker.voice_id, active=True).first()
                if voice:
                    production.brief["voice_choices"][speaker.name] = str(voice.pk)
        data["current_script"] = production.draft or project_payload(project) if kind == "refine" else {}
        production.stage = Production.Stage.SCRIPT
    elif kind == "speech":
        _apply_draft(production, user)
        production.approved_script = editable_project_snapshot(project)
        data["reuse_job"] = str(production.speech_job_id) if production.speech_job_id else ""
        production.approved_audio = None
        production.mixed_revision = None
        production.stage = Production.Stage.SCRIPT
    elif kind == "plan":
        if production.stage == Production.Stage.SPEECH:
            job = production.speech_job
            audio = AudioAsset.objects.filter(job=job, deleted_at__isnull=True, expires_at__gt=timezone.now()).first() if job else None
            if not job or job.status != "succeeded" or not audio:
                raise ProductionError("Bitte warten Sie auf eine fertige Sprachfassung und hören Sie sie vor der Freigabe an.")
            production.approved_audio = audio
        approved_audio(production)
        for key in ("music_wishes", "effects_wishes"):
            if key in data:
                production.brief[key] = data[key]
        data["previous_plan"] = deepcopy(production.plan)
    elif kind == "mix":
        audio = approved_audio(production)
        production.plan = validate_plan(project, production.plan, float(audio.duration_seconds or speech_asset(production).duration))
        data["plan"] = deepcopy(production.plan)
        session = StudioSession.objects.filter(project=project).first()
        data["studio_revision"] = session.revision if session else 0
        production.stage = Production.Stage.PLAN
    elif kind in ("preview", "export"):
        approved_audio(production)
        session = StudioSession.objects.select_for_update().filter(project=project).first()
        if not session or not session.state.get("clips"):
            raise ProductionError("Es gibt noch keinen gespeicherten Studioschnitt.")
        speech_ids = {clip["asset_id"] for clip in session.state["clips"] if clip["track"] == "speech"}
        if not live_assets(project).filter(pk__in=speech_ids, source_audio=production.approved_audio).exists():
            raise ProductionError("Der Studioschnitt enthält die freigegebene Sprachfassung noch nicht. Bitte erstellen Sie die Mischung auf Grundlage des Klangplans neu.")
        if kind == "export" and (production.mixed_revision != session.revision or not production.mix_asset_id
                                 or not live_assets(project).filter(pk=production.mix_asset_id).exists()):
            raise ProductionError("Der Studioschnitt wurde geändert oder die Vorschau ist abgelaufen. Bitte erzeugen und prüfen Sie zuerst eine neue Mix-Vorschau.")
        if kind == "export" and data.get("format") not in ("mp3", "wav"):
            raise ProductionError("Wählen Sie MP3 oder WAV.")
        data["studio_revision"] = session.revision
    data["base_script"] = editable_project_snapshot(project)
    production.revision += 1
    production.save()
    data["revision"] = production.revision
    run = ProductionRun.objects.create(project=project, requested_by=user, kind=kind, input_data=data)
    transaction.on_commit(lambda: _dispatch(run))
    return run


def _progress(run, message, **result):
    run.result.update(result)
    run.progress = message
    run.save(update_fields=["result", "progress"])


def _check_script(run):
    if run.input_data["base_script"] != editable_project_snapshot(run.project):
        raise ProductionError("Das Skript oder eine Stimme wurde während der Arbeit geändert. Bitte prüfen Sie den Stand und starten Sie die Phase erneut.")


def _export(run, production, revision, fmt):
    _check_script(run)
    job = create_export(run.project, run.requested_by, revision, fmt)
    _progress(run, "Die Audios werden gemeinsam gerendert.", export_job=str(job.pk))
    run_job(job.pk)
    job.refresh_from_db()
    if job.status != "succeeded":
        raise ProductionError(job.error_message)
    session = StudioSession.objects.get(project=run.project)
    if session.revision != revision:
        raise ProductionError("Der Studioschnitt wurde während des Exports verändert. Die erzeugte Fassung bleibt in der Audiobibliothek; bitte prüfen Sie den neuen Stand.")
    return job.asset


def run_production(run_id):
    with transaction.atomic():
        run = ProductionRun.objects.select_for_update().get(pk=run_id)
        if run.status != "queued":
            return
        run.status, run.started_at = "running", timezone.now()
        run.save(update_fields=["status", "started_at"])
    run = ProductionRun.objects.select_related("project", "requested_by").get(pk=run_id)
    try:
        user = get_user_model().objects.get(pk=run.requested_by_id)
        authorize(run.project, user)
        production = Production.objects.get(project=run.project)
        _check_script(run)
        updates = {}
        if run.kind in ("script", "refine"):
            _progress(run, "Das Skript wird vorbereitet.")
            brief = {key: value for key, value in production.brief.items() if key not in ("voice_choices", "initial_voice_choices")}
            request = {"task": "create" if run.kind == "script" else "revise", "brief": brief,
                       "production": True, "current_script": run.input_data.get("current_script", {}),
                       "change_request": run.input_data.get("instruction", "")}
            result = _provider_request(request, user)
            draft = validate_script_proposal(result.payload)
            if draft["language"] != run.project.language:
                raise ProductionError("Der Entwurf hat die vereinbarte Sprache nicht eingehalten. Bitte starten Sie die Skriptphase erneut.")
            draft["level"] = production.brief.get("level", run.project.level)
            if run.kind == "script" and production.brief.get("initial_voice_choices"):
                production.brief["voice_choices"] = {speaker["name"]: production.brief["initial_voice_choices"][str(index)]
                    for index, speaker in enumerate(draft["speakers"], 1) if str(index) in production.brief["initial_voice_choices"]}
            updates = {"draft": draft, "brief": production.brief, "stage": Production.Stage.SCRIPT}
            _progress(run, "Der Skriptentwurf ist bereit zur Prüfung.", draft=draft)
        elif run.kind == "speech":
            _progress(run, "Die freigegebene Sprachfassung wird erzeugt.")
            source = GenerationJob.objects.filter(pk=run.input_data["reuse_job"]).first() if run.input_data.get("reuse_job") else None
            job = create_generation_job(run.project, user, reuse_job=source)
            Production.objects.filter(pk=production.pk).update(speech_job=job)
            _progress(run, "Die Sprachabschnitte werden erzeugt und zusammengefügt.", speech_job=str(job.pk))
            run_generation_job(job.pk)
            updates = {"stage": Production.Stage.SPEECH}
        elif run.kind == "plan":
            _progress(run, "Musik und Geräusche werden für die geprüfte Sprachfassung geplant.")
            speech = speech_asset(production)
            library = [{"asset_id": str(a.pk), "title": a.title, "kind": a.kind, "duration": a.duration}
                       for a in live_assets(run.project).filter(kind__in=("music", "effects"))[:100]]
            result = _provider_request({"task": "sound_plan", "brief": production.brief,
                "speech_duration": speech.duration, "script": project_payload(run.project), "library": library,
                "previous_plan": run.input_data["previous_plan"], "change_request": run.input_data.get("instruction", "")}, user)
            plan = validate_plan(run.project, result.payload, speech.duration)
            updates = {"plan": plan, "stage": Production.Stage.PLAN}
            _progress(run, "Der Klangplan ist bereit zur Prüfung.", plan=plan)
        elif run.kind == "mix":
            production.plan = run.input_data["plan"]
            speech = speech_asset(production)
            assets = []
            for index, item in enumerate(production.plan["items"], 1):
                _check_script(run)
                _progress(run, f"Musik und Geräusche: Element {index} von {len(production.plan['items'])}.")
                asset = available_material(production, item)
                if not asset:
                    job = create_generation(run.project, user, {"kind": item["kind"], "prompt": item["prompt"],
                                                              "duration": item["duration"], "loop": item["loop"]})
                    _progress(run, run.progress, last_material_job=str(job.pk))
                    run_job(job.pk)
                    job.refresh_from_db()
                    if job.status != "succeeded":
                        raise ProductionError(job.error_message)
                    asset = job.asset
                    asset.title = item["title"]
                    asset.save(update_fields=["title"])
                    production.materials[material_key(item)] = str(asset.pk)
                    Production.objects.filter(pk=production.pk).update(materials=production.materials)
                assets.append(asset)
            _check_script(run)
            state = build_state(production, speech, assets)
            session = save_state(run.project, user, run.input_data["studio_revision"], state)
            asset = _export(run, production, session.revision, "mp3")
            updates = {"mix_asset": asset, "mixed_revision": session.revision, "stage": Production.Stage.MIX}
        else:
            fmt = "mp3" if run.kind == "preview" else run.input_data["format"]
            asset = _export(run, production, run.input_data["studio_revision"], fmt)
            if run.kind == "preview":
                updates = {"mix_asset": asset, "mixed_revision": run.input_data["studio_revision"], "stage": Production.Stage.MIX}
            else:
                updates = {"final_asset": asset, "stage": Production.Stage.COMPLETE}
        with transaction.atomic():
            Project.objects.select_for_update().get(pk=run.project_id)
            production = Production.objects.select_for_update().get(project=run.project)
            current_run = ProductionRun.objects.select_for_update().get(pk=run.pk)
            if current_run.status != "running" or production.revision != run.input_data["revision"]:
                raise ProductionError("Der Produktionsstand ist inzwischen überholt. Bitte prüfen Sie die vorhandenen Ergebnisse.")
            _check_script(run)
            for key, value in updates.items():
                setattr(production, key, value)
            production.revision += 1
            production.save()
            run.status, run.progress, run.finished_at = "succeeded", "Bereit zur Prüfung.", timezone.now()
            run.save(update_fields=["status", "progress", "finished_at", "result"])
    except Exception as exc:
        safe = isinstance(exc, (ProductionError, StudioError, GenerationValidationError, ProviderError, AssistantProviderError, ProposalValidationError, QuotaExceeded))
        message = str(exc) if safe else "Die Produktion konnte nicht abgeschlossen werden. Der bisherige Stand bleibt erhalten. Bitte prüfen Sie die Konfiguration und versuchen Sie es erneut."
        if not safe:
            logger.exception("Production run %s failed", run.pk)
        run.status, run.error_message, run.finished_at = "failed", message[:500], timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at", "result"])


def recover_stale_runs(project=None):
    cutoff = timezone.now() - timedelta(minutes=35)
    runs = ProductionRun.objects.filter(status__in=("queued", "running"), created_at__lt=cutoff)
    if project is not None:
        runs = runs.filter(project=project)
    for run in runs:
        with transaction.atomic():
            locked = ProductionRun.objects.select_for_update().get(pk=run.pk)
            if locked.status not in ("queued", "running"):
                continue
            for model, key in ((GenerationJob, "speech_job"), (StudioJob, "last_material_job"), (StudioJob, "export_job")):
                if locked.result.get(key):
                    model.objects.filter(pk=locked.result[key], status__in=("queued", "running")).update(
                        status="failed", error_message="Die Verarbeitung wurde unterbrochen. Bitte prüfen Sie den Produktionsstand.", finished_at=timezone.now())
            locked.status, locked.finished_at = "failed", timezone.now()
            locked.error_message = "Die Verarbeitung wurde unterbrochen. Vorhandene Ergebnisse bleiben erhalten. Ein erneuter Versuch kann zusätzliche Credits verbrauchen."
            locked.save(update_fields=["status", "finished_at", "error_message"])
