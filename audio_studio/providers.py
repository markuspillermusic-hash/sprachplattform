from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx
from django.conf import settings

from tts.providers import get_tts_configuration, tts_provider_is_configured
from .media import StudioError


class ProviderRejected(StudioError):
    """Explicit rejection: the budget reservation may be released."""


@dataclass
class GeneratedAudio:
    audio: bytes
    request_id: str = ""
    credits: Decimal | None = None


def provider_credentials(config):
    if config.encrypted_api_key:
        return config.get_api_key(), "https://api.elevenlabs.io"
    tts = get_tts_configuration()
    if tts and tts.is_configured:
        return tts.get_api_key(), tts.base_url
    return settings.ELEVENLABS_API_KEY, settings.ELEVENLABS_BASE_URL


def provider_ready(config, kind):
    return bool(config and getattr(config, f"{kind}_enabled")
                and getattr(config, f"{kind}_eur_per_minute") > 0
                and (config.encrypted_api_key or tts_provider_is_configured()))


class ElevenLabsAudioProvider:
    """Adapter boundary for future music providers, including Suno."""
    def __init__(self, config, client=None):
        self.api_key, base_url = provider_credentials(config)
        self.client = client
        self.base_url = base_url

    def generate(self, kind, request):
        if not self.api_key:
            raise ProviderRejected("Der ElevenLabs-Zugang fehlt. Die Administration muss die Anbindung einrichten.")
        if kind == "music":
            endpoint = "/v1/music"
            payload = {"prompt": request["prompt"], "music_length_ms": round(request["duration"] * 1000),
                       "model_id": request["model"], "force_instrumental": True}
        else:
            endpoint = "/v1/sound-generation"
            payload = {"text": request["prompt"], "duration_seconds": request["duration"],
                       "model_id": "eleven_text_to_sound_v2", "loop": request["loop"]}
        client = self.client or httpx.Client(base_url=self.base_url.rstrip("/"),
                                            timeout=httpx.Timeout(600, connect=10), follow_redirects=False)
        try:
            with client.stream("POST", endpoint, json=payload,
                               params={"output_format": "auto" if kind == "music" else "mp3_44100_128"},
                               headers={"xi-api-key": self.api_key, "Accept": "audio/mpeg"}) as response:
                if response.status_code >= 300:
                    if response.status_code < 500:
                        raise ProviderRejected(f"ElevenLabs hat die Anfrage abgelehnt (HTTP {response.status_code}). Prüfen Sie Freigabe und Kontoguthaben.")
                    raise StudioError("ElevenLabs meldet einen Verarbeitungsfehler. Eine mögliche Nutzung bleibt protokolliert.")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > settings.AUDIO_STUDIO_MAX_UPLOAD_BYTES:
                        raise StudioError("Die Anbieterdatei überschreitet die zulässige Größe.")
                    chunks.append(chunk)
                if not size:
                    raise StudioError("ElevenLabs hat keine Audiodatei geliefert.")
                try:
                    credits = Decimal(response.headers["character-cost"])
                    if not credits.is_finite() or credits < 0:
                        credits = None
                except (KeyError, InvalidOperation):
                    credits = None
                return GeneratedAudio(b"".join(chunks),
                                      (response.headers.get("request-id") or response.headers.get("song-id") or "")[:160], credits)
        except httpx.RequestError:
            raise StudioError("Die Verbindung zu ElevenLabs wurde unterbrochen. Der Auftrag wird nicht automatisch erneut berechnet.") from None
        finally:
            if self.client is None:
                client.close()
