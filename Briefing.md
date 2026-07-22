# Briefing: Sprachplattform für KI-generierte Hörtexte

> **Dokumenttyp:** Lebendes Projektbriefing und verbindliche Arbeitsgrundlage  
> **Stand:** 22. Juli 2026  
> **Status:** Phasen 0–2 lokal abgeschlossen; Phasen 3–6 technisch vorbereitet; GitHub- und Serverbereitstellung begonnen  
> **Arbeitsverzeichnis:** `D:\OneDrive\KI\Arbeitsbereich\Sprachplattform`

## 1. Verwendung dieses Dokuments

Dieses Dokument ist die zentrale, fortlaufend gepflegte Projektquelle. Jeder neue Arbeitschat soll zuerst diese Datei vollständig lesen, bevor geplant oder programmiert wird.

Bei jeder Arbeitssitzung gelten folgende Regeln:

1. Vor Arbeitsbeginn den Abschnitt **Aktueller Stand** und die **Nächste konkrete Aufgabe** prüfen.
2. Relevante neue Entscheidungen sofort im **Entscheidungsprotokoll** festhalten.
3. Erledigte Arbeit nur dann als abgeschlossen markieren, wenn sie überprüft wurde.
4. Nach Änderungen den **Aktuellen Stand**, die **Nächste konkrete Aufgabe** und das **Änderungsprotokoll** aktualisieren.
5. Offene Fragen nicht stillschweigend als entschieden behandeln.
6. API-Schlüssel, Passwörter und andere Zugangsdaten niemals in dieser Datei oder im Git-Repository speichern.

## 2. Projektziel

Für ungefähr 20 Lehrkräfte, überwiegend aus dem Sprachunterricht, soll eine einfache interne Webplattform entstehen. Lehrkräfte sollen ohne technische Vorkenntnisse Hörtexte und Dialoge erstellen, als Audio anhören und als MP3 herunterladen können.

Die Plattform stellt eigene Benutzerkonten bereit und verwendet zentral hinterlegte KI-APIs. Nutzer benötigen keine eigenen Konten bei ElevenLabs, Alibaba oder anderen Anbietern.

Der wichtigste Erfolgsmesswert ist nicht die Anzahl verfügbarer Einstellungen, sondern:

> Eine Lehrkraft kann in wenigen Minuten einen mehrsprachigen, mehrstimmigen Hörtext erstellen, prüfen und als MP3 herunterladen.

## 3. Ausgangslage und Rahmenbedingungen

- Etwa 20 interessierte Lehrkräfte.
- Jahresbudget: maximal 1.800 EUR.
- Hauptanwendung: Hörverstehensaufgaben für den Sprachunterricht.
- Die eingegebenen Texte sollen fiktiv und frei von Schülerdaten oder anderen personenbezogenen Daten sein.
- Die Plattform wird zunächst auf einem eigenen Server getestet.
- Die Anwendung soll gemeinsam mit Codex iterativ entwickelt werden.
- Eine lokal geprüfte Django-Anwendung ist vorhanden; echte Provider- und Serverabnahmen stehen noch aus.

Vorhandene Recherchedateien:

- `artifacts/tts-recherche/cost-model.csv`
- `artifacts/tts-recherche/source-notes.md`

## 4. Grundsatzentscheidung

### 4.1 Empfohlener Startanbieter

Für das MVP soll zunächst die **ElevenLabs API mit Eleven v3 und Text to Dialogue** integriert werden.

Begründung:

- Abdeckung der Kernsprachen Deutsch, Englisch, Französisch, Spanisch und Italienisch.
- Zusätzlich unter anderem Türkisch, Russisch und Arabisch.
- Native Dialog-API mit mehreren Stimmen in einem Auftrag.
- Regie- und Emotionsanweisungen über Audio-Tags.
- Fertige Audioausgabe über die API.
- Die erwarteten API-Kosten liegen deutlich unter dem Jahresbudget.

Relevante Dokumentation:

- https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue
- https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert
- https://elevenlabs.io/docs/overview/models
- https://elevenlabs.io/pricing/api

### 4.2 Alibaba/Qwen

`qwen-audio-3.0-tts-plus` soll nicht die erste und einzige Sprach-API sein. Das Modell ist über Alibaba Model Studio per API integrierbar und unterstützt gute Ausdruckssteuerung, seine aktuellen Systemstimmen unterstützen jedoch nur Mandarin und Englisch.

Qwen bleibt als späterer zweiter Provider interessant, insbesondere für englische Inhalte und Modellvergleiche. Die Architektur muss den späteren Anbieterwechsel beziehungsweise mehrere Provider vorbereiten, ohne im MVP mehrere vollständige Integrationen umzusetzen.

Relevante Dokumentation:

- https://www.alibabacloud.com/help/en/model-studio/tts-model/
- https://www.alibabacloud.com/help/en/model-studio/qwen-audio-tts-voice-list
- https://www.alibabacloud.com/help/en/model-studio/realtime-tts-user-guide

### 4.3 Keine Enterprise-Mehrnutzerlösung im MVP

Es wird zunächst kein ElevenLabs-Enterprise-Konto für alle Lehrkräfte beschafft. Die eigene Plattform verwendet einen zentralen, ausschließlich serverseitig gespeicherten API-Schlüssel. Die Lehrkräfte arbeiten nur in der eigenen Anwendung.

### 4.4 KI-Assistent getrennt von TTS

Die Text- und Skripterzeugung wird als eigene Provider-Schnittstelle behandelt. Die Sprach-API darf nicht fest mit dem später verwendeten Textmodell gekoppelt werden.

## 5. Zielgruppen und Rollen

### 5.1 Administrator

