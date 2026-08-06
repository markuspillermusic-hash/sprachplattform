from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from projects.models import Project, ScriptSegment, Speaker
from tts.providers.base import SynthesisResult

from generation.models import AudioAsset, GenerationJob, UsageLedger
from generation.services import (
    UsageLimitExceeded,
    assemble_mp3,
    build_generation_parts,
    build_project_snapshot,
    create_generation_job,
    run_generation_job,
)


class FakeProvider:
    def __init__(self):
        self.calls = []

    def synthesize_dialogue(self, inputs, options=None):
        self.calls.append((inputs, options))
        return SynthesisResult(
            audio=f"part-{len(self.calls)}".encode(),
            content_type="audio/mpeg",
            provider_request_id=f"request-{len(self.calls)}",
        )


class GenerationPipelineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audio",
            password="Test-Passphrase-123!",
            must_change_password=False,
        )
        self.project = Project.objects.create(owner=self.user, title="Dialog", language="en")
        self.speaker = Speaker.objects.create(
            project=self.project,
            name="Camille",
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-camille",
            accent=Speaker.Accent.BRITISH,
        )
        self.segment = ScriptSegment.objects.create(
            project=self.project,
            speaker=self.speaker,
            text="Bonjour ! Comment allez-vous ?",
            direction="friendly",
            pause_after_ms=700,
            position=1,
        )

    def test_long_text_is_split_below_provider_limit_and_keeps_final_pause(self):
        self.segment.text = ("Eine lange Aussage mit sinnvoller Wortgrenze. " * 100).strip()
        self.segment.save(update_fields=["text"])
        parts = build_generation_parts(build_project_snapshot(self.project))

        self.assertGreater(len(parts), 1)
        self.assertTrue(all(part["character_count"] <= 2000 for part in parts))
        self.assertTrue(all(part["pause_after_ms"] == 0 for part in parts[:-1]))
        self.assertEqual(parts[-1]["pause_after_ms"], 700)

    def test_job_creates_immutable_version_and_reserves_usage(self):
        job = create_generation_job(self.project, self.user)
        original_text = job.version.snapshot["segments"][0]["text"]
        self.segment.text = "Später geändert"
        self.segment.save(update_fields=["text"])

        job.version.refresh_from_db()
        self.assertEqual(job.version.number, 1)
        self.assertEqual(job.version.snapshot["segments"][0]["text"], original_text)
        self.assertEqual(job.parts.count(), 1)
        self.assertEqual(UsageLedger.objects.get(job=job).character_count, len(original_text))
        self.assertEqual(job.usage_event.status, "reserved")
        self.assertEqual(job.version.snapshot["speakers"][0]["accent"], "british")
        self.assertEqual(job.parts.get().input_data[0]["accent"], "British accent")

    def test_user_limit_is_enforced_before_job_creation(self):
        self.user.character_limit = 5
        self.user.save(update_fields=["character_limit"])

        with self.assertRaisesMessage(UsageLimitExceeded, "monatliches Zeichenlimit"):
            create_generation_job(self.project, self.user)

        self.assertFalse(GenerationJob.objects.exists())
        self.assertFalse(UsageLedger.objects.exists())

    def test_service_rejects_job_for_foreign_project(self):
        other = get_user_model().objects.create_user(
            username="foreign-audio",
            password="x",
            must_change_password=False,
        )

        with self.assertRaises(PermissionDenied):
            create_generation_job(self.project, other)

        self.assertFalse(GenerationJob.objects.exists())

    def test_mocked_provider_pipeline_creates_final_asset(self):
        job = create_generation_job(self.project, self.user)
        provider = FakeProvider()

        def fake_assembler(parts, output_path):
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"final-mp3")

        with TemporaryDirectory() as audio_root:
            asset = run_generation_job(job.pk, provider=provider, audio_root=audio_root, assembler=fake_assembler)
            self.assertEqual(Path(asset.file_path).read_bytes(), b"final-mp3")

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.SUCCEEDED)
        self.assertEqual(job.provider_request_ids, ["request-1"])
        self.assertIsNone(job.actual_cost_eur)
        self.assertIsNone(job.usage_entry.actual_cost_eur)
        job.usage_event.refresh_from_db()
        self.assertEqual(job.usage_event.status, "committed")
        self.assertEqual(provider.calls[0][0][0].accent, "British accent")

    @mock.patch("generation.services.subprocess.run")
    def test_assembler_fades_and_pads_every_phrase_before_the_configured_pause(self, run):
        parts = [
            SimpleNamespace(audio_path="part-1.mp3", pause_after_ms=700),
            SimpleNamespace(audio_path="part-2.mp3", pause_after_ms=0),
        ]

        assemble_mp3(
            parts,
            "final.mp3",
            tail_fade_ms=45,
            tail_padding_ms=80,
        )

        command = run.call_args.args[0]
        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertEqual(filter_complex.count("areverse,afade=t=in:st=0:d=0.045,areverse"), 2)
        self.assertEqual(filter_complex.count("apad=pad_dur=0.080"), 2)
        self.assertIn("anullsrc=r=44100:cl=stereo:d=0.700[s0]", filter_complex)
        run.assert_called_once()


class AudioAccessAndCleanupTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="owner", password="x", must_change_password=False)
        self.other = users.objects.create_user(username="other-audio", password="x", must_change_password=False)
        self.project = Project.objects.create(owner=self.owner, title="Audio", language="de")
        speaker = Speaker.objects.create(project=self.project, name="A", provider="elevenlabs", model="eleven_v3", voice_id="a")
        ScriptSegment.objects.create(project=self.project, speaker=speaker, text="Hallo", position=1)

    def test_other_user_cannot_download_asset(self):
        job = create_generation_job(self.project, self.owner)
        with TemporaryDirectory() as root:
            path = Path(root) / "audio.mp3"
            path.write_bytes(b"audio")
            asset = AudioAsset.objects.create(
                version=job.version,
                job=job,
                file_path=str(path),
                size_bytes=5,
                expires_at=timezone.now() + timezone.timedelta(days=1),
            )
            self.client.force_login(self.other)
            with override_settings(AUDIO_STORAGE_ROOT=root):
                response = self.client.get(reverse("generation:download", args=[asset.pk]))
            self.assertEqual(response.status_code, 404)

    def test_expired_audio_command_deletes_only_files_inside_audio_root(self):
        job = create_generation_job(self.project, self.owner)
        with TemporaryDirectory() as root:
            path = Path(root) / "expired.mp3"
            path.write_bytes(b"audio")
            asset = AudioAsset.objects.create(
                version=job.version,
                job=job,
                file_path=str(path),
                size_bytes=5,
                expires_at=timezone.now() - timezone.timedelta(seconds=1),
            )
            with override_settings(AUDIO_STORAGE_ROOT=root):
                call_command("delete_expired_audio", verbosity=0)
            asset.refresh_from_db()
            self.assertFalse(path.exists())
            self.assertIsNotNone(asset.deleted_at)
