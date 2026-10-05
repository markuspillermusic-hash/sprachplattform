import uuid

from django.conf import settings
from django.db import models


class Worksheet(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Wird vorbereitet"
        RUNNING = "running", "Wird erstellt"
        READY = "ready", "Entwurf zur Prüfung"
        FAILED = "failed", "Nicht abgeschlossen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="worksheets")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    brief = models.JSONField(default=dict)
    source = models.JSONField(default=dict)
    payload = models.JSONField(default=dict)
    error_message = models.CharField(max_length=500, blank=True)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Arbeitsblatt"
        verbose_name_plural = "Arbeitsblätter"