Der Administrator kann:

- Benutzer anlegen, bearbeiten, sperren und reaktivieren.
- Individuelle temporäre Erstpasswörter erzeugen.
- Passwortzurücksetzungen auslösen.
- Monats- oder Jahreslimits pro Nutzer festlegen.
- Nutzung und geschätzte Kosten einsehen.
- verfügbare Sprachen, Stimmen und Modelle freischalten.
- globale Aufbewahrungsfristen konfigurieren.
- fehlgeschlagene Generierungsaufträge einsehen.

Der Admin-Account soll besonders geschützt werden; Mehrfaktor-Authentifizierung ist spätestens vor dem produktiven Rollout vorzusehen.

### 5.2 Lehrkraft

Eine Lehrkraft kann:

- sich mit Benutzername und individuellem temporären Passwort anmelden.
- beim ersten Login ein eigenes Passwort vergeben.
- eigene Projekte anlegen, bearbeiten, duplizieren und löschen.
- Skripte schreiben oder durch einen KI-Assistenten erstellen beziehungsweise verändern lassen.
- Sprache, Sprecher, Stimmen, Tempo und Regieanweisungen wählen.
- einzelne Beiträge probehören.
- das vollständige Audio erzeugen, abspielen und als MP3 herunterladen.
- ausschließlich die eigenen Projekte und Audiodateien sehen.
- die eigene verbleibende Nutzung einsehen.

## 6. Sprachen

### 6.1 Kernsprachen des MVP

- Deutsch
- Englisch
- Französisch
- Spanisch
- Italienisch

### 6.2 Weitere gewünschte Sprachen

- Türkisch
- Russisch
- Arabisch

Weitere von Eleven v3 unterstützte Sprachen können später über Konfiguration freigeschaltet werden. Die Kernsprachen müssen vor dem Pilot mit geeigneten Stimmen und typischen Unterrichtstexten getestet werden.

## 7. Produktumfang des MVP

### 7.1 Bestandteil des MVP

- Login und erzwungener Passwortwechsel beim ersten Login.
- Admin-Oberfläche für Benutzerverwaltung.
- Projektübersicht für Lehrkräfte.
- strukturierter Skripteditor.
- Einzelsprecher- und Mehrsprecherskripte.
- Sprach- und Stimmenauswahl.
- einfache Regieanweisungen.
- einstellbare Pausen zwischen Beiträgen.
- ElevenLabs-v3-Text-to-Dialogue-Integration.
- Hintergrundverarbeitung mit verständlichem Fortschrittsstatus.
- Audioplayer und MP3-Download.
- Nutzungs- und Kostenprotokoll.
- konfigurierbare Nutzungslimits.
- automatische Dateilöschung nach einer festzulegenden Frist.
- Docker-basierter Testbetrieb auf dem eigenen Server.

### 7.2 Nachgelagerte Funktionen

- KI-Assistent zur strukturierten Skripterzeugung und -überarbeitung.
- Qwen-Audio- oder weitere TTS-Provider.
- direkter Qualitätsvergleich verschiedener Anbieter.
- Aussprachewörterbücher.
- Vorlagenbibliothek für Unterrichtssituationen.
- gemeinsame Projekte oder Freigaben zwischen Lehrkräften.
- Export von Arbeitsblättern und Hörverstehensfragen.
- Voice Cloning.

### 7.3 Bewusst nicht Bestandteil des ersten MVP

- öffentliche Registrierung.
- Schülerkonten.
- Verarbeitung von Schülerdaten.
- Abrechnung oder Bezahlung durch einzelne Nutzer.
- native Smartphone-App.
- Echtzeit-Sprachchat.
- komplexe Audio-Nachbearbeitung wie Musikbett oder Sounddesign.

## 8. Hauptablauf für Lehrkräfte

1. Lehrkraft meldet sich an.
2. Auf der Projektübersicht wird **Neuen Hörtext erstellen** gewählt.
3. Titel, Zielsprache und optional GER-Niveau werden festgelegt.
4. Ein Skript wird manuell eingegeben oder später mit dem KI-Assistenten entworfen.
5. Sprecher werden angelegt und passenden Stimmen zugeordnet.
6. Das Skript wird aus einzelnen Sprechbeiträgen aufgebaut.
7. Optional werden Regieanweisungen und Pausen gesetzt.
8. Einzelne Beiträge können probeweise erzeugt werden.
9. Die Anwendung zeigt vor der vollständigen Generierung Zeichenzahl und geschätzten Verbrauch.
10. **Audio erzeugen** startet einen Hintergrundauftrag.
11. Nach Abschluss kann das Audio abgespielt und als MP3 heruntergeladen werden.
12. Das Projekt bleibt bearbeitbar; Änderungen erzeugen eine neue Audioversion.

## 9. Bedien- und Oberflächenkonzept

Die Anwendung ist ein Arbeitswerkzeug für Lehrkräfte. Sie soll ruhig, klar, freundlich und hochwertig wirken, aber keine unnötigen technischen Begriffe zeigen.

### 9.1 Desktop-Editor

Der Editor verwendet eine Zwei-Spalten-Struktur:

- **Links, etwa zwei Drittel:** Skript und Sprechbeiträge.
- **Rechts, etwa ein Drittel:** Audioeinstellungen, Sprecher/Stimmen, KI-Assistent und Hauptaktion.

Die rechte Spalte bleibt beim Scrollen sichtbar, sofern die Bildschirmhöhe dies erlaubt.

### 9.2 Linker Skriptbereich

Jeder Sprechbeitrag ist ein strukturierter Block mit:

