import streamlit as st
import pandas as pd
import json
import glob
import re
import plotly.express as px
import plotly.graph_objects as go
import locale
import requests
from datetime import datetime
import os
import sys

# ============================================================================
# KONFIGURATION
# ============================================================================
DEFAULT_PLAYER = "DrPivot"  # Standard-Spieler für Highlighting

# Farbpalette für Player-Zuordnung - 50 gut unterscheidbare Farben
PLAYER_COLOR_PALETTE = [
    '#FF0000', '#00EE00', '#0000FF', '#DDDD00', '#FF00FF',
    '#FF1111', '#11EE11', '#1111FF', '#DDDD11', '#FF11FF',
    '#FF2222', '#22EE22', '#2222FF', '#DDDD22', '#FF22FF',
    '#FF3333', '#33EE33', '#3333FF', '#DDDD33', '#FF33FF',
    '#FF4444', '#44EE44', '#4444FF', '#DDDD44', '#FF44FF',
    '#FF5555', '#55EE55', '#5555FF', '#DDDD55', '#FF55FF',
    '#FF6666', '#66EE66', '#6666FF', '#DDDD66', '#FF66FF',
    '#FF7777', '#77EE77', '#7777FF', '#DDDD77', '#FF77FF',
    '#FF8888', '#88EE88', '#8888FF', '#DDDD88', '#FF88FF',
    '#FF9999', '#99EE99', '#9999FF', '#DDDD99', '#FF99FF'
]

# ============================================================================
# SETUP
# ============================================================================
# Setze deutsche Locale für Zahlenformatierung
try:
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'German_Germany.1252')
    except:
        pass  # Fallback wenn keine deutsche Locale verfügbar

