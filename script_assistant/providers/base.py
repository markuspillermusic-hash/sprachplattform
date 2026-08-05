from abc import ABC, abstractmethod
from dataclasses import dataclass


class AssistantProviderError(RuntimeError):
    pass


class AssistantProviderNotConfigured(AssistantProviderError):
    pass


@dataclass(frozen=True)
class AssistantProviderResult:
    payload: dict
    model: str
    response_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class ScriptAssistantProvider(ABC):
    @abstractmethod
    def generate_proposal(self, request_data): ...

    @abstractmethod
    def test_connection(self): ...


def get_script_assistant_provider():
    from script_assistant.models import AssistantConfiguration

    from .openai import OpenAIScriptAssistantProvider

    configuration = AssistantConfiguration.objects.filter(active=True).order_by("pk").first()
    if not configuration or not configuration.is_configured:
        raise AssistantProviderNotConfigured(
            "Der KI-Assistent ist noch nicht eingerichtet. Ein Administrator kann den OpenAI-API-Schlüssel in der Verwaltung hinterlegen."
        )
    return OpenAIScriptAssistantProvider(configuration)
