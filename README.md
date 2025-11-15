# SWGOH Guild Progress Analyzer 🌟

Eine umfassende Analyseanwendung für Star Wars Galaxy of Heroes Gildendaten der **BΛ Bataillon Allianz**.

Ermöglicht Multi-Player-Vergleiche über verschiedene Zeitpunkte hinweg basierend auf HotBots CSV-Exporten.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

## Features

### 🎯 Gilden-Management
- **Allianz-Zugriff**: Nur für Gilden der BΛ Bataillon Allianz
- **Multi-Zeitpunkt-Analyse**: Vergleiche von bis zu 2 historischen Datenpunkten
- **CSV Upload**: Zusätzliche Daten können hochgeladen werden
- **Player Selection**: Individuelle Spieler per Checkbox auswählen/abwählen
- **Color Coding**: Jeder Spieler erhält eine eindeutige Farbe für Vergleiche

### 📊 Analyse-Tabs

#### Character Overview
- Filterung nach Combat Type (Characters/Ships), Alignment, Kategorie, Rolle
- Besitz-Übersicht aller Spieler
- Detaillierte Charakterstatistiken (Power, Speed, Health, Protection, etc.)
- Gear Level & Relic Level Tracking

#### Character Stats (10 Charts)
- Interaktive Balkendiagramme für 10 Statistiken:
  - Relic Level, Gear Level, Character Level
  - Speed, Health, Protection, Physical Damage/Critical, Special Damage/Critical, Armor
- Farb-codierte Spieler-Balken
- Optimierte Performance (<20ms für alle 10 Charts)

#### Player Relics
- Relic-Verteilung pro Spieler
- Segmented Control: Gesamt vs. Light Side vs. Dark Side
- Vergleichbare Visualisierung über alle Spieler

#### Player Omicrons
- Omicron-Übersicht pro Spieler
- Segmented Control: Gesamt vs. Light Side vs. Dark Side
- Identifiziert Spieler mit/ohne Omicrons

#### Player Speed Mods
- Speed-Mod-Analyse (20+ Speed Mods)
- Segmented Control: Gesamt vs. Light Side vs. Dark Side
- Vergleicht High-Speed-Mod-Anzahl zwischen Spielern

#### Settings
- Header ein-/ausblenden
- Player-Farben anpassen
- Uncheck All Button für schnelles Zurücksetzen

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
   ├── requirements.txt        # Python Dependencies
   ├── .streamlit/
   │   └── config.toml        # Streamlit-Konfiguration (Dark Theme)
   ├── assets/                 # Bilder/Logos (optional)
   ├── data/                   # Referenzdaten (characters, ships, mods)
   │   ├── characters.json
   │   ├── ships.json
   │   ├── statMod.json
   │   └── statModSet.json
   └── hu_data/                # CSV-Gildendaten (HotBots Export)
       ├── YYYY-MM-DD [Guild Name]Full.csv
       └── ...
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

Erforderliche Spalten im CSV:
- Name, Galactic_Power, Character_Galactic_Power, Ship_Galactic_Power
- Character/Ship Details: Base_Id, Combat_Type, Alignment, Role, Categories
- Stats: Relic_Tier, Gear_Level, Level, Speed, Health, Protection, etc.
- Mods: Mod_Set_Id, Speed (aus Secondary_N_Value)

### Streamlit Cloud Deployment

1. **Repository auf GitHub pushen** (privates Repo empfohlen für CSV-Daten)
2. **Streamlit Cloud öffnen**: https://share.streamlit.io/
3. **App deployen**:
   - "New app" klicken
   - Repository: `DrPivot/SWGOH-Guild-Progress`
   - Main file: `swgoh_guild_progress.py`
   - Deploy!

**Wichtig**: 
- CSV-Dateien und JSON-Daten müssen im Repository enthalten sein
- `.streamlit/config.toml` für Theme-Einstellungen einbinden
- Für große CSV-Dateien: Git LFS verwenden oder externe Storage

### Navigation

