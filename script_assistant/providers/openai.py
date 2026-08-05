import hashlib
import json

import httpx

from projects.models import Project, ScriptSegment

from .base import AssistantProviderError, AssistantProviderResult, ScriptAssistantProvider


SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 160},
        "language": {"type": "string", "enum": list(Project.Language.values)},
        "level": {"type": "string", "enum": list(Project.Level.values)},
        "speakers": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 80}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        "segments": {
            "type": "array",
            "minItems": 1,
            "maxItems": 500,
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "text": {"type": "string", "minLength": 1, "maxLength": 4000},
                    "direction": {"type": "string", "enum": list(ScriptSegment.Direction.values)},
                    "pause_after_ms": {"type": "integer", "minimum": 0, "maximum": 5000},
                    "speed": {"type": "number", "minimum": 0.5, "maximum": 1.5},
                },
                "required": ["speaker", "text", "direction", "pause_after_ms", "speed"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "language", "level", "speakers", "segments"],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """Du erstellst didaktisch geeignete Hörtexte für den Sprachunterricht.
Halte Zielsprache, GER-Niveau, Situation, Rollen, gewünschte Länge und Lernziele genau ein.
Schreibe natürlich, altersneutral und ohne Erklärtext außerhalb des verlangten Schemas.
Jeder Sprechername muss eindeutig sein und jeder Beitrag muss einen vorhandenen Sprecher verwenden.
Schätze die Länge mit etwa 130 gesprochenen Wörtern pro Minute.
Regieanweisungen dürfen nur aus der vorgegebenen Auswahlliste stammen; nutze im Zweifel den leeren Wert.
Wenn ein vorhandener Entwurf und ein Änderungswunsch übergeben werden, überarbeite den Entwurf vollständig und bewahre alles, was nicht geändert werden soll."""


def _extract_text(data):
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise AssistantProviderError("Der KI-Dienst hat diese Anfrage abgelehnt.")
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    raise AssistantProviderError("Der KI-Dienst hat keinen verwendbaren Entwurf zurückgegeben.")


class OpenAIScriptAssistantProvider(ScriptAssistantProvider):
    def __init__(self, configuration, *, transport=None):
        self.configuration = configuration
        self.client = httpx.Client(
            base_url=configuration.base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(75.0, connect=10.0),
            transport=transport,
        )

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.configuration.get_api_key()}",
            "Content-Type": "application/json",
        }

    def generate_proposal(self, request_data):
        request_payload = dict(request_data) if isinstance(request_data, dict) else request_data
        user_id = request_payload.pop("_user_id", None) if isinstance(request_payload, dict) else None
        body = {
            "model": self.configuration.model,
            "instructions": SYSTEM_PROMPT,
            "input": json.dumps(request_payload, ensure_ascii=False, separators=(",", ":")),
            "max_output_tokens": self.configuration.max_output_tokens,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "hoertext_entwurf",
                    "strict": True,
                    "schema": SCRIPT_SCHEMA,
                }
            },
        }
        if user_id is not None:
            body["safety_identifier"] = hashlib.sha256(
                f"sprachplattform-user:{user_id}".encode("utf-8")
            ).hexdigest()
        try:
            response = self.client.post("responses", headers=self._headers(), json=body)
            response.raise_for_status()
            data = response.json()
            payload = json.loads(_extract_text(data))
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise AssistantProviderError("Der KI-Dienst ist derzeit nicht erreichbar. Bitte versuchen Sie es erneut.") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                message = "Der OpenAI-API-Schlüssel wurde nicht akzeptiert."
            elif status == 429:
                message = "Das OpenAI-Limit ist derzeit erreicht. Bitte versuchen Sie es später erneut."
            else:
                message = f"Der KI-Dienst konnte den Entwurf nicht erstellen (HTTP {status})."
            raise AssistantProviderError(message) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise AssistantProviderError("Die Antwort des KI-Dienstes konnte nicht verarbeitet werden.") from exc

        usage = data.get("usage") or {}
        return AssistantProviderResult(
            payload=payload,
            model=data.get("model") or self.configuration.model,
            response_id=data.get("id", ""),
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        )

    def test_connection(self):
        try:
            response = self.client.get(
                f"models/{self.configuration.model}",
                headers=self._headers(),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise AssistantProviderError("Der OpenAI-API-Schlüssel wurde nicht akzeptiert.") from exc
            raise AssistantProviderError(
                f"Die OpenAI-Verbindung konnte nicht geprüft werden (HTTP {exc.response.status_code})."
            ) from exc
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise AssistantProviderError("OpenAI ist derzeit nicht erreichbar.") from exc
        return True