- Sprechername.
- Textfeld.
- Regieanweisung.
- Pause danach in Millisekunden oder über verständliche Presets.
- Beitrag probehören.
- duplizieren.
- löschen.
- Reihenfolge ändern.

Oben befinden sich nur Projekttitel, Sprache und optional GER-Niveau. Änderungen werden automatisch gespeichert.

### 9.3 Rechte Seitenleiste

Reihenfolge der Inhalte:

1. Zielsprache.
2. Sprecher und zugeordnete Stimmen, jeweils mit Stimmenprobe.
3. globale Geschwindigkeit und Ausgabequalität.
4. eingeklappte erweiterte Einstellungen.
5. KI-Assistent.
6. deutlich hervorgehobene Hauptaktion **Audio erzeugen**.

Technische Modellnamen wie `eleven_v3` werden normalen Nutzern nicht prominent angezeigt. Stattdessen werden verständliche Qualitätsprofile verwendet, beispielsweise:

- Ausdrucksstark – empfohlen.
- Gleichmäßig.
- Schnelle Vorschau.

### 9.4 Mobile und kleine Bildschirme

- Bereiche werden untereinander angeordnet.
- Die Hauptaktion bleibt leicht erreichbar.
- Kein wichtiger Inhalt darf nur über Hover zugänglich sein.
- Alle wesentlichen Funktionen müssen mit Tastatur bedienbar sein.
- Zielstandard ist WCAG 2.2 AA.

### 9.5 Zustände, die gestaltet werden müssen

- leeres Projekt.
- Autosave aktiv/gespeichert/fehlgeschlagen.
- API-Auftrag wartet/läuft/erfolgreich/fehlgeschlagen.
- Nutzungslimit fast erreicht/erreicht.
- Stimme für gewählte Sprache ungeeignet.
- Teilabschnitt fehlgeschlagen.
- Server oder Provider vorübergehend nicht erreichbar.
- Audio wurde automatisch gelöscht und muss neu erzeugt werden.

## 10. Regieanweisungen

Lehrkräfte wählen zunächst aus verständlichen deutschen Begriffen. Die Anwendung übersetzt diese intern in getestete Eleven-v3-Audio-Tags.

Beispiele:

| Anzeige | Interne Anweisung |
|---|---|
| freundlich | `[friendly]` |
| erfreut | `[cheerfully]` |
| überrascht | `[surprised]` |
| flüsternd | `[whispering]` |
| ernst | `[serious]` |
| traurig | `[sad]` |
| aufgeregt | `[excited]` |
| zögernd | `[hesitant]` |
| lachend | `[laughing]` |

Die Zuordnung ist eine testbare Konfiguration und darf nicht als garantiert identische Wirkung bei allen Stimmen betrachtet werden.

Exakte Pausen werden nicht nur sprachlich angefordert. Sie werden bei Bedarf technisch in die Audiokette eingefügt.

## 11. ElevenLabs-Integration

### 11.1 Text to Dialogue

Die Integration verwendet vorrangig:

- Endpoint: `POST /v1/text-to-dialogue`
- Modell: `eleven_v3`
- Eingabe: geordnete Liste aus `text` und `voice_id`
- optionaler `language_code`
- Audioausgabe zunächst als MP3.

### 11.2 Zu beachtende Grenzen

- Für zuverlässige Dialoggenerierung sollen pro Anfrage insgesamt höchstens ungefähr 2.000 Zeichen verwendet werden.
- Pro Anfrage sind höchstens zehn unterschiedliche Voice IDs vorgesehen.
- Längere Skripte müssen an Dialoggrenzen segmentiert und anschließend zusammengefügt werden.
- Die Ausgabe ist nicht vollständig deterministisch.
- Ein optionaler Seed kann die Reproduzierbarkeit verbessern, garantiert sie aber nicht.
- Exakte SSML-Pausen werden von Eleven v3 nicht unterstützt.

### 11.3 Audio-Pipeline

Für längere oder exakt gesteuerte Projekte:

1. Skript in zusammenhängende Abschnitte unterhalb der Providergrenze teilen.
2. Abschnitte getrennt erzeugen.
3. Audioformat und Lautstärke vereinheitlichen.
4. definierte Pausen einfügen.
5. Abschnitte mit FFmpeg zusammenfügen.
6. finale MP3 nur einmal kodieren.
7. Audiodatei und technische Metadaten einer Projektversion zuordnen.

Ein fehlgeschlagener Abschnitt muss einzeln wiederholt werden können, ohne das gesamte Projekt neu zu generieren.

### 11.4 Provider-Abstraktion

Die Geschäftslogik darf keine ElevenLabs-spezifischen Felder direkt in den zentralen Projektmodellen voraussetzen.

Vorgesehene interne Schnittstelle:

```python
class TTSProvider:
    def list_voices(self, language: str): ...
    def estimate_usage(self, script): ...
    def synthesize_dialogue(self, script, options): ...
    def get_job_result(self, provider_job_id): ...
```

Provider-spezifische Besonderheiten werden im jeweiligen Adapter umgesetzt.

## 12. KI-Assistent

Der KI-Assistent wird als separates Modul nach der stabilen TTS-Grundfunktion implementiert.

### 12.1 Eingaben

- Zielsprache.
- GER-Niveau.
- Thema beziehungsweise Situation.
- gewünschte Dauer.
- Anzahl und Rollen der Sprecher.
- gewünschter Lernwortschatz.
- Grammatikschwerpunkt.
- gewünschte Art der Hörverstehensaufgabe.
- freier Arbeitsauftrag.

### 12.2 Strukturierte Ausgabe

Der Assistent muss valides strukturiertes JSON liefern, das serverseitig geprüft wird. Beispiel:

