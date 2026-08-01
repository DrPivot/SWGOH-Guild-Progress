# SWGOH Guild Progress Analyzer 🌟

Eine umfassende Analyseanwendung für Star Wars Galaxy of Heroes Gildendaten der **BΛ Bataillon Allianz**.

Ermöglicht Multi-Player-Vergleiche über verschiedene Zeitpunkte hinweg basierend auf HotBots CSV-Exporten.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://swgoh-guild-progress.streamlit.app/)

## Features

### 🎯 Gilden-Management
- **Allianz-Zugriff**: Nur für Gilden der BΛ Bataillon Allianz
- **Multi-Zeitpunkt-Analyse**: Vergleiche von bis zu 2 historischen Datenpunkten
- **CSV Upload**: Zusätzliche Daten können hochgeladen werden
- **CSV-Verschlüsselung**: Gildendaten im Repository verschlüsselt (Fernet AES-128)
- **Benchmark-Basis**: Vergleich gegen All Guilds, Top 100 Guilds, Top 1000 Kyber oder die eigene Gilde
- **Era-Filter**: Units können zusätzlich nach Era bzw. Conquest-Zuordnung gefiltert werden
- **Player Highlighting**: Einzelne Spieler lassen sich tab-übergreifend farblich hervorheben
- **Color Coding**: Jeder Spieler erhält eine eindeutige Farbe für Vergleiche

### 📊 Analyse-Tabs

#### Guild Relics
- Filterung nach Combat Type (Characters/Ships), Era, Alignment, Kategorie, Rolle und Ability Classes
- Benchmark-basierte Zielwerte für Characters und gildenbasierte Zielwerte für Ships
- Optionale Benchmark-Filterung direkt auf den angezeigten Unit-Pool
- **OR/AND Toggle**: Flexible Filterlogik für Categories und Ability Classes
- **Relic Cost Calculator**: Zeigt benötigte Materialien für Relic-Upgrades
  - Berücksichtigt Player Relic Level vs. Recommended Level
  - Aufgeteilt in Signal Data (4 Typen) und Scrap Materials (11 Typen)
- Besitz-Übersicht der Gilde inklusive Era-Spalte und Relic-Verteilung

#### Guild Stats
- Statistische Auswertung für den aktuell gefilterten Unit-Pool
- Vergleich des markierten Spielers gegen Median, Durchschnitt und Max der Gilde
- Unterstützt Speed, Health, Protection, Effective H+P, Damage, Crit-Werte, Potency und Tenacity

#### Progress
- Vergleich mehrerer Datenstände für Relics, Omicrons, Speed Mods und Mod6
- Einheitlicher Benchmark-Filter mit gemeinsamem Session-State über Sidebar und Progress-Tab
- Delta-Auswertung pro Spieler gegenüber einem auswählbaren Vergleichsdatum

#### Char Stats
- Interaktive Balkendiagramme für 10 Statistiken eines ausgewählten Characters
- Spieler können per Klick in Tabelle und Charts farblich markiert werden
- Optimierte Performance für große Gilden-Roster

#### Mod Distribution
- Analyse von Mod Primaries oder Mod Sets auf dem aktuell gefilterten Character-Pool
- Sortierung nach Gesamtwert, Spielernamen oder einzelner Stat
- Durchschnittszeile und farbliche Hervorhebung ausgewählter Spieler

#### App-Info
- Integriertes Benutzerhandbuch, technische Kennzahlen und Troubleshooting-Hinweise

### 🚀 Performance-Optimierungen
- Session State Caching für Validierung
- Dictionary Lookups statt DataFrame-Filterung
- Vectorized Pandas Operations
- Chart Coloring optimiert: 1.2s → 15ms (~97% schneller)

## Installation

### Lokale Installation

1. **Repository klonen**:
   ```bash
   git clone https://github.com/DrPivot/SWGOH-Guild-Progress.git
   cd SWGOH-Guild-Progress
   ```

