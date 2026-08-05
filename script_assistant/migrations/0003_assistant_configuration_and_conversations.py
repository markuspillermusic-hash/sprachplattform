import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0003_project_demo_key_project_unique_owner_demo_project"),
        ("script_assistant", "0002_assistantproposal_applied_snapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="OpenAI / ChatGPT", max_length=80)),
                ("active", models.BooleanField(default=True)),
                (
                    "model",
                    models.CharField(
                        choices=[
                            ("gpt-5.6-luna", "GPT-5.6 Luna · sparsam"),
                            ("gpt-5.6-terra", "GPT-5.6 Terra · ausgewogen"),
                            ("gpt-5.6-sol", "GPT-5.6 Sol · höchste Qualität"),
                        ],
                        default="gpt-5.6-luna",
                        max_length=80,
                    ),
                ),
                ("base_url", models.URLField(default="https://api.openai.com/v1")),
                ("encrypted_api_key", models.TextField(blank=True, editable=False)),
                ("api_key_hint", models.CharField(blank=True, editable=False, max_length=16)),
                ("max_output_tokens", models.PositiveIntegerField(default=8000)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "KI-Anbindung", "verbose_name_plural": "KI-Anbindung"},
        ),
        migrations.CreateModel(
            name="AssistantConversation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("brief", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "In Bearbeitung"), ("applied", "Übernommen"), ("discarded", "Verworfen")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("started_from_empty", models.BooleanField(default=False)),
                ("provider", models.CharField(default="openai", max_length=40)),
                ("model", models.CharField(blank=True, max_length=80)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assistant_conversations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assistant_conversations",
                        to="projects.project",
                    ),
                ),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="AssistantMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("user", "Nutzer"), ("assistant", "Assistent")], max_length=16)),
                ("content", models.TextField(max_length=4000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="script_assistant.assistantconversation",
                    ),
                ),
            ],
            options={"ordering": ("created_at", "pk")},
        ),
        migrations.AddField(
            model_name="assistantproposal",
            name="conversation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="proposals",
                to="script_assistant.assistantconversation",
            ),
        ),
    ]
