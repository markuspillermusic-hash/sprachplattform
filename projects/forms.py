from django import forms

from tts.models import ProviderVoice

from .models import Project, ScriptSegment, Speaker


def compatible_voice_queryset(project):
    active_voices = ProviderVoice.objects.filter(active=True).only("pk", "languages")
    if project is None:
        return ProviderVoice.objects.filter(active=True)
    compatible_ids = [
        voice.pk
        for voice in active_voices
        if not voice.languages or project.language in voice.languages
    ]
    return ProviderVoice.objects.filter(active=True, pk__in=compatible_ids)


class ProjectCreateForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("title", "language", "level")
        labels = {"title": "Titel", "language": "Zielsprache", "level": "GER-Niveau (optional)"}


class ProjectMetaForm(ProjectCreateForm):
    pass


class SpeakerForm(forms.ModelForm):
    voice = forms.ModelChoiceField(
        queryset=ProviderVoice.objects.none(),
        required=False,
        label="Freigegebene Stimme",
        empty_label="Noch keine Stimme",
    )

    class Meta:
        model = Speaker
        fields = ("name", "color")
        labels = {"name": "Sprechername", "color": "Farbe"}

    def __init__(self, *args, project=None, voice_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project or (self.instance.project if self.instance and self.instance.project_id else None)
        self.fields["voice"].queryset = (
            voice_queryset if voice_queryset is not None else compatible_voice_queryset(self.project)
        )
        self.fields["voice"].widget.attrs["data-voice-select"] = "true"
        if self.instance.pk and self.instance.voice_id:
            self.fields["voice"].initial = ProviderVoice.objects.filter(
                provider=self.instance.provider,
                model=self.instance.model,
                voice_id=self.instance.voice_id,
                active=True,
            ).first()

    def clean_voice(self):
        voice = self.cleaned_data["voice"]
        if voice and self.project and voice.languages and self.project.language not in voice.languages:
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
            "direction": "Regieanweisung",
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
