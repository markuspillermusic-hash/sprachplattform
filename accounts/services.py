import secrets
import string
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import TemporaryStudentAccess


TEMPORARY_PASSWORD_LENGTH = 18
TEMPORARY_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "-_.!"


def generate_temporary_password(length=TEMPORARY_PASSWORD_LENGTH):
    """Generate a one-time password without persisting its plain text."""
    if length < 14:
        raise ValueError("Temporäre Passwörter müssen mindestens 14 Zeichen lang sein.")
    return "".join(secrets.choice(TEMPORARY_PASSWORD_ALPHABET) for _ in range(length))


def reset_temporary_password(user):
    password = generate_temporary_password()
    user.set_password(password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
    return password


STUDENT_USERNAME_ALPHABET = string.ascii_lowercase + string.digits


def _student_username():
    users = get_user_model()
    while True:
        suffix = "".join(secrets.choice(STUDENT_USERNAME_ALPHABET) for _ in range(8))
        username = f"sp-{suffix}"
        if not users.objects.filter(username=username).exists():
            return username


@transaction.atomic
def create_temporary_student_accesses(
    *,
    teacher,
    label,
    count,
    duration_hours,
    character_limit,
    allow_ai=False,
):
    """Create anonymous, time-limited accounts and return one-time credentials."""
    users = get_user_model()
    if not (teacher.is_staff or teacher.role in (users.Role.ADMIN, users.Role.TEACHER)):
        raise PermissionError("Nur Lehrkräfte dürfen temporäre Schülerzugänge erstellen.")
    if count < 1 or count > 35:
        raise ValueError("Es können zwischen 1 und 35 Zugänge erstellt werden.")
    if duration_hours < 1 or duration_hours > 168:
        raise ValueError("Die Laufzeit darf höchstens sieben Tage betragen.")
    if character_limit < 500 or character_limit > 20_000:
        raise ValueError("Das Audio-Kontingent muss zwischen 500 und 20.000 Zeichen liegen.")
    expires_at = timezone.now() + timedelta(hours=duration_hours)
    credentials = []
    for index in range(1, count + 1):
        username = _student_username()
        password = generate_temporary_password()
        access_label = f"{label} · Platz {index:02d}" if count > 1 else label
        student = users.objects.create_user(
            username=username,
            password=password,
            role=users.Role.STUDENT,
            must_change_password=False,
            character_limit=character_limit,
            openai_monthly_input_token_limit=60_000 if allow_ai else 0,
            openai_monthly_output_token_limit=15_000 if allow_ai else 0,
            openai_daily_request_limit=5 if allow_ai else 0,
        )
        access = TemporaryStudentAccess.objects.create(
            teacher=teacher,
            student=student,
            label=access_label,
            expires_at=expires_at,
        )
        credentials.append(
            {
                "access": access,
                "username": username,
                "password": password,
            }
        )
    return credentials


@transaction.atomic
def revoke_temporary_student_access(access):
    if access.revoked_at is None:
        access.revoked_at = timezone.now()
        access.save(update_fields=["revoked_at"])
    if access.student.is_active:
        access.student.is_active = False
        access.student.save(update_fields=["is_active"])
    return access


@transaction.atomic
def reset_student_access_password(access):
    password = generate_temporary_password()
    access.student.set_password(password)
    access.student.must_change_password = False
    access.student.save(update_fields=["password", "must_change_password"])
    return password