```json
{
  "title": "Au cinéma",
  "language": "fr",
  "level": "A2",
  "speakers": [
    {"name": "Élodie"},
    {"name": "Thomas"}
  ],
  "segments": [
    {
      "speaker": "Élodie",
      "text": "À quelle heure commence le film ?",
      "direction": "curious",
      "pause_after_ms": 500
    }
  ]
}
```

### 12.3 Änderungsprinzip

Der Assistent darf Nutzereingaben nicht automatisch überschreiben. Änderungen werden als Vorschau angeboten:

- Vorschlag übernehmen.
- nur ergänzen.
- markierten Bereich ersetzen.
- erneut überarbeiten.
- verwerfen.
- rückgängig machen.

### 12.4 Typische Assistentenaktionen

- einfacher oder anspruchsvoller formulieren.
- auf ein bestimmtes GER-Niveau bringen.
- verlängern oder kürzen.
- natürlicher gestalten.
- weiteren Sprecher ergänzen.
- bestimmten Wortschatz einbauen.
- Zahlen, Uhrzeiten oder Datumsangaben ergänzen.
- passende Hörverstehensfragen erzeugen.

Der konkrete LLM-Anbieter ist noch nicht entschieden.

## 13. Vorgeschlagene technische Architektur

Diese Architektur ist die aktuelle Empfehlung und wird vor dem Scaffold anhand des Zielservers bestätigt.

### 13.1 Komponenten

- **Backend und Webanwendung:** Django/Python.
- **Datenbank:** PostgreSQL.
- **Dynamische Oberfläche:** Django Templates mit HTMX/Alpine; React nur, wenn der Editor es tatsächlich erforderlich macht.
- **Hintergrundaufträge:** Celery.
- **Warteschlange:** Redis.
- **Audioverarbeitung:** FFmpeg.
- **Dateispeicher im Pilot:** lokaler, nicht öffentlich erreichbarer Serverpfad.
- **Deployment:** Docker Compose.
- **HTTPS/Reverse Proxy:** Caddy oder vorhandener Nginx/Traefik.
- **Produktiver Prozess:** Gunicorn/Uvicorn entsprechend der finalen Django-Konfiguration.

### 13.2 Warum Django

- ausgereifte Benutzer- und Passwortverwaltung.
- integrierte Admin-Oberfläche.
- Berechtigungen und Sessions vorhanden.
- gute Python-Integration für ElevenLabs und Audioverarbeitung.
- geringerer Implementierungsaufwand als ein getrenntes SPA- und API-System.

### 13.3 Erwartete Serverressourcen für den Pilot

Als Arbeitsannahme:

- 2 bis 4 CPU-Kerne.
- mindestens 4 GB RAM.
- mindestens 20 GB freier Speicher.
- keine GPU erforderlich.
- Linux und Docker empfohlen.

Die endgültigen Anforderungen hängen von Betriebssystem, vorhandenen Diensten, Sicherungsstrategie und gewünschter Aufbewahrungszeit ab.

## 14. Vorgeschlagenes Datenmodell

### User

- ID.
- Benutzername.
- Passwort-Hash über das Django-Authentifizierungssystem.
- Rolle: Admin oder Lehrkraft.
- aktiv/gesperrt.
- Passwortwechsel erforderlich.
- Zeichenlimit pro Abrechnungszeitraum.
- Erstellungs- und letzte Anmeldezeit.

### Project

- ID.
- Eigentümer.
- Titel.
- Zielsprache.
- optional GER-Niveau.
- Status.
- Erstellungs- und Änderungszeit.

### Speaker

- ID.
- Projekt.
- Anzeigename.
- interne Farbe/Icon zusätzlich zum Textlabel.
- Provider.
- Modell.
- Voice ID.

### ScriptSegment

- ID.
- Projekt.
- Reihenfolge.
- Sprecher.
- Text.
- Regieanweisung.
- Geschwindigkeit.
- Pause danach in Millisekunden.

### GenerationJob

- ID.
- Projekt und Projektversion.
- anfordernder Nutzer.
- Status: queued/running/succeeded/failed/cancelled.
- Provider und Modell.
- Zeichenzahl.
- geschätzte und tatsächliche Kosten.
- Provider Request IDs.
- Fehlermeldung in bereinigter Form.
- Zeitstempel.

### AudioAsset

- ID.
- Projektversion.
- interner Dateipfad.
- Format, Dauer und Dateigröße.
- erzeugt am.
- Ablauf-/Löschzeitpunkt.

### UsageLedger

- Nutzer.
- Auftrag.
- Provider.
- Modell.
- Zeichenmenge.
- geschätzte Kosten.
- Datum und Abrechnungszeitraum.

### ProviderVoice

- Provider und Modell.
- Voice ID.
- Anzeigename.
- unterstützte Sprachen.
- Eigenschaften wie Geschlecht, Alter, Akzent, Stil.
- Vorschau-URL oder lokale kurze Vorschau.
- aktiv/freigegeben.

## 15. Sicherheit und Betrieb

- Kein identisches Standardpasswort für alle Nutzer.
- Pro Benutzer ein zufälliges temporäres Erstpasswort oder später ein Einmal-Einladungslink.
- Erzwungener Passwortwechsel beim ersten Login.
- Sichere Passwort-Hashes über Django; keine eigene Kryptografie.
- Anmelderatenbegrenzung und Schutz vor Brute Force.
- Sichere, HTTP-only und SameSite-konfigurierte Cookies.
- CSRF-Schutz.
- Berechtigungsprüfung auf jeder Projekt- und Dateianfrage.
- Admin-MFA vor produktiver Freigabe.
- API-Schlüssel ausschließlich als Server-Secret beziehungsweise Umgebungsvariable.
- Keine API-Schlüssel im Browser, HTML, JavaScript-Bundle, Log oder Git.
- Audiopfade nicht als frei erratbare öffentliche URLs.
- Eingabegrößen begrenzen und Uploads nur nach ausdrücklicher Erweiterung zulassen.
- Fehlermeldungen dürfen keine Schlüssel oder vollständigen Providerantworten an Nutzer ausgeben.
- Backups von Datenbank und notwendiger Konfiguration testen.
- automatische Löschung alter Audiodateien und temporärer Zwischenstücke.

