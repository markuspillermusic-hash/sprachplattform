from django import forms
from django.forms import formset_factory

from projects.models import Project
from .schema import PHASES, TASK_TYPES


class WorksheetBriefForm(forms.Form):
    target_group = forms.CharField(label="Klasse oder Zielgruppe", max_length=200,
                                  widget=forms.TextInput(attrs={"placeholder": "Zum Beispiel: Klasse 7"}))
    level = forms.ChoiceField(label="Schwierigkeitsniveau", choices=[("", "Am Hörtext orientieren"), *Project.Level.choices], required=False)
    learning_goal = forms.CharField(label="Lernziel (optional)", max_length=600, required=False,
                                    widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Zum Beispiel: wichtige Informationen gezielt heraushören"}))
    pages = forms.TypedChoiceField(label="Umfang", coerce=int, initial=2,
                                   choices=((1, "Kompakt · 3 Aufgaben"), (2, "Standard · 6 Aufgaben"), (3, "Ausführlich · 9 Aufgaben")),
                                   help_text="Etwa 1–3 Schülerseiten, abhängig von Textlänge und Antwortflächen. Lösungen sind separat.")
    instruction_language = forms.ChoiceField(label="Sprache der Aufgaben", initial="target",
                                             choices=(("target", "Sprache des Hörtexts"), ("de", "Deutsch")))
    focus = forms.MultipleChoiceField(label="Schwerpunkte", initial=["listening", "vocabulary", "transfer"],
        choices=(("listening", "Hörverstehen"), ("vocabulary", "Wortschatz"), ("grammar", "Grammatik"),
                 ("transfer", "Schreiben oder Sprechen")), widget=forms.CheckboxSelectMultiple)
    instructions = forms.CharField(label="Weitere Wünsche (optional)", max_length=1200, required=False,
                                    widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Zum Beispiel: überwiegend Auswahlaufgaben und ein kurzer Partnerdialog"}))


class WorksheetMetaForm(forms.Form):
    title = forms.CharField(label="Titel", max_length=160)
    introduction = forms.CharField(label="Einführung und Vorgehen", max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    learning_goal = forms.CharField(label="Lernziel auf dem Blatt", max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ExerciseForm(forms.Form):
    phase = forms.ChoiceField(label="Phase", choices=list(PHASES.items()))
    kind = forms.ChoiceField(label="Aufgabenart", choices=list(TASK_TYPES.items()))
    question = forms.CharField(label="Arbeitsauftrag", max_length=600, widget=forms.Textarea(attrs={"rows": 3, "spellcheck": "true"}))
    options = forms.CharField(label="Antwortoptionen", max_length=803, required=False, widget=forms.Textarea(attrs={"rows": 3}),
                             help_text="Eine Option pro Zeile. Offene Aufgaben bleiben hier leer.")
    answer_lines = forms.IntegerField(label="Antwortzeilen", min_value=1, max_value=5)
    answer = forms.CharField(label="Lösung oder Erwartungshorizont", max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))
    evidence = forms.CharField(label="Wörtlicher Beleg aus dem Skript", max_length=600, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    source_segments = forms.CharField(label="Beitragsnummern", max_length=60, required=False,
                                      help_text="Zum Beispiel: 2, 4. Hörverstehensaufgaben benötigen einen passenden Beleg.")

    def clean_options(self):
        return [line.strip() for line in self.cleaned_data["options"].splitlines() if line.strip()]

    def clean_source_segments(self):
        text = self.cleaned_data["source_segments"].strip()
        try:
            values = [int(value.strip()) for value in text.split(",") if value.strip()]
        except ValueError:
            raise forms.ValidationError("Bitte geben Sie Beitragsnummern durch Kommas getrennt ein.")
        return values


ExerciseForms = formset_factory(ExerciseForm, extra=0, min_num=3, max_num=9, validate_min=True, validate_max=True, absolute_max=9)


class RefinementForm(forms.Form):
    change_request = forms.CharField(label="Änderungswunsch an den Assistenten", max_length=1200,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Zum Beispiel: weniger Schreibaufgaben, mehr gezieltes Hörverstehen"}))
