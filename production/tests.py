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
from usage_control.models import UsageEvent
from accounts.models import TemporaryStudentAccess

from .models import Production, ProductionRun
from .planning import ProductionError, material_key, validate_plan
from .services import recover_stale_runs, run_production, save_draft, save_plan, select_speech, start_run


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
        job.usage_event.refresh_from_db()
        self.assertEqual(job.usage_event.estimated_credits, 0)
        self.assertEqual(job.usage_event.provider_credit_count, 0)
        self.assertNotEqual(job.parts.get().audio_path, audio.job.parts.get().audio_path)

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
