# Klangqualität und verständliche Freigabe – 10. Oktober 2026

Anlass: Speichern in der Geräuschverwaltung führt zu einer schwer verständlichen Meldung; Außenatmosphären wirken für den Nutzer dumpf und wie in einem engen Raum. Die vorhandenen Quellen wurden technisch untersucht, nicht durch automatisierte Analyse akustisch freigegeben.

## Speicher- und Freigabeablauf

Die geöffnete Marktplatz-Seite enthielt nach einem abgelehnten Speicherversuch den Status „Freigegeben“ mit nicht gesetzter Bestätigung „Wiederholung akustisch geprüft“. Der gespeicherte Serverstatus war weiterhin „Entwurf“. Diese Kombination wird absichtlich abgelehnt. Die alte gemeinsame Fehlermeldung nannte zusätzlich Herkunft, obwohl diese bereits vorhanden war, und stand nur oberhalb des Formulars.

Die Validierung benennt jetzt das konkret fehlende Feld: fehlende Herkunft am Herkunftsfeld, fehlende Wiederholungsprüfung am Bestätigungsfeld. Der Hinweis erklärt auch, dass Status „Entwurf“ normales Metadatenspeichern erlaubt. Beide Felder erhalten verständliche Bedienhinweise; die Audioanzeige verlinkt direkt zur Hörprüfung und Freigabe. Es erfolgt keine automatische Klangfreigabe.

Regression: unverändertes Speichern und Pegeländerung funktionieren für Atmosphären und Einzelgeräusche jeweils als Entwurf und als freigegebene Quelle. Fehlende Prüfbestätigung verhindert weiterhin die Veröffentlichung; eine anschließend bewusst bestätigte Freigabe funktioniert. Keine zusätzliche Verbrauchsbuchung. Die 16 Bibliothekstests bestehen lokal.

Die Korrektur ist als Anwendungscode `03e708e` produktiv veröffentlicht. Dieselben 16 Tests bestehen im finalen Produktionsimage (50,672 Sekunden). Zusätzliche Prüfung mit den echten Servereinträgen: alle 16 unveränderten Adminformulare erfolgreich speicherbar; der Versuch erfolgt innerhalb einer anschließend zurückgenommenen Datenbanktransaktion, damit keine Metadaten, Nutzerfreigaben oder Adminprotokolle verändert bleiben. Keine neue Verbrauchsbuchung. Die neuen Hinweise und der direkte Hörprüflink wurden im angemeldeten Browser auf der öffentlichen Domain geprüft. Webdienst gesund und Worker antwortet mit `pong`; keine Schemaänderung erforderlich.

## Messung der vorhandenen Atmosphären

Verglichen wurden die echten 30-Sekunden-Anbieterquellen mit den FLAC-Mastern sowie den ersten 30 Sekunden der 120-Sekunden-Standardfassungen. Verfahren: FFmpeg-Decodierung in Stereo bei 44.100 Hz, 4.096 Samples je nicht überlappendem Hann-Fenster, gemittelte spektrale Energie beider Kanäle. Die angegebenen Prozentwerte sind relative Signalenergie in 20–20.000 Hz und keine wahrgenommene Lautheit oder Qualitätsnote.

| Quelle | 20–250 Hz | 250–2.000 Hz | 2.000–8.000 Hz | 8.000–20.000 Hz |
|---|---:|---:|---:|---:|
| Bahnhof | 98,235 % | 1,738 % | 0,024 % | 0,003 % |
| Marktplatz | 49,120 % | 48,408 % | 2,142 % | 0,330 % |
| Straße | 31,512 % | 66,751 % | 1,717 % | 0,020 % |
| Café | 25,246 % | 72,921 % | 1,570 % | 0,263 % |
| Sommernacht | 0,121 % | 0,152 % | 1,357 % | 98,370 % |
| Wald | 3,185 % | 11,411 % | 43,985 % | 41,419 % |
| Wind | 0,235 % | 5,226 % | 56,607 % | 37,932 % |
| Pausenhof | 1,116 % | 89,049 % | 9,650 % | 0,186 % |

Bei allen acht Quellen ist die Korrelation zwischen decodiertem Original und pegelangepasstem Master auf acht Nachkommastellen 1,00000000. Die relativen Bandanteile bleiben im Master innerhalb der Rundungsauflösung von 0,0001 dB gleich. Die erneute MP3-Codierung der Standardfassung verändert die vier Bandanteile um höchstens etwa 0,43 dB. Die Verarbeitung fügt keinen Raumhall und keinen EQ hinzu; sie passt den Pegel an, wiederholt decodierte Samples und codiert die Standardfassung.

Der Bahnhof ist bereits in der Anbieterquelle extrem basslastig; 98,235 % der gemessenen Energie liegen unter 250 Hz. Das stützt den beschriebenen dumpfen Eindruck, beweist aber weder einen konkreten Raum noch dessen Reflexionen. Wald und Wind besitzen dagegen ausgeprägte Höhenanteile. Eine pauschale Höhenanhebung aller 16 Klänge wäre daher ungeeignet.

