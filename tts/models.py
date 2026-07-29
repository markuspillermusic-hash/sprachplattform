from django.conf import settings
from django.db import models


class ProviderVoice(models.Model):
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=80)
    voice_id = models.CharField(max_length=160)
    display_name = models.CharField(max_length=120)
    languages = models.JSONField(default=list)
    labels = models.JSONField(default=dict, blank=True)
    preview_url = models.URLField(max_length=500, blank=True)
    active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("display_name",)
        constraints = [
            models.UniqueConstraint(fields=("provider", "model", "voice_id"), name="unique_provider_model_voice")
        ]

    def __str__(self):
        return self.display_name


class VoiceFavorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_favorites",
    )
    voice = models.ForeignKey(
        ProviderVoice,
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "voice"),
                name="unique_user_voice_favorite",
            )
        ]

    def __str__(self):
        return f"{self.user} · {self.voice}"
