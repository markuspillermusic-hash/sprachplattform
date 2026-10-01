"""Project content lifecycle; paid usage survives content deletion."""
import logging
import shutil
import uuid
from copy import deepcopy
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audio_studio.media import StudioError, stored_path
from audio_studio.models import StudioAsset, StudioJob, StudioRevision, StudioSession
from audio_studio.services import live_assets, validate_state
from generation.models import AudioAsset, GenerationJob, GenerationPart, ProjectVersion
from .models import Project

logger = logging.getLogger(__name__)


class ProjectContentError(ValueError):
    pass


def _check_idle(project):
    if (GenerationJob.objects.filter(version__project=project, status__in=("queued", "running")).exists()
            or project.studio_jobs.filter(status__in=("queued", "running")).exists()):
        raise ProjectContentError("Für diesen Hörtext läuft noch eine Audioerzeugung oder ein Export. Bitte warten Sie bis zum Abschluss und versuchen Sie es dann erneut.")


def _copy_file(raw, folder, created_files):
    source = stored_path(raw)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{uuid.uuid4()}{source.suffix}"
    created_files.append(target)
    shutil.copyfile(source, target)
    return str(target)


def _remap_state(state, asset_map):
    state = deepcopy(state)
    for clip in state["clips"]:
        if clip["asset_id"] not in asset_map:
            raise ProjectContentError("Ein verwendeter Audioclip ist abgelaufen oder fehlt. Bitte ersetzen oder entfernen Sie ihn vor dem Duplizieren.")
        clip["asset_id"] = str(asset_map[clip["asset_id"]].pk)
    return state


def duplicate_project(project, owner=None):
    from .services import _duplicate_script
    created_files = []
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update().get(pk=project.pk)
            _check_idle(project)
            session = StudioSession.objects.select_for_update().filter(project=project).first()
            duplicate = _duplicate_script(project, owner=owner)
            folder = Path(settings.AUDIO_STORAGE_ROOT).resolve() / "studio" / str(duplicate.pk)
            speech_map = {}
            for audio in AudioAsset.objects.filter(version__project=project, deleted_at__isnull=True,
                                                    expires_at__gt=timezone.now()).select_related("version", "job"):
                version, _ = ProjectVersion.objects.get_or_create(
                    project=duplicate, number=audio.version.number,
                    defaults={"snapshot": deepcopy(audio.version.snapshot), "created_by": duplicate.owner})
                job = GenerationJob.objects.create(
                    version=version, requested_by=duplicate.owner, status="succeeded",
                    provider=audio.job.provider, model=audio.job.model,
                    character_count=audio.job.character_count, estimated_cost_eur=0,
                    actual_cost_eur=0, provider_credit_count=0, is_copy=True, finished_at=timezone.now())
                # Copies remain playable in the ordinary speech editor, without new provider usage.
                speech_map[audio.pk] = AudioAsset.objects.create(
                    version=version, job=job, file_path=_copy_file(audio.file_path, folder, created_files),
                    format=audio.format, duration_seconds=audio.duration_seconds, size_bytes=audio.size_bytes,
                    expires_at=audio.expires_at)
                for part in audio.job.parts.all():
                    GenerationPart.objects.create(
                        job=job, position=part.position, status="succeeded", input_data=deepcopy(part.input_data),
                        character_count=part.character_count, pause_after_ms=part.pause_after_ms)
            asset_map = {}
            for asset in live_assets(project):
                asset_map[str(asset.pk)] = StudioAsset.objects.create(
                    project=duplicate, title=asset.title, kind=asset.kind,
                    file_path=_copy_file(asset.file_path, folder, created_files),
                    original_path=_copy_file(asset.original_path, folder, created_files) if asset.original_path else "",
                    format=asset.format, duration=asset.duration, size_bytes=asset.size_bytes,
                    waveform=deepcopy(asset.waveform), source_audio=speech_map.get(asset.source_audio_id),
                    expires_at=asset.expires_at, is_demo_sample=asset.is_demo_sample)
            if session:
                state = validate_state(duplicate, _remap_state(session.state, asset_map))
                copied_session = StudioSession.objects.create(project=duplicate, state=state, revision=session.revision)
                for revision in session.revisions.all():
                    try:
                        previous_state = validate_state(duplicate, _remap_state(revision.state, asset_map))
                    except (ProjectContentError, StudioError):
                        # Old history can refer to expired audio; the current timeline must be complete.
                        continue
                    StudioRevision.objects.create(session=copied_session, number=revision.number,
                                                  state=previous_state, created_by=duplicate.owner)
            return duplicate
    except Exception as exc:
        for path in created_files:
            path.unlink(missing_ok=True)
        if isinstance(exc, (OSError, StudioError)):
            raise ProjectContentError("Die Audiodateien konnten nicht vollständig kopiert werden. Bitte prüfen Sie die verfügbaren Clips und versuchen Sie es erneut.") from exc
        raise


def _delete_unreferenced_files(paths):
    root = Path(settings.AUDIO_STORAGE_ROOT).resolve()
    # Some older demos may share files. Preserve any path still used by another project.
    referenced = set()
    for raw in AudioAsset.objects.values_list("file_path", flat=True):
        if raw:
            referenced.add(Path(raw).resolve())
    for file_path, original_path in StudioAsset.objects.values_list("file_path", "original_path"):
        referenced.update(Path(raw).resolve() for raw in (file_path, original_path) if raw)
    for raw in GenerationPart.objects.exclude(audio_path="").values_list("audio_path", flat=True):
        referenced.add(Path(raw).resolve())
    for raw in paths:
        path = Path(raw).resolve()
        if path == root or not path.is_relative_to(root) or path in referenced:
            continue
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            logger.exception("Could not remove project audio file %s", path)


@transaction.atomic
def delete_project(project):
    project = Project.objects.select_for_update().get(pk=project.pk)
    _check_idle(project)
    # Lock the timeline in the same order as export/duplicate.
    list(StudioSession.objects.select_for_update().filter(project=project))
    jobs = GenerationJob.objects.filter(version__project=project)
    paths = set(AudioAsset.objects.filter(version__project=project).values_list("file_path", flat=True))
    paths.update(GenerationPart.objects.filter(job__in=jobs).exclude(audio_path="").values_list("audio_path", flat=True))
    for file_path, original_path in project.studio_assets.values_list("file_path", "original_path"):
        paths.update(raw for raw in (file_path, original_path) if raw)
    # Keep duration/cost records for quotas, but erase script, prompts and render snapshots.
    GenerationPart.objects.filter(job__in=jobs).delete()
    jobs.update(error_message="", provider_request_ids=[])
    project.studio_jobs.update(input_data={}, error_message="")
    project.delete()
    transaction.on_commit(lambda: _delete_unreferenced_files(paths))
