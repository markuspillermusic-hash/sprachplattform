import io
import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import TemporaryStudentAccess
from audio_studio.models import StudioConfiguration, StudioJob
from generation.models import GenerationJob, UsageLedger
from generation.services import _period_usage
from projects.models import Project
from usage_control.models import ProviderBudget, UsageEvent
from usage_control.reporting import audio_usage, meter, personal_snapshot, provider_snapshot, review_snapshot
from usage_control.services import QuotaExceeded, reserve_usage


@override_settings(SECURE_SSL_REDIRECT=False)
class ReportingTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = get_user_model().objects.create_user(username='private-user', must_change_password=False,
            character_limit=100, openai_monthly_input_token_limit=1000, openai_monthly_output_token_limit=500)
        self.other = get_user_model().objects.create_user(username='other-private-user', must_change_password=False)

    def event(self, **changes):
        defaults = dict(user=self.user, provider='elevenlabs', feature='audio', model='test',
                        billing_period=self.today.replace(day=1))
        defaults.update(changes)
        return UsageEvent.objects.create(**defaults)

    def budget(self, **changes):
        defaults = dict(provider='elevenlabs', starts_on=date(2026,1,1), expires_on=date(2028,12,31),
                        reserve_percent=5, monthly_credit_limit=1000, credit_cycle_day=16)
        defaults.update(changes)
        return ProviderBudget.objects.create(**defaults)

    def test_personal_totals_include_reservations_exclude_released_and_other_users(self):
        self.event(status='committed',character_count=30)
        self.event(status='reserved',character_count=15)
        self.event(status='released',character_count=90)
        event=self.event(status='committed',character_count=80)
        UsageEvent.objects.filter(pk=event.pk).update(user=self.other)
        event=self.event(status='committed',character_count=10)
        UsageEvent.objects.filter(pk=event.pk).update(billing_period=date(2025,1,1))
        snapshot=personal_snapshot(self.user)
        card=snapshot['cards'][0]
        self.assertEqual((card['committed'],card['reserved'],card['remaining']), (30,15,55))
        self.assertEqual(card['percent'],45)
        self.assertEqual(self.client.get(reverse('usage_control:overview')).status_code,302)
        self.client.force_login(self.user)
        page=self.client.get(reverse('usage_control:overview'))
        self.assertContains(page,'Rücksetzung:')
        self.assertNotContains(page,'other-private-user')
        self.assertNotContains(page,'Gemeinsames Plattformkontingent')
        self.assertIn('no-store',page.headers['Cache-Control'])

    def test_calendar_reset_is_local_next_month_and_year_boundary(self):
        self.assertEqual(personal_snapshot(self.user,date(2026,12,31))['reset'],date(2027,1,1))
        self.assertEqual(personal_snapshot(self.user,date(2027,2,28))['reset'],date(2027,3,1))

    def test_known_credit_cycle_preserves_original_day_after_short_month(self):
        budget=self.budget(credit_cycle_day=31)
        feb=provider_snapshot(budget,date(2027,2,27))
        self.assertEqual(feb['reset'],date(2027,2,28))
        self.assertEqual(provider_snapshot(budget,date(2027,2,28))['reset'],date(2027,3,31))
        self.assertEqual(provider_snapshot(budget,date(2026,12,31))['reset'],date(2027,1,31))
        budget.credit_cycle_day=0
        card=provider_snapshot(budget,date(2027,3,1))
        self.assertIsNone(card['reset']); self.assertIn('noch nicht bestätigt',card['note'])

    def test_actual_provider_credits_replace_estimates_and_share_audio_types(self):
        budget=self.budget(credit_cycle_day=0)
        self.event(status='committed', provider_credit_count=60,estimated_credits=200)
        self.event(status='reserved', feature='music',estimated_credits=50)
        self.event(status='released',estimated_credits=900)
        card=provider_snapshot(budget)
        self.assertEqual((card['limit'],card['committed'],card['reserved'],card['remaining']),(950,60,50,840))

    def test_dynamic_money_month_matches_enforced_pacing_and_has_no_fake_yearly_reset(self):
        today=date(2026,10,10)
        budget=self.budget(provider='openai',monthly_credit_limit=0,allocated_amount=120,
            reserve_percent=0,starts_on=date(2026,10,1),expires_on=date(2026,12,31))
        event=UsageEvent.objects.create(user=self.user,provider='openai',feature='script_assistant',model='test',
            billing_period=today.replace(day=1),status='committed',actual_cost=5,estimated_cost=10)
        UsageEvent.objects.filter(pk=event.pk).update(created_at=timezone.make_aware(datetime(2026,10,2)))
        card=provider_snapshot(budget,today)
        self.assertEqual((card['limit'],card['committed'],card['remaining']),(40,5,35))
        self.assertEqual(card['reset'],date(2026,11,1))
        budget.enforce_monthly_pacing=False
        self.assertIsNone(provider_snapshot(budget,today)['reset'])
        budget.active=False
        self.assertEqual(provider_snapshot(budget,today)['state'],'disabled')
        budget.active=True; budget.expires_on=date(2026,10,31)
        self.assertIsNone(provider_snapshot(budget,today)['reset'])

    def test_students_keep_lifetime_usage_without_claiming_monthly_reset(self):
        self.user.role='student'; self.user.save()
        TemporaryStudentAccess.objects.create(student=self.user,teacher=self.other,label='QA',
            expires_at=timezone.now()+timezone.timedelta(days=3))
        event=self.event(status='committed',character_count=40)
        UsageEvent.objects.filter(pk=event.pk).update(billing_period=date(2025,1,1))
        snapshot=personal_snapshot(self.user)
        self.assertTrue(snapshot['lifetime']); self.assertIsNone(snapshot['reset'])
        self.assertEqual(snapshot['cards'][0]['total'],40)
        self.client.force_login(self.user)
        page=self.client.get(reverse('usage_control:overview'))
        self.assertContains(page,'nicht jeden Monat erneuert')
        self.assertNotContains(page,'Rücksetzung:')

    def test_legacy_ledgers_and_modern_events_are_counted_once_and_enforcement_agrees(self):
        def ledger(characters,event=None):
            job=GenerationJob.objects.create(requested_by=self.user,provider='elevenlabs',model='test',
                character_count=characters,estimated_cost_eur=0,usage_event=event)
            UsageLedger.objects.create(user=self.user,job=job,provider='elevenlabs',model='test',
                character_count=characters,estimated_cost_eur=0,billing_period=self.today.replace(day=1))
        event=self.event(status='committed',character_count=30)
        ledger(60,event)
        ledger(20)
        released=self.event(status='released',character_count=40); ledger(40,released)
        self.assertEqual(audio_usage(self.user)['committed'],50)
        self.assertEqual(_period_usage(self.user,self.today)[0],50)
        reserve_usage(user=self.user,provider='elevenlabs',feature='audio',model='test',estimated_cost=0,
            currency='EUR',character_count=50,estimated_credits=50)
        with self.assertRaises(QuotaExceeded):
            reserve_usage(user=self.user,provider='elevenlabs',feature='audio',model='test',estimated_cost=0,
                currency='EUR',character_count=1,estimated_credits=1)

    def test_studio_source_seconds_count_but_library_preparations_do_not(self):
        StudioConfiguration.objects.create(effects_enabled=True,effects_seconds_per_user_month=1800)
        project=Project.objects.create(owner=self.user,title='QA',language='de')
        event=self.event(status='committed',feature='sound_effects')
        StudioJob.objects.create(project=project,requested_by=self.user,kind='effects',duration=30,usage_event=event,input_data={})
        StudioJob.objects.create(project=project,requested_by=self.user,kind='library_prepare',duration=120,input_data={})
        card=next(c for c in personal_snapshot(self.user)['cards'] if c['key']=='effects')
        self.assertEqual(card['total'],Decimal('.5'))
        self.assertEqual(card['limit'],30)

    def test_zero_and_over_limit_are_not_shown_as_unlimited(self):
        self.assertEqual(meter('x','x','Tokens',0)['state'],'disabled')
        card=meter('x','x','Tokens',100,committed=110,reserved=10)
        self.assertEqual((card['percent'],card['progress'],card['remaining'],card['state']),(120,100,0,'exhausted'))

    def test_shared_budgets_require_explicit_permission_and_report_is_aggregate(self):
        self.budget()
        self.user.is_staff=True; self.user.save()
        self.client.force_login(self.user)
        url=reverse('usage_control:overview')
        self.assertNotContains(self.client.get(url),'Gemeinsames Plattformkontingent')
        self.user.is_superuser=True; self.user.save()
        self.assertContains(self.client.get(url),'Gemeinsames Plattformkontingent')
        self.event(status='committed',character_count=25)
        output=io.StringIO(); call_command('usage_review',stdout=output)
        report=json.loads(output.getvalue())
        self.assertEqual(report['active_users_this_month'],1)
        self.assertEqual(len(report['last_7_days']),1)
        self.assertNotIn('private-user',output.getvalue())
        self.assertNotIn('encrypted_api_key',output.getvalue())
