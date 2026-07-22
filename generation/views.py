from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from projects.views import owned_project, visible_projects

from .models import AudioAsset, GenerationJob
from .services import GenerationValidationError, UsageLimitExceeded, create_generation_job
from .tasks import generate_audio


@require_POST
@login_required
def start_generation(request, project_id):
    project = owned_project(request, project_id)
    if not settings.ELEVENLABS_API_KEY:
        messages.error(request, "Der ElevenLabs-Zugang ist noch nicht serverseitig konfiguriert.")
        return redirect("projects:editor", project_id=project.pk)
    try:
        job = create_generation_job(project, request.user)
    except (GenerationValidationError, UsageLimitExceeded) as exc:
        messages.error(request, str(exc))
        return redirect("projects:editor", project_id=project.pk)
    try:
        generate_audio.delay(str(job.pk))
    except Exception:
        job.status = GenerationJob.Status.FAILED
        job.error_message = "Die Hintergrundverarbeitung ist vorübergehend nicht erreichbar."
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_message", "finished_at"])
        messages.error(request, job.error_message)
    else:
        messages.success(request, "Die Audioerzeugung wurde gestartet.")
    return redirect("projects:editor", project_id=project.pk)


@require_POST
@login_required
def retry_generation(request, job_id):
    job = get_object_or_404(
        GenerationJob,
        pk=job_id,
        version__project__in=visible_projects(request.user),
    )
    if job.status != GenerationJob.Status.FAILED:
        messages.error(request, "Nur fehlgeschlagene Aufträge können erneut gestartet werden.")
    else:
        job.status = GenerationJob.Status.QUEUED
        job.error_message = ""
        job.finished_at = None
        job.save(update_fields=["status", "error_message", "finished_at"])
        generate_audio.delay(str(job.pk))
        messages.success(request, "Fehlgeschlagene Teile werden erneut versucht.")
    return redirect("projects:editor", project_id=job.version.project_id)


@require_GET
@login_required
def job_status(request, job_id):
    job = get_object_or_404(
        GenerationJob,
        pk=job_id,
        version__project__in=visible_projects(request.user),
    )
    completed = job.parts.filter(status="succeeded").count()
    return JsonResponse(
        {
            "id": str(job.pk),
            "status": job.status,
            "status_label": job.get_status_display(),
            "completed_parts": completed,
            "total_parts": job.parts.count(),
            "error": job.error_message,
        }
    )


def _get_audio_asset(request, asset_id):
    asset = get_object_or_404(
        AudioAsset.objects.select_related("version__project"),
        pk=asset_id,
        version__project__in=visible_projects(request.user),
        deleted_at__isnull=True,
    )
    if asset.expires_at <= timezone.now():
        raise Http404("Die Audiodatei ist abgelaufen.")
    path = Path(asset.file_path).resolve()
    root = Path(settings.AUDIO_STORAGE_ROOT).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise Http404("Audiodatei nicht verfügbar.")
    return asset, path


@require_GET
@login_required
def play_audio(request, asset_id):
    _, path = _get_audio_asset(request, asset_id)
    return FileResponse(path.open("rb"), content_type="audio/mpeg")


@require_GET
@login_required
def download_audio(request, asset_id):
    asset, path = _get_audio_asset(request, asset_id)
    filename = f"{asset.version.project.title}-v{asset.version.number}.mp3"
    return FileResponse(path.open("rb"), as_attachment=True, filename=filename, content_type="audio/mpeg")
