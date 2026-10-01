import tempfile
import uuid
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from audio_studio.models import StudioAsset, StudioJob, StudioRevision, StudioSession, empty_state
from generation.models import AudioAsset, GenerationJob, GenerationPart, ProjectVersion, UsageLedger
from generation.services import _period_usage
from projects.lifecycle import ProjectContentError, delete_project
from projects.models import Project, ScriptSegment, Speaker
from projects.services import duplicate_project
from usage_control.models import UsageEvent


class AudioLifecycleTests(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.settings_override = override_settings(AUDIO_STORAGE_ROOT=self.root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user(username="lifecycle", must_change_password=False)
        self.client.force_login(self.user)
        self.project = Project.objects.create(owner=self.user, title="Hörspiel", language="de")
        speaker = Speaker.objects.create(project=self.project, name="Mira")
        ScriptSegment.objects.create(project=self.project, speaker=speaker, text="Hallo!", position=1)
        self.version = ProjectVersion.objects.create(project=self.project, number=1, snapshot={"title": "Hörspiel"}, created_by=self.user)
        self.event = UsageEvent.objects.create(user=self.user, provider="elevenlabs", feature="audio", model="eleven_v4",
                                              status="committed", character_count=6, provider_credit_count=6,
                                              billing_period=timezone.localdate().replace(day=1))
        self.job = GenerationJob.objects.create(version=self.version, requested_by=self.user, status="succeeded",
                                                provider="elevenlabs", model="eleven_v4", character_count=6,
                                                estimated_cost_eur="0.01", usage_event=self.event)
        self.ledger = UsageLedger.objects.create(user=self.user, job=self.job, provider="elevenlabs", model="eleven_v4",
                                                character_count=6, estimated_cost_eur="0.01", billing_period=self.event.billing_period)
        self.audio = AudioAsset.objects.create(version=self.version, job=self.job, file_path=self.file("speech.mp3"),
                                                duration_seconds=5, size_bytes=5, expires_at=timezone.now() + timedelta(days=15))
        self.part = GenerationPart.objects.create(job=self.job, position=1, status="succeeded", input_data=[{"text": "Hallo!"}],
                                                  character_count=6, audio_path=self.file("part.mp3"))
        self.assets = [self.asset(kind) for kind in ("speech", "music", "effects", "mix")]
        self.assets[0].source_audio = self.audio
        self.assets[0].save()
        state = empty_state()
        state["mix"] = {"compression": 37, "music_duck_db": 3, "duck_attack_ms": 300, "duck_release_ms": 1000}
        state["tracks"]["music"]["gain_db"] = -2.5
        state["clips"] = [{"id": str(uuid.uuid4()), "asset_id": str(asset.pk), "track": asset.kind,
                           "start": index * .7, "trim_start": .2, "trim_end": 4.8,
                           "fade_in": .3, "fade_out": .6, "gain_db": -3.7}
                          for index, asset in enumerate(self.assets[:3])]
        self.session = StudioSession.objects.create(project=self.project, state=state, revision=1)
        StudioRevision.objects.create(session=self.session, state=state, number=1, created_by=self.user)
        self.music_event = UsageEvent.objects.create(user=self.user, provider="elevenlabs", feature="music", model="music_v2_5",
                                                    status="committed", billing_period=self.event.billing_period)
        self.music_job = StudioJob.objects.create(project=self.project, requested_by=self.user, kind="music", status="succeeded",
                                                  duration=5, usage_event=self.music_event, asset=self.assets[1], input_data={"prompt": "Musik"})

    def file(self, name):
        path = self.root / name
        path.write_bytes(b"audio")
        return str(path)

    def asset(self, kind):
        return StudioAsset.objects.create(project=self.project, title=kind, kind=kind,
                                         file_path=self.file(f"{kind}-studio.mp3"), original_path=self.file(f"{kind}-original.wav"),
                                         duration=5, size_bytes=5, waveform=[.1, .5, .2], expires_at=self.audio.expires_at)

    def test_complete_copy_preserves_timeline_and_independent_audio_without_usage(self):
        original_state = deepcopy(self.session.state)
        duplicate = duplicate_project(self.project)
        self.assertEqual(duplicate.studio_assets.count(), 4)
        for source in self.assets:
            copied = duplicate.studio_assets.get(kind=source.kind)
            self.assertNotEqual(copied.pk, source.pk)
            for name in ("file_path", "original_path"):
                self.assertNotEqual(getattr(copied, name), getattr(source, name))
                self.assertEqual(Path(getattr(copied, name)).read_bytes(), b"audio")
            self.assertEqual(copied.waveform, source.waveform)
            self.assertEqual(copied.expires_at, source.expires_at)
        copied_state = duplicate.studio.state
        self.assertEqual(copied_state["tracks"], original_state["tracks"])
        self.assertEqual(copied_state["mix"]["compression"], 37)
        for old, new in zip(original_state["clips"], copied_state["clips"]):
            self.assertNotEqual(new["asset_id"], old["asset_id"])
            self.assertEqual({k: v for k, v in new.items() if k != "asset_id"}, {k: v for k, v in old.items() if k != "asset_id"})
        self.assertEqual(duplicate.studio.revisions.get().state, copied_state)
        speech = duplicate.versions.get().audio_assets.get()
        self.assertTrue(speech.job.is_copy)
        self.assertEqual(duplicate.studio_assets.get(kind="speech").source_audio, speech)
        self.assertEqual(UsageLedger.objects.count(), 1)
        self.assertEqual(UsageEvent.objects.count(), 2)
        with self.captureOnCommitCallbacks(execute=True):
            delete_project(self.project)
        self.assertTrue(Path(speech.file_path).is_file())
        self.assertTrue(all(Path(a.file_path).is_file() for a in duplicate.studio_assets.all()))
        response = self.client.get(reverse("generation:play", args=[speech.pk]))
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_delete_preserves_all_usage_and_removes_content_and_files(self):
        before = _period_usage(self.user, timezone.localdate())
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("projects:delete", args=[self.project.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())
        self.assertEqual(_period_usage(self.user, timezone.localdate()), before)
        self.job.refresh_from_db()
        self.music_job.refresh_from_db()
        self.assertIsNone(self.job.version_id)
        self.assertIsNone(self.music_job.project_id)
        self.assertIsNone(self.music_job.asset_id)
        self.assertEqual(self.music_job.duration, 5)
        self.assertEqual(self.music_job.input_data, {})
        self.assertFalse(GenerationPart.objects.filter(job=self.job).exists())
        self.assertEqual(UsageLedger.objects.count(), 1)
        self.assertEqual(UsageEvent.objects.count(), 2)
        self.assertFalse(list(self.root.rglob("*.mp3")))
        self.assertFalse(list(self.root.rglob("*.wav")))

    def test_uncommitted_delete_keeps_audio_files(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            delete_project(self.project)
        self.assertEqual(len(callbacks), 1)
        self.assertTrue(Path(self.audio.file_path).exists())

    def test_missing_file_rolls_back_copy_and_removes_partial_files(self):
        Path(self.assets[1].file_path).unlink()
        with self.assertRaises(ProjectContentError):
            duplicate_project(self.project)
        self.assertEqual(Project.objects.count(), 1)
        self.assertFalse(list((self.root / "studio").rglob("*.mp3")))
        self.assertEqual(UsageLedger.objects.count(), 1)

    def test_copy_write_failure_removes_partial_file(self):
        def failed_copy(source, target):
            target.write_bytes(b"partial")
            raise OSError("Disk full")
        with patch("projects.lifecycle.shutil.copyfile", side_effect=failed_copy), self.assertRaises(ProjectContentError):
            duplicate_project(self.project)
        self.assertEqual(Project.objects.count(), 1)
        self.assertFalse(list((self.root / "studio").rglob("*.mp3")))

    def test_expired_current_clip_prevents_partial_copy(self):
        self.assets[2].expires_at = timezone.now() - timedelta(seconds=1)
        self.assets[2].save()
        with self.assertRaises(ProjectContentError):
            duplicate_project(self.project)
        self.assertEqual(Project.objects.count(), 1)

    def test_running_jobs_block_both_actions_with_readable_message(self):
        for job in (self.job, self.music_job):
            job.status = "running"
            job.save()
            for route in ("duplicate", "delete"):
                response = self.client.post(reverse(f"projects:{route}", args=[self.project.pk]))
                self.assertEqual(response.status_code, 302)
                self.assertIn("läuft noch", str(list(response.wsgi_request._messages)[0]))
                self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
            job.status = "succeeded"
            job.save()

    def test_foreign_user_cannot_duplicate_or_delete(self):
        other = get_user_model().objects.create_user(username="other-lifecycle", must_change_password=False)
        self.client.force_login(other)
        for route in ("duplicate", "delete"):
            self.assertEqual(self.client.post(reverse(f"projects:{route}", args=[self.project.pk])).status_code, 404)

    def test_deleted_project_job_cannot_be_retried(self):
        self.job.status = "failed"
        self.job.save()
        delete_project(self.project)
        with patch("generation.views.generate_audio.delay") as delay:
            self.assertEqual(self.client.post(reverse("generation:retry", args=[self.job.pk])).status_code, 404)
        delay.assert_not_called()

    def test_shared_audio_and_files_outside_storage_are_kept(self):
        other = Project.objects.create(owner=self.user, title="Shared", language="de")
        StudioAsset.objects.create(project=other, title="Shared", kind="music", file_path=self.assets[1].file_path,
                                   duration=5, size_bytes=5, expires_at=self.audio.expires_at)
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "keep.mp3"
            external.write_bytes(b"keep")
            self.assets[2].original_path = str(external)
            self.assets[2].save()
            with self.captureOnCommitCallbacks(execute=True):
                delete_project(self.project)
            self.assertTrue(external.exists())
            self.assertTrue(Path(self.assets[1].file_path).exists())

    def test_copy_maximum_length_title_and_expired_unused_assets(self):
        self.project.title = "A" * 160
        self.project.save()
        self.assets[3].expires_at = timezone.now() - timedelta(seconds=1)
        self.assets[3].save()
        duplicate = duplicate_project(self.project)
        self.assertLessEqual(len(duplicate.title), 160)
        self.assertEqual(duplicate.studio_assets.count(), 3)

    def test_admin_delete_uses_content_service(self):
        request = RequestFactory().post("/admin/")
        request.user = self.user
        with self.captureOnCommitCallbacks(execute=True):
            admin.site._registry[Project].delete_model(request, self.project)
        self.assertFalse(Path(self.audio.file_path).exists())
        self.assertEqual(UsageLedger.objects.count(), 1)
