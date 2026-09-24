from django.db import migrations, models


def migrate_to_gpt6(apps, schema_editor):
    configuration = apps.get_model("script_assistant", "AssistantConfiguration")
    replacements = {
        "gpt-5.6-luna": ("gpt-6-luna", "0.1000", "0.5000"),
        "gpt-5.6-terra": ("gpt-6-sol", "2.0000", "10.0000"),
        "gpt-5.6-sol": ("gpt-6-sol", "2.0000", "10.0000"),
    }
    for old_model, (new_model, input_price, output_price) in replacements.items():
        configuration.objects.filter(model=old_model).update(
            model=new_model,
            reasoning_effort="low",
            pricing_currency="USD",
            input_price_per_million=input_price,
            output_price_per_million=output_price,
        )


class Migration(migrations.Migration):
    dependencies = [("script_assistant", "0004_assistantconfiguration_pricing")]

    operations = [
        migrations.AddField(
            model_name="assistantconfiguration",
            name="reasoning_effort",
            field=models.CharField(
                choices=[
                    ("none", "Ohne zusätzlichen Reasoning-Aufwand"),
                    ("low", "Niedrig · empfohlen"),
                    ("medium", "Mittel"),
                    ("high", "Hoch"),
                ],
                default="low",
                help_text=(
                    "Niedrig ist für strukturierte Hörtexte normalerweise ausreichend und spart Zeit und Tokens."
                ),
                max_length=16,
                verbose_name="Reasoning-Aufwand",
            ),
        ),
        migrations.AlterField(
            model_name="assistantconfiguration",
            name="model",
            field=models.CharField(
                choices=[
                    ("gpt-6-luna", "GPT-6 Luna · sparsam"),
                    ("gpt-6-sol", "GPT-6 Sol · höhere Qualität"),
                ],
                default="gpt-6-luna",
                max_length=80,
            ),
        ),
        migrations.AlterField(
            model_name="assistantconfiguration",
            name="input_price_per_million",
            field=models.DecimalField(
                decimal_places=4,
                default="0.1000",
                max_digits=10,
                verbose_name="Preis je 1 Mio. Eingabetokens",
            ),
        ),
        migrations.AlterField(
            model_name="assistantconfiguration",
            name="output_price_per_million",
            field=models.DecimalField(
                decimal_places=4,
                default="0.5000",
                max_digits=10,
                verbose_name="Preis je 1 Mio. Ausgabetokens",
            ),
        ),
        migrations.RunPython(migrate_to_gpt6, migrations.RunPython.noop),
    ]
