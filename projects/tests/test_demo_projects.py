from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from projects.models import Project
from projects.services import DEMO_PROJECTS, ensure_demo_projects
from tts.models import ProviderVoice


class DemoProjectTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="demo-teacher",
            password="Test-Passphrase-123!",
            must_change_password=False,
        )
        for index, name in enumerate(("Demo Voice A", "Demo Voice B"), start=1):
            ProviderVoice.objects.create(
                provider="elevenlabs",
                model="eleven_v3",
                voice_id=f"demo-voice-{index}",
                display_name=name,
                languages=["de", "en", "fr", "es", "it"],
                preview_url=f"https://example.com/demo-{index}.mp3",
                active=True,
            )

    def test_creates_five_titled_demos_with_dialogue_and_voices(self):
        created = ensure_demo_projects(self.user)

        self.user.refresh_from_db()
        self.assertTrue(self.user.demo_projects_initialized)
        self.assertEqual(len(created), len(DEMO_PROJECTS))
        self.assertEqual(self.user.projects.filter(demo_key__gt="").count(), 5)
        for project in self.user.projects.filter(demo_key__gt=""):
            self.assertTrue(project.title.startswith("Demo ·"))
            self.assertEqual(project.level, "A2")
            self.assertEqual(project.speakers.count(), 2)
            self.assertEqual(project.segments.count(), 4)
            self.assertEqual(
                project.speakers.exclude(voice_id="").values("voice_id").distinct().count(),
                2,
            )
            self.assertEqual(
                list(project.segments.values_list("pause_after_ms", flat=True)),
                [400, 500, 350, 800],
            )

    def test_initialization_is_idempotent_and_preserves_user_edits(self):
        ensure_demo_projects(self.user)
        project = self.user.projects.get(demo_key="station-de")
        project.title = "Mein angepasster Bahnhofsdialog"
        project.save(update_fields=["title"])

        created_again = ensure_demo_projects(self.user)

        self.assertEqual(created_again, [])
        self.assertEqual(self.user.projects.filter(demo_key__gt="").count(), 5)
        project.refresh_from_db()
        self.assertEqual(project.title, "Mein angepasster Bahnhofsdialog")

    def test_deleted_demo_stays_deleted_unless_force_is_requested(self):
        ensure_demo_projects(self.user)
        self.user.projects.get(demo_key="station-it").delete()

        self.assertEqual(ensure_demo_projects(self.user), [])
        self.assertFalse(self.user.projects.filter(demo_key="station-it").exists())

        recreated = ensure_demo_projects(self.user, force=True)

        self.assertEqual([project.demo_key for project in recreated], ["station-it"])

    def test_project_list_initializes_demos_for_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("projects:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.projects.filter(demo_key__gt="").count(), 5)
        self.assertContains(response, "Demo · Deutsch · Am Bahnhof")
        self.assertContains(response, "demo-badge", html=False)

    def test_management_command_initializes_named_user(self):
        output = StringIO()

        call_command(
            "seed_demo_projects",
            username=self.user.username,
            stdout=output,
        )

        self.assertEqual(self.user.projects.filter(demo_key__gt="").count(), 5)
        self.assertIn("5 Demos für 1 Benutzerkonten angelegt.", output.getvalue())
