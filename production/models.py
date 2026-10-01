import uuid

from django.conf import settings
from django.db import models


class Production(models.Model):
    class Stage(models.TextChoices):
        SCRIPT = "script", "Skript prüfen"
        SPEECH = "speech", "Hörtext prüfen"
        PLAN = "plan", "Klanggestaltung planen"
        MIX = "mix", "Mischung prüfen"
        COMPLETE = "complete", "Fertiges Hörspiel"

    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="production")
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.SCRIPT)
    revision = models.PositiveIntegerField(default=0)
    brief = models.JSONField(default=dict)
    draft = models.JSONField(default=dict)
    approved_script = models.JSONField(default=dict)
    speech_job = models.ForeignKey("generation.GenerationJob", null=True, blank=True, on_delete=models.SET_NULL)
    approved_audio = models.ForeignKey("generation.AudioAsset", null=True, blank=True, on_delete=models.SET_NULL)
    plan = models.JSONField(default=dict)
    materials = models.JSONField(default=dict)
    mix_asset = models.ForeignKey("audio_studio.StudioAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="production_previews")
    mixed_revision = models.PositiveIntegerField(null=True, blank=True)
    final_asset = models.ForeignKey("audio_studio.StudioAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="production_finals")
    updated_at = models.DateTimeField(auto_now=True)


class ProductionRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Wartet"
        RUNNING = "running", "In Arbeit"
        SUCCEEDED = "succeeded", "Fertig"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="production_runs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, choices=[
        ("script", "Skript entwerfen"), ("refine", "Skript überarbeiten"),
        ("speech", "Hörtext erzeugen"), ("plan", "Klangplan entwerfen"),
        ("mix", "Mischung erstellen"), ("preview", "Studioschnitt anhören"),
        ("export", "Hörspiel exportieren")])
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    input_data = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    error_message = models.CharField(max_length=500, blank=True)
    progress = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=["project"], condition=models.Q(status__in=["queued", "running"]), name="one_active_production_run")]
