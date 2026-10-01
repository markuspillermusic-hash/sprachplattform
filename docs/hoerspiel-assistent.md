# Integrierter Hörspiel-Assistent

Einstieg: **Meine Hörtexte → Hörspiel mit Assistent erstellen**, direkt unter `/produktion/neu/`. Für vorhandene Projekte führt der Skripteditor im Bereich Hörspiel-Produktion zum Assistenten. Lehrkräfte benötigen weder eine lokale KI-Installation noch einen Skill auf ihrem Gerät.

## Geführter Ablauf

1. Unterrichtsauftrag eingeben: Sprache, Niveau, Zielgruppe, Lernziel, Rollen, Dauer sowie Musik- und Geräuschwünsche. OpenAI erstellt einen Skriptentwurf. Das Projektskript bleibt bis zur Übernahme unverändert.
2. Entwurf direkt bearbeiten oder einen Änderungswunsch formulieren. Stimmen vorab im Skripteditor kontrollieren. **Skript freigeben und Hörtext erzeugen** übernimmt den Stand und erzeugt die Sprachfassung über ElevenLabs. **Nur Skript übernehmen** erzeugt kein Audio.
3. Sprachfassung anhören. **Hörtext freigeben und Klangplan vorbereiten** plant Musik und Geräusche anhand der tatsächlichen Audiodauer. Dieser Schritt erzeugt noch keine Musik und Geräusche.
4. Klangplan kontrollieren: Beschreibungen, vorhandene Audios, Start, Dauer, Lautstärke, Fades und Sprachkompression. Änderungen zunächst speichern und den aktualisierten Verbrauch prüfen. **Klangplan freigeben und Mischung erstellen** erzeugt fehlende Audios, ordnet alle Clips im Studio an und rendert eine Vorschau.
5. Mischung anhören. Bei Bedarf im bestehenden Studio schneiden, Fades und Lautstärken korrigieren, speichern und eine neue Vorschau rendern. **Mischung freigeben und final exportieren** erzeugt MP3 oder WAV ohne weitere Anbieter-Credits.

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

Neue Migrationen: `generation/0005`, `production/0001`. Lokale Prüfung: 200 Tests, darunter 21 neue Prüfungen für Freigaben, Rechte, Versionskonflikte, vollständige Audioverarbeitung, Teilfehler, Wiederverwendung, Kopien und Export. Browserprüfung bei 1440 und 390 Pixeln: keine JavaScript-Fehler oder horizontalen Überläufe.
