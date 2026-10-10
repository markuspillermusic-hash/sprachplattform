from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import subprocess

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from audio_studio.models import StudioConfiguration, StudioSession
from audio_studio.providers import GeneratedAudio, ProviderRejected
from audio_studio.services import save_state
from audio_studio.tests.test_studio import wav_bytes
from generation.models import GenerationJob, UsageLedger
from generation.services import create_generation_job, run_generation_job
from projects.lifecycle import ProjectContentError, delete_project, duplicate_project
from projects.models import Project, ScriptSegment, Speaker
from script_assistant.services import editable_project_snapshot
from script_assistant.workflows import project_payload
from tts.providers.base import SynthesisResult
from usage_control.models import UsageEvent, ProviderBudget
from accounts.models import TemporaryStudentAccess

from .models import Production, ProductionRun
from .planning import ProductionError, material_key, validate_plan
from .services import recover_stale_runs, run_production, save_draft, save_plan, select_speech, start_run
from .views import plan_forms, script_forms, voice_forms
from .forms import ProductionBriefForm
from tts.models import ProviderVoice


def mp3_bytes(seconds):
    return subprocess.run(["ffmpeg", "-v", "error", "-f", "wav", "-i", "pipe:0", "-c:a", "libmp3lame", "-f", "mp3", "pipe:1"],
                          input=wav_bytes(seconds), capture_output=True, check=True).stdout