Auch bei fiktiven Texten soll Datensparsamkeit gelten. Rohtexte und Audiodateien werden nur so lange gespeichert, wie es für die Projektfunktion erforderlich ist.

## 16. Nutzungslimits und Kostenkontrolle

Vorläufige Startwerte:

- 30.000 abrechenbare Zeichen pro Nutzer und Monat.
- zusätzliches organisationsweites Monats- und Jahreslimit.
- Warnung bei 80 Prozent des Nutzerlimits.
- Sperre weiterer Generierungen bei 100 Prozent, außer Admin hebt das Limit an.
- Probe- und Vollgenerierungen werden gleichermaßen protokolliert.
- Vor jeder Generierung wird eine Verbrauchsschätzung angezeigt.

Die Limits werden nach dem Pilot anhand der tatsächlichen Nutzung angepasst.

## 17. Qualitätssicherung

### 17.1 Automatisierte Tests

- Benutzer- und Berechtigungsprüfungen.
- erzwungener Erstpasswortwechsel.
- Projektzugriff nur durch Eigentümer/Admin.
- Zeichenzählung und Limitprüfung.
- Skriptsegmentierung unter Providergrenzen.
- Provideradapter mit gemockten Antworten.
- Retry- und Fehlerzustände.
- strukturierte KI-Assistentenantworten gegen Schema validieren.
- automatische Dateilöschung.

### 17.2 Manuelle Tests

- Anmeldung und Passwortwechsel.
- vollständiger Erstellungsablauf ohne technische Vorkenntnisse.
- Tastaturbedienung.
- responsives Verhalten.
- sichtbare Fokuszustände und Kontraste.
- Audioerzeugung in allen fünf Kernsprachen.
- zwei bis vier Sprecher.
- lange Skripte über 2.000 Zeichen.
- Provider- und Netzwerkfehler.
- Limitüberschreitung.
- Serverneustart während wartender Aufträge.

### 17.3 Pädagogischer Qualitätstest

Für jede Kernsprache werden mehrere typische Skripte getestet:

- Dialog Alltagssituation.
- sachlicher Einzeltext.
- Zahlen, Uhrzeiten und Eigennamen.
- langsames A1/A2-Sprechtempo.
- emotionaler Dialog.
- drei oder mehr Sprecher.

Bewertungskriterien:

- Aussprache.
- Natürlichkeit.
- Verständlichkeit.
- Konstanz der Stimme.
- Einhaltung von Regieanweisungen.
- didaktische Eignung.
- Fehler- beziehungsweise Regenerationsquote.

## 18. Umsetzungsphasen

### Phase 0 – Projektgrundlage

- Zielserver und Deploymentbedingungen klären.
- technischen Stack endgültig bestätigen.
- Repository-/Projektstruktur anlegen.
- `.env.example` ohne Geheimnisse erstellen.
- Docker-Compose-Entwicklungsumgebung aufsetzen.
- Django-Grundprojekt, PostgreSQL und Redis starten.
- Basis-CI beziehungsweise lokale Prüfkommandos definieren.
- dieses Briefing nach den Entscheidungen aktualisieren.

**Abnahme:** Die leere Anwendung startet reproduzierbar lokal per dokumentiertem Kommando; Datenbankmigration und Grundtests laufen erfolgreich.

### Phase 1 – Benutzer und Administration

- eigenes User-Modell beziehungsweise früh festgelegte Erweiterung des Django-Users.
- Admin-Login.
- Lehrkräfte anlegen/sperren.
- individuelles temporäres Passwort.
- erzwungener Passwortwechsel.
- Login, Logout und Passwortzurücksetzung.
- Rollen und Berechtigungstests.

**Abnahme:** Ein Admin kann eine Lehrkraft anlegen; diese kann sich einmalig anmelden, muss das Passwort ändern und sieht danach ausschließlich den eigenen Bereich.

### Phase 2 – Projekte und Skripteditor

- Projektliste.
- Projekt erstellen, umbenennen, duplizieren und löschen.
- Sprecherverwaltung.
- strukturierte Sprechbeiträge.
- Reihenfolge, Regieanweisung und Pausen.
- Autosave und verständliche Zustände.
- responsiver Zwei-Spalten-Editor.

**Abnahme:** Ein vollständiges Dialogskript kann ohne API-Aufruf erstellt, gespeichert und nach Neuanmeldung unverändert weiterbearbeitet werden.

### Phase 3 – Stimmenkatalog und ElevenLabs

- Provider-Abstraktion.
- ElevenLabs-Adapter.
- Stimmen abrufen, filtern und administrativ freigeben.
- Stimmenprobe.
- Sprache und Voice ID validieren.
- Verbrauch vorab schätzen.
- Secret-Verwaltung dokumentieren.

**Abnahme:** Eine Lehrkraft kann für jede Kernsprache geeignete freigegebene Stimmen auswählen und einen kurzen Testbeitrag erzeugen.

### Phase 4 – Dialog- und Audio-Pipeline

