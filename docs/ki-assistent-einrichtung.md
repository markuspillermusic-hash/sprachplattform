# KI-Assistent einrichten und verwenden

## OpenAI im Adminbereich verbinden

1. Als Administrator anmelden und **Verwaltung** öffnen.
2. Unter **Skript-Assistent** den Punkt **KI-Anbindung** öffnen.
3. Falls noch kein Eintrag existiert, **KI-Anbindung hinzufügen** wählen.
4. Den persönlichen OpenAI-API-Schlüssel in das Passwortfeld einfügen.
5. Als Standardmodell zunächst **GPT-5.6 Luna · sparsam** verwenden. Terra und Sol sind für höhere Qualitätsanforderungen auswählbar.
6. **Sichern** wählen.
7. In der Liste den Eintrag markieren und unter **Aktion** den Punkt **OpenAI-Verbindung für Auswahl prüfen** ausführen.

Die Prüfung ruft nur die Modellinformation ab und erzeugt keinen Hörtext. Nach dem Speichern wird der API-Schlüssel nicht mehr vollständig angezeigt. Ein leeres Schlüsselfeld behält den vorhandenen Schlüssel bei; die gesonderte Checkbox entfernt ihn.

## Hörtext mit KI-Unterstützung erstellen

1. **Hörtexte → Neuer Hörtext** öffnen.
2. **Mit KI-Unterstützung erstellen** wählen.
3. Sprache, Niveau, Textart, Thema, Länge und Sprecherzahl festlegen.
4. Optional Wortschatz, Grammatikziel, Rollen oder weitere Vorgaben ergänzen.
5. **Entwurf erstellen** wählen.
6. Den Entwurf prüfen, über die Schnellvorschläge oder einen eigenen Änderungswunsch überarbeiten und anschließend ausdrücklich übernehmen.
7. Im Editor Stimmen prüfen, den Text bei Bedarf manuell ändern und erst danach das Audio erzeugen.

Die Plattform verändert einen bestehenden Hörtext niemals allein durch eine KI-Anfrage. Erst **Entwurf übernehmen und bearbeiten** ersetzt den Inhalt. Solange anschließend nichts manuell geändert wurde, kann die letzte KI-Übernahme im Editor rückgängig gemacht werden.

## Stimmenzuordnung

Nach der Übernahme verwendet die Plattform nur aktive Stimmen, die zur Zielsprache passen. Persönliche Favoriten werden zuerst vergeben; bei mehreren Rollen werden nach Möglichkeit unterschiedliche Stimmen gewählt. Die Zuordnung kann vor der Audiogenerierung jederzeit im Editor geändert werden.

## Sicherheit und Betrieb

- Der OpenAI-Schlüssel wird serverseitig verschlüsselt gespeichert und weder an Browser noch Nutzer ausgeliefert.
- Die Verschlüsselung hängt am `DJANGO_SECRET_KEY`. Dieser Schlüssel muss sicher gesichert und bei einer Wiederherstellung beibehalten werden.
- Jede KI-Anfrage wird mit Nutzer, Modell sowie Ein- und Ausgabetokens protokolliert; der API-Schlüssel und die vollständige Providerantwort werden nicht protokolliert.
- An OpenAI werden nur die Angaben des Erstellungsdialogs und gegebenenfalls der zu überarbeitende Hörtext geschickt. Personenbezogene Schülerdaten sollten dort nicht eingegeben werden.
- Bei `401` den Schlüssel ersetzen und erneut testen. Bei `429` wurden das OpenAI-Guthaben oder ein Rate-Limit erreicht.
