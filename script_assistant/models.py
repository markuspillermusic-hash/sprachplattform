import uuid

from django.conf import settings
from django.db import models

from projects.models import Project


class AssistantProposal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Zur Prüfung"
        APPLIED = "applied", "Übernommen"
        DISCARDED = "discarded", "Verworfen"
        REVERTED = "reverted", "Rückgängig gemacht"

    class ApplyMode(models.TextChoices):
        REPLACE = "replace", "Skript ersetzen"
        APPEND = "append", "Skript ergänzen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assistant_proposals")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assistant_proposals")
    payload = models.JSONField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    apply_mode = models.CharField(max_length=16, choices=ApplyMode.choices, blank=True)
    previous_snapshot = models.JSONField(null=True, blank=True)
    applied_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
