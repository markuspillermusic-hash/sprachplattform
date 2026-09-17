import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_openai_quotas"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Administrator"),
                    ("teacher", "Lehrkraft"),
                    ("student", "Temporärer Schülerzugang"),
                ],
                default="teacher",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="TemporaryStudentAccess",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("label", models.CharField(max_length=100)),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "student",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="temporary_student_access",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="temporary_student_accesses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Temporärer Schülerzugang",
                "verbose_name_plural": "Temporäre Schülerzugänge",
                "ordering": ("-created_at",),
            },
        ),
    ]