- Text-to-Dialogue-Aufträge.
- Hintergrundwarteschlange.
- Fortschrittsanzeige.
- Segmentierung langer Skripte.
- Retry einzelner Teile.
- FFmpeg-Zusammenführung und exakte Pausen.
- finale MP3, Player und Download.
- Versionierung und Dateilöschung.
- Nutzungsledger und Limits.

**Abnahme:** Ein Dialog über 2.000 Zeichen mit mehreren Sprechern wird zuverlässig als eine MP3 erzeugt; Fehler können ohne vollständige Neugenerierung behoben werden.

### Phase 5 – KI-Assistent

- LLM-Anbieter auswählen.
- Eingabeformular und freier Prompt.
- strukturiertes Ausgabeschema.
- serverseitige Validierung.
- Vorschau, übernehmen, ergänzen, verwerfen und rückgängig.
- gezielte Überarbeitung markierter Abschnitte.
- Token-/Kostenlimits.

**Abnahme:** Aus einem kurzen Unterrichtsauftrag entsteht ein valides bearbeitbares Skript, ohne vorhandenen Inhalt ungefragt zu überschreiben.

### Phase 6 – Pilot und Härtung

- Testserver mit HTTPS.
- Backups und Wiederherstellung testen.
- Logging und Monitoring.
- automatisierte und manuelle Sicherheitsprüfungen.
- Accessibility-Prüfung.
- Pilot mit fünf Lehrkräften.
- Nutzung, Fehler und Supportbedarf auswerten.
- Freigabe für ungefähr 20 Nutzer.

**Abnahme:** Achtwöchiger Pilot kann mit benanntem technischen Verantwortlichen und dokumentiertem Wiederherstellungsweg beginnen.

## 19. Definition of Done für Implementierungsaufgaben

Eine Aufgabe gilt nur als erledigt, wenn:

- die geforderte Funktion implementiert ist.
- relevante automatisierte Tests vorhanden sind und bestehen.
- Fehler- und Leerzustände berücksichtigt wurden.
- Berechtigungen geprüft wurden.
- keine Geheimnisse eingecheckt wurden.
- relevante Dokumentation aktualisiert wurde.
- die Änderung visuell beziehungsweise funktional im Browser geprüft wurde, wenn sie die Oberfläche betrifft.
- dieses Briefing bei geänderten Entscheidungen oder Projektständen aktualisiert wurde.

## 20. Offene Entscheidungen vor dem ersten Server-Deployment

- Betriebssystem und Version des Zielservers.
- Sind Docker und Docker Compose vorhanden oder zulässig?
- verfügbare CPU-, RAM- und Speicherressourcen.
- Domain festgelegt: `sprachplattform.markuspiller.de`; öffentliche HTTPS-Terminierung noch zu prüfen.
- vorhandener Reverse Proxy und HTTPS-Konfiguration.
- SSH-/Deploymentweg.
- vorhandene Backupinfrastruktur.
- SMTP-Server für spätere Einladungen/Passwortzurücksetzung.
- gewünschte Aufbewahrungsfrist für Projekte und Audiodateien.
- ElevenLabs-Pay-as-you-go-Konto und API-Key vorhanden?
- gewünschte erste Stimmen je Kernsprache.
- späterer Text-KI-Anbieter für den Assistenten.
- visuelle Bezeichnung und eventuelles Logo der Plattform.

Zugangsdaten werden bei Bedarf ausschließlich über sichere Serverkonfiguration eingebracht, niemals in das Briefing oder in Chatnachrichten kopiert.

## 21. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Stimmenqualität schwankt je Sprache | Kuratierte Stimmen je Sprache und pädagogischer Pilot |
| Eleven v3 liefert variable Ergebnisse | Seed wo sinnvoll, Einzelbeiträge erneut erzeugen, Versionen behalten |
| Lange Dialoge überschreiten Providergrenze | Automatische Segmentierung an Sprecher-/Satzgrenzen |
| Mehrere Generierungen verbrauchen unnötig Budget | Vorschau, Zeichenschätzung, Nutzer- und Organisationslimits |
| Ein Nutzer sieht fremde Projekte | konsequente serverseitige Objektberechtigungen und Tests |
| API-Schlüssel wird offengelegt | ausschließlich serverseitiges Secret, Logbereinigung |
| Provider fällt aus oder ändert API | Provideradapter und saubere interne Datenmodelle |
| Oberfläche wird durch Optionen überladen | Modellnamen verstecken, progressive Offenlegung, eine Hauptaktion |
| KI-Assistent überschreibt gute Arbeit | Änderungsvorschau, Rückgängig und explizite Übernahme |
| Vibe-Coding erzeugt schwer wartbaren Prototyp | kleine überprüfbare Schritte, Tests, Migrationen und laufende Dokumentation |

## 22. Aktueller Stand

