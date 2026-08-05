from django.conf import settings

from .elevenlabs import ElevenLabsProvider


def get_tts_configuration():
    from tts.models import TTSConfiguration

    return TTSConfiguration.objects.filter(active=True).order_by("pk").first()


def tts_provider_is_configured():
    configuration = get_tts_configuration()
    return bool(
        (configuration and configuration.is_configured)
        or settings.ELEVENLABS_API_KEY
    )


def get_tts_provider(name="elevenlabs"):
    if name != "elevenlabs":
        raise ValueError("Unbekannter TTS-Provider.")
    configuration = get_tts_configuration()
    if configuration and configuration.is_configured:
        return ElevenLabsProvider(
            api_key=configuration.get_api_key(),
            base_url=configuration.base_url,
            model_id=configuration.model,
            estimated_eur_per_1000_characters=configuration.estimated_eur_per_1000_characters,
        )
    return ElevenLabsProvider(
        api_key=settings.ELEVENLABS_API_KEY,
        base_url=settings.ELEVENLABS_BASE_URL,
        model_id=settings.ELEVENLABS_MODEL_ID,
        estimated_eur_per_1000_characters=settings.TTS_ESTIMATED_EUR_PER_1000_CHARACTERS,
    )


__all__ = (
    "ElevenLabsProvider",
    "get_tts_configuration",
    "get_tts_provider",
    "tts_provider_is_configured",
)