1. **Startbildschirm**:
   - Gilde aus BΛ Bataillon Allianz auswählen
   - Bis zu 2 Datenpunkte (CSV-Dateien) auswählen
   - Optional: CSV hochladen für zusätzliche Daten
   - "Start Analysis" klicken

2. **Analyse-Modus**:
   - Spieler in Sidebar per Checkbox aktivieren
   - Tabs für verschiedene Analysen durchklicken
   - Filter anwenden (Combat Type, Alignment, Kategorie, Rolle)
   - Segmented Controls für Light/Dark Side Vergleiche nutzen

## Technische Details

- **Framework**: Streamlit 1.40+ (Web-Interface)
- **Datenverarbeitung**: Pandas (optimiert mit vectorized operations)
- **Visualisierung**: Plotly (interaktive Balkendiagramme)
- **Caching**: Session State für Validierung & Player-Daten
- **Theme**: Dark Mode Standard (umschaltbar in Settings)
- **Performance**: Chart Rendering <20ms für 10 Charts

### Architektur-Highlights
- **get_final_df()**: Lädt und mergt CSV-Dateien + Upload
- **Validation Caching**: Teure unique() Operations nur einmal
- **Dictionary Lookups**: O(1) Player-Farben statt O(n) DataFrame-Zugriffe
- **Vectorized Coloring**: Pandas .map() statt Python-Loops

## Troubleshooting

### Häufige Probleme

1. **"Gilde nicht im Repository gefunden"**:
   - Nur Gilden der BΛ Bataillon Allianz haben Zugriff
   - CSV-Dateien müssen im `hu_data/` Ordner liegen
   - Dateiname-Format: `YYYY-MM-DD [Guild Name]Full.csv`

2. **"Keine gemeinsamen Spieler zwischen Upload und Cached-Daten"**:
   - Upload-CSV muss Spieler der ausgewählten Gilde enthalten
   - Validierung prüft Name-Spalte auf Übereinstimmungen

3. **"Charakterdaten konnten nicht geladen werden"**:
   - `data/` Ordner mit JSON-Dateien muss vorhanden sein
   - characters.json, ships.json erforderlich für Filterung

4. **Performance-Probleme**:
   - Erste Datenladung kann länger dauern (mehrere CSVs mergen)
   - Session State cached Validierung für schnelleres Tab-Switching
   - Chart Coloring optimiert für <20ms Renderzeit

## Erweiterte Nutzung

### Anpassungen
- **Neue Tabs**: In `main()` weitere st.tabs() hinzufügen
- **Filter erweitern**: `available_categories`, `available_roles` anpassen
- **Player-Farben**: In Settings-Tab individuell konfigurierbar
- **Theme**: `.streamlit/config.toml` bearbeiten

### Datenaktualisierung
1. **Neue Guild hinzufügen**:
   - CSV-Dateien in `hu_data/` ablegen
   - Format: `YYYY-MM-DD [Guild Name]Full.csv`
   - Automatisch im Guild-Filter verfügbar

2. **Zeitpunkte aktualisieren**:
   - Weitere CSV-Dateien für existierende Gilden hinzufügen
   - Datums-Auswahl wird automatisch aktualisiert

3. **Referenzdaten aktualisieren**:
   - `data/characters.json` für neue Charaktere
   - `data/ships.json` für neue Schiffe
   - HotBots/SWGOH.gg API-Exporte verwenden

## Support & Kontakt

Bei Fragen oder Problemen:
1. Überprüfe CSV-Dateiformat (HotBots Export)
2. Kontrolliere Spaltenbezeichnungen (Case-Sensitive)
3. Prüfe Browser-Konsole für JavaScript-Fehler
4. Streamlit-Logs für Python-Exceptions

**Entwickelt für die BΛ Bataillon Allianz** ⭐

---

### Changelog

- **v1.0** (2025-11-15): Initial Release
  - Multi-Guild Support für BΛ Bataillon
  - 6 Analyse-Tabs (Overview, Stats, Relics, Omicrons, Speed Mods, Settings)
  - CSV Upload Feature
  - Performance-Optimierungen (Chart Coloring: 97% schneller)
  - Dark Theme Standard
