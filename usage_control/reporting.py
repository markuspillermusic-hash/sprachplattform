"""Read-only quota snapshots using the same periods and reservations as enforcement."""
import calendar
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import ProviderBudget, UsageEvent, current_month_start, effective_credits_expression, months_inclusive

ACTIVE = (UsageEvent.Status.COMMITTED, UsageEvent.Status.RESERVED)


def next_month(today):
    return today.replace(year=today.year + 1, month=1, day=1) if today.month == 12 else today.replace(month=today.month + 1, day=1)


def legacy_characters(user=None, today=None, lifetime=False):
    """Only old ledgers without a linked event; never count modern jobs twice."""
    from generation.models import UsageLedger
    rows = UsageLedger.objects.filter(job__usage_event__isnull=True)
    if user is not None:
        rows = rows.filter(user=user)
    if not lifetime:
        rows = rows.filter(billing_period=current_month_start(today))
    return rows.aggregate(total=Coalesce(Sum('character_count'), 0))['total']


def audio_usage(user, today=None):
    today = today or timezone.localdate()
    lifetime = user.role == user.Role.STUDENT
    events = UsageEvent.objects.filter(user=user, provider='elevenlabs', status__in=ACTIVE)
    if not lifetime:
        events = events.filter(billing_period=current_month_start(today))
    totals = split_total(events, 'character_count')
    totals['committed'] += legacy_characters(user, today, lifetime)
    return totals


def split_total(rows, expression):
    default = 0 if isinstance(expression, str) and expression in ('character_count', 'input_tokens', 'output_tokens') else Decimal('0')
    sums = rows.aggregate(
        committed=Coalesce(Sum(expression, filter=Q(status='committed')), default),
        reserved=Coalesce(Sum(expression, filter=Q(status='reserved')), default),
    )
    return {key: Decimal(str(value)) for key, value in sums.items()}


def meter(key, label, unit, limit, committed=0, reserved=0, reset=None, note='', enabled=True, precision=0):
    limit = max(Decimal('0'), Decimal(str(limit)))
    committed, reserved = Decimal(str(committed)), Decimal(str(reserved))
    total = committed + reserved
    percent = total / limit * 100 if limit else Decimal('0')
    state = 'disabled' if not enabled or not limit else 'exhausted' if total >= limit else 'warning' if percent >= 80 else 'available'
    return dict(key=key, label=label, unit=unit, limit=limit, committed=committed, reserved=reserved,
                total=total, remaining=max(Decimal('0'), limit-total), percent=percent,
                progress=min(Decimal('100'), percent), state=state, reset=reset, note=note, precision=precision,
                number_format=f'{precision}g')


def personal_snapshot(user, today=None):
    from audio_studio.models import StudioConfiguration, StudioJob
    today = today or timezone.localdate()
    month = current_month_start(today)
    lifetime = user.role == user.Role.STUDENT
    reset = None if lifetime else next_month(today)
    events = UsageEvent.objects.filter(user=user, provider='openai', status__in=ACTIVE)
    if not lifetime:
        events = events.filter(billing_period=month)
    audio = meter('speech', 'Sprache', 'Zeichen', user.character_limit, **audio_usage(user, today), reset=reset)
    cards = [audio]
    for key, label, field, limit in (
        ('input', 'KI-Eingaben', 'input_tokens', user.openai_monthly_input_token_limit),
        ('output', 'KI-Antworten', 'output_tokens', user.openai_monthly_output_token_limit),
    ):
        cards.append(meter(key, label, 'Tokens', limit, **split_total(events, field), reset=reset))
    daily = events if lifetime else events.filter(created_at__date=today)
    cards.append(meter('requests', 'KI-Anfragen' if lifetime else 'KI-Anfragen heute', 'Anfragen', user.openai_daily_request_limit,
        committed=daily.filter(status='committed').count(), reserved=daily.filter(status='reserved').count(),
        reset=None if lifetime else today+timedelta(days=1)))
    config = StudioConfiguration.objects.order_by('pk').first()
    if config and not lifetime:
        for kind, label in (('music', 'Musik'), ('effects', 'Geräusche')):
            rows = StudioJob.objects.filter(requested_by=user, kind=kind, created_at__date__gte=month, usage_event__status__in=ACTIVE)
            committed = rows.filter(usage_event__status='committed').aggregate(total=Sum('duration'))['total'] or 0
            reserved = rows.filter(usage_event__status='reserved').aggregate(total=Sum('duration'))['total'] or 0
            cards.append(meter(kind, label, 'Minuten', getattr(config, f'{kind}_seconds_per_user_month')/60,
                committed=committed/60, reserved=reserved/60, reset=reset, precision=2,
                enabled=getattr(config, f'{kind}_enabled'), note='Gezählt wird nur die erzeugte Quelldauer. Bibliotheksklänge und lokale Verlängerungen verbrauchen kein Generierungskontingent.'))
    expires = None
    if lifetime:
        try:
            expires = user.temporary_student_access.expires_at
        except ObjectDoesNotExist:
            pass
    return dict(month=month, reset=reset, lifetime=lifetime, expires=expires, cards=cards, compact_cards=cards[:3])


