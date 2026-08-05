import decimal
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0003_user_openai_quotas"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderBudget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("elevenlabs", "ElevenLabs"), ("openai", "OpenAI")], max_length=40, unique=True)),
                ("active", models.BooleanField(default=True)),
                ("allocated_amount", models.DecimalField(decimal_places=4, default=0, help_text="Bei gemeinsam genutzten Anbieterkonten nur den Anteil eintragen, der für die Sprachplattform vorgesehen ist.", max_digits=12, verbose_name="Guthaben für die Sprachplattform")),
                ("currency", models.CharField(default="EUR", max_length=3, verbose_name="Abrechnungswährung")),
                ("starts_on", models.DateField(verbose_name="Beginn")),
                ("expires_on", models.DateField(verbose_name="Ablaufdatum")),
                ("reserve_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("10.00"), max_digits=5, verbose_name="Sicherheitsreserve in Prozent")),
                ("enforce_monthly_pacing", models.BooleanField(default=True, help_text="Verteilt das verbleibende Guthaben gleichmäßig auf die verbleibenden Monate. Nicht verbrauchtes Budget wird automatisch neu verteilt.", verbose_name="Dynamischen Monatsrahmen erzwingen")),
                ("warning_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("80.00"), max_digits=5, verbose_name="Warnschwelle in Prozent")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Anbieterbudget", "verbose_name_plural": "Anbieterbudgets", "ordering": ("provider",)},
        ),
        migrations.CreateModel(
            name="UsageEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(choices=[("elevenlabs", "ElevenLabs"), ("openai", "OpenAI")], max_length=40)),
                ("feature", models.CharField(choices=[("audio", "Audioerzeugung"), ("script_assistant", "KI-Hörtextassistent")], max_length=40)),
                ("model", models.CharField(max_length=80)),
                ("status", models.CharField(choices=[("reserved", "Reserviert"), ("committed", "Verbraucht"), ("released", "Freigegeben")], default="reserved", max_length=16)),
                ("character_count", models.PositiveIntegerField(default=0)),
                ("provider_credit_count", models.DecimalField(decimal_places=4, default=0, max_digits=14)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("estimated_cost", models.DecimalField(decimal_places=6, default=0, max_digits=14)),
                ("actual_cost", models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True)),
                ("currency", models.CharField(default="EUR", max_length=3)),
                ("provider_request_id", models.CharField(blank=True, max_length=160)),
                ("reference", models.CharField(blank=True, max_length=200)),
                ("billing_period", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="provider_usage_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Verbrauchsbuchung", "verbose_name_plural": "Verbrauchsbuchungen", "ordering": ("-created_at",)},
        ),
        migrations.AddIndex(model_name="usageevent", index=models.Index(fields=["provider", "billing_period", "status"], name="usage_contr_provide_8e06b7_idx")),
        migrations.AddIndex(model_name="usageevent", index=models.Index(fields=["user", "billing_period", "status"], name="usage_contr_user_id_4bca8c_idx")),
    ]
