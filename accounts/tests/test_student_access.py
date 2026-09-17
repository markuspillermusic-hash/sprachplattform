from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import TemporaryStudentAccess
from accounts.services import create_temporary_student_accesses
from projects.models import Project
from usage_control.models import UsageEvent
from usage_control.services import QuotaExceeded, reserve_usage


class TemporaryStudentAccessTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.teacher = users.objects.create_user(
            username="lehrkraft",
            password="test",
            role=users.Role.TEACHER,
            must_change_password=False,
        )
        self.other_teacher = users.objects.create_user(
            username="andere-lehrkraft",
            password="test",
            role=users.Role.TEACHER,
            must_change_password=False,
        )
        self.client.force_login(self.teacher)

    def create_access(self, **overrides):
        values = {
            "teacher": self.teacher,
            "label": "Französisch 8a",
            "count": 1,
            "duration_hours": 24,
            "character_limit": 5_000,
            "allow_ai": False,
        }
        values.update(overrides)
        return create_temporary_student_accesses(**values)[0]

    def test_teacher_creates_anonymous_batch_with_one_time_credentials(self):
        response = self.client.post(
            reverse("accounts:student_access_create"),
            {
                "label": "Englisch 7b",
                "count": 2,
                "duration_hours": 8,
                "character_limit": 3_000,
                "allow_ai": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nur jetzt sichtbar")
        accesses = list(TemporaryStudentAccess.objects.select_related("student").order_by("label"))
        self.assertEqual(len(accesses), 2)
        self.assertEqual(accesses[0].label, "Englisch 7b · Platz 01")
        for access in accesses:
            self.assertEqual(access.teacher, self.teacher)
            self.assertEqual(access.student.role, get_user_model().Role.STUDENT)
            self.assertFalse(access.student.must_change_password)
            self.assertEqual(access.student.character_limit, 3_000)
            self.assertEqual(access.student.openai_daily_request_limit, 5)
            self.assertContains(response, access.student.username)

    def test_active_student_can_log_in_without_password_change(self):
        credential = self.create_access()
        self.client.logout()

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": credential["username"],
                "password": credential["password"],
            },
        )

        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("projects:list")).status_code, 200)

    def test_expired_student_cannot_log_in(self):
        credential = self.create_access(duration_hours=2)
        TemporaryStudentAccess.objects.filter(pk=credential["access"].pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.client.logout()

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": credential["username"],
                "password": credential["password"],
            },
        )

        self.assertContains(response, "nicht mehr gültig")

    def test_expired_student_session_is_ended(self):
        credential = self.create_access()
        TemporaryStudentAccess.objects.filter(pk=credential["access"].pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.client.force_login(credential["access"].student)

        response = self.client.get(reverse("projects:list"))

        self.assertRedirects(response, reverse("accounts:login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_teacher_can_revoke_own_but_not_foreign_access(self):
        own = self.create_access()["access"]
        foreign = self.create_access(teacher=self.other_teacher, label="Fremd")["access"]

        response = self.client.post(reverse("accounts:student_access_revoke", args=[own.pk]))
        self.assertRedirects(response, reverse("accounts:student_access_list"))
        own.refresh_from_db()
        own.student.refresh_from_db()
        self.assertIsNotNone(own.revoked_at)
        self.assertFalse(own.student.is_active)

        response = self.client.post(reverse("accounts:student_access_revoke", args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_open_teacher_access_management(self):
        credential = self.create_access()
        self.client.force_login(credential["access"].student)

        self.assertEqual(self.client.get(reverse("accounts:student_access_list")).status_code, 403)

    def test_teacher_can_retrieve_own_students_projects_but_other_teacher_cannot(self):
        credential = self.create_access()
        project = Project.objects.create(
            owner=credential["access"].student,
            title="Schülerdialog",
            language="fr",
        )

        response = self.client.get(reverse("accounts:student_access_list"))
        self.assertContains(response, "Schülerdialog")
        self.assertEqual(
            self.client.get(reverse("projects:editor", args=[project.pk])).status_code,
            200,
        )

        self.client.force_login(self.other_teacher)
        self.assertEqual(
            self.client.get(reverse("projects:editor", args=[project.pk])).status_code,
            404,
        )

    def test_student_audio_quota_applies_across_billing_months(self):
        credential = self.create_access(character_limit=500)
        student = credential["access"].student
        UsageEvent.objects.create(
            user=student,
            provider=UsageEvent.Provider.ELEVENLABS,
            feature=UsageEvent.Feature.AUDIO,
            model="eleven_v3",
            status=UsageEvent.Status.COMMITTED,
            character_count=450,
            estimated_cost=Decimal("0.045"),
            currency="EUR",
            billing_period=(timezone.localdate().replace(day=1) - timedelta(days=1)).replace(day=1),
        )

        with self.assertRaisesMessage(QuotaExceeded, "Audio-Kontingent"):
            reserve_usage(
                user=student,
                provider=UsageEvent.Provider.ELEVENLABS,
                feature=UsageEvent.Feature.AUDIO,
                model="eleven_v3",
                estimated_cost=Decimal("0.010"),
                currency="EUR",
                character_count=100,
            )

    def test_ai_creation_is_hidden_when_student_has_no_ai_quota(self):
        credential = self.create_access(allow_ai=False)
        self.client.force_login(credential["access"].student)

        response = self.client.get(reverse("projects:create"))

        self.assertNotContains(response, "Mit KI-Unterstützung erstellen")
        self.assertContains(response, "Hörtext selbst erstellen")
