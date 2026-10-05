from copy import deepcopy
from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile
import json
import httpx

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import TemporaryStudentAccess

from projects.models import Project, Speaker, ScriptSegment
from usage_control.models import UsageEvent
from script_assistant.models import AssistantConfiguration
from script_assistant.providers.openai import OpenAIScriptAssistantProvider
from .exports import export_docx, export_pdf
from .models import Worksheet
from .sample import BRIEF, PAYLOAD, SOURCE, sample_worksheet
from .schema import validate_payload, WorksheetValidationError
from .services import generate_worksheet, is_stale, queue_worksheet, script_source


class WorksheetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="worksheet-teacher", must_change_password=False, demo_projects_initialized=True)
        self.project = Project.objects.create(owner=self.user, title=SOURCE["title"], language="de", level="A2")
        speakers = {}
        for index, segment in enumerate(SOURCE["segments"]):
            speaker = speakers.setdefault(segment["speaker"], Speaker.objects.get_or_create(project=self.project, name=segment["speaker"])[0])
            ScriptSegment.objects.create(project=self.project, speaker=speaker, position=index, text=segment["text"])
        self.sheet = Worksheet.objects.create(project=self.project, created_by=self.user, status="ready", brief=BRIEF, source=script_source(self.project), payload=PAYLOAD)
        self.client.force_login(self.user)

    def test_source_validation_rejects_invented_quote_and_invalid_reference(self):
        validate_payload(PAYLOAD, SOURCE, expected_count=6)
        for field, value in (("evidence", "Der Zug fährt um 12 Uhr."), ("source_segments", [99]), ("answer", "Keine Option")):
            with self.subTest(field=field):
                payload = deepcopy(PAYLOAD)
                payload["exercises"][1][field] = value
                with self.assertRaises(WorksheetValidationError):
                    validate_payload(payload, SOURCE)

    def test_teacher_can_open_and_student_and_other_teacher_cannot(self):
        routes = [reverse("worksheets:detail", args=[self.sheet.pk]), reverse("worksheets:status", args=[self.sheet.pk]),
                  reverse("worksheets:preview", args=[self.sheet.pk, "teacher"]), reverse("worksheets:download", args=[self.sheet.pk, "student", "docx"])]
        for route in routes:
            self.assertEqual(self.client.get(route).status_code, 200)
        for role, expected in (("teacher", 404), ("student", 403)):
            other = get_user_model().objects.create_user(username=role, role=role, must_change_password=False, demo_projects_initialized=True)
            if role == "student":
                TemporaryStudentAccess.objects.create(student=other, teacher=self.user, label="Test", expires_at=timezone.now() + timedelta(hours=1))
            self.client.force_login(other)
            for route in routes:
                self.assertEqual(self.client.get(route).status_code, expected)

    def test_student_preview_does_not_contain_answer_or_source(self):
        student = self.client.get(reverse("worksheets:preview", args=[self.sheet.pk, "student"]))
        self.assertNotContains(student, PAYLOAD["exercises"][2]["answer"])
        self.assertNotContains(student, SOURCE["segments"][1]["text"])
        self.assertNotContains(student, "Textbeleg:")
        teacher = self.client.get(reverse("worksheets:preview", args=[self.sheet.pk, "teacher"]))
        self.assertContains(teacher, SOURCE["segments"][1]["text"])

    def test_docx_is_editable_and_separates_solutions(self):
        for audience in ("student", "teacher"):
            with ZipFile(BytesIO(export_docx(self.sheet, audience))) as archive:
                xml = archive.read("word/document.xml").decode()
                self.assertIn("Wann fährt der nächste Zug", xml)
                self.assertEqual("Textbeleg:" in xml, audience == "teacher")
                self.assertEqual(SOURCE["segments"][1]["text"] in xml, audience == "teacher")

    def test_script_change_marks_old_sheet_stale_but_keeps_payload(self):
        self.assertFalse(is_stale(self.sheet))
        segment = self.project.segments.first()
        segment.text += " Neue Information."
        segment.save()
        self.assertTrue(is_stale(self.sheet))
        self.assertContains(self.client.get(reverse("worksheets:detail", args=[self.sheet.pk])), "inzwischen geändert")
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.payload, PAYLOAD)

    def test_queue_captures_source_and_does_not_overwrite_previous(self):
        with patch("worksheets.tasks.process_worksheet.delay") as task, self.captureOnCommitCallbacks(execute=True):
            created = queue_worksheet(self.project, self.user, BRIEF, previous=self.sheet)
        task.assert_called_once_with(str(created.pk))
        self.assertEqual(created.brief["previous_worksheet"], PAYLOAD)
        self.assertEqual(created.source, SOURCE)
        with self.assertRaises(ValueError):
            queue_worksheet(self.project, self.user, BRIEF)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.payload, PAYLOAD)

    def test_generation_is_idempotent_and_uses_worksheet_quota_feature(self):
        self.sheet.status = "queued"
        self.sheet.save()
        with patch("worksheets.services._provider_request", return_value=SimpleNamespace(payload=PAYLOAD)) as provider:
            generate_worksheet(self.sheet.pk)
            generate_worksheet(self.sheet.pk)
        provider.assert_called_once()
        self.assertEqual(provider.call_args.kwargs["feature"], UsageEvent.Feature.WORKSHEET)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.status, "ready")

    def test_invalid_generation_fails_without_exporting(self):
        self.sheet.status = "queued"
        self.sheet.save()
        with patch("worksheets.services._provider_request", return_value=SimpleNamespace(payload={})):
            generate_worksheet(self.sheet.pk)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.status, "failed")
        self.assertEqual(self.client.get(reverse("worksheets:download", args=[self.sheet.pk, "teacher", "docx"])).status_code, 404)

    def test_stalled_task_recovers(self):
        Worksheet.objects.filter(pk=self.sheet.pk).update(status="running", updated_at=timezone.now() - timedelta(minutes=6))
        response = self.client.get(reverse("worksheets:status", args=[self.sheet.pk]))
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_edit_and_conflicting_revision(self):
        data = {"action": "save", "revision": "0", "meta-title": "Mein Arbeitsblatt", "meta-introduction": PAYLOAD["introduction"],
                "meta-learning_goal": PAYLOAD["learning_goal"], "tasks-TOTAL_FORMS": "6", "tasks-INITIAL_FORMS": "6"}
        for index, item in enumerate(PAYLOAD["exercises"]):
            for key, value in item.items():
                if key == "options": value = "\n".join(value)
                if key == "source_segments": value = ",".join(map(str, value))
                data[f"tasks-{index}-{key}"] = value
        url = reverse("worksheets:detail", args=[self.sheet.pk])
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.payload["title"], "Mein Arbeitsblatt")
        self.assertEqual(self.client.post(url, data).status_code, 409)

    def test_pdf_uses_real_pages_and_separates_solutions(self):
        try:
            import weasyprint
        except OSError:
            self.skipTest("Pango wird im Linux-Produktionsimage geprüft.")
        from pypdf import PdfReader
        for audience, count in (("student", 2), ("teacher", 3)):
            pdf = PdfReader(BytesIO(export_pdf(self.sheet, audience)))
            self.assertEqual(len(pdf.pages), count)
            text = "\n".join(page.extract_text() for page in pdf.pages)
            self.assertEqual("Textbeleg:" in text, audience == "teacher")

    def test_provider_sends_worksheet_schema_without_storing_data(self):
        configuration = AssistantConfiguration(model="gpt-6-luna")
        configuration.set_api_key("sk-test-worksheet")
        captured = {}
        def handler(request):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(PAYLOAD)}]}]})
        provider = OpenAIScriptAssistantProvider(configuration, transport=httpx.MockTransport(handler))
        result = provider.generate_proposal({"task": "worksheet", "brief": BRIEF, "script": SOURCE})
        self.assertEqual(result.payload, PAYLOAD)
        self.assertEqual(captured["text"]["format"]["name"], "arbeitsblatt")
        self.assertTrue(captured["text"]["format"]["strict"])
        self.assertFalse(captured["store"])
