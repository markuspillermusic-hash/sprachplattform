# Optionale Hörspiel-Produktion mit drei Spuren

Unter **Meine Hörtexte** auf der gewünschten Hörtext-Karte **Hörspiel-Studio öffnen** wählen. Derselbe Einstieg steht auch oben im Skripteditor; der Bereich **Optional: Hörspiel-Produktion** unter der Audioausgabe enthält weitere Hinweise. Reine Sprachaufnahmen werden weiterhin über die normale Audioausgabe erzeugt und heruntergeladen; das Studio ist ein zusätzliches Werkzeug.

Admins sehen unter **Meine Hörtexte** zunächst ihre eigenen Hörtexte ohne Demos. Mit **Hörtexte von** lassen sich alle Nutzer, andere Nutzer oder ein einzelner Nutzer auswählen. Unter **Demos** können diese ausgeblendet, mit angezeigt oder allein angezeigt werden. **Filter anwenden** übernimmt die Auswahl; **Zurücksetzen** führt zur Standardansicht zurück. Die Hörtext-Karten zeigen für Admins den Besitzer. Normale Nutzer sehen weiterhin ihre eigenen Hörtexte einschließlich ihrer Demos.

## Hörspiel-Demo

**Das Geheimnis der alten Uhr** ist eine kurze, fertig gemischte Szene mit sechs Sprachabschnitten, Jingle und Hintergrundmusik sowie Uhrticken, Glockenschlag und einer knarrenden Tür. Unter **Meine Hörtexte → Hörspiel ausprobieren** lässt sich der Mix direkt anhören und die persönliche Demo im Studio öffnen. Dieser Einstieg bleibt auch für Admins mit ausgeblendeten Demos sichtbar. Die vorbereiteten Clips zeigen Fades, überlappende Geräusche, Musikabsenkung und Sprachkompression.

Die Referenzaufnahmen werden einmal erzeugt und unter `AUDIO_STORAGE_ROOT/demos/clockwork-v1/` aufbewahrt. `python manage.py seed_audio_drama_demo` mischt die vorbereiteten Referenzen einmal und verteilt unabhängige Dateikopien und Bearbeitungsstände an aktive Konten. Dieser Befehl und die automatische Bereitstellung beim ersten Besuch neuer Nutzer lösen keine Anbieteraufrufe aus. Bereits bearbeitete Demos bleiben erhalten; bewusst gelöschte Demos werden nur mit der ausdrücklichen Option `--restore` neu angelegt.

Die unveränderten Demo-Hörbeispiele bleiben dauerhaft verfügbar. Eigene Uploads, zusätzliche generierte Dateien und neue Exporte unterliegen weiterhin der normalen Aufbewahrungsfrist. Die Referenzdateien gehören in die Sicherung des Audio-Volumes. Die Demo hebt die allgemeinen Freigaben für Musik- und Geräuscherzeugung nicht auf.

## Bedienung

1. Sprache im Skripteditor erzeugen und im Audioeditor über **Sprache übernehmen** hinzufügen. Die gewünschte Sprachversion ist auswählbar.
2. Musik und Geräusche beschreiben und erzeugen oder eigene MP3-, WAV-, OGG-, FLAC- bzw. M4A-Dateien hochladen. Generierte Dateien erscheinen nach Abschluss in der Bibliothek und können über **Einfügen** platziert werden. Dateien werden an der aktuellen Abspielposition eingefügt.
3. Clips auf der Zeitachse verschieben oder an den seitlichen Rändern kürzen. Die Griffe oben links und rechts nach innen ziehen, um Ein- und Ausblenden einzustellen. Die Griffe wandern mit der Fade-Dauer; die eingeblendete Linie zeigt den linearen Lautstärkeverlauf direkt während des Ziehens. Zurück zum Rand ziehen entfernt den Fade. Bei sehr schmalen Clips hineinzoomen, damit beide Griffe sichtbar werden. Für genaue Werte oder Tastaturbedienung den Clip auswählen und Position, Schnittanfang, Schnittende, Pegel sowie Ein- und Ausblenddauer bearbeiten. Schnittgrenzen beziehen sich auf die Quelldatei; Position bezieht sich auf den Gesamtmix.
4. Die Abspielposition über das Sekundenfeld oder einen Klick auf die obere Zeitachse setzen. **An Abspielposition teilen** schneidet einen ausgewählten Clip in zwei Teile. **Duplizieren** setzt eine Kopie unmittelbar dahinter. Die Quelldatei wird dabei nicht verändert.
5. **Stumm** entfernt eine Spur aus Vorschau und Export. Sobald eine Spur **Solo** ist, sind nur die Solo-Spuren hörbar; Stumm hat Vorrang. Der Pegel lässt sich pro Clip und pro Spur einstellen.
6. **Stand speichern** sichert die Bearbeitung. Rückgängig/Wiederholen gilt für die laufende Sitzung. Frühere gespeicherte Stände können geladen und als neuer Stand gespeichert werden. Änderungen aus einem zweiten Fenster werden nicht still überschrieben.
7. **Mix exportieren** speichert zunächst den aktuellen Stand und startet einen Hintergrundauftrag für MP3 (192 kbit/s) oder WAV (44,1 kHz, 16 Bit, Stereo). Der fertige Mix erscheint mit Wiedergabe und Download im Exportbereich. Währenddessen kann an einem neuen Stand weitergearbeitet werden.

