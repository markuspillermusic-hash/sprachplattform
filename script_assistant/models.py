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
    conversation = models.ForeignKey(
        "AssistantConversation",
        on_delete=models.CASCADE,
        related_name="proposals",
        null=True,
        blank=True,
    )
    payload = models.JSONField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    apply_mode = models.CharField(max_length=16, choices=ApplyMode.choices, blank=True)
    previous_snapshot = models.JSONField(null=True, blank=True)
    applied_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)


class AssistantConfiguration(models.Model):
    MODEL_CHOICES = (
        ("gpt-5.6-luna", "GPT-5.6 Luna · sparsam"),
        ("gpt-5.6-terra", "GPT-5.6 Terra · ausgewogen"),
        ("gpt-5.6-sol", "GPT-5.6 Sol · höchste Qualität"),
    )

    name = models.CharField(max_length=80, default="OpenAI / ChatGPT")
    active = models.BooleanField(default=True)
    model = models.CharField(max_length=80, choices=MODEL_CHOICES, default="gpt-5.6-luna")
    base_url = models.URLField(default="https://api.openai.com/v1")
    encrypted_api_key = models.TextField(blank=True, editable=False)
    api_key_hint = models.CharField(max_length=16, blank=True, editable=False)
    max_output_tokens = models.PositiveIntegerField(default=8_000)
    pricing_currency = models.CharField(
        "Abrechnungswährung",
        max_length=3,
        choices=(("USD", "USD"), ("EUR", "EUR")),
        default="USD",
    )
    input_price_per_million = models.DecimalField(
        "Preis je 1 Mio. Eingabetokens",
        max_digits=10,
        decimal_places=4,
        default=1,
    )
    output_price_per_million = models.DecimalField(
        "Preis je 1 Mio. Ausgabetokens",
        max_digits=10,
        decimal_places=4,
        default=6,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "KI-Anbindung"
        verbose_name_plural = "KI-Anbindung"

    def __str__(self):
        return self.name

    @property
    def is_configured(self):
        return bool(self.active and self.encrypted_api_key)

    def set_api_key(self, api_key):
        from .secrets import encrypt_secret

        api_key = api_key.strip()
        self.encrypted_api_key = encrypt_secret(api_key) if api_key else ""
        self.api_key_hint = f"…{api_key[-4:]}" if api_key else ""

    def get_api_key(self):
        from .secrets import decrypt_secret

        return decrypt_secret(self.encrypted_api_key) if self.encrypted_api_key else ""


class AssistantConversation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "In Bearbeitung"
        APPLIED = "applied", "Übernommen"
        DISCARDED = "discarded", "Verworfen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assistant_conversations")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assistant_conversations",
    )
    brief = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    started_from_empty = models.BooleanField(default=False)
    provider = models.CharField(max_length=40, default="openai")
    model = models.CharField(max_length=80, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"KI-Entwurf für {self.project}"


class AssistantMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Nutzer"
        ASSISTANT = "assistant", "Assistent"

    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(max_length=4_000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