@override_settings(SECURE_SSL_REDIRECT=False, ELEVENLABS_API_KEY="test-only")
class ProductionTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        settings = override_settings(AUDIO_STORAGE_ROOT=Path(self.folder.name))
        settings.enable(); self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_user(username="producer", must_change_password=False)
        self.other = get_user_model().objects.create_user(username="other", must_change_password=False)
        self.project = Project.objects.create(owner=self.user, title="Wald", language="de", level="A2")
        self.speaker = Speaker.objects.create(project=self.project, name="Erzähler", voice_id="voice-a", provider="elevenlabs", model="eleven_v4")
        self.segment = ScriptSegment.objects.create(project=self.project, speaker=self.speaker, text="Im Wald ist es still.", pause_after_ms=100, position=1)
        self.production = Production.objects.create(project=self.project, brief={"language": "de", "level": "A2", "topic": "Wald"})
        self.config = StudioConfiguration.objects.create(music_enabled=True, effects_enabled=True, music_eur_per_minute=.5, effects_eur_per_minute=.2)
        self.provider = Mock(model_id="eleven_v4", estimated_rate=Decimal(".2"))
        self.provider.synthesize_dialogue.return_value = SynthesisResult(wav_bytes(.6), "audio/wav", "test-request", Decimal(20))
        patcher = patch("generation.services.get_tts_provider", return_value=self.provider)
        patcher.start(); self.addCleanup(patcher.stop)
        self.client.force_login(self.user)
        self.plan = {"summary": "Ruhige Musik und Vogelruf", "speech_start": 0, "music_duck_db": 4, "compression": 25, "items": [
            {"title": "Musik", "kind": "music", "asset_id": "", "prompt": "Quiet instrumental piano", "duration": 3, "start": 0, "gain_db": -18, "fade_in": .1, "fade_out": .2, "loop": False},
            {"title": "Vogel", "kind": "effects", "asset_id": "", "prompt": "A short bird call", "duration": 1, "start": .2, "gain_db": -8, "fade_in": .01, "fade_out": .1, "loop": False}]}

    def run_phase(self, kind, data=None):
        self.production.refresh_from_db()
        run = start_run(self.project, self.user, kind, self.production.revision, data)
        run_production(run.pk)
        run.refresh_from_db(); self.production.refresh_from_db()
        self.assertEqual(run.status, "succeeded", run.error_message)
        return run

    @staticmethod
    def form_data(form):
        return {field.html_name: ("on" if field.value() is True else "" if field.value() is None or field.value() is False else str(field.value())) for field in form}

    def plan_post(self):
        settings, items = plan_forms(self.production)
        data = {"action": "save_plan", "revision": self.production.revision, **self.form_data(settings), **self.form_data(items.management_form)}
        for form in items:
            data.update(self.form_data(form))
        return data

    def voice(self, **kwargs):
        return ProviderVoice.objects.create(provider="elevenlabs", model="eleven_v4", voice_id=kwargs.pop("voice_id", "selected-voice"), display_name="Gewählte Stimme", active=True, languages=kwargs.pop("languages", ["de"]), **kwargs)

    def test_home_and_project_list_offer_equal_audio_formats(self):
        for path in ("/", reverse("projects:list")):
            response = self.client.get(path)
            self.assertContains(response, "Hörtext erstellen")
            self.assertContains(response, "Hörspiel erstellen")
            self.assertContains(response, "Ein reiner Sprechtext")
            self.assertContains(response, "Sprechtexte mit Musik und Geräuschen")

    def test_inserted_script_lines_save_in_submitted_order_without_audio(self):
        payload, lines = script_forms(self.production)
        original = self.form_data(lines.forms[0])
        data = {"action": "save_script", "revision": 0, **self.form_data(lines.management_form), "script-TOTAL_FORMS": 3}
        for index, text in enumerate(("Ein vergessener Anfang.", self.segment.text, "Ein neuer Schluss.")):
            for key, value in original.items():
                data[key.replace("script-0-", f"script-{index}-")] = value
            data[f"script-{index}-text"] = text
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.production.refresh_from_db()
        self.assertEqual([s["text"] for s in self.production.draft["segments"]],
                         ["Ein vergessener Anfang.", self.segment.text, "Ein neuer Schluss."])
        self.assertEqual(self.project.segments.count(), 1)
        self.assertFalse(self.project.production_runs.exists())

    def test_production_accepts_duration_between_previous_presets(self):
        form = ProductionBriefForm({"language": "de", "format": "dialogue", "topic": "Wald", "speaker_count": 2,
                                    "duration_seconds": 255, "target_group": "Klasse 7"}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["duration_seconds"], 255)

    def test_twenty_minute_ten_speaker_brief_preserves_last_role_voice(self):
        from copy import deepcopy
        voice = self.voice()
        response = self.client.post(reverse("production:create"), {"language": "de", "format": "dialogue",
            "duration_seconds": 1200, "speaker_count": 10, "target_group": "Klasse 7", "topic": "Wald",
            "level": "", "voice_10": voice.pk})
        self.assertEqual(response.status_code, 302)
        project = Project.objects.exclude(pk=self.project.pk).get()
        self.assertEqual(project.production.brief["speaker_count"], 10)
        self.assertEqual(project.production.brief["duration_seconds"], 1200)
        self.assertEqual(project.production.brief["initial_voice_choices"], {"10": str(voice.pk)})
        self.assertNotIn("voice_10", project.production.brief)
        draft = project_payload(self.project)
        draft["speakers"] = [{**deepcopy(draft["speakers"][0]), "name": f"Rolle {index}"} for index in range(1, 11)]
        draft["segments"] = [{**deepcopy(draft["segments"][0]), "speaker": f"Rolle {index}"} for index in range(1, 11)]
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=draft)):
            run_production(project.production_runs.get().pk)
        project.production.refresh_from_db()
        self.assertEqual(project.production.brief["voice_choices"], {"Rolle 10": str(voice.pk)})
        self.assertEqual(len(project.production.draft["speakers"]), 10)
        self.assertFalse(GenerationJob.objects.filter(version__project=project).exists())

    def test_inactive_voice_for_tenth_role_is_rejected(self):
        voice = self.voice(); voice.active = False; voice.save()
        form = ProductionBriefForm({"language": "de", "format": "dialogue", "duration_seconds": 1200,
            "speaker_count": 10, "target_group": "Klasse 7", "topic": "Wald", "voice_10": voice.pk}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("voice_10", form.errors)

    def test_optional_level_and_initial_voice_are_saved_without_audio_generation(self):
        voice = self.voice()
        response = self.client.post(reverse("production:create"), {"language": "de", "format": "monologue", "duration_seconds": 30,
            "speaker_count": 1, "target_group": "Klasse 7", "topic": "Wald", "level": "", "voice_1": voice.pk})
        self.assertEqual(response.status_code, 302)
        project = Project.objects.exclude(pk=self.project.pk).get()
        self.assertEqual(project.level, "")
        self.assertEqual(project.production.brief["initial_voice_choices"], {"1": str(voice.pk)})
        run = project.production_runs.get()
        draft = project_payload(self.project)
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=draft)) as provider:
            run_production(run.pk)
        project.production.refresh_from_db()
        self.assertEqual(project.production.draft["level"], "")
        self.assertEqual(project.production.brief["voice_choices"], {"Erzähler": str(voice.pk)})
        self.assertNotIn("initial_voice_choices", provider.call_args.args[0]["brief"])
        self.assertFalse(project.segments.exists())
        self.assertFalse(GenerationJob.objects.filter(version__project=project).exists())

    def test_initial_voice_rejects_incompatible_language_and_inactive_catalog_entry(self):
        voice = self.voice(languages=["en"])
        voice.provider = "other"; voice.save()
        data = {"language": "de", "format": "monologue", "duration_seconds": 30, "speaker_count": 1,
                "target_group": "Klasse 7", "topic": "Wald", "voice_1": voice.pk}
        form = ProductionBriefForm(data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("voice_1", form.errors)
        voice.active = False; voice.save()
        self.assertFalse(ProductionBriefForm(data, user=self.user).is_valid())

    def test_multilingual_voice_can_be_selected_and_applied_to_german_draft(self):
        from production.services import save_draft
        voice = self.voice(languages=["en"])
        form = ProductionBriefForm({"language": "de", "format": "monologue", "duration_seconds": 30,
            "speaker_count": 1, "target_group": "Klasse 7", "topic": "Wald", "voice_1": voice.pk}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        payload = project_payload(self.project)
        choices = {speaker["name"]: str(voice.pk) for speaker in payload["speakers"]}
        save_draft(self.project, self.user, self.production.revision, payload, apply=True, voice_choices=choices)
        speaker = self.project.speakers.get()
        self.assertEqual(speaker.voice_id, voice.voice_id)

    def test_editor_handoff_loads_draft_unsaved_text_and_selected_voice_without_audio(self):
        voice = self.voice()
        payload = project_payload(self.project)
        self.project.segments.all().delete(); self.project.speakers.all().delete()
        self.production.draft = payload; self.production.save()
        lines = script_forms(self.production)[1]; voices = voice_forms(self.production, self.user)
        data = {"action": "edit_script", "revision": self.production.revision, **self.form_data(lines.management_form), **self.form_data(voices.management_form)}
        for form in [*lines.forms, *voices.forms]: data.update(self.form_data(form))
        data["script-0-text"] = "Dieser geänderte Entwurf kommt im Editor an."
        data["voices-0-voice"] = voice.pk
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertRedirects(response, reverse("projects:editor", args=[self.project.pk]))
        self.assertEqual(self.project.segments.get().text, data["script-0-text"])
        self.assertEqual(self.project.speakers.get().voice_id, voice.voice_id)
        self.production.refresh_from_db()
        self.assertFalse(self.production.draft)
        self.assertFalse(GenerationJob.objects.exists())

    def test_explicit_voice_is_kept_when_applying_a_draft(self):
        voice = self.voice()
        prod = save_draft(self.project, self.user, 0, project_payload(self.project), voice_choices={"Erzähler": str(voice.pk)})
        self.assertEqual(self.project.speakers.get().voice_id, "voice-a")
        self.run_phase("speech")
        self.assertEqual(self.production.speech_job.parts.get().input_data[0]["voice_id"], voice.voice_id)

    def test_automatic_voice_choice_can_replace_a_previous_manual_voice(self):
        voice = self.voice()
        save_draft(self.project, self.user, 0, project_payload(self.project), apply=True, voice_choices={"Erzähler": ""})
        self.assertEqual(self.project.speakers.get().voice_id, voice.voice_id)

    def test_editor_voice_changes_are_authoritative_for_followup_drafts(self):
        first = self.voice(voice_id="first-choice")
        second = self.voice(voice_id="editor-choice")
        save_draft(self.project, self.user, 0, project_payload(self.project), apply=True, voice_choices={"Erzähler": str(first.pk)})
        speaker = self.project.speakers.get(); speaker.voice_id = second.voice_id; speaker.save()
        self.production.refresh_from_db()
        self.assertEqual(voice_forms(self.production, self.user).forms[0]["voice"].value(), second.pk)
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=project_payload(self.project))):
            self.run_phase("refine", {"instruction": "Text verbessern"})
        self.assertEqual(self.production.brief["voice_choices"]["Erzähler"], str(second.pk))
        save_draft(self.project, self.user, self.production.revision, self.production.draft, apply=True)
        self.assertEqual(self.project.speakers.get().voice_id, second.voice_id)

    def test_untouched_optional_audio_with_browser_defaults_is_ignored(self):
        self.approve_audio()
        data = self.plan_post()
        self.assertEqual(data["items-2-kind"], "music")
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.production.refresh_from_db()
        self.assertEqual(len(self.production.plan["items"]), 2)

    def test_new_optional_music_is_saved_with_default_timing_and_gain(self):
        self.approve_audio()
        data = self.plan_post()
        data.update({"items-2-title": "Abspann", "items-2-prompt": "Gentle instrumental outro"})
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.production.refresh_from_db()
        self.assertEqual(self.production.plan["items"][2]["prompt"], "Gentle instrumental outro")
        self.assertEqual(self.production.plan["items"][2]["duration"], 15)
        self.assertEqual(self.production.plan["items"][2]["start"], 0)
        self.assertFalse(self.project.production_runs.filter(kind="mix").exists())

    def test_semantic_plan_errors_preserve_every_entered_audio(self):
        self.approve_audio()
        data = self.plan_post()
        data.update({"items-2-title": "Zusätzliche Musik bleibt erhalten", "items-2-prompt": "My entered music request",
                     "items-2-duration": 5, "items-2-fade_in": 4, "items-2-fade_out": 4})
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "My entered music request", status_code=400)
        self.assertContains(response, "Zusätzliche Musik bleibt erhalten", status_code=400)
        self.assertEqual(response.context["items"].forms[2]["fade_out"].value(), "4")
        self.production.refresh_from_db()
        self.assertEqual(len(self.production.plan["items"]), 2)
        data["items-2-fade_out"] = 1
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.production.refresh_from_db()
        self.assertEqual(len(self.production.plan["items"]), 3)

    def test_partial_optional_audio_keeps_text_and_shows_specific_field_errors(self):
        self.approve_audio()
        data = self.plan_post(); data["items-2-prompt"] = "This entered description must stay"
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, data["items-2-prompt"], status_code=400)
        self.assertIn("title", response.context["items"].forms[2].errors)

    def test_project_payload_does_not_invent_a_level(self):
        self.project.level = ""; self.project.save()
        self.assertEqual(project_payload(self.project)["level"], "")

    def speech(self):
        self.run_phase("speech")
        return self.production.speech_job.audio_asset

    def approve_audio(self):
        self.speech()
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=self.plan)):
            self.run_phase("plan")

    def mix(self):
        self.approve_audio()
        with patch("audio_studio.services.ElevenLabsAudioProvider.generate", side_effect=lambda kind, data: GeneratedAudio(mp3_bytes(data["duration"]), "test-material", Decimal(10))):
            self.run_phase("mix")

    def test_planning_requires_teacher_approval_without_audio_calls(self):
        with self.assertRaises(ProductionError):
            start_run(self.project, self.user, "plan", 0)
        with self.assertRaises(ProductionError):
            start_run(self.project, self.user, "mix", 0)
        self.assertFalse(GenerationJob.objects.exists())
        self.assertFalse(UsageEvent.objects.exists())

    def test_plan_request_confirms_speech_approval_but_only_requests_a_draft(self):
        self.speech()
        before = GenerationJob.objects.count()
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=self.plan)) as provider:
            self.run_phase("plan", {"music_wishes": "Klavier", "effects_wishes": "Vogel"})
        request = provider.call_args.args[0]
        self.assertTrue(request["workflow_context"]["speech_approved"])
        self.assertEqual(request["workflow_context"]["operation"], "draft_sound_plan")
        self.assertEqual(request["workflow_context"]["plan_approval_required_for"], "generate_audio_and_mix")
        self.assertEqual(request["brief"]["music_wishes"], "Klavier")
        self.assertEqual(self.production.stage, "plan")
        self.assertEqual(GenerationJob.objects.count(), before)
        self.assertFalse(self.project.studio_jobs.exclude(kind="export").exists())

    def test_refine_plan_saves_manual_changes_and_does_not_generate_audio(self):
        self.approve_audio()
        self.production.brief.update(music_wishes="Klavier", effects_wishes="Vogel")
        self.production.save()
        data = self.plan_post()
        data.update(action="refine_plan", instruction="Ersetze den Vogel durch Regen", **{"items-0-gain_db": -24})
        before = GenerationJob.objects.count()
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 302)
        run = self.project.production_runs.first()
        self.assertEqual(run.kind, "plan")
        self.assertEqual(run.input_data["previous_plan"]["items"][0]["gain_db"], -24)
        self.assertEqual(run.input_data["instruction"], data["instruction"])
        revised = deepcopy(self.plan)
        revised["items"][0]["gain_db"] = -24
        revised["items"][1]["title"] = "Regen"
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=revised)) as provider:
            run_production(run.pk)
        self.production.refresh_from_db()
        self.assertEqual(self.production.plan, revised)
        self.assertEqual(provider.call_args.args[0]["brief"]["music_wishes"], "Klavier")
        self.assertEqual(GenerationJob.objects.count(), before)
        self.assertFalse(self.project.production_runs.filter(kind="mix").exists())

    def test_invalid_refinement_preserves_plan_edits_and_instruction(self):
        self.approve_audio()
        data = self.plan_post()
        data.update(action="refine_plan", instruction="Bitte leisere Musik", **{"items-0-title": "Meine Musik", "items-0-fade_in": 3, "items-0-fade_out": 3})
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertContains(response, "Bitte leisere Musik", status_code=400)
        self.assertEqual(response.context["items"].forms[0]["title"].value(), "Meine Musik")
        self.assertEqual(self.project.production_runs.filter(kind="plan").count(), 1)
        data.update(instruction="", **{"items-0-fade_in": 0, "items-0-fade_out": 0})
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("instruction", response.context["plan_refinement"].errors)
        self.assertEqual(self.project.production_runs.filter(kind="plan").count(), 1)

    def test_empty_plan_can_be_edited_or_revised_without_plan_approval(self):
        self.approve_audio()
        self.production.plan = {**self.plan, "summary": "Keine Freigabe angegeben", "items": []}
        self.production.save()
        response = self.client.get(reverse("production:detail", args=[self.project.pk]))
        self.assertContains(response, "Klangplan nach Änderungswunsch überarbeiten")
        self.assertContains(response, "Der Vorschlag enthält noch keine")
        data = self.plan_post()
        data.update(action="refine_plan", instruction="Bitte Jingle und Vogel planen")
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 302)
        run = self.project.production_runs.first()
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=self.plan)):
            run_production(run.pk)
        self.production.refresh_from_db()
        self.assertEqual(len(self.production.plan["items"]), 2)
        self.assertFalse(self.project.production_runs.filter(kind="mix").exists())

    def test_failed_plan_refinement_retains_manual_edits(self):
        self.approve_audio()
        data = self.plan_post()
        data.update(action="refine_plan", instruction="Weniger Spannung", **{"items-0-gain_db": -24})
        self.client.post(reverse("production:action", args=[self.project.pk]), data)
        from script_assistant.providers import AssistantProviderError
        run = self.project.production_runs.first()
        with patch("production.services._provider_request", side_effect=AssistantProviderError("KI nicht erreichbar")):
            run_production(run.pk)
        run.refresh_from_db(); self.production.refresh_from_db()
        self.assertEqual(run.status, "failed")
        self.assertEqual(self.production.plan["items"][0]["gain_db"], -24)

    def test_ai_plan_change_invalidates_previous_mix_approval(self):
        self.approve_audio()
        self.production.mixed_revision = 7
        self.production.save()
        revised = deepcopy(self.plan); revised["music_duck_db"] = 2
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=revised)):
            self.run_phase("plan", {"instruction": "Weniger Absenkung"})
        self.assertIsNone(self.production.mixed_revision)

    def test_new_script_is_only_a_draft_until_approved(self):
        self.segment.delete(); self.speaker.delete()
        payload = {"title": "Waldgeschichte", "language": "de", "level": "A2", "speakers": [{"name": "Anna"}], "segments": [{"speaker": "Anna", "text": "Hallo!", "direction": "", "pause_after_ms": 0, "speed": 1}]}
        with patch("production.services._provider_request", return_value=SimpleNamespace(payload=payload)):
            self.run_phase("script")
        self.assertFalse(self.project.segments.exists())
        self.assertEqual(self.production.draft["title"], "Waldgeschichte")
        self.assertFalse(GenerationJob.objects.exists())
        self.assertContains(self.client.get(reverse("production:detail", args=[self.project.pk])), "Waldgeschichte")

    def test_apply_updates_title_preserves_chosen_voice_and_history(self):
        payload = project_payload(self.project); payload["title"] = "Neuer Titel"
        prod = save_draft(self.project, self.user, 0, payload, apply=True)
        self.assertEqual(prod.project.title, "Neuer Titel")
        self.assertEqual(prod.project.speakers.get().voice_id, "voice-a")
        self.assertEqual(self.project.assistant_proposals.get().applied_snapshot, editable_project_snapshot(prod.project))

    def test_foreign_users_and_students_cannot_operate_production(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("production:detail", args=[self.project.pk])).status_code, 404)
        with self.assertRaises(PermissionDenied):
            start_run(self.project, self.other, "speech", 0)
        self.user.role = "student"; self.user.save()
        TemporaryStudentAccess.objects.create(teacher=self.other, student=self.user, label="Test", expires_at=timezone.now() + timedelta(days=1))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("production:create")).status_code, 403)

    def test_stale_revision_and_double_submission_do_not_repeat_work(self):
        run = start_run(self.project, self.user, "speech", 0)
        with self.assertRaises(ProductionError):
            start_run(self.project, self.user, "speech", 0)
        run_production(run.pk); run_production(run.pk)
        self.assertEqual(self.provider.synthesize_dialogue.call_count, 1)
        self.production.refresh_from_db()
        with self.assertRaises(ProductionError):
            save_draft(self.project, self.user, 0, project_payload(self.project))

    def test_script_drift_stops_queued_generation_before_provider_call(self):
        run = start_run(self.project, self.user, "speech", 0)
        self.segment.text = "Geändert"; self.segment.save()
        run_production(run.pk); run.refresh_from_db()
        self.assertEqual(run.status, "failed")
        self.provider.synthesize_dialogue.assert_not_called()

    def test_speech_plan_mix_and_final_export_use_real_audio_processing(self):
        self.mix()
        self.assertEqual(self.production.stage, "mix")
        session = StudioSession.objects.get(project=self.project)
        self.assertEqual(len(session.state["clips"]), 3)
        self.assertEqual(session.state["mix"]["duck_release_ms"], 1000)
        self.assertTrue(Path(self.production.mix_asset.file_path).is_file())
        before = UsageEvent.objects.count()
        self.run_phase("export", {"format": "wav"})
        self.assertEqual(self.production.stage, "complete")
        self.assertEqual(Path(self.production.final_asset.file_path).read_bytes()[:4], b"RIFF")
        self.assertEqual(UsageEvent.objects.count(), before)
        response = self.client.get(reverse("production:detail", args=[self.project.pk]))
        self.assertContains(response, "Bereit für den Unterricht")
        self.assertContains(response, "css/production.css")

    def test_mix_reuses_existing_material_when_only_positions_change(self):
        self.mix()
        plan = deepcopy(self.production.plan); plan["items"][0]["start"] = .5
        save_plan(self.project, self.user, self.production.revision, plan)
        before = UsageEvent.objects.count()
        with patch("audio_studio.services.ElevenLabsAudioProvider.generate") as generate:
            self.run_phase("mix")
        generate.assert_not_called()
        self.assertEqual(UsageEvent.objects.count(), before)

    def test_shared_library_plan_and_mix_never_generate_sfx(self):
        from audio_studio.library import prepare_source
        from audio_studio.models import SoundLibraryAsset
        from production.services import estimate_mix
        source = Path(self.folder.name) / 'qa-ambience.wav'
        source.write_bytes(wav_bytes(.8))
        entry = SoundLibraryAsset.objects.create(key='qa-forest', title='QA Wald', description='Testdatei',
            category='nature', role='atmosphere', provenance='Nur Test', loop_verified=True)
        prepare_source(entry, source)
        entry.status = 'published'; entry.full_clean(); entry.save()
        self.plan['items'] = [dict(self.plan['items'][1], library_id=str(entry.pk), prompt='',
            duration=135, start=0, gain_db=-20, loop=True, generation_duration=0)]
        self.speech()
        with patch('production.services._provider_request', return_value=SimpleNamespace(payload=self.plan)) as provider:
            self.run_phase('plan')
        self.assertEqual(provider.call_args.args[0]['sound_library'][0]['library_id'], str(entry.pk))
        self.assertEqual(estimate_mix(self.production)['credits'], 0)
        before = UsageEvent.objects.count()
        with patch('audio_studio.services.ElevenLabsAudioProvider.generate') as generate:
            self.run_phase('mix')
        generate.assert_not_called()
        self.assertEqual(UsageEvent.objects.count(), before)
        session = StudioSession.objects.get(project=self.project)
        effect = next(c for c in session.state['clips'] if c['track'] == 'effects')
        self.assertEqual(effect['trim_end'], 135)
        self.assertAlmostEqual(self.production.mix_asset.duration, 135, delta=.08)

    def test_partial_music_success_is_reused_after_effect_failure(self):
        self.approve_audio()
        self.production.refresh_from_db()
        run = start_run(self.project, self.user, "mix", self.production.revision)
        with patch("audio_studio.services.ElevenLabsAudioProvider.generate", side_effect=[GeneratedAudio(mp3_bytes(3), "music-ok", Decimal(10)), ProviderRejected("Geräusch abgelehnt")]):
            run_production(run.pk)
        run.refresh_from_db(); self.production.refresh_from_db()
        self.assertEqual(run.status, "failed")
        self.assertEqual(len(self.production.materials), 1)
        with patch("audio_studio.services.ElevenLabsAudioProvider.generate", return_value=GeneratedAudio(mp3_bytes(1), "effect-ok", Decimal(10))) as generate:
            self.run_phase("mix")
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(generate.call_args.args[0], "effects")

    def test_manual_studio_change_requires_new_preview_before_export(self):
        self.mix()
        session = StudioSession.objects.get(project=self.project)
        session.state["clips"][1]["gain_db"] = -25
        save_state(self.project, self.user, session.revision, session.state)
        with self.assertRaises(ProductionError):
            start_run(self.project, self.user, "export", self.production.revision, {"format": "wav"})
        self.run_phase("preview")
        self.run_phase("export", {"format": "mp3"})

    def test_changed_plan_invalidates_export_approval(self):
        self.mix()
        plan = deepcopy(self.plan); plan["compression"] = 40
        prod = save_plan(self.project, self.user, self.production.revision, plan)
        with self.assertRaises(ProductionError):
            start_run(self.project, self.user, "export", prod.revision, {"format": "wav"})

    def test_changed_script_invalidates_audio_approval(self):
        self.approve_audio()
        self.segment.text = "Anderer Text"; self.segment.save()
        with self.assertRaises(ProductionError):
            start_run(self.project, self.user, "mix", self.production.revision)

    def test_plan_validates_ranges_overlap_and_foreign_material(self):
        for field, value in [("duration", 31), ("gain_db", float("nan")), ("asset_id", "00000000-0000-0000-0000-000000000000"), ("start", 1800)]:
            plan = deepcopy(self.plan); plan["items"][1][field] = value
            with self.assertRaises(ProductionError):
                validate_plan(self.project, plan, 10)
        self.assertEqual(len(validate_plan(self.project, self.plan, 10)["items"]), 2)
        other = deepcopy(self.plan["items"][0]); other["gain_db"] = -30; other["start"] = 8
        self.assertEqual(material_key(other), material_key(self.plan["items"][0]))

    def test_speech_reuse_charges_only_changed_text_and_applies_new_tempo(self):
        ScriptSegment.objects.create(project=self.project, speaker=self.speaker, text="Ein Vogel ruft.", pause_after_ms=0, position=2)
        audio = self.speech()
        self.segment.speed = Decimal("1.20"); self.segment.pause_after_ms = 200; self.segment.save()
        second = self.project.segments.get(position=2); second.text = "Ein Fuchs läuft."; second.save()
        self.provider.synthesize_dialogue.reset_mock()
        job = create_generation_job(self.project, self.user, reuse_job=audio.job)
        result = run_generation_job(job.pk)
        self.assertEqual(job.parts.filter(is_reused=True).count(), 1)
        self.assertEqual(job.parts.get(position=1).playback_speed, Decimal("1.20"))
        self.assertEqual(self.provider.synthesize_dialogue.call_count, 1)
        self.assertEqual(UsageLedger.objects.get(job=job).character_count, len(second.text))
        self.assertNotEqual(result.file_path, audio.file_path)

    def test_fully_reused_speech_costs_zero_and_has_independent_files(self):
        audio = self.speech()
        self.provider.synthesize_dialogue.reset_mock()
        job = create_generation_job(self.project, self.user, reuse_job=audio.job)
        run_generation_job(job.pk)
        self.provider.synthesize_dialogue.assert_not_called()
        self.assertIsNone(job.usage_event_id)
        self.assertEqual(job.character_count, 0)
        self.assertNotEqual(job.parts.get().audio_path, audio.job.parts.get().audio_path)

    def test_free_speech_reuse_works_with_exhausted_shared_credit_and_user_limits(self):
        audio = self.speech()
        ProviderBudget.objects.create(provider="elevenlabs", allocated_amount=0, monthly_credit_limit=1,
            starts_on=timezone.localdate() - timedelta(days=1), expires_on=timezone.localdate() + timedelta(days=365))
        self.user.character_limit = 1; self.user.save()
        before = UsageEvent.objects.count()
        self.provider.synthesize_dialogue.reset_mock()
        job = create_generation_job(self.project, self.user, reuse_job=audio.job)
        run_generation_job(job.pk)
        self.provider.synthesize_dialogue.assert_not_called()
        self.assertEqual(UsageEvent.objects.count(), before)
        from generation.services import ensure_generation_reservation
        self.assertIsNone(ensure_generation_reservation(job))

    def test_expired_speech_is_not_reused_or_approved(self):
        audio = self.speech(); audio.expires_at = timezone.now() - timedelta(seconds=1); audio.save()
        job = create_generation_job(self.project, self.user, reuse_job=audio.job)
        self.assertFalse(job.parts.filter(is_reused=True).exists())
        job.status = "failed"; job.save()
        with self.assertRaises(ProductionError):
            select_speech(self.project, self.user, self.production.revision, audio.pk)

    def test_copy_retains_guided_progress_with_independent_audio(self):
        self.mix()
        copy = duplicate_project(self.project)
        self.assertEqual(copy.production.stage, "mix")
        self.assertEqual(copy.production.approved_script, editable_project_snapshot(copy))
        self.assertEqual(copy.production.approved_audio.version.project_id, copy.pk)
        self.assertNotEqual(copy.production.mix_asset.file_path, self.production.mix_asset.file_path)
        self.assertEqual(len(copy.production.materials), 2)

    def test_active_production_blocks_deletion_and_copy(self):
        start_run(self.project, self.user, "speech", 0)
        with self.assertRaises(ProjectContentError):
            delete_project(self.project)
        with self.assertRaises(ProjectContentError):
            duplicate_project(self.project)

    def test_stale_worker_can_be_recovered_without_automatic_paid_retry(self):
        run = start_run(self.project, self.user, "speech", 0)
        ProductionRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(minutes=36))
        recover_stale_runs(self.project); run.refresh_from_db()
        self.assertEqual(run.status, "failed")
        self.assertIn("zusätzliche Credits", run.error_message)
        run_production(run.pk)
        self.provider.synthesize_dialogue.assert_not_called()

    def test_queue_failure_is_visible_and_does_not_call_provider(self):
        with patch("production.tasks.process_production.delay", side_effect=OSError("Queue unavailable")):
            with self.captureOnCommitCallbacks(execute=True):
                run = start_run(self.project, self.user, "speech", 0)
        run.refresh_from_db()
        self.assertEqual(run.status, "failed")
        self.provider.synthesize_dialogue.assert_not_called()

    def test_edited_plan_must_be_saved_and_cost_reviewed_before_generation(self):
        self.approve_audio()
        data = {"action": "mix", "revision": self.production.revision, "items-TOTAL_FORMS": 3, "items-INITIAL_FORMS": 2,
                "items-MIN_NUM_FORMS": 0, "items-MAX_NUM_FORMS": 12}
        for key, value in self.plan.items():
            if key != "items": data[f"plan-{key}"] = value
        for index, item in enumerate(self.plan["items"]):
            for key, value in item.items(): data[f"items-{index}-{key}"] = value if not isinstance(value, bool) else ("on" if value else "")
        data["items-0-duration"] = 4
        response = self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.production.refresh_from_db()
        self.assertEqual(self.production.plan["items"][0]["duration"], 4)
        self.assertFalse(self.project.production_runs.filter(kind="mix").exists())
        data["revision"] = self.production.revision
        self.client.post(reverse("production:action", args=[self.project.pk]), data)
        self.assertEqual(self.project.production_runs.filter(kind="mix").count(), 1)
