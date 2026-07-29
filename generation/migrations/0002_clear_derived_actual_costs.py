from django.db import migrations
from django.db.models import F


def clear_derived_actual_costs(apps, schema_editor):
    generation_job = apps.get_model("generation", "GenerationJob")
    usage_ledger = apps.get_model("generation", "UsageLedger")
    generation_job.objects.filter(
        actual_cost_eur=F("estimated_cost_eur"),
    ).update(actual_cost_eur=None)
    usage_ledger.objects.filter(
        actual_cost_eur=F("estimated_cost_eur"),
    ).update(actual_cost_eur=None)


class Migration(migrations.Migration):
    dependencies = [
        ("generation", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(clear_derived_actual_costs, migrations.RunPython.noop),
    ]
