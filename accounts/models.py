from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        TEACHER = "teacher", "Lehrkraft"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.TEACHER)
    must_change_password = models.BooleanField(default=True)
    character_limit = models.PositiveIntegerField(default=30_000)

