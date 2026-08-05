from django.db import migrations, models
import django.db.models.deletion


def copy_existing_usage(apps, schema_editor):
    GenerationJob = apps.get_model("generation", "GenerationJob")
    UsageLedger = apps.get_model("generation", "UsageLedger")
    UsageEvent = apps.get_model("usage_control", "UsageEvent")
    for ledger in UsageLedger.objects.select_related("job").iterator():
        if ledger.job.status in {"queued", "running"}:
            status = "reserved"
        elif ledger.job.status == "succeeded":
            status = "committed"
        else:
            status = "released"
        event = UsageEvent.objects.create(
            user_id=ledger.user_id,
            provider=ledger.provider,
            feature="audio",
            model=ledger.model,
            status=status,
            character_count=ledger.character_count,
            provider_credit_count=ledger.provider_credit_count or 0,
            estimated_cost=ledger.estimated_cost_eur,
            actual_cost=ledger.actual_cost_eur,
            currency="EUR",
            reference=f"generation:{ledger.job_id}:migrated",
            billing_period=ledger.billing_period,
            created_at=ledger.created_at,
        )
        UsageEvent.objects.filter(pk=event.pk).update(created_at=ledger.created_at)
        GenerationJob.objects.filter(pk=ledger.job_id).update(usage_event_id=event.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("generation", "0002_clear_derived_actual_costs"),
        ("usage_control", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="generationjob",
            name="provider_credit_count",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="generationjob",
            name="usage_event",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="generation_job", to="usage_control.usageevent"),
        ),
        migrations.AddField(
            model_name="generationpart",
            name="provider_credit_count",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="usageledger",
            name="provider_credit_count",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True),
        ),
        migrations.RunPython(copy_existing_usage, migrations.RunPython.noop),
    ]
