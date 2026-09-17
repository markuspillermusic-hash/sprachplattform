import hashlib

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


class TemporaryStudentAccessForm(forms.Form):
    DURATION_CHOICES = (
        (2, "2 Stunden"),
        (8, "8 Stunden"),
        (24, "1 Tag"),
        (72, "3 Tage"),
        (168, "7 Tage"),
    )

    label = forms.CharField(
        label="Bezeichnung",
        max_length=100,
        help_text="Zum Beispiel „Französisch 8a“. Bitte keine vollständigen Schülernamen verwenden.",
        widget=forms.TextInput(attrs={"placeholder": "z. B. Französisch 8a"}),
    )
    count = forms.IntegerField(
        label="Anzahl der Zugänge",
        min_value=1,
        max_value=35,
        initial=1,
        help_text="Für jede Person wird ein eigener anonymer Zugang erzeugt.",
    )
    duration_hours = forms.TypedChoiceField(
        label="Gültigkeit",
        choices=DURATION_CHOICES,
        coerce=int,
        initial=24,
    )
    character_limit = forms.IntegerField(
        label="Audio-Kontingent je Zugang",
        min_value=500,
        max_value=20_000,
        initial=2_500,
        step_size=500,
        help_text="Gesamtzahl der Zeichen, die dieser Zugang in Audio umwandeln darf.",
    )
    allow_ai = forms.BooleanField(
        label="KI-Textassistent freigeben",
        required=False,
        help_text="Optional: höchstens fünf KI-Anfragen innerhalb der gesamten Laufzeit.",
    )


class RateLimitedAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "rate_limited": "Zu viele fehlgeschlagene Anmeldeversuche. Bitte warten Sie fünf Minuten.",
    }

    def _cache_key(self):
        username = self.data.get("username", "").strip().casefold()
        remote_address = self.request.META.get("REMOTE_ADDR", "unknown") if self.request else "unknown"
        digest = hashlib.sha256(f"{remote_address}:{username}".encode()).hexdigest()
        return f"login-attempts:{digest}"

    def clean(self):
        key = self._cache_key()
        attempts = cache.get(key, 0)
        if attempts >= settings.LOGIN_RATE_LIMIT_ATTEMPTS:
            raise forms.ValidationError(self.error_messages["rate_limited"], code="rate_limited")
        try:
            cleaned_data = super().clean()
        except forms.ValidationError:
            cache.set(key, attempts + 1, timeout=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
            raise
        cache.delete(key)
        return cleaned_data

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.role != user.Role.STUDENT:
            return
        try:
            access = user.temporary_student_access
        except ObjectDoesNotExist:
            access = None
        if access is None or access.revoked_at is not None or access.expires_at <= timezone.now():
            raise forms.ValidationError(
                "Dieser Schülerzugang ist nicht mehr gültig. Bitte wenden Sie sich an Ihre Lehrkraft.",
                code="student_access_expired",
            )
