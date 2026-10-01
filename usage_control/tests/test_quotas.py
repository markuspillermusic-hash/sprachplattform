import calendar
import io
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from projects.models import Project
from script_assistant.models import AssistantConversation, AssistantMessage

from usage_control.models import ProviderBudget, UsageEvent
from usage_control.services import QuotaExceeded, commit_usage, release_usage, reserve_usage


def date_after_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, calendar.monthrange(year, month)[1])


class QuotaServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="quota-user",
            password="test",
            must_change_password=False,
            character_limit=100,
            openai_monthly_input_token_limit=100,
            openai_monthly_output_token_limit=5,
            openai_daily_request_limit=10,
        )

    def reserve_openai(self, output_tokens=2, estimated_cost="0.010000"):
        return reserve_usage(
            user=self.user,
            provider=UsageEvent.Provider.OPENAI,
            feature=UsageEvent.Feature.SCRIPT_ASSISTANT,
            model="gpt-test",
            estimated_cost=Decimal(estimated_cost),
            currency="USD",
            input_tokens=10,
            output_tokens=output_tokens,
        )

    def test_user_tokens_are_reserved_before_request_and_reconciled_afterwards(self):
        first = self.reserve_openai(output_tokens=4)
        commit_usage(first, input_tokens=8, output_tokens=3, actual_cost=Decimal("0.004"))

        with self.assertRaisesMessage(QuotaExceeded, "Ausgabekontingent"):
            self.reserve_openai(output_tokens=3)

        first.refresh_from_db()
        self.assertEqual(first.status, UsageEvent.Status.COMMITTED)
        self.assertEqual(first.output_tokens, 3)
        self.assertEqual(first.actual_cost, Decimal("0.004000"))

    def test_released_reservation_no_longer_consumes_user_quota(self):
        event = self.reserve_openai(output_tokens=5)
        release_usage(event)

        replacement = self.reserve_openai(output_tokens=5)

        self.assertEqual(replacement.status, UsageEvent.Status.RESERVED)

    def test_dynamic_budget_spreads_remaining_credit_over_remaining_months(self):
        today = timezone.localdate()
        ProviderBudget.objects.create(
            provider=ProviderBudget.Provider.OPENAI,
            allocated_amount=Decimal("120.00"),
            currency="USD",
            starts_on=today,
            expires_on=date_after_months(today, 11),
            reserve_percent=0,
            enforce_monthly_pacing=True,
        )
        self.reserve_openai(output_tokens=1, estimated_cost="9.00")

        with self.assertRaisesMessage(QuotaExceeded, "dynamische Monatsrahmen"):
            self.reserve_openai(output_tokens=1, estimated_cost="2.00")

    def credit_budget(self, **values):
        today = timezone.localdate()
        return ProviderBudget.objects.create(provider="elevenlabs", allocated_amount=0,
            monthly_credit_limit=100, reserve_percent=0, starts_on=today.replace(month=1,day=1),
            expires_on=date_after_months(today,11), **values)

    def reserve_credits(self, amount, feature="audio", user=None):
        return reserve_usage(user=user or self.user, provider="elevenlabs", feature=feature,
            model="test", estimated_cost=Decimal("10"), currency="EUR", estimated_credits=amount)

    def test_credit_pool_combines_all_users_and_features_and_reconciles_headers(self):
        budget = self.credit_budget()
        other = get_user_model().objects.create_user(username="second-credit-user", must_change_password=False)
        speech = self.reserve_credits(60)
        music = self.reserve_credits(25, "music", other)
        with self.assertRaisesMessage(QuotaExceeded, "gemeinsame ElevenLabs"):
            self.reserve_credits(20, "sound_effects", other)
        self.assertEqual(budget.spent_credits(), 85)
        commit_usage(speech, provider_credit_count=50)
        effects = self.reserve_credits(25, "sound_effects", other)
        self.assertEqual(budget.spent_credits(), 100)
        release_usage(music)
        self.assertEqual(budget.spent_credits(), 75)
        self.assertEqual(effects.effective_credits, 25)

    def test_credit_cycle_handles_reset_day_short_months_and_rolling_fallback(self):
        budget = self.credit_budget(credit_cycle_day=31)
        self.assertEqual(budget.credit_cycle_start(date(2027,2,27)), date(2027,1,31))
        self.assertEqual(budget.credit_cycle_start(date(2027,2,28)), date(2027,2,28))
        budget.credit_cycle_day = 0
        self.assertEqual(budget.credit_cycle_start(date(2027,3,2)), date(2027,1,31))

    def test_credit_reserve_and_period_boundary_are_enforced(self):
        from datetime import timedelta
        from unittest.mock import patch
        today = timezone.localdate()
        budget = self.credit_budget(); budget.reserve_percent = 5; budget.save()
        first = self.reserve_credits(95)
        with self.assertRaises(QuotaExceeded): self.reserve_credits(1)
        old = timezone.now() - timedelta(days=31)
        UsageEvent.objects.filter(pk=first.pk).update(created_at=old)
        self.assertEqual(budget.spent_credits(), 0)
        self.reserve_credits(95)

    def test_generous_configuration_is_previewable_and_preserves_disabled_features(self):
        from audio_studio.models import StudioConfiguration
        output = io.StringIO()
        call_command("configure_generous_limits", stdout=output)
        self.assertFalse(ProviderBudget.objects.exists())
        self.user.openai_daily_request_limit = 0; self.user.save()
        call_command("configure_generous_limits", apply=True, stdout=output)
        self.user.refresh_from_db()
        self.assertEqual(self.user.character_limit,100000)
        self.assertEqual(self.user.openai_daily_request_limit,0)
        self.assertEqual(ProviderBudget.objects.get(provider="elevenlabs").spendable_credits,123500)
        self.assertEqual(ProviderBudget.objects.get(provider="openai").allocated_amount,100)
        studio = StudioConfiguration.objects.get()
        self.assertTrue(studio.effects_enabled and studio.music_enabled)
        call_command("configure_generous_limits", apply=True, stdout=output)
        self.assertEqual(ProviderBudget.objects.count(),2)
        self.assertFalse(UsageEvent.objects.exists())


class UsagePrivacyAdminTests(TestCase):
    def test_conversation_admin_monitors_metadata_without_showing_message_content(self):
        admin_user = get_user_model().objects.create_superuser(
            username="usage-admin",
            password="test",
            email="admin@example.test",
            must_change_password=False,
        )
        project = Project.objects.create(owner=admin_user, title="Vertraulich", language="de")
        conversation = AssistantConversation.objects.create(
            project=project,
            created_by=admin_user,
            model="gpt-test",
        )
        AssistantMessage.objects.create(
            conversation=conversation,
            role=AssistantMessage.Role.USER,
            content="Dieser vertrauliche Inhalt darf nicht im Monitoring erscheinen.",
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("admin:script_assistant_assistantconversation_change", args=[conversation.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Dieser vertrauliche Inhalt")

    def test_usage_changelist_contains_per_user_month_summary(self):
        admin_user = get_user_model().objects.create_superuser(
            username="summary-admin",
            password="test",
            email="admin@example.test",
            must_change_password=False,
        )
        reserve_usage(
            user=admin_user,
            provider=UsageEvent.Provider.ELEVENLABS,
            feature=UsageEvent.Feature.AUDIO,
            model="eleven-test",
            estimated_cost=Decimal("0.10"),
            currency="EUR",
            character_count=50,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:usage_control_usageevent_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verbrauch nach Benutzer")
        self.assertContains(response, "summary-admin")
        self.assertContains(response, "50 Zeichen")
