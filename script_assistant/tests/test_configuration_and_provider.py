import json

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from script_assistant.models import AssistantConfiguration
from script_assistant.providers import AssistantProviderResult, get_script_assistant_provider
from script_assistant.providers.openai import OpenAIScriptAssistantProvider

from .test_proposals import valid_payload


class AssistantConfigurationTests(TestCase):
    def test_api_key_is_encrypted_and_can_be_read_by_provider(self):
        configuration = AssistantConfiguration(model="gpt-6-luna")
        configuration.set_api_key("sk-test-secret-1234")
        configuration.save()

        self.assertNotIn("sk-test-secret", configuration.encrypted_api_key)
        self.assertEqual(configuration.api_key_hint, "…1234")
        self.assertEqual(configuration.get_api_key(), "sk-test-secret-1234")
        self.assertIsInstance(get_script_assistant_provider(), OpenAIScriptAssistantProvider)

    def test_admin_saves_key_but_never_renders_it_again(self):
        admin_user = get_user_model().objects.create_superuser(
            username="ki-admin",
            password="admin",
            email="admin@example.test",
            must_change_password=False,
        )
        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("admin:script_assistant_assistantconfiguration_add"),
            {
                "name": "OpenAI / ChatGPT",
                "active": "on",
                "model": "gpt-6-luna",
                "reasoning_effort": "low",
                "base_url": "https://api.openai.com/v1",
                "max_output_tokens": 8000,
                "api_key": "sk-admin-secret-9876",
                "_save": "Speichern",
            },
        )
        self.assertEqual(response.status_code, 302)
        configuration = AssistantConfiguration.objects.get()
        self.assertEqual(configuration.get_api_key(), "sk-admin-secret-9876")

        change = self.client.get(
            reverse("admin:script_assistant_assistantconfiguration_change", args=[configuration.pk])
        )
        self.assertContains(change, "…9876")
        self.assertNotContains(change, "sk-admin-secret-9876")

    def test_admin_model_change_keeps_key_and_applies_matching_prices(self):
        admin_user = get_user_model().objects.create_superuser(
            username="model-admin",
            password="admin",
            email="model-admin@example.test",
            must_change_password=False,
        )
        configuration = AssistantConfiguration.objects.create(
            model="gpt-6-luna",
            reasoning_effort="low",
        )
        configuration.set_api_key("sk-existing-secret-4321")
        configuration.save()
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse(
                "admin:script_assistant_assistantconfiguration_change",
                args=[configuration.pk],
            ),
            {
                "name": "OpenAI / ChatGPT",
                "active": "on",
                "model": "gpt-6-sol",
                "reasoning_effort": "low",
                "base_url": "https://api.openai.com/v1",
                "max_output_tokens": 8000,
                "pricing_currency": "USD",
                "input_price_per_million": "0.1000",
                "output_price_per_million": "0.5000",
                "_save": "Speichern",
            },
        )

        self.assertEqual(response.status_code, 302)
        configuration.refresh_from_db()
        self.assertEqual(configuration.model, "gpt-6-sol")
        self.assertEqual(configuration.get_api_key(), "sk-existing-secret-4321")
        self.assertEqual(str(configuration.input_price_per_million), "2.0000")
        self.assertEqual(str(configuration.output_price_per_million), "10.0000")


class OpenAIProviderTests(TestCase):
    def setUp(self):
        self.configuration = AssistantConfiguration(model="gpt-6-luna", reasoning_effort="low")
        self.configuration.set_api_key("sk-provider-test")
        self.configuration.save()

    def test_responses_api_uses_strict_schema_and_extracts_usage(self):
        captured = {}

        def handler(request):
            captured["authorization"] = request.headers["authorization"]
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "resp_123",
                    "model": "gpt-6-luna-2026-09-22",
                    "usage": {"input_tokens": 123, "output_tokens": 456},
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": json.dumps(valid_payload())}
                            ],
                        }
                    ],
                },
            )

        provider = OpenAIScriptAssistantProvider(
            self.configuration,
            transport=httpx.MockTransport(handler),
        )
        result = provider.generate_proposal(
            {"task": "create", "brief": {"language": "fr"}, "_user_id": 42}
        )

        self.assertIsInstance(result, AssistantProviderResult)
        self.assertEqual(result.payload["title"], "Au cinéma")
        self.assertEqual(result.input_tokens, 123)
        self.assertEqual(result.output_tokens, 456)
        self.assertEqual(captured["authorization"], "Bearer sk-provider-test")
        self.assertFalse(captured["body"]["store"])
        self.assertEqual(captured["body"]["reasoning"], {"effort": "low"})
        self.assertTrue(captured["body"]["text"]["format"]["strict"])
        speaker_schema = captured["body"]["text"]["format"]["schema"]["properties"]["speakers"]["items"]
        self.assertIn("age_group", speaker_schema["required"])
        self.assertIn("role_type", speaker_schema["required"])
        self.assertIn("accent", speaker_schema["required"])
        self.assertIn("voice_style", speaker_schema["required"])
        self.assertNotIn("_user_id", captured["body"]["input"])
        self.assertIn("safety_identifier", captured["body"])

    def test_connection_check_uses_model_endpoint_without_generation(self):
        captured = {}

        def handler(request):
            captured["method"] = request.method
            captured["path"] = request.url.path
            return httpx.Response(200, json={"id": "gpt-6-luna"})

        provider = OpenAIScriptAssistantProvider(
            self.configuration,
            transport=httpx.MockTransport(handler),
        )
        self.assertTrue(provider.test_connection())
        self.assertEqual(captured, {"method": "GET", "path": "/v1/models/gpt-6-luna"})
