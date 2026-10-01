# Generierungsrahmen ab 1. Oktober 2026

Die persönlichen Kontingente erlauben großzügige Varianten und Korrekturen. Sie sind keine zusätzlichen Anbieter-Credits: Alle ElevenLabs-Aufträge teilen sich einen gemeinsamen Rahmen. Bestehende höhere persönliche Limits bleiben erhalten; absichtlich auf 0 gesetzte Funktionen bleiben gesperrt.

| Bereich | Persönliches Kontingent | Gemeinsame Grenze |
| --- | --- | --- |
| Sprache, Lehrkräfte und Administration | 100.000 Zeichen pro Kalendermonat | ElevenLabs-Credit-Rahmen |
| Musik | 30 Minuten pro Nutzer und Kalendermonat | ElevenLabs-Credit-Rahmen |
| Geräusche | 30 Minuten pro Nutzer und Kalendermonat | ElevenLabs-Credit-Rahmen |
| OpenAI-Assistent | 100 Anfragen pro Tag, 2 Mio. Eingabe- und 500.000 Ausgabetokens pro Kalendermonat | 100 USD Plattform-Jahresanteil, 5 % Reserve und dynamischer Monatsrahmen |
| Neue temporäre Schülerzugänge | 10.000 Sprachzeichen als Formularvorschlag, bis zu 50.000 wählbar; bei freigegebenem Assistenten 15 Anfragen, 200.000 Eingabe- und 50.000 Ausgabetokens | Persönliche Werte gelten für die gesamte Zugangslaufzeit; Anbieterrahmen gelten zusätzlich |

Der Besitzer nennt etwa 130.000 monatliche ElevenLabs-Credits. Die Plattform lässt nach 5 % Reserve 123.500 Credits zu und zählt reservierte sowie abgeschlossene Aufträge zusammen. Solange der genaue Erneuerungstag unbekannt ist, verwendet sie vorsichtig die letzten 31 Kalendertage. Ein bestätigter Erneuerungstag kann unter Anbieterbudgets eingetragen werden; 0 bedeutet gleitender Rahmen. Kurze Monate verwenden ihren letzten Tag. Credit-Rollover und außerhalb der Sprachplattform verbrauchte Credits werden nicht automatisch synchronisiert. Der vorhandene Schlüssel erlaubt derzeit keine Abonnementabfrage. [ElevenLabs-Abrechnung](https://elevenlabs.io/docs/overview/administration/billing).

Vor dem Anbieteraufruf werden Credits geschätzt und atomar reserviert. Sprache berücksichtigt die tatsächlich zu sendenden Teile inklusive Richtungs- und Akzenttags. Musik reserviert konservativ 1.500 Credits je Minute, Geräusche 20 Credits je Sekunde. Diese konfigurierbaren Werte sind interne Schätzungen; die Antwortdaten des Anbieters ersetzen sie, wenn ein `character-cost`-Header vorliegt. Die API-Hilfe nennt für zeitlich festgelegte Geräusche 20 Credits pro Sekunde; in den bisherigen Antworten dieses Kontos wurden 11 pro Sekunde gemeldet. [Sound-Effects-Abrechnung](https://help.elevenlabs.io/hc/en-us/articles/25735337678481-How-much-does-it-cost-to-generate-sound-effects), [API-Antwortheader](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert).

Die Studio-Tarifwerte werden aus der vorhandenen internen EUR-Schätzung pro 1.000 Credits abgeleitet. Bei 0,10 EUR sind das zunächst 0,15 EUR je Musikminute und 0,12 EUR je Geräuschminute. Sie dienen der internen Planung und sind keine behaupteten zusätzlichen Einzelabbuchungen. Musik- und Geräuscherzeugung werden mit dieser Konfiguration freigegeben.

Für OpenAI nennt der Besitzer insgesamt ungefähr 500 EUR für ein Jahr, gemeinsam mit anderen Anwendungen. Der vorläufige Plattformanteil beträgt bewusst 100 **USD**, passend zur vorhandenen Preiskonfiguration. Das ist keine 1:1-Umrechnung von Euro und keine Beanspruchung des gesamten gemeinsamen Guthabens. Nach Reserve bleiben 95 USD bis 30. September 2027; anfangs etwa 7,92 USD je Monat. Ungenutzte Mittel werden auf die verbleibenden Monate verteilt. Der Anteil ist unter Anbieterbudgets änderbar. Die zusätzlich möglichen 200 EUR sind noch nicht als aufgeladenes Guthaben eingerechnet; es findet kein automatischer Kauf statt.

`python manage.py configure_generous_limits` zeigt den konkreten Rahmen ohne Änderungen. `--apply` übernimmt ihn. Optional: `--elevenlabs-credits`, `--cycle-day` und `--openai-budget` (in der bereits konfigurierten OpenAI-Abrechnungswährung). Ein erneuter Aufruf erzeugt keine doppelten Budgets oder Nutzungsbuchungen. Die Organisationseinstellungen in der Serverumgebung müssen auf 2 Mio. beziehungsweise 24 Mio. Zeichen gesetzt werden. Die bestehenden technischen Grenzen für Audiodauer, Uploads und gleichzeitige Hintergrundaufträge bleiben bestehen.
