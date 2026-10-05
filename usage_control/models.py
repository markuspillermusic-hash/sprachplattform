import calendar
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.functions import Coalesce
from django.utils import timezone


class ProviderBudget(models.Model):
    class Provider(models.TextChoices):
        ELEVENLABS = "elevenlabs", "ElevenLabs"
        OPENAI = "openai", "OpenAI"

    provider = models.CharField(max_length=40, choices=Provider.choices, unique=True)
    active = models.BooleanField(default=True)
    allocated_amount = models.DecimalField(
        "Guthaben für die Sprachplattform",
        max_digits=12,
        decimal_places=4,
        default=0,
        help_text=(
            "Bei gemeinsam genutzten Anbieterkonten nur den Anteil eintragen, der für "
            "die Sprachplattform vorgesehen ist."
        ),
    )
    currency = models.CharField("Abrechnungswährung", max_length=3, default="EUR")
    starts_on = models.DateField("Beginn")
    expires_on = models.DateField("Ablaufdatum")
    reserve_percent = models.DecimalField(
        "Sicherheitsreserve in Prozent",
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
    )
    enforce_monthly_pacing = models.BooleanField(
        "Dynamischen Monatsrahmen erzwingen",
        default=True,
        help_text=(
            "Verteilt das verbleibende Guthaben gleichmäßig auf die verbleibenden Monate. "
            "Nicht verbrauchtes Budget wird automatisch neu verteilt."
        ),
    )
    warning_percent = models.DecimalField(
        "Warnschwelle in Prozent",
        max_digits=5,
        decimal_places=2,
        default=Decimal("80.00"),
    )
    monthly_credit_limit = models.PositiveIntegerField(
        "ElevenLabs-Credits je Abrechnungszyklus", default=0,
        help_text="0 verwendet das Geldbudget. Ein positiver Wert ersetzt es durch einen gemeinsamen Credit-Rahmen für Sprache, Musik und Geräusche; zählt nur Plattformnutzung.")
    credit_cycle_day = models.PositiveSmallIntegerField(
        "Erneuerungstag der Credits", default=0,
        validators=[MinValueValidator(0), MaxValueValidator(31)],
        help_text="0 verwendet vorsichtig die letzten 31 Tage. Sonst: Tag im Monat laut Anbieter-Abonnement; kurze Monate verwenden ihren letzten Tag.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Anbieterbudget"
        verbose_name_plural = "Anbieterbudgets"
        ordering = ("provider",)

    def __str__(self):
        return self.get_provider_display()

    def clean(self):
        errors = {}
        if self.expires_on and self.starts_on and self.expires_on <= self.starts_on:
            errors["expires_on"] = "Das Ablaufdatum muss nach dem Beginn liegen."
        if self.reserve_percent < 0 or self.reserve_percent >= 100:
            errors["reserve_percent"] = "Die Reserve muss zwischen 0 und unter 100 Prozent liegen."
        if self.warning_percent <= 0 or self.warning_percent > 100:
            errors["warning_percent"] = "Die Warnschwelle muss über 0 und höchstens 100 Prozent liegen."
        if self.monthly_credit_limit and self.provider != self.Provider.ELEVENLABS:
            errors["monthly_credit_limit"] = "Der Credit-Rahmen ist nur für ElevenLabs verfügbar."
        if errors:
            raise ValidationError(errors)

    @property
    def spendable_amount(self):
        return (self.allocated_amount * (Decimal("100") - self.reserve_percent) / Decimal("100"))

    def usage_queryset(self):
        return UsageEvent.objects.filter(
            provider=self.provider,
            status__in=(UsageEvent.Status.RESERVED, UsageEvent.Status.COMMITTED),
            created_at__date__gte=self.starts_on,
            created_at__date__lte=self.expires_on,
        )

    def spent_amount(self):
        return self.usage_queryset().aggregate(
            total=Coalesce(
                models.Sum(Coalesce("actual_cost", "estimated_cost")),
                Decimal("0"),
            )
        )["total"]

    def credit_cycle_start(self, today=None):
        today = today or timezone.localdate()
        if self.credit_cycle_day == 0:
            return max(today - timedelta(days=30), self.starts_on)
        anchor = today.replace(day=min(self.credit_cycle_day, calendar.monthrange(today.year, today.month)[1]))
        if today < anchor:
            year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
            anchor = anchor.replace(year=year, month=month, day=min(self.credit_cycle_day, calendar.monthrange(year, month)[1]))
        return max(anchor, self.starts_on)

    @property
    def spendable_credits(self):
        return Decimal(self.monthly_credit_limit) * (100 - self.reserve_percent) / 100

    def spent_credits(self, today=None):
        return self.usage_queryset().filter(created_at__date__gte=self.credit_cycle_start(today)).aggregate(
            total=Coalesce(models.Sum(effective_credits_expression()), Decimal("0")))["total"]


class UsageEvent(models.Model):
    class Provider(models.TextChoices):
        ELEVENLABS = "elevenlabs", "ElevenLabs"
        OPENAI = "openai", "OpenAI"

    class Feature(models.TextChoices):
        AUDIO = "audio", "Audioerzeugung"
        MUSIC = "music", "Musikerzeugung"
        SOUND_EFFECTS = "sound_effects", "Geräuscherzeugung"
        SCRIPT_ASSISTANT = "script_assistant", "KI-Hörtextassistent"
        WORKSHEET = "worksheet", "Arbeitsblatt-Assistent"

    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserviert"
        COMMITTED = "committed", "Verbraucht"
        RELEASED = "released", "Freigegeben"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="provider_usage_events",
    )
    provider = models.CharField(max_length=40, choices=Provider.choices)
    feature = models.CharField(max_length=40, choices=Feature.choices)
    model = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RESERVED)
    character_count = models.PositiveIntegerField(default=0)
    provider_credit_count = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    estimated_credits = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    actual_cost = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    provider_request_id = models.CharField(max_length=160, blank=True)
    reference = models.CharField(max_length=200, blank=True)
    billing_period = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Verbrauchsbuchung"
        verbose_name_plural = "Verbrauchsbuchungen"
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("provider", "billing_period", "status"),
                name="usage_contr_provide_8e06b7_idx",
            ),
            models.Index(
                fields=("user", "billing_period", "status"),
                name="usage_contr_user_id_4bca8c_idx",
            ),
        ]

    def __str__(self):
        return f"{self.get_provider_display()} · {self.user} · {self.created_at:%d.%m.%Y}"

    @property
    def effective_cost(self):
        if self.status == self.Status.RELEASED:
            return Decimal("0")
        return self.actual_cost if self.actual_cost is not None else self.estimated_cost

    @property
    def effective_credits(self):
        if self.status == self.Status.RELEASED:
            return Decimal("0")
        return self.provider_credit_count or self.estimated_credits or Decimal(self.character_count)


def effective_credits_expression():
    return models.Case(
        models.When(provider_credit_count__gt=0, then=models.F("provider_credit_count")),
        models.When(estimated_credits__gt=0, then=models.F("estimated_credits")),
        default=models.F("character_count"), output_field=models.DecimalField(max_digits=14, decimal_places=4))


def months_inclusive(start, end):
    if end < start:
        return 0
    return (end.year - start.year) * 12 + end.month - start.month + 1


def current_month_start(value=None):
    value = value or timezone.localdate()
    return value.replace(day=1)
