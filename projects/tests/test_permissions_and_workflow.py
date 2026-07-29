from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.forms import SegmentForm, SpeakerForm
from projects.models import Project, ScriptSegment, Speaker
from tts.models import ProviderVoice


class ProjectWorkflowTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.teacher = users.objects.create_user(
            username="anna",
            password="Test-Passphrase-123!",
            must_change_password=False,
        )
        self.other = users.objects.create_user(
            username="ben",
            password="Test-Passphrase-456!",
            must_change_password=False,
        )
        self.project = Project.objects.create(owner=self.teacher, title="Au café", language="fr", level="A2")
        self.speaker = Speaker.objects.create(project=self.project, name="Élodie", position=1)
        self.segment = ScriptSegment.objects.create(
            project=self.project,
            speaker=self.speaker,
            position=1,
            text="Bonjour, je voudrais un café.",
        )
        self.other_project = Project.objects.create(owner=self.other, title="Fremdes Projekt", language="de")
        self.client.force_login(self.teacher)

    def test_project_list_contains_only_own_projects(self):
        response = self.client.get(reverse("projects:list"))

        self.assertContains(response, "Au café")
        self.assertNotContains(response, "Fremdes Projekt")

    def test_other_users_project_is_not_exposed_or_mutated(self):
        self.assertEqual(
            self.client.get(reverse("projects:editor", args=[self.other_project.pk])).status_code,
            404,
        )
        response = self.client.post(
            reverse("projects:autosave", args=[self.other_project.pk]),
            {
                "project-title": "Übernommen",
                "project-language": "de",
                "project-level": "",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.other_project.refresh_from_db()
        self.assertEqual(self.other_project.title, "Fremdes Projekt")

    def test_create_assigns_authenticated_owner(self):
        response = self.client.post(
            reverse("projects:create"),
            {"title": "En la estación", "language": "es", "level": "A1"},
        )
        created = Project.objects.get(title="En la estación")

        self.assertEqual(created.owner, self.teacher)
        self.assertRedirects(response, reverse("projects:editor", args=[created.pk]), fetch_redirect_response=False)

    def test_duplicate_copies_speakers_and_segments(self):
        response = self.client.post(reverse("projects:duplicate", args=[self.project.pk]))
        copied = Project.objects.exclude(pk=self.project.pk).exclude(pk=self.other_project.pk).get()

        self.assertRedirects(response, reverse("projects:editor", args=[copied.pk]), fetch_redirect_response=False)
        self.assertEqual(copied.owner, self.teacher)
        self.assertEqual(copied.speakers.count(), 1)
        self.assertEqual(copied.segments.get().text, self.segment.text)
        self.assertNotEqual(copied.segments.get().speaker_id, self.speaker.pk)

    def test_segment_form_rejects_speaker_from_another_project(self):
        foreign_speaker = Speaker.objects.create(project=self.other_project, name="Fremd")
        form = SegmentForm(
            {
                "speaker": foreign_speaker.pk,
                "text": "Nicht erlaubt",
                "direction": "",
                "pause_after_ms": 500,
                "speed": 1,
            },
            project=self.project,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("speaker", form.errors)

    def test_speaker_form_only_offers_active_voices_for_project_language(self):
        french_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr",
            display_name="Camille",
            languages=["fr"],
            preview_url="https://example.com/camille.mp3",
            active=True,
        )
        ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-de",
            display_name="Hanna",
            languages=["de"],
            active=True,
        )
        ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr-inactive",
            display_name="Inaktiv",
            languages=["fr"],
            active=False,
        )

        form = SpeakerForm(project=self.project)

        self.assertEqual(list(form.fields["voice"].queryset), [french_voice])
        self.assertEqual(form.fields["voice"].widget.attrs["data-voice-select"], "true")

    def test_speaker_can_be_added_with_compatible_voice(self):
        voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr",
            display_name="Camille",
            languages=["fr"],
            active=True,
        )

        response = self.client.post(
            reverse("projects:speaker_add", args=[self.project.pk]),
            {"name": "Camille", "color": "berry", "voice": voice.pk},
        )

        self.assertRedirects(
            response,
            reverse("projects:editor", args=[self.project.pk]),
            fetch_redirect_response=False,
        )
        speaker = self.project.speakers.get(name="Camille")
        self.assertEqual(speaker.voice_id, "voice-fr")
        self.assertEqual(speaker.provider, "elevenlabs")

    def test_speaker_error_message_includes_validation_detail(self):
        german_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-de",
            display_name="Hanna",
            languages=["de"],
            active=True,
        )

        response = self.client.post(
            reverse("projects:speaker_add", args=[self.project.pk]),
            {"name": "Hanna", "color": "forest", "voice": german_voice.pk},
            follow=True,
        )

        self.assertContains(response, "Der Sprecher konnte nicht hinzugefügt werden.")
        self.assertContains(response, "Freigegebene Stimme:")
        self.assertFalse(self.project.speakers.filter(name="Hanna").exists())

    def test_editor_exposes_preview_data_for_compatible_voices(self):
        voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr",
            display_name="Camille",
            languages=["fr"],
            preview_url="https://example.com/camille.mp3",
            active=True,
        )

        response = self.client.get(reverse("projects:editor", args=[self.project.pk]))

        self.assertEqual(
            response.context["voice_preview_data"][str(voice.pk)],
            {"name": "Camille", "url": "https://example.com/camille.mp3"},
        )
        self.assertContains(response, 'data-voice-preview-panel')

    def test_segment_autosave_updates_only_owned_segment(self):
        prefix = str(self.segment.pk)
        response = self.client.post(
            reverse("projects:segment_autosave", args=[self.project.pk, self.segment.pk]),
            {
                f"{prefix}-speaker": self.speaker.pk,
                f"{prefix}-text": "Bonsoir !",
                f"{prefix}-direction": "friendly",
                f"{prefix}-pause_after_ms": 700,
                f"{prefix}-speed": 0.9,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.segment.refresh_from_db()
        self.assertEqual(self.segment.text, "Bonsoir !")
        self.assertEqual(self.segment.direction, "friendly")

    def test_destructive_routes_reject_get(self):
        self.assertEqual(self.client.get(reverse("projects:delete", args=[self.project.pk])).status_code, 405)
        self.assertEqual(
            self.client.get(reverse("projects:segment_delete", args=[self.project.pk, self.segment.pk])).status_code,
            405,
        )

    def test_used_speaker_cannot_be_deleted_individually(self):
        response = self.client.post(
            reverse("projects:speaker_delete", args=[self.project.pk, self.speaker.pk])
        )

        self.assertRedirects(
            response,
            reverse("projects:editor", args=[self.project.pk]),
            fetch_redirect_response=False,
        )
        self.assertTrue(Speaker.objects.filter(pk=self.speaker.pk).exists())
        self.assertTrue(ScriptSegment.objects.filter(pk=self.segment.pk).exists())

    def test_project_delete_cascades_through_speakers_and_segments(self):
        project_id = self.project.pk
        speaker_id = self.speaker.pk
        segment_id = self.segment.pk

        response = self.client.post(reverse("projects:delete", args=[project_id]))

        self.assertRedirects(response, reverse("projects:list"), fetch_redirect_response=False)
        self.assertFalse(Project.objects.filter(pk=project_id).exists())
        self.assertFalse(Speaker.objects.filter(pk=speaker_id).exists())
        self.assertFalse(ScriptSegment.objects.filter(pk=segment_id).exists())
