from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import httpx

from .base import (
    DialogueInput,
    ProviderConfigurationError,
    ProviderError,
    ProviderTemporaryError,
    SynthesisResult,
    TTSProvider,
    UsageEstimate,
    VoiceInfo,
)


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"
    max_characters = 2_000
    max_unique_voices = 10

    def __init__(
        self,
        *,
        api_key,
        base_url="https://api.elevenlabs.io",
        model_id="eleven_v3",
        estimated_eur_per_1000_characters=Decimal("0.18"),
        client=None,
    ):
        self.api_key = api_key
        self.model_id = model_id
        self.estimated_rate = Decimal(estimated_eur_per_1000_characters)
        self.client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(60, connect=10),
        )

    def _headers(self):
        if not self.api_key:
            raise ProviderConfigurationError("Der ElevenLabs-Zugang ist noch nicht konfiguriert.")
        return {"xi-api-key": self.api_key, "Accept": "application/json"}

    def _raise_safe(self, response):
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429 or status >= 500:
                raise ProviderTemporaryError(f"ElevenLabs ist vorübergehend nicht verfügbar (HTTP {status}).") from None
            raise ProviderError(f"ElevenLabs hat die Anfrage abgelehnt (HTTP {status}).") from None

    def list_voices(self, language=None):
        voices = []
        next_page_token = None
        while True:
            params = {"page_size": 100, "include_total_count": "false"}
            if next_page_token:
                params["next_page_token"] = next_page_token
            try:
                response = self.client.get("/v2/voices", params=params, headers=self._headers())
            except httpx.TimeoutException:
                raise ProviderTemporaryError("Die Stimmenliste konnte wegen einer Zeitüberschreitung nicht geladen werden.") from None
            except httpx.RequestError:
                raise ProviderTemporaryError("Die Verbindung zu ElevenLabs ist vorübergehend gestört.") from None
            self._raise_safe(response)
            payload = response.json()
            for item in payload.get("voices", []):
                verified = item.get("verified_languages") or []
                languages = tuple(sorted({entry.get("language", "") for entry in verified if entry.get("language")}))
                label_language = (item.get("labels") or {}).get("language")
                if label_language and label_language not in languages:
                    languages += (label_language,)
                if language and languages and language not in languages:
                    continue
                voices.append(
                    VoiceInfo(
                        voice_id=item["voice_id"],
                        name=item.get("name") or item["voice_id"],
                        languages=languages,
                        labels=item.get("labels") or {},
                        preview_url=item.get("preview_url") or "",
                    )
                )
            if not payload.get("has_more"):
                break
            next_page_token = payload.get("next_page_token")
            if not next_page_token:
                break
        return voices

    def search_voice_library(
        self,
        *,
        language=None,
        accent=None,
        page_size=20,
        sort="trending",
    ):
        params = {
            "page_size": max(1, min(int(page_size), 100)),
            "sort": sort,
            "include_custom_rates": "false",
            "include_live_moderated": "false",
            "min_notice_period_days": 30,
        }
        if language:
            params["language"] = language
        if accent:
            params["accent"] = accent
        try:
            response = self.client.get("/v1/shared-voices", params=params, headers=self._headers())
        except httpx.TimeoutException:
            raise ProviderTemporaryError("Die ElevenLabs-Stimmenbibliothek hat zu lange gebraucht.") from None
        except httpx.RequestError:
            raise ProviderTemporaryError("Die ElevenLabs-Stimmenbibliothek ist derzeit nicht erreichbar.") from None
        self._raise_safe(response)
        voices = []
        for item in response.json().get("voices", []):
            verified = item.get("verified_languages") or []
            languages = {
                entry.get("language", "")
                for entry in verified
                if entry.get("language")
            }
            if item.get("language"):
                languages.add(item["language"])
            labels = {
                key: str(item.get(key) or "").strip().lower()
                for key in ("age", "accent", "gender", "use_case", "descriptive")
                if item.get(key)
            }
            labels.update(
                catalog_source="voice_library",
                description=str(item.get("description") or "").strip(),
                notice_period_days=str(item.get("notice_period") or ""),
            )
            voices.append(
                VoiceInfo(
                    voice_id=item["voice_id"],
                    name=item.get("name") or item["voice_id"],
                    languages=tuple(sorted(languages)),
                    labels=labels,
                    preview_url=item.get("preview_url") or "",
                )
            )
        return voices

    def test_connection(self):
        try:
            response = self.client.get(
                "/v2/voices",
                params={"page_size": 1, "include_total_count": "false"},
                headers=self._headers(),
            )
        except httpx.TimeoutException:
            raise ProviderTemporaryError("Die ElevenLabs-Verbindung hat zu lange gedauert.") from None
        except httpx.RequestError:
            raise ProviderTemporaryError("ElevenLabs ist derzeit nicht erreichbar.") from None
        self._raise_safe(response)
        return True

    def estimate_usage(self, script):
        characters = sum(len(item.text) for item in script)
        cost = (Decimal(characters) / Decimal(1000) * self.estimated_rate).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )
        return UsageEstimate(characters=characters, estimated_cost_eur=cost)

    def synthesize_dialogue(self, script, options=None):
        script = list(script)
        options = options or {}
        estimate = self.estimate_usage(script)
        rendered_characters = sum(
            len(item.text)
            + (len(item.direction) + 3 if item.direction else 0)
            + (len(item.accent) + 3 if item.accent else 0)
            for item in script
        )
        if estimate.characters == 0:
            raise ProviderError("Das Skript enthält keinen Sprechtext.")
        if rendered_characters > self.max_characters:
            raise ProviderError("Der Dialogabschnitt überschreitet die sichere Grenze von 2.000 Zeichen.")
        if len({item.voice_id for item in script}) > self.max_unique_voices:
            raise ProviderError("Ein Dialogabschnitt darf höchstens zehn Stimmen verwenden.")

        inputs = []
        for item in script:
            accent = f"[{item.accent}] " if item.accent else ""
            direction = f"[{item.direction}] " if item.direction else ""
            inputs.append({"text": f"{accent}{direction}{item.text}", "voice_id": item.voice_id})
        body = {
            "inputs": inputs,
            "model_id": self.model_id,
        }
        for key in ("language_code", "seed", "settings", "apply_text_normalization"):
            if key in options and options[key] is not None:
                body[key] = options[key]
        params = {"output_format": options.get("output_format", "mp3_44100_128")}

        try:
            response = self.client.post(
                "/v1/text-to-dialogue",
                params=params,
                json=body,
                headers={**self._headers(), "Content-Type": "application/json", "Accept": "audio/mpeg"},
            )
        except httpx.TimeoutException:
            raise ProviderTemporaryError("Die Audioerzeugung hat zu lange gedauert.") from None
        except httpx.RequestError:
            raise ProviderTemporaryError("Die Verbindung zu ElevenLabs ist vorübergehend gestört.") from None
        self._raise_safe(response)
        try:
            provider_credit_count = (
                Decimal(response.headers["character-cost"])
                if response.headers.get("character-cost")
                else None
            )
        except (InvalidOperation, ValueError):
            provider_credit_count = None
        return SynthesisResult(
            audio=response.content,
            content_type=response.headers.get("content-type", "audio/mpeg"),
            provider_request_id=response.headers.get("request-id", response.headers.get("xi-request-id", "")),
            provider_credit_count=provider_credit_count,
        )

    def get_job_result(self, provider_job_id):
        raise ProviderError("Text to Dialogue liefert das Audio synchron; es gibt keinen separaten Providerauftrag.")


__all__ = ("DialogueInput", "ElevenLabsProvider")
