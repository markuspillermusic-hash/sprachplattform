from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.services import reset_temporary_password


class FirstLoginFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="maria",
            password="Temporary-Password-123!",
        )

    def test_first_login_forces_personal_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "Temporary-Password-123!"},
        )
        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)

        response = self.client.get(reverse("core:home"))
        self.assertRedirects(response, reverse("accounts:password_change"), fetch_redirect_response=False)

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "Temporary-Password-123!",
                "new_password1": "Eigene-Passphrase-2026!",
                "new_password2": "Eigene-Passphrase-2026!",
            },
        )
        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password("Eigene-Passphrase-2026!"))

    def test_logout_requires_post(self):
        self.user.must_change_password = False
        self.user.save(update_fields=["must_change_password"])
        self.client.force_login(self.user)

        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(
            self.client.post(reverse("accounts:logout")),
            reverse("accounts:login"),
            fetch_redirect_response=False,
        )

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "Temporary-Password-123!"},
        )
        self.assertContains(response, "Bitte Benutzername und Passwort eingeben")


class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        get_user_model().objects.create_user(username="ziel", password="Correct-Passphrase-123!")

    def test_repeated_failures_are_rate_limited(self):
        for _ in range(5):
            self.client.post(
                reverse("accounts:login"),
                {"username": "ziel", "password": "falsch"},
                REMOTE_ADDR="192.0.2.10",
            )

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "ziel", "password": "Correct-Passphrase-123!"},
            REMOTE_ADDR="192.0.2.10",
        )
        self.assertContains(response, "Zu viele fehlgeschlagene Anmeldeversuche")


class TemporaryPasswordTests(TestCase):
    def test_reset_returns_one_time_plaintext_and_updates_hash(self):
        user = get_user_model().objects.create_user(
            username="reset",
            password="Old-Passphrase-123!",
            must_change_password=False,
        )

        temporary_password = reset_temporary_password(user)
        user.refresh_from_db()

        self.assertGreaterEqual(len(temporary_password), 14)
        self.assertTrue(user.check_password(temporary_password))
        self.assertTrue(user.must_change_password)
