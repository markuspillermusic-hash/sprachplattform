from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Project
from script_assistant.models import AssistantConversation, AssistantProposal
from script_assistant.providers import AssistantProviderResult
from tts.models import ProviderVoice, VoiceFavorite
from usage_control.models import UsageEvent

from .test_proposals import valid_payload


class FakeProvider:
    def __init__(self, payload=None):
        self.payload = payload or valid_payload()

    def generate_proposal(self, request_data):
        return AssistantProviderResult(
            payload=self.payload,
            model="gpt-5.6-luna",
            response_id="resp_test",
            input_tokens=100,
            output_tokens=200,
        )


class AssistantWorkflowTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user(
            username="teacher",
            password="test",
            must_change_password=False,
        )
        self.other = users.objects.create_user(
            username="other",
            password="test",
            must_change_password=False,
        )
        self.client.force_login(self.user)
        self.favorite_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr-favorite",
            display_name="Zoé",
            languages=["fr"],
            active=True,
        )
        self.other_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="voice-fr-other",
            display_name="Amélie",
            languages=["fr"],
            active=True,
        )
        VoiceFavorite.objects.create(user=self.user, voice=self.favorite_voice)

    def assistant_form_data(self):
        return {
            "mode": "assistant",
            "language": "fr",
            "english_accent": "british",
            "level": "A2",
            "format": "dialogue",
            "topic": "Zwei Freunde verabreden sich für das Kino.",
            "duration_seconds": "60",
            "speaker_count": "2",
            "vocabulary": "film, billet",
            "grammar_focus": "",
            "speaker_roles": "zwei Freunde",
            "voice_preferences": "junge, natürliche Stimmen",
            "additional_instructions": "",
        }

    @patch("script_assistant.workflows.get_script_assistant_provider", return_value=FakeProvider())
    def test_assisted_creation_is_previewed_then_applied_with_favorite_voice_first(self, provider):
        response = self.client.post(reverse("projects:create"), self.assistant_form_data())
        conversation = AssistantConversation.objects.get()
        project = conversation.project

        self.assertRedirects(
            response,
            reverse("script_assistant:conversation", args=[conversation.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(project.segments.count(), 0)
        self.assertEqual(conversation.brief["english_accent"], "unspecified")
        preview = self.client.get(reverse("script_assistant:conversation", args=[conversation.pk]))
        self.assertContains(preview, "Au cinéma")
        self.assertContains(preview, "Entwurf übernehmen und bearbeiten")

        applied = self.client.post(reverse("script_assistant:apply", args=[conversation.pk]))
        project.refresh_from_db()
        conversation.refresh_from_db()
        speakers = list(project.speakers.order_by("position"))
        self.assertRedirects(
            applied,
            reverse("projects:editor", args=[project.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(conversation.status, AssistantConversation.Status.APPLIED)
        self.assertEqual(project.segments.count(), 1)
        self.assertEqual(speakers[0].voice_id, self.favorite_voice.voice_id)
        self.assertEqual(speakers[1].voice_id, self.other_voice.voice_id)
        usage = UsageEvent.objects.get(provider=UsageEvent.Provider.OPENAI)
        self.assertEqual(usage.status, UsageEvent.Status.COMMITTED)
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 200)

    @patch("script_assistant.workflows.get_script_assistant_provider", return_value=FakeProvider())
    def test_english_accent_is_kept_in_assistant_brief(self, provider):
        form_data = self.assistant_form_data()
        form_data["language"] = "en"
        form_data["english_accent"] = "american"

        self.client.post(reverse("projects:create"), form_data)

        self.assertEqual(AssistantConversation.objects.get().brief["english_accent"], "american")

    @patch("script_assistant.workflows.get_script_assistant_provider", return_value=FakeProvider())
    def test_foreign_user_cannot_open_conversation(self, provider):
        self.client.post(reverse("projects:create"), self.assistant_form_data())
        conversation = AssistantConversation.objects.get()
        self.client.force_login(self.other)

        response = self.client.get(reverse("script_assistant:conversation", args=[conversation.pk]))
        self.assertEqual(response.status_code, 404)

    @patch("script_assistant.workflows.get_script_assistant_provider")
    def test_refinement_keeps_history_and_replaces_only_pending_proposal(self, provider):
        provider.return_value = FakeProvider()
        self.client.post(reverse("projects:create"), self.assistant_form_data())
        conversation = AssistantConversation.objects.get()
        first = conversation.proposals.get(status=AssistantProposal.Status.PENDING)
        changed = valid_payload()
        changed["title"] = "Au cinéma – einfacher"
        provider.return_value = FakeProvider(changed)

        response = self.client.post(
            reverse("script_assistant:refine", args=[conversation.pk]),
            {"instruction": "Bitte einfacher."},
        )

        self.assertRedirects(
            response,
            reverse("script_assistant:conversation", args=[conversation.pk]),
            fetch_redirect_response=False,
        )
        first.refresh_from_db()
        conversation.refresh_from_db()
        self.assertEqual(first.status, AssistantProposal.Status.DISCARDED)
        self.assertEqual(
            conversation.proposals.get(status=AssistantProposal.Status.PENDING).payload["title"],
            "Au cinéma – einfacher",
        )
        self.assertEqual(conversation.messages.count(), 4)
        self.assertEqual(conversation.input_tokens, 200)
        self.assertEqual(conversation.output_tokens, 400)

    @patch("script_assistant.workflows.get_script_assistant_provider", return_value=FakeProvider())
    def test_discarding_new_draft_removes_empty_placeholder_project(self, provider):
        self.client.post(reverse("projects:create"), self.assistant_form_data())
        conversation = AssistantConversation.objects.get()
        project_id = conversation.project_id

        response = self.client.post(reverse("script_assistant:discard", args=[conversation.pk]))

        self.assertRedirects(response, reverse("projects:list"), fetch_redirect_response=False)
        self.assertFalse(Project.objects.filter(pk=project_id).exists())