- Phase 0 ist abgeschlossen: Django 5.2 LTS, Python 3.12, PostgreSQL, Redis, Celery, Gunicorn, FFmpeg und Docker Compose sind als reproduzierbares Grundgerüst vorhanden.
- Phase 1 ist lokal abgeschlossen: Login, POST-Logout, Sperrung, Rate-Limit, einmalig sichtbare temporäre Passwörter, erzwungener Erstwechsel und Adminverwaltung sind implementiert und getestet.
- Phase 2 ist lokal abgeschlossen: eigentümergeschützte Projekte, Sprecher, Beiträge, Regieanweisungen, Pausen, Reihenfolge, Duplikation und Autosave sind implementiert.
- Phase 3 ist technisch vorbereitet: providerneutrale Schnittstelle, aktueller ElevenLabs-Text-to-Dialogue-Adapter, paginierter Stimmenimport, administrative Freigabe, Sprachprüfung und gemockte Tests sind vorhanden.
- Phase 4 ist technisch vorbereitet: unveränderliche Versionen, Nutzungslimits, wiederholbare Teile, Celery-Aufträge, FFmpeg-Zusammenbau, Player, Download, Nutzungsledger und Dateilöschung sind implementiert und mit einem Fake-Provider geprüft.
- Phase 5 ist teilweise vorbereitet: strikte JSON-Validierung sowie explizites Ergänzen, Ersetzen, Verwerfen und Rückgängigmachen sind vorhanden; LLM-Anbieter, Eingabeoberfläche und echter Modellaufruf sind bewusst offen.
- Phase 6 ist lokal vorbereitet: CSP und weitere Sicherheitsheader, responsive Browserprüfung, Betriebsleitfaden und Pilotcheckliste liegen vor.
- 39 automatisierte Tests, Migrationen, Systemcheck, Abhängigkeitsprüfung und Desktop-/Mobil-Browser-QA sind erfolgreich.
- Docker und FFmpeg sind auf dem aktuellen Entwicklungsrechner nicht installiert; Compose- und reale Audiokette konnten deshalb nicht end-to-end gestartet werden.
- ElevenLabs-Key, kuratierte Stimmen, Zielserver, Domain, HTTPS, SMTP, MFA, Backup-Restore und Aufbewahrungsfrist sind weiterhin extern zu bestätigen.
- Das Projekt ist im öffentlichen GitHub-Repository `markuspillermusic-hash/sprachplattform` veröffentlicht; `main` ist der Standardbranch.
- Zieladresse und interner Proxyweg sind festgelegt: `https://sprachplattform.markuspiller.de` leitet an `http://127.0.0.1:8085` weiter.

## 23. Nächste konkrete Aufgabe

**Externen Integrationspilot vorbereiten: Zielserver bestätigen, Compose-Stack starten, ElevenLabs-Zugang sicher konfigurieren und die reale Audiokette mit kuratierten Stimmen prüfen.**

Ein neuer Arbeitschat soll:

1. `Briefing.md` vollständig lesen.
2. die noch offenen Serverangaben, Domain, HTTPS, Backupziel, SMTP, Aufbewahrungsfrist und MFA-Entscheidung klären.
3. Docker Compose auf dem Zielserver starten und Healthchecks, Migrationen sowie `check --deploy` prüfen.
4. den ElevenLabs-Key ausschließlich als Server-Secret setzen, Stimmen je Kernsprache synchronisieren, akustisch prüfen und administrativ freigeben.
5. kurze und lange Dialoge mit mehreren Stimmen, Pausen, Retry, Player, Download, Limits und Löschung end-to-end testen.
6. einen dokumentierten Backup-Restore und Accessibility-Schnelltest durchführen.
7. danach den LLM-Anbieter für Phase 5 auswählen oder den Assistenten weiter deaktiviert lassen.

## 24. Entscheidungsprotokoll

| Datum | Entscheidung | Begründung |
|---|---|---|
| 2026-07-22 | Eigenes internes Portal statt 20-Sitz-Enterprise-Lösung | API-Kosten sind niedrig; Nutzerführung, Limits und Anbieterwechsel bleiben unter eigener Kontrolle. |
| 2026-07-22 | Verwaltete API statt selbst gehostetem TTS-Modell im MVP | Kein GPU-Betrieb notwendig; geringerer Wartungs- und Infrastrukturaufwand. |
| 2026-07-22 | ElevenLabs v3 Text to Dialogue als erster TTS-Provider | Deckt alle gewünschten Sprachen ab und unterstützt native Mehrsprecherdialoge sowie Regie-Tags. |
| 2026-07-22 | Qwen-Audio-3.0-TTS-Plus zunächst nur als spätere Erweiterung | Gute Ausdruckssteuerung, aber aktuelle Systemstimmen nur für Mandarin und Englisch. |
| 2026-07-22 | Provider-Abstraktion von Beginn an | Verhindert harte Anbieterbindung, ohne das MVP durch mehrere Integrationen zu überladen. |
| 2026-07-22 | Strukturierter Dialogeditor statt ausschließlich freiem Textfeld | Sprecher, Stimmen, Pausen, Teilwiederholungen und KI-Ausgaben werden zuverlässig bearbeitbar. |
| 2026-07-22 | Technische Modellnamen werden für Lehrkräfte verborgen | Niedrige Einstiegshürde und geringere kognitive Belastung. |
| 2026-07-22 | KI-Assistent als getrennte spätere Phase | Zuerst TTS-Kernworkflow stabilisieren; Textmodell bleibt unabhängig austauschbar. |
| 2026-07-22 | Django 5.2 LTS und Python 3.12 als bestätigter Web-Stack | LTS-Wartungsfenster, integrierte Benutzerverwaltung und Python-Audiointegration reduzieren Betriebs- und Implementierungsrisiken. |
| 2026-07-22 | PostgreSQL 17, Redis 7.4, Celery, FFmpeg und Docker Compose für den Pilot | Deckt persistente Daten, Hintergrundaufträge und die spätere Audio-Pipeline mit reproduzierbarem Betrieb ab. |
| 2026-07-22 | Eigenes Django-User-Modell bereits in Phase 0 | Ein späterer Wechsel des zentralen User-Modells wäre migrationskritisch; Rollen, Erstpasswortwechsel und Zeichenlimit sind so von Beginn an erweiterbar. |
| 2026-07-22 | Linux und Docker Compose bis zur Serverklärung als Pilotannahme | Die Zielserverdaten sind noch offen; das Scaffold bleibt lokal mit SQLite testbar und dokumentiert die ausstehende Betriebsbestätigung. |
| 2026-07-22 | UUIDs plus serverseitige Eigentümerprüfung für Projekte und Dateien | Nicht erratbare URLs ergänzen, ersetzen aber nicht die geprüfte Objektberechtigung. |
| 2026-07-22 | Temporäre Passwörter werden nur einmal im Admin angezeigt | Klartext wird nicht gespeichert; anschließend erzwingt die Anwendung ein persönliches Passwort. |
| 2026-07-22 | Providerzugriff über schmalen eigenen Adapter statt Kopplung an ein SDK | API-Vertrag, Fehlerbereinigung, Tests und ein späterer Providerwechsel bleiben unter eigener Kontrolle. |
| 2026-07-22 | Verbrauch wird beim Anlegen eines Generierungsauftrags reserviert | Parallele Aufträge können Limits nicht erst nach einem erfolgreichen Provideraufruf überraschend überschreiten. |
| 2026-07-22 | Audioteile werden einzeln erzeugt und mit FFmpeg samt exakten Pausen zusammengesetzt | Fehler lassen sich teilbezogen wiederholen; die finale MP3 wird nur einmal kodiert. |
| 2026-07-22 | KI-Vorschläge verwenden ein geschlossenes Schema und explizite Übernahmemodi | Unbekannte Felder werden abgewiesen und vorhandene Arbeit wird nie ungefragt überschrieben. |
| 2026-07-22 | Noch kein LLM-Anbieter für den Assistenten | Die TTS-Grundfunktion ist zuerst real zu validieren; Anbieter-, Datenschutz- und Kostenentscheidung bleibt offen. |
| 2026-07-22 | Keine Inline-Skripte; Content-Security-Policy ab lokaler Entwicklung | Reduziert die Angriffsfläche und macht Sicherheitsfehler früh sichtbar. |
| 2026-07-22 | `sprachplattform.markuspiller.de` mit internem Upstream `127.0.0.1:8085` | Die öffentliche Adresse bleibt verständlich; der Anwendungsport ist nur lokal erreichbar und HTTPS endet am Reverse Proxy. |

