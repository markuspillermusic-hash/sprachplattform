import io
import json
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from audio_studio.demos import (DEMO_KEY, SAMPLES, bundle_folder, demo_state,
                               ensure_audio_drama_demo, prepare_bundle, read_bundle)
from audio_studio.models import StudioAsset, StudioDemoEnrollment
from audio_studio.services import live_assets
from usage_control.models import UsageEvent


@override_settings(SECURE_SSL_REDIRECT=False)
class AudioDramaDemoTests(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        override = override_settings(AUDIO_STORAGE_ROOT=Path(self.folder.name))
        override.enable(); self.addCleanup(override.disable)
        self.user = get_user_model().objects.create_user(username="demo-drama", must_change_password=False,
                                                        demo_projects_initialized=True, is_staff=True)
        self.other = get_user_model().objects.create_user(username="other-drama", must_change_password=False,
                                                         demo_projects_initialized=True)
        self.bundle = {"key": DEMO_KEY, "samples": {}}
        root = bundle_folder(); root.mkdir(parents=True)
        for name, (title, kind) in SAMPLES.items():
            duration = 45 if kind == "music" else 12 if name == "clock" else 3
            self.bundle["samples"][name] = {"title": title, "kind": kind, "duration": duration, "waveform": [.1]}
            (root / f"{name}.mp3").write_bytes(b"fixture-audio")
        self.bundle["state"] = demo_state(self.bundle["samples"])
        self.bundle["samples"]["mix"] = {"title": "Fertiger Mix", "kind": "mix", "duration": 27, "waveform": [.1]}
        (root / "mix.mp3").write_bytes(b"fixture-mix")
        (root / "manifest.json").write_text(json.dumps(self.bundle), encoding="utf-8")

    def test_existing_users_receive_independent_editable_copies_without_provider_usage(self):
        first = ensure_audio_drama_demo(self.user)
        second = ensure_audio_drama_demo(self.other)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.demo_key, DEMO_KEY)
        self.assertEqual(first.segments.count(), 6)
        self.assertEqual(first.studio_assets.count(), 11)
        self.assertEqual(first.studio_jobs.get().status, "succeeded")
        self.assertSetEqual({c["track"] for c in first.studio.state["clips"]}, {"speech", "music", "effects"})
        self.assertTrue(first.studio.state["speech_compression"])
        self.assertTrue(first.studio.state["effects_ducking"])
        first_ids = {c["asset_id"] for c in first.studio.state["clips"]}
        second_ids = {c["asset_id"] for c in second.studio.state["clips"]}
        self.assertFalse(first_ids & second_ids)
        self.assertFalse(UsageEvent.objects.exists())
        sample = first.studio_assets.exclude(kind="mix").first()
        other_sample = second.studio_assets.get(title=sample.title)
        Path(sample.file_path).write_bytes(b"personal-change")
        self.assertEqual(Path(other_sample.file_path).read_bytes(), b"fixture-audio")

    def test_revisiting_preserves_user_edits_and_deleted_demo_stays_deleted(self):
        project = ensure_audio_drama_demo(self.user)
        project.title = "Mein eigener Schluss"; project.save()
        self.assertEqual(ensure_audio_drama_demo(self.user).title, project.title)
        self.assertEqual(StudioDemoEnrollment.objects.filter(user=self.user).count(), 1)
        project.delete()
        self.assertIsNone(ensure_audio_drama_demo(self.user))
        self.assertIsNotNone(ensure_audio_drama_demo(self.user, restore=True))

    def test_demo_is_discoverable_for_admin_even_with_demos_hidden(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("projects:list"))
        project = self.user.studio_demo_enrollment.project
        self.assertNotIn(project, response.context["projects"])
        self.assertContains(response, "Hörspiel-Demo im Studio öffnen")
        self.assertContains(response, reverse("audio_studio:editor", args=[project.pk]))
        self.assertContains(response, 'aria-label="Hörspiel-Demo anhören"')

    def test_samples_are_protected_and_only_reference_samples_survive_retention(self):
        project = ensure_audio_drama_demo(self.user)
        sample = project.studio_assets.first()
        project.studio_assets.update(expires_at=timezone.now() - timedelta(days=40))
        ordinary = StudioAsset.objects.create(project=project, title="Eigener Upload", kind="upload",
                                               file_path=str(Path(self.folder.name) / "upload.mp3"), duration=1,
                                               size_bytes=3, expires_at=timezone.now() - timedelta(days=1))
        Path(ordinary.file_path).write_bytes(b"old")
        call_command("delete_expired_audio", stdout=io.StringIO())
        self.assertEqual(live_assets(project).count(), 11)
        self.assertTrue(Path(sample.file_path).exists())
        self.assertFalse(Path(ordinary.file_path).exists())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("audio_studio:asset", args=[project.pk, sample.pk])).status_code, 404)
        self.client.force_login(self.user)
        data = self.client.get(reverse("audio_studio:state", args=[project.pk])).json()
        self.assertTrue(all(a["expires_at"] is None for a in data["assets"]))
        self.assertIsNotNone(data["jobs"][0]["asset"])

    def test_partial_bundle_does_not_create_a_broken_project_or_enrollment(self):
        (bundle_folder() / "music.mp3").unlink()
        self.assertIsNone(read_bundle())
        self.assertIsNone(ensure_audio_drama_demo(self.user))
        self.assertFalse(StudioDemoEnrollment.objects.exists())

    def test_failed_copy_rolls_back_database_and_removes_partial_files(self):
        original = shutil.copyfile
        count = 0
        def interrupted(source, target):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("interrupted")
            return original(source, target)
        with patch("audio_studio.demos.shutil.copyfile", side_effect=interrupted):
            with self.assertRaises(OSError):
                ensure_audio_drama_demo(self.user)
        self.assertFalse(self.user.projects.exists())
        self.assertFalse(StudioDemoEnrollment.objects.exists())
        self.assertFalse(list((Path(self.folder.name) / "studio").rglob("*.mp3")))

    def test_seed_is_idempotent_and_does_not_overwrite_existing_demo(self):
        output = io.StringIO()
        call_command("seed_audio_drama_demo", stdout=output)
        self.assertEqual(StudioDemoEnrollment.objects.count(), 2)
        call_command("seed_audio_drama_demo", stdout=output)
        self.assertEqual(StudioDemoEnrollment.objects.count(), 2)

    @skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_reference_mix_is_rendered_once_from_real_audio(self):
        from audio_studio.media import normalize, probe
        from audio_studio.tests.test_studio import wav_bytes
        root = bundle_folder()
        (root / "manifest.json").unlink()
        source = root / "tone.wav"
        source.write_bytes(wav_bytes(6))
        progress = {}
        for name in SAMPLES:
            duration, peaks = normalize(source, root / f"{name}.mp3")
            progress[name] = {"status": "ready", "duration": duration, "waveform": peaks}
        (root / "generation-progress.json").write_text(json.dumps(progress))
        bundle = prepare_bundle()
        self.assertGreater(probe(root / "mix.mp3"), 40)
        self.assertEqual(len(bundle["samples"]), 11)
        with patch("audio_studio.demos.render_mix", side_effect=AssertionError("rendered again")):
            self.assertEqual(prepare_bundle(), bundle)
