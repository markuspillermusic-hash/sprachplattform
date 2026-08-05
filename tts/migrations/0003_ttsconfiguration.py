from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tts", "0002_voicefavorite")]

    operations = [
        migrations.CreateModel(
            name="TTSConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="ElevenLabs", max_length=80)),
                ("active", models.BooleanField(default=True)),
                ("model", models.CharField(default="eleven_v3", max_length=80)),
                ("base_url", models.URLField(default="https://api.elevenlabs.io")),
                ("estimated_eur_per_1000_characters", models.DecimalField(decimal_places=4, default="0.1800", max_digits=10, verbose_name="Geschätzte Kosten je 1.000 Credits in EUR")),
                ("encrypted_api_key", models.TextField(blank=True, editable=False)),
                ("api_key_hint", models.CharField(blank=True, editable=False, max_length=16)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "ElevenLabs-Anbindung", "verbose_name_plural": "ElevenLabs-Anbindung"},
        ),
    ]