# CSS um hochgeladenen Dateinamen zu verstecken
st.markdown("""
    <style>
    /* Verstecke die hochgeladene Datei-Liste (stabile Klasse: e16n7gab7) */
    [data-testid="stFileUploader"] .e16n7gab7 {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_character_data():
    """Lädt die Charakterdaten aus der JSON-Datei."""
    try:
        with open('data/characters.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ characters.json nicht gefunden!")
        return []
    except json.JSONDecodeError:
        st.error("❌ Fehler beim Laden der characters.json!")
        return []


@st.cache_data
def load_ship_data():
    """Lädt die Schiffsdaten aus der JSON-Datei."""
    try:
        with open('data/ships.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning("⚠️ ships.json nicht gefunden!")
        return []
    except json.JSONDecodeError:
        st.error("❌ Fehler beim Laden der ships.json!")
        return []

@st.cache_data
def load_units_data():
    """Lädt und kombiniert Character- und Schiffsdaten."""
    characters = load_character_data()
    ships = load_ship_data()
    # Kombiniere beide Listen
    all_units = characters + ships
    return all_units

@st.cache_data
def get_available_guilds():
    """Scannt hu_data Ordner und gibt Liste aller Guilds zurück."""
    pattern = "hu_data/*Full.csv"
    files = glob.glob(pattern)
    
    guilds_info = {}
    for file in files:
        filename = os.path.basename(file)
        match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(.+?)Full\.csv', filename)
        if match:
            guild_name = match.group(2).strip()
            if guild_name not in guilds_info:
                guilds_info[guild_name] = 0
            guilds_info[guild_name] += 1
    
    # DataFrame für Anzeige: Guild Name + CSV Count
    guilds_df = pd.DataFrame([
        {'Guild Name': guild, 'CSVs': count}
        for guild, count in sorted(guilds_info.items())
    ])
    return guilds_df

@st.cache_data
def get_dates_for_guild(guild_name):
    """Gibt alle verfügbaren Daten für eine Guild zurück (nur Repository)."""
    pattern = f"hu_data/*{guild_name}Full.csv"
    files = glob.glob(pattern)
    
    dates_info = []
    for file in files:
        filename = os.path.basename(file)
        match = re.match(r'(\d{4}-\d{2}-\d{2})\s+.+?Full\.csv', filename)
        if match:
            date_str = match.group(1)
            dates_info.append({'Datum': date_str, 'Quelle': 'Repo'})
    
    # Sortiere nach Datum (neueste zuerst)
    dates_df = pd.DataFrame(dates_info)
    if not dates_df.empty:
        dates_df = dates_df.sort_values('Datum', ascending=False)
    return dates_df

def get_dates_with_upload(guild_name, upload_date=None, upload_guild=None):
    """Gibt Repo-Daten + Upload zurück (falls vorhanden UND Gilde stimmt überein)."""
    dates_df = get_dates_for_guild(guild_name)
    
    # Füge Upload hinzu (nur wenn vorhanden UND Gilde stimmt überein!)
    if upload_date and upload_guild == guild_name:
        upload_row = pd.DataFrame([{'Datum': upload_date, 'Quelle': '📤 Upload'}])
        dates_df = pd.concat([upload_row, dates_df], ignore_index=True)
    
    return dates_df

@st.cache_data
def load_guild_data(guild_filter, selected_dates):
    """Lädt nur ausgewählte CSVs der Gilde (mit Caching)."""
    
    # Suche nur nach CSVs dieser Guild
    pattern = f"hu_data/*{guild_filter}Full.csv"
    files = glob.glob(pattern)
    
    if not files:
        st.error(f"❌ Keine CSV-Dateien für {guild_filter} gefunden!")
        return None
    
    all_dataframes = []
    # Convert selected_dates to set for faster lookup
    selected_dates_set = set(selected_dates) if selected_dates else set()

    for file in files:
        try:
            # Extrahiere Datum aus Dateinamen
            filename = os.path.basename(file)
            match = re.match(r'(\d{4}-\d{2}-\d{2})\s+.+?Full\.csv', filename)
            
            if match:
                date_str = match.group(1)
                
                # Nur laden wenn in selected_dates (oder wenn keine Auswahl = alle laden)
                if not selected_dates_set or date_str in selected_dates_set:
                    # Lade CSV
                    df = pd.read_csv(file)
                    
                    # Füge Spalten hinzu
                    df['date'] = date_str
                    df['guild'] = guild_filter
                    
                    all_dataframes.append(df)

        except Exception as e:
            st.warning(f"⚠️ Fehler beim Laden von {file}: {e}")
            continue
    
    if not all_dataframes:
        st.error("❌ Keine gültigen CSV-Dateien geladen!")
        return None
    
    # Kombiniere alle DataFrames
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    return combined_df

@st.cache_data
def get_final_df(guild_filter, selected_dates, upload_csv_data=None, upload_date=None, upload_guild=None):
    """
    Kombiniert gecachte Repository-Daten + optionalen Upload (MIT CACHING!).
    Upload wird im Cache gespeichert - alle User der gleichen Gilde profitieren während App läuft.
    
    Args:
        guild_filter: Name der Gilde
        selected_dates: Tuple der ausgewählten Daten aus Repository
        upload_csv_data: Optional - Upload-CSV als String (für Cache-Key)
        upload_date: Optional - Datum des Uploads
        upload_guild: Optional - Gilde des Uploads (für Validierung)
    
    Returns:
        DataFrame mit allen Daten (Repository + Upload falls vorhanden)
    """
    # Lade gecachte CSVs aus Repository
    df_cached = load_guild_data(guild_filter, tuple(selected_dates))
    
    if df_cached is None:
        return None
    
    # Füge Upload hinzu (falls übergeben UND Gilde stimmt überein!)
    if upload_csv_data is not None and upload_guild == guild_filter:
        # Parse Upload-CSV
        from io import StringIO
        df_upload = pd.read_csv(StringIO(upload_csv_data))
        
        # Validierung: Spieler-Übereinstimmung
        if 'AllyCode' in df_upload.columns and 'AllyCode' in df_cached.columns:
            upload_players = set(df_upload['AllyCode'].unique())
            cached_players = set(df_cached['AllyCode'].unique())
            common_players = upload_players & cached_players
            
            if not common_players:
                # KEINE gemeinsamen Spieler = fremde Gilde → Return empty DataFrame
                return pd.DataFrame()
        
        # Kombiniere beide DataFrames
        df_upload = df_upload.copy()
        df_upload['guild'] = guild_filter
        df_upload['date'] = upload_date if upload_date else datetime.now().strftime('%Y-%m-%d')
        
        df_final = pd.concat([df_upload, df_cached], ignore_index=True)
    else:
        df_final = df_cached
    
    return df_final

def show_start_screen():
    """Zeigt Startbildschirm mit Guild-Auswahl, Date-Auswahl und CSV-Upload."""
    
    # Header mit Logo und Titel nebeneinander
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image("assets/bataillon_logo.png", width=600)
    with col2:
        st.title("SWGOH Guild Progress")
    
    st.markdown("---")
    
    # Zwei-Spalten-Layout für Guild und Dates
    col_guild, col_dates = st.columns([1, 1])
    
    # Linke Spalte: Guild auswählen
    with col_guild:
        st.subheader("📋 Schritt 1: Gildenauswahl")
        
        guilds_df = get_available_guilds()
        
        if guilds_df.empty:
            st.error("❌ Keine Gilden gefunden! Bitte CSVs in hu_data/ Ordner ablegen.")
            st.info("📝 Dateinamen-Format: `YYYY-MM-DD GuildNameFull.csv`")
            return
        
        # Guild-Tabelle mit single-row selection
        guild_selection = st.dataframe(
            guilds_df,
            hide_index=True,
            selection_mode="single-row",
            on_select=lambda: None,
            key="guild_selection",
            width='stretch'
        )
        
        # Extrahiere ausgewählte Guild
        selected_guild_rows = guild_selection.selection.rows if hasattr(guild_selection, 'selection') else []
        
        if selected_guild_rows:
            selected_guild_idx = selected_guild_rows[0]
            selected_guild = guilds_df.iloc[selected_guild_idx]['Guild Name']
            st.session_state.selected_guild = selected_guild
    
    # Rechte Spalte: Dates auswählen (nur wenn Guild gewählt)
    with col_dates:
        st.subheader(f"📅 Schritt 2: Datumsauswahl")
        if 'selected_guild' in st.session_state:
            # Hole Upload-Datum und Upload-Gilde falls vorhanden
            upload_date = None
            upload_guild = None
            if 'uploaded_csv_df' in st.session_state:
                upload_date = st.session_state.get('uploaded_csv_date', None)
                upload_guild = st.session_state.get('uploaded_csv_guild', None)
            
            # Hole Daten inkl. Upload (Upload nur wenn Gilde übereinstimmt!)
            dates_df = get_dates_with_upload(st.session_state.selected_guild, upload_date, upload_guild)
            
            if dates_df.empty:
                st.warning(f"⚠️ Keine Daten für {st.session_state.selected_guild} gefunden!")
            else:
                # Dates-Tabelle mit multi-row selection
                dates_selection = st.dataframe(
                    dates_df,
                    hide_index=True,
                    selection_mode="multi-row",
                    on_select=lambda: None,
                    key="dates_selection",
                    width='stretch'
                )
                
                # Extrahiere ausgewählte Dates
                selected_date_rows = dates_selection.selection.rows if hasattr(dates_selection, 'selection') else []
                
                if selected_date_rows:
                    # Filtere Upload-Zeilen raus (Upload wird separat behandelt!)
                    selected_dates = [
                        dates_df.iloc[idx]['Datum'] 
                        for idx in selected_date_rows 
                        if dates_df.iloc[idx]['Quelle'] == 'Repo'
                    ]
                    st.session_state.selected_dates = selected_dates
                    
                    # Prüfe ob Upload ausgewählt wurde
                    has_upload_selected = any(
                        dates_df.iloc[idx]['Quelle'] == '📤 Upload' 
                        for idx in selected_date_rows
                    )
                    
                    # Info-Text
                    repo_count = len(selected_dates)
                    upload_text = " + Upload" if has_upload_selected else ""
                    st.info(f"✅ {repo_count} Repo-CSV(s){upload_text} ausgewählt")
        else:
            st.info("👈 Bitte zuerst eine Gilde auswählen")
    
    # Schritt 3 & 4: CSV Upload und Start-Button (volle Breite)
    if 'selected_guild' in st.session_state:
        st.markdown("---")
        
        # Schritt 3: Optional CSV hochladen
        st.subheader("📤 Schritt 3: Neue CSV hochladen (optional)")
        
        # Prüfe ob bereits ein Upload existiert
        has_existing_upload = 'uploaded_csv_df' in st.session_state
        
        if has_existing_upload:
            # Zeige Success-Meldung nach Upload
            upload_date = st.session_state.get('uploaded_csv_date', 'Unbekannt')
            upload_guild = st.session_state.get('uploaded_csv_guild', 'Unbekannt')
            upload_rows = len(st.session_state.uploaded_csv_df)
            st.success(f"✅ {upload_rows} Zeilen für {upload_guild} hochgeladen! (Datum: {upload_date})")
            
            st.info("ℹ️ Nur ein Upload pro Session erlaubt.")
            if st.button("🗑️ Aktuellen Upload löschen"):
                del st.session_state['uploaded_csv_df']
                del st.session_state['uploaded_csv_data']
                del st.session_state['uploaded_csv_date']
                del st.session_state['uploaded_csv_guild']
                if 'upload_validation_warnings' in st.session_state:
                    del st.session_state['upload_validation_warnings']
                if 'upload_guild_mismatch' in st.session_state:
                    del st.session_state['upload_guild_mismatch']
                st.rerun()
        
        uploaded_file = st.file_uploader(
            "Neue CSV-Datei hochladen",
            type=['csv'],
            help="Optional: Lade eine neue CSV hoch (Format: YYYY-MM-DD GuildNameFull.csv)",
            disabled=has_existing_upload
        )
        
        if uploaded_file is not None and 'uploaded_csv_df' not in st.session_state:
            try:
                df_upload = pd.read_csv(uploaded_file)
                
                # Validierung 1 & 2: Dateiname prüfen (falls vorhanden)
                filename = uploaded_file.name
                upload_date = datetime.now().strftime('%Y-%m-%d')  # Default: heute
                validation_warnings = []
                
                if filename:
                    # Versuche Datum und Gildenname zu extrahieren
                    match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(.+?)Full\.csv', filename)
                    if match:
                        extracted_date = match.group(1)
                        extracted_guild = match.group(2).strip()
                        
                        # Prüfung 1: Passt Gildenname zur ausgewählten Gilde?
                        selected_guild = st.session_state.selected_guild
                        if extracted_guild != selected_guild:
                            validation_warnings.append(f"⚠️ Gildennamen-Mismatch: Datei enthält '{extracted_guild}', aber '{selected_guild}' ist ausgewählt!")
                            st.session_state.upload_guild_mismatch = True  # Flag für Start-Button
                        else:
                            st.session_state.upload_guild_mismatch = False
                        
                        # Prüfung 2: Nutze Datum aus Dateinamen
                        upload_date = extracted_date
                    else:
                        # Kein Match im Dateinamen - Upload erlauben (könnte manuell umbenannt sein)
                        st.session_state.upload_guild_mismatch = False
                else:
                    # Kein Dateiname - Upload erlauben
                    st.session_state.upload_guild_mismatch = False
                
                # Speichere Upload in Session State + CSV-String für Cache (EINMALIG!)
                st.session_state.uploaded_csv_df = df_upload
                st.session_state.uploaded_csv_data = df_upload.to_csv(index=False)  # Einmalige Konvertierung!
                st.session_state.uploaded_csv_date = upload_date
                st.session_state.uploaded_csv_guild = st.session_state.selected_guild  # Speichere Gilde!
                st.session_state.upload_validation_warnings = validation_warnings
                
                # Zeige Warnings falls vorhanden
                for warning in validation_warnings:
                    st.warning(warning)
                
                # Rerun um Upload-Zeile in Tabelle anzuzeigen (Success-Meldung kommt nach Rerun!)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Fehler beim Laden der CSV: {e}")
        
        st.markdown("---")
        
        # Schritt 4: Start-Button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
                # Prüfe ob Upload-Gilde nicht passt
                guild_mismatch = st.session_state.get('upload_guild_mismatch', False)
                button_disabled = guild_mismatch
                
                if button_disabled:
                    st.error("🚫 Start blockiert: Gildennamen-Mismatch!")
                    st.info("💡 Nur Gilden aus dem Repository dürfen das Tool nutzen.")
                
                if st.button("▶️ Start Analysis", type="primary", width='stretch', disabled=button_disabled):
                    if 'selected_dates' in st.session_state and st.session_state.selected_dates:
                        st.session_state.analysis_started = True
                        st.rerun()
                    else:
                        st.warning("⚠️ Bitte mindestens ein Datum auswählen!")

def apply_filters(characters_data, alignment_filter, categories_filter, role_filter, ability_classes_filter):
    """Wendet Filter auf die Charakterdaten an."""
    filtered = characters_data.copy()
    
    if alignment_filter:  # Wenn Liste nicht leer
        filtered = [char for char in filtered if char.get('alignment') in alignment_filter]
    
    if categories_filter:  # Wenn Liste nicht leer - UND-Verknüpfung
        filtered = [char for char in filtered if all(cat in char.get('categories', []) for cat in categories_filter)]
    
    if role_filter:  # Wenn Liste nicht leer
        filtered = [char for char in filtered if char.get('role') in role_filter]
    
    if ability_classes_filter:  # Wenn Liste nicht leer - UND-Verknüpfung
        filtered = [char for char in filtered if all(ac in char.get('ability_classes', []) for ac in ability_classes_filter)]
    
    return filtered

def show_character_overview(df, filtered_characters, characters_data, filters_active):
    st.markdown('<h3 style="margin-top: -12px; margin-bottom: 0;">📋 Character Overview</h3>', unsafe_allow_html=True)
    
    # Falls Filter angewendet wurden, nur gefilterte Charaktere anzeigen
    if filters_active:
        if filtered_characters:
            filtered_base_ids = [char['base_id'] for char in filtered_characters]
            df_filtered = df[df['BaseId'].isin(filtered_base_ids)]
        else:
            # Filter aktiv aber keine Treffer - leere Ergebnismenge
            df_filtered = df[df['BaseId'].isin([])]  # Leerer DataFrame
    else:
        # Keine Filter aktiv - alle anzeigen
        df_filtered = df
    
    if df_filtered.empty:
        st.warning("❌ Keine Daten für die ausgewählten Filter gefunden.")
        return
    
    # Erstelle ein Mapping von BaseId zu Name für die Anzeige
    base_id_to_name = {char['base_id']: char['name'] for char in characters_data}
    
    # Gruppierung nach BaseId (Charaktername) und Berechnung der Kennzahlen
    char_stats = df_filtered.groupby('BaseId').agg({
        'Speed': 'mean',
        'Health': 'mean',
        'Protection': 'mean',
        'Damage': 'mean',
        'SpecialDamage': 'mean',
        'RelicLevel': [
            lambda x: sum(x == 9),    # R9
            lambda x: sum(x == 8),    # R8  
            lambda x: sum(x == 7),    # R7
            lambda x: sum(x == 6),    # R6
            lambda x: sum(x < 6),     # <R6
            'count'                   # Total count
        ]
    }).round(0)  # Keine Nachkommastellen
    
    # Spalten strukturieren - alle als Integer
    char_overview = pd.DataFrame({
        'Character': [base_id_to_name.get(base_id, base_id) for base_id in char_stats.index],
        'Avg Speed': char_stats['Speed']['mean'].astype(int),
        'Avg Health': char_stats['Health']['mean'].astype(int),
        'Avg Protection': char_stats['Protection']['mean'].astype(int),
        'Avg Damage': char_stats['Damage']['mean'].astype(int),
        'Avg SpecialDamage': char_stats['SpecialDamage']['mean'].astype(int),
        'Count': char_stats['RelicLevel']['count'].astype(int),
        'R9': char_stats['RelicLevel']['<lambda_0>'].astype(int),
        'R8': char_stats['RelicLevel']['<lambda_1>'].astype(int), 
        'R7': char_stats['RelicLevel']['<lambda_2>'].astype(int),
        'R6': char_stats['RelicLevel']['<lambda_3>'].astype(int),
        '<R6': char_stats['RelicLevel']['<lambda_4>'].astype(int)
    })
    
    # Nach Average Speed sortieren
    char_overview = char_overview.sort_values('Avg Speed', ascending=False)
    
    # Index zurücksetzen um BaseId zu entfernen
    char_overview = char_overview.reset_index(drop=True)
    
    # Tabelle anzeigen mit kleiner Zeilenhöhe für mehr sichtbare Zeilen
    # row_height=21 ermöglicht ca. 50 Zeilen bei 1140px Container-Höhe
    st.dataframe(char_overview, hide_index=True, width="stretch", height=1100, row_height=21)

def show_analytics_tab(df, filtered_characters, characters_data, filters_active):
    """Tab 2 - Character Stats mit Multi-Player Vergleich via Checkboxen."""
    
    # Hole player_base DIREKT aus Session State (nicht als Parameter!)
    player_base = st.session_state.player_base_global
    
    # Character-Filter wird unten links hinzugefügt - hier erstmal die Charakterliste erstellen
    if filters_active:
        if filtered_characters:
            available_characters = [(char['name'], char['base_id']) for char in filtered_characters]
        else:
            available_characters = []  # Filter aktiv aber keine Treffer
    else:
        available_characters = [(char['name'], char['base_id']) for char in characters_data]
    
    # Character-Dropdown wird über Session State verwaltet
    if 'selected_character_tab2' not in st.session_state:
        st.session_state.selected_character_tab2 = available_characters[0][0] if available_characters else None
    
    if not available_characters:
        st.warning("❌ Keine Charaktere verfügbar.")
        return
    
    # Charakter für Tab 2 aus Session State holen
    selected_character_name = st.session_state.selected_character_tab2
    selected_base_id = next((base_id for name, base_id in available_characters if name == selected_character_name), None)
    
    if not selected_base_id:
        st.warning("❌ Kein gültiger Charakter ausgewählt.")
        return
    
    # Filtere Daten für den ausgewählten Charakter
    df_character = df[df['BaseId'] == selected_base_id].copy()
    
    if df_character.empty:
        st.warning(f"❌ Keine Daten für {selected_character_name} gefunden.")
        return
    
    st.markdown(f'<h3 style="margin-top: -12px; margin-bottom: 0;">📊 Character Stats für {selected_character_name}</h3>', unsafe_allow_html=True)
    
    # Alle Stats aus der Tabelle für Diagramme (CritChance vor CritDamage)
    stats_columns = ['Speed', 'Health', 'Protection', 'Armor', 'Damage', 'CritChance', 'CritDamage', 'Potency', 'Tenacity', 'RelicLevel']
    
    # Hilfsfunktion: Hex zu RGBA mit Transparenz
    def hex_to_rgba(hex_color, opacity=0.6):
        """Konvertiert Hex-Farbe zu RGBA mit Transparenz."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f'rgba({r},{g},{b},{opacity})'
    
    # Diagramme in einem Container mit fester Breite (Player: 200px + 10*150 = 1700px)
    with st.container(width=1800, gap=None):
        
        # Erstelle Lookup-Dictionaries EINMAL für ALLE Charts (statt 10x pro Chart!)
        player_checked = dict(zip(player_base['Name'], player_base['Checked']))
        player_colors = dict(zip(player_base['Name'], player_base['PlayerColor']))
        
        # Precompute RGBA colors für alle checked players (statt 50x pro Chart!)
        player_colors_rgba = {
            name: hex_to_rgba(color, 0.6) 
            for name, color in player_colors.items() 
            if player_checked.get(name, False)
        }
        
        # Diagramme nebeneinander anzeigen - wie gewünscht!
        
        # Charts mit perfekter Ausrichtung anzeigen (jetzt 10 Stats)
        # KEINE Checkbox-Spalte mehr! Nur Player: 200px + 10*150px Charts
        chart_cols = st.columns([200] + [150] * 10, gap="small")
        
        with chart_cols[0]:
            st.markdown("")  # Spacer für Player-Spalte
        
        for i, stat in enumerate(stats_columns):
            # Emoji für jeden Stat
            stat_emojis = {
                'Speed': '⚡',
                'Health': '❤️', 
                'Protection': '🛡️',
                'Armor': '🧥',
                'Damage': '⚔️',
                'CritChance': '🎲',
                'CritDamage': '💥',
                'Potency': '🎯',
                'Tenacity': '🧘',
                'RelicLevel': '⭐'
            }
            
            # Daten für diesen Stat vorbereiten - absteigend sortiert
            stat_data = df_character[['Name', 'AllyCode', stat]].sort_values(stat, ascending=False)
            
            # Farben für Balken: Vektorisierte Operation (blitzschnell!)
            colors = stat_data['Name'].map(lambda name: player_colors_rgba.get(name, "#222222")).tolist()
            
            # Hover-Text erstellen: Name + Wert
            hover_texts = [
                f"{row['Name']}<br>{stat}: {row[stat]:.0f}"
                for _, row in stat_data.iterrows()
            ]
            
            # Chart erstellen mit plotly - exakt 150px Breite
            fig = go.Figure()
            # Balken (farbig oder dunkelgrau)
            fig.add_trace(go.Bar(
                x=list(range(len(stat_data))),  # Index statt Namen
                y=stat_data[stat],
                marker_color=colors,  # Checked/selected/default colors
                showlegend=False,
                hovertext=hover_texts,
                hoverinfo='text'  # Zeige nur den custom text
            ))
            # Graue Linie über den Balken
            fig.add_trace(go.Scatter(
                x=list(range(len(stat_data))),
                y=stat_data[stat],
                mode='lines',
                line=dict(color='#888888', width=2),
                showlegend=False,
                hoverinfo='skip'  # Kein Hover für die Linie
            ))
            
            fig.update_layout(
                xaxis={
                    'showticklabels': False,  # Keine x-Achsen Namen
                    'title': "",  # Kein x-Achsen Titel
                    'showgrid': False,
                    'zeroline': False,
                    'fixedrange': True
                },
                yaxis={
                    'showticklabels': False,  # Keine y-Achsen Werte
                    'title': "",  # Kein y-Achsen Titel
                    'showgrid': False,
                    'zeroline': False,
                    'fixedrange': True,
                    'automargin': False  # Verhindert automatische Margins für y-Achse
                },
                width=150,  # Chart-Breite: 150px
                height=150,  # Kompakte Höhe
                margin={'l': 2, 'r': 2, 't': 24, 'b': 1},  # Null Margins für maximale Nutzung
                bargap=0,  # Kein Abstand zwischen Balken
                plot_bgcolor='rgba(0,0,0,0)',  # Transparenter Hintergrund
                paper_bgcolor='rgba(0,0,0,0)',  # Transparenter Hintergrund
                title={
                    'text': f"{stat_emojis.get(stat, '📊')} {stat}",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 12}
                },
                shapes=[
                    # Rahmen um den Chart
                    dict(
                        type='rect',
                        xref='paper',
                        yref='paper',
                        x0=0,
                        y0=0,
                        x1=1,
                        y1=1,
                        line=dict(
                            color='#444444',
                            width=1
                        ),
                        fillcolor='rgba(0,0,0,0)'
                    )
                ]
            )
            
            with chart_cols[i + 1]:  # Index +1 wegen nur Player Spalte (keine Checkbox mehr!)
                st.plotly_chart(fig, width='content', config={'displayModeBar': False}, key=f"chart_{stat}")
    
    # Tabelle direkt unter den Diagrammen (ohne große Lücke)
    # st.markdown("")  # Minimaler Abstand
    
    # Spalten für die Anzeige auswählen (ohne BaseId) - CritChance vor CritDamage
    display_columns = ['Name', 'Speed', 'Health', 'Protection', 'Armor', 'Damage', 'CritChance', 'CritDamage', 'Potency', 'Tenacity', 'RelicLevel']
    
    # DataFrame für Anzeige vorbereiten (gleiche Sortierung wie Diagramm)
    display_df = df_character[display_columns].copy()
    display_df = display_df.sort_values('Speed', ascending=False)  # Nach Speed sortieren
    
    # Merge mit player_base um Checked-Status und PlayerColor zu bekommen
    display_df = display_df.merge(
        player_base[['Name', 'Checked', 'PlayerColor']], 
        on='Name', 
        how='left'
    )
    
    # Erstelle Mapping für Styling
    name_to_color = dict(zip(display_df['Name'], display_df['PlayerColor']))
    
    # Spalte "Name" in "Player" umbenennen für Tab 2
    display_df = display_df.rename(columns={'Name': 'Player'})
    
    # KEINE Checkbox-Spalte mehr - wird durch on_select ersetzt!
    # Entferne PlayerColor und Checked aus Anzeige-Spalten
    display_df_clean = display_df.drop(columns=['PlayerColor', 'Checked'])
    
    # Tabelle anzeigen mit Farbcodierung für checked players
    def highlight_players(row):
        """Färbt Zeilen basierend auf checked Status - nutzt feste Farben."""
        # Hole checked-Status aus player_base
        player_name = row['Player']
        is_checked = player_base.loc[player_base['Name'] == player_name, 'Checked'].iloc[0] if player_name in player_base['Name'].values else False
        
        if is_checked:
            color = name_to_color.get(player_name, '#CCCCCC')
            return [f'background-color: {color}99' for _ in row]
        else:
            return ['' for _ in row]
    
    # Prozent-Spalten definieren
    percent_columns = {
        'CritDamage', 'Potency', 'Tenacity', 'HealthSteal', 'CritChance', 
        'Accuracy', 'Armor', 'DodgeChance', 'CritAvoidance', 
        'SpecialCritChance', 'SpecialAccuracy', 'Resistance', 
        'DeflectionChance', 'SpecialCritAvoidance'
    }
    
    # Styling anwenden
    styled_df = display_df_clean.style.apply(highlight_players, axis=1)
    
    # Spalten-Konfiguration: 32px für row-select + Player (200px) + Stats mit Prozenten wo nötig
    column_config = {
        'Player': st.column_config.TextColumn(width=200)
    }
    
    for col in display_df_clean.columns:
        if col != 'Player':
            if col in percent_columns:
                # Prozent-Spalten
                column_config[col] = st.column_config.NumberColumn(width=160, format="%.1f %%")
            else:
                # Normale Zahlen
                column_config[col] = st.column_config.NumberColumn(width=160, format="%.0f")
    
    # on_select Callback für Cell-Selection
    def on_player_select():
        """Callback wenn Spieler-Zelle ausgewählt wird - toggle den Spieler der Zeile."""
        # Hole Selection-Event
        selection = st.session_state.player_comparison_table_selection
        
        # Zugriff auf selection dict
        if hasattr(selection, 'selection'):
            sel_dict = selection.selection
        elif isinstance(selection, dict):
            sel_dict = selection.get('selection', {})
        else:
            return
        
        selected_cells = sel_dict.get('cells', [])
        
        # Extrahiere Zeilen-Index aus erster Zelle: (row_idx, column_name)
        if selected_cells:
            cell = selected_cells[0]
            if isinstance(cell, (list, tuple)) and len(cell) >= 1:
                row_idx = cell[0]
            elif isinstance(cell, dict):
                row_idx = cell.get('row', 0)
            else:
                return
            
            player_name = display_df_clean.iloc[row_idx]['Player']
            
            if player_name in st.session_state.player_base_global['Name'].values:
                # Toggle: checked → unchecked, unchecked → checked
                current_state = st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ].iloc[0]
                
                st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ] = not current_state
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width=1810,
        column_config=column_config,
        height=960,
        row_height=20,
        selection_mode="single-cell",
        on_select=on_player_select,
        key="player_comparison_table_selection"
    )

