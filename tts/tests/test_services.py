from django.test import TestCase

from tts.models import ProviderVoice
from tts.providers.base import VoiceInfo
from tts.services import CURATED_LIBRARY_SEARCHES, sync_curated_voice_library


class FakeLibraryProvider:
    model_id = "eleven_v3"

    def __init__(self):
        self.calls = []

    def search_voice_library(self, **kwargs):
        self.calls.append(kwargs)
        return [
            VoiceInfo(
                voice_id="shared-voice",
                name="Shared Voice",
                languages=(kwargs["language"],),
                labels={
                    "accent": kwargs.get("accent") or "standard",
                    "catalog_source": "voice_library",
                },
                preview_url="https://example.test/shared.mp3",
            )
        ]


class VoiceLibrarySyncTests(TestCase):
    def test_curated_import_deduplicates_and_keeps_new_voices_inactive(self):
        provider = FakeLibraryProvider()

        voices, created = sync_curated_voice_library(provider=provider, page_size=12)

        self.assertEqual(len(provider.calls), len(CURATED_LIBRARY_SEARCHES))
        self.assertTrue(all(call["page_size"] == 12 for call in provider.calls))
        self.assertEqual(len(voices), 1)
        self.assertEqual(created, 1)
        stored = ProviderVoice.objects.get(voice_id="shared-voice")
        self.assertFalse(stored.active)
        self.assertEqual(stored.labels["catalog_source"], "voice_library")
        self.assertEqual(
            stored.labels["curated_matches"],
            sorted(
                f"{language}:{accent or 'all'}"
                for language, accent in CURATED_LIBRARY_SEARCHES
            ),
        )
        self.assertEqual(stored.labels["curated_ranks"]["en:british"], 1)
