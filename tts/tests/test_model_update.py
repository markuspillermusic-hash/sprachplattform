import importlib
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from projects.models import Project, Speaker
from tts.models import ProviderVoice, TTSConfiguration, VoiceFavorite
from tts.providers import get_tts_provider
from script_assistant.models import AssistantConfiguration
from audio_studio.models import StudioConfiguration


class ModelUpdateTests(TestCase):
    def migrate_data(self, module, function):
        getattr(importlib.import_module(module), function)(apps, SimpleNamespace(connection=connection))

    def test_speech_update_preserves_curation_favorites_and_speaker_assignment(self):
        user = get_user_model().objects.create_user(username='model-update')
        project = Project.objects.create(owner=user, title='Dialog', language='de')
        old = ProviderVoice.objects.create(provider='elevenlabs', model='eleven_v3', voice_id='voice',
                                          display_name='Test', languages=['de'], active=True, labels={'curated_matches': ['de:all']})
        VoiceFavorite.objects.create(user=user, voice=old)
        speaker = Speaker.objects.create(project=project, name='A', provider='elevenlabs', model='eleven_v3', voice_id='voice')
        config = TTSConfiguration.objects.create(model='eleven_v3')
        self.migrate_data('tts.migrations.0004_alter_ttsconfiguration_model', 'upgrade_speech_model')
        old.refresh_from_db();speaker.refresh_from_db();config.refresh_from_db()
        self.assertEqual(old.model, 'eleven_v4')
        self.assertTrue(old.active)
        self.assertEqual(old.labels, {'curated_matches': ['de:all']})
        self.assertEqual(VoiceFavorite.objects.get(user=user).voice_id, old.pk)
        self.assertEqual(speaker.model, 'eleven_v4')
        self.assertEqual(config.model, 'eleven_v4')
        self.migrate_data('tts.migrations.0004_alter_ttsconfiguration_model', 'upgrade_speech_model')
        self.assertEqual(ProviderVoice.objects.count(), 1)

    def test_already_imported_v4_voice_merges_favorites_without_duplicates(self):
        user = get_user_model().objects.create_user(username='merge-update')
        old = ProviderVoice.objects.create(provider='elevenlabs', model='eleven_v3', voice_id='voice', display_name='Old', active=True,
                                          languages=['de'], labels={'curated_matches': ['de:all'], 'curated_ranks': {'de:all': 1}})
        new = ProviderVoice.objects.create(provider='elevenlabs', model='eleven_v4', voice_id='voice', display_name='New')
        VoiceFavorite.objects.create(user=user, voice=old)
        VoiceFavorite.objects.create(user=user, voice=new)
        self.migrate_data('tts.migrations.0004_alter_ttsconfiguration_model', 'upgrade_speech_model')
        new.refresh_from_db()
        self.assertTrue(new.active)
        self.assertEqual(new.labels['curated_matches'], ['de:all'])
        self.assertEqual(new.languages, ['de'])
        self.assertEqual(VoiceFavorite.objects.get(user=user).voice_id, new.pk)
        self.assertEqual(ProviderVoice.objects.count(), 1)

    def test_existing_generation_can_select_original_model_with_current_credentials(self):
        config = TTSConfiguration.objects.create(model='eleven_v4')
        config.set_api_key('private-key');config.save()
        self.assertEqual(get_tts_provider().model_id, 'eleven_v4')
        original = get_tts_provider(model_id='eleven_v3')
        self.assertEqual(original.model_id, 'eleven_v3')
        self.assertEqual(original.api_key, 'private-key')

    def test_assistant_update_preserves_economy_model_and_custom_prices(self):
        economy = AssistantConfiguration.objects.create(model='gpt-6-luna', reasoning_effort='none')
        quality = AssistantConfiguration.objects.create(model='gpt-6-sol', reasoning_effort='none', pricing_currency='EUR',
                                                       input_price_per_million='2.1234', output_price_per_million='10.1234')
        self.migrate_data('script_assistant.migrations.0006_alter_assistantconfiguration_model_and_more', 'upgrade_quality_model')
        economy.refresh_from_db();quality.refresh_from_db()
        self.assertEqual((economy.model, economy.reasoning_effort), ('gpt-6-luna','none'))
        self.assertEqual((quality.model, quality.reasoning_effort), ('gpt-6.1-sol','low'))
        self.assertEqual(quality.pricing_currency, 'EUR')
        self.assertEqual(str(quality.input_price_per_million), '2.1234')

    def test_music_update_preserves_quota_and_credit_estimates(self):
        config = StudioConfiguration.objects.create(music_model='music_v1', music_seconds_per_user_month=2222,
                                                   music_credits_per_minute=1800)
        self.migrate_data('audio_studio.migrations.0006_alter_studioconfiguration_music_model', 'upgrade_music_model')
        config.refresh_from_db()
        self.assertEqual(config.music_model, 'music_v2_5')
        self.assertEqual(config.music_seconds_per_user_month, 2222)
        self.assertEqual(config.music_credits_per_minute, 1800)
