from copy import deepcopy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from audio_studio.models import StudioSession
from audio_studio.media import StudioError
from audio_studio.services import live_assets
from projects.models import Project
from projects.views import owned_project
from script_assistant.models import AssistantConfiguration
from script_assistant.workflows import project_payload
from script_assistant.schema import ProposalValidationError
from tts.providers import get_tts_provider, tts_provider_is_configured
from generation.models import AudioAsset
from generation.services import GenerationValidationError

from .forms import PlanItems, PlanSettingsForm, ProductionBriefForm, ScriptLines, WishesForm
from .models import Production
from .planning import ProductionError
from .planning import validate_plan
from .services import authorize, busy, estimate_mix, recover_stale_runs, save_draft, save_plan, select_speech, speech_is_current, start_run


def script_forms(production, data=None):
    payload = production.draft or project_payload(production.project)
    return payload, ScriptLines(data, prefix="script", initial=payload["segments"],
                                form_kwargs={"speaker_names": [speaker["name"] for speaker in payload["speakers"]]})


def plan_forms(production, data=None):
    assets = list(live_assets(production.project).filter(kind__in=("music", "effects")))
    plan = production.plan or {"summary": "", "speech_start": 0, "music_duck_db": 4, "compression": 25, "items": []}
    return PlanSettingsForm(data, prefix="plan", initial=plan), PlanItems(data, prefix="items", initial=plan["items"], form_kwargs={"assets": assets})


def render_detail(request, production, *, lines=None, settings_form=None, items=None, wishes=None, code=200):
    project = production.project
    recover_stale_runs(project)
    run = busy(production)
    payload, default_lines = script_forms(production)
    default_settings, default_items = plan_forms(production)
    session = StudioSession.objects.filter(project=project).first()
    speech = None
    if production.speech_job_id:
        speech = production.speech_job.audio_asset if hasattr(production.speech_job, "audio_asset") else None
    from django.utils import timezone
    if speech and (speech.deleted_at or speech.expires_at <= timezone.now()):
        speech = None
    mix = live_assets(project).filter(pk=production.mix_asset_id).first() if production.mix_asset_id else None
    final = live_assets(project).filter(pk=production.final_asset_id).first() if production.final_asset_id else None
    dirty_script = bool(production.approved_script and not speech_is_current(production))
    dirty_mix = bool(session and mix and session.revision != production.mixed_revision)
    chars = sum(len(segment["text"]) for segment in payload["segments"])
    rate = get_tts_provider().estimated_rate
    config = AssistantConfiguration.objects.filter(active=True).first()
    return render(request, "production/detail.html", {
        "production": production, "project": project, "run": run, "last_run": project.production_runs.first(),
        "script_payload": payload, "lines": lines if lines is not None else default_lines,
        "plan_settings": settings_form if settings_form is not None else default_settings,
        "items": items if items is not None else default_items,
        "wishes": wishes or WishesForm(initial=production.brief),
        "speech": speech, "mix_asset": mix, "final_asset": final,
        "dirty_script": dirty_script, "dirty_mix": dirty_mix,
        "character_count": chars, "speech_cost": round(chars / 1000 * float(rate), 4),
        "mix_estimate": estimate_mix(production), "provider_configured": tts_provider_is_configured(),
        "assistant_configured": bool(config and config.is_configured),
        "history": list(project.production_runs.all()[:12]),
        "audio_versions": AudioAsset.objects.filter(version__project=project, deleted_at__isnull=True, expires_at__gt=timezone.now()).select_related("version")[:8],
    }, status=code)


@login_required
def create(request):
    if request.user.role == request.user.Role.STUDENT:
        raise PermissionDenied
    form = ProductionBriefForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from django.db import transaction
        with transaction.atomic():
            brief = dict(form.cleaned_data)
            project = Project.objects.create(owner=request.user, title="Hörspiel-Entwurf", language=brief["language"], level=brief["level"])
            production = Production.objects.create(project=project, brief=brief)
            start_run(project, request.user, "script", production.revision)
        return redirect("production:detail", project_id=project.pk)
    return render(request, "production/create.html", {"form": form})


@login_required
def detail(request, project_id):
    project = owned_project(request, project_id)
    authorize(project, request.user)
    production, _ = Production.objects.get_or_create(project=project, defaults={"brief": {
        "language": project.language, "level": project.level or "A2", "topic": project.title,
        "format": "dialogue", "duration_seconds": 120, "speaker_count": project.speakers.count() or 2}})
    return render_detail(request, production)