@st.cache_data
def get_all_relic_counts_per_date(df_guild, player_base):
    """
    Berechnet ALLE Relic-Counts (R6-R10) pro Spieler und Datum (mit Caching).
    Wird nur einmal pro Guild berechnet, dann für alle User geteilt.
    
    Args:
        df_guild: Gefilterte Daten für diese Gilde (aus Cache)
        player_base: DataFrame mit [AllyCode, Name] - einheitliche Spielerliste
    
    Returns:
        Dict[date, DataFrame]: {date: DataFrame mit [AllyCode, Name, R6, R7, R8, R9, R10]}
    """
    available_dates = sorted(df_guild['date'].unique(), reverse=True)
    
    result = {}
    for date in available_dates:
        df_date = df_guild[df_guild['date'] == date]
        
        # Zähle jedes Relic-Level separat - für alle Spieler in player_base
        player_counts = []
        for _, player_row in player_base.iterrows():
            ally_code = player_row['AllyCode']
            player_name = player_row['Name']
            
            df_player = df_date[df_date['AllyCode'] == ally_code]
            
            if not df_player.empty:
                # Nur Characters (keine Ships)
                df_chars = df_player[df_player['CombatType'] == 'Character']
                
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    'R10': (df_chars['RelicLevel'] == 10).sum(),
                    'R9': (df_chars['RelicLevel'] == 9).sum(),
                    'R8': (df_chars['RelicLevel'] == 8).sum(),
                    'R7': (df_chars['RelicLevel'] == 7).sum(),
                    'R6': (df_chars['RelicLevel'] == 6).sum()
                }
            else:
                # Spieler nicht in diesem Datum - None (nicht 0!)
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    'R10': None, 'R9': None, 'R8': None, 'R7': None, 'R6': None
                }
            player_counts.append(counts)
        
        result[date] = pd.DataFrame(player_counts)
    
    return result

