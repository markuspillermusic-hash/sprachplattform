import json

from django import forms


class VoiceSelect(forms.Select):
    """Keep a native select while exposing metadata to the shared voice search."""

    def __init__(self, attrs=None, choices=()):
        super().__init__({"data-voice-select": "true", "data-voice-picker": "true", **(attrs or {})}, choices)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        voice = getattr(value, "instance", None)
        if voice is not None:
            option["attrs"].update({
                "data-languages": json.dumps(voice.languages),
                "data-gender": voice.labels.get("gender", ""),
                "data-age": voice.labels.get("age", ""),
                "data-favorite": "true" if str(label).startswith("★ ") else "false",
                "data-search": " ".join([voice.display_name, *(str(v) for v in voice.labels.values())]),
            })
        return option