2. **Python Pakete installieren**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Datenstruktur**:
   ```
   SWGOH-Guild-Progress/
   ├── swgoh_guild_progress.py # Hauptanwendung
   ├── helper-scripts/
   │   ├── encrypt_csvs.py             # CSV-Verschlüsselungs-Tool
   │   ├── extract_era_catalog.py      # Era-Daten aus SWGOH.GG HTML extrahieren
   │   ├── extract_relic_benchmarks.py # Benchmark-Daten aus SWGOH.GG HTML extrahieren
   │   └── get_units.py                # Kanonischen Unit-Katalog bauen
   ├── requirements.txt                # Python Dependencies
   ├── ENCRYPTION.md                   # Verschlüsselungs-Dokumentation
   ├── .streamlit/
   │   ├── config.toml                 # Streamlit-Konfiguration (Dark Theme)
   │   └── secrets.toml                # Encryption Key (lokal, nicht committen!)
   ├── assets/                         # Bilder/Logos (optional)
   ├── data/                           # Referenzdaten, Benchmarks und verschlüsselte Gildendaten
   │   ├── hotutils/
   │   │   ├── input/
   │   │   ├── YYYY-MM-DD [Guild]Full.csv.encrypted
   │   │   └── ...
   │   ├── relic_costs_cumulative.json
   │   ├── relic_benchmarks.csv
   │   ├── relic_player_data_raw.csv
   │   ├── unit_era_catalog.csv
   │   ├── unit_list.csv
   │   └── swgoh_gg/                   # lokale Rohdaten für Helper, nicht für das öffentliche Repo gedacht
   │       ├── characters.json
   │       ├── ships.json
   │       ├── relics_all.html
   │       ├── relics_guilds_100.html
   │       ├── relics_kyber_1000.html
   │       ├── Eras/
   │       └── Conquest/
   └── README.md
   ```

## Verwendung

### Lokal starten:
```bash
streamlit run swgoh_guild_progress.py
```

Die Anwendung ist dann unter `http://localhost:8501` verfügbar.

### CSV-Dateiformat (HotBots Export)
Dateinamen müssen folgendem Format entsprechen:
```
YYYY-MM-DD [Guild Name]Full.csv
Beispiel: 2025-11-14 670th GUARD BataillonFull.csv
```

**Verschlüsselung** (empfohlen für Repository):
1. Neue CSV in `data/hotutils/input/` ablegen
2. `python helper-scripts/encrypt_csvs.py` ausführen
3. Verschlüsselte `.csv.encrypted` Datei wird in `data/hotutils/` erstellt
4. Details siehe [ENCRYPTION.md](ENCRYPTION.md)

**Kanonische Unit-Daten aktualisieren**:
1. Lokale SWGOH.GG-Quelldaten in `data/swgoh_gg/` aktualisieren
   - `characters.json` und `ships.json` lokal für die Helper bereitstellen
   - Relic-Benchmark-Seiten lokal als einzelne HTML-Dateien speichern:
      - `data/swgoh_gg/relics_all.html`
      - `data/swgoh_gg/relics_guilds_100.html`
      - `data/swgoh_gg/relics_kyber_1000.html`
   - Era-Seiten lokal als einzelne HTML-Dateien in `data/swgoh_gg/Eras/` ablegen
   - Conquest-Seiten lokal als einzelne HTML-Dateien in `data/swgoh_gg/Conquest/` ablegen
   - Empfohlen ist "Webpage, HTML only" beziehungsweise eine einzelne `.html`-Datei; die Helper lesen nur den HTML-Quelltext und nutzen keine zusätzlichen Ressourcenordner
   - Diese Rohdaten dienen nur der lokalen Vorbereitung und sind per `.gitignore` aus dem öffentlichen Repository ausgeschlossen
2. `python helper-scripts/extract_era_catalog.py` ausführen
3. `python helper-scripts/extract_relic_benchmarks.py` ausführen
4. `python helper-scripts/get_units.py` ausführen
5. Die App nutzt anschließend `data/unit_list.csv` als stabile Datenbasis

