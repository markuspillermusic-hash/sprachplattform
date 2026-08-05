from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("script_assistant", "0003_assistant_configuration_and_conversations")]

    operations = [
        migrations.AddField(
            model_name="assistantconfiguration",
            name="input_price_per_million",
            field=models.DecimalField(decimal_places=4, default=1, max_digits=10, verbose_name="Preis je 1 Mio. Eingabetokens"),
        ),
        migrations.AddField(
            model_name="assistantconfiguration",
            name="output_price_per_million",
            field=models.DecimalField(decimal_places=4, default=6, max_digits=10, verbose_name="Preis je 1 Mio. Ausgabetokens"),
        ),
        migrations.AddField(
            model_name="assistantconfiguration",
            name="pricing_currency",
            field=models.CharField(choices=[("USD", "USD"), ("EUR", "EUR")], default="USD", max_length=3, verbose_name="Abrechnungswährung"),
        ),
    ]
