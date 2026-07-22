import hashlib

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache


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
