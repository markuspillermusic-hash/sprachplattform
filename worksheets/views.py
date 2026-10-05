from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods

from projects.views import visible_projects
from script_assistant.models import AssistantConfiguration
from .forms import ExerciseForms, RefinementForm, WorksheetBriefForm, WorksheetMetaForm
from .models import Worksheet
from .schema import WorksheetValidationError, validate_payload
from .services import expire_stalled, is_stale, queue_worksheet


def teacher_project(request, project_id):
    if request.user.role == "student":
        raise PermissionDenied
    return get_object_or_404(visible_projects(request.user), pk=project_id)


def teacher_worksheet(request, worksheet_id):
    worksheet = get_object_or_404(Worksheet.objects.select_related("project"), pk=worksheet_id)
    teacher_project(request, worksheet.project_id)
    expire_stalled(worksheet.project)
    worksheet.refresh_from_db()
    return worksheet


def configured():
    config = AssistantConfiguration.objects.filter(active=True).first()
    return bool(config and config.is_configured)


@login_required
@require_http_methods(["GET", "POST"])
def start(request, project_id):
    project = teacher_project(request, project_id)
    expire_stalled(project)
    production = getattr(project, "production", None)
    initial = {"target_group": production.brief.get("target_group", "") if production else "",
               "level": project.level, "learning_goal": production.brief.get("learning_goal", "") if production else ""}
    form = WorksheetBriefForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if not configured() or not request.user.openai_daily_request_limit:
            form.add_error(None, "Die KI-Anbindung oder Ihr KI-Kontingent ist derzeit nicht verfügbar.")
        else:
            brief = dict(form.cleaned_data)
            if brief["instruction_language"] == "target":
                brief["instruction_language"] = project.language
            try:
                worksheet = queue_worksheet(project, request.user, brief)
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                return redirect("worksheets:detail", worksheet_id=worksheet.pk)
    return render(request, "worksheets/start.html", {"project": project, "form": form,
        "history": project.worksheets.all()[:8], "can_generate": configured() and bool(request.user.openai_daily_request_limit),
        "has_script": project.segments.exclude(text="").exists()})


def exercise_initial(payload):
    return [{**item, "options": "\n".join(item["options"]),
             "source_segments": ", ".join(str(ref) for ref in item["source_segments"])} for item in payload["exercises"]]


@login_required
@require_http_methods(["GET", "POST"])
def detail(request, worksheet_id):
    worksheet = teacher_worksheet(request, worksheet_id)
    meta = WorksheetMetaForm(initial=worksheet.payload, prefix="meta")
    exercises = ExerciseForms(initial=exercise_initial(worksheet.payload), prefix="tasks") if worksheet.payload else None
    refinement = RefinementForm()
    code = 200
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save" and worksheet.status == "ready":
            meta = WorksheetMetaForm(request.POST, prefix="meta")
            exercises = ExerciseForms(request.POST, prefix="tasks")
            if meta.is_valid() and exercises.is_valid():
                try:
                    payload = validate_payload({**meta.cleaned_data, "exercises": [form.cleaned_data for form in exercises]}, worksheet.source)
                    revision = int(request.POST.get("revision", "-1"))
                except (WorksheetValidationError, ValueError) as exc:
                    meta.add_error(None, str(exc))
                else:
                    with transaction.atomic():
                        locked = Worksheet.objects.select_for_update().get(pk=worksheet.pk)
                        if locked.revision != revision:
                            meta.add_error(None, "Das Arbeitsblatt wurde inzwischen geändert. Laden Sie die Seite neu, bevor Sie erneut speichern.")
                            code = 409
                        else:
                            locked.payload = payload
                            locked.revision += 1
                            locked.save(update_fields=["payload", "revision", "updated_at"])
                            messages.success(request, "Arbeitsblatt und Lösungen sind gespeichert.")
                            return redirect("worksheets:detail", worksheet_id=worksheet.pk)
        elif action in ("refine", "retry"):
            if action == "refine":
                refinement = RefinementForm(request.POST)
                if not refinement.is_valid():
                    return render_detail(request, worksheet, meta, exercises, refinement)
            if not configured() or not request.user.openai_daily_request_limit:
                refinement.add_error(None, "Die KI-Anbindung oder Ihr KI-Kontingent ist derzeit nicht verfügbar.")
            else:
                brief = {key: value for key, value in worksheet.brief.items() if key != "previous_worksheet"}
                if action == "refine":
                    brief["change_request"] = refinement.cleaned_data["change_request"]
                try:
                    created = queue_worksheet(worksheet.project, request.user, brief, previous=worksheet if action == "refine" else None)
                except ValueError as exc:
                    refinement.add_error(None, str(exc))
                else:
                    return redirect("worksheets:detail", worksheet_id=created.pk)
        else:
            return HttpResponse("Dieser Arbeitsschritt ist nicht verfügbar.", status=400)
    return render_detail(request, worksheet, meta, exercises, refinement, code)


def render_detail(request, worksheet, meta, exercises, refinement, code=200):
    return render(request, "worksheets/detail.html", {"worksheet": worksheet, "project": worksheet.project,
        "meta": meta, "exercises": exercises, "refinement": refinement, "stale": is_stale(worksheet),
        "can_generate": configured() and bool(request.user.openai_daily_request_limit)}, status=code)


@login_required
@require_GET
def status(request, worksheet_id):
    worksheet = teacher_worksheet(request, worksheet_id)
    response = JsonResponse({"status": worksheet.status, "label": worksheet.get_status_display()})
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_GET
def preview(request, worksheet_id, audience):
    worksheet = teacher_worksheet(request, worksheet_id)
    if audience not in ("student", "teacher") or worksheet.status != "ready":
        raise Http404
    from .exports import document_context
    return render(request, "worksheets/document.html", document_context(worksheet, audience, preview=True))


@login_required
@require_GET
def download(request, worksheet_id, audience, file_format):
    worksheet = teacher_worksheet(request, worksheet_id)
    if audience not in ("student", "teacher") or file_format not in ("pdf", "docx") or worksheet.status != "ready":
        raise Http404
    from .exports import export_pdf, export_docx
    contents = export_pdf(worksheet, audience) if file_format == "pdf" else export_docx(worksheet, audience)
    mime = "application/pdf" if file_format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    response = HttpResponse(contents, content_type=mime)
    label = "arbeitsblatt" if audience == "student" else "loesungen"
    response["Content-Disposition"] = f'attachment; filename="{slugify(worksheet.payload["title"])[:70] or "hoertext"}-{label}.{file_format}"'
    response["Cache-Control"] = "private, no-store"
    return response
