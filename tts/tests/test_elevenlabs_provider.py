import json
from decimal import Decimal

import httpx
from django.test import SimpleTestCase

from tts.providers.base import DialogueInput, ProviderError
from tts.providers.elevenlabs import ElevenLabsProvider


class ElevenLabsProviderTests(SimpleTestCase):
    def provider_with_handler(self, handler):
        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.example.test",
        )
        return ElevenLabsProvider(
            api_key="test-key-never-log",
            client=client,
            estimated_eur_per_1000_characters=Decimal("0.20"),
        )

    def test_dialogue_request_uses_verified_endpoint_and_payload(self):
        captured = {}

        def handler(request):
            captured["path"] = request.url.path
            captured["query"] = dict(request.url.params)
            captured["headers"] = request.headers
            captured["json"] = json.loads(request.content)
            return httpx.Response(
                200,
                content=b"fake-mp3",
                headers={
                    "content-type": "audio/mpeg",
                    "request-id": "req-123",
                    "character-cost": "17.5",
                },
            )

        provider = self.provider_with_handler(handler)
        result = provider.synthesize_dialogue(
            [
                DialogueInput(
                    text="Bonjour !",
                    voice_id="voice-a",
                    direction="friendly",
                    accent="British accent",
                )
            ],
            {"language_code": "fr", "seed": 42},
        )

        self.assertEqual(captured["path"], "/v1/text-to-dialogue")
        self.assertEqual(captured["query"]["output_format"], "mp3_44100_128")
        self.assertEqual(captured["json"]["model_id"], "eleven_v3")
        self.assertEqual(
            captured["json"]["inputs"][0],
            {"text": "[British accent] [friendly] Bonjour !", "voice_id": "voice-a"},
        )
        self.assertEqual(captured["json"]["language_code"], "fr")
        self.assertEqual(captured["headers"]["xi-api-key"], "test-key-never-log")
        self.assertEqual(result.audio, b"fake-mp3")
        self.assertEqual(result.provider_request_id, "req-123")
        self.assertEqual(result.provider_credit_count, Decimal("17.5"))

    def test_voice_catalog_extracts_verified_languages(self):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "voices": [
                        {
                            "voice_id": "voice-a",
                            "name": "Camille",
                            "labels": {"gender": "female"},
                            "preview_url": "https://cdn.example.test/camille.mp3",
                            "verified_languages": [{"language": "fr", "model_id": "eleven_v3"}],
                        },
                        {
                            "voice_id": "voice-b",
                            "name": "John",
                            "labels": {},
                            "verified_languages": [{"language": "en", "model_id": "eleven_v3"}],
                        },
                    ],
                    "has_more": False,
                },
            )

        voices = self.provider_with_handler(handler).list_voices(language="fr")

        self.assertEqual([voice.name for voice in voices], ["Camille"])
        self.assertEqual(voices[0].languages, ("fr",))

    def test_provider_limits_are_checked_before_network_request(self):
        def handler(request):
            self.fail("Network request must not be sent for invalid input")

        provider = self.provider_with_handler(handler)
        with self.assertRaisesMessage(ProviderError, "2.000 Zeichen"):
            provider.synthesize_dialogue([DialogueInput(text="x" * 2001, voice_id="voice-a")])
        with self.assertRaisesMessage(ProviderError, "höchstens zehn Stimmen"):
            provider.synthesize_dialogue(
                [DialogueInput(text="x", voice_id=f"voice-{index}") for index in range(11)]
            )

    def test_shared_voice_library_search_uses_safe_filters_and_normalizes_metadata(self):
        captured = {}

        def handler(request):
            captured["path"] = request.url.path
            captured["query"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={
                    "voices": [
                        {
                            "voice_id": "shared-british",
                            "name": "Oliver",
                            "language": "en",
                            "accent": "British",
                            "gender": "Male",
                            "age": "Young",
                            "use_case": "conversational",
                            "descriptive": "calm",
                            "description": "A clear young British voice.",
                            "preview_url": "https://example.test/oliver.mp3",
                            "verified_languages": [
                                {"language": "en", "accent": "british", "locale": "en-GB"}
                            ],
                        }
                    ]
                },
            )

        voices = self.provider_with_handler(handler).search_voice_library(
            language="en",
            accent="british",
            page_size=20,
        )

        self.assertEqual(captured["path"], "/v1/shared-voices")
        self.assertEqual(captured["query"]["language"], "en")
        self.assertEqual(captured["query"]["accent"], "british")
        self.assertEqual(captured["query"]["include_custom_rates"], "false")
        self.assertEqual(voices[0].labels["gender"], "male")
        self.assertEqual(voices[0].labels["catalog_source"], "voice_library")
        self.assertEqual(voices[0].languages, ("en",))

    def test_rendered_direction_tags_count_toward_provider_limit(self):
        provider = self.provider_with_handler(
            lambda request: self.fail("Network request must not be sent for invalid input")
        )

        with self.assertRaisesMessage(ProviderError, "2.000 Zeichen"):
            provider.synthesize_dialogue(
                [DialogueInput(text="x" * 1995, voice_id="voice-a", direction="friendly")]
            )

    def test_rendered_accent_tags_count_toward_provider_limit(self):
        provider = self.provider_with_handler(
            lambda request: self.fail("Network request must not be sent for invalid input")
        )

        with self.assertRaisesMessage(ProviderError, "2.000 Zeichen"):
            provider.synthesize_dialogue(
                [DialogueInput(text="x" * 1985, voice_id="voice-a", accent="British accent")]
            )

    def test_usage_estimate_is_provider_neutral(self):
        provider = self.provider_with_handler(lambda request: httpx.Response(500))

        estimate = provider.estimate_usage([DialogueInput(text="x" * 250, voice_id="voice-a")])

        self.assertEqual(estimate.characters, 250)
        self.assertEqual(estimate.estimated_cost_eur, Decimal("0.0500"))

    def test_connection_check_uses_account_endpoint_without_generation(self):
        captured = {}

        def handler(request):
            captured["method"] = request.method
            captured["path"] = request.url.path
            return httpx.Response(200, json={"user_id": "school"})

        provider = self.provider_with_handler(handler)

        self.assertTrue(provider.test_connection())
        self.assertEqual(captured, {"method": "GET", "path": "/v2/voices"})

    def test_http_error_does_not_expose_api_key_or_response_body(self):
        provider = self.provider_with_handler(
            lambda request: httpx.Response(401, json={"detail": "secret provider payload"})
        )

        with self.assertRaises(ProviderError) as raised:
            provider.list_voices()

        message = str(raised.exception)
        self.assertNotIn("test-key-never-log", message)
        self.assertNotIn("secret provider payload", message)
        self.assertIn("HTTP 401", message)
