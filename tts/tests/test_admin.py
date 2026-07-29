from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tts.models import ProviderVoice


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
