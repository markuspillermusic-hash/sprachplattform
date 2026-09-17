import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        TEACHER = "teacher", "Lehrkraft"
        STUDENT = "student", "Temporärer Schülerzugang"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.TEACHER)
    must_change_password = models.BooleanField(default=True)
    character_limit = models.PositiveIntegerField(default=30_000)
    openai_monthly_input_token_limit = models.PositiveIntegerField(
        "OpenAI-Eingabetokens pro Monat",
        default=250_000,
    )
    openai_monthly_output_token_limit = models.PositiveIntegerField(
        "OpenAI-Ausgabetokens pro Monat",
        default=60_000,
    )
    openai_daily_request_limit = models.PositiveIntegerField(
        "OpenAI-Anfragen pro Tag",
        default=30,
    )
    demo_projects_initialized = models.BooleanField(default=False, editable=False)


class TemporaryStudentAccess(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="temporary_student_accesses",
    )
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="temporary_student_access",
    )
    label = models.CharField(max_length=100)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Temporärer Schülerzugang"
        verbose_name_plural = "Temporäre Schülerzugänge"

    def __str__(self):
        return f"{self.label} · {self.student.username}"

    @property
    def is_usable(self):
        return bool(
            self.revoked_at is None
            and self.expires_at > timezone.now()
            and self.student.is_active
        )

    @property
    def status_label(self):
        if self.revoked_at is not None or not self.student.is_active:
            return "Gesperrt"
        if self.expires_at <= timezone.now():
            return "Abgelaufen"
        return "Aktiv"
