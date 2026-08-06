from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projects.views import owned_project

from .forms import AssistantRefinementForm, AssistantRevisionForm
from .models import AssistantConversation, AssistantProposal
from .providers import AssistantProviderError, AssistantProviderNotConfigured
from .schema import ProposalValidationError
from .services import apply_proposal, discard_proposal, undo_proposal
from .voice_casting import profile_for_display
from .workflows import begin_project_revision, refine_conversation
from usage_control.services import QuotaExceeded


def owned_conversation(request, conversation_id):
    queryset = AssistantConversation.objects.select_related("project", "created_by")
    if not (request.user.is_staff or request.user.role == request.user.Role.ADMIN):
        queryset = queryset.filter(created_by=request.user)
    return get_object_or_404(queryset, pk=conversation_id)


@login_required
def conversation_detail(request, conversation_id):
    conversation = owned_conversation(request, conversation_id)
    proposal = conversation.proposals.filter(status=AssistantProposal.Status.PENDING).first()
    if proposal is None:
        messages.info(request, "Dieser KI-Entwurf wurde bereits abgeschlossen.")
        return redirect("projects:editor", project_id=conversation.project_id)
    return render(
        request,
        "script_assistant/conversation.html",
        {
            "conversation": conversation,
            "proposal": proposal,
            "speaker_profiles": [
                profile_for_display(profile) for profile in proposal.payload.get("speakers", [])
            ],
            "refinement_form": AssistantRefinementForm(),
        },
    )


@require_POST
@login_required
def conversation_refine(request, conversation_id):
    conversation = owned_conversation(request, conversation_id)
    form = AssistantRefinementForm(request.POST)
    if not form.is_valid():
        proposal = conversation.proposals.filter(status=AssistantProposal.Status.PENDING).first()
        return render(
            request,
            "script_assistant/conversation.html",
            {
                "conversation": conversation,
                "proposal": proposal,
                "speaker_profiles": [
                    profile_for_display(profile)
                    for profile in (proposal.payload.get("speakers", []) if proposal else [])
                ],
                "refinement_form": form,
            },
            status=422,
        )
    try:
        refine_conversation(conversation, form.cleaned_data["instruction"])
    except (AssistantProviderError, AssistantProviderNotConfigured, ProposalValidationError, QuotaExceeded, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Der Entwurf wurde nach Ihrem Wunsch überarbeitet.")
    return redirect("script_assistant:conversation", conversation_id=conversation.pk)


@require_POST
@login_required
def conversation_apply(request, conversation_id):
    conversation = owned_conversation(request, conversation_id)
    proposal = get_object_or_404(
        conversation.proposals,
        status=AssistantProposal.Status.PENDING,
    )
    try:
        project = apply_proposal(proposal, AssistantProposal.ApplyMode.REPLACE)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("script_assistant:conversation", conversation_id=conversation.pk)
    conversation.status = AssistantConversation.Status.APPLIED
    conversation.save(update_fields=["status", "updated_at"])
    messages.success(
        request,
        "Der KI-Entwurf wurde übernommen. Sie können Text und Stimmen jetzt frei bearbeiten.",
    )
    for warning in getattr(project, "_voice_assignment_warnings", []):
        messages.warning(request, warning)
    return redirect("projects:editor", project_id=project.pk)


@require_POST
@login_required
def conversation_discard(request, conversation_id):
    conversation = owned_conversation(request, conversation_id)
    proposal = conversation.proposals.filter(status=AssistantProposal.Status.PENDING).first()
    if proposal:
        discard_proposal(proposal)
    project = conversation.project
    started_from_empty = conversation.started_from_empty
    conversation.status = AssistantConversation.Status.DISCARDED
    conversation.save(update_fields=["status", "updated_at"])
    if started_from_empty and not project.segments.exists():
        project.delete()
        messages.info(request, "Der KI-Entwurf wurde verworfen.")
        return redirect("projects:list")
    messages.info(request, "Der KI-Vorschlag wurde verworfen; Ihr bisheriger Hörtext bleibt unverändert.")
    return redirect("projects:editor", project_id=project.pk)


@login_required
def project_revision(request, project_id):
    project = owned_project(request, project_id)
    form = AssistantRevisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            conversation = begin_project_revision(
                project,
                request.user,
                form.cleaned_data["instruction"],
            )
        except (AssistantProviderError, AssistantProviderNotConfigured, ProposalValidationError, QuotaExceeded) as exc:
            messages.error(request, str(exc))
        else:
            return redirect("script_assistant:conversation", conversation_id=conversation.pk)
    return render(
        request,
        "script_assistant/revision_start.html",
        {"project": project, "form": form},
    )


@require_POST
@login_required
def proposal_undo(request, proposal_id):
    proposal = get_object_or_404(AssistantProposal.objects.select_related("project"), pk=proposal_id)
    owned_project(request, proposal.project_id)
    try:
        project = undo_proposal(proposal)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        if proposal.conversation_id:
            AssistantConversation.objects.filter(pk=proposal.conversation_id).update(
                status=AssistantConversation.Status.DISCARDED
            )
        messages.success(request, "Die letzte KI-Übernahme wurde rückgängig gemacht.")
    return redirect("projects:editor", project_id=proposal.project_id)
