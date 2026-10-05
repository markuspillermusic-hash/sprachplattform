import json

from django import forms
from django.forms import formset_factory

from projects.models import ScriptSegment
from projects.forms import VoiceChoiceField, compatible_voice_queryset, user_favorite_voice_ids
from script_assistant.forms import AssistantBriefForm
from tts.models import ProviderVoice


class VoiceLanguageSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if getattr(value, "instance", None) is not None:
            option["attrs"]["data-languages"] = json.dumps(value.instance.languages)
        return option


class ProductionBriefForm(AssistantBriefForm):
    target_group = forms.CharField(label="Klasse oder Zielgruppe", max_length=300,
                                  widget=forms.TextInput(attrs={"placeholder": "Zum Beispiel: Klasse 7"}))
    learning_goal = forms.CharField(label="Lernziel", max_length=1000, required=False,
                                   widget=forms.Textarea(attrs={"rows": 2}))
    music_wishes = forms.CharField(label="Musikwünsche", max_length=2000, required=False,
                                  widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Zum Beispiel: kurzer Jingle, danach ruhige Klaviermusik"}))
    effects_wishes = forms.CharField(label="Geräusche und Atmosphäre", max_length=2000, required=False,
                                    widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Zum Beispiel: Bahnhofsatmosphäre und eine Tür am Anfang"}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["duration_seconds"].initial = 120
        favorites = user_favorite_voice_ids(user)
        voices = compatible_voice_queryset(None, favorite_ids=favorites)
        for index in range(1, 5):
            field = VoiceChoiceField(queryset=voices, required=False, label=f"Stimme für Rolle {index}", empty_label="Automatisch passend auswählen", widget=VoiceLanguageSelect)
            field.favorite_ids = favorites
            self.fields[f"voice_{index}"] = field

    def clean(self):
        cleaned = super().clean()
        for index in range(1, 5):
            field = f"voice_{index}"
            voice = cleaned.get(field)
            if index > cleaned.get("speaker_count", 0):
                cleaned[field] = None
            elif voice and voice.languages and cleaned.get("language") not in voice.languages:
                self.add_error(field, "Diese Stimme ist für die gewählte Zielsprache nicht freigegeben.")
        return cleaned


class SpeakerVoiceForm(forms.Form):
    name = forms.CharField(widget=forms.HiddenInput)
    voice = VoiceChoiceField(queryset=ProviderVoice.objects.none(),
                             required=False, label="Stimme", empty_label="Automatisch passend auswählen")

    def __init__(self, *args, project, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        favorites = user_favorite_voice_ids(user)
        self.fields["voice"].queryset = compatible_voice_queryset(project, favorite_ids=favorites)
        self.fields["voice"].favorite_ids = favorites


SpeakerVoices = formset_factory(SpeakerVoiceForm, extra=0, max_num=10, validate_max=True, absolute_max=10)


class ScriptLineForm(forms.Form):
    speaker = forms.ChoiceField(label="Rolle")
    text = forms.CharField(label="Sprechtext", max_length=4000, widget=forms.Textarea(attrs={"rows": 3}))
    direction = forms.ChoiceField(label="Regieanweisung (optional)", choices=ScriptSegment.Direction.choices, required=False, initial="")
    pause_after_ms = forms.IntegerField(label="Pause danach (ms)", min_value=0, max_value=5000, initial=500)
    speed = forms.DecimalField(label="Tempo", min_value=.5, max_value=1.5, decimal_places=2, initial=1)

    def __init__(self, *args, speaker_names, language="de", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["speaker"].choices = [(name, name) for name in speaker_names]
        self.fields["text"].widget.attrs.update({"lang": language, "spellcheck": "true", "data-script-text": "true"})


ScriptLines = formset_factory(ScriptLineForm, extra=0, max_num=500, validate_max=True, absolute_max=500)


class WishesForm(forms.Form):
    music_wishes = forms.CharField(label="Musikwünsche", max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    effects_wishes = forms.CharField(label="Geräusche und Atmosphäre", max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    instruction = forms.CharField(label="Was soll sich ändern?", max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 2}))


class PlanSettingsForm(forms.Form):
    summary = forms.CharField(label="Gestaltung", max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    speech_start = forms.FloatField(label="Sprache beginnt bei (Sekunden)", min_value=0, max_value=30)
    music_duck_db = forms.FloatField(label="Musikabsenkung bei Sprache (dB)", min_value=0, max_value=8)
    compression = forms.FloatField(label="Sprachkompression (0–100)", min_value=0, max_value=100)


class PlanRefinementForm(forms.Form):
    instruction = forms.CharField(label="Änderungswunsch an den Assistenten", max_length=2000, required=False,
                                  widget=forms.Textarea(attrs={"id": "plan-change", "rows": 2, "placeholder": "Zum Beispiel: kürzerer Jingle, leisere Hintergrundmusik und Regen ab der zweiten Szene."}))


class PlanItemForm(forms.Form):
    title = forms.CharField(label="Name", max_length=120)
    kind = forms.ChoiceField(label="Audioart", choices=[("music", "Musik"), ("effects", "Geräusch")])
    asset_id = forms.ChoiceField(label="Vorhandenes Audio", required=False)
    prompt = forms.CharField(label="Beschreibung für neue Erzeugung", max_length=4100, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    duration = forms.FloatField(label="Dauer (Sekunden)", min_value=.01, max_value=1800)
    start = forms.FloatField(label="Start (Sekunden)", min_value=0, max_value=1800)
    gain_db = forms.FloatField(label="Lautstärke (dB)", min_value=-60, max_value=12)
    fade_in = forms.FloatField(label="Einblenden (Sekunden)", min_value=0, max_value=30)
    fade_out = forms.FloatField(label="Ausblenden (Sekunden)", min_value=0, max_value=30)
    loop = forms.BooleanField(label="Nahtlose Geräuschschleife", required=False)

    def __init__(self, *args, assets, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_id"].choices = [("", "Neues Audio erzeugen")] + [(str(a.pk), a.title) for a in assets]
        if self.empty_permitted:
            self.initial = {"kind": "music", "duration": 15, "start": 0, "gain_db": -18, "fade_in": 0, "fade_out": 0, **self.initial}

    def has_changed(self):
        # The browser submits default choices even inside a closed optional row.
        # Only a name, generation description or selected audio starts a new row.
        if self.empty_permitted and self.is_bound and not any(
                str(self.data.get(self.add_prefix(key), "")).strip() for key in ("title", "prompt", "asset_id")):
            return False
        return super().has_changed()


PlanItems = formset_factory(PlanItemForm, extra=1, can_delete=True, max_num=12, validate_max=True, absolute_max=13)