Erforderliche Spalten im CSV:
- Name, Galactic_Power, Character_Galactic_Power, Ship_Galactic_Power
- Character/Ship Details: Base_Id, Combat_Type, Alignment, Role, Categories
- Stats: Relic_Tier, Gear_Level, Level, Speed, Health, Protection, etc.
- Mods: Mod_Set_Id, Speed (aus Secondary_N_Value)

### Streamlit Cloud Deployment

1. **Repository auf GitHub pushen** (privates Repo empfohlen)
2. **Streamlit Cloud öffnen**: https://share.streamlit.io/
3. **Secrets konfigurieren** (für verschlüsselte CSVs):
   - App Settings → Secrets
   - Encryption Key hinzufügen:
     ```toml
     [encryption]
     key = "DEIN-FERNET-KEY-HIER"
     ```
   - Key lokal generieren: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
4. **App deployen**:
   - "New app" klicken
   - Repository: `DrPivot/SWGOH-Guild-Progress`
   - Main file: `swgoh_guild_progress.py`
   - Deploy!

**Wichtig**: 
- Für den App-Betrieb müssen die erzeugten CSV-Artefakte und verschlüsselten Gildendaten im Repository enthalten sein
- Rohe SWGOH.GG-JSON- und HTML-Quelldateien werden nur lokal für die Helper benötigt und nicht öffentlich versioniert
- `.streamlit/secrets.toml` ist lokal - für Cloud separate Secrets-Konfiguration
- Encryption Key in beiden Umgebungen gleich halten!

### Navigation

1. **Startbildschirm**:
   - Gilde aus BΛ Bataillon Allianz auswählen
   - Bis zu 2 Datenpunkte (CSV-Dateien) auswählen
   - Optional: CSV hochladen für zusätzliche Daten
   - "Start Analysis" klicken

2. **Analyse-Modus**:
   - Benchmark-Quelle und optionalen Benchmark-Filter wählen
   - Tabs für verschiedene Analysen durchklicken
   - Filter anwenden (Combat Type, Era, Alignment, Kategorie, Rolle, Abilities)
   - Spieler in Tabellen per Klick farblich hervorheben

## Technische Details

- **Framework**: Streamlit 1.60+ (Web-Interface)
- **Datenverarbeitung**: Pandas (optimiert mit vectorized operations)
- **Visualisierung**: Plotly (interaktive Balkendiagramme)
- **Verschlüsselung**: Fernet (AES-128) via `cryptography` Bibliothek
- **Caching**: Session State für Validierung & Player-Daten
- **Metadatenbasis**: Kanonischer Unit-Katalog aus `data/unit_list.csv`
- **Performance**: Chart Rendering <20ms für 10 Charts

### Architektur-Highlights
- **load_guild_data() / get_newest_df() / get_all_dates_df()**: Laden Repository-Daten und optionalen Upload effizient
- **Kanonischer Unit-Katalog**: App-Logik hängt an `data/unit_list.csv`, nicht an wechselnden Rohquellen
- **Helper-Pipeline**: Era- und Benchmark-Daten werden vorab in stabile CSV-Artefakte überführt
- **Transparente Entschlüsselung**: CSV-Decryption direkt im RAM (keine Temp-Dateien)
- **Validation Caching**: Teure unique() Operations nur einmal
- **Dictionary Lookups**: O(1) Player-Farben statt O(n) DataFrame-Zugriffe
- **Vectorized Coloring**: Pandas .map() statt Python-Loops
- **Relic Cost Calculation**: Cumulative JSON-Struktur für effiziente Delta-Berechnung

## Troubleshooting

### Häufige Probleme

1. **"Gilde nicht im Repository gefunden"**:
   - Nur Gilden der BΛ Bataillon Allianz haben Zugriff
   - CSV-Dateien müssen im `data/hotutils/` Ordner liegen
   - Dateiname-Format: `YYYY-MM-DD [Guild Name]Full.csv`

2. **"Keine gemeinsamen Spieler zwischen Upload und Cached-Daten"**:
   - Upload-CSV muss Spieler der ausgewählten Gilde enthalten
   - Validierung prüft Name-Spalte auf Übereinstimmungen