Der Bahnhof-Prompt fordert „soft distant stationary train hum“ und nennt keine räumliche Geometrie. Viele weitere Prompts verwenden „soft“, „distant“ und „underneath spoken dialogue“. Das kann gedämpfte, unspezifische Texturen begünstigen; es ist eine plausible Interpretation der Ergebnisse, keine kontrolliert bewiesene Modellursache. Das Erzeugen eines zu dunklen Klanges ist nicht notwendig, um Sprache später gut verständlich darüber zu mischen: Dafür gibt es Clippegel, Fades und Ducking.

Anbieterquellen werden aktuell als `mp3_44100_128` angefordert. Die lokale 192-kbit/s-Fassung oder der FLAC-Master stellt darin verlorene Information nicht wieder her. Eine künftig direkt höherwertige Quelle kann Codierungsartefakte reduzieren, behebt aber keine falsch erzeugte Raumakustik.

## Aktuell belegte Modelloptionen

- **ElevenLabs:** Die [offizielle Sound-Effects-API](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert) nennt derzeit ausschließlich `eleven_text_to_sound_v2`, höchstens 30 Sekunden und den Loop-Parameter. Ein Sound Effects v3 oder konkreter baldiger Veröffentlichungstermin ist dort nicht belegt. Sprachmodell-Versionen und Music-Versionen sind davon getrennt.
- **Stable Audio 3.0:** Eine bereits verfügbare alternative Modellfamilie, keine neue ElevenLabs-Version. Stability nennt [3.0 Small SFX für Soundeffekte und 3.0 Large über die API](https://stability.ai/news-updates/meet-stable-audio-3-the-model-family-built-for-artistic-experimentation-with-open-weight-models). Die [Promptanleitung](https://stability.ai/guides/stable-audio-3-prompt-guide) behandelt Geräuschquelle, Aktion, Mikrofonposition und Raumcharakter sowie längere Ausgaben und Continuation. Ob diese Modelle die gewünschten Außenräume überzeugender treffen, ist durch einen Hörvergleich zu klären.
- **Adobe Firefly:** [Generate sound effects](https://helpx.adobe.com/sg/firefly/web/work-with-audio-and-video/work-with-audio/text-to-sound-effects.html) unterstützt Geräusche und Atmosphären. Eine weitere Vergleichsoption; ein besseres konkretes Ergebnis oder bereits vorhandene Plattformanbindung wird damit nicht behauptet.

## Empfohlener nächster Qualitätsversuch

Zunächst einen problematischen Schauplatz vergleichen, statt alle 16 Quellen neu zu erzeugen. „Offener Bahnsteig“ und „große Bahnhofshalle“ erhalten getrennte Szenenbeschreibungen: Ein Außenbahnsteig benötigt plausibel freie Ausbreitung und wenige diskrete entfernte Reflexionen; eine Halle kann weiten Nachhall besitzen. Mehr Hall allein macht einen Außenraum nicht automatisch richtig.

Vorschlag für einen offenen Bahnsteig:

> Natural stereo field recording on a broad open-air railway platform, open sky and tracks extending into the distance. Airy outdoor spatial perspective, distinct footsteps at varying distances, subtle rail hiss and occasional distant mechanical detail. Balanced spectrum, restrained low-frequency rumble, sparse distant reflections from platform structures, no enclosed-room resonance. No music, no intelligible announcements. Seamless steady ambience.

Vorschlag für eine große Bahnhofshalle:

> Natural stereo ambience inside a vast high-roof railway concourse. Spacious long diffuse reverberation, scattered footsteps and distant indistinct people, clear small transient details over restrained distant rail activity. Broad spectral balance, no close boxy room sound or dominant bass drone. No music, no intelligible announcements. Seamless steady ambience.

Diese Vorschläge beschreiben Alternativen, die zunächst erzeugt und angehört werden müssten. Kein bestehender Prompt oder Klang wurde stillschweigend ersetzt. Höhere Prompttreue bei ElevenLabs kann als separater Versuchsparameter dienen; mehr Details oder ein höherer Wert garantieren kein besseres Ergebnis.

Vergleich bei gleichem wahrgenommenem Pegel, einmal allein und einmal über demselben Dialog. Entscheidend sind räumliche Plausibilität, spektrale Balance, natürliche Ereignisdetails, störende Sprache/Musik und Wiederholungsübergänge. Erst den Gewinner als neue Version importieren und auf der bestehenden Hörprüfseite freigeben. Extern erzeugte oder passend lizenzierte Aufnahmen können schon über den vorhandenen Quelldatei-Upload übernommen werden; der gemeinsame Katalog ist nicht auf ElevenLabs-Dateien beschränkt.

In dieser Untersuchung wurden keine neuen kostenpflichtigen Sounds erzeugt, keine vorhandenen Audiodateien verändert und keine Nutzerfreigaben geändert.
