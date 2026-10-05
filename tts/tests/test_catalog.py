from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Project
from projects.forms import SpeakerForm, ProjectCreateForm
from tts.models import ProviderVoice, VoiceFavorite


class VoiceCatalogTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user(
            username="listener",
            password="start",
            must_change_password=False,
        )
        self.other = users.objects.create_user(
            username="other-listener",
            password="start",
            must_change_password=False,
        )
        self.french_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr",
            display_name="Camille",
            languages=["fr"],
            labels={
                "gender": "female",
                "use_case": "conversational",
                "accent": "parisian",
                "age": "young",
            },
            preview_url="https://example.com/camille.mp3",
            active=True,
        )
        self.german_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-de",
            display_name="Anton",
            languages=["de"],
            labels={"gender": "male", "use_case": "narration"},
            active=True,
        )
        self.inactive_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-hidden",
            display_name="Versteckt",
            languages=["fr"],
            active=False,
        )
        self.url = reverse("tts:catalog")
        self.client.force_login(self.user)

    def test_catalog_requires_login_and_only_shows_active_voices(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Camille")
        self.assertContains(response, "Anton")
        self.assertNotContains(response, "Versteckt")
        self.assertContains(response, "https://example.com/camille.mp3")
        self.assertContains(response, "Hören Sie alle freigegebenen Stimmen")

    def test_catalog_filters_by_language_category_and_search_terms(self):
        response = self.client.get(
            self.url,
            {
                "language": "fr",
                "gender": "female",
                "accent": "parisian",
                "age": "young",
                "use_case": "conversational",
                "q": "parisian",
            },
        )

        self.assertEqual([card["voice"] for card in response.context["cards"]], [self.french_voice])
        self.assertContains(response, "Französisch")
        self.assertContains(response, "Pariser Französisch")
        self.assertNotContains(response, "Anton")

    def test_favorites_are_personal_and_sorted_first(self):
        VoiceFavorite.objects.create(user=self.user, voice=self.french_voice)
        VoiceFavorite.objects.create(user=self.other, voice=self.german_voice)

        response = self.client.get(self.url)

        cards = response.context["cards"]
        self.assertEqual(cards[0]["voice"], self.french_voice)
        self.assertTrue(cards[0]["is_favorite"])
        self.assertFalse(cards[1]["is_favorite"])
        self.assertEqual(response.context["favorite_count"], 1)

    def test_favorites_only_filter(self):
        VoiceFavorite.objects.create(user=self.user, voice=self.french_voice)

        response = self.client.get(self.url, {"favorites": "1"})

        self.assertEqual([card["voice"] for card in response.context["cards"]], [self.french_voice])
        self.assertNotContains(response, "Anton")

    def test_favorite_toggle_adds_and_removes_favorite(self):
        toggle_url = reverse("tts:favorite_toggle", args=[self.french_voice.pk])

        response = self.client.post(toggle_url, {"next": f"{self.url}?language=fr"})
        self.assertRedirects(
            response,
            f"{self.url}?language=fr",
            fetch_redirect_response=False,
        )
        self.assertTrue(
            VoiceFavorite.objects.filter(
                user=self.user,
                voice=self.french_voice,
            ).exists()
        )

        response = self.client.post(
            toggle_url,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertJSONEqual(
            response.content,
            {
                "is_favorite": False,
                "voice_id": self.french_voice.pk,
            },
        )
        self.assertFalse(
            VoiceFavorite.objects.filter(
                user=self.user,
                voice=self.french_voice,
            ).exists()
        )

    def test_catalog_marks_favorite_forms_for_in_place_updates(self):
        response = self.client.get(self.url)

        self.assertContains(response, "data-favorite-form")
        self.assertContains(response, "data-favorite-count")
        self.assertContains(response, "Favoriten erscheinen nach dem nächsten Laden zuerst")

    def test_inactive_voice_cannot_be_favorited(self):
        response = self.client.post(
            reverse("tts:favorite_toggle", args=[self.inactive_voice.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_favorite_is_first_in_project_voice_choice(self):
        project = Project.objects.create(
            owner=self.user,
            title="Französisch",
            language="fr",
        )
        second_french_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr-a",
            display_name="Amélie",
            languages=["fr"],
            active=True,
        )
        VoiceFavorite.objects.create(user=self.user, voice=self.french_voice)

        form = SpeakerForm(project=project, user=self.user)
        choices = list(form.fields["voice"].choices)

        self.assertEqual(choices[1][0].value, self.french_voice.pk)
        self.assertEqual(choices[1][1], "★ Camille")
        self.assertEqual(choices[2][0].value, second_french_voice.pk)

    def test_large_catalog_paginates_and_retains_filters(self):
        ProviderVoice.objects.bulk_create([
            ProviderVoice(provider="elevenlabs", model="eleven_v4", voice_id=f"large-{i}",
                          display_name=f"Studio {i:03d}", languages=["de"], active=True)
            for i in range(60)
        ])
        first = self.client.get(self.url, {"q": "Studio", "language": "de"})
        second = self.client.get(self.url, {"q": "Studio", "language": "de", "page": 2})
        self.assertEqual(first.context["result_count"], 60)
        self.assertEqual(len(first.context["cards"]), 24)
        self.assertEqual(first.context["page_obj"].paginator.num_pages, 3)
        self.assertFalse({c["voice"].pk for c in first.context["cards"]} & {c["voice"].pk for c in second.context["cards"]})
        self.assertContains(first, "q=Studio&amp;language=de&amp;page=2")
        self.assertContains(second, "Vorherige Seite")
        self.assertEqual(self.client.get(self.url, {"q": "missing", "page": 900}).status_code, 200)

    def test_english_elevenlabs_voice_is_selectable_for_german(self):
        voice = ProviderVoice.objects.create(provider="elevenlabs", model="eleven_v4", voice_id="english-only",
            display_name="English narrator", languages=["en"], active=True, labels={"age": "young", "gender": "male"})
        project = Project.objects.create(owner=self.user, title="Deutsch", language="de")
        form = SpeakerForm({"name": "Erzähler", "color": "forest", "voice": voice.pk}, project=project, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["voice"], voice)
        self.assertIn('data-voice-picker="true"', str(form["voice"]))
        self.assertIn('data-age="young"', str(form["voice"]))
        self.assertIn('data-project-language="de"', str(form["voice"]))
        voice.active = False; voice.save()
        self.assertFalse(SpeakerForm({"name": "Erzähler", "color": "forest", "voice": voice.pk}, project=project, user=self.user).is_valid())

    def test_additional_project_language_is_available(self):
        form = ProjectCreateForm({"title": "Portugiesischer Dialog", "language": "pt", "level": "A2"})
        self.assertTrue(form.is_valid(), form.errors)
