# Kontingente und Nutzungsmonitoring

Die Sprachplattform führt für OpenAI und ElevenLabs ein gemeinsames, internes Verbrauchsbuch. Vor jeder Anbieteranfrage wird das erwartete Budget reserviert. Nach der Antwort wird die Reservierung mit den tatsächlichen Tokens beziehungsweise den von ElevenLabs gemeldeten Credits abgeglichen. Nicht ausgeführte Anfragen werden freigegeben.

## Anbieterbudgets einrichten

In der Django-Verwaltung unter **Nutzung und Budgets → Anbieterbudgets** wird pro Anbieter ein Budget angelegt:

- **Guthaben für die Sprachplattform:** Nur der Anteil, der dieser Anwendung zur Verfügung steht. Wird das OpenAI-Konto auch von der PrüfungsAPP verwendet, darf hier nicht automatisch das vollständige OpenAI-Guthaben eingetragen werden.
- **Beginn und Ablaufdatum:** Der tatsächliche Gültigkeitszeitraum des gekauften Guthabens.
- **Sicherheitsreserve:** Standardmäßig werden zehn Prozent nicht für normale Nutzer freigegeben.
- **Dynamischer Monatsrahmen:** `verbleibendes freigegebenes Guthaben / verbleibende Monate`. Nicht genutztes Budget wird dadurch auf die Restlaufzeit verteilt.
- **Währung:** Muss zur Preiskonfiguration passen. ElevenLabs wird derzeit in EUR geschätzt; OpenAI verwendet die in der KI-Anbindung hinterlegte Währung.

Ohne aktives Anbieterbudget gelten weiterhin die individuellen Nutzerkontingente, aber kein geldbasierter Organisationsrahmen. Vor dem Livegang müssen deshalb beide Anbieterbudgets angelegt werden.

## Nutzerkontingente

Unter **Benutzer** stehen pro Konto folgende harte Grenzen zur Verfügung:

- ElevenLabs-Zeichen pro Kalendermonat
- OpenAI-Eingabetokens pro Kalendermonat
- OpenAI-Ausgabetokens pro Kalendermonat
- OpenAI-Anfragen pro Tag

Die Standardwerte können für einzelne Nutzer angepasst werden. Eine Anbieteranfrage wird nicht gestartet, wenn die Reservierung eine Grenze überschreiten würde.

## OpenAI-Preise

Unter **KI-Anbindung** werden zusätzlich zur Modellauswahl die Abrechnungswährung sowie Eingabe- und Ausgabepreis je eine Million Tokens gepflegt. Diese Werte müssen bei einer Preis- oder Modelländerung aktualisiert werden.

Für Sprachplattform und PrüfungsAPP sollen getrennte OpenAI-Projekte und getrennte API-Schlüssel verwendet werden. Dadurch bleiben Verbrauch und Sperrung je Anwendung nachvollziehbar, obwohl beide Projekte dasselbe Organisationsguthaben nutzen.

## Monitoring

Unter **Nutzung und Budgets → Verbrauchsbuchungen** zeigt die Verwaltung:

- Monatswerte je Benutzer,
- ElevenLabs-Zeichen und Credits,
- OpenAI-Eingabe- und Ausgabetokens,
- geschätzte beziehungsweise gemeldete Kosten,
- Reservierungen, gebuchte und freigegebene Anfragen,
- Provider-Request-IDs für den Abgleich,
- CSV-Export.

Die normalen Monitoring-Seiten zeigen bewusst keine Chatnachrichten oder vollständigen KI-Texte. Sie erfassen Nutzungsmetadaten, nicht die inhaltliche Arbeit der Lehrkräfte.
