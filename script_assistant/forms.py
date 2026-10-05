from django import forms

from projects.models import Project


class AssistantBriefForm(forms.Form):
    FORMAT_CHOICES = (
        ("dialogue", "Dialog"),
        ("monologue", "Monolog"),
        ("interview", "Interview"),
        ("announcement", "Durchsage"),
        ("story", "Erzählung"),
    )
    SPEAKER_CHOICES = tuple((count, str(count)) for count in range(1, 5))
    ENGLISH_ACCENT_CHOICES = (
        ("unspecified", "Automatisch passend auswählen"),
        ("british", "Britisches Englisch"),
        ("american", "Amerikanisches Englisch"),
        ("australian", "Australisches Englisch"),
        ("irish", "Irisches Englisch"),
    )

    language = forms.ChoiceField(choices=Project.Language.choices, label="Zielsprache")
    english_accent = forms.ChoiceField(
        choices=ENGLISH_ACCENT_CHOICES,
        label="Englischer Akzent",
        initial="unspecified",
        required=False,
        help_text="Bei Englisch kann die Aussprache gezielt festgelegt werden.",
    )
    level = forms.ChoiceField(choices=[("", "Kein Sprachniveau vorgeben"), *Project.Level.choices], label="GER-Niveau (optional)", required=False)
    format = forms.ChoiceField(choices=FORMAT_CHOICES, label="Art des Hörtexts", initial="dialogue")
    topic = forms.CharField(
        label="Thema oder Situation",
        max_length=1_000,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Zum Beispiel: Zwei Freunde planen einen Kinobesuch."}
        ),
    )
    duration_seconds = forms.IntegerField(
        min_value=30,
        max_value=600,
        label="Ungefähre Länge",
        initial=60,
        widget=forms.NumberInput(attrs={"type": "range", "min": 30, "max": 600, "step": 15, "data-duration-slider": "true"}),
        help_text="30 Sekunden bis 10 Minuten in 15-Sekunden-Schritten. Die tatsächliche Audiodauer kann abweichen.",
    )
    speaker_count = forms.TypedChoiceField(
        choices=SPEAKER_CHOICES,
        coerce=int,
        label="Anzahl der Sprecher",
        initial=2,
    )
    vocabulary = forms.CharField(
        label="Gewünschter Wortschatz",
        max_length=1_000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optional: Wörter oder Wendungen"}),
    )
    grammar_focus = forms.CharField(
        label="Grammatikschwerpunkt",
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Optional, zum Beispiel: passé composé"}),
    )
    speaker_roles = forms.CharField(
        label="Rollen oder Sprecherwünsche",
        max_length=1_000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optional: Kundin und Verkäufer, zwei Jugendliche …"}),
    )
    voice_preferences = forms.CharField(
        label="Stimmenwünsche je Rolle (optional)",
        max_length=1_000,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Optional: Lehrerin erwachsen und ruhig; Schüler jugendlich und locker …",
            }
        ),
        help_text="Beschreiben Sie jede Stimme mit Rollenname oder Nummer, zum Beispiel: Rolle 1 / Lehrerin: erwachsen und ruhig; Rolle 2 / Schüler: jugendlich und locker. Die Reihenfolge gilt auch für die Stimmenauswahl.",
    )
    additional_instructions = forms.CharField(
        label="Was ist sonst noch wichtig?",
        max_length=2_000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional: Ton, Lernziel oder besondere Vorgaben"}),
    )

    def clean_duration_seconds(self):
        duration = self.cleaned_data["duration_seconds"]
        if duration % 15:
            raise forms.ValidationError("Wählen Sie die Länge in 15-Sekunden-Schritten.")
        return duration

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("format") == "monologue":
            cleaned["speaker_count"] = 1
        if cleaned.get("language") != Project.Language.EN:
            cleaned["english_accent"] = "unspecified"
        return cleaned


class AssistantRefinementForm(forms.Form):
    instruction = forms.CharField(
        label="Was soll geändert werden?",
        max_length=2_000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Zum Beispiel: Bitte etwas einfacher und mit mehr Alltagssprache.",
                "data-assistant-instruction": "true",
            }
        ),
    )


class AssistantRevisionForm(AssistantRefinementForm):
    pass
