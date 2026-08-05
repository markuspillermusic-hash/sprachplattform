from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_user_demo_projects_initialized")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="openai_daily_request_limit",
            field=models.PositiveIntegerField(default=30, verbose_name="OpenAI-Anfragen pro Tag"),
        ),
        migrations.AddField(
            model_name="user",
            name="openai_monthly_input_token_limit",
            field=models.PositiveIntegerField(default=250000, verbose_name="OpenAI-Eingabetokens pro Monat"),
        ),
        migrations.AddField(
            model_name="user",
            name="openai_monthly_output_token_limit",
            field=models.PositiveIntegerField(default=60000, verbose_name="OpenAI-Ausgabetokens pro Monat"),
        ),
    ]
