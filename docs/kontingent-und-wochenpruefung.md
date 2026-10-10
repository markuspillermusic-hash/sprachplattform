# Kontingentanzeige und wöchentliche Modellprüfung

Stand: 10. Oktober 2026. Die derzeitigen Modelle bleiben aktiv. Neue Modelloptionen und mögliche Limitänderungen werden wöchentlich bewertet; ohne eigene Freigabe erfolgt keine automatische Umstellung oder Budgeterhöhung.

## Sichtbare Kontingente

Der Menüpunkt **Kontingent** führt zu `/kontingent/`. „Meine Hörtexte“ enthält zusätzlich drei kompakte Monatsbalken für Sprache und KI-Tokens. Die vollständige Seite zeigt Sprache, Eingabe-/Ausgabetokens, tägliche KI-Anfragen und freigegebene Musik-/Geräuscherzeugung. Laufende Reservierungen sind gesondert ausgewiesen und zählen bereits gegen den Rahmen. Freigegebene Reservierungen zählen nicht weiter; tatsächlich gemeldete Anbietercredits ersetzen Schätzwerte.

Persönliche Monatskontingente erneuern sich am ersten Kalendertag des Folgemonats um 00:00 Uhr in Europe/Berlin. Tägliche Anfragen erneuern sich am folgenden Tag. Temporäre Schülerzugänge haben ein Gesamtbudget über die Zugangslaufzeit und erhalten keinen erfundenen monatlichen Reset. Quelldauer und lokal verlängerte Abspieldauer bleiben bei Studio-Geräuschen getrennt: Bibliotheksnutzung erzeugt keinen neuen Anbieterauftrag.

Aktive Mitarbeiter mit `usage_control.view_providerbudget` sehen zusätzlich die gemeinsamen Plattformbudgets, auch im bestehenden Admin-Nutzungsmonitoring. Reguläre Lehrkräfte und Schüler sehen diese Daten nicht. Die Kontingentseite akzeptiert keine fremde Nutzer-ID und ist nicht öffentlich zwischenspeicherbar.

ElevenLabs zählt Sprache, Musik und Geräusche gemeinsam in Credits. Der Balken verwendet den konfigurierten Plattformrahmen abzüglich Sicherheitsreserve und ausschließlich Plattformbuchungen. Er ist keine synchronisierte Anzeige des gesamten Anbieterkontos: andere Anwendungen, Guthabenüberträge und Zukäufe werden nicht automatisch berücksichtigt. OpenAI verwendet den vorhandenen dynamischen Monatsrahmen in seiner Abrechnungswährung; unverbrauchtes Geld wird auf die verbleibenden Monate verteilt. Ein Gesamtbudget ohne Monatsverteilung erhält kein monatliches Resetdatum.