def calculate_player_relic_overview(df_guild, player_base, relic_levels, compare_date):
    """
    Berechnet Relic-Overview basierend auf gecachten Counts (OHNE eigenes Caching).
    Schnell (~10ms) weil nur Summierung gecachter Daten.
    
    Args:
        df_guild: Gefilterte Daten für diese Gilde (aus Cache)
        player_base: DataFrame mit [AllyCode, Name] - einheitliche Spielerliste
        relic_levels: Liste der Relic-Levels zum Zählen (z.B. [8, 9, 10])
        compare_date: Datum für Delta-Vergleich
    
    Returns:
        Tuple: (player_overview, date_columns, available_dates)
    """
    # SKIP wenn nur Styling-Änderung (Checkbox geklickt)
    if not st.session_state.get('recalculate', True):
        # Hole gecachtes Ergebnis aus Session State
        if 'player_overview_relics' in st.session_state:
            # Dummy return - wird nicht verwendet, da player_overview bereits in Session State
            return st.session_state.player_overview_relics, [], []
    
    # Hole gecachte Counts (nur einmal pro Guild berechnet!)
    counts_per_date = get_all_relic_counts_per_date(df_guild, player_base)
    
    available_dates = sorted(counts_per_date.keys(), reverse=True)
    newest_date = available_dates[0]
    
    # Starte mit Spielerliste aus player_base (nicht aus counts!)
    player_overview = player_base.copy()
    
    # Für jedes Datum: Summiere die ausgewählten Relic-Levels
    date_columns = []
    relic_cols = [f'R{r}' for r in relic_levels]
    
    for i, date in enumerate(available_dates):
        df_date_counts = counts_per_date[date]
        
        # Summiere nur die gewählten Relic-Levels - aber nur wenn nicht alle None sind!
        # skipna=False bedeutet: wenn irgendein Wert None ist, bleibt das Ergebnis None
        df_date_counts['RelicCount'] = df_date_counts[relic_cols].sum(axis=1, skipna=False)
        
        col_name = date
        date_columns.append(col_name)
        
        player_overview = player_overview.merge(
            df_date_counts[['AllyCode', 'RelicCount']],
            on='AllyCode',
            how='left'
        )
        player_overview = player_overview.rename(columns={'RelicCount': col_name})
        
        # Alle Spalten als Int64 (erlaubt None für fehlende Spieler)
        player_overview[col_name] = player_overview[col_name].astype('Int64')
    
    # Berechne Delta nur wenn beide Werte vorhanden sind
    if compare_date in available_dates and compare_date != newest_date:
        compare_col = compare_date
        player_overview['Δ'] = player_overview.apply(
            lambda row: row[date_columns[0]] - row[compare_col] 
            if pd.notna(row[date_columns[0]]) and pd.notna(row[compare_col]) else None,
            axis=1
        )
    else:
        player_overview['Δ'] = None
    
    return player_overview, date_columns, available_dates

@st.cache_data
def get_all_omicron_counts_per_date(df_guild, player_base):
    """
    Berechnet ALLE Omicron-Counts pro Spieler und Datum (mit Caching).
    Wird nur einmal pro Guild berechnet.
    
    Args:
        df_guild: Gefilterte Daten für diese Gilde
        player_base: DataFrame mit [AllyCode, Name] - einheitliche Spielerliste
    
    Returns:
        Dict[date, DataFrame]: {date: DataFrame mit [AllyCode, Name, TWOmiCount, GACOmiCount, TBOmiCount, CQOmiCount]}
    """
    available_dates = sorted(df_guild['date'].unique(), reverse=True)
    omicron_cols = ['TWOmiCount', 'GACOmiCount', 'TBOmiCount', 'CQOmiCount']
    
    result = {}
    for date in available_dates:
        df_date = df_guild[df_guild['date'] == date]
        
        # Nur Characters (keine Ships)
        df_chars = df_date[df_date['CombatType'] == 'Character']
        
        # Für alle Spieler in player_base
        player_counts = []
        for _, player_row in player_base.iterrows():
            ally_code = player_row['AllyCode']
            player_name = player_row['Name']
            
            df_player = df_chars[df_chars['AllyCode'] == ally_code]
            
            if not df_player.empty:
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    **{col: df_player[col].sum() for col in omicron_cols}
                }
            else:
                # Spieler nicht in diesem Datum - None (nicht 0!)
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    **{col: None for col in omicron_cols}
                }
            player_counts.append(counts)
        
        result[date] = pd.DataFrame(player_counts)
    
    return result

