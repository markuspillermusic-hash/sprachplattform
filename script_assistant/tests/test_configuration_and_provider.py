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
        configuration = AssistantConfiguration(model="gpt-5.6-luna")
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
                "model": "gpt-5.6-luna",
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


class OpenAIProviderTests(TestCase):
    def setUp(self):
        self.configuration = AssistantConfiguration(model="gpt-5.6-luna")
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
                    "model": "gpt-5.6-luna-2026-07-01",
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
            return httpx.Response(200, json={"id": "gpt-5.6-luna"})

        provider = OpenAIScriptAssistantProvider(
            self.configuration,
            transport=httpx.MockTransport(handler),
        )
        self.assertTrue(provider.test_connection())
        self.assertEqual(captured, {"method": "GET", "path": "/v1/models/gpt-5.6-luna"})
