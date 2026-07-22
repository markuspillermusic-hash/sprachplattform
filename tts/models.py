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