def calculate_player_omicron_overview(df_guild, player_base, omicron_columns, compare_date):
    """
    Berechnet Omicron-Overview basierend auf gecachten Counts (OHNE eigenes Caching).
    
    Args:
        df_guild: Gefilterte Daten für diese Gilde
        player_base: DataFrame mit [AllyCode, Name] - einheitliche Spielerliste
        omicron_columns: Liste der Omicron-Spalten (z.B. ['TWOmiCount', 'GACOmiCount'])
        compare_date: Datum für Delta-Vergleich
    
    Returns:
        Tuple: (player_overview, date_columns, available_dates)
    """
    # SKIP wenn nur Styling-Änderung (Checkbox geklickt)
    if not st.session_state.get('recalculate', True):
        if 'player_overview_omicrons' in st.session_state:
            return st.session_state.player_overview_omicrons, [], []
    
    # Hole gecachte Counts
    counts_per_date = get_all_omicron_counts_per_date(df_guild, player_base)
    
    available_dates = sorted(counts_per_date.keys(), reverse=True)
    newest_date = available_dates[0]
       
    # Starte mit Spielerliste aus player_base (nicht aus counts!)
    player_overview = player_base.copy()
    
    # Für jedes Datum: Summiere die ausgewählten Omicron-Spalten
    date_columns = []
    for i, date in enumerate(available_dates):
        df_date_counts = counts_per_date[date]
        
        # Summiere nur die gewählten Omicron-Typen - aber nur wenn nicht alle None sind!
        df_date_counts['OmicronCount'] = df_date_counts[omicron_columns].sum(axis=1, skipna=False)
        
        col_name = date
        date_columns.append(col_name)
        
        player_overview = player_overview.merge(
            df_date_counts[['AllyCode', 'OmicronCount']],
            on='AllyCode',
            how='left'
        )
        player_overview = player_overview.rename(columns={'OmicronCount': col_name})
        
        # Alle Spalten als Int64 (erlaubt None für fehlende Spieler)
        player_overview[col_name] = player_overview[col_name].astype('Int64')
    
    # Berechne Delta nur wenn beide Werte vorhanden sind
    if compare_date in available_dates and compare_date != newest_date:
        compare_col = compare_date
        player_overview['Δ'] = player_overview.apply(
            lambda row: row[date_columns[0]] - row[compare_col] 
            if pd.notna(row[date_columns[0]]) and pd.notna(row[compare_col]) else None,
            axis=1
        )
    else:
        player_overview['Δ'] = None
    
    return player_overview, date_columns, available_dates

@st.cache_data
def get_all_speed_mod_counts_per_date(df_guild, player_base):
    """
    Berechnet ALLE Speed-Mod-Counts pro Spieler und Datum (mit Caching).
    Wird nur einmal pro Guild berechnet.
    
    Args:
        df_guild: Gefilterte Daten für diese Gilde
        player_base: DataFrame mit [AllyCode, Name] - einheitliche Spielerliste
    
    Returns:
        Dict[date, DataFrame]: {date: DataFrame mit [AllyCode, Name, Speed10, Speed15, Speed20, Speed25]}
    """
    available_dates = sorted(df_guild['date'].unique(), reverse=True)
    speed_cols = ['Speed10', 'Speed15', 'Speed20', 'Speed25']
    
    result = {}
    for date in available_dates:
        df_date = df_guild[df_guild['date'] == date]
        
        # Nur Characters (keine Ships)
        df_chars = df_date[df_date['CombatType'] == 'Character']
        
        # Für alle Spieler in player_base
        player_counts = []
        for _, player_row in player_base.iterrows():
            ally_code = player_row['AllyCode']
            player_name = player_row['Name']
            
            df_player = df_chars[df_chars['AllyCode'] == ally_code]
            
            if not df_player.empty:
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    **{col: df_player[col].sum() for col in speed_cols}
                }
            else:
                # Spieler nicht in diesem Datum - None (nicht 0!)
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    **{col: None for col in speed_cols}
                }
            player_counts.append(counts)
        
        result[date] = pd.DataFrame(player_counts)
    
    return result

def calculate_player_speed_mod_overview(df_guild, player_base, speed_columns, compare_date):
    """
    Berechnet Speed-Mod-Overview basierend auf gecachten Counts (OHNE eigenes Caching).
    
    Args:
        df_guild: Gefilterte Daten für diese Gilde
        player_base: DataFrame mit [AllyCode, Name] - einheitliche Spielerliste
        speed_columns: Liste der Speed-Spalten (z.B. ['Speed20', 'Speed25'])
        compare_date: Datum für Delta-Vergleich
    
    Returns:
        Tuple: (player_overview, date_columns, available_dates)
    """
    # SKIP wenn nur Styling-Änderung (Checkbox geklickt)
    if not st.session_state.get('recalculate', True):
        if 'player_overview_speed_mods' in st.session_state:
            return st.session_state.player_overview_speed_mods, [], []
    
    # Hole gecachte Counts
    counts_per_date = get_all_speed_mod_counts_per_date(df_guild, player_base)
    
    available_dates = sorted(counts_per_date.keys(), reverse=True)
    newest_date = available_dates[0]
    
    # Starte mit Spielerliste aus player_base (nicht aus counts!)
    player_overview = player_base.copy()
    
    # Für jedes Datum: Summiere die ausgewählten Speed-Spalten
    date_columns = []
    for i, date in enumerate(available_dates):
        df_date_counts = counts_per_date[date]
        
        # Summiere nur die gewählten Speed-Thresholds - aber nur wenn nicht alle None sind!
        df_date_counts['SpeedModCount'] = df_date_counts[speed_columns].sum(axis=1, skipna=False)
        
        col_name = date
        date_columns.append(col_name)
        
        player_overview = player_overview.merge(
            df_date_counts[['AllyCode', 'SpeedModCount']],
            on='AllyCode',
            how='left'
        )
        player_overview = player_overview.rename(columns={'SpeedModCount': col_name})
        
        # Alle Spalten als Int64 (erlaubt None für fehlende Spieler)
        player_overview[col_name] = player_overview[col_name].astype('Int64')
    
    # Berechne Delta nur wenn beide Werte vorhanden sind
    if compare_date in available_dates and compare_date != newest_date:
        compare_col = compare_date
        player_overview['Δ'] = player_overview.apply(
            lambda row: row[date_columns[0]] - row[compare_col] 
            if pd.notna(row[date_columns[0]]) and pd.notna(row[compare_col]) else None,
            axis=1
        )
    else:
        player_overview['Δ'] = None
    
    return player_overview, date_columns, available_dates

def show_player_overview_tab(df_guild, compare_date):
    """Tab 3 - Player Relics mit Relic-Vergleich und Row-Selection."""
    
    # Hole player_base DIREKT aus Session State (nicht als Parameter!)
    player_base = st.session_state.player_base_global
    
    # Initialize session state for player tab filters
    if 'player_relics_selection' not in st.session_state:
        st.session_state.player_relics_selection = ['R10', 'R9', 'R8']
    
    # Header mit Segmented Control in einem Container mit fester Breite
    with st.container(width=750):
        col1, col2 = st.columns([3, 3])
        with col1:
            st.markdown('<h3 style="margin-top: -12px; margin-bottom: 0;">🔟 Player Relics</h3>', unsafe_allow_html=True)
        with col2:
            # Relic Level Segmented Control - iOS-style button group
            relic_options = ['R10', 'R9', 'R8', 'R7', 'R6']
            selected_relics = st.segmented_control(
                "Relic Level",
                options=relic_options,
                default=st.session_state.player_relics_selection,
                key="player_relics_segmented",
                selection_mode="multi",
                label_visibility="collapsed"
            )
            
            # Update session state
            if selected_relics != st.session_state.player_relics_selection:
                st.session_state.player_relics_selection = selected_relics
            
            # Konvertiere zu Relic-Level-Liste (z.B. ['R8', 'R10'] → [8, 10])
            relic_levels = [int(r[1:]) for r in selected_relics] if selected_relics else []
    
    if not relic_levels:
        st.warning("⚠️ Bitte mindestens ein Relic-Level auswählen.")
        return
    
    # Berechne player_overview (df_guild ist bereits gefiltert!)
    player_base_minimal = player_base[['AllyCode', 'Name']].copy()
    player_overview, date_columns, available_dates = calculate_player_relic_overview(
        df_guild, player_base_minimal, relic_levels, compare_date
    )
    
    if len(available_dates) < 2:
        st.warning("⚠️ Mindestens 2 Datenabzüge erforderlich für Vergleich.")
        return
    
    # Merge mit player_base_global (hat Checked/PlayerColor!)
    player_overview = player_overview.merge(
        player_base[['AllyCode', 'Checked', 'PlayerColor']], 
        on='AllyCode', 
        how='left'
    )
    
    # Füge Label-Spalte hinzu
    sorted_relics = sorted(selected_relics, key=lambda x: int(x[1:]), reverse=True)
    selected_label = ' '.join(sorted_relics)
    player_overview['Metric'] = selected_label
    
    # KEINE Checkbox-Spalte mehr - wird durch Row-Selection ersetzt!
    
    # Sortiere nach Delta
    player_overview = player_overview.sort_values('Δ', ascending=False, na_position='last')
    player_overview = player_overview.reset_index(drop=True)
    
    # Erstelle Mapping für Styling
    player_color_mapping = dict(zip(player_overview['Name'], player_overview['PlayerColor']))
    
    # Spalten neu ordnen - OHNE ✓!
    column_order = ['Name', 'AllyCode', 'Δ', 'Metric'] + date_columns
    player_overview = player_overview[column_order]
    
    # Styling für checked players - nutzt PlayerColor aus Mapping
    def highlight_checked_players(row):
        # Hole checked-Status aus player_base
        player_name = row['Name']
        is_checked = player_base.loc[player_base['Name'] == player_name, 'Checked'].iloc[0] if player_name in player_base['Name'].values else False
        
        if is_checked:
            color = player_color_mapping.get(player_name, '#CCCCCC')
            return [f'background-color: {color}99' for _ in row]
        else:
            return ['' for _ in row]
    
    # Styling anwenden
    styled_df = player_overview.style.apply(highlight_checked_players, axis=1)
    
    # Spalten-Konfiguration - KEINE Checkbox-Spalte mehr!
    column_config = {
        'Name': st.column_config.TextColumn('Player Name', width=175),
        'AllyCode': st.column_config.TextColumn('AllyCode', width=120),
        'Δ': st.column_config.NumberColumn(
            'Δ',
            help='Änderung seit letztem Datenabzug (nur bei Spielern in beiden CSVs)',
            format='%+d',
            width=80
        ),
        'Metric': st.column_config.TextColumn('Metric', width=110)
    }
    
    # Datums-Spalten als Zahlen
    for col in date_columns:
        column_config[col] = st.column_config.NumberColumn(col, format='%d', width=120)
    
    # on_select Callback für Cell-Selection
    def on_relics_select():
        """Callback wenn Spieler-Zelle ausgewählt wird - toggle den Spieler der Zeile."""
        # Hole Selection-Event
        selection = st.session_state.player_relics_table_selection
        
        # Zugriff auf selection dict
        if hasattr(selection, 'selection'):
            sel_dict = selection.selection
        elif isinstance(selection, dict):
            sel_dict = selection.get('selection', {})
        else:
            return
        
        selected_cells = sel_dict.get('cells', [])
        
        # Extrahiere Zeilen-Index: (row_idx, column_name)
        if selected_cells:
            cell = selected_cells[0]
            if isinstance(cell, (list, tuple)) and len(cell) >= 1:
                row_idx = cell[0]
            elif isinstance(cell, dict):
                row_idx = cell.get('row', 0)
            else:
                return
            
            player_name = player_overview.iloc[row_idx]['Name']
            
            if player_name in st.session_state.player_base_global['Name'].values:
                # Toggle: checked → unchecked, unchecked → checked
                current_state = st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ].iloc[0]
                
                st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ] = not current_state
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width="content",
        height=1100,
        row_height=21,
        column_config=column_config,
        selection_mode="single-cell",
        on_select=on_relics_select,
        key="player_relics_table_selection"
    )


