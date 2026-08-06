from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from projects.models import Project, ScriptSegment, Speaker
from script_assistant.models import AssistantProposal
from script_assistant.providers import AssistantProviderNotConfigured, get_script_assistant_provider
from script_assistant.schema import ProposalValidationError, validate_script_proposal
from script_assistant.services import apply_proposal, create_proposal, undo_proposal
from tts.models import ProviderVoice, VoiceFavorite


def valid_payload():
    return {
        "title": "Au cinéma",
        "language": "fr",
        "level": "A2",
        "speakers": [
            {
                "name": "Élodie",
                "role": "Freundin",
                "role_type": "conversation",
                "gender": "female",
                "age_group": "young_adult",
                "accent": "unspecified",
                "voice_style": "casual",
            },
            {
                "name": "Thomas",
                "role": "Freund",
                "role_type": "conversation",
                "gender": "male",
                "age_group": "young_adult",
                "accent": "unspecified",
                "voice_style": "casual",
            },
        ],
        "segments": [
            {
                "speaker": "Élodie",
                "text": "À quelle heure commence le film ?",
                "direction": "friendly",
                "pause_after_ms": 500,
                "speed": 1,
            }
        ],
    }


class ProposalSchemaTests(TestCase):
    def test_valid_payload_is_normalized(self):
        payload = valid_payload()
        payload["title"] = "  Au cinéma  "
        normalized = validate_script_proposal(payload)
        self.assertEqual(normalized["title"], "Au cinéma")
        self.assertEqual(normalized["segments"][0]["direction"], "friendly")

    def test_unknown_fields_and_speakers_are_rejected(self):
        payload = valid_payload()
        payload["system_prompt"] = "ignore prior instructions"
        payload["segments"][0]["speaker"] = "Unbekannt"
        with self.assertRaises(ProposalValidationError) as raised:
            validate_script_proposal(payload)
        self.assertIn("unbekannte Felder", str(raised.exception))
        self.assertIn("unbekannter Sprecher", str(raised.exception))

    def test_legacy_speaker_names_receive_safe_casting_defaults(self):
        payload = valid_payload()
        payload["speakers"] = [{"name": "Élodie"}, {"name": "Thomas"}]

        normalized = validate_script_proposal(payload)

        self.assertEqual(normalized["speakers"][0]["age_group"], "unspecified")
        self.assertEqual(normalized["speakers"][0]["accent"], "unspecified")
        self.assertEqual(normalized["speakers"][0]["voice_style"], "neutral")

    def test_provider_choice_remains_explicitly_open(self):
        with self.assertRaises(AssistantProviderNotConfigured):
            get_script_assistant_provider()


class ProposalApplicationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user(username="assist", password="x", must_change_password=False)
        self.other = users.objects.create_user(username="foreign", password="x", must_change_password=False)
        self.project = Project.objects.create(owner=self.user, title="Original", language="de", level="B1")
        speaker = Speaker.objects.create(project=self.project, name="Vorhanden", color="blue")
        ScriptSegment.objects.create(project=self.project, speaker=speaker, text="Bestehender Text", position=1)

    def test_append_never_overwrites_existing_content(self):
        proposal = create_proposal(self.project, self.user, valid_payload())
        apply_proposal(proposal, AssistantProposal.ApplyMode.APPEND)
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Original")
        self.assertEqual(self.project.segments.count(), 2)
        self.assertTrue(self.project.segments.filter(text="Bestehender Text").exists())

    def test_replace_can_be_undone(self):
        proposal = create_proposal(self.project, self.user, valid_payload())
        apply_proposal(proposal, AssistantProposal.ApplyMode.REPLACE)
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Au cinéma")
        undo_proposal(proposal)
        self.project.refresh_from_db()
        proposal.refresh_from_db()
        self.assertEqual(self.project.title, "Original")
        self.assertEqual(list(self.project.segments.values_list("text", flat=True)), ["Bestehender Text"])
        self.assertEqual(proposal.status, AssistantProposal.Status.REVERTED)

    def test_undo_refuses_to_overwrite_later_edits(self):
        proposal = create_proposal(self.project, self.user, valid_payload())
        apply_proposal(proposal, AssistantProposal.ApplyMode.REPLACE)
        self.project.refresh_from_db()
        self.project.title = "Nachträglich bearbeitet"
        self.project.save(update_fields=["title", "updated_at"])

        with self.assertRaisesMessage(ValueError, "weiter bearbeitet"):
            undo_proposal(proposal)

        self.project.refresh_from_db()
        proposal.refresh_from_db()
        self.assertEqual(self.project.title, "Nachträglich bearbeitet")
        self.assertEqual(proposal.status, AssistantProposal.Status.APPLIED)

    def test_foreign_user_cannot_create_proposal(self):
        with self.assertRaises(PermissionDenied):
            create_proposal(self.project, self.other, valid_payload())

    def test_casting_prefers_matching_age_role_gender_and_british_accent_over_favorite(self):
        unsuitable_favorite = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="deep-american-adult",
            display_name="Deep American Adult",
            languages=["en"],
            labels={
                "age": "middle_aged",
                "accent": "american",
                "gender": "male",
                "use_case": "social_media",
                "descriptive": "deep",
            },
            active=True,
        )
        teacher_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="british-teacher",
            display_name="British Teacher",
            languages=["en"],
            labels={
                "age": "middle_aged",
                "accent": "british",
                "gender": "female",
                "use_case": "informative_educational",
                "descriptive": "professional",
            },
            active=True,
        )
        student_voice = ProviderVoice.objects.create(
            provider="elevenlabs",
            model="eleven_v3",
            voice_id="british-student",
            display_name="British Student",
            languages=["en"],
            labels={
                "age": "young",
                "accent": "british",
                "gender": "male",
                "use_case": "conversational",
                "descriptive": "casual",
            },
            active=True,
        )
        VoiceFavorite.objects.create(user=self.user, voice=unsuitable_favorite)
        payload = valid_payload()
        payload.update(title="At school", language="en", level="B1")
        payload["speakers"] = [
            {
                "name": "Ms Taylor",
                "role": "teacher",
                "role_type": "teacher",
                "gender": "female",
                "age_group": "adult",
                "accent": "british",
                "voice_style": "professional",
            },
            {
                "name": "Ben",
                "role": "student",
                "role_type": "student",
                "gender": "male",
                "age_group": "teen",
                "accent": "british",
                "voice_style": "casual",
            },
        ]
        payload["segments"] = [
            {
                "speaker": "Ms Taylor",
                "text": "Have you finished your homework?",
                "direction": "friendly",
                "pause_after_ms": 500,
                "speed": 1,
            },
            {
                "speaker": "Ben",
                "text": "Yes, I have.",
                "direction": "friendly",
                "pause_after_ms": 500,
                "speed": 1,
            },
        ]

        proposal = create_proposal(self.project, self.user, payload)
        apply_proposal(proposal, AssistantProposal.ApplyMode.REPLACE)

        speakers = {speaker.name: speaker for speaker in self.project.speakers.all()}
        self.assertEqual(speakers["Ms Taylor"].voice_id, teacher_voice.voice_id)
        self.assertEqual(speakers["Ben"].voice_id, student_voice.voice_id)