3. **"Charakterdaten konnten nicht geladen werden"**:
   - Für die App selbst muss `data/unit_list.csv` vorhanden sein
   - Falls der kanonische Unit-Katalog neu erzeugt werden muss, werden zusätzlich lokale Quelldateien in `data/swgoh_gg/` von den Helper-Skripten benötigt
   - Falls Referenzdaten fehlen: Helper-Skripte für Era, Benchmarks und Unit-Katalog erneut ausführen

4. **Performance-Probleme**:
   - Erste Datenladung kann länger dauern (mehrere CSVs mergen)
   - Session State cached Validierung für schnelleres Tab-Switching
   - Chart Coloring optimiert für <20ms Renderzeit

## Erweiterte Nutzung

### Anpassungen
- **Neue Tabs**: In `main()` weitere st.tabs() hinzufügen
- **Filter erweitern**: `available_categories`, `available_roles` anpassen
- **Player-Farben**: Über die klickbaren Tabellenzustände in den Analyse-Tabs steuern
- **Theme**: `.streamlit/config.toml` bearbeiten

### Datenaktualisierung
1. **Neue Guild hinzufügen**:
   - CSV-Export aus HotBots in `data/hotutils/input/` ablegen
   - Format: `YYYY-MM-DD [Guild Name]Full.csv`
   - `python helper-scripts/encrypt_csvs.py` ausführen
   - Verschlüsselte Datei committen: `git add data/hotutils/*.encrypted`
   - Automatisch im Guild-Filter verfügbar

2. **Zeitpunkte aktualisieren**:
   - Weitere CSV-Dateien für existierende Gilden verschlüsseln
   - Datums-Auswahl wird automatisch aktualisiert

3. **Referenzdaten aktualisieren**:
   - Lokale SWGOH.GG-Quelldateien in `data/swgoh_gg/` aktualisieren
   - Erwartete HTML-Dateien in `data/swgoh_gg/`, `data/swgoh_gg/Eras/` und `data/swgoh_gg/Conquest/` als einzelne `.html`-Dateien ablegen
   - `data/unit_era_catalog.csv` für Era-Zuordnung neu generieren
   - `data/relic_benchmarks.csv` für Benchmark-Daten neu generieren
   - `data/unit_list.csv` als kanonische App-Datenbasis neu erzeugen
   - `data/relic_costs_cumulative.json` bei neuen Relic Tiers
   - Nur die abgeleiteten Artefakte ins Repository übernehmen, nicht die rohen SWGOH.GG-Quelldateien

## Support & Kontakt

Bei Fragen oder Problemen:
1. Überprüfe CSV-Dateiformat (HotBots Export)
2. Kontrolliere Spaltenbezeichnungen (Case-Sensitive)
3. Prüfe Browser-Konsole für JavaScript-Fehler
4. Streamlit-Logs für Python-Exceptions

**Entwickelt für die BΛ Bataillon Allianz** ⭐

---

### Changelog

- **v1.2** (2026-08-01): Feature Update
  - Key-Character von manueller Pflege auf Benchmark umgestellt (Top 1000 Kyber etc.)
  - Chars nach Era/Conquest filterbar
  - Kanonische Datenbasis über `data/unit_list.csv` und neue Helper-Skripte eingeführt
  - Gildendaten von `hu_data/` nach `data/hotutils/` verschoben

- **v1.1** (2025-11-22): Security & Feature Update
  - CSV-Verschlüsselung mit Fernet (AES-128)
  - Relic Cost Calculator in Character Overview
  - OR/AND Toggle für Categories & Ability Classes Filter
  - Performance: base_ids Iteration optimiert
  - Umfassende Dokumentation (ENCRYPTION.md)

- **v1.0** (2025-11-15): Initial Release
  - Multi-Guild Support für BΛ Bataillon
  - Erste Analyse-Tabs als Basis für die heutige App-Struktur
  - CSV Upload Feature
  - Performance-Optimierungen (Chart Coloring: 97% schneller)
  - Dark Theme Standard