@require_POST
@login_required
def action(request, project_id):
    project = owned_project(request, project_id)
    authorize(project, request.user)
    production = get_object_or_404(Production, project=project)
    kind = request.POST.get("action", "")
    try:
        revision = int(request.POST.get("revision", ""))
        if kind in ("save_script", "apply_script", "speech"):
            payload, lines = script_forms(production, request.POST)
            if not lines.is_valid() or not lines.forms:
                messages.error(request, "Prüfen Sie bitte die markierten Sprechbeiträge.")
                return render_detail(request, production, lines=lines, code=400)
            payload = deepcopy(payload)
            payload["segments"] = [{**form.cleaned_data, "speed": float(form.cleaned_data["speed"])} for form in lines]
            production = save_draft(project, request.user, revision, payload, apply=kind != "save_script")
            if kind == "speech":
                start_run(project, request.user, "speech", production.revision)
            else:
                messages.success(request, "Der Skriptstand wurde gespeichert." if kind == "save_script" else "Das Skript wurde übernommen. Die Stimmen können Sie im Skripteditor prüfen.")
        elif kind == "refine":
            instruction = request.POST.get("instruction", "").strip()
            if not instruction or len(instruction) > 2000:
                raise ProductionError("Beschreiben Sie die gewünschte Änderung mit höchstens 2.000 Zeichen.")
            start_run(project, request.user, kind, revision, {"instruction": instruction})
        elif kind == "plan":
            wishes = WishesForm(request.POST)
            if not wishes.is_valid():
                return render_detail(request, production, wishes=wishes, code=400)
            start_run(project, request.user, kind, revision, wishes.cleaned_data)
        elif kind in ("save_plan", "mix"):
            settings_form, items = plan_forms(production, request.POST)
            if not settings_form.is_valid() or not items.is_valid():
                messages.error(request, "Prüfen Sie bitte die markierten Elemente des Klangplans.")
                return render_detail(request, production, settings_form=settings_form, items=items, code=400)
            plan = {**settings_form.cleaned_data, "items": [{k: v for k, v in form.cleaned_data.items() if k != "DELETE"}
                    for form in items if form.cleaned_data and not form.cleaned_data.get("DELETE")]}
            from .services import approved_audio, speech_asset
            audio = approved_audio(production)
            plan = validate_plan(project, plan, float(audio.duration_seconds or speech_asset(production).duration))
            changed = plan != production.plan
            production = save_plan(project, request.user, revision, plan)
            if kind == "mix" and not changed:
                start_run(project, request.user, "mix", production.revision)
            else:
                messages.success(request, "Der Klangplan wurde gespeichert. Prüfen Sie den aktualisierten Verbrauch und geben Sie anschließend die Mischung frei.")
        elif kind in ("preview", "export", "script"):
            start_run(project, request.user, kind, revision, {"format": request.POST.get("format", "wav")})
        elif kind == "use_speech":
            import uuid
            audio_id = uuid.UUID(request.POST.get("audio_id", ""))
            select_speech(project, request.user, revision, audio_id)
        else:
            raise ProductionError("Diese Aktion ist nicht verfügbar.")
    except (ProductionError, StudioError, GenerationValidationError, ProposalValidationError, ValueError) as exc:
        messages.error(request, str(exc) if isinstance(exc, (ProductionError, StudioError, GenerationValidationError, ProposalValidationError)) else "Der Produktionsstand ist ungültig. Bitte laden Sie die Seite neu.")
    return redirect("production:detail", project_id=project.pk)


@login_required
def status(request, project_id):
    project = owned_project(request, project_id)
    authorize(project, request.user)
    production = get_object_or_404(Production, project=project)
    recover_stale_runs(project)
    run = busy(production)
    message = run.progress if run else "Bereit zur Prüfung."
    if run and run.kind == "speech" and run.result.get("speech_job"):
        job = production.speech_job
        if job:
            message = f"Sprache: {job.parts.filter(status='succeeded').count()} von {job.parts.count()} Abschnitten fertig."
    return JsonResponse({"busy": bool(run), "progress": message or "Der Assistent bereitet die Phase vor.", "revision": production.revision})
