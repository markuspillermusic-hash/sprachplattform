from django.test import TestCase
from django.urls import reverse


class HomeViewTests(TestCase):
    def test_home_page_uses_project_language_and_heading(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="de">')
        self.assertContains(response, "Hörtexte für den Sprachunterricht")

    def test_security_headers_allow_only_required_capabilities(self):
        response = self.client.get(reverse("core:home"))

        policy = response.headers["Content-Security-Policy"]
        self.assertIn("script-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")
        self.assertNotContains(response, "<script>")


class HealthViewTests(TestCase):
    def test_liveness_endpoint(self):
        response = self.client.get(reverse("core:live"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_endpoint_checks_database(self):
        response = self.client.get(reverse("core:ready"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})