def show_player_omicrons_tab(df_guild, compare_date):
    """Tab 4 - Player Omicrons mit Omicron-Vergleich und Row-Selection."""
    
    # Hole player_base DIREKT aus Session State (nicht als Parameter!)
    player_base = st.session_state.player_base_global
    
    # Initialize session state for player tab filters
    if 'player_omicrons_selection' not in st.session_state:
        st.session_state.player_omicrons_selection = ['TW', 'GAC']
    
    # Header mit Segmented Control in einem Container mit fester Breite
    with st.container(width=750):
        col1, col2 = st.columns([3, 3])
        with col1:
            st.markdown('<h3 style="margin-top: -12px; margin-bottom: 0;">🏐 Player Omicrons</h3>', unsafe_allow_html=True)
        with col2:
            # Omicron Type Segmented Control - iOS-style button group
            omicron_options = {
                'TW': 'TWOmiCount',
                'GAC': 'GACOmiCount',
                'TB': 'TBOmiCount',
                'CQ': 'CQOmiCount'
            }
            selected_omicrons = st.segmented_control(
                "Omicron Type",
                options=list(omicron_options.keys()),
                default=st.session_state.player_omicrons_selection,
                key="player_omicrons_segmented",
                selection_mode="multi",
                label_visibility="collapsed"
            )
            
            # Update session state
            if selected_omicrons != st.session_state.player_omicrons_selection:
                st.session_state.player_omicrons_selection = selected_omicrons
            
            # Konvertiere zu Spalten-Liste
            omicron_columns = [omicron_options[omi] for omi in selected_omicrons] if selected_omicrons else []
    
    if not omicron_columns:
        st.warning("⚠️ Bitte mindestens einen Omicron-Type auswählen.")
        return
    
    # Berechne player_overview (df_guild ist bereits gefiltert!)
    player_base_minimal = player_base[['AllyCode', 'Name']].copy()
    player_overview, date_columns, available_dates = calculate_player_omicron_overview(
        df_guild, player_base_minimal, omicron_columns, compare_date
    )
    
    if len(available_dates) < 2:
        st.warning("⚠️ Mindestens 2 Datenabzüge erforderlich für Vergleich.")
        return
    
    # Merge mit player_base_global (hat Checked/PlayerColor!)
    player_overview = player_overview.merge(
        player_base[['AllyCode', 'Checked', 'PlayerColor']], 
        on='AllyCode', 
        how='left'
    )
    
    # Füge Label-Spalte hinzu
    sorted_omicrons = sorted(selected_omicrons, reverse=True)
    selected_label = ' '.join(sorted_omicrons)
    player_overview['Metric'] = selected_label
    
    # KEINE Checkbox-Spalte mehr - wird durch Row-Selection ersetzt!
    
    # Sortiere nach Delta
    player_overview = player_overview.sort_values('Δ', ascending=False, na_position='last')
    player_overview = player_overview.reset_index(drop=True)
    
    # Erstelle Mapping für Styling
    player_color_mapping = dict(zip(player_overview['Name'], player_overview['PlayerColor']))
    
    # Spalten neu ordnen - OHNE ✓!
    column_order = ['Name', 'AllyCode', 'Δ', 'Metric'] + date_columns
    player_overview = player_overview[column_order]
    
    # Styling für checked players - nutzt PlayerColor aus Mapping
    def highlight_checked_players(row):
        # Hole checked-Status aus player_base
        player_name = row['Name']
        is_checked = player_base.loc[player_base['Name'] == player_name, 'Checked'].iloc[0] if player_name in player_base['Name'].values else False
        
        if is_checked:
            color = player_color_mapping.get(player_name, '#CCCCCC')
            return [f'background-color: {color}99' for _ in row]
        else:
            return ['' for _ in row]
    
    # Styling anwenden
    styled_df = player_overview.style.apply(highlight_checked_players, axis=1)
    
    # Spalten-Konfiguration - KEINE Checkbox-Spalte mehr!
    column_config = {
        'Name': st.column_config.TextColumn('Player Name', width=175),
        'AllyCode': st.column_config.TextColumn('AllyCode', width=120),
        'Δ': st.column_config.NumberColumn(
            'Δ',
            help='Änderung seit letztem Datenabzug (nur bei Spielern in beiden CSVs)',
            format='%+d',
            width=80
        ),
        'Metric': st.column_config.TextColumn('Metric', width=110)
    }
    
    # Datums-Spalten als Zahlen
    for col in date_columns:
        column_config[col] = st.column_config.NumberColumn(col, format='%d', width=120)
    
    # on_select Callback für Cell-Selection
    def on_omicrons_select():
        """Callback wenn Spieler-Zelle ausgewählt wird - toggle den Spieler der Zeile."""
        # Hole Selection-Event
        selection = st.session_state.player_omicrons_table_selection
        
        # Zugriff auf selection dict
        if hasattr(selection, 'selection'):
            sel_dict = selection.selection
        elif isinstance(selection, dict):
            sel_dict = selection.get('selection', {})
        else:
            return
        
        selected_cells = sel_dict.get('cells', [])
        
        # Extrahiere Zeilen-Index: (row_idx, column_name)
        if selected_cells:
            cell = selected_cells[0]
            if isinstance(cell, (list, tuple)) and len(cell) >= 1:
                row_idx = cell[0]
            elif isinstance(cell, dict):
                row_idx = cell.get('row', 0)
            else:
                return
            
            player_name = player_overview.iloc[row_idx]['Name']
            
            if player_name in st.session_state.player_base_global['Name'].values:
                # Toggle: checked → unchecked, unchecked → checked
                current_state = st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ].iloc[0]
                
                st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ] = not current_state
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width="content",
        height=1100,
        row_height=21,
        column_config=column_config,
        selection_mode="single-cell",
        on_select=on_omicrons_select,
        key="player_omicrons_table_selection"
    )


def show_player_speed_mods_tab(df_guild, compare_date):
    """Tab 5 - Player Speed Mods mit Speed-Vergleich und Row-Selection."""
    
    # Hole player_base DIREKT aus Session State (nicht als Parameter!)
    player_base = st.session_state.player_base_global
    
    # Initialize session state for player tab filters
    if 'player_speed_mods_selection' not in st.session_state:
        st.session_state.player_speed_mods_selection = ['20+', '25+']
    
    # Header mit Segmented Control in einem Container mit fester Breite
    with st.container(width=750):
        col1, col2 = st.columns([3, 3])
        with col1:
            st.markdown('<h3 style="margin-top: -12px; margin-bottom: 0;">🎲 Player Speed Mods</h3>', unsafe_allow_html=True)
        with col2:
            # Speed Threshold Segmented Control - iOS-style button group
            speed_options = {
                '25+': 'Speed25',
                '20+': 'Speed20',                
                '15+': 'Speed15',
                '10+': 'Speed10'
            }
            selected_speeds = st.segmented_control(
                "Speed Threshold",
                options=list(speed_options.keys()),
                default=st.session_state.player_speed_mods_selection,
                key="player_speed_mods_segmented",
                selection_mode="multi",
                label_visibility="collapsed"
            )
            
            # Update session state
            if selected_speeds != st.session_state.player_speed_mods_selection:
                st.session_state.player_speed_mods_selection = selected_speeds
            
            # Konvertiere zu Spalten-Liste
            speed_columns = [speed_options[speed] for speed in selected_speeds] if selected_speeds else []
    
    if not speed_columns:
        st.warning("⚠️ Bitte mindestens einen Speed-Threshold auswählen.")
        return
    
    # Berechne player_overview (df_guild ist bereits gefiltert!)
    player_base_minimal = player_base[['AllyCode', 'Name']].copy()
    player_overview, date_columns, available_dates = calculate_player_speed_mod_overview(
        df_guild, player_base_minimal, speed_columns, compare_date
    )
    
    if len(available_dates) < 2:
        st.warning("⚠️ Mindestens 2 Datenabzüge erforderlich für Vergleich.")
        return
    
    # Merge mit player_base_global (hat Checked/PlayerColor!)
    player_overview = player_overview.merge(
        player_base[['AllyCode', 'Checked', 'PlayerColor']], 
        on='AllyCode', 
        how='left'
    )
    
    # Füge Label-Spalte hinzu
    sorted_speeds = sorted(selected_speeds, key=lambda x: int(x[:-1]), reverse=True)
    selected_label = ' '.join(sorted_speeds)
    player_overview['Metric'] = selected_label
    
    # KEINE Checkbox-Spalte mehr - wird durch Row-Selection ersetzt!
    
    # Sortiere nach Delta
    player_overview = player_overview.sort_values('Δ', ascending=False, na_position='last')
    player_overview = player_overview.reset_index(drop=True)
    
    # Erstelle Mapping für Styling
    player_color_mapping = dict(zip(player_overview['Name'], player_overview['PlayerColor']))
    
    # Spalten neu ordnen - OHNE ✓!
    column_order = ['Name', 'AllyCode', 'Δ', 'Metric'] + date_columns
    player_overview = player_overview[column_order]
    
    # Styling für checked players - nutzt PlayerColor aus Mapping
    def highlight_checked_players(row):
        # Hole checked-Status aus player_base
        player_name = row['Name']
        is_checked = player_base.loc[player_base['Name'] == player_name, 'Checked'].iloc[0] if player_name in player_base['Name'].values else False
        
        if is_checked:
            color = player_color_mapping.get(player_name, '#CCCCCC')
            return [f'background-color: {color}99' for _ in row]
        else:
            return ['' for _ in row]
    
    # Styling anwenden
    styled_df = player_overview.style.apply(highlight_checked_players, axis=1)
    
    # Spalten-Konfiguration - KEINE Checkbox-Spalte mehr!
    column_config = {
        'Name': st.column_config.TextColumn('Player Name', width=175),
        'AllyCode': st.column_config.TextColumn('AllyCode', width=120),
        'Δ': st.column_config.NumberColumn(
            'Δ',
            help='Änderung seit letztem Datenabzug (nur bei Spielern in beiden CSVs)',
            format='%+d',
            width=80
        ),
        'Metric': st.column_config.TextColumn('Metric', width=110)
    }
    
    # Datums-Spalten als Zahlen
    for col in date_columns:
        column_config[col] = st.column_config.NumberColumn(col, format='%d', width=120)
       
    # on_select Callback für Cell-Selection
    def on_speed_mods_select():
        """Callback wenn Spieler-Zelle ausgewählt wird - toggle den Spieler der Zeile."""
        # Hole Selection-Event
        selection = st.session_state.player_speed_mods_table_selection
        
        # Zugriff auf selection dict
        if hasattr(selection, 'selection'):
            sel_dict = selection.selection
        elif isinstance(selection, dict):
            sel_dict = selection.get('selection', {})
        else:
            return
        
        selected_cells = sel_dict.get('cells', [])
        
        # Extrahiere Zeilen-Index: (row_idx, column_name)
        if selected_cells:
            cell = selected_cells[0]
            if isinstance(cell, (list, tuple)) and len(cell) >= 1:
                row_idx = cell[0]
            elif isinstance(cell, dict):
                row_idx = cell.get('row', 0)
            else:
                return
            
            player_name = player_overview.iloc[row_idx]['Name']
            
            if player_name in st.session_state.player_base_global['Name'].values:
                # Toggle: checked → unchecked, unchecked → checked
                current_state = st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ].iloc[0]
                
                st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ] = not current_state
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width="content",
        height=1100,
        row_height=21,
        column_config=column_config,
        selection_mode="single-cell",
        on_select=on_speed_mods_select,
        key="player_speed_mods_table_selection"
    )


