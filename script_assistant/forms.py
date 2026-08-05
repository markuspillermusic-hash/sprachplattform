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
    DURATION_CHOICES = (
        (30, "etwa 30 Sekunden"),
        (60, "etwa 1 Minute"),
        (120, "etwa 2 Minuten"),
        (180, "etwa 3 Minuten"),
    )
    SPEAKER_CHOICES = tuple((count, str(count)) for count in range(1, 5))

    language = forms.ChoiceField(choices=Project.Language.choices, label="Zielsprache")
    level = forms.ChoiceField(choices=Project.Level.choices, label="GER-Niveau", initial=Project.Level.A2)
    format = forms.ChoiceField(choices=FORMAT_CHOICES, label="Art des Hörtexts", initial="dialogue")
    topic = forms.CharField(
        label="Thema oder Situation",
        max_length=1_000,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Zum Beispiel: Zwei Freunde planen einen Kinobesuch."}
        ),
    )
    duration_seconds = forms.TypedChoiceField(
        choices=DURATION_CHOICES,
        coerce=int,
        label="Ungefähre Länge",
        initial=60,
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
    additional_instructions = forms.CharField(
        label="Was ist sonst noch wichtig?",
        max_length=2_000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional: Ton, Lernziel oder besondere Vorgaben"}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("format") == "monologue":
            cleaned["speaker_count"] = 1
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
