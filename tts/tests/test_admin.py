from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tts.models import ProviderVoice, TTSConfiguration
from tts.providers import get_tts_provider, tts_provider_is_configured


class ProviderVoiceAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="voice-admin",
            password="Test-Passphrase-123!",
            must_change_password=False,
        )
        self.client.force_login(self.admin)
        self.french_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr",
            display_name="Camille",
            languages=["fr"],
            labels={"gender": "female", "use_case": "conversational"},
            preview_url="https://example.com/camille.mp3",
            active=False,
        )
        self.german_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-de",
            display_name="Hanna",
            languages=["de"],
            active=False,
        )
        self.url = reverse("admin:tts_providervoice_changelist")

    def test_selected_voices_can_be_activated_with_admin_action(self):
        response = self.client.post(
            self.url,
            {
                "action": "activate_selected",
                "_selected_action": [str(self.french_voice.pk)],
                "index": "0",
            },
            follow=True,
        )

        self.french_voice.refresh_from_db()
        self.german_voice.refresh_from_db()
        self.assertTrue(self.french_voice.active)
        self.assertFalse(self.german_voice.active)
        self.assertContains(response, "1 ausgewählte Stimme wurde aktiviert.")

    def test_language_filter_and_audio_preview_are_visible(self):
        response = self.client.get(self.url, {"language": "fr"})

        self.assertContains(response, "Camille")
        self.assertNotContains(response, "Hanna")
        self.assertContains(response, "<audio", html=False)
        self.assertContains(response, "https://example.com/camille.mp3")


class TTSConfigurationAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="tts-config-admin",
            password="Test-Passphrase-123!",
            must_change_password=False,
        )
        self.client.force_login(self.admin)

    def test_admin_encrypts_key_and_provider_prefers_database_configuration(self):
        response = self.client.post(
            reverse("admin:tts_ttsconfiguration_add"),
            {
                "name": "ElevenLabs Schule",
                "active": "on",
                "model": "eleven_v3",
                "estimated_eur_per_1000_characters": "0.1800",
                "api_key": "sk_elevenlabs-test-9876",
                "_save": "Speichern",
            },
        )

        self.assertEqual(response.status_code, 302)
        configuration = TTSConfiguration.objects.get()
        self.assertNotIn("sk_elevenlabs-test", configuration.encrypted_api_key)
        self.assertEqual(configuration.api_key_hint, "…9876")
        self.assertTrue(tts_provider_is_configured())
        self.assertEqual(get_tts_provider().api_key, "sk_elevenlabs-test-9876")

        change = self.client.get(
            reverse("admin:tts_ttsconfiguration_change", args=[configuration.pk])
        )
        self.assertContains(change, "…9876")
        self.assertNotContains(change, "sk_elevenlabs-test-9876")
