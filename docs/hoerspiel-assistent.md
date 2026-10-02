# Integrierter Hörspiel-Assistent

Einstieg: **Startseite oder Meine Hörtexte → Hörspiel erstellen**, direkt unter `/produktion/neu/`. Hörtext und Hörspiel werden mit gleichwertigen Schaltflächen und kurzen Erklärungen angeboten. Für vorhandene Projekte führt der Skripteditor im Bereich Hörspiel-Produktion zum Assistenten. Lehrkräfte benötigen weder eine lokale KI-Installation noch einen Skill auf ihrem Gerät.

## Geführter Ablauf

1. Unterrichtsauftrag eingeben: Sprache, optionales Niveau, Zielgruppe, Lernziel, Rollen, Dauer sowie Musik- und Geräuschwünsche. Stimmen können vorab für die Rollen ausgewählt werden; ohne Auswahl erfolgt eine automatische Zuordnung. OpenAI erstellt einen Skriptentwurf. Das Projektskript bleibt bis zur Übernahme unverändert.
2. Entwurf und Stimmen direkt bearbeiten oder einen Änderungswunsch formulieren. **Skript und Stimmen im Editor bearbeiten** übernimmt den aktuellen Entwurf einschließlich eingetragener Änderungen und öffnet ihn im Editor, ohne Audio zu erzeugen. Dort geänderte Stimmen bleiben für folgende Entwürfe maßgeblich. **Skript freigeben und Hörtext erzeugen** übernimmt den Stand und erzeugt die Sprachfassung über ElevenLabs. **Nur Skript übernehmen** erzeugt kein Audio.
3. Sprachfassung anhören. **Hörtext freigeben und Klangplan vorbereiten** plant Musik und Geräusche anhand der tatsächlichen Audiodauer. Dieser Schritt erzeugt noch keine Musik und Geräusche.
4. Klangplan kontrollieren: Beschreibungen, vorhandene Audios, Start, Dauer, Lautstärke, Fades und Sprachkompression. Bestehende Elemente sind direkt zur Bearbeitung geöffnet. Für eine KI-Überarbeitung unten einen **Änderungswunsch an den Assistenten** eingeben und **Klangplan nach Änderungswunsch überarbeiten** wählen. Dabei werden direkte Änderungen zuerst gespeichert und als Grundlage übergeben; Musik- und Geräuschwünsche bleiben erhalten. Auch ein leerer Vorschlag kann ergänzt oder überarbeitet werden. Änderungen zunächst speichern und den aktualisierten Verbrauch prüfen. Erst **Klangplan freigeben und Mischung erstellen** erzeugt fehlende Audios, ordnet alle Clips im Studio an und rendert eine Vorschau.
5. Mischung anhören. Bei Bedarf im bestehenden Studio schneiden, Fades und Lautstärken korrigieren, speichern und eine neue Vorschau rendern. **Mischung freigeben und final exportieren** erzeugt MP3 oder WAV ohne weitere Anbieter-Credits.

Der optionale Zusatzblock für Musik und Geräusche bleibt leer, wenn kein weiteres Audio gewünscht ist. Ein neuer Eintrag beginnt mit Name, Beschreibung oder ausgewähltem Audio; Zeit- und Lautstärkewerte sind vorbelegt. Bei Feldfehlern oder unpassenden Fades bleiben alle Eingaben zur Korrektur erhalten. Ohne GER-Vorgabe bleibt das Niveau leer, auch im Skripteditor und bei späteren Vorschlägen.

Zwischenstände und Arbeitsschritte bleiben gespeichert. Seiten können während der Hintergrundverarbeitung verlassen werden. Ein Projekt lässt sich erst nach Abschluss laufender Aufträge kopieren oder löschen. Kopien übernehmen den verfügbaren Produktionsstand mit eigenen Audiodateien. Frühere Skriptübernahmen und Studioänderungen bleiben in ihren jeweiligen Historien erhalten.

## Grenzen und Kosten

