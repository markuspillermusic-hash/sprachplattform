from django.contrib.auth import get_user_model
from django.test import TestCase


class UserModelTests(TestCase):
    def test_teacher_defaults_are_safe_for_first_login(self):
        user = get_user_model().objects.create_user(
            username="lehrkraft",
            password="temporary-test-password",
        )

        self.assertEqual(user.role, user.Role.TEACHER)
        self.assertTrue(user.must_change_password)
        self.assertEqual(user.character_limit, 30_000)
