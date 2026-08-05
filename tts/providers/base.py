from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


class ProviderError(Exception):
    """Safe provider error whose message may be shown to administrators."""


class ProviderTemporaryError(ProviderError):
    pass


class ProviderConfigurationError(ProviderError):
    pass


@dataclass(frozen=True)
class DialogueInput:
    text: str
    voice_id: str
    direction: str = ""
    pause_after_ms: int = 0


@dataclass(frozen=True)
class VoiceInfo:
    voice_id: str
    name: str
    languages: tuple[str, ...] = ()
    labels: dict = field(default_factory=dict)
    preview_url: str = ""


@dataclass(frozen=True)
class UsageEstimate:
    characters: int
    estimated_cost_eur: Decimal


@dataclass(frozen=True)
class SynthesisResult:
    audio: bytes
    content_type: str
    provider_request_id: str = ""
    provider_credit_count: Decimal | None = None


class TTSProvider(ABC):
    @abstractmethod
    def list_voices(self, language: str | None = None): ...

    @abstractmethod
    def estimate_usage(self, script): ...

    @abstractmethod
    def synthesize_dialogue(self, script, options=None): ...

    @abstractmethod
    def get_job_result(self, provider_job_id): ...