def show_settings_tab(df):
    """Tab 6 - Settings & Data Management."""
    st.header("⚙️ Settings")
    
    # UI Settings
    st.markdown('<h3 style="margin-top: -12px; margin-bottom: 0;">🎨 UI Einstellungen</h3>', unsafe_allow_html=True)
    
    # Toggle für Streamlit Header (Deploy-Button, Clear Cache)
    if 'show_header' not in st.session_state:
        st.session_state.show_header = True
    
    show_header = st.toggle(
        "Streamlit Menü anzeigen (Deploy, Clear Cache)",
        value=st.session_state.show_header,
        help="Blendet das Streamlit-Menü oben rechts ein/aus"
    )
    
    if show_header != st.session_state.show_header:
        st.session_state.show_header = show_header
        st.rerun()
    
    st.divider()
    
    # Info-Bereich
    st.markdown('<h3 style="margin-top: -12px; margin-bottom: 0;">ℹ️ App Information</h3>', unsafe_allow_html=True)
    st.markdown(f"""
    - **Geladene CSVs:** {len(df['date'].unique())} Datenabzüge
    - **Verfügbare Daten:** {', '.join(sorted(df['date'].unique(), reverse=True))}
    - **Gesamt-Einträge:** {len(df):,} Zeilen
    - **Memory:** {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB
    - **Spieler (neueste CSV):** {df[df['date'] == df['date'].max()]['AllyCode'].nunique()}
    """)

