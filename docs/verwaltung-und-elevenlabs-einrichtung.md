# Verwaltung und ElevenLabs-Einrichtung

Stand: 30. Juli 2026

Diese Anleitung beschreibt die nächsten Schritte, um die Sprachplattform für einen Pilotbetrieb einsatzbereit zu machen. Sie enthält absichtlich keine Passwörter, API-Schlüssel oder andere Geheimnisse.

## Ausgangslage

- Plattform: <https://sprachplattform.markuspiller.de>
- Verwaltung: <https://sprachplattform.markuspiller.de/admin/>
- Proxmox-VM: `105` (`sprachplattform`)
- Installationsordner auf der VM: `/opt/sprachplattform`
- Webserver und Reverse Proxy: Container `101`

## Was wird wo eingerichtet?

| Einstellung | Ort |
| --- | --- |
| ElevenLabs-API-Schlüssel | `.env` auf VM `105` |
| ElevenLabs-Modell | `.env` auf VM `105` |
| Stimmen von ElevenLabs einlesen | Serverkonsole auf VM `105` |
| Stimmen prüfen und freischalten | Django-Verwaltung |
| Benutzer anlegen und sperren | Django-Verwaltung |
| Persönliche Nutzungslimits | Django-Verwaltung |
| Generierungen und Nutzung kontrollieren | Django-Verwaltung |
| Organisationsweite Standardlimits | `.env` auf VM `105` |

Geheimnisse niemals in Git, Chats, Tickets, Screenshots oder die Django-Verwaltung kopieren.

## 1. ElevenLabs-API-Schlüssel erstellen

1. Bei ElevenLabs anmelden.
2. Den Bereich **Developers → API Keys** öffnen.
3. Einen neuen eingeschränkten Schlüssel mit einem eindeutigen Namen wie `sprachplattform-prod` erstellen.
4. Mindestens Berechtigungen für **Text to Speech/Text to Dialogue** und lesenden Zugriff auf **Voices** vergeben. Die genaue Bezeichnung kann sich in der ElevenLabs-Oberfläche unterscheiden.
5. Wenn ElevenLabs es anbietet, ein sinnvolles Credit- oder Nutzungslimit für den Schlüssel setzen.
6. Den Schlüssel sicher zwischenspeichern. Er wird nur einmal auf der Serverkonsole benötigt.

Bei einer IP-Einschränkung muss die öffentliche IP des Internetanschlusses eingetragen werden, nicht die interne Adresse `192.168.2.21`. Eine IP-Einschränkung ist nur sinnvoll, wenn die öffentliche IP dauerhaft gleich bleibt.

Offizielle Dokumentation:

- [ElevenLabs: API-Schlüssel verwalten](https://elevenlabs.io/docs/overview/administration/workspaces/api-keys)
- [ElevenLabs: Text to Dialogue](https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue)
- [ElevenLabs: Stimmen suchen](https://elevenlabs.io/docs/api-reference/voices/search)

## 2. API-Schlüssel und Modell auf dem Server hinterlegen

In Proxmox die Konsole der VM `105` öffnen und als Benutzer `deploy` anmelden:

```sh
cd /opt/sprachplattform
sudo nano .env
```

Die folgenden Einträge suchen oder ergänzen:

```dotenv
ELEVENLABS_API_KEY=HIER_DEN_ECHTEN_SCHLUESSEL_EINTRAGEN
ELEVENLABS_BASE_URL=https://api.elevenlabs.io
ELEVENLABS_MODEL_ID=eleven_v3
TTS_ESTIMATED_EUR_PER_1000_CHARACTERS=0.18
AUDIO_TAIL_FADE_MS=45
AUDIO_TAIL_PADDING_MS=80
```

In Nano speichern:

1. `Strg` + `O`
2. mit `Enter` bestätigen
3. `Strg` + `X`

Danach die Dateiberechtigung absichern und Webanwendung sowie Worker neu erstellen:

```sh
sudo chmod 600 .env
sudo docker compose up -d --force-recreate web worker
sudo docker compose ps
```

Erwartetes Ergebnis: `web` und `worker` stehen auf `Up`; die Dienste `web`, `db` und `redis` sind nach kurzer Startzeit gesund.

## 3. Stimmen von ElevenLabs einlesen

Für die fünf vorgesehenen Sprachen:

```sh
cd /opt/sprachplattform
for language in de en fr es it; do
  sudo docker compose exec -T web python manage.py sync_provider_voices --language "$language"
done
```

Die eingelesenen Stimmen bleiben zunächst absichtlich deaktiviert. Bei `401` oder `403` zuerst API-Schlüssel und ElevenLabs-Berechtigungen prüfen. Den Schlüssel nicht zur Fehlersuche weitergeben oder in einen Screenshot aufnehmen.

## 4. Geeignete Stimmen freischalten

1. <https://sprachplattform.markuspiller.de/admin/> öffnen.
2. Mit dem Administratorkonto anmelden.
3. Im Bereich **TTS** die **Provider Voices/Provider-Stimmen** öffnen.
4. Nach dem Modell `eleven_v3` filtern.
5. Sprache, Bezeichnungen und – falls vorhanden – die Vorschau jeder Stimme prüfen.
6. Für den Anfang nur etwa zwei bis vier geeignete Stimmen je Sprache aktivieren.

Die Felder für Provider, Modell, Stimmen-ID und Sprachen nicht manuell umschreiben. Diese Angaben stammen aus der Provider-Synchronisierung.

## 5. Erste echte Audiogenerierung testen

1. Zur normalen Anwendung wechseln.
2. Ein deutsches Testprojekt anlegen.
3. Zwei Sprecher hinzufügen und zwei freigegebene Stimmen auswählen.
4. Einen kurzen Dialog mit ungefähr 200 bis 400 Zeichen eingeben.
5. Die Generierung starten.
6. Wiedergabe und Download prüfen.
7. Danach einen längeren Text mit mehr als 2.000 Zeichen testen. Damit werden auch Aufteilung und Zusammenbau der Audiodateien geprüft.

Falls ein Test fehlschlägt, in der Verwaltung zuerst den zugehörigen Generierungsauftrag ansehen. Providerfehler sollten dort ohne geheimen API-Schlüssel erscheinen.

Beim Zusammenbau erhält jede TTS-Phrase standardmäßig einen 45 ms langen Ausklang und 80 ms stille Endpolsterung. Damit werden harte Schnitte und Klickgeräusche vermieden. Beide Werte lassen sich über `AUDIO_TAIL_FADE_MS` und `AUDIO_TAIL_PADDING_MS` in der Server-`.env` anpassen.

## 6. Betrieb in der Verwaltung kontrollieren

Die wichtigsten Bereiche sind:

- **Generation Jobs/Generierungsaufträge:** Status, Fortschritt und bereinigte Fehlermeldungen
- **Usage Ledgers/Nutzungsübersichten:** verbrauchte und reservierte Zeichen
- **Audio Assets/Audiodateien:** erzeugte Dateien und Ablaufdatum
- **Project Versions/Projektversionen:** unveränderliche Grundlage einer Generierung

Aktuell vorgesehene Standardwerte:

- persönliches Monatslimit: `30.000` Zeichen
- Organisationslimit pro Monat: `600.000` Zeichen
- Organisationslimit pro Jahr: `7.200.000` Zeichen
- Audio-Aufbewahrung: `30` Tage
- interner Tarifwert: `0,18 EUR` pro 1.000 Zeichen

Der angezeigte Eurobetrag ist ein anteiliger Schätzwert zur internen Planung, keine zusätzliche Einzelabbuchung. Innerhalb des ElevenLabs-Monatskontingents entstehen normalerweise nicht für jeden Auftrag gesonderte Kosten. Nach Tarifwechseln sollte der Wert mit dem effektiven Preis je 1.000 Credits verglichen und bei Bedarf angepasst werden.

## 7. Pilotbenutzer anlegen

1. In der Verwaltung **Accounts → Users/Benutzer** öffnen.
2. **Benutzer hinzufügen** wählen und den Benutzernamen eintragen.
3. Ein frei gewähltes Startpasswort zweimal eingeben. Es gibt bewusst keine Vorgaben zu Länge, Zeichenarten oder häufig verwendeten Passwörtern.
4. Rolle und persönliches Monatslimit festlegen, zum Beispiel zunächst `10.000` Zeichen.
5. Speichern und das Startpasswort sicher an die betreffende Person übermitteln.
6. Beim ersten Login wird automatisch ein persönliches Passwort verlangt; diese Vorgabe kann beim Anlegen nicht versehentlich abgeschaltet werden.
7. **Aktiv** eingeschaltet lassen. **Mitarbeiterstatus** und **Superuserstatus** bleiben für Lehrkräfte ausgeschaltet.

Für einen späteren Passwort-Reset steht weiterhin die Verwaltungsaktion **Neue temporäre Passwörter erzeugen** zur Verfügung. Auch dieses Passwort muss beim nächsten Login geändert werden.

Lehrkräfte arbeiten ausschließlich in der normalen Plattform. Die Django-Verwaltung bleibt Administratoren vorbehalten.

## 8. Noch keine LLM-API einrichten

Der KI-Assistent ist technisch noch nicht vollständig an einen LLM-Anbieter angebunden. Deshalb aktuell keinen OpenAI-, Anthropic- oder anderen LLM-Schlüssel hinterlegen. Die produktive Einrichtung dafür erfolgt erst, nachdem Anbieter, Modell, Kostenlimit und Datenschutzentscheidung festgelegt und die Integration implementiert wurden.

## Checkliste für den ersten Pilot

- [ ] eingeschränkten ElevenLabs-API-Schlüssel erstellt
- [ ] API-Schlüssel und `eleven_v3` in der Server-`.env` hinterlegt
- [ ] `web` und `worker` neu erstellt und Zustand geprüft
- [ ] Stimmen für Deutsch, Englisch, Französisch, Spanisch und Italienisch synchronisiert
- [ ] wenige geeignete Stimmen je Sprache freigeschaltet
- [ ] kurze Generierung erfolgreich abgespielt und heruntergeladen
- [ ] lange Generierung mit Textaufteilung erfolgreich geprüft
- [ ] mindestens einen normalen Pilotbenutzer mit niedrigem Limit angelegt
- [ ] Nutzungsübersicht und ElevenLabs-Verbrauch nach dem Test verglichen

Vor einer größeren Freigabe bleiben außerdem SMTP beziehungsweise ein sicherer Einladungsweg, Admin-MFA, die endgültige Audio-Aufbewahrungsfrist und eine pädagogische Qualitätsprüfung aller fünf Sprachen zu klären.
