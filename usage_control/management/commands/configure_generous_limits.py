"""Reviewable, explicit configuration; does not purchase or top up provider credit."""
import calendar
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from audio_studio.models import StudioConfiguration
from script_assistant.models import AssistantConfiguration
from tts.models import TTSConfiguration
from usage_control.models import ProviderBudget, UsageEvent


def raise_positive_limits(queryset, values):
    for key, minimum in values.items():
        queryset.filter(**{f"{key}__gt": 0, f"{key}__lt": minimum}).update(**{key: minimum})


class Command(BaseCommand):
    help = "Zeigt großzügige Limits; --apply übernimmt sie ohne Anbieteraufrufe oder Guthabenkauf."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--elevenlabs-credits", type=int, default=130000)
        parser.add_argument("--cycle-day", type=int, default=0)
        parser.add_argument("--openai-budget", type=Decimal, default=Decimal("100"))

    @transaction.atomic
    def handle(self, *args, **options):
        if options["elevenlabs_credits"] <= 0 or not 0 <= options["cycle_day"] <= 31:
            raise CommandError("Credits müssen positiv sein; Erneuerungstag muss zwischen 0 und 31 liegen.")
        if not options["openai_budget"].is_finite() or options["openai_budget"] <= 0:
            raise CommandError("Das OpenAI-Budget muss positiv sein.")
        today = timezone.localdate()
        # Exactly twelve inclusive calendar months, without an accidental thirteenth month.
        end_index = today.month - 1 + 11
        end_year, end_month = today.year + end_index // 12, end_index % 12 + 1
        expires = date(end_year, end_month, calendar.monthrange(end_year, end_month)[1])
        assistant = AssistantConfiguration.objects.order_by("pk").first()
        currency = assistant.pricing_currency if assistant else "USD"
        tts = TTSConfiguration.objects.order_by("pk").first()
        rate = tts.estimated_eur_per_1000_characters if tts else Decimal("0.1")
        if rate <= 0:
            raise CommandError("Die vorhandene ElevenLabs-Tarifschätzung muss positiv sein.")
        normal_limits = {"character_limit": 100000, "openai_monthly_input_token_limit": 2000000,
                         "openai_monthly_output_token_limit": 500000, "openai_daily_request_limit": 100}
        student_limits = {"character_limit": 10000, "openai_monthly_input_token_limit": 200000,
                          "openai_monthly_output_token_limit": 50000, "openai_daily_request_limit": 15}
        plan = {"elevenlabs_credits": options["elevenlabs_credits"], "reserve_percent": 5,
                "elevenlabs_usage_start": str(today - timedelta(days=30)),
                "cycle_day": options["cycle_day"], "openai_platform_budget": str(options["openai_budget"]),
                "openai_currency": currency, "starts_on": str(today), "expires_on": str(expires),
                "teacher_admin_minimums": normal_limits, "student_minimums": student_limits,
                "studio_seconds_per_user_month": {"music": 1800, "effects": 1800},
                "estimated_music_credits_per_minute": 1500, "estimated_effects_credits_per_second": 20,
                "music_eur_per_minute": str(rate * Decimal("1.5")),
                "effects_eur_per_minute": str(rate * Decimal("1.2")),
                "unfunded_extra_topup": "Nicht als verfügbares Guthaben eingerechnet"}
        self.stdout.write(json.dumps(plan, ensure_ascii=False, indent=2))
        if not options["apply"]:
            self.stdout.write("Vorschau; keine Einstellungen geändert.")
            return
        users = get_user_model().objects.filter(is_active=True)
        raise_positive_limits(users.exclude(role="student"), normal_limits)
        raise_positive_limits(users.filter(role="student", temporary_student_access__revoked_at__isnull=True,
                                            temporary_student_access__expires_at__gt=timezone.now()), student_limits)
        studio = StudioConfiguration.objects.order_by("pk").first() or StudioConfiguration.objects.create()
        studio.music_enabled = studio.effects_enabled = True
        studio.music_seconds_per_user_month = max(studio.music_seconds_per_user_month, 1800)
        studio.effects_seconds_per_user_month = max(studio.effects_seconds_per_user_month, 1800)
        studio.music_credits_per_minute = max(studio.music_credits_per_minute, 1500)
        studio.effects_credits_per_second = max(studio.effects_credits_per_second, 20)
        studio.music_eur_per_minute = max(studio.music_eur_per_minute, rate * Decimal("1.5"))
        studio.effects_eur_per_minute = max(studio.effects_eur_per_minute, rate * Decimal("1.2"))
        studio.save()
        eleven, _ = ProviderBudget.objects.get_or_create(provider="elevenlabs", defaults={
            "starts_on": today, "expires_on": expires})
        eleven.active = True; eleven.monthly_credit_limit = options["elevenlabs_credits"]
        eleven.credit_cycle_day = options["cycle_day"]; eleven.reserve_percent = 5
        eleven.starts_on = min(eleven.starts_on, today - timedelta(days=30)); eleven.expires_on = max(eleven.expires_on, expires)
        eleven.save()
        openai, _ = ProviderBudget.objects.get_or_create(provider="openai", defaults={
            "starts_on": today, "expires_on": expires, "currency": currency})
        if openai.currency != currency:
            raise CommandError("Bestehendes OpenAI-Budget hat eine andere Währung; bitte zuerst korrigieren.")
        openai.active = True; openai.allocated_amount = max(openai.allocated_amount, options["openai_budget"])
        openai.reserve_percent = 5; openai.enforce_monthly_pacing = True
        openai.starts_on = min(openai.starts_on, today); openai.expires_on = max(openai.expires_on, expires)
        openai.save()
        # Preserve older reservations for which the provider did not return a credit header.
        for event in UsageEvent.objects.filter(provider="elevenlabs", estimated_credits=0, provider_credit_count=0):
            event.estimated_credits = max(Decimal(event.character_count), event.estimated_cost / rate * 1000)
            event.save(update_fields=["estimated_credits"])
        self.stdout.write(self.style.SUCCESS("Limits übernommen; keine Anbieteraufrufe und kein Guthaben gekauft."))
