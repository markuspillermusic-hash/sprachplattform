from abc import ABC, abstractmethod


class AssistantProviderNotConfigured(RuntimeError):
    pass


class ScriptAssistantProvider(ABC):
    @abstractmethod
    def generate_proposal(self, request_data): ...


def get_script_assistant_provider():
    raise AssistantProviderNotConfigured(
        "Für den KI-Assistenten wurde bewusst noch kein LLM-Anbieter ausgewählt."
    )

