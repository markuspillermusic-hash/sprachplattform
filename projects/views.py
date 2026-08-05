from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models.deletion import RestrictedError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from generation.models import GenerationJob, UsageLedger
from script_assistant.forms import AssistantBriefForm
from script_assistant.models import AssistantConfiguration, AssistantProposal
from script_assistant.providers import AssistantProviderError, AssistantProviderNotConfigured
from script_assistant.schema import ProposalValidationError
from script_assistant.workflows import begin_assisted_project
from usage_control.services import QuotaExceeded
from tts.providers import tts_provider_is_configured
from .forms import (
    ProjectCreateForm,
    ProjectMetaForm,
    SegmentForm,
    SpeakerForm,
    compatible_voice_queryset,
    user_favorite_voice_ids,
)
from .models import Project, ScriptSegment, Speaker
from .services import duplicate_project, ensure_demo_projects, move_segment, next_position


def visible_projects(user):
    queryset = Project.objects.all()
    if user.is_staff or user.role == user.Role.ADMIN:
        return queryset
    return queryset.filter(owner=user)


def owned_project(request, project_id):
    return get_object_or_404(visible_projects(request.user), pk=project_id)


def form_error_summary(form):
    details = []
    for field_name, errors in form.errors.items():
        label = form.fields[field_name].label if field_name in form.fields else "Eingabe"
        details.extend(f"{label}: {error}" for error in errors)
    return " ".join(details)


@login_required
def project_list(request):
    ensure_demo_projects(request.user)
    projects = visible_projects(request.user).prefetch_related("segments", "speakers")
    return render(request, "projects/project_list.html", {"projects": projects})


@login_required
def project_create(request):
    assistant_configuration = AssistantConfiguration.objects.order_by("pk").first()
    selected_mode = request.POST.get("mode") or request.GET.get("mode", "")
    if request.method == "POST" and not selected_mode and "title" in request.POST:
        selected_mode = "manual"
    form = ProjectCreateForm(request.POST or None) if selected_mode == "manual" else ProjectCreateForm()
    assistant_form = (
        AssistantBriefForm(request.POST or None)
        if selected_mode == "assistant"
        else AssistantBriefForm(initial={"level": Project.Level.A2})
    )
    if request.method == "POST" and selected_mode == "manual" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        messages.success(request, "Der Hörtext wurde angelegt.")
        return redirect("projects:editor", project_id=project.pk)
    if request.method == "POST" and selected_mode == "assistant" and assistant_form.is_valid():
        brief = dict(assistant_form.cleaned_data)
        brief["creation_mode"] = "new"
        try:
            conversation = begin_assisted_project(request.user, brief)
        except (AssistantProviderError, AssistantProviderNotConfigured, ProposalValidationError, QuotaExceeded) as exc:
            messages.error(request, str(exc))
        else:
            return redirect("script_assistant:conversation", conversation_id=conversation.pk)
    return render(
        request,
        "projects/project_create.html",
        {
            "form": form,
            "assistant_form": assistant_form,
            "selected_mode": selected_mode,
            "assistant_configuration": assistant_configuration,
            "assistant_configured": bool(
                assistant_configuration and assistant_configuration.is_configured
            ),
        },
    )


@login_required
def project_editor(request, project_id):
    project = owned_project(request, project_id)
    segments = list(project.segments.select_related("speaker"))
    speakers = list(project.speakers.all())
    favorite_voice_ids = user_favorite_voice_ids(request.user)
    speaker_form_voice_queryset = compatible_voice_queryset(
        project,
        favorite_ids=favorite_voice_ids,
    )
    speaker_form_voices = list(speaker_form_voice_queryset)
    month_start = timezone.localdate().replace(day=1)
    usage_used = UsageLedger.objects.filter(
        user=request.user,
        billing_period=month_start,
    ).aggregate(total=Sum("character_count"))["total"] or 0
    last_applied_proposal = project.assistant_proposals.filter(
        status=AssistantProposal.Status.APPLIED,
    ).first()
    assistant_configuration = AssistantConfiguration.objects.order_by("pk").first()
    return render(
        request,
        "projects/editor.html",
        {
            "project": project,
            "project_form": ProjectMetaForm(instance=project, prefix="project"),
            "speaker_form": SpeakerForm(
                project=project,
                voice_queryset=speaker_form_voice_queryset,
                favorite_ids=favorite_voice_ids,
            ),
            "speakers_with_forms": [
                (
                    speaker,
                    SpeakerForm(
                        instance=speaker,
                        project=project,
                        prefix=str(speaker.pk),
                        voice_queryset=speaker_form_voice_queryset,
                        favorite_ids=favorite_voice_ids,
                    ),
                    next(
                        (
                            voice
                            for voice in speaker_form_voices
                            if voice.provider == speaker.provider
                            and voice.model == speaker.model
                            and voice.voice_id == speaker.voice_id
                        ),
                        None,
                    ),
                )
                for speaker in speakers
            ],
            "voice_preview_data": {
                str(voice.pk): {
                    "name": voice.display_name,
                    "url": voice.preview_url,
                }
                for voice in speaker_form_voices
                if voice.preview_url
            },
            "segments_with_forms": [
                (segment, SegmentForm(instance=segment, project=project, prefix=str(segment.pk)))
                for segment in segments
            ],
            "latest_jobs": GenerationJob.objects.filter(version__project=project).prefetch_related("parts")[:5],
            "usage_used": usage_used,
            "usage_limit": request.user.character_limit,
            "usage_percent": min(100, round(usage_used / request.user.character_limit * 100)) if request.user.character_limit else 100,
            "provider_configured": tts_provider_is_configured(),
            "assistant_configuration": assistant_configuration,
            "assistant_configured": bool(
                assistant_configuration and assistant_configuration.is_configured
            ),
            "last_applied_proposal": last_applied_proposal,
        },
    )


