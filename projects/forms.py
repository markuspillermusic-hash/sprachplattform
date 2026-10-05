from django import forms
from django.db.models import Case, IntegerField, Value, When
from django.db.models.functions import Lower

from tts.models import ProviderVoice, VoiceFavorite
from tts.widgets import VoiceSelect

from .models import Project, ScriptSegment, Speaker


def user_favorite_voice_ids(user):
    if not user or not user.is_authenticated:
        return set()
    return set(
        VoiceFavorite.objects.filter(
            user=user,
            voice__active=True,
        ).values_list("voice_id", flat=True)
    )


def voice_supports_language(voice, language):
    # Language metadata describes training/verification, not model capability.
    if voice.provider == "elevenlabs" and voice.model in {"eleven_v4", "eleven_v3"}:
        return language in Project.Language.values
    return not voice.languages or language in voice.languages


def compatible_voice_queryset(project, *, user=None, favorite_ids=None):
    active_voices = ProviderVoice.objects.filter(active=True).only("pk", "languages", "provider", "model")
    if project is None:
        queryset = ProviderVoice.objects.filter(active=True)
    else:
        compatible_ids = [
            voice.pk
            for voice in active_voices
            if voice_supports_language(voice, project.language)
        ]
        queryset = ProviderVoice.objects.filter(active=True, pk__in=compatible_ids)

    favorite_ids = set(
        user_favorite_voice_ids(user)
        if favorite_ids is None
        else favorite_ids
    )
    queryset = queryset.annotate(
        favorite_order=Case(
            When(pk__in=favorite_ids, then=Value(0)),
            default=Value(1), output_field=IntegerField(),
        )
    )
    if project is not None:
        preferred_ids = [voice.pk for voice in active_voices if project.language in voice.languages]
        queryset = queryset.annotate(
            language_order=Case(When(pk__in=preferred_ids, then=Value(0)), default=Value(1), output_field=IntegerField())
        ).order_by("favorite_order", "language_order", Lower("display_name"))
    else:
        queryset = queryset.order_by("favorite_order", Lower("display_name"))
    return queryset


class VoiceChoiceField(forms.ModelChoiceField):
    widget = VoiceSelect
    favorite_ids = frozenset()

    def label_from_instance(self, voice):
        prefix = "★ " if voice.pk in self.favorite_ids else ""
        return f"{prefix}{voice.display_name}"


class ProjectCreateForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("title", "language", "level")
        labels = {"title": "Titel", "language": "Zielsprache", "level": "GER-Niveau (optional)"}


class ProjectMetaForm(ProjectCreateForm):
    pass


class SpeakerForm(forms.ModelForm):
    voice = VoiceChoiceField(
        queryset=ProviderVoice.objects.none(),
        required=False,
        label="Freigegebene Stimme",
        empty_label="Noch keine Stimme",
    )

    class Meta:
        model = Speaker
        fields = ("name", "color", "accent")
        labels = {
            "name": "Sprechername",
            "color": "Farbe",
            "accent": "Akzentsteuerung",
        }
        help_texts = {
            "accent": "Optional: Verstärkt diesen Akzent zusätzlich zur gewählten Grundstimme.",
        }

    def __init__(
        self,
        *args,
        project=None,
        user=None,
        voice_queryset=None,
        favorite_ids=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.project = project or (self.instance.project if self.instance and self.instance.project_id else None)
        if self.project and self.project.language != Project.Language.EN:
            self.fields.pop("accent", None)
        favorite_ids = set(
            user_favorite_voice_ids(user)
            if favorite_ids is None
            else favorite_ids
        )
        self.fields["voice"].queryset = (
            voice_queryset
            if voice_queryset is not None
            else compatible_voice_queryset(
                self.project,
                user=user,
                favorite_ids=favorite_ids,
            )
        )
        self.fields["voice"].favorite_ids = favorite_ids
        self.fields["voice"].widget.attrs["data-voice-select"] = "true"
        if self.project:
            self.fields["voice"].widget.attrs["data-project-language"] = self.project.language
        if self.instance.pk and self.instance.voice_id:
            self.fields["voice"].initial = ProviderVoice.objects.filter(
                provider=self.instance.provider,
                model=self.instance.model,
                voice_id=self.instance.voice_id,
                active=True,
            ).first()

    def clean_voice(self):
        voice = self.cleaned_data["voice"]
        if voice and self.project and not voice_supports_language(voice, self.project.language):
            raise forms.ValidationError("Diese Stimme ist für die gewählte Zielsprache nicht freigegeben.")
        return voice

    def save(self, commit=True):
        instance = super().save(commit=False)
        voice = self.cleaned_data.get("voice")
        instance.provider = voice.provider if voice else ""
        instance.model = voice.model if voice else ""
        instance.voice_id = voice.voice_id if voice else ""
        if commit:
            instance.save()
        return instance


class SegmentForm(forms.ModelForm):
    class Meta:
        model = ScriptSegment
        fields = ("speaker", "text", "direction", "pause_after_ms", "speed")
        labels = {
            "speaker": "Sprecher",
            "text": "Sprechtext",
            "direction": "Regieanweisung (optional)",
            "pause_after_ms": "Pause danach (ms)",
            "speed": "Tempo",
        }
        widgets = {
            "text": forms.Textarea(attrs={"rows": 5, "maxlength": 4000}),
            "pause_after_ms": forms.NumberInput(attrs={"min": 0, "max": 5000, "step": 100}),
            "speed": forms.NumberInput(attrs={"min": 0.5, "max": 1.5, "step": 0.05}),
        }

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["speaker"].queryset = project.speakers.all()
        self.fields["text"].widget.attrs.update({"lang": project.language, "spellcheck": "true", "data-script-text": "true"})
