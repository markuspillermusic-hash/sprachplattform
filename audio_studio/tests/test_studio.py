import io
import json
import math
import shutil
import struct
import tempfile
import uuid
import wave
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import skipUnless
from unittest.mock import Mock, patch

import httpx
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from projects.models import Project
from usage_control.models import ProviderBudget, UsageEvent
from usage_control.services import QuotaExceeded, release_usage
from audio_studio.admin import ConfigurationForm
from audio_studio.media import StudioError
from audio_studio.models import StudioAsset, StudioConfiguration, StudioJob, StudioSession, empty_state
from audio_studio.providers import ElevenLabsAudioProvider, GeneratedAudio, ProviderRejected
from audio_studio.services import (RevisionConflict, create_export, create_generation, queue_failed,
                                   recover_stale_jobs, run_job, save_state, validate_state)


def wav_bytes(seconds=2, frequency=440, amplitude=.2):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
        audio.writeframes(b"".join(struct.pack("<h", round(32767 * amplitude * math.sin(2 * math.pi * frequency * i / 44100)))
                                   for i in range(round(seconds * 44100))))
    return stream.getvalue()


@override_settings(ELEVENLABS_API_KEY="test-studio-key", SECURE_SSL_REDIRECT=False)
class StudioFixture(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        override = override_settings(AUDIO_STORAGE_ROOT=Path(self.folder.name))
        override.enable(); self.addCleanup(override.disable)
        users = get_user_model()
        self.user = users.objects.create_user(username="studio", password="test-password", must_change_password=False)
        self.other = users.objects.create_user(username="other", must_change_password=False)
        self.project = Project.objects.create(owner=self.user, title="Bahnhof", language="de")
        self.foreign = Project.objects.create(owner=self.other, title="Privat", language="de")
        self.config = StudioConfiguration.objects.create(music_enabled=True, effects_enabled=True,
                                                         music_eur_per_minute="0.5", effects_eur_per_minute="0.2")
        self.asset = StudioAsset.objects.create(project=self.project, title="Sprache", kind="speech",
                                                duration=20, size_bytes=10, file_path=str(Path(self.folder.name)/"speech.mp3"),
                                                expires_at=timezone.now() + timedelta(days=1))
        self.client.force_login(self.user)

    def url(self, action, project=None):
        return reverse(f"audio_studio:{action}", args=[(project or self.project).pk])

    def state(self):
        state = empty_state()
        state["clips"] = [{"id": str(uuid.uuid4()), "asset_id": str(self.asset.pk), "track": "speech",
                            "start": 1, "trim_start": 0, "trim_end": 10, "gain_db": 0,
                            "fade_in": .3, "fade_out": .3}]
        return state

    def post(self, action, value, project=None):
        return self.client.post(self.url(action, project), json.dumps(value), content_type="application/json")


class StudioTests(StudioFixture):
    def test_editor_and_read_do_not_create_session(self):
        self.assertContains(self.client.get(self.url("editor")), "Alle hörbaren Spuren exportieren")
        data = self.client.get(self.url("state")).json()
        self.assertEqual(data["state"], empty_state())
        self.assertFalse(StudioSession.objects.exists())

    def test_every_project_endpoint_requires_project_access(self):
        for action in ("editor", "state", "jobs"):
            self.assertEqual(self.client.get(self.url(action, self.foreign)).status_code, 404)
        for action in ("save", "generate", "export", "import", "upload"):
            self.assertEqual(self.post(action, {}, self.foreign).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url("editor")).status_code, 302)

    def test_save_versions_and_conflicting_window(self):
        snapshot = self.state()
        session = save_state(self.project, self.user, 0, snapshot)
        snapshot["clips"][0]["start"] = 8
        with self.assertRaises(RevisionConflict):
            save_state(self.project, self.user, 0, snapshot)
        self.assertEqual(session.revisions.get().state["clips"][0]["start"], 1)
        self.assertEqual(self.post("save", {"revision": 0, "state": snapshot}).status_code, 409)
        self.assertEqual(self.post("save", {"revision": 1, "state": snapshot}).status_code, 200)

    def test_invalid_ranges_foreign_assets_and_expiry(self):
        for key, bad in (("start", -1), ("start", 1800), ("trim_end", 21), ("trim_end", 0),
                         ("gain_db", 13), ("gain_db", True), ("fade_in", 10), ("trim_start", float("nan"))):
            state = self.state(); state["clips"][0][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(StudioError):
                validate_state(self.project, state)
        state = self.state(); state["clips"][0]["asset_id"] = str(uuid.uuid4())
        with self.assertRaises(StudioError): validate_state(self.project, state)
        self.asset.expires_at = timezone.now() - timedelta(seconds=1); self.asset.save()
        with self.assertRaises(StudioError): validate_state(self.project, self.state())

    def test_duplicate_ids_and_malformed_json(self):
        state = self.state(); state["clips"].append(state["clips"][0].copy())
        self.assertEqual(self.post("save", {"revision": 0, "state": state}).status_code, 422)
        response = self.client.post(self.url("save"), "[", content_type="application/json")
        self.assertEqual(response.status_code, 422)

    def test_optional_sound_settings_support_existing_saved_states(self):
        state = self.state()
        state.pop("effects_ducking"); state.pop("speech_compression")
        validated = validate_state(self.project,state)
        self.assertFalse(validated["speech_compression"])
        self.assertFalse(validated["effects_ducking"])
        state["speech_compression"]="true"
        with self.assertRaises(StudioError): validate_state(self.project,state)

    def test_project_offers_optional_radio_play_tool(self):
        response=self.client.get(reverse("projects:editor",args=[self.project.pk]))
        self.assertContains(response,"Optional: Hörspiel-Produktion")
        self.assertContains(response,"Hörspiel-Studio öffnen")

    def test_mix_knobs_validate_and_survive_export_snapshots(self):
        from audio_studio.mixing import mix_settings, MIX_RANGES
        state = self.state()
        self.assertEqual(mix_settings(state)["music_duck_db"], 4)
        state["mix"] = {"music_duck_db": 6, "effects_duck_db": 0, "compression": 62,
                        "duck_attack_ms": 400, "duck_release_ms": 1200}
        saved = save_state(self.project, self.user, 0, state)
        job = create_export(self.project, self.user, saved.revision, "wav")
        self.assertEqual(job.input_data["state"]["mix"]["compression"], 62)
        for key, (low, high) in MIX_RANGES.items():
            for value in (low - 1, high + 1, True, float("nan"), "50"):
                state["mix"] = {key: value}
                with self.subTest(key=key, value=value), self.assertRaises(StudioError):
                    validate_state(self.project, state)
        state["mix"] = []
        with self.assertRaises(StudioError): validate_state(self.project, state)

    def test_export_snapshot_and_revision_validation(self):
        session = save_state(self.project, self.user, 0, self.state())
        job = create_export(self.project, self.user, session.revision, "wav")
        new = self.state(); new["clips"][0]["start"] = 9
        save_state(self.project, self.user, 1, new)
        self.assertEqual(job.input_data["state"]["clips"][0]["start"], 1)
        with self.assertRaises(RevisionConflict): create_export(self.project, self.user, 1, "wav")
        with self.assertRaises(StudioError): create_export(self.project, self.user, 2, "exe")

    def test_muted_clips_do_not_export(self):
        state = self.state(); state["tracks"]["speech"]["mute"] = True
        session = save_state(self.project, self.user, 0, state)
        with self.assertRaises(StudioError): create_export(self.project, self.user, session.revision, "mp3")

    def test_separate_duration_quota_with_no_speech_characters(self):
        self.config.music_seconds_per_user_month = 10; self.config.save()
        first = create_generation(self.project, self.user, {"kind": "music", "prompt": "Jingle", "duration": 6})
        self.assertEqual(first.usage_event.feature, UsageEvent.Feature.MUSIC)
        self.assertEqual(first.usage_event.character_count, 0)
        with self.assertRaises(StudioError):
            create_generation(self.project, self.user, {"kind": "music", "prompt": "Jingle", "duration": 6})
        release_usage(first.usage_event)
        self.assertIsNotNone(create_generation(self.project, self.user, {"kind": "music", "prompt": "Jingle", "duration": 6}))

    def test_provider_budget_applies_to_music(self):
        today = timezone.localdate()
        ProviderBudget.objects.create(provider="elevenlabs", starts_on=today, expires_on=today+timedelta(days=30),
                                       allocated_amount=Decimal("0.01"), enforce_monthly_pacing=False)
        with self.assertRaises(QuotaExceeded):
            create_generation(self.project, self.user, {"kind": "music", "prompt": "Jingle", "duration": 6})

    def test_disabled_and_invalid_generation(self):
        for data in ({"kind": "music", "prompt": "", "duration": 6},
                     {"kind": "effects", "prompt": "Regen", "duration": 31},
                     {"kind": "effects", "prompt": "Regen", "duration": 1, "loop": "yes"}):
            self.assertEqual(self.post("generate", data).status_code, 422)
        self.config.music_enabled = False; self.config.save()
        self.assertEqual(self.post("generate", {"kind": "music", "prompt": "Musik", "duration": 6}).status_code, 422)

    def test_queue_failure_releases_reserved_budget(self):
        with patch("audio_studio.views.process_audio.delay", side_effect=RuntimeError("private details")):
            result = self.post("generate", {"kind": "music", "prompt": "Musik", "duration": 6})
        job = StudioJob.objects.get(pk=result.json()["job"]["id"])
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.usage_event.status, "released")
        self.assertNotIn("private details", job.error_message)

    def test_queue_failure_does_not_cancel_claimed_job(self):
        job = create_generation(self.project, self.user, {"kind": "music", "prompt": "Musik", "duration": 6})
        job.status = "running"; job.save()
        queue_failed(job); job.refresh_from_db()
        self.assertEqual(job.status, "running")
        self.assertEqual(job.usage_event.status, "reserved")

    def test_stale_worker_recovery_accounts_for_possible_provider_call(self):
        for attempted, expected in ((False, "released"), (True, "committed")):
            job = create_generation(self.project, self.user, {"kind": "effects", "prompt": "Regen", "duration": 2})
            job.status = "running"
            job.started_at = timezone.now()-timedelta(minutes=21)
            job.provider_attempted = attempted
            job.save()
            recover_stale_jobs(); job.refresh_from_db()
            self.assertEqual(job.status,"failed")
            self.assertEqual(job.usage_event.status,expected)

    def test_upload_limit_and_csrf_are_enforced(self):
        with override_settings(AUDIO_STUDIO_MAX_UPLOAD_BYTES=2):
            response=self.client.post(self.url("upload"),{"audio":SimpleUploadedFile("large.wav",b"123")})
        self.assertEqual(response.status_code,422)
        from django.test import Client
        csrf_client=Client(enforce_csrf_checks=True); csrf_client.force_login(self.user)
        response=csrf_client.post(self.url("save"),json.dumps({"revision":0,"state":self.state()}),content_type="application/json")
        self.assertEqual(response.status_code,403)

    def test_rejection_releases_but_unknown_completion_retains_usage(self):
        for exception, status in ((ProviderRejected("HTTP 403"), "released"), (StudioError("Timeout"), "committed")):
            job = create_generation(self.project, self.user, {"kind": "effects", "prompt": "Regen", "duration": 2})
            provider = Mock(); provider.generate.side_effect = exception
            run_job(job.pk, provider); job.refresh_from_db()
            self.assertEqual(job.status, "failed")
            self.assertEqual(job.usage_event.status, status)
            run_job(job.pk, provider)
            self.assertEqual(provider.generate.call_count, 1)

    def test_asset_access_expiry_and_path_confinement(self):
        outside = Path(self.folder.name).parent / "outside.mp3"
        self.asset.file_path = str(outside); self.asset.save()
        url = reverse("audio_studio:asset", args=[self.project.pk,self.asset.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        foreign_url = reverse("audio_studio:asset", args=[self.foreign.pk,self.asset.pk])
        self.assertEqual(self.client.get(foreign_url).status_code, 404)

    def test_keys_are_encrypted_and_configuration_requires_rate(self):
        self.config.set_api_key("secret-studio-key"); self.config.save()
        self.assertNotIn("secret-studio-key", self.config.encrypted_api_key)
        self.assertEqual(self.config.get_api_key(), "secret-studio-key")
        data = {"name": "Musik", "music_enabled": True, "music_model": "music_v1", "music_eur_per_minute": 0,
                "effects_eur_per_minute": 0, "music_seconds_per_user_month": 10, "effects_seconds_per_user_month": 10}
        self.assertFalse(ConfigurationForm(data, instance=self.config).is_valid())


class ProviderTests(TestCase):
    @override_settings(ELEVENLABS_API_KEY="provider-test-key")
    def test_music_and_effects_request_contracts(self):
        seen = []
        def respond(request):
            seen.append((request.url.path, json.loads(request.content), request.headers["xi-api-key"], dict(request.url.params)))
            return httpx.Response(200, content=b"audio", headers={"character-cost": "80", "request-id": "test-request"})
        config = StudioConfiguration()
        with httpx.Client(base_url="https://api.elevenlabs.io", transport=httpx.MockTransport(respond)) as client:
            provider = ElevenLabsAudioProvider(config, client)
            result = provider.generate("music", {"prompt": "Jingle", "duration": 6, "model": config.music_model})
            provider.generate("effects", {"prompt": "Regen", "duration": 2, "loop": True})
        self.assertEqual(seen[0][0], "/v1/music")
        self.assertEqual(seen[0][1]["music_length_ms"], 6000)
        self.assertTrue(seen[0][1]["force_instrumental"])
        self.assertEqual(seen[0][1]["model_id"], "music_v2_5")
        self.assertEqual(seen[0][3]["output_format"], "auto")
        self.assertEqual(seen[1][0], "/v1/sound-generation")
        self.assertTrue(seen[1][1]["loop"])
        self.assertEqual(seen[1][1]["model_id"], "eleven_text_to_sound_v2")
        self.assertEqual(seen[1][3]["output_format"], "mp3_44100_128")
        self.assertEqual(result.credits, Decimal(80))

    @override_settings(ELEVENLABS_API_KEY="provider-test-key")
    def test_errors_never_expose_provider_payload(self):
        config = StudioConfiguration()
        with httpx.Client(base_url="https://api.elevenlabs.io", transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"secret": "do-not-show"}))) as client:
            with self.assertRaises(ProviderRejected) as error:
                ElevenLabsAudioProvider(config, client).generate("effects", {"prompt": "Rain", "duration": 2, "loop": False})
        self.assertNotIn("do-not-show", str(error.exception))


@skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg integration requires ffmpeg and ffprobe")
class AudioIntegrationTests(StudioFixture):
    def upload_wav(self, title, duration, frequency=440, amplitude=.2):
        response = self.client.post(self.url("upload"), {"audio": SimpleUploadedFile(title+".wav", wav_bytes(duration, frequency, amplitude))})
        self.assertEqual(response.status_code, 201, response.content)
        return StudioAsset.objects.get(pk=response.json()["asset"]["id"])

    def test_three_track_upload_save_and_actual_wav_export(self):
        music = self.upload_wav("Musik", 6)
        speech = self.upload_wav("Sprache", 2, amplitude=0)
        effects = self.upload_wav("Geräusch", .5, frequency=880)
        self.assertTrue(Path(music.original_path).is_file())
        state = empty_state()
        def clip(asset, track, start, end, fade=0):
            return {"id": str(uuid.uuid4()), "asset_id": str(asset.pk), "track": track, "start": start,
                    "trim_start": 0, "trim_end": end, "gain_db": 0, "fade_in": fade, "fade_out": fade}
        state["clips"] = [clip(music,"music",0,6,1), clip(speech,"speech",2,2), clip(effects,"effects",5,.5)]
        session = save_state(self.project, self.user, 0, state)
        job = create_export(self.project, self.user, session.revision, "wav")
        run_job(job.pk); job.refresh_from_db()
        self.assertEqual(job.status, "succeeded", job.error_message)
        with wave.open(job.asset.file_path, "rb") as audio:
            self.assertEqual(audio.getnchannels(), 2)
            self.assertEqual(audio.getframerate(), 44100)
            data = audio.readframes(audio.getnframes())
        samples = [s[0]/32768 for s in struct.iter_unpack("<hh", data)]
        def rms(start,end):
            values = samples[round(start*44100):round(end*44100)]
            return math.sqrt(sum(x*x for x in values)/len(values))
        self.assertAlmostEqual(job.asset.duration,6,places=2)
        self.assertAlmostEqual(rms(2.5,3.5) / rms(1.2,1.8), 10 ** (-4/20), delta=.03)
        self.assertLess(rms(.05,.15), rms(1.2,1.8)*.2)
        self.assertGreater(rms(5.1,5.3), rms(4.5,4.8))
        self.assertLess(rms(5.9,5.99), rms(4.5,4.8)*.2)
        download = self.client.get(reverse("audio_studio:asset", args=[self.project.pk,job.asset.pk])+"?download=1")
        self.assertEqual(download["Content-Type"], "audio/wav")
        self.assertIn("attachment", download["Content-Disposition"])
        download.close()

    def render_samples(self,state,filename):
        from audio_studio.media import render_mix
        target=Path(self.folder.name)/filename
        render_mix(state,{str(a.pk):a for a in StudioAsset.objects.all()},target,"wav")
        with wave.open(str(target),"rb") as audio:
            return [s[0]/32768 for s in struct.iter_unpack("<hh",audio.readframes(audio.getnframes()))]

    def test_overlapping_effects_are_mixed_and_limited(self):
        effect=self.upload_wav("Effekt",2,amplitude=.5)
        state=empty_state()
        state["clips"]=[{"id":str(uuid.uuid4()),"asset_id":str(effect.pk),"track":"effects","start":0,
                          "trim_start":0,"trim_end":2,"gain_db":0,"fade_in":0,"fade_out":0}]
        single=self.render_samples(state,"single.wav")
        state["clips"] += [dict(state["clips"][0],id=str(uuid.uuid4())) for _ in range(7)]
        stacked=self.render_samples(state,"stacked.wav")
        self.assertGreater(max(abs(x) for x in stacked),max(abs(x) for x in single)*1.5)
        self.assertLessEqual(max(abs(x) for x in stacked),.9501)
        self.assertAlmostEqual(len(single),len(stacked),delta=2)

    def test_speech_compression_increases_quiet_passages_and_reduces_dynamic_range(self):
        audio=io.BytesIO()
        with wave.open(audio,"wb") as out:
            out.setparams((1,2,44100,0,"NONE","not compressed"))
            for amplitude in (.03,.6):
                with wave.open(io.BytesIO(wav_bytes(2,amplitude=amplitude)),"rb") as segment:
                    out.writeframes(segment.readframes(segment.getnframes()))
        result=self.client.post(self.url("upload"),{"audio":SimpleUploadedFile("dynamic.wav",audio.getvalue())})
        self.assertEqual(result.status_code,201,result.content)
        asset_id=result.json()["asset"]["id"]
        state=empty_state()
        state["clips"]=[{"id":str(uuid.uuid4()),"asset_id":asset_id,"track":"speech","start":0,
                          "trim_start":0,"trim_end":4,"gain_db":0,"fade_in":0,"fade_out":0}]
        plain=self.render_samples(state,"plain.wav")
        state["speech_compression"]=True
        state["mix"]={"compression":100}
        compressed=self.render_samples(state,"compressed.wav")
        def rms(samples,start,end):
            segment=samples[round(start*44100):round(end*44100)]
            return math.sqrt(sum(x*x for x in segment)/len(segment))
        self.assertGreater(rms(compressed,.5,1.5),rms(plain,.5,1.5)*1.2)
        ratio=lambda samples:rms(samples,2.5,3.5)/rms(samples,.5,1.5)
        self.assertLess(ratio(compressed),ratio(plain)*.7)

    def test_effects_duck_only_when_enabled_and_speech_audible(self):
        effects=self.upload_wav("Kulisse",4)
        speech=self.upload_wav("Sprechpause",2,amplitude=0)
        state=empty_state()
        state["clips"]=[{"id":str(uuid.uuid4()),"asset_id":str(a.pk),"track":track,"start":start,
                          "trim_start":0,"trim_end":end,"gain_db":0,"fade_in":0,"fade_out":0}
                         for a,track,start,end in ((effects,"effects",0,4),(speech,"speech",1,2))]
        plain=self.render_samples(state,"effects-plain.wav")
        state["effects_ducking"]=True
        ducked=self.render_samples(state,"effects-duck.wav")
        state["tracks"]["speech"]["mute"]=True
        muted=self.render_samples(state,"effects-muted.wav")
        def rms(samples):
            data=samples[round(1.5*44100):round(2.5*44100)]
            return math.sqrt(sum(x*x for x in data)/len(data))
        self.assertAlmostEqual(rms(ducked)/rms(plain),10 ** (-2/20),delta=.02)
        self.assertAlmostEqual(rms(muted)/rms(plain),1,delta=.02)

    def test_duck_attack_release_and_short_pauses_are_gentle_in_actual_export(self):
        from audio_studio.media import speech_intervals
        effects = self.upload_wav("Kulisse", 5)
        speech = self.upload_wav("Stille Sprache", 1, amplitude=0)
        state = empty_state()
        state["mix"] = {"effects_duck_db": 6, "duck_attack_ms": 400, "duck_release_ms": 1000}
        state["clips"] = [{"id":str(uuid.uuid4()),"asset_id":str(a.pk),"track":track,"start":start,
                           "trim_start":0,"trim_end":end,"gain_db":0,"fade_in":0,"fade_out":0}
                          for a,track,start,end in ((effects,"effects",0,5),(speech,"speech",1,1),
                                                   (speech,"speech",2.5,1))]
        self.assertEqual(speech_intervals(state), [[1, 3.5]])
        samples = self.render_samples(state, "natural-duck.wav")
        def rms(start, end):
            data = samples[round(start*44100):round(end*44100)]
            return math.sqrt(sum(x*x for x in data)/len(data))
        base = rms(.2,.4)
        self.assertAlmostEqual(rms(1.5,1.7)/base, 10 ** (-6/20), delta=.02)
        self.assertAlmostEqual(rms(2.2,2.3)/base, 10 ** (-6/20), delta=.02)
        self.assertGreater(rms(.8,.9), rms(1.5,1.7))
        self.assertLess(rms(.8,.9), base)
        self.assertLess(rms(3.6,3.7), rms(4.2,4.3))
        self.assertAlmostEqual(rms(4.6,4.8)/base, 1, delta=.02)

    def test_speech_compressor_does_not_compress_solo_music(self):
        music = self.upload_wav("Music", 2, amplitude=.4)
        state = empty_state()
        state["tracks"]["music"]["solo"] = True
        state["clips"] = [{"id":str(uuid.uuid4()),"asset_id":str(music.pk),"track":"music","start":0,
                           "trim_start":0,"trim_end":2,"gain_db":0,"fade_in":0,"fade_out":0}]
        plain = self.render_samples(state, "music-no-compression.wav")
        state["mix"] = {"compression": 100}
        compressed = self.render_samples(state, "music-with-speech-compression.wav")
        self.assertEqual(plain, compressed)

    def test_generated_quiet_effects_get_audible_peaks_and_keep_the_original(self):
        from audio_studio.services import create_asset
        source = Path(self.folder.name) / "quiet-effect.wav"
        source.write_bytes(wav_bytes(2, amplitude=.02))
        asset = create_asset(self.project, source, "Leises KI-Geräusch", "effects")
        self.assertGreater(max(asset.waveform), .5)
        self.assertLess(max(asset.waveform), .7)
        self.assertEqual(Path(asset.original_path).read_bytes(), source.read_bytes())

    def test_provider_result_normalized_and_duplicate_delivery_ignored(self):
        from audio_studio.media import run
        source = Path(self.folder.name)/"source.wav"; source.write_bytes(wav_bytes(3))
        target = Path(self.folder.name)/"result.mp3"
        run(["ffmpeg","-v","error","-i",str(source),"-y",str(target)])
        provider = Mock(); provider.generate.return_value = GeneratedAudio(target.read_bytes(), "req123", Decimal(120))
        job = create_generation(self.project,self.user,{"kind":"effects","prompt":"Atmosphäre","duration":3})
        run_job(job.pk,provider); run_job(job.pk,provider); job.refresh_from_db()
        self.assertEqual(job.status,"succeeded",job.error_message)
        self.assertEqual(job.provider_request_id,"req123")
        self.assertEqual(job.usage_event.provider_credit_count,Decimal(120))
        self.assertEqual(provider.generate.call_count,1)
        self.assertTrue(job.asset.waveform)

    def test_invalid_audio_is_rejected_and_temporary_files_removed(self):
        response = self.client.post(self.url("upload"), {"audio": SimpleUploadedFile("bad.mp3", b"not audio")})
        self.assertEqual(response.status_code,422)
        self.assertFalse(list((Path(self.folder.name)/"studio").rglob("*.mp3")))

    def test_speech_import_is_owned_deduplicated_and_retains_expiry(self):
        from generation.models import AudioAsset, GenerationJob, ProjectVersion
        version=ProjectVersion.objects.create(project=self.project,number=1,snapshot={},created_by=self.user)
        job=GenerationJob.objects.create(version=version,requested_by=self.user,provider="elevenlabs",model="eleven_v3",
                                         character_count=1,estimated_cost_eur=0,status="succeeded")
        path=Path(self.folder.name)/"speech.wav"; path.write_bytes(wav_bytes(1))
        source=AudioAsset.objects.create(version=version,job=job,file_path=str(path),size_bytes=path.stat().st_size,
                                         expires_at=timezone.now()+timedelta(hours=1))
        first=self.post("import",{"asset_id":str(source.pk)})
        second=self.post("import",{"asset_id":str(source.pk)})
        self.assertEqual(first.status_code,201,first.content)
        self.assertEqual(first.json()["asset"]["id"],second.json()["asset"]["id"])
        imported=StudioAsset.objects.get(pk=first.json()["asset"]["id"])
        self.assertEqual(imported.expires_at,source.expires_at)
        self.assertTrue(Path(imported.original_path).is_file())
        self.assertEqual(self.post("import",{"asset_id":str(source.pk)},self.foreign).status_code,404)

    def test_expiry_cleans_original_and_processed_files(self):
        asset = self.upload_wav("Alt",1)
        asset.expires_at = timezone.now()-timedelta(seconds=1); asset.save()
        call_command("delete_expired_audio",stdout=io.StringIO())
        self.assertFalse(Path(asset.file_path).exists())
        self.assertFalse(Path(asset.original_path).exists())
