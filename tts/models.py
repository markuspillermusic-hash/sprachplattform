from django.conf import settings
from django.db import models


class TTSConfiguration(models.Model):
    name = models.CharField(max_length=80, default="ElevenLabs")
    active = models.BooleanField(default=True)
    model = models.CharField(max_length=80, default="eleven_v3")
    base_url = models.URLField(default="https://api.elevenlabs.io")
    estimated_eur_per_1000_characters = models.DecimalField(
        "Geschätzte Kosten je 1.000 Credits in EUR",
        max_digits=10,
        decimal_places=4,
        default="0.1800",
    )
    encrypted_api_key = models.TextField(blank=True, editable=False)
    api_key_hint = models.CharField(max_length=16, blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ElevenLabs-Anbindung"
        verbose_name_plural = "ElevenLabs-Anbindung"

    def __str__(self):
        return self.name

    @property
    def is_configured(self):
        return bool(self.active and self.encrypted_api_key)

    def set_api_key(self, api_key):
        from script_assistant.secrets import encrypt_secret

        api_key = api_key.strip()
        self.encrypted_api_key = encrypt_secret(api_key) if api_key else ""
        self.api_key_hint = f"…{api_key[-4:]}" if api_key else ""

    def get_api_key(self):
        from script_assistant.secrets import decrypt_secret

        return decrypt_secret(self.encrypted_api_key) if self.encrypted_api_key else ""


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
