from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        TEACHER = "teacher", "Lehrkraft"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.TEACHER)
    must_change_password = models.BooleanField(default=True)
    character_limit = models.PositiveIntegerField(default=30_000)
    openai_monthly_input_token_limit = models.PositiveIntegerField(
        "OpenAI-Eingabetokens pro Monat",
        default=250_000,
    )
    openai_monthly_output_token_limit = models.PositiveIntegerField(
        "OpenAI-Ausgabetokens pro Monat",
        default=60_000,
    )
    openai_daily_request_limit = models.PositiveIntegerField(
        "OpenAI-Anfragen pro Tag",
        default=30,
    )
    demo_projects_initialized = models.BooleanField(default=False, editable=False)
