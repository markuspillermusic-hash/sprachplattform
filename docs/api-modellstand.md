# API-Modellstand · 1. Oktober 2026

| Funktion | Aktuelle Plattformwahl | Aktualisierung |
| --- | --- | --- |
| Textentwürfe, sparsam | `gpt-6-luna` | Bereits aktuell, bleibt Standard |
| Textentwürfe, höhere Qualität | `gpt-6.1-sol` | Ersetzt vorhandenes `gpt-6-sol`; Vorgänger bleibt auswählbar |
| Sprache und Dialog | `eleven_v4` | Ersetzt `eleven_v3`; Vorgänger bleibt auswählbar |
| Instrumentalmusik | `music_v2_5` | Ersetzt v1/v2 als aktuelle Wahl |
| Geräusche | `eleven_text_to_sound_v2` | Bereits aktuell |

OpenAI verwendet weiterhin die Responses API mit striktem JSON-Schema und ohne Antwortspeicherung. Der höhere Qualitätsmodus benötigt mindestens `reasoning.effort=low`. Die Standardpreise je Million Tokens betragen 0,10/0,50 USD für Luna und 2/10 USD für GPT-6.1 Sol. Die sparsame Standardwahl und das geteilte Jahresbudget bleiben erhalten; Astra wird wegen des anderen Kostenprofils nicht automatisch aktiviert.

Eleven v4 ist für den bestehenden Text-to-Dialogue-Endpunkt verfügbar und hat laut echter Modellabfrage denselben Credit-Faktor 1 wie v3. Die Plattform behält vorsichtig maximal 2.000 gesendete Zeichen pro Dialoganfrage bei, da dies die Dialog-API für zuverlässige Generierung empfiehlt. Die größere Modellgrenze für reine TTS-Anfragen wird nicht ungeprüft auf Dialoge übertragen. Bei v4 sind vorherige Request-IDs zur Fortsetzung zugelassen, bei v3 bleiben sie ausgenommen.

Die Migration übernimmt den vorhandenen Stimmenkatalog einschließlich Freigaben, Sprachen, Kuratierung und Favoriten auf v4. Bearbeitbare Sprecherzuordnungen erhalten dieselben Voice-IDs mit dem neuen Modell. Historische Versionen, Aufträge und Verbrauchsbuchungen werden nicht umgeschrieben. Wiederholungen alter Sprachaufträge benutzen ausdrücklich deren ursprüngliches Modell mit dem aktuellen Zugang. Musikaufträge enthalten ihr Modell bereits im unveränderlichen Auftrag.

Für Music v2.5 nutzt die API `output_format=auto`, damit sie die passende MP3-Qualität liefert; die lokale Audioverarbeitung bleibt kompatibel. Keine automatische Zweitanfrage bei Anbieterfehlern. Bereits generierte Hörtexte und Demos bleiben erhalten und werden nicht kostenpflichtig neu erzeugt.

Vor der Umstellung wurden die echten Schlüssel durch Modellabfragen geprüft und je ein kurzer Auftrag mit Eleven v4, Music v2.5 und GPT-6.1 Sol erfolgreich ausgeführt. Audio wurde mit ffprobe überprüft und die Textantwort gegen das Plattform-Schema validiert. Die Testnutzung ist im normalen Verbrauchsprotokoll gebucht. Diese technische Prüfung ersetzt keinen umfangreichen Hörvergleich aller Sprachen und Stimmen.

Die administrative ElevenLabs-Verbindungsprüfung fragt ausschließlich `/v1/models` ab und kontrolliert das gewählte Sprachmodell. Sie benötigt keine Kontostimmen-Leseberechtigung und erzeugt kein Audio. Der bestehende Produktionsschlüssel erlaubt die echten Generierungsaufrufe und Modellabfragen, lehnt `/v2/voices` jedoch mit HTTP 401 ab. Ein künftiger Kontostimmen-Import benötigt weiterhin die entsprechende Berechtigung. Die Modellprüfung allein bestätigt keine Schreibberechtigung; dafür wurden die kurzen echten Aufträge ausgeführt.

Serverabnahme: 167 Tests im Produktionsimage bestanden; nach Anpassung der Verbindungsprüfung alle 53 betroffenen Tests erneut lokal und auf PostgreSQL bestanden. Migrationen angewendet, Web/Worker neu gestartet und öffentliche Plattform geprüft: zwei v4-Sprachabschnitte mit Request-Fortsetzung und MP3-Download, v2.5-Musik mit automatischem Ausgabeformat sowie ein neuer v2-Geräuscheffekt. Alle drei Spuren wurden mit feinem Clippegel und Fades als WAV exportiert und heruntergeladen. Die 260 Stimmen (81 freigegeben) bleiben verfügbar; Budgetrahmen bleiben unverändert. Temporäre Testprojekte und Audiodateien wurden entfernt, die API-Verbrauchsbuchungen bleiben bestehen. Der öffentliche Adminbereich bleibt durch Cloudflare Access geschützt; seine Modellfelder wurden zusätzlich über den authentifizierten Serverclient geprüft.

Quellen:

- [OpenAI: Modelle](https://developers.openai.com/api/docs/models)
- [OpenAI: GPT-6.1 Sol und Standardpreise](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [OpenAI: Migration der GPT-6-Familie](https://developers.openai.com/api/docs/guides/latest-model)
- [ElevenLabs: Einführung von Eleven v4 am 28. September 2026](https://elevenlabs.io/docs/changelog/2026/9/28)
- [ElevenLabs: Text to Dialogue](https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue)
- [ElevenLabs: Dialog-API und empfohlene Anfragegröße](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert)
- [ElevenLabs: Musik und Music v2.5](https://elevenlabs.io/docs/overview/capabilities/music)
- [ElevenLabs: Musik-API und Ausgabeformat](https://elevenlabs.io/docs/api-reference/music/compose)
- [ElevenLabs: Geräusch-API](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert)
