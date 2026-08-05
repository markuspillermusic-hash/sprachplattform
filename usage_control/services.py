import json
import math
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import ProviderBudget, UsageEvent, current_month_start, months_inclusive


class QuotaExceeded(RuntimeError):
    pass


class QuotaConfigurationError(QuotaExceeded):
    pass


ACTIVE_STATUSES = (UsageEvent.Status.RESERVED, UsageEvent.Status.COMMITTED)


def estimate_openai_input_tokens(request_data, overhead_tokens=2_500):
    serialized = json.dumps(request_data, ensure_ascii=False, separators=(",", ":"))
    return max(1, math.ceil(len(serialized) / 4) + overhead_tokens)


def calculate_token_cost(input_tokens, output_tokens, input_price, output_price):
    cost = (
        Decimal(input_tokens) * Decimal(input_price)
        + Decimal(output_tokens) * Decimal(output_price)
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _cost_total(queryset):
    return queryset.aggregate(
        total=Coalesce(
            Sum(Coalesce("actual_cost", "estimated_cost")),
            Decimal("0"),
        )
    )["total"]


def _check_user_quota(user, provider, character_count, input_tokens, output_tokens, today):
    month_start = current_month_start(today)
    usage = UsageEvent.objects.filter(
        user=user,
        provider=provider,
        billing_period=month_start,
        status__in=ACTIVE_STATUSES,
    )
    totals = usage.aggregate(
        characters=Coalesce(Sum("character_count"), 0),
        input_tokens=Coalesce(Sum("input_tokens"), 0),
        output_tokens=Coalesce(Sum("output_tokens"), 0),
    )
    if provider == UsageEvent.Provider.ELEVENLABS:
        if totals["characters"] + character_count > user.character_limit:
            raise QuotaExceeded("Ihr monatliches ElevenLabs-Kontingent ist erreicht.")
        return

    daily_requests = usage.filter(created_at__date=today).count()
    if daily_requests >= user.openai_daily_request_limit:
        raise QuotaExceeded("Ihr tägliches Kontingent für den KI-Assistenten ist erreicht.")
    if totals["input_tokens"] + input_tokens > user.openai_monthly_input_token_limit:
        raise QuotaExceeded("Ihr monatliches OpenAI-Eingabekontingent ist erreicht.")
    if totals["output_tokens"] + output_tokens > user.openai_monthly_output_token_limit:
        raise QuotaExceeded("Ihr monatliches OpenAI-Ausgabekontingent ist erreicht.")


def _check_provider_budget(provider, estimated_cost, currency, today):
    budget = (
        ProviderBudget.objects.select_for_update()
        .filter(provider=provider, active=True)
        .first()
    )
    if budget is None:
        return
    if today < budget.starts_on:
        raise QuotaExceeded("Das Anbieterbudget ist noch nicht freigegeben.")
    if today > budget.expires_on:
        raise QuotaExceeded("Das Anbieterbudget ist abgelaufen.")
    if budget.currency.upper() != currency.upper():
        raise QuotaConfigurationError(
            f"Die Abrechnungswährung für {budget.get_provider_display()} stimmt nicht mit der Preiskonfiguration überein."
        )

    queryset = budget.usage_queryset()
    spent = _cost_total(queryset)
    spendable = budget.spendable_amount
    if spent + estimated_cost > spendable:
        raise QuotaExceeded(f"Das Gesamtbudget für {budget.get_provider_display()} ist erreicht.")

    if budget.enforce_monthly_pacing:
        month_start = current_month_start(today)
        before_month = _cost_total(queryset.filter(created_at__date__lt=month_start))
        month_spent = _cost_total(queryset.filter(billing_period=month_start))
        remaining_months = months_inclusive(month_start, budget.expires_on)
        monthly_target = (
            (spendable - before_month) / Decimal(max(1, remaining_months))
        )
        if month_spent + estimated_cost > monthly_target:
            raise QuotaExceeded(
                f"Der dynamische Monatsrahmen für {budget.get_provider_display()} ist erreicht."
            )


@transaction.atomic
def reserve_usage(
    *,
    user,
    provider,
    feature,
    model,
    estimated_cost,
    currency,
    character_count=0,
    input_tokens=0,
    output_tokens=0,
    reference="",
):
    today = timezone.localdate()
    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
    estimated_cost = Decimal(estimated_cost)
    _check_user_quota(
        locked_user,
        provider,
        character_count,
        input_tokens,
        output_tokens,
        today,
    )
    _check_provider_budget(provider, estimated_cost, currency, today)
    return UsageEvent.objects.create(
        user=locked_user,
        provider=provider,
        feature=feature,
        model=model,
        status=UsageEvent.Status.RESERVED,
        character_count=character_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        currency=currency.upper(),
        reference=reference,
        billing_period=current_month_start(today),
    )


@transaction.atomic
def commit_usage(
    event,
    *,
    estimated_cost=None,
    actual_cost=None,
    character_count=None,
    provider_credit_count=None,
    input_tokens=None,
    output_tokens=None,
    provider_request_id=None,
    reference=None,
):
    event = UsageEvent.objects.select_for_update().get(pk=event.pk)
    event.status = UsageEvent.Status.COMMITTED
    if estimated_cost is not None:
        event.estimated_cost = Decimal(estimated_cost)
    if actual_cost is not None:
        event.actual_cost = Decimal(actual_cost)
    if character_count is not None:
        event.character_count = character_count
    if provider_credit_count is not None:
        event.provider_credit_count = Decimal(provider_credit_count)
    if input_tokens is not None:
        event.input_tokens = input_tokens
    if output_tokens is not None:
        event.output_tokens = output_tokens
    if provider_request_id is not None:
        event.provider_request_id = provider_request_id
    if reference is not None:
        event.reference = reference
    event.save()
    return event


@transaction.atomic
def release_usage(event, *, reference=None):
    event = UsageEvent.objects.select_for_update().get(pk=event.pk)
    event.status = UsageEvent.Status.RELEASED
    if reference is not None:
        event.reference = reference
    event.save(update_fields=("status", "reference", "updated_at"))
    return event
