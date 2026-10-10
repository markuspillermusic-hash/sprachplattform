import json
import shutil
import uuid
from copy import deepcopy
from decimal import Decimal
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from audio_studio.library import (create_preparation, extend_asset, materialize,
                                  prepare_source, record_request)
from audio_studio.media import StudioError, probe
from audio_studio.models import SoundLibraryAsset, SoundLibraryRequest, StudioSession
from audio_studio.providers import GeneratedAudio
from audio_studio.services import create_export, create_generation, run_job, save_state
from audio_studio.tests.test_studio import StudioFixture, wav_bytes
from production.models import Production
from production.planning import ProductionError, material_key, validate_plan
from production.services import estimate_mix
from projects.lifecycle import delete_project, duplicate_project
from usage_control.models import UsageEvent


@skipUnless(shutil.which('ffmpeg'), 'FFmpeg is required')
class SoundLibraryTests(StudioFixture):
    def test_listening_review_has_full_audio_and_explicit_idempotent_approval(self):
        entry = self.source(publish=False)
        url = reverse('admin:audio_studio_soundlibraryasset_listening_review')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.user.is_staff = True; self.user.is_superuser = True; self.user.save()
        page = self.client.get(url)
        self.assertContains(page, entry.title)
        self.assertContains(page, '?full=1')
        self.assertContains(page, 'csrfmiddlewaretoken')
        self.client.post(url, {'source_id': str(entry.pk)})
        entry.refresh_from_db(); self.assertEqual(entry.status, 'draft')
        self.client.post(url, {'source_id': str(entry.pk), 'heard': 'on'})
        entry.refresh_from_db(); self.assertEqual(entry.status, 'published'); self.assertTrue(entry.loop_verified)
        self.client.post(url, {'source_id': str(entry.pk), 'heard': 'on'})
        from django.contrib.admin.models import LogEntry
        self.assertEqual(LogEntry.objects.count(), 1)
        self.assertFalse(UsageEvent.objects.exists())
        self.assertEqual(self.client.post(url, {'source_id': 'invalid', 'heard': 'on'}).status_code, 302)

    def test_listening_review_requires_change_permission_and_valid_provenance(self):
        entry = self.source(role='oneshot', publish=False)
        url = reverse('admin:audio_studio_soundlibraryasset_listening_review')
        self.user.is_staff = True; self.user.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'source_id': str(entry.pk), 'heard': 'on'}).status_code, 403)
        self.user.is_superuser = True; self.user.save()
        entry.provenance = ''; entry.save()
        self.client.post(url, {'source_id': str(entry.pk), 'heard': 'on'})
        entry.refresh_from_db(); self.assertEqual(entry.status, 'draft')
        entry.provenance = 'Nur Test'; entry.save()
        self.client.post(url, {'source_id': str(entry.pk), 'heard': 'on'})
        entry.refresh_from_db(); self.assertEqual(entry.status, 'published'); self.assertFalse(entry.loop_verified)

    def source(self, role='atmosphere', publish=True):
        source = Path(self.folder.name) / 'test-source.wav'
        source.write_bytes(wav_bytes(.8))
        entry = SoundLibraryAsset.objects.create(key=uuid.uuid4().hex, title='QA Wald',
            description='Technische Testdatei, keine echte Atmosphäre', category='nature',
            role=role, tags='Forst Bäume', provenance='Nur Testfixture',
            fade_in=.02, fade_out=.1)
        prepare_source(entry, source)
        if publish:
            entry.loop_verified = role == 'atmosphere'
            entry.status = 'published'
            entry.full_clean(); entry.save()
        return entry

    def request(self, source, duration=120):
        return {'request_id': str(uuid.uuid4()), 'library_id': str(source.pk),
                'duration': duration, 'placement': {'track': 'effects', 'start': 3}}

    def plan(self, item):
        return {'summary': 'Test', 'speech_start': 0, 'music_duck_db': 4,
                'compression': 25, 'items': [item]}

    def item(self, **changes):
        return {'title': 'Wald', 'kind': 'effects', 'asset_id': '', 'prompt': 'Forest ambience',
                'duration': 30, 'start': 0, 'gain_db': -20, 'fade_in': 1,
                'fade_out': 2, 'loop': True, **changes}

    def test_drafts_are_hidden_and_require_acoustic_review_and_provenance(self):
        entry = self.source(publish=False)
        self.assertEqual(self.client.get(self.url('library_catalog')).json()['sounds'], [])
        preview = reverse('audio_studio:library_preview', args=[entry.pk])
        self.assertEqual(self.client.get(preview).status_code, 404)
        entry.status = 'published'
        with self.assertRaises(ValidationError): entry.full_clean()
        entry.loop_verified = True; entry.provenance = ''
        with self.assertRaises(ValidationError): entry.full_clean()
        entry.provenance = 'Nur Test'; entry.full_clean(); entry.save()
        entry.duration = 80
        with self.assertRaises(ValidationError): entry.full_clean()

    def test_preparation_is_idempotent_free_and_project_scoped(self):
        entry = self.source(); data = self.request(entry)
        self.config.effects_enabled = False
        self.config.effects_seconds_per_user_month = 0
        self.config.save()
        first = create_preparation(self.project, self.user, data)
        self.assertEqual(create_preparation(self.project, self.user, data).pk, first.pk)
        with patch('audio_studio.services.ElevenLabsAudioProvider') as provider:
            run_job(first.pk); run_job(first.pk)
            provider.assert_not_called()
        first.refresh_from_db()
        self.assertEqual(first.status, 'succeeded', first.error_message)
        self.assertIsNone(first.usage_event_id)
        self.assertEqual(first.asset.duration, 120)
        self.assertFalse(UsageEvent.objects.exists())
        self.assertEqual(materialize(self.project, entry, 60).pk, first.asset_id)
        self.assertNotEqual(materialize(self.foreign, entry, 60).pk, first.asset_id)
        altered = deepcopy(data); altered['duration'] = 60
        with self.assertRaises(StudioError): create_preparation(self.project, self.user, altered)
        self.assertEqual(self.client.get(self.url('library_catalog', self.foreign)).status_code, 404)
        self.assertEqual(self.post('library_prepare', data, self.foreign).status_code, 404)

    def test_student_cannot_select_request_or_preview_shared_sounds(self):
        entry = self.source()
        self.user.role = self.user.Role.STUDENT; self.user.save()
        from accounts.models import TemporaryStudentAccess
        TemporaryStudentAccess.objects.create(teacher=self.other, student=self.user, label='Test', expires_at=timezone.now() + timedelta(days=1))
        with self.assertRaises(PermissionDenied): create_preparation(self.project, self.user, self.request(entry))
        self.assertEqual(self.client.get(self.url('library_catalog')).status_code, 403)
        self.assertEqual(self.post('library_request', {'label': 'Regen'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('audio_studio:library_preview', args=[entry.pk])).status_code, 403)

    def test_oneshot_and_foreign_private_assets_cannot_be_extended(self):
        entry = self.source(role='oneshot')
        with self.assertRaises(StudioError): create_preparation(self.project, self.user, self.request(entry, 120))
        data = self.request(entry); data.pop('library_id'); data['asset_id'] = str(self.asset.pk)
        with self.assertRaises(StudioError): create_preparation(self.foreign, self.other, data)
        with self.assertRaises(StudioError): extend_asset(self.project, self.asset, 120)

    def test_extension_survives_retirement_and_is_a_finite_exportable_clip(self):
        entry = self.source(); asset = materialize(self.project, entry, 5)
        entry.status = 'retired'; entry.save()
        with self.assertRaises(StudioError): materialize(self.project, entry, 160)
        extended = extend_asset(self.project, asset, 121.37)
        self.assertEqual(extend_asset(self.project, asset, 121.37).pk, extended.pk)
        self.assertAlmostEqual(probe(extended.file_path), 121.37, delta=.08)
        state = self.state(); state['clips'][0].update(asset_id=str(extended.pk), track='effects', start=0,
            trim_start=0, trim_end=121.37, fade_in=1, fade_out=2)
        session = save_state(self.project, self.user, 0, state)
        job = create_export(self.project, self.user, session.revision, 'wav'); run_job(job.pk); job.refresh_from_db()
        self.assertEqual(job.status, 'succeeded', job.error_message)
        self.assertAlmostEqual(probe(job.asset.file_path), 121.37, delta=.002)
        self.assertFalse(UsageEvent.objects.exists())

    def test_maximum_duration_and_mp3_import_respect_encoder_padding(self):
        entry = self.source()
        other = SoundLibraryAsset.objects.create(key='encoded', title='MP3', description='Test', category='actions', role='oneshot')
        prepare_source(other, entry.preview_path)
        self.assertAlmostEqual(other.duration, .8, delta=.002)
        asset = materialize(self.project, entry, 1800)
        self.assertEqual(asset.duration, 1800)
        self.assertAlmostEqual(probe(asset.file_path), 1800, delta=.08)

    def test_master_has_consistent_peak_and_published_versions_cannot_be_reopened(self):
        import struct
        from audio_studio.media import input_options, run
        entry = self.source()
        samples = run(['ffmpeg', '-v', 'error', *input_options(entry.master_path), '-f', 'f32le', 'pipe:1'])
        peak = max(abs(v[0]) for v in struct.iter_unpack('<f', samples))
        self.assertAlmostEqual(peak, .6, delta=.002)
        entry.status = 'draft'
        with self.assertRaises(ValidationError): entry.full_clean()
        request = self.request(entry, 80)
        request.update(asset_id='', replace_clip_id=str(uuid.uuid4()), trim_start=30)
        request['placement']['start'] = 1740
        # 80 seconds of prepared source contain 30 trimmed seconds: visible 50 seconds.
        entry.status = 'published'
        job = create_preparation(self.project, self.user, request)
        self.assertEqual(job.input_data['trim_start'], 30)

    def test_usage_counts_saved_projects_and_missing_requests_are_deduplicated(self):
        entry = self.source(); asset = materialize(self.project, entry, 60)
        self.assertFalse(SoundLibraryRequest.objects.exists())
        state = self.state(); state['clips'][0].update(asset_id=str(asset.pk), track='effects')
        session = save_state(self.project, self.user, 0, state)
        save_state(self.project, self.user, session.revision, state)
        self.assertEqual(SoundLibraryRequest.objects.filter(kind='used').count(), 1)
        a = record_request(self.project, self.user, 'missing', '  Starker   Regen ')
        b = record_request(self.project, self.user, 'missing', 'starker regen')
        self.assertEqual(a.pk, b.pk)
        self.assertNotEqual(a.pk, record_request(self.foreign, self.other, 'missing', 'starker regen').pk)

    def test_submission_is_private_and_does_not_publish(self):
        entry = self.source(); asset = materialize(self.project, entry, 60)
        count = SoundLibraryAsset.objects.count()
        self.assertEqual(self.post('library_request', {'asset_id': str(asset.pk)}).status_code, 200)
        self.assertEqual(SoundLibraryRequest.objects.get().kind, 'suggestion')
        self.assertEqual(SoundLibraryAsset.objects.count(), count)
        self.assertEqual(self.post('library_request', {'asset_id': str(asset.pk)}, self.foreign).status_code, 404)

    def test_project_copy_keeps_original_and_global_library_survives_deletion(self):
        entry = self.source(); asset = materialize(self.project, entry, 60)
        state = self.state(); state['clips'][0].update(asset_id=str(asset.pk), track='effects')
        save_state(self.project, self.user, 0, state)
        # The unused mock speech asset has no physical fixture and is removed first.
        self.asset.delete()
        copy = duplicate_project(self.project, self.user)
        copied = copy.studio_assets.get()
        self.assertEqual(copied.library_source, entry)
        self.assertTrue(copied.loopable)
        self.assertNotEqual(copied.file_path, asset.file_path)
        delete_project(self.project)
        self.assertTrue(Path(copied.file_path).is_file())
        self.assertTrue(Path(entry.master_path).is_file())
        self.assertTrue(SoundLibraryAsset.objects.filter(pk=entry.pk).exists())

    def test_plan_uses_catalog_and_costs_source_only_with_duplicate_reuse(self):
        entry = self.source()
        library = self.item(prompt='', library_id=str(entry.pk), generation_duration=0, duration=180)
        new = self.item(duration=120, generation_duration=30, library_id='')
        plan = self.plan(library); plan['items'] += [new, dict(new, start=130)]
        plan = validate_plan(self.project, plan, 20)
        production = Production.objects.create(project=self.project, plan=plan)
        estimated = estimate_mix(production)
        self.assertEqual(estimated['credits'], 1200)
        self.assertEqual(estimated['source_seconds'], 30)
        self.assertEqual(estimated['eur'], .1)
        self.assertEqual(estimated['new'], 1)
        self.assertEqual(estimated['library'], 1)
        legacy = self.item()
        normalized = validate_plan(self.project, self.plan(dict(legacy, library_id='', generation_duration=0)), 20)['items'][0]
        self.assertEqual(material_key(normalized), material_key(legacy))
        for value in (False, True, float('nan'), 31):
            with self.subTest(value=value), self.assertRaises(ProductionError):
                validate_plan(self.project, self.plan(self.item(generation_duration=value)), 20)

    def test_generation_reserves_source_seconds_and_local_loop_has_no_second_charge(self):
        job = create_generation(self.project, self.user, {'kind': 'effects', 'duration': .8, 'loop': True,
            'playback_duration': 4, 'prompt': 'A repeating test sound'})
        self.assertEqual(job.usage_event.estimated_credits, Decimal(32))
        provider = Mock()
        from production.tests import mp3_bytes
        provider.generate.return_value = GeneratedAudio(mp3_bytes(.8), 'test', Decimal(32))
        run_job(job.pk, provider); job.refresh_from_db()
        self.assertEqual(job.status, 'succeeded', job.error_message)
        self.assertEqual(job.asset.duration, 4)
        self.assertTrue(job.asset.loopable)
        self.assertEqual(UsageEvent.objects.count(), 1)
        provider.generate.assert_called_once()