Der vom Nutzer genannte **16. September** ist die jährliche Verlängerung seines ElevenLabs-Abos. Die [offizielle Abrechnungshilfe](https://elevenlabs.io/docs/overview/administration/billing) unterscheidet Jahreszahlung von Credit-Erneuerung: reguläre Self-Service-Jahresabos erhalten monatliche Credits; Enterprise-Jahrespläne können abweichen. Die [Reset-Hilfe](https://elevenlabs.io/docs/help-center/account/general/when-do-my-credits-reset) beschreibt den ursprünglichen Anmeldetag und die ungefähre Anmeldeuhrzeit als monatlichen Anker. Der 16. ist für dieses Konto dennoch nicht bestätigt. Die lesende Abfrage `GET /v1/user/subscription` wurde mit dem bestehenden Schlüssel versucht und mit HTTP 401 abgelehnt. Es wurden keine Berechtigungen erweitert.

Deshalb bleibt `credit_cycle_day=0` erhalten: vorsichtiges gleitendes 31-Tage-Fenster und sichtbarer Hinweis „Anbieter-Rücksetzdatum noch nicht bestätigt“. Sobald der tatsächliche monatliche Erneuerungstag aus der Kontoanzeige oder aus `next_character_count_reset_unix` bestätigt ist, kann er eingetragen werden. Es wird weder der Monatsanfang noch der 16. aus dem Jahresdatum geraten. Bei bekannten Tagen 29–31 werden kurze Monate berücksichtigt; der ursprüngliche Tag bleibt für den Folgemonat erhalten. Endet ein Budget vorher, wird kein weiter gültiger Reset versprochen.

## Gemeinsame Verbrauchsberechnung

Die Anzeige und die persönliche Sprachbegrenzung verwenden `UsageEvent` für aktuelle Aufträge. Ältere `UsageLedger` ohne verknüpfte Verbrauchsbuchung werden zusätzlich berücksichtigt, moderne Aufträge nicht doppelt. Dadurch bleiben Reservierungen sichtbar und freigegebene moderne Reservierungen erhöhen das persönliche Kontingent wieder, auch wenn ein alter Ledger-Snapshot des Auftrags existiert. Historische Buchungen werden nicht gelöscht oder verändert. Die zusätzliche Organisationsgrenze und Anbieterbudgets bleiben bestehen.

Native `progress`-Elemente zeigen Prozentwerte mit gültigen HTML-Zahlen unabhängig von deutscher Dezimalformatierung. Null-Limits bedeuten „Nicht verfügbar“, keine unbegrenzte Nutzung; Überziehungen zeigen die tatsächliche Prozentzahl bei begrenztem Balken. Die Seite braucht keine JavaScript- oder Anbieteranfrage. CSS kommt aus lokalen Dateien unter der bestehenden CSP.

## Wöchentliche Prüfung

Zeitpunkt: **montags um 09:00 Uhr**, lokale Zeitzone Europe/Berlin, als Codex-Heartbeat an diesen Chat gebunden. Der Rechner beziehungsweise Codex muss für die lokale Ausführung verfügbar sein; es handelt sich nicht um einen auf dem Server installierten Scheduler.

Die Prüfung liest die tatsächlich konfigurierten Modelle und vergleicht sie mit offiziellen Herstellerquellen auf Verfügbarkeit, Kompatibilität, Preise, Qualitätsverbesserungen und Abkündigungen. Die Nutzungsanalyse enthält Monat und letzte sieben Tage nach Anbieter, Funktion und Modell, aktive Nutzer, laufende Reservierungen, freigegebene Reservierungen, persönliche Engpässe, gemeinsame Rahmen und Bibliotheksbedarf. Namen, Texte, Prompts und Schlüssel sind kein Bestandteil des aggregierten Berichts.

Lesender Serverbefehl:

```sh
cd /opt/sprachplattform
sudo docker compose exec -T web python manage.py usage_review
```

Optional `--date YYYY-MM-DD` für einen Stichtag. Dieser Befehl verändert weder Budgets noch Buchungen und ruft keine Anbieter-API auf. Der aktuelle Bericht und der vorherige Prüfstand werden lokal unter dem ignorierten Ordner `var/weekly-review/` aufbewahrt. Vergleich und Empfehlungen müssen die kurze Beobachtungsdauer, Monats-/Anbieterzyklen und unterschiedliche Währungen berücksichtigen. Der Bericht ist aggregiert; er rekonstruiert keine historischen Benutzerlimits oder Anbieterbudgets, wenn diese zwischenzeitlich geändert wurden.

Die Automation meldet nur handlungsrelevante Modelländerungen, Abkündigungen, Engpässe oder neue Prüfprobleme. Bei unverändertem Stand bleibt sie still. Empfehlungen nennen konkrete neue Limits, die zugrunde liegende Nachfrage und die erwarteten Kostenfolgen. Es erfolgt keine automatische Budgeterhöhung, kein Guthabenkauf und keine kostenpflichtige Probeproduktion.

## Prüfung und Veröffentlichung

Regressionen decken Monats-/Jahreswechsel, kurze Monate, unbekannte Anbietertermine, Reservierungen, tatsächliche Credits, dynamische Geldrahmen, Null-Limits, Überziehungen, Schülerlaufzeiten, Nutzerrechte und doppelte historische Buchungen ab. Zusätzlich wird die Seite auf Desktop und in schmaler Ansicht geprüft. Der Veröffentlichungsstand wird nach der Serverabnahme ergänzt.
