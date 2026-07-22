# Quellen- und Rechennotizen: TTS-Plattform für 20 Lehrkräfte

Stand: 22. Juli 2026 (Europe/Berlin)

## Entscheidungsfrage

Welche Lösung ermöglicht etwa 20 Sprachlehrkräften ein Jahr lang die zuverlässige Erzeugung von Audio für Hörverstehensaufgaben innerhalb eines Budgets von 1.800 EUR: ein ElevenLabs-Mehrnutzerkonto, ein eigenes Portal mit verwalteter TTS-API oder ein selbst betriebenes Modell?

## Rechenmodell

- 20 Lehrkräfte, 10 aktive Schulmonate.
- Niedrig: 2 Audios je Lehrkraft und Monat zu je 5 Minuten.
- Typisch: 5 Audios je Lehrkraft und Monat zu je 5 Minuten.
- Hoch: 10 Audios je Lehrkraft und Monat zu je 5 Minuten.
- 800 Zeichen pro Audiominute als konservative Arbeitsannahme für westliche Sprachen.
- 30 Prozent Aufschlag für Neu-Generierungen, Korrekturen und Varianten.
- Umrechnung: 1 USD = 0,875810 EUR, abgeleitet aus 1 EUR = 1,1418 USD (EZB-Referenzkurs vom 21. Juli 2026).
- Anbieterpreise sind Listenpreise vor Steuern; Wechselkurs, Umsatzsteuer, Freikontingente und individuelle Rabatte sind nicht eingerechnet.

## Preisquellen

- ElevenLabs API: Flash/Turbo 0,05 USD je 1.000 Zeichen; Multilingual v2/v3 0,10 USD je 1.000 Zeichen. https://elevenlabs.io/pricing/api
- ElevenLabs Mehrnutzerpläne: Scale 299 USD/Monat mit 3 Plätzen, Business 990 USD/Monat mit 10 Plätzen; Jahresabrechnung entspricht zehn Monatsraten; Enterprise individuell. https://elevenlabs.io/pricing
- Alibaba Model Studio: Qwen Audio 3.0 Plus 0,20 USD je 10.000 Zeichen; Qwen3-TTS Instruct Flash 0,115 USD je 10.000 Zeichen. https://www.alibabacloud.com/help/en/model-studio/model-pricing
- Google Chirp 3 HD: 30 USD je 1 Mio. Zeichen. https://cloud.google.com/text-to-speech/pricing
- Amazon Polly Generative: 30 USD je 1 Mio. Zeichen; Neural: 16 USD je 1 Mio. Zeichen. https://aws.amazon.com/polly/pricing/
- Azure Speech Neural: 15 USD je 1 Mio. Zeichen laut aktueller Quoten-/Kostenbeispieldokumentation. https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-services-quotas-and-limits

## Funktions- und Datenschutzquellen

- Qwen Audio 3.0 Systemstimmen: Mandarin und Englisch; weitere Sprachen einschließlich Deutsch/Französisch über geklonte Stimmen. Qwen3-TTS Systemstimmen: zehn Sprachen einschließlich Deutsch, Englisch, Französisch, Italienisch, Portugiesisch und Spanisch. https://www.alibabacloud.com/help/en/model-studio/tts-model/
- Alibaba Model Studio: Qwen-TTS ist international in Singapur verfügbar; EU-Datenresidenz ist nur für Modelle verfügbar, die in Frankfurt/EU angeboten werden. https://www.alibabacloud.com/help/en/model-studio/regions/
- ElevenLabs: Standarddatenhaltung in den USA; EU-Datenresidenz und Zero Retention sind Enterprise-Funktionen. https://elevenlabs.io/docs/overview/administration/data-residency
- Azure Speech: Verarbeitung und Speicherung erfolgen in der Region der Speech-Ressource. https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions
- Google Cloud TTS: EU-Endpunkt hält Daten bei Speicherung und Verarbeitung in Europa; Chirp 3 HD ist im EU-Multiregion-Endpunkt verfügbar. https://docs.cloud.google.com/text-to-speech/docs/endpoints
- AWS Polly Generative ist unter anderem in Frankfurt verfügbar. https://docs.aws.amazon.com/polly/latest/dg/generative-voices.html
- Qwen3-TTS Open Source: Apache-2.0, Modelle mit 0,6B und 1,7B Parametern. https://github.com/QwenLM/Qwen3-TTS

## Qualitative Unsicherheit

Sprachqualität ist nicht aus Preistabellen ableitbar. Die Empfehlung setzt deshalb einen kleinen Blindtest mit authentischen Unterrichtstexten voraus. Anbieterangaben zu Natürlichkeit werden nicht als unabhängiger Qualitätsnachweis behandelt.

## Berichtstruktur

- Required Structure des Executive Reports: Titel; Executive Summary; Befunde mit Visual; nächste Schritte; offene Fragen; Annahmen und Einschränkungen.
- Visual: horizontaler Balkenvergleich der jährlichen API-Kosten im typischen Szenario; die Balken starten bei null.
- Tabellen: Kosten je Nutzungsszenario; Vergleich der drei Betriebsmodelle; Anbieter-/Datenschutzmatrix.
- Kein Trenddiagramm: Es gibt drei diskrete Szenarien, keine Zeitreihe.
