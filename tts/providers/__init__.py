from django.conf import settings

from .elevenlabs import ElevenLabsProvider


def get_tts_provider(name="elevenlabs"):
    if name != "elevenlabs":
        raise ValueError("Unbekannter TTS-Provider.")
    return ElevenLabsProvider(
        api_key=settings.ELEVENLABS_API_KEY,
        base_url=settings.ELEVENLABS_BASE_URL,
        model_id=settings.ELEVENLABS_MODEL_ID,
        estimated_eur_per_1000_characters=settings.TTS_ESTIMATED_EUR_PER_1000_CHARACTERS,
    )


__all__ = ("ElevenLabsProvider", "get_tts_provider")

