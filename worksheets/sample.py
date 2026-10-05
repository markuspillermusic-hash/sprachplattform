from .models import Worksheet

SOURCE = {"title": "Am Bahnhof", "language": "de", "level": "A2", "segments": [
    {"speaker": "Lena", "text": "Guten Morgen! Ich möchte eine Fahrkarte nach Hamburg."},
    {"speaker": "Mitarbeiter", "text": "Der nächste Zug fährt um 10:15 Uhr von Gleis 3."},
    {"speaker": "Lena", "text": "Was kostet die Fahrkarte?"},
    {"speaker": "Mitarbeiter", "text": "Die Fahrkarte kostet zwölf Euro. Sie können mit Karte bezahlen."},
    {"speaker": "Lena", "text": "Danke. Kann ich auch eine Rückfahrkarte kaufen?"},
    {"speaker": "Mitarbeiter", "text": "Ja. Der letzte Zug zurück fährt um 18:40 Uhr."},
]}
BRIEF = {"target_group": "Klasse 7", "level": "A2", "pages": 2, "instruction_language": "de",
         "focus": ["listening", "vocabulary", "transfer"], "learning_goal": "Reiseinformationen verstehen", "instructions": ""}


def task(phase, question, answer, *, kind="open", options=None, evidence="", refs=None, lines=2):
    return {"phase": phase, "kind": kind, "question": question, "options": options or [], "answer": answer,
            "evidence": evidence, "source_segments": refs or [], "answer_lines": lines}


PAYLOAD = {"title": "Am Bahnhof · Gut zuhören, sicher ankommen",
    "introduction": "Lies zuerst die Aufgaben. Höre den Dialog zweimal: zuerst für einen Überblick, danach für die Einzelheiten.",
    "learning_goal": "Du kannst wichtige Informationen zu einer Zugfahrt gezielt heraushören.",
    "exercises": [
        task("before", "Welche Informationen brauchst du, wenn du mit dem Zug fahren möchtest? Notiere zwei Fragen.",
             "Individuelle Antworten. Beispiel: Wann fährt der Zug? Wie viel kostet die Fahrkarte?"),
        task("while", "Wohin möchte Lena fahren? Kreuze die passende Antwort an.", "Nach Hamburg", kind="choice",
             options=["Nach Berlin", "Nach Hamburg", "Nach Köln"], evidence="Ich möchte eine Fahrkarte nach Hamburg.", refs=[1]),
        task("while", "Wann fährt der nächste Zug und von welchem Gleis?", "Um 10:15 Uhr von Gleis 3.",
             evidence="Der nächste Zug fährt um 10:15 Uhr von Gleis 3.", refs=[2]),
        task("while", "Wie viel kostet die Fahrkarte?", "Zwölf Euro.", evidence="Die Fahrkarte kostet zwölf Euro.", refs=[4]),
        task("while", "Lena kann mit Karte bezahlen. Richtig oder falsch?", "Richtig", kind="true_false", options=["Richtig", "Falsch"],
             evidence="Sie können mit Karte bezahlen.", refs=[4]),
        task("after", "Spielt zu zweit einen kurzen Dialog am Fahrkartenschalter. Fragt nach Ziel, Abfahrt und Preis. Verwendet eigene Reiseangaben.",
             "Individuelle Dialoge. Beispiel: Ich möchte nach Köln. Wann fährt der Zug? Um 14 Uhr. Was kostet die Fahrkarte? Zehn Euro.", lines=4),
    ]}


def sample_worksheet():
    return Worksheet(status="ready", source=SOURCE, brief=BRIEF, payload=PAYLOAD)
