from django.db import transaction

from .models import ProviderVoice
from .providers import get_tts_provider


@transaction.atomic
def sync_provider_voices(language=None):
    provider = get_tts_provider("elevenlabs")
    voices = provider.list_voices(language=language)
    synced = []
    for voice in voices:
        catalog_voice, _ = ProviderVoice.objects.update_or_create(
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
        synced.append(catalog_voice)
    return synced
