# SWGOH Guild Progress Tracker 🌟

Eine umfassende Analyseanwendung für Star Wars Galaxy of Heroes Gildendaten, entwickelt mit Streamlit.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

## Features

### 👤 Charakter-spezifische Analyse
- Detaillierte Statistiken für jeden Charakter
- Besitz-Details aller Gildenmitglieder
- Statistik-Verteilungen (Power, Speed, Health, Protection)

### ⚙️ Mod-Analyse
- Kampftyp-Verteilung
- Ausrichtungs-Analyse (Light Side, Dark Side, Neutral)
- Mod-Set Referenz

## Installation

### Lokale Installation

1. **Repository klonen**:
   ```bash
   git clone https://github.com/DEIN_USERNAME/SWGOH-Guild-Progress.git
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
   ├── assets/                 # Bilder/Logos (optional)
   ├── data/                   # Referenzdaten
   │   ├── characters.json
   │   ├── ships.json
   │   ├── statMod.json
   │   └── statModSet.json
   └── hu_data/                # CSV-Gildendaten
       ├── 2025-02-28 101st Beskar BataillonFull.csv
       └── 2025-11-02 101st Beskar BataillonFull.csv
   ```

## Verwendung

### Lokal starten:
```bash
# Im Projektverzeichnis ausführen:
streamlit run swgoh_guild_progress.py
```

Die Anwendung ist dann unter `http://localhost:8501` verfügbar.

### Streamlit Cloud Deployment:

1. **Repository auf GitHub pushen** (privates Repo empfohlen)
2. **Streamlit Cloud öffnen**: https://share.streamlit.io/
3. **App deployen**:
   - "New app" klicken
   - Repository auswählen: `DEIN_USERNAME/SWGOH-Guild-Progress`
   - Main file: `swgoh_guild_progress.py`
   - Deploy!

**Hinweis**: CSV-Dateien und JSON-Daten müssen im Repository enthalten sein oder über Secrets/externe Quellen geladen werden.

### Navigation:

## Technische Details

- **Framework**: Streamlit (Web-Interface)
- **Datenverarbeitung**: Pandas
- **Visualisierung**: Plotly (interaktive Diagramme)
- **Caching**: @st.cache_data für optimale Performance

## Troubleshooting

### Häufige Probleme:

1. **"Keine CSV-Dateien gefunden"**:
   - Überprüfen Sie, dass CSV-Dateien im `hu_data/` Ordner liegen
   - Dateiformat sollte UTF-8 sein

2. **"Charakterdaten konnten nicht geladen werden"**:
   - Überprüfen Sie die `data/` Ordnerstruktur
   - JSON-Dateien müssen gültig formatiert sein

3. **Performance-Probleme**:
   - Bei großen Dateien kann das erste Laden länger dauern
   - Streamlit cacht Daten automatisch für nachfolgende Zugriffe

## Erweiterte Nutzung

### Anpassungen:
- Neue Analysen können als zusätzliche Tabs implementiert werden
- Filteroptionen in der Sidebar hinzufügen
- Export-Funktionen für Berichte

### Datenexport:
Die Anwendung generiert interaktive Visualisierungen, die als PNG/HTML exportiert werden können.

## GitHub Setup

### Erstmaliges Pushen:

```bash
# Git initialisieren (falls noch nicht geschehen)
git init

# Alle Dateien stagen
git add .

# Ersten Commit erstellen
git commit -m "Initial commit: SWGOH Guild Progress Tracker"

# Remote Repository hinzufügen (ersetze mit deiner URL)
git remote add origin https://github.com/DEIN_USERNAME/SWGOH-Guild-Progress.git

# Branch umbenennen zu main (optional)
git branch -M main

# Pushen
git push -u origin main
```

### Regelmäßige Updates:

```bash
git add .
git commit -m "Update: Beschreibung der Änderung"
git push
```

**Wichtig**: Die `.gitignore` Datei ist bereits konfiguriert. Prüfe, ob du CSV/JSON-Dateien committen möchtest oder nicht.

## Support

Bei Fragen oder Problemen:
1. Überprüfen Sie die Dateistruktur
2. Kontrollieren Sie die CSV-Spaltenbezeichnungen
3. Prüfen Sie die Konsolen-Ausgabe für Fehlermeldungen

---

**Entwickelt für die strategische Analyse von SWGOH Gildendaten** ⭐