def main():
    st.set_page_config(
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'About': "SWGOH Guild Roster Analyzer by DrPivot"
        }
    )
    
    # CSS für kompakteres Layout
    # Header-Visibility dynamisch basierend auf Settings
    if 'show_header' not in st.session_state:
        st.session_state.show_header = True
    
    header_css = "" if st.session_state.show_header else """
        /* Versteckt Streamlit Header komplett */
        header[data-testid="stHeader"] {
            display: none;
        }
    """
    
    st.markdown(f"""
        <style>
        {header_css}
        /* Reduziert Abstände über Filter und Tabs */
        .block-container {{
            padding-top: 3rem;
            padding-bottom: 0rem;
        }}
        /* Fix für collapsed label bei segmented_control */
        div[data-testid="stSegmentedControl"] {{
            margin-top: 2rem;
        }}
        /* Sidebar kompakter und breiter */
        section[data-testid="stSidebar"] > div {{
            padding-top: 0rem;
        }}
        /* Sidebar-Breite erhöhen (pills nebeneinander) */
        section[data-testid="stSidebar"] {{
            width: 380px !important;
            min-width: 380px !important;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    # Prüfe ob Analysis bereits gestartet wurde
    if 'analysis_started' not in st.session_state:
        show_start_screen()
        return  # Stop hier - zeige nur Startbildschirm
    
    # Ab hier: Analysis-Modus (nach Start-Button)
    
    # Lade Daten basierend auf Auswahl
    guild_filter = st.session_state.selected_guild
    selected_dates = st.session_state.selected_dates

    # Zeige ausgewählte Guild und Dates
    has_upload = 'uploaded_csv_df' in st.session_state
    data_info = f"{len(selected_dates)} CSV(s)" + (" + 1 Upload" if has_upload else "")
    st.sidebar.info(f"**Gilde:** {guild_filter}\n\n**Daten:** {data_info}")
    
    # Bereite Upload-Daten für Cache vor (falls vorhanden)
    upload_csv_data = None
    upload_date = None
    upload_guild = None
    if has_upload:
        # Nutze bereits gespeicherten CSV-String (wurde beim Upload erstellt!)
        upload_csv_data = st.session_state.get('uploaded_csv_data', None)
        upload_date = st.session_state.get('uploaded_csv_date', datetime.now().strftime('%Y-%m-%d'))
        upload_guild = st.session_state.get('uploaded_csv_guild', None)
    
    # Lade Daten (GECACHT - Upload wird im Cache gespeichert!)
    df = get_final_df(guild_filter, tuple(selected_dates), upload_csv_data, upload_date, upload_guild)

    if df is None or df.empty:
        st.error("❌ Fehler beim Laden der Daten!")
        if df is not None and df.empty:
            st.error("🚫 Zugriff verweigert: Diese Gilde ist nicht im Repository!")
            st.info("💡 Nur Gilden aus dem BΛ Bataillon dürfen das Tool nutzen.")
        if st.button("↩️ Zurück zur Auswahl"):
            # Upload bleibt erhalten - nur analysis_started zurücksetzen
            del st.session_state['analysis_started']
            st.rerun()
        return
    
    # Button um zurück zur Auswahl zu gehen
    if st.sidebar.button("↩️ Neue Auswahl"):
        # Clear NUR analysis_started - Upload bleibt erhalten!
        del st.session_state['analysis_started']
        st.rerun()
        
    # Seitenleiste für Filter
        
    # Verfügbare Daten aus geladenen CSVs
    available_dates = sorted(df['date'].unique(), reverse=True)
    date_filter = available_dates[0]  # Neuestes Datum
    
    # Datum für Delta-Vergleich
    default_compare_index = 1 if len(available_dates) >= 2 else 0
    compare_date = st.sidebar.selectbox(
        "Datum für Delta-Vergleich:", 
        available_dates, 
        index=default_compare_index,
        key="compare_date_select"
    )
    
    # Filtere DataFrame nach Date (Guild ist bereits gefiltert durch get_final_df!)
    df_filtered = df[df['date'] == date_filter]
    
    if df_filtered.empty:
        st.error("❌ Keine Daten für das ausgewählte Datum gefunden.")
        return
    
    # Lade Charakterdaten und Schiffsdaten für dynamische Filter
    characters_data = load_units_data()
    
    # Dynamische Filter mit gegenseitiger Beeinflussung
    st.sidebar.markdown("---")  # Trennlinie
    st.sidebar.markdown("**🎛️ Charakter Filter:**")
    
    # Initialize session state for filters
    if 'combat_type_filter' not in st.session_state:
        st.session_state.combat_type_filter = []
    if 'alignment_filter' not in st.session_state:
        st.session_state.alignment_filter = []
    if 'categories_filter' not in st.session_state:
        st.session_state.categories_filter = []
    if 'role_filter' not in st.session_state:
        st.session_state.role_filter = []
    if 'ability_classes_filter' not in st.session_state:
        st.session_state.ability_classes_filter = []
    
    # Reset counter für unique keys
    if 'filter_reset_counter' not in st.session_state:
        st.session_state.filter_reset_counter = 0
    
    # Unique keys basierend auf reset counter
    reset_suffix = f"_{st.session_state.filter_reset_counter}"
    
    # CombatType Filter (erste Position) - direkt aus CSV
    available_combat_types = sorted(df_filtered['CombatType'].unique())
    
    # Segmented Control für CombatType
    combat_type_filter = st.sidebar.segmented_control(
        "Combat Type",
        options=available_combat_types,
        default=st.session_state.get('combat_type_filter', []),
        key=f"combat_type_segmented{reset_suffix}",
        selection_mode="multi",
        label_visibility="collapsed"
    )
    # Update session state nur wenn sich Wert geändert hat
    if combat_type_filter != st.session_state.get('combat_type_filter', []):
        st.session_state.combat_type_filter = combat_type_filter
    
    # Filtere DataFrame nach CombatType
    if combat_type_filter:
        df_filtered = df_filtered[df_filtered['CombatType'].isin(combat_type_filter)]
    
    # Filtere characters_data auf BaseIds, die im aktuellen df_filtered vorhanden sind
    # Das stellt sicher, dass nur relevante Optionen (z.B. nur Ships) in den Filtern angezeigt werden
    available_base_ids = set(df_filtered['BaseId'].unique())
    characters_data_filtered = [char for char in characters_data if char.get('base_id') in available_base_ids]
    
    # Alle verfügbaren Optionen sammeln (nur aus den im DataFrame vorhandenen Units)
    all_alignments = sorted(list({char.get('alignment', '') for char in characters_data_filtered if char.get('alignment')}))
    
    # Gesinnung Filter (Segmented Control)
    alignment_filter = st.sidebar.segmented_control(
        "Gesinnung",
        options=all_alignments,
        default=st.session_state.get('alignment_filter', []),
        key=f"alignment_segmented{reset_suffix}",
        selection_mode="multi",
        label_visibility="collapsed"
    )
    # Update session state nur wenn sich Wert geändert hat
    if alignment_filter != st.session_state.get('alignment_filter', []):
        st.session_state.alignment_filter = alignment_filter
    
    # Filtere Charaktere basierend auf aktueller Auswahl für nachfolgende Filter
    filtered_chars_for_categories = characters_data_filtered
    if alignment_filter:
        filtered_chars_for_categories = [char for char in filtered_chars_for_categories if char.get('alignment') in alignment_filter]
    
    # Verfügbare Kategorien basierend auf Gesinnung
    available_categories = sorted(list({cat for char in filtered_chars_for_categories for cat in char.get('categories', [])}))
    
    # Verfügbare Rollen basierend auf vorherigen Filtern (vor Kategorie berechnen)
    filtered_chars_for_roles = filtered_chars_for_categories
    roles_set = set()
    for char in filtered_chars_for_roles:
        role = char.get('role')
        if role and role.strip():
            if role != 'Unknown':  # "Unknown" wird nicht angezeigt
                roles_set.add(role)
        else:  # Keine Rolle vorhanden
            roles_set.add('?')
    available_roles = sorted(list(roles_set))
    
    # Rolle Filter (Segmented Control) - jetzt vor Kategorie
    role_filter = st.sidebar.segmented_control(
        "Rolle",
        options=available_roles,
        default=[role for role in st.session_state.get('role_filter', []) if role in available_roles],
        key=f"role_segmented{reset_suffix}",
        selection_mode="multi",
        label_visibility="collapsed"
    )
    # Update session state nur wenn sich Wert geändert hat
    if role_filter != st.session_state.get('role_filter', []):
        st.session_state.role_filter = role_filter
    
    # Kategorie Filter (Multiselect) - jetzt nach Rolle
    categories_filter = st.sidebar.multiselect(
        "Categories:",
        options=available_categories,
        default=[cat for cat in st.session_state.get('categories_filter', []) if cat in available_categories],
        key=f"categories_multiselect{reset_suffix}"
    )
    # Update session state nur wenn sich Wert geändert hat
    if categories_filter != st.session_state.get('categories_filter', []):
        st.session_state.categories_filter = categories_filter
    
    # Filtere weiter für Fähigkeitsklassen (basierend auf Rolle und Kategorie)
    filtered_chars_for_abilities = filtered_chars_for_categories
    if role_filter:
        filtered_chars_for_abilities = [char for char in filtered_chars_for_abilities if char.get('role') in role_filter]
    if categories_filter:
        filtered_chars_for_abilities = [char for char in filtered_chars_for_abilities 
                                  if any(cat in char.get('categories', []) for cat in categories_filter)]
    
    # Verfügbare Fähigkeitsklassen basierend auf vorherigen Filtern
    available_ability_classes = sorted(list({ac for char in filtered_chars_for_abilities for ac in char.get('ability_classes', [])}))
    
    # Fähigkeitsklasse Filter (Chips)
    ability_classes_filter = st.sidebar.multiselect(
        "Ability classes:",
        options=available_ability_classes,
        default=[ac for ac in st.session_state.get('ability_classes_filter', []) if ac in available_ability_classes],
        key=f"ability_classes_multiselect{reset_suffix}"
    )
    # Update session state nur wenn sich Wert geändert hat
    if ability_classes_filter != st.session_state.get('ability_classes_filter', []):
        st.session_state.ability_classes_filter = ability_classes_filter
    
    # Filter zurücksetzen Button
    if st.sidebar.button("🗑️ Alle Filter zurücksetzen"):
        # Reset counter erhöhen für neue Widget-Keys
        st.session_state.filter_reset_counter += 1
        # Session state zurücksetzen - Sidebar-Filter UND selected_character_tab2
        st.session_state.combat_type_filter = []
        st.session_state.alignment_filter = []
        st.session_state.categories_filter = []
        st.session_state.role_filter = []
        st.session_state.ability_classes_filter = []
        # Lösche selected_character_tab2, damit er neu initialisiert wird
        if 'selected_character_tab2' in st.session_state:
            del st.session_state.selected_character_tab2
        st.rerun()
    
    # Filter anwenden
    filtered_characters = apply_filters(
        characters_data, 
        alignment_filter, 
        categories_filter, 
        role_filter, 
        ability_classes_filter
    )
    
    # Prüfe ob irgendwelche Filter aktiv sind
    filters_active = bool(alignment_filter or categories_filter or role_filter or ability_classes_filter)
    
    st.sidebar.markdown("---")  # Trennlinie
    
    # Character-Filter für Tab 2
    st.sidebar.markdown("**☯ Character Auswahl:**")
    if filters_active:
        if filtered_characters:
            available_characters_tab2 = [(char['name'], char['base_id']) for char in filtered_characters]
        else:
            available_characters_tab2 = []  # Filter aktiv aber keine Treffer
    else:
        available_characters_tab2 = [(char['name'], char['base_id']) for char in characters_data]
    
    character_names_tab2 = [name for name, base_id in available_characters_tab2]
    
    if character_names_tab2:
        # Character-Dropdown für Tab 2
        selected_character_tab2 = st.sidebar.selectbox(
            "Charakter für Tab 2:",
            character_names_tab2,
            key="tab2_character_select"
        )
        
        # Session State aktualisieren
        if 'selected_character_tab2' not in st.session_state:
            st.session_state.selected_character_tab2 = selected_character_tab2
        else:
            if st.session_state.selected_character_tab2 != selected_character_tab2:
                st.session_state.selected_character_tab2 = selected_character_tab2
    
    # Player Uncheck Button am Ende der Sidebar
    st.sidebar.markdown("---")
    if st.sidebar.button("❌ Uncheck All", key="uncheck_all_btn", use_container_width=True):
        if 'player_base_global' in st.session_state:
            st.session_state.player_base_global['Checked'] = False
            st.rerun()
    
    # GLOBALES PLAYER_BASE in Session State - EINMALIG initialisieren!
    # Dies ist die zentrale Datenstruktur für ALLE Player-Tabs
    if 'player_base_global' not in st.session_state or st.session_state.get('current_guild') != guild_filter:
        # Verwende df (bereits gefiltert nach Guild!)
        available_dates_list = sorted(df['date'].unique(), reverse=True)
        newest_date = available_dates_list[0]
        df_newest = df[df['date'] == newest_date]
        player_base = df_newest[['AllyCode', 'Name']].drop_duplicates().copy()
        player_base = player_base.sort_values('Name').reset_index(drop=True)
        
        # Füge PlayerColor UND Checked-Status hinzu
        player_base['PlayerColor'] = [
            PLAYER_COLOR_PALETTE[i % len(PLAYER_COLOR_PALETTE)] 
            for i in range(len(player_base))
        ]
        player_base['Checked'] = False  # Default: niemand gecheckt
        
        # DEFAULT_PLAYER automatisch checken
        if DEFAULT_PLAYER in player_base['Name'].values:
            player_base.loc[player_base['Name'] == DEFAULT_PLAYER, 'Checked'] = True
        
        # Speichere in Session State
        st.session_state.player_base_global = player_base
        st.session_state.current_guild = guild_filter
    
    # Hole globales player_base (shared across all tabs!)
    player_base = st.session_state.player_base_global
    
    # Tab-Navigation mit Segmented Control - NUR aktiver Tab wird gerendert!
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "📋 Character Overview"
        
    selected_tab = st.segmented_control(
        "Navigation",
        options=["📋 Character Overview", "📊 Character Stats", "🔟 Player Relics", 
                 "🏐 Player Omicrons", "🎲 Player Speed Mods", "⚙️ Settings"],
            default=st.session_state.active_tab,
            key="main_navigation",
            selection_mode="single",
            label_visibility="collapsed"
        )
    
    # Update active tab
    st.session_state.active_tab = selected_tab
    
    # CONDITIONAL RENDERING - nur aktiver Tab wird ausgeführt!
    if selected_tab == "📋 Character Overview":
        show_character_overview(df_filtered, filtered_characters, characters_data, filters_active)
    elif selected_tab == "📊 Character Stats":
        show_analytics_tab(df_filtered, filtered_characters, characters_data, filters_active)
    elif selected_tab == "🔟 Player Relics":
        show_player_overview_tab(df, compare_date)
    elif selected_tab == "🏐 Player Omicrons":
        show_player_omicrons_tab(df, compare_date)
    elif selected_tab == "🎲 Player Speed Mods":
        show_player_speed_mods_tab(df, compare_date)
    elif selected_tab == "⚙️ Settings":
        show_settings_tab(df)

if __name__ == "__main__":
    main()