def provider_snapshot(budget, today=None):
    today = today or timezone.localdate()
    month = current_month_start(today)
    rows = budget.usage_queryset()
    enabled = budget.active and budget.starts_on <= today <= budget.expires_on
    reset = None
    if budget.monthly_credit_limit:
        start = budget.credit_cycle_start(today)
        rows = rows.filter(created_at__date__gte=start)
        limit = budget.spendable_credits
        totals = split_total(rows, effective_credits_expression())
        unit, precision = 'Credits', 0
        if budget.credit_cycle_day:
            anchor = today.replace(day=min(budget.credit_cycle_day, calendar.monthrange(today.year, today.month)[1]))
            target = anchor if today < anchor else next_month(today)
            reset = target.replace(day=min(budget.credit_cycle_day, calendar.monthrange(target.year, target.month)[1]))
            note = f'Abrechnungszyklus ab {start:%d.%m.%Y}. Rücksetzdatum nach eingetragenem Erneuerungstag; die genaue Anbieteruhrzeit kann abweichen.'
        else:
            note = 'Gleitender Rahmen über die letzten 31 Tage. Anbieter-Rücksetzdatum noch nicht bestätigt; kein fester monatlicher Reset.'
    else:
        cost = Coalesce('actual_cost', 'estimated_cost')
        limit = budget.spendable_amount
        if budget.enforce_monthly_pacing:
            before = rows.filter(created_at__date__lt=month).aggregate(total=Coalesce(Sum(cost), Decimal('0')))['total']
            limit = max(Decimal('0'), (limit-before)/max(1, months_inclusive(month, budget.expires_on)))
            rows = rows.filter(billing_period=month)
            reset = next_month(today)
            note = 'Dynamischer Monatsrahmen aus dem verbleibenden Gesamtbudget. Am Monatswechsel wird der Rahmen neu berechnet.'
        else:
            note = 'Gesamtbudget für die gesamte Laufzeit; kein monatlicher Reset.'
        totals = split_total(rows, cost)
        unit, precision = budget.currency, 2
    if reset and (reset > budget.expires_on or not enabled):
        reset = None
    card = meter(budget.provider, budget.get_provider_display(), unit, limit, **totals, reset=reset,
                 enabled=enabled, note=note, precision=precision)
    card.update(gross_limit=budget.monthly_credit_limit or budget.allocated_amount,
                reserve_percent=budget.reserve_percent, expires=budget.expires_on,
                active=enabled, scheduled=budget.starts_on > today, budget_id=budget.pk,
                starts=budget.starts_on)
    return card


def can_view_platform(user):
    return user.is_active and user.is_staff and user.role != user.Role.STUDENT and user.has_perm('usage_control.view_providerbudget')


def platform_snapshot(today=None):
    return [provider_snapshot(budget, today) for budget in ProviderBudget.objects.all()]


def review_snapshot(today=None):
    """Aggregated operational evidence; no usernames, texts, credentials or prompts."""
    from django.contrib.auth import get_user_model
    from django.conf import settings
    from audio_studio.models import SoundLibraryRequest, StudioConfiguration
    from script_assistant.models import AssistantConfiguration
    from tts.models import TTSConfiguration
    today = today or timezone.localdate()
    month = current_month_start(today)
    events = UsageEvent.objects.filter(status__in=ACTIVE)
    month_events = events.filter(billing_period=month)
    week_events = events.filter(created_at__date__gte=today-timedelta(days=6))
    groups = list(month_events.values('provider','feature','model','status','currency').annotate(
        requests=Count('pk'), users=Count('user_id', distinct=True), credits=Sum(effective_credits_expression()),
        input_tokens=Sum('input_tokens'), output_tokens=Sum('output_tokens'),
        cost=Sum(Coalesce('actual_cost','estimated_cost'))).order_by('provider','feature','model','status','currency'))
    pressures = []
    users = get_user_model().objects.filter(is_active=True).exclude(role='student')
    for user in users.iterator():
        snapshot = personal_snapshot(user, today)
        pressures.extend(card['key'] for card in snapshot['cards'] if card['state'] in ('warning','exhausted'))
    from collections import Counter
    studio = StudioConfiguration.objects.order_by('pk').first()
    assistant = AssistantConfiguration.objects.order_by('pk').first()
    tts = TTSConfiguration.objects.filter(active=True).order_by('pk').first()
    week_groups = list(week_events.values('provider','feature','model','status','currency').annotate(
        requests=Count('pk'), credits=Sum(effective_credits_expression()),
        input_tokens=Sum('input_tokens'), output_tokens=Sum('output_tokens'),
        cost=Sum(Coalesce('actual_cost','estimated_cost'))).order_by('provider','feature','model','status','currency'))
    return dict(as_of=today, calendar_month=month, calendar_reset=next_month(today),
        active_users_this_month=month_events.values('user').distinct().count(), requests_last_7_days=week_events.count(),
        pending_reservations=UsageEvent.objects.filter(status='reserved').count(),
        released_requests_this_month=UsageEvent.objects.filter(status='released',billing_period=month).count(),
        groups=groups, last_7_days=week_groups, provider_budgets=platform_snapshot(today), near_personal_limits=dict(Counter(pressures)),
        models=dict(speech=tts.model if tts and tts.is_configured else settings.ELEVENLABS_MODEL_ID, assistant=assistant.model if assistant else '',
                    music=studio.music_model if studio else '', effects='eleven_text_to_sound_v2'),
        library_requests_last_30_days=list(SoundLibraryRequest.objects.filter(created_at__date__gte=today-timedelta(days=29))
            .values('kind').annotate(projects=Count('project',distinct=True), requests=Count('pk')).order_by('kind')),
        scope='Platform usage only; money values are estimated where actual_cost is unavailable. Released reservations excluded. No external provider balance synchronization.')
