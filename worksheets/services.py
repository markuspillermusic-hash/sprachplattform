import hashlib
import json
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from script_assistant.workflows import _provider_request
from usage_control.models import UsageEvent
from .models import Worksheet
from .schema import validate_payload

logger = logging.getLogger(__name__)


def script_source(project):
    return {"title": project.title, "language": project.language, "level": project.level,
            "segments": [{"speaker": segment.speaker.name, "text": segment.text}
                         for segment in project.segments.select_related("speaker").order_by("position", "pk")]}


def source_signature(source):
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def is_stale(worksheet):
    return source_signature(worksheet.source) != source_signature(script_source(worksheet.project))


def expire_stalled(project):
    project.worksheets.filter(status__in=("queued", "running"),
        updated_at__lt=timezone.now() - timedelta(minutes=5)).update(status="failed",
        error_message="Die Verarbeitung wurde unterbrochen. Bitte versuchen Sie es erneut.", updated_at=timezone.now())


def queue_worksheet(project, user, brief, *, previous=None):
    with transaction.atomic():
        from projects.models import Project
        project = Project.objects.select_for_update().get(pk=project.pk)
        expire_stalled(project)
        if project.worksheets.filter(status__in=("queued", "running")).exists():
            raise ValueError("Für diesen Hörtext wird bereits ein Arbeitsblatt erstellt.")
        source = script_source(project)
        if not source["segments"] or not any(segment["text"].strip() for segment in source["segments"]):
            raise ValueError("Speichern Sie zuerst den Hörtext, auf dem das Arbeitsblatt beruhen soll.")
        stored_brief = dict(brief)
        if previous and previous.payload:
            stored_brief["previous_worksheet"] = previous.payload
        worksheet = Worksheet.objects.create(project=project, created_by=user, brief=stored_brief, source=source)
        from .tasks import process_worksheet
        transaction.on_commit(lambda: dispatch(worksheet.pk, process_worksheet))
    return worksheet


def dispatch(worksheet_id, task):
    try:
        task.delay(str(worksheet_id))
    except Exception:
        logger.exception("Worksheet dispatch failed")
        Worksheet.objects.filter(pk=worksheet_id, status="queued").update(status="failed",
            error_message="Die Verarbeitung konnte nicht gestartet werden. Bitte versuchen Sie es erneut.", updated_at=timezone.now())


def generate_worksheet(worksheet_id):
    if not Worksheet.objects.filter(pk=worksheet_id, status="queued").update(status="running", updated_at=timezone.now()):
        return
    worksheet = Worksheet.objects.select_related("project", "created_by").filter(pk=worksheet_id).first()
    if not worksheet:
        return
    try:
        if not worksheet.created_by.is_active or worksheet.created_by.role == "student":
            raise ValueError("Dieser Zugang darf keine Arbeitsblätter erzeugen.")
        result = _provider_request({"task": "worksheet", "brief": worksheet.brief, "script": worksheet.source},
                                   worksheet.created_by, feature=UsageEvent.Feature.WORKSHEET)
        payload = validate_payload(result.payload, worksheet.source, expected_count=int(worksheet.brief["pages"]) * 3)
        Worksheet.objects.filter(pk=worksheet.pk, status="running").update(payload=payload, status="ready", updated_at=timezone.now())
    except Exception as exc:
        from script_assistant.providers import AssistantProviderError
        from usage_control.services import QuotaExceeded
        from .schema import WorksheetValidationError
        logger.exception("Worksheet generation failed: %s", worksheet.pk)
        message = str(exc) if isinstance(exc, (AssistantProviderError, QuotaExceeded, WorksheetValidationError, ValueError)) else "Das Arbeitsblatt konnte nicht erstellt werden. Bitte versuchen Sie es erneut."
        Worksheet.objects.filter(pk=worksheet.pk, status="running").update(status="failed", error_message=message[:500], updated_at=timezone.now())