@require_POST
@login_required
def project_autosave(request, project_id):
    project = owned_project(request, project_id)
    form = ProjectMetaForm(request.POST, instance=project, prefix="project")
    if form.is_valid():
        form.save()
        return JsonResponse({"status": "saved", "updated_at": project.updated_at.isoformat()})
    return JsonResponse({"status": "invalid", "errors": form.errors.get_json_data()}, status=422)


@require_POST
@login_required
def project_duplicate(request, project_id):
    project = owned_project(request, project_id)
    copied = duplicate_project(project, owner=request.user)
    messages.success(request, "Das Projekt wurde vollständig dupliziert.")
    return redirect("projects:editor", project_id=copied.pk)


@require_POST
@login_required
def project_delete(request, project_id):
    project = owned_project(request, project_id)
    project.delete()
    messages.success(request, "Das Projekt wurde gelöscht.")
    return redirect("projects:list")


@require_POST
@login_required
def speaker_add(request, project_id):
    project = owned_project(request, project_id)
    form = SpeakerForm(request.POST, project=project, user=request.user)
    if form.is_valid():
        speaker = form.save(commit=False)
        speaker.project = project
        speaker.position = next_position(project.speakers)
        speaker.save()
        messages.success(request, f"{speaker.name} wurde hinzugefügt.")
    else:
        details = form_error_summary(form)
        messages.error(
            request,
            "Der Sprecher konnte nicht hinzugefügt werden."
            + (f" {details}" if details else ""),
        )
    return redirect("projects:editor", project_id=project.pk)


@require_POST
@login_required
def speaker_autosave(request, project_id, speaker_id):
    project = owned_project(request, project_id)
    speaker = get_object_or_404(project.speakers, pk=speaker_id)
    form = SpeakerForm(
        request.POST,
        instance=speaker,
        project=project,
        prefix=str(speaker.pk),
        user=request.user,
    )
    if form.is_valid():
        form.save()
        return JsonResponse({"status": "saved"})
    return JsonResponse({"status": "invalid", "errors": form.errors.get_json_data()}, status=422)


@require_POST
@login_required
def speaker_delete(request, project_id, speaker_id):
    project = owned_project(request, project_id)
    speaker = get_object_or_404(project.speakers, pk=speaker_id)
    try:
        speaker.delete()
        messages.success(request, "Der Sprecher wurde entfernt.")
    except RestrictedError:
        messages.error(request, "Dieser Sprecher wird noch in Sprechbeiträgen verwendet.")
    return redirect("projects:editor", project_id=project.pk)


@require_POST
@login_required
def segment_add(request, project_id):
    project = owned_project(request, project_id)
    speaker = project.speakers.first()
    if speaker is None:
        messages.error(request, "Legen Sie zuerst mindestens einen Sprecher an.")
    else:
        ScriptSegment.objects.create(
            project=project,
            speaker=speaker,
            position=next_position(project.segments),
            text="",
        )
    return redirect("projects:editor", project_id=project.pk)


@require_POST
@login_required
def segment_autosave(request, project_id, segment_id):
    project = owned_project(request, project_id)
    segment = get_object_or_404(project.segments, pk=segment_id)
    form = SegmentForm(request.POST, instance=segment, project=project, prefix=str(segment.pk))
    if form.is_valid():
        form.save()
        project.save(update_fields=["updated_at"])
        return JsonResponse({"status": "saved", "characters": len(segment.text)})
    return JsonResponse({"status": "invalid", "errors": form.errors.get_json_data()}, status=422)


@require_POST
@login_required
def segment_duplicate(request, project_id, segment_id):
    project = owned_project(request, project_id)
    segment = get_object_or_404(project.segments, pk=segment_id)
    ScriptSegment.objects.create(
        project=project,
        speaker=segment.speaker,
        position=next_position(project.segments),
        text=segment.text,
        direction=segment.direction,
        speed=segment.speed,
        pause_after_ms=segment.pause_after_ms,
    )
    return redirect("projects:editor", project_id=project.pk)


@require_POST
@login_required
def segment_delete(request, project_id, segment_id):
    project = owned_project(request, project_id)
    get_object_or_404(project.segments, pk=segment_id).delete()
    return redirect("projects:editor", project_id=project.pk)


@require_POST
@login_required
def segment_move(request, project_id, segment_id, direction):
    if direction not in {"up", "down"}:
        raise PermissionDenied
    project = owned_project(request, project_id)
    segment = get_object_or_404(project.segments, pk=segment_id)
    move_segment(segment, direction)
    return redirect("projects:editor", project_id=project.pk)