Die automatische Musikabsenkung startet sanft mit 4 dB, 250 ms Attack und 900 ms Release. Absenkung und Übergänge sind über Regler einstellbar; 0 dB schaltet die Absenkung aus. Eine weiche S-Kurve und das Überbrücken kurzer Pausen vermeiden hektisches Pumpen. Die Absenkung richtet sich nach den Clipgrenzen, einschließlich innerhalb eines Clips enthaltener Sprechpausen. Für längere Geräuschkulissen kann ein nahtlos wiederholbares Geräusch erzeugt und dupliziert werden.

**T** teilt einen markierten Clip an der roten Abspielposition; **Leertaste** startet und pausiert. In Eingabefeldern, nativen Audioplayern und bearbeitbaren Texten werden keine Hotkeys ausgelöst. Das Quell-Wellenbild bleibt beim Kürzen unverändert und wird nur angeschnitten beziehungsweise verschoben. Zoom ändert weiterhin den Zeitmaßstab.

Grenzen der ersten Version: 60 Clips pro Stand, 30 Minuten Gesamtdauer, 200 verfügbare Bibliotheksdateien je Projekt und 50 MB pro Upload. Musik kann 3–600 Sekunden, ein Geräusch 0,5–30 Sekunden lang erzeugt werden. Es gibt keine automatische inhaltliche Szenenerkennung. Die Musikbeschreibung und die Platzierung werden durch den Benutzer festgelegt. Ein Export mischt die hörbaren Spuren; Einzelspurexporte sind über Solo und einen weiteren Export möglich.

Die Browser-Vorschau und FFmpeg verwenden dieselben Schnitt-, Fade- und Pegelwerte. Die Übersteuerungsbegrenzung erfolgt im Browser über einen Kompressor und beim Export über einen FFmpeg-Limiter; nahe der Pegelgrenze können sich beide leicht unterscheiden. Für die finale Kontrolle den gerenderten Mix anhören.

Beim Hochladen können mehrere Dateien gleichzeitig ausgewählt werden. Sie werden nacheinander verarbeitet und an derselben Abspielposition eingefügt. Über die Spurauswahl kann die Geräuschspur als Ziel festgelegt werden.

## Sprachverständlichkeit und Pegelschutz

Mehrere Geräusche auf derselben Spur können zeitlich überlappen und werden gleichzeitig gemischt. Zur Übersicht erscheinen überlappende Clips untereinander innerhalb der Spur. Jeder Clip hat eigene Schnitt-, Lautstärke- und Fade-Werte. Die Grenze von 60 Clips gilt für alle drei Spuren gemeinsam.

- **Sprachkompressor** dosiert die Stärke von 0 bis 100 Prozent: Schwelle −18 dB, Verhältnis 1:1 bis 3:1 und maximal +2 dB Pegelanhebung. Attack startet mit 25 ms, Release mit 350 ms; beide sind einstellbar. FFmpeg verwendet RMS-Erkennung. Kompression wirkt auf die Sprachspur; Musik und Geräusche behalten ihre Dynamik bis zur Begrenzung von Gesamtmix-Spitzen.
- **Geräusche während der Sprache absenken** ist von 0 bis 18 dB regelbar. Alte aktivierte Einstellungen erhalten als sanfteren Startwert 2 dB. Die überarbeitete Referenz-Demo lässt Geräusche ohne Absenkung hörbar.
- Alle Werte werden im JSON-Bearbeitungsstand unter `mix` gespeichert und in Exportaufträge übernommen. Alte gespeicherte Haken werden auf sanfte Standardwerte abgebildet; vorhandene Clips, Versionen und Exporte bleiben erhalten.
- Neu generierte Geräusche erhalten eine konstante Pegelanpassung auf etwa 0,6 Sample-Spitzenwert, höchstens +30 dB; Stille bleibt unverändert. Die Originaldatei bleibt erhalten. Eigene Uploads und Sprach- oder Musikdateien erhalten keine solche automatische Anpassung.
- Der fertige Mix hat vor dem Limiter 20 Prozent Pegelreserve; der Export-Limiter begrenzt Sample-Spitzen auf 0,95 (ungefähr −0,45 dBFS). Das schützt den WAV-Mix auch bei mehreren gleichzeitig lauten Geräuschen. Viele sehr laute Clips können dennoch die gesamte Mischung hörbar herunterdrücken; dafür zunächst die einzelnen Effekte leiser stellen. Der Limiter ist keine automatische Lautheitsnormalisierung und repariert keine Verzerrung im Original. MP3-Codierung kann Spitzen verändern; eine garantierte True-Peak-Grenze nach der Codierung ist nicht implementiert.

