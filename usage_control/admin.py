import csv
from decimal import Decimal

from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils import timezone

from .models import ProviderBudget, UsageEvent, current_month_start, months_inclusive


@admin.register(ProviderBudget)
class ProviderBudgetAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "allocated_amount",
        "currency",
        "spent_display",
        "remaining_display",
        "monthly_target_display",
        "status_display",
        "expires_on",
        "active",
    )
    list_editable = ("active",)
    fieldsets = (
        ("Anbieter", {"fields": ("provider", "active", "currency")}),
        (
            "Zwölfmonatsbudget",
            {
                "fields": (
                    "allocated_amount",
                    "starts_on",
                    "expires_on",
                    "reserve_percent",
                    "enforce_monthly_pacing",
                    "warning_percent",
                )
            },
        ),
    )

    @admin.display(description="Gebucht")
    def spent_display(self, budget):
        return f"{budget.spent_amount():.2f} {budget.currency}"

    @admin.display(description="Verfügbar")
    def remaining_display(self, budget):
        return f"{max(Decimal('0'), budget.spendable_amount - budget.spent_amount()):.2f} {budget.currency}"

    @admin.display(description="Dynamischer Monatsrahmen")
    def monthly_target_display(self, budget):
        today = timezone.localdate()
        if today > budget.expires_on:
            return "abgelaufen"
        month_start = current_month_start(max(today, budget.starts_on))
        before_month = budget.usage_queryset().filter(created_at__date__lt=month_start)
        spent_before = before_month.aggregate(
            total=Coalesce(Sum(Coalesce("actual_cost", "estimated_cost")), Decimal("0"))
        )["total"]
        months = max(1, months_inclusive(month_start, budget.expires_on))
        target = (budget.spendable_amount - spent_before) / Decimal(months)
        return f"{max(Decimal('0'), target):.2f} {budget.currency}"

    @admin.display(description="Status")
    def status_display(self, budget):
        spendable = budget.spendable_amount
        percent = Decimal("100") if spendable <= 0 else budget.spent_amount() / spendable * 100
        if percent >= 95:
            color, label = "#ba2121", "kritisch"
        elif percent >= 85:
            color, label = "#b36b00", "beobachten"
        elif percent >= 70:
            color, label = "#6b6200", "Hinweis"
        else:
            color, label = "#287b45", "im Plan"
        return format_html(
            '<strong style="color:{}">{} · {}</strong>',
            color,
            label,
            f"{percent:.1f}%",
        )


@admin.register(UsageEvent)
class UsageEventAdmin(admin.ModelAdmin):
    change_list_template = "admin/usage_control/usageevent/change_list.html"
    list_display = (
        "created_at",
        "user",
        "provider",
        "feature",
        "status",
        "units_display",
        "cost_display",
        "model",
    )
    list_filter = ("provider", "feature", "status", "model", "billing_period")
    search_fields = ("user__username", "provider_request_id", "reference")
    date_hierarchy = "created_at"
    readonly_fields = tuple(field.name for field in UsageEvent._meta.fields)
    actions = ("export_csv",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Einheiten")
    def units_display(self, event):
        if event.provider == UsageEvent.Provider.ELEVENLABS:
            credits = event.provider_credit_count or event.character_count
            return f"{credits:g} Credits"
        return f"{event.input_tokens} In / {event.output_tokens} Out"

    @admin.display(description="Kosten")
    def cost_display(self, event):
        return f"{event.effective_cost:.4f} {event.currency}"

    def changelist_view(self, request, extra_context=None):
        month_start = current_month_start()
        month_events = UsageEvent.objects.filter(
            billing_period=month_start,
            status__in=(UsageEvent.Status.RESERVED, UsageEvent.Status.COMMITTED),
        )
        user_rows = list(
            month_events.values(
                "user__username",
                "user__character_limit",
                "user__openai_monthly_input_token_limit",
                "user__openai_monthly_output_token_limit",
            )
            .annotate(
                requests=Count("id"),
                characters=Coalesce(Sum("character_count"), 0),
                input_tokens=Coalesce(Sum("input_tokens"), 0),
                output_tokens=Coalesce(Sum("output_tokens"), 0),
                elevenlabs_cost=Coalesce(
                    Sum(
                        Coalesce("actual_cost", "estimated_cost"),
                        filter=Q(provider=UsageEvent.Provider.ELEVENLABS),
                    ),
                    Decimal("0"),
                ),
                openai_cost=Coalesce(
                    Sum(
                        Coalesce("actual_cost", "estimated_cost"),
                        filter=Q(provider=UsageEvent.Provider.OPENAI),
                    ),
                    Decimal("0"),
                ),
            )
            .order_by("-requests", "user__username")
        )
        for row in user_rows:
            tts_limit = row["user__character_limit"]
            input_limit = row["user__openai_monthly_input_token_limit"]
            output_limit = row["user__openai_monthly_output_token_limit"]
            row["tts_percent"] = min(100, round(row["characters"] / tts_limit * 100)) if tts_limit else 100
            input_percent = row["input_tokens"] / input_limit * 100 if input_limit else 100
            output_percent = row["output_tokens"] / output_limit * 100 if output_limit else 100
            row["openai_percent"] = min(100, round(max(input_percent, output_percent)))
        totals = month_events.aggregate(
            requests=Count("id"),
            characters=Coalesce(Sum("character_count"), 0),
            input_tokens=Coalesce(Sum("input_tokens"), 0),
            output_tokens=Coalesce(Sum("output_tokens"), 0),
        )
        extra_context = {
            **(extra_context or {}),
            "usage_month": month_start,
            "usage_totals": totals,
            "usage_user_rows": user_rows,
        }
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description="Ausgewählte Buchungen als CSV exportieren")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="sprachplattform-verbrauch.csv"'
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "Zeitpunkt",
                "Benutzer",
                "Anbieter",
                "Funktion",
                "Status",
                "Zeichen",
                "Credits",
                "Input-Tokens",
                "Output-Tokens",
                "Geschätzte Kosten",
                "Tatsächliche Kosten",
                "Währung",
                "Modell",
                "Provider-Request-ID",
            ]
        )
        for event in queryset.select_related("user"):
            writer.writerow(
                [
                    event.created_at.isoformat(),
                    event.user.username,
                    event.provider,
                    event.feature,
                    event.status,
                    event.character_count,
                    event.provider_credit_count,
                    event.input_tokens,
                    event.output_tokens,
                    event.estimated_cost,
                    event.actual_cost if event.actual_cost is not None else "",
                    event.currency,
                    event.model,
                    event.provider_request_id,
                ]
            )
        return response
