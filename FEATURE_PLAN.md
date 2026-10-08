# TankFlix: Karte, Preisvergleich und Bedienung

Implementierter Plan aus der Feature-Abstimmung. Alle Punkte sind umgesetzt; die Tests verwenden isolierte Beispieldaten und simulieren externe Dienste.

## Karte und Tabelle verbinden

- [x] „Auf Karte zeigen“ pro Tabellenzeile: Karte öffnen, Standort zentrieren, Marker hervorheben, Popup öffnen.
- [x] Auswahl in beide Richtungen: Marker wählt Tabellenzeile; „Zur Liste“ scrollt und setzt den Tastaturfokus.
- [x] Deutliche gemeinsame Auswahl; bleibt bei Sortierung, Filterwechsel und Kraftstoffwechsel erhalten. Ausgefilterte Auswahl bleibt gespeichert, wird aber nicht auf der Karte angezeigt.
- [x] Preis des aktiven Kraftstoffs direkt auf den Markern; Name und Adresse im Popup.
- [x] „Günstigste“-Kennzeichnung in Karte und Liste für alle Bestpreis-Gleichstände.
- [x] Schnellaktion „Günstigste auf Karte anzeigen“; bei Gleichstand wird nach Luftlinie entschieden.

## Vergleich und Orientierung

- [x] Ein gemeinsamer gefilterter Datensatz für Karte, Liste und Favoritenvergleich.
- [x] Textsuche nach Name, Marke, Straße und Ort.
- [x] Sichtbare Sortierung nach Preis, Luftlinie oder Favoriten zuerst.
- [x] Routenlinks in Tabellenzeile, Popup, Favoritenvergleich und Detailansicht.
- [x] Entfernungen ausdrücklich als Luftlinie gekennzeichnet.
- [x] Markergruppen mit Anzahl und Mindestpreis; Aktivierung zeigt die enthaltenen Stationen einzeln. Ausgewählte Stationen bleiben außerhalb von Gruppen.

## Mobile Nutzung und Bedienbarkeit

- [x] Karte ein- und ausklappbar; gespeicherter Zustand innerhalb des Tabs.
- [x] Kraftstoffwechsel und Schnellaktionen beim Scrollen erreichbar.
- [x] Mobile Darstellung der Tabelle als Tankstellenkarten.
- [x] Text, Symbole und Umrandung zusätzlich zur Farbe; Filter, Aktionen und Marker per Tastatur bedienbar. Dialog schließt mit Escape; reduzierte Bewegung wird berücksichtigt.
- [x] Kartenlegende für Preise, Bestpreis, Auswahl und Gruppen.

## Datenqualität und Entscheidungshilfen

- [x] Letzter erfolgreicher Abruf und veraltete Preise sichtbar. Zwischengespeicherte Antworten behalten den tatsächlichen Preisstand und erzeugen keine doppelte Historie.
- [x] Unterschiedliche Hinweise für fehlenden API-Key, Abruffehler, erfolgreichen Abruf ohne Treffer und Filter ohne Treffer.
- [x] Detailansicht mit Preisverlauf über 24 Stunden, 7 oder 30 Tage, Min/Max und Messwerttabelle; klare Zustände bei fehlenden Daten und Ladefehlern.
- [x] Favoritenvergleich mit eigenem Bestpreis und Schnellaktion, passend zu Kraftstoff und Filtern.
- [x] Alarmdetails mit Preisgrenze, vorigem Messwert, Änderung in Cent und Änderungsschwelle; aktuelle Bedingungen vom bestätigten Teams-Versand unterschieden.

## Validierung und Betriebsgrenzen

- 12 Backend-/HTTP-Tests: Historien-API, Kraftstofftrennung, Eingabevalidierung, sichere Datenübergabe, Admin/CSRF/Speichern/Logout, Abrufzustände, Cache-Zeitstempel, Fehlererhalt, erfolgreiche leere Antworten, additive Schemaerweiterung und Alarm-Deduplizierung.
- 11 Chromium-Browserprüfungen: Desktop/Mobil, Karte ↔ Liste, Gleichstände, Filter/Sortierung/Suche, Favoriten, Kraftstoffwechsel, Tastatur, Diagramm/Zeiträume/Retry, leere und einzelne Messwerte, Storage- und Kartenfehler, sichere Stationsnamen und Alterungskennzeichnung.
- 4 JavaScript-Tests: Filterkombinationen, Sortierung/Favoriten, Bestpreis-Gleichstände und Gruppen/individuelle Auswahl.
- Bestehender Onboarding-Smoke-Test mit 14 Funktionsprüfungen lief während der Umsetzung ebenfalls erfolgreich.
- Live-Tankerkönig-Daten, echte Teams-Zustellung und tatsächliche Google-Maps-Routen wurden nicht extern getestet. Kartenkacheln wurden in den Browserprüfungen simuliert; echtes Leaflet und die Anwendung liefen lokal.
- Keine bestehenden Anwendungstabellen geändert. `fetch_status` wird zusätzlich beim Start angelegt. Historie, Konfiguration und Admin-Daten bleiben bestehen.
- Leaflet ist lokal mit BSD-Lizenz und geprüftem Herkunftsnachweis eingebunden. Der Kartenhintergrund benötigt weiterhin OpenStreetMap-Zugriff.

Testbefehle und Bedienung: siehe [README.md](README.md).