Die Sprachkompressoren im Browser und im Export verwenden ähnliche Einstellungen, können aber leicht unterschiedlich klingen. Für die finale Kontrolle den gerenderten Mix anhören.

Die Audiodateien lassen sich nach Audioart filtern; die Übersicht zeigt die Zahl der verfügbaren Geräuschbeispiele. `python manage.py seed_audio_drama_demo --refresh-mix` passt die vorhandenen Referenz-Geräusche im Pegel an und mischt die Referenz neu, ohne Anbieteraufrufe. Nur unveränderte Erststände erhalten die neuen Clippegel und einen zusätzlichen Export. Eigene Schnittbearbeitungen sowie historische Exportdateien bleiben erhalten. Der vorherige Referenzsatz muss vor dem Aufruf gesichert werden.

## Einrichtung

- Neue Migrationen mit `python manage.py migrate` anwenden und Webanwendung sowie Celery-Worker mit dem neuen Code starten. FFmpeg und ffprobe müssen erreichbar sein; beide sind im bestehenden Docker-Image vorhanden.
- Unter **Verwaltung → Audioeditor → Musik- und Geräuschanbindung** eine Konfiguration anlegen. Musik und Geräusche getrennt freigeben, Musikmodell wählen und **positive geschätzte Tarifwerte in EUR je Minute** gemäß dem eigenen Tarif eintragen. Es werden bewusst keine unbestätigten Preisannahmen voreingestellt.
- Ohne eigenen API-Schlüssel wird die bestehende ElevenLabs-Sprachanbindung verwendet (alternativ die Serverumgebungsvariable). Ein eigener Schlüssel kann optional verschlüsselt hinterlegt werden. Der API-Schlüssel benötigt Zugriff auf die jeweiligen Modelle/Funktionen; die Plattformfreigabe garantiert keine tarifseitige Freischaltung.
- Musik- und Geräuschkontingente werden unabhängig in Sekunden pro Benutzer und Kalendermonat reserviert. Die vorhandenen ElevenLabs-Anbieterbudgets gelten zusätzlich; die Spracherzeugung wird weiterhin in Zeichen begrenzt. Die neuen Nutzungsarten erscheinen im vorhandenen Verbrauchsprotokoll. Tarifwerte sind Schätzungen; tatsächliche Credits werden gespeichert, falls der Anbieter sie liefert. Es findet keine automatische Umrechnung dieser Credits mit dem Sprachtarif statt.
- Bei expliziter Ablehnung wird die Reservierung freigegeben. Bei erfolgreicher Generierung zählt der Verbrauch auch dann, wenn die anschließende lokale Verarbeitung scheitert. Bei Verbindungsabbruch oder unklarer Fertigstellung wird die Schätzung konservativ als Verbrauch protokolliert; der Auftrag wird nicht automatisch wiederholt. Nach einem solchen Fehler vor einer neuen Generierung das Anbieterkonto prüfen.
- Nginx benötigt für Uploads `client_max_body_size 52m`. Das aktualisierte Beispiel verwendet 185 Sekunden Lesetimeout; Gunicorn verwendet 180 Sekunden für Uploadverarbeitung. Vorhandene produktive Proxy-Konfigurationen müssen entsprechend angepasst werden.
- `python manage.py delete_expired_audio` regelmäßig ausführen. Der Befehl entfernt auch Studio-Originale, bearbeitbare Dateien, Exporte und alte verwaiste Dateien im Studio-Unterverzeichnis. Es gilt `AUDIO_RETENTION_DAYS`. Übernommene Sprachdateien laufen spätestens mit ihrer ursprünglichen Sprachversion ab. Gespeicherte Stände ersetzen keine dauerhafte Archivierung; abgelaufene Clips müssen entfernt oder erneut hinzugefügt werden.
- Derselbe Wartungsbefehl setzt seit mehr als 20 Minuten laufende Studio-Aufträge auf fehlgeschlagen (Worker-Zeitlimit: 15 Minuten). Wurde ein Anbieteraufruf bereits begonnen, bleibt die mögliche Nutzung als Schätzung protokolliert; andernfalls wird die Reservierung freigegeben.

API-Dokumentation:

- [ElevenLabs Music](https://elevenlabs.io/docs/api-reference/music/compose)
- [ElevenLabs Sound Effects](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert)

Weitere Musikanbieter können hinter der Provideradapter-Grenze ergänzt werden. Suno ist in dieser Version noch nicht implementiert.

## Prüfung

`python manage.py test audio_studio` prüft Berechtigungen, Validierung, Versionskonflikte, Reservierungen, Anbieterfehler und die API-Anfrageformate. Wenn FFmpeg und ffprobe verfügbar sind, werden zusätzlich echte Uploads, Normalisierung, Fades, Musikabsenkung, Export und Dateibereinigung geprüft. Die Anbieteraufrufe sind simuliert; es werden keine kostenpflichtigen API-Aufträge ausgelöst.