## 25. Änderungsprotokoll

### 2026-07-22 – Initiale Fassung

- Projektziel, Umfang und Rollen festgehalten.
- Anbieterentscheidung und Sprachumfang dokumentiert.
- UX- und Editor-Konzept beschrieben.
- technische Architektur und Datenmodell vorgeschlagen.
- Sicherheits-, Kosten- und Qualitätsanforderungen ergänzt.
- Umsetzungsphasen mit Abnahmekriterien definiert.
- offene Serverentscheidungen und nächste Aufgabe festgehalten.

### 2026-07-22 – Phase-0-Grundgerüst

- Django-5.2-LTS-Projekt mit eigenem User-Modell und erster Migration angelegt.
- PostgreSQL, Redis, Webprozess und Celery-Worker in Docker Compose beschrieben; FFmpeg ist im Anwendungsimage enthalten.
- Secret-freie Beispielkonfiguration, Git-/Docker-Ausschlüsse, Healthchecks und Prüfskripte ergänzt.
- Git-Repository mit Hauptbranch `main` initialisiert und Compose-Datei syntaktisch geprüft.
- ruhige, responsive und tastaturtaugliche Startansicht als überprüfbarer Systemzustand umgesetzt.
- Migrationen, vier Tests, Systemcheck, Asset-Build und Browserdarstellung lokal erfolgreich geprüft.
- fehlendes Docker auf dem Entwicklungsrechner und weiterhin offene Zielserverfragen transparent dokumentiert.
- nächste konkrete Aufgabe auf Phase 1 aktualisiert.

### 2026-07-22 – Phasen 1 bis 6 lokal weitergeführt

- Authentifizierung, Erstpasswortwechsel, temporärer Passwortreset, Sperrung und Anmelderatenbegrenzung umgesetzt.
- eigentümergeschützte Projektübersicht und responsiven Zwei-Spalten-Editor mit Autosave, Sprecher- und Segmentverwaltung umgesetzt.
- ElevenLabs-Adapter und Stimmenkatalog gegen die aktuelle offizielle API modelliert und vollständig gemockt getestet.
- Projektversionen, Verbrauchsreservierung, Nutzer-/Organisationslimits, Celery-Teile, FFmpeg-Zusammenbau, Audiozugriff und Löschroutine implementiert.
- geschlossenes Schema und explizite Änderungsmodi für spätere KI-Vorschläge einschließlich Rückgängig umgesetzt.
- CSP, Sicherheitsheader, Betriebsleitfaden, Pilotcheckliste und Caddy-Beispiel ergänzt.
- 39 Tests sowie Desktop-/Mobilfluss, Autosave, Fokus und horizontale Reflow-Eigenschaften erfolgreich geprüft.
- Löschkaskaden, Service-Berechtigungen, Providergrenzen und ein konfliktfreies Rückgängigmachen nachträglich weiter gehärtet.
- echte Provider-Audios, Compose-Serverbetrieb, MFA, Backup-Restore und pädagogische Sprachqualität ausdrücklich nicht als erledigt markiert.
- nächste konkrete Aufgabe auf den externen Integrationspilot aktualisiert.

### 2026-07-22 – GitHub- und Servervorbereitung

- Ziel-Repository auf `markuspillermusic-hash/sprachplattform` korrigiert.
- geprüften Initialstand auf dem Standardbranch `main` veröffentlicht.
- öffentliche Zieladresse `https://sprachplattform.markuspiller.de` festgelegt.
- Compose-Port ausschließlich an `127.0.0.1:8085` gebunden und Reverse-Proxy-Beispiel angepasst.
- secret-freie Produktionsumgebungsvorlage und konkrete Serverhinweise ergänzt.
