import uuid

from django.conf import settings
from django.db import models

from projects.models import Project


class ProjectVersion(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="project_versions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-number",)
        constraints = [
            models.UniqueConstraint(fields=("project", "number"), name="unique_project_version_number")
        ]

    def __str__(self):
        return f"{self.project} · Version {self.number}"


class GenerationJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Wartet"
        RUNNING = "running", "Wird erzeugt"
        SUCCEEDED = "succeeded", "Fertig"
        FAILED = "failed", "Fehlgeschlagen"
        CANCELLED = "cancelled", "Abgebrochen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(ProjectVersion, on_delete=models.PROTECT, related_name="jobs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="generation_jobs")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=80)
    character_count = models.PositiveIntegerField()
    estimated_cost_eur = models.DecimalField(max_digits=10, decimal_places=4)
    actual_cost_eur = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    provider_request_ids = models.JSONField(default=list)
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)


class GenerationPart(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Wartet"
        RUNNING = "running", "Wird erzeugt"
        SUCCEEDED = "succeeded", "Fertig"
        FAILED = "failed", "Fehlgeschlagen"

    job = models.ForeignKey(GenerationJob, on_delete=models.CASCADE, related_name="parts")
    position = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    input_data = models.JSONField()
    character_count = models.PositiveIntegerField()
    pause_after_ms = models.PositiveIntegerField(default=0)
    audio_path = models.CharField(max_length=500, blank=True)
    provider_request_id = models.CharField(max_length=160, blank=True)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(fields=("job", "position"), name="unique_generation_part_position")
        ]


class AudioAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(ProjectVersion, on_delete=models.CASCADE, related_name="audio_assets")
    job = models.OneToOneField(GenerationJob, on_delete=models.PROTECT, related_name="audio_asset")
    file_path = models.CharField(max_length=500)
    format = models.CharField(max_length=16, default="mp3")
    duration_seconds = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    size_bytes = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)


class UsageLedger(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="usage_entries")
    job = models.OneToOneField(GenerationJob, on_delete=models.PROTECT, related_name="usage_entry")
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=80)
    character_count = models.PositiveIntegerField()
    estimated_cost_eur = models.DecimalField(max_digits=10, decimal_places=4)
    actual_cost_eur = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    billing_period = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