- Dieselben verschlüsselten OpenAI- und ElevenLabs-Anbindungen und Budgetgrenzen wie im übrigen Werkzeug gelten. Es gibt keine neuen API-Schlüssel im Browser und keine Erhöhung der gemeinsam genutzten Budgets.
- Der angezeigte Sprachpreis ist ein oberer Tarifwert. Unveränderte verfügbare Sprachabschnitte derselben Modellfassung werden in eine neue Version kopiert; nur neue Abschnitte werden berechnet. Pausen und Tempo werden beim Zusammenfügen angewendet. Neue Stimmen oder Regieanweisungen benötigen neue Erzeugung.
- Vorhandene oder bereits erzeugte Musik und Geräusche werden wiederverwendet. Position, Fades, Lautstärke und Kompression benötigen keine erneute Anbieter-Erzeugung. Geänderte Erzeugungsbeschreibung, Dauer oder Loop-Einstellung können neue Credits verbrauchen.
- Höchstens zwölf Musik-/Geräuschelemente pro Klangplan, neue Musik 3–600 Sekunden, neue Geräusche 0,5–30 Sekunden; fertige Mischung höchstens 30 Minuten. Geräusche dürfen sich überlappen. Danach stehen die bestehenden Studiofunktionen zur Verfügung.
- Der Klangplan enthält Zeitvorschläge auf Grundlage von Skript und Gesamtdauer, keine erzwungene wortgenaue Synchronisierung. Geräuschzeitpunkte vor Verwendung anhören und bei Bedarf im Studio verschieben.
- Bei unklarem Anbieterfehler gibt es keinen automatischen kostenpflichtigen Wiederholungsversuch. Erfolgreiche Teilergebnisse bleiben verfügbar. Ein erneut gestarteter Auftrag kann weitere Credits verbrauchen.
- Die allgemeine Audioaufbewahrung gilt auch für Assistentenergebnisse. Abgelaufene Audios werden nicht als freigegeben oder wiederverwendbar behandelt.
- Arbeitsblätter sind kein Bestandteil dieser Umsetzung.

## Technik und Prüfung

`production/AGENT_GUIDE.md` ist die zentral gepflegte Produktionsanleitung für die KI-Aufträge. Der Server steuert die Phasen und Freigaben; OpenAI liefert ausschließlich strukturierte Skript- und Klangvorschläge. Keine frei ausführbaren Befehle, fremden Audiodateien oder Dateipfade aus Modellantworten werden akzeptiert.

`Production` speichert Briefing, Entwurf, Freigaben, Audioversion, Klangplan und Vorschau. `ProductionRun` protokolliert die einzelnen Hintergrundphasen; pro Projekt ist genau ein aktiver Assistentenauftrag zulässig. Versionsprüfungen erkennen parallele Änderungen. Skript- oder Stimmenänderungen sperren die weitere Nutzung einer alten Sprachfreigabe. Geänderte Studioschnitte erfordern eine aktuelle Vorschau vor dem Export.

Beim Klangplan-Auftrag bestätigt der Server die bereits geprüfte Sprachfreigabe ausdrücklich im `workflow_context`. Die Produktionsanleitung unterscheidet zwischen dem bearbeitbaren Planvorschlag und der späteren Freigabe zur Audioerzeugung. Frühere Planbeschreibungen bestimmen keine Freigaben. Ein überarbeiteter Klangplan hebt die bisherige Mix-Freigabe auf; bei einem fehlgeschlagenen KI-Auftrag bleiben die davor gespeicherten manuellen Änderungen erhalten.

Neue Migrationen: `generation/0005`, `production/0001`. Prüfung: 201 Tests im PostgreSQL-Produktionsimage, darunter 22 neue Prüfungen für Freigaben, Rechte, Versionskonflikte, vollständige Audioverarbeitung, Teilfehler, Wiederverwendung, Kopien und Export. Browserprüfung bei 1440 und 390 Pixeln: keine JavaScript-Fehler oder horizontalen Überläufe.

Öffentliche Abnahme am 1. Oktober 2026: authentifizierter Unterrichtsauftrag, echter OpenAI-Skriptentwurf, freigegebene ElevenLabs-Sprachfassung, echter OpenAI-Klangplan, generierter Drei-Sekunden-Jingle und Ein-Sekunden-Vogelruf, automatische Drei-Spur-MP3-Vorschau und heruntergeladener WAV-Export erfolgreich. Zusätzlich eine eigene neue Sprachversion aus vorhandenen Audioabschnitten über den öffentlichen Ablauf mit aktivem Credit-Budget erzeugt: kein neuer Anbieteraufruf und keine neue Verbrauchsbuchung. Tests mit ausgeschöpften Nutzer- und Credit-Grenzen bestätigen denselben kostenfreien Wiederverwendungsfall. Temporäre Abnahmeprojekte sind entfernt; echte Verbrauchsnachweise bleiben erhalten.

Korrekturabnahme am 2. Oktober 2026: 213 Tests im PostgreSQL-Produktionsimage erfolgreich. Im Browser gleichwertige Startoptionen, optionales Niveau, sprachkompatible Stimmenwahl, leerer Zusatzblock, Fehlerkorrektur ohne Textverlust, Speichern zusätzlicher Musik und geladener Entwurf im Editor geprüft. Die beiden Startaktionen sind bei 1366 × 768 sichtbar; bei 390 Pixeln gibt es keinen horizontalen Überlauf. Öffentlicher Test mit echtem OpenAI-Entwurf ohne GER-Vorgabe, explizit gewählter Stimme und Textänderung beim Editorwechsel erfolgreich. Auch die Klangplan-Korrekturen über die öffentliche Adresse bestätigt. Dafür wurde kein neuer ElevenLabs-Auftrag ausgelöst; die technische Formularprüfung verwendete eine unabhängige Demokopie. Abnahmeprojekt entfernt.
