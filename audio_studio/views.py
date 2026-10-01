import json
import tempfile
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from generation.models import AudioAsset
from projects.views import owned_project
from usage_control.services import QuotaExceeded
from usage_control.models import ProviderBudget
from .media import INPUT_FORMATS, StudioError, stored_path
from .models import StudioConfiguration, StudioJob, StudioSession, empty_state
from .providers import provider_ready
from .services import (RevisionConflict, asset_folder, create_asset, create_export, create_generation,
                       identifier, live_assets, queue_failed, save_state)
from .tasks import process_audio


def api_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except RevisionConflict as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except (StudioError, QuotaExceeded) as exc:
            return JsonResponse({"error": str(exc)}, status=422)
    return wrapped


def body(request):
    try:
        value = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise StudioError("Die Anfrage enthält keine gültigen Bearbeitungsdaten.") from None
    if not isinstance(value, dict):
        raise StudioError("Ungültige Anfrage.")
    return value


def asset_data(asset):
    return {"id": str(asset.pk), "title": asset.title, "kind": asset.kind, "duration": asset.duration,
            "waveform": asset.waveform, "expires_at": None if asset.is_demo_sample else asset.expires_at.isoformat(),
            "url": reverse("audio_studio:asset", args=[asset.project_id, asset.pk]),
            "download_url": reverse("audio_studio:asset", args=[asset.project_id, asset.pk]) + "?download=1"}


def job_data(job):
    return {"id": str(job.pk), "kind": job.kind, "status": job.status,
            "label": job.get_status_display(), "error": job.error_message,
            "revision": job.input_data.get("revision"),
            "asset": asset_data(job.asset) if job.asset and job.asset.deleted_at is None
            and (job.asset.is_demo_sample or job.asset.expires_at > timezone.now()) else None}


@require_GET
@login_required
def editor(request, project_id):
    project = owned_project(request, project_id)
    return render(request, "audio_studio/editor.html", {"project": project})


@require_GET
@login_required
def state(request, project_id):
    project = owned_project(request, project_id)
    session = StudioSession.objects.filter(project=project).first()
    config = StudioConfiguration.objects.order_by("pk").first()
    budget = ProviderBudget.objects.filter(provider="elevenlabs", active=True, monthly_credit_limit__gt=0).first()
    speech = AudioAsset.objects.filter(version__project=project, deleted_at__isnull=True,
                                       expires_at__gt=timezone.now()).select_related("version")[:30]
    return JsonResponse({"revision": session.revision if session else 0,
                         "state": session.state if session else empty_state(),
                         "assets": [asset_data(a) for a in live_assets(project)[:200]],
                         "speech": [{"id": str(a.pk), "title": f"Sprachversion {a.version.number}"} for a in speech],
                         "history": [{"number": r.number, "state": r.state, "created_at": r.created_at.isoformat()}
                                     for r in session.revisions.all()[:20]] if session else [],
                         "jobs": [job_data(j) for j in project.studio_jobs.select_related("asset")[:20]],
                         "generation": {kind: {"enabled": provider_ready(config, kind),
                                                "rate": str(getattr(config, f"{kind}_eur_per_minute", 0)),
                                                "credits_per_second": getattr(config, "effects_credits_per_second", 20)
                                                if kind == "effects" else getattr(config, "music_credits_per_minute", 1500) / 60,
                                                "seconds_limit": getattr(config, f"{kind}_seconds_per_user_month", 0)}
                                        for kind in ("music", "effects")},
                         "credit_budget": {"limit": float(budget.spendable_credits),
                                           "remaining": float(max(0, budget.spendable_credits - budget.spent_credits()))}
                         if budget else None})


@require_POST
@login_required
@api_errors
def save(request, project_id):
    project = owned_project(request, project_id)
    data = body(request)
    session = save_state(project, request.user, data.get("revision"), data.get("state"))
    return JsonResponse({"revision": session.revision, "state": session.state})


@require_POST
@login_required
@api_errors
def upload(request, project_id):
    project = owned_project(request, project_id)
    if live_assets(project).count() >= 200:
        raise StudioError("Dieses Projekt enthält bereits 200 Audiodateien.")
    audio = request.FILES.get("audio")
    if not audio or audio.size > settings.AUDIO_STUDIO_MAX_UPLOAD_BYTES:
        raise StudioError("Wählen Sie eine Audiodatei mit höchstens 50 MB.")
    suffix = Path(audio.name).suffix.lower()
    if suffix not in INPUT_FORMATS:
        raise StudioError("Unterstützte Formate: MP3, WAV, OGG, FLAC und M4A.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=asset_folder(project), suffix=suffix, delete=False) as f:
            temporary = Path(f.name)
            for chunk in audio.chunks():
                f.write(chunk)
        asset = create_asset(project, temporary, Path(audio.name).stem, "upload")
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return JsonResponse({"asset": asset_data(asset)}, status=201)


@require_POST
@login_required
@api_errors
def import_speech(request, project_id):
    project = owned_project(request, project_id)
    source_id = identifier(body(request).get("asset_id"))
    source = get_object_or_404(AudioAsset, pk=source_id, version__project=project,
                               deleted_at__isnull=True, expires_at__gt=timezone.now())
    existing = live_assets(project).filter(source_audio=source).first()
    if existing:
        return JsonResponse({"asset": asset_data(existing)})
    if live_assets(project).count() >= 200:
        raise StudioError("Dieses Projekt enthält bereits 200 Audiodateien.")
    asset = create_asset(project, stored_path(source.file_path), f"Sprache · Version {source.version.number}", "speech", source)
    return JsonResponse({"asset": asset_data(asset)}, status=201)


def dispatch(job):
    try:
        process_audio.delay(str(job.pk))
    except Exception:
        queue_failed(job)
    job.refresh_from_db()
    return JsonResponse({"job": job_data(job)}, status=202)


@require_POST
@login_required
@api_errors
def generate(request, project_id):
    project = owned_project(request, project_id)
    if live_assets(project).count() >= 200:
        raise StudioError("Dieses Projekt enthält bereits 200 Audiodateien.")
    return dispatch(create_generation(project, request.user, body(request)))


@require_POST
@login_required
@api_errors
def export(request, project_id):
    project = owned_project(request, project_id)
    data = body(request)
    return dispatch(create_export(project, request.user, data.get("revision"), data.get("format")))


@require_GET
@login_required
def jobs(request, project_id):
    project = owned_project(request, project_id)
    return JsonResponse({"jobs": [job_data(j) for j in project.studio_jobs.select_related("asset")[:20]]})


@require_GET
@login_required
def asset(request, project_id, asset_id):
    project = owned_project(request, project_id)
    audio = get_object_or_404(live_assets(project), pk=asset_id)
    try:
        path = stored_path(audio.file_path)
    except StudioError:
        raise Http404("Audiodatei nicht verfügbar.") from None
    response = FileResponse(path.open("rb"), as_attachment=request.GET.get("download") == "1",
                            filename=f"{project.title}-{audio.title}.{audio.format}",
                            content_type="audio/wav" if audio.format == "wav" else "audio/mpeg")
    response["Cache-Control"] = "private, no-store"
    return response
