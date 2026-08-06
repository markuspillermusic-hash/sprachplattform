from django.db import transaction

from .models import ProviderVoice
from .providers import get_tts_provider


CURATED_LIBRARY_SEARCHES = (
    ("en", "british"),
    ("en", "american"),
    ("en", "australian"),
    ("en", "irish"),
    ("de", None),
    ("fr", None),
    ("es", None),
    ("it", None),
    ("tr", None),
    ("ru", None),
    ("ar", None),
)


def _store_voice(provider, voice, *, activate=False):
    catalog_voice, created = ProviderVoice.objects.update_or_create(
        provider="elevenlabs",
        model=provider.model_id,
        voice_id=voice.voice_id,
        defaults={
            "display_name": voice.name,
            "languages": list(voice.languages),
            "labels": voice.labels,
            "preview_url": voice.preview_url,
        },
    )
    if activate and not catalog_voice.active:
        catalog_voice.active = True
        catalog_voice.save(update_fields=["active", "updated_at"])
    return catalog_voice, created


@transaction.atomic
def sync_provider_voices(language=None):
    provider = get_tts_provider("elevenlabs")
    voices = provider.list_voices(language=language)
    synced = []
    for voice in voices:
        catalog_voice, _ = _store_voice(provider, voice)
        synced.append(catalog_voice)
    return synced


def sync_curated_voice_library(*, provider=None, activate=False, page_size=20):
    provider = provider or get_tts_provider("elevenlabs")
    synced = {}
    created_count = 0
    for language, accent in CURATED_LIBRARY_SEARCHES:
        voices = provider.search_voice_library(
            language=language,
            accent=accent,
            page_size=page_size,
            sort="trending",
        )
        for voice in voices:
            catalog_voice, created = _store_voice(provider, voice, activate=activate)
            synced[catalog_voice.pk] = catalog_voice
            created_count += int(created)
    return list(synced.values()), created_count
