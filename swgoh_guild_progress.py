import streamlit as st
import pandas as pd
import json
import glob
import re
import plotly.graph_objects as go
import locale
from datetime import datetime
from io import StringIO
import os
import sys

# Encryption (optional - nur wenn verschlüsselte CSVs vorhanden)
try:
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False

# ============================================================================
# KONFIGURATION
# ============================================================================
DEFAULT_ALLY_CODE = "817994826"  # Default AllyCode for highlighting (DrPivot)

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

# Tab Names as Constants
TAB_OVERVIEW = "📑 Overview"
TAB_CHAR_STATS = "📊 Char Stats"
TAB_PROGRESS = "📈 Progress"
TAB_MOD_DISTRIBUTION = "⚖️ Mod Distribution"
TAB_INFO = "ℹ️ App-Info"

# Mod Slot Constants
MOD_ARROW = '↗'
MOD_TRIANGLE = '▲'
MOD_CIRCLE = '●'
MOD_CROSS = '✙'

# Mod Slot Display Names (for segmented control)
# SLOT_ARROW = f'{MOD_ARROW} Arrow'
# SLOT_TRIANGLE = f'{MOD_TRIANGLE} Triangle'
# SLOT_CIRCLE = f'{MOD_CIRCLE} Circle'
# SLOT_CROSS = f'{MOD_CROSS} Cross'
SLOT_ARROW = MOD_ARROW
SLOT_TRIANGLE = MOD_TRIANGLE
SLOT_CIRCLE = MOD_CIRCLE
SLOT_CROSS = MOD_CROSS

# Mod Slot Keys (for data mapping)
SLOT_KEY_ARROW = 'Arrow'
SLOT_KEY_TRIANGLE = 'Triangle'
SLOT_KEY_CIRCLE = 'Circle'
SLOT_KEY_CROSS = 'Cross'

# Combat Types (constant - nur Character und Ship)
COMBAT_TYPES = ['Character', 'Ship']

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
        st.error("❌ characters.json not found!")
        return []
    except json.JSONDecodeError:
        st.error("❌ Error loading characters.json!")
        return []


@st.cache_data
def load_ship_data():
    """Lädt die Schiffsdaten aus der JSON-Datei."""
    try:
        with open('data/ships.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning("⚠️ ships.json not found!")
        return []
    except json.JSONDecodeError:
        st.error("❌ Error loading ships.json!")
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
def load_character_relevance_data():
    """Lädt character_relevance.csv mit key_character Flag, relic_rec und notes."""
    try:
        df = pd.read_csv('data/character_relevance.csv')
        # Erstelle Dict: BaseID -> key_character (yes/no)
        relevance_dict = dict(zip(df['BaseID'], df['key_character']))
        # Erstelle Dict: BaseID -> relic_rec (empfohlenes Relic-Level)
        relic_rec_dict = dict(zip(df['BaseID'], df['relic_rec']))
        # Erstelle Dict: BaseID -> notes (Kommentar)
        notes_dict = dict(zip(df['BaseID'], df['notes']))
        return relevance_dict, relic_rec_dict, notes_dict
    except FileNotFoundError:
        st.warning("⚠️ character_relevance.csv not found!")
        return {}, {}, {}
    except Exception as e:
        st.error(f"❌ Error loading character_relevance.csv: {e}")
        return {}, {}, {}

@st.cache_data
def load_relic_costs():
    """Lädt relic_costs_cumulative.json mit kumulierten Materialkosten pro Relic-Level."""
    try:
        with open('data/relic_costs_cumulative.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ relic_costs_cumulative.json not found!")
        return {}
    except json.JSONDecodeError:
        st.error("❌ Invalid JSON in relic_costs_cumulative.json!")
        return {}

def calculate_total_relic_costs(char_overview, player_relic_dict, relic_rec_dict, relic_costs):
    """
    Berechnet Gesamtkosten aller Materialien für alle Characters im char_overview.
    Nur für Characters mit gültigen current + target relic levels.
    
    Args:
        char_overview: DataFrame mit 'Character' und BaseId im Index
        player_relic_dict: {BaseId: current_relic_level}
        relic_rec_dict: {BaseId: recommended_relic_level}
        relic_costs: Dict aus load_relic_costs() mit kumulierten Kosten
    
    Returns:
        Dict mit {material_name: total_cost}
    """
    # Initialize totals for all materials (exclude credits)
    material_keys = [
        'fragmented_signal_data', 'incomplete_signal_data', 'flawed_signal_data',
        'corrupted_signal_data', 'carbonite_circuit_board', 'bronzium_wiring',
        'chromium_transistor', 'aurodium_heatsink', 'electrium_conductor',
        'zinbiddle_card', 'impulse_detector', 'aeromagnifier',
        'gyrda_keypad', 'droid_brain', 'coaxial_servomotors'
    ]
    
    totals = {key: 0 for key in material_keys}
    
    # Iterate over all characters in overview
    for base_id in char_overview.index:
        current_level = player_relic_dict.get(base_id, None)
        target_level = relic_rec_dict.get(base_id, None)
        
        # Skip if either level is missing or current >= target
        if current_level is None or target_level is None:
            continue
        if pd.isna(current_level) or pd.isna(target_level):
            continue
        if current_level >= target_level:
            continue
        
        # Calculate cost: costs[0_to_target] - costs[0_to_current]
        target_key = f"0_to_{int(target_level)}"
        current_key = f"0_to_{int(current_level)}"
        
        if target_key not in relic_costs or current_key not in relic_costs:
            continue
        
        target_costs = relic_costs[target_key]
        current_costs = relic_costs[current_key]
        
        # Add difference to totals
        for material in material_keys:
            totals[material] += target_costs[material] - current_costs[material]
    
    return totals

@st.cache_data
def get_available_guilds():
    """Scannt hu_data Ordner und gibt Liste aller Guilds zurück (plain + encrypted CSVs)."""
    pattern_plain = "hu_data/*Full.csv"
    pattern_encrypted = "hu_data/*Full.csv.encrypted"
    
    files_plain = glob.glob(pattern_plain)
    files_encrypted = glob.glob(pattern_encrypted)
    
    # Entferne .encrypted aus Plain-Liste (falls beide existieren)
    files_plain = [f for f in files_plain if f"{f}.encrypted" not in files_encrypted]
    
    all_files = files_plain + files_encrypted
    
    guilds_info = {}
    for file in all_files:
        filename = os.path.basename(file).replace('.encrypted', '')
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
    """Gibt alle verfügbaren Daten für eine Guild zurück (Repository - plain + encrypted)."""
    pattern_plain = f"hu_data/*{guild_name}Full.csv"
    pattern_encrypted = f"hu_data/*{guild_name}Full.csv.encrypted"
    
    files_plain = glob.glob(pattern_plain)
    files_encrypted = glob.glob(pattern_encrypted)
    
    # Entferne .encrypted aus Plain-Liste (falls beide existieren)
    files_plain = [f for f in files_plain if f"{f}.encrypted" not in files_encrypted]
    
    all_files = files_plain + files_encrypted
    
    dates_info = []
    for file in all_files:
        filename = os.path.basename(file).replace('.encrypted', '')
        match = re.match(r'(\d{4}-\d{2}-\d{2})\s+.+?Full\.csv', filename)
        if match:
            date_str = match.group(1)
            dates_info.append({'Date': date_str, 'Source': 'Repository'})
    
    # Sortiere nach Datum (neueste zuerst)
    dates_df = pd.DataFrame(dates_info)
    if not dates_df.empty:
        dates_df = dates_df.sort_values('Date', ascending=False)
    return dates_df

def get_dates_with_upload(guild_name, upload_date=None, upload_guild=None):
    """Gibt Repo-Daten + Upload zurück (falls vorhanden UND Gilde stimmt überein)."""
    dates_df = get_dates_for_guild(guild_name)
    
    # Füge Upload hinzu (nur wenn vorhanden UND Gilde stimmt überein!)
    if upload_date and upload_guild == guild_name:
        upload_row = pd.DataFrame([{'Date': upload_date, 'Source': '📤 Upload'}])
        dates_df = pd.concat([upload_row, dates_df], ignore_index=True)
    
    return dates_df

@st.cache_data
def load_guild_data(guild_filter, selected_dates):
    """Lädt nur ausgewählte CSVs der Gilde (mit Caching). Unterstützt verschlüsselte .encrypted Dateien."""
    
    # Initialisiere Cipher falls Encryption verfügbar
    cipher = None
    if ENCRYPTION_AVAILABLE:
        try:
            key = st.secrets.get("encryption", {}).get("key")
            if key:
                cipher = Fernet(key.encode())
        except Exception:
            pass  # Kein Key vorhanden = nur unverschlüsselte CSVs laden
    
    # Suche nach CSVs (verschlüsselt UND unverschlüsselt)
    pattern_plain = f"hu_data/*{guild_filter}Full.csv"
    pattern_encrypted = f"hu_data/*{guild_filter}Full.csv.encrypted"
    
    files_plain = glob.glob(pattern_plain)
    files_encrypted = glob.glob(pattern_encrypted)
    
    # Entferne .encrypted aus Plain-Liste (falls beide existieren, bevorzuge encrypted)
    files_plain = [f for f in files_plain if f"{f}.encrypted" not in files_encrypted]
    
    all_files = files_plain + files_encrypted
    
    if not all_files:
        st.error(f"❌ No CSV files found for {guild_filter}!")
        return None
    
    all_dataframes = []
    # Convert selected_dates to set for faster lookup
    selected_dates_set = set(selected_dates) if selected_dates else set()

    for file in all_files:
        try:
            # Extrahiere Datum aus Dateinamen (ohne .encrypted)
            filename = os.path.basename(file).replace('.encrypted', '')
            match = re.match(r'(\d{4}-\d{2}-\d{2})\s+.+?Full\.csv', filename)
            
            if match:
                date_str = match.group(1)
                
                # Nur laden wenn in selected_dates (oder wenn keine Auswahl = alle laden)
                if not selected_dates_set or date_str in selected_dates_set:
                    # Lade CSV (verschlüsselt oder plain)
                    if file.endswith('.encrypted'):
                        if not cipher:
                            st.warning(f"⚠️ Skipped encrypted file (no key): {filename}")
                            continue
                        
                        # Entschlüssele
                        with open(file, 'rb') as f:
                            encrypted_data = f.read()
                        decrypted_data = cipher.decrypt(encrypted_data)
                        df = pd.read_csv(StringIO(decrypted_data.decode('utf-8')))
                    else:
                        # Plain CSV
                        df = pd.read_csv(file)
                    
                    # Füge Spalten hinzu
                    df['date'] = date_str
                    # df['guild'] = guild_filter  ### Nicht nötig, da alle Daten der gleichen Gilde sind
                    
                    all_dataframes.append(df)

        except Exception as e:
            st.warning(f"⚠️ Error loading {file}: {e}")
            continue
    
    if not all_dataframes:
        st.error("❌ No valid CSV files loaded!")
        return None
    
    # Kombiniere alle DataFrames
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    
    # Droppe UnitId-Spalte (wird nicht verwendet, spart Memory)
    if 'UnitId' in combined_df.columns:
        combined_df = combined_df.drop(columns=['UnitId'])
    
    return combined_df

@st.cache_data
def get_newest_df(guild_filter, selected_dates, upload_csv_data=None, upload_date=None, upload_guild=None):
    """
    Lädt NEUESTEN Datenstand mit ALLEN Spalten (für Overview, Char Stats, Mod Distribution).
    Kombiniert gecachte Repository-Daten + optionalen Upload (MIT CACHING!).
    
    Args:
        guild_filter: Name der Gilde
        selected_dates: Tuple der ausgewählten Daten aus Repository
        upload_csv_data: Optional - Upload-CSV als String (für Cache-Key)
        upload_date: Optional - Datum des Uploads
        upload_guild: Optional - Gilde des Uploads (für Validierung)
    
    Returns:
        DataFrame mit neuestem Datenstand (alle Spalten inkl. Stats, Mods)
    """
    # Lade gecachte CSVs aus Repository
    df_cached = load_guild_data(guild_filter, tuple(selected_dates))
    
    if df_cached is None:
        return None
    
    # Füge Upload hinzu (falls übergeben UND Gilde stimmt überein!)
    if upload_csv_data is not None and upload_guild == guild_filter:
        # Parse Upload-CSV
        df_upload = pd.read_csv(StringIO(upload_csv_data))
        
        # Droppe UnitId-Spalte (wird nicht verwendet, spart Memory)
        if 'UnitId' in df_upload.columns:
            df_upload = df_upload.drop(columns=['UnitId'])
        
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
        df_upload['date'] = upload_date if upload_date else datetime.now().strftime('%Y-%m-%d')
        
        df_combined = pd.concat([df_upload, df_cached], ignore_index=True)
    else:
        df_combined = df_cached
    
    # Extrahiere NEUESTEN Datenstand
    newest_date = sorted(df_combined['date'].unique(), reverse=True)[0]
    df_newest = df_combined[df_combined['date'] == newest_date].copy()
    
    return df_newest

@st.cache_data
def get_all_dates_df(guild_filter, selected_dates, upload_csv_data=None, upload_date=None, upload_guild=None):
    """
    Lädt ALLE Datenstände mit REDUZIERTEN Spalten (für Progress Tab).
    Entfernt Stats/Mods (außer Speed) um Memory zu sparen.
    
    Args:
        guild_filter: Name der Gilde
        selected_dates: Tuple der ausgewählten Daten aus Repository
        upload_csv_data: Optional - Upload-CSV als String (für Cache-Key)
        upload_date: Optional - Datum des Uploads
        upload_guild: Optional - Gilde des Uploads (für Validierung)
    
    Returns:
        DataFrame mit allen Datenständen (reduzierte Spalten ohne Stats/Mods außer Speed)
    """
    # Lade gecachte CSVs aus Repository
    df_cached = load_guild_data(guild_filter, tuple(selected_dates))
    
    if df_cached is None:
        return None
    
    # Füge Upload hinzu (falls übergeben UND Gilde stimmt überein!)
    if upload_csv_data is not None and upload_guild == guild_filter:
        # Parse Upload-CSV
        df_upload = pd.read_csv(StringIO(upload_csv_data))
        
        # Droppe UnitId-Spalte (wird nicht verwendet, spart Memory)
        if 'UnitId' in df_upload.columns:
            df_upload = df_upload.drop(columns=['UnitId'])
        
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
        df_upload['date'] = upload_date if upload_date else datetime.now().strftime('%Y-%m-%d')
        
        df_combined = pd.concat([df_upload, df_cached], ignore_index=True)
    else:
        df_combined = df_cached
    
    # Definiere benötigte Spalten für Progress Tab (und zukünftige Progress-KPIs!)
    progress_columns = [
        # Identifier
        'AllyCode', 'Name', 'BaseId', 'date', 'CombatType', 'Alignment',
        # Basic Stats
        'Stars', 'Level', 'GearLevel', 'Power',
        # Zetas & Omicrons
        'ZetaCount', 'ZetaLead', 'OmiCount', 'TWOmiCount', 'GACOmiCount', 'TBOmiCount', 'CQOmiCount',
        # Ultimate & Relic
        'Ultimate', 'RelicLevel',
        # Speed Mods
        'Speed10', 'Speed15', 'Speed20', 'Speed25',
        # Mod Counts
        'ModCount', 'ModSixCount', 'PlusSpeed',
        # Speed Stat (AUSNAHME - einziger Stat-Wert!)
        'Speed'
    ]
    
    # Filtere nur existierende Spalten (falls CSV-Format unterschiedlich)
    available_columns = [col for col in progress_columns if col in df_combined.columns]
    df_all_dates = df_combined[available_columns].copy()
    
    return df_all_dates

def show_start_screen():
    """Zeigt Startbildschirm mit Guild-Auswahl, Date-Auswahl und CSV-Upload."""
    
    # Header mit Logo und Titel nebeneinander
    col1, col2, col3 = st.columns([2, 4, 1])
    with col1:
        st.image("assets/BA_Logo_rot.png", width=200)
    with col2:
        st.title("SWGOH")
        st.header("Guild Progress")
    with col3:
        query_params = st.query_params
        default_ally_code_url = query_params.get("ally_code", "")

        ally_code_input = st.text_input(
            "Your AllyCode:", 
            value=default_ally_code_url,
            key="ally_code_input",
            placeholder="817-994-826",
            help="9-digit AllyCode (with or without dashes)"
        )

        # Extract 9 digits from input (remove dashes and other characters)
        ally_code_clean = re.sub(r'\D', '', ally_code_input)
        
        # Validate: must be exactly 9 digits
        if ally_code_clean and len(ally_code_clean) == 9:
            st.session_state.default_ally_code = ally_code_clean
            # Update URL wenn Wert sich ändert
            if ally_code_clean != default_ally_code_url:
                st.query_params["ally_code"] = ally_code_clean
        elif ally_code_clean and len(ally_code_clean) != 9:
            st.warning(f"⚠️ AllyCode must be 9 digits (found {len(ally_code_clean)})")
            # Use fallback if invalid
            if 'default_ally_code' not in st.session_state:
                st.session_state.default_ally_code = DEFAULT_ALLY_CODE
        else:
            # Empty input - use fallback
            if 'default_ally_code' not in st.session_state:
                st.session_state.default_ally_code = DEFAULT_ALLY_CODE
    
    st.markdown("---")
    
    # Zwei-Spalten-Layout für Guild und Dates
    col_guild, col_dates = st.columns([1, 1])
    
    # Left column: Guild selection
    with col_guild:
        st.subheader("📋 Step 1: Guild Selection")
        
        guilds_df = get_available_guilds()
        
        if guilds_df.empty:
            st.error("❌ No guilds found! Please place CSVs in hu_data/ folder.")
            st.info("📝 Filename format: `YYYY-MM-DD GuildNameFull.csv`")
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
            
            # Check if guild changed - reset mismatch flag if yes
            if 'selected_guild' in st.session_state and st.session_state.selected_guild != selected_guild:
                # Guild wurde gewechselt - reset upload_guild_mismatch flag
                if 'upload_guild_mismatch' in st.session_state:
                    # Re-check mismatch mit neuer Guild
                    upload_guild = st.session_state.get('uploaded_csv_guild', None)
                    if upload_guild and upload_guild == selected_guild:
                        st.session_state.upload_guild_mismatch = False
                    # Wenn immer noch Mismatch, bleibt der Flag True
            
            st.session_state.selected_guild = selected_guild
    
    # Right column: Dates selection (only if Guild selected)
    with col_dates:
        st.subheader(f"📅 Step 2: Date Selection")
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
                st.warning(f"⚠️ No data found for {st.session_state.selected_guild}!")
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
                        dates_df.iloc[idx]['Date'] 
                        for idx in selected_date_rows 
                        if dates_df.iloc[idx]['Source'] == 'Repository'
                    ]
                    st.session_state.selected_dates = selected_dates
                    
                    # Prüfe ob Upload ausgewählt wurde
                    has_upload_selected = any(
                        dates_df.iloc[idx]['Source'] == '📤 Upload' 
                        for idx in selected_date_rows
                    )
                    
                    # Info text
                    repo_count = len(selected_dates)
                    upload_text = " + Upload" if has_upload_selected else ""
                    st.info(f"✅ {repo_count} Repo-CSV(s){upload_text} selected")
        else:
            st.info("👈 Please select a guild first")
    
    # Schritt 3 & 4: CSV Upload und Start-Button (volle Breite)
    if 'selected_guild' in st.session_state:
        st.markdown("---")
        
        # Step 3: Optional CSV upload
        st.subheader("📤 Step 3: Upload new CSV (optional)")
        
        # Check if upload already exists
        has_existing_upload = 'uploaded_csv_df' in st.session_state
        
        if has_existing_upload:
            # Show success message after upload
            upload_date = st.session_state.get('uploaded_csv_date', 'Unknown')
            upload_guild = st.session_state.get('uploaded_csv_guild', 'Unknown')
            upload_rows = len(st.session_state.uploaded_csv_df)
            st.success(f"✅ {upload_rows} rows uploaded for {upload_guild}! (Date: {upload_date})")
            
            st.info("ℹ️ Only one upload per session allowed.")
            if st.button("🗑️ Delete current upload"):
                del st.session_state['uploaded_csv_df']
                del st.session_state['uploaded_csv_data']
                del st.session_state['uploaded_csv_date']
                del st.session_state['uploaded_csv_guild']
                if 'upload_validation_warnings' in st.session_state:
                    del st.session_state['upload_validation_warnings']
                if 'upload_guild_mismatch' in st.session_state:
                    del st.session_state['upload_guild_mismatch']
                
                # LÖSCHE gecachte DataFrames - müssen neu geladen werden ohne Upload!
                if 'df_newest_cached' in st.session_state:
                    del st.session_state['df_newest_cached']
                if 'df_all_dates_cached' in st.session_state:
                    del st.session_state['df_all_dates_cached']
                if 'player_base_global' in st.session_state:
                    del st.session_state['player_base_global']
                
                st.rerun()
        
        uploaded_file = st.file_uploader(
            "Upload new CSV file",
            type=['csv'],
            help="Optional: Upload a new CSV (Format: YYYY-MM-DD GuildNameFull.csv)",
            disabled=has_existing_upload
        )
        
        if uploaded_file is not None and 'uploaded_csv_df' not in st.session_state:
            try:
                df_upload = pd.read_csv(uploaded_file)
                
                # Validierung 1 & 2: Dateiname prüfen (falls vorhanden)
                filename = uploaded_file.name
                upload_date = datetime.now().strftime('%Y-%m-%d')  # Default: heute
                upload_guild_name = None  # Will be extracted from filename
                validation_warnings = []
                
                if filename:
                    # Versuche Datum und Gildenname zu extrahieren
                    match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(.+?)Full\.csv', filename)
                    if match:
                        extracted_date = match.group(1)
                        extracted_guild = match.group(2).strip()
                        
                        # Check 1: Does guild name match selected guild?
                        selected_guild = st.session_state.selected_guild
                        if extracted_guild != selected_guild:
                            validation_warnings.append(f"⚠️ Guild name mismatch: File contains '{extracted_guild}', but '{selected_guild}' is selected!")
                            st.session_state.upload_guild_mismatch = True  # Flag for Start button
                        else:
                            st.session_state.upload_guild_mismatch = False
                        
                        # Prüfung 2: Nutze Datum aus Dateinamen
                        upload_date = extracted_date
                        upload_guild_name = extracted_guild  # Use guild from filename
                    else:
                        # Kein Match im Dateinamen - Upload erlauben (könnte manuell umbenannt sein)
                        st.session_state.upload_guild_mismatch = False
                else:
                    # Kein Dateiname - Upload erlauben
                    st.session_state.upload_guild_mismatch = False
                
                # Fallback: wenn kein Guild-Name aus Dateinamen, nutze selected_guild
                if upload_guild_name is None:
                    upload_guild_name = st.session_state.selected_guild
                
                # Speichere Upload in Session State + CSV-String für Cache (EINMALIG!)
                st.session_state.uploaded_csv_df = df_upload
                st.session_state.uploaded_csv_data = df_upload.to_csv(index=False)  # Einmalige Konvertierung!
                st.session_state.uploaded_csv_date = upload_date
                st.session_state.uploaded_csv_guild = upload_guild_name  # Speichere Guild-Name aus Datei!
                st.session_state.upload_validation_warnings = validation_warnings
                
                # LÖSCHE gecachte DataFrames - müssen neu geladen werden mit Upload!
                if 'df_newest_cached' in st.session_state:
                    del st.session_state['df_newest_cached']
                if 'df_all_dates_cached' in st.session_state:
                    del st.session_state['df_all_dates_cached']
                if 'player_base_global' in st.session_state:
                    del st.session_state['player_base_global']  # Auch player_base neu initialisieren!
                
                # Zeige Warnings falls vorhanden
                for warning in validation_warnings:
                    st.warning(warning)
                
                # Rerun um Upload-Zeile in Tabelle anzuzeigen (Success-Meldung kommt nach Rerun!)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error loading CSV: {e}")
        
        st.markdown("---")
        
        # Step 4: Start button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
                # Check if upload guild doesn't match
                guild_mismatch = st.session_state.get('upload_guild_mismatch', False)
                button_disabled = guild_mismatch
                
                if button_disabled:
                    st.error("🚫 Start blocked: Guild name mismatch!")
                    st.info("💡 Only guilds from the repository may use this tool.")
                
                if st.button("▶️ Start Analysis", type="primary", width='stretch', disabled=button_disabled):
                    if 'selected_dates' in st.session_state and st.session_state.selected_dates:
                        # Bereite Upload-Daten vor (falls vorhanden)
                        upload_csv_data = None
                        upload_date = None
                        upload_guild = None
                        if 'uploaded_csv_df' in st.session_state:
                            upload_csv_data = st.session_state.get('uploaded_csv_data', None)
                            upload_date = st.session_state.get('uploaded_csv_date', datetime.now().strftime('%Y-%m-%d'))
                            upload_guild = st.session_state.get('uploaded_csv_guild', None)
                        
                        # Lade BEIDE DataFrames EINMALIG beim Start
                        df_newest_temp = get_newest_df(st.session_state.selected_guild, tuple(st.session_state.selected_dates), upload_csv_data, upload_date, upload_guild)
                        df_all_dates_temp = get_all_dates_df(st.session_state.selected_guild, tuple(st.session_state.selected_dates), upload_csv_data, upload_date, upload_guild)
                        
                        if df_newest_temp is not None and not df_newest_temp.empty and df_all_dates_temp is not None:
                            # Ermittle available dates aus df_all_dates
                            available_dates_list = sorted(df_all_dates_temp['date'].unique(), reverse=True)
                            newest_date = available_dates_list[0]
                            
                            # Player Name lookup aus df_newest
                            default_ally_code = st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE)
                            player_name_match = df_newest_temp[df_newest_temp['AllyCode'].astype(str) == default_ally_code]['Name'].unique()
                            player_name = player_name_match[0] if len(player_name_match) > 0 else default_ally_code
                            
                            # Speichere BEIDE DataFrames in Session State (für main())
                            st.session_state.df_newest_cached = df_newest_temp
                            st.session_state.df_all_dates_cached = df_all_dates_temp
                            st.session_state.available_dates_cached = available_dates_list
                            st.session_state.player_name_cached = player_name
                            st.session_state.newest_date_cached = newest_date
                            
                            # Starte Analysis
                            st.session_state.analysis_started = True
                            st.rerun()
                        else:
                            st.error("❌ Error loading data for analysis!")
                    else:
                        st.warning("⚠️ Please select at least one date from the repository!")

def apply_filters(characters_data, alignment_filter, categories_filter, role_filter, ability_classes_filter, key_relevance_filter=None, relevance_dict=None, categories_use_and=False, ability_classes_use_and=False):
    """Wendet Filter auf die Charakterdaten an."""
    filtered = characters_data.copy()
    
    # Key Relevance Filter (zuerst anwenden)
    if key_relevance_filter and relevance_dict:
        # Wenn nur eine Option ausgewählt ist
        if len(key_relevance_filter) == 1:
            if '👍' in key_relevance_filter:
                # Nur Key Characters
                filtered = [char for char in filtered if relevance_dict.get(char.get('base_id'), 'no') == 'yes']
            elif '👎' in key_relevance_filter:
                # Nur 👎 (keine Key Characters)
                filtered = [char for char in filtered if relevance_dict.get(char.get('base_id'), 'no') == 'no']
        # Wenn beide oder keine ausgewählt sind, zeige alle (kein Filter)
    
    if alignment_filter:  # Wenn Liste nicht leer
        filtered = [char for char in filtered if char.get('alignment') in alignment_filter]
    
    if categories_filter:  # Wenn Liste nicht leer
        if categories_use_and:
            # UND-Verknüpfung: Char muss ALLE haben
            filtered = [char for char in filtered if all(cat in char.get('categories', []) for cat in categories_filter)]
        else:
            # ODER-Verknüpfung: Char muss mindestens EINEN haben
            filtered = [char for char in filtered if any(cat in char.get('categories', []) for cat in categories_filter)]
    
    if role_filter:  # Wenn Liste nicht leer
        filtered = [char for char in filtered if char.get('role') in role_filter]
    
    if ability_classes_filter:  # Wenn Liste nicht leer
        if ability_classes_use_and:
            # UND-Verknüpfung: Char muss ALLE haben
            filtered = [char for char in filtered if all(ac in char.get('ability_classes', []) for ac in ability_classes_filter)]
        else:
            # ODER-Verknüpfung: Char muss mindestens EINEN haben
            filtered = [char for char in filtered if any(ac in char.get('ability_classes', []) for ac in ability_classes_filter)]
    
    return filtered

def show_character_overview(df_newest, filtered_characters, characters_data, filters_active, key_relevance_filter=None, relevance_dict=None, relic_rec_dict=None, notes_dict=None, relic_costs=None):
    # === OVERVIEW zeigt Characters UND/ODER Ships basierend auf Combat Type Filter! ===
    # filtered_base_ids aus Session State enthält nur Characters (für Mod Distribution)
    # Overview braucht separate Logik für Ships und muss Combat Type Filter beachten!
    
    # Hole Combat Type Filter aus Session State
    combat_type_filter = st.session_state.get('combat_type_filter', ['Character'])
    
    # Bestimme welche Combat Types angezeigt werden sollen
    show_characters = 'Character' in combat_type_filter or not combat_type_filter
    show_ships = 'Ship' in combat_type_filter or not combat_type_filter
    
    filtered_base_ids_chars = st.session_state.get('filtered_base_ids', []) if show_characters else []
    
    # Für Ships: Nutze relevance_dict und key_relevance_filter
    filtered_base_ids_ships = []
    if show_ships:
        relevance_dict = relevance_dict or {}
        available_ships = set(df_newest[df_newest['CombatType'] == 'Ship']['BaseId'].unique())
        
        # Filtere Ships basierend auf Key Relevance Filter
        if key_relevance_filter:
            if '👍' in key_relevance_filter and '👎' not in key_relevance_filter:
                # Nur Key Ships
                filtered_base_ids_ships = [base_id for base_id, value in relevance_dict.items() 
                                          if value == 'yes' and base_id in available_ships]
            elif '👎' in key_relevance_filter and '👍' not in key_relevance_filter:
                # Nur Non-Key Ships
                filtered_base_ids_ships = [base_id for base_id, value in relevance_dict.items() 
                                          if value == 'no' and base_id in available_ships]
            else:
                # Beide oder keine = Alle Ships
                filtered_base_ids_ships = list(available_ships)
        else:
            filtered_base_ids_ships = list(available_ships)
    
    # Kombiniere Characters und Ships basierend auf Combat Type Filter
    all_filtered_base_ids = filtered_base_ids_chars + filtered_base_ids_ships
    
    # Filtere DataFrame
    if all_filtered_base_ids:
        df_filtered = df_newest[df_newest['BaseId'].isin(all_filtered_base_ids)]
    else:
        df_filtered = df_newest[df_newest['BaseId'].isin([])]
    
    if df_filtered.empty:
        st.warning("❌ No data found for the selected filters.")
        return
    
    # Zähle Characters und Ships separat
    char_count = len(filtered_base_ids_chars)
    ship_count = len(filtered_base_ids_ships)
    
    # Erstelle Titel mit Anzahl
    title_parts = []
    if char_count > 0:
        title_parts.append(f"{char_count} char{'s' if char_count != 1 else ''}")
    if ship_count > 0:
        title_parts.append(f"{ship_count} ship{'s' if ship_count != 1 else ''}")
    
    if title_parts:
        count_text = " & ".join(title_parts)
        title = f'<h3 id="character-overview" style="margin-top: -12px; margin-bottom: 0;">{TAB_OVERVIEW} ({count_text})</h3>'
    else:
        title = f'<h3 id="character-overview" style="margin-top: -12px; margin-bottom: 0;">{TAB_OVERVIEW} (0 chars)</h3>'
    
    st.markdown(title, unsafe_allow_html=True)
    
    # Erstelle ein Mapping von BaseId zu Name für die Anzeige
    base_id_to_name = {char['base_id']: char['name'] for char in characters_data}
    
    # Get default_ally_code from session state for Player relic level
    default_ally_code = st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE)
    
    # Filter df_filtered für den ausgewählten Spieler (Characters UND Ships!)
    df_player = df_filtered[df_filtered['AllyCode'].astype(str) == default_ally_code]
    
    # Erstelle Mapping: BaseId -> RelicLevel für den ausgewählten Spieler
    player_relic_dict = dict(zip(df_player['BaseId'], df_player['RelicLevel']))
    
    # Gruppierung nach BaseId (Charaktername) und Berechnung der Kennzahlen
    char_stats = df_filtered.groupby('BaseId').agg({
        'RelicLevel': [
            lambda x: sum(x == 10),   # R10
            lambda x: sum(x == 9),    # R9
            lambda x: sum(x == 8),    # R8  
            lambda x: sum(x == 7),    # R7
            lambda x: sum(x < 7),     # <R7
            'count'                   # Total count
        ]
    }).round(0)  # Keine Nachkommastellen
    
    # Spalten strukturieren - alle als Integer
    # Einmal base_ids auslesen statt mehrfach iterieren
    base_ids = char_stats.index.tolist()
    
    char_overview = pd.DataFrame({
        'Character': [base_id_to_name.get(base_id, base_id) for base_id in base_ids],
        'Player relic': [player_relic_dict.get(base_id, None) for base_id in base_ids],
        'Recommended': [relic_rec_dict.get(base_id, None) if relic_rec_dict else None for base_id in base_ids],
        'Δ': [
            (rec - player if rec and player and rec > player else 0)
            for rec, player in zip(
                [relic_rec_dict.get(base_id, None) if relic_rec_dict else None for base_id in base_ids],
                [player_relic_dict.get(base_id, None) for base_id in base_ids]
            )
        ],
        'Comment': [notes_dict.get(base_id, None) if notes_dict else None for base_id in base_ids],
        'Guild': char_stats['RelicLevel']['count'].astype(int),
        'R10': char_stats['RelicLevel']['<lambda_0>'].astype(int),
        'R9': char_stats['RelicLevel']['<lambda_1>'].astype(int), 
        'R8': char_stats['RelicLevel']['<lambda_2>'].astype(int),
        'R7': char_stats['RelicLevel']['<lambda_3>'].astype(int),
        '<R7': char_stats['RelicLevel']['<lambda_4>'].astype(int)
    })
    
    # Berechne Relic-Kosten (vor reset_index, da BaseId noch im Index ist!)
    if relic_costs:
        total_costs = calculate_total_relic_costs(char_overview, player_relic_dict, relic_rec_dict, relic_costs)
    else:
        total_costs = None
    
    # Index zurücksetzen um BaseId zu entfernen
    char_overview = char_overview.reset_index(drop=True)
    
    # Zwei-Spalten-Layout: Character Overview (links) + Relic Costs (rechts)
    with st.container(horizontal=True, gap="medium"):
        # Tabelle anzeigen mit kleiner Zeilenhöhe für mehr sichtbare Zeilen
        # row_height=21 ermöglicht ca. 50 Zeilen bei 1140px Container-Höhe
        st.dataframe(char_overview, hide_index=True, width="content", height=1100, row_height=21)
        
        # Relic Costs in vertikalem Container (Überschriften + Tabellen übereinander)
        with st.container():
            if total_costs:
                # Material-Namen für Anzeige (lesbar)
                material_display_names = {
                    'fragmented_signal_data': 'Fragmented Signal Data',
                    'incomplete_signal_data': 'Incomplete Signal Data',
                    'flawed_signal_data': 'Flawed Signal Data',
                    'corrupted_signal_data': 'Corrupted Signal Data',
                    'carbonite_circuit_board': 'Carbonite Circuit Board',
                    'bronzium_wiring': 'Bronzium Wiring',
                    'chromium_transistor': 'Chromium Transistor',
                    'aurodium_heatsink': 'Aurodium Heatsink',
                    'electrium_conductor': 'Electrium Conductor',
                    'zinbiddle_card': 'Zinbiddle Card',
                    'impulse_detector': 'Impulse Detector',
                    'aeromagnifier': 'Aeromagnifier',
                    'gyrda_keypad': 'Gyrda Keypad',
                    'droid_brain': 'Droid Brain',
                    'coaxial_servomotors': 'Coaxial Servomotors'
                }
                
                # Kategorisierung: Signal Data vs Scrap Materials
                signal_data_keys = [
                    'fragmented_signal_data', 'incomplete_signal_data', 
                    'flawed_signal_data', 'corrupted_signal_data'
                ]
                scrap_material_keys = [
                    'carbonite_circuit_board', 'bronzium_wiring', 'chromium_transistor',
                    'aurodium_heatsink', 'electrium_conductor', 'zinbiddle_card',
                    'impulse_detector', 'aeromagnifier', 'gyrda_keypad',
                    'droid_brain', 'coaxial_servomotors'
                ]
                
                # Erstelle separate Listen (nur Materialien mit Wert > 0)
                signal_data = []
                scrap_materials = []
                
                for material_key, total in total_costs.items():
                    if total > 0:
                        data = {
                            'Material': material_display_names[material_key],
                            'Total': total
                        }
                        if material_key in signal_data_keys:
                            signal_data.append(data)
                        elif material_key in scrap_material_keys:
                            scrap_materials.append(data)
                
                if signal_data or scrap_materials:
                    # Signal Data Tabelle
                    if signal_data:
                        signal_df = pd.DataFrame(signal_data)
                        st.markdown('<h4 style="margin-top: 0; margin-bottom: 10px;">📡 Signal Data</h4>', unsafe_allow_html=True)
                        st.dataframe(
                            signal_df,
                            hide_index=True,
                            width="content",
                            height=150,
                            row_height=24
                        )
                    
                    # Scrap Materials Tabelle
                    if scrap_materials:
                        scrap_df = pd.DataFrame(scrap_materials)
                        st.markdown('<h4 style="margin-top: 20px; margin-bottom: 10px;">⚙️ Scrap Materials</h4>', unsafe_allow_html=True)
                        st.dataframe(
                            scrap_df,
                            hide_index=True,
                            width="content",
                            height=320,
                            row_height=24
                        )
                else:
                    st.info("✅ No upgrades needed!")
            else:
                st.warning("⚠️ Relic cost data not available")

def show_analytics_tab(df_newest, filtered_characters, characters_data, filters_active):
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
        st.warning("❌ No characters available.")
        return
    
    # Character for Tab 2 from Session State
    selected_character_name = st.session_state.selected_character_tab2
    selected_base_id = next((base_id for name, base_id in available_characters if name == selected_character_name), None)
    
    if not selected_base_id:
        st.warning("❌ No valid character selected.")
        return
    
    # Filter data for the selected character
    df_character = df_newest[df_newest['BaseId'] == selected_base_id].copy()
    
    if df_character.empty:
        st.warning(f"❌ No data found for {selected_character_name}.")
        return
    
    st.markdown(f'<h3 style="margin-top: -12px; margin-bottom: 0;">📊 Character Stats for {selected_character_name}</h3>', unsafe_allow_html=True)
    
    # Hole Character-Image aus characters_data
    character_image_url = None
    for char in characters_data:
        if char.get('base_id') == selected_base_id:
            character_image_url = char.get('image', '')
            break
    
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
    
    # Diagramme in einem Container mit fester Breite (Player: 200px -6px Ausrichtung + 10 Spalten mit 150px + 10px gap)
    with st.container(width=1794, gap="small"):
        # Charts mit perfekter Ausrichtung zur nachfolgende Tabelle anzeigen
        chart_cols = st.columns([194] + [150] * 10, gap="small")

        # Erstelle Lookup-Dictionaries EINMAL für ALLE Charts (statt 10x pro Chart!)
        player_checked = dict(zip(player_base['Name'], player_base['Checked']))
        player_colors = dict(zip(player_base['Name'], player_base['PlayerColor']))
        
        # Precompute RGBA colors für alle checked players (statt 50x pro Chart!)
        player_colors_rgba = {
            name: hex_to_rgba(color, 0.6) 
            for name, color in player_colors.items() 
            if player_checked.get(name, False)
        }
                
        with chart_cols[0]:
            # Character-Bild horizontal zentriert anzeigen (150px Höhe wie Charts)
            if character_image_url:
                st.markdown(
                    f'<div style="display: flex; justify-content: center; align-items: center; height: 150px; background: #1A1C24; border-radius: 8px;">'
                    f'<img src="{character_image_url}" style="height: 150px; width: auto; border-radius: 8px;">'
                    f'</div>',
                    unsafe_allow_html=True
                )
        
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
            colors = stat_data['Name'].map(lambda name: player_colors_rgba.get(name, "#1A1C24")).tolist()
            
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
                    'fixedrange': True,
                    'range': [-0.5, len(stat_data) + 0.5]  # Symmetrische Range mit Padding
                },
                yaxis={
                    'showticklabels': False,  # Keine y-Achsen Werte
                    'title': "",  # Kein y-Achsen Titel
                    'showgrid': False,
                    'zeroline': False,
                    'fixedrange': True,
                    'automargin': False  # Verhindert automatische Margins für y-Achse
                },
                width=150,  # Chart-Breite: 152px
                height=180,  # Kompakte Höhe (+30, da plotly unten Platz reserviert)
                margin={'l': 2, 'r': 4, 't': 24, 'b': 0},  # Minimale Margins
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
                    # Rahmen um den Plot-Bereich
                    dict(
                        type='rect',
                        xref='x',
                        yref='paper',
                        x0=-2,
                        y0=0,
                        x1=len(stat_data) + 1,
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
    
    # Reduziere Abstand zur Tabelle
    st.markdown("""
        <style>
        [data-testid="stDataFrame"] {
            margin-top: -40px !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Spalten für die Anzeige auswählen (ohne BaseId) - CritChance vor CritDamage
    display_columns = ['Name', 'Speed', 'Health', 'Protection', 'Armor', 'Damage', 'CritChance', 'CritDamage', 'Potency', 'Tenacity', 'RelicLevel']
    
    # DataFrame für Anzeige vorbereiten (gleiche Sortierung wie Diagramm)
    display_df = df_character[display_columns].copy()
    display_df = display_df.sort_values('Speed', ascending=False)  # Nach Speed sortieren
    
    # OPTIMIERT: Index-basiertes Mapping statt teurer merge (500ms → ~5ms)
    # Erstelle Dicts für schnelle Lookups (O(1) statt O(n) merge)
    player_base_indexed = player_base.set_index('Name')
    name_to_checked = player_base_indexed['Checked'].to_dict()
    name_to_color = player_base_indexed['PlayerColor'].to_dict()
    
    # Füge Checked/Color via map hinzu (viel schneller als merge)
    display_df['Checked'] = display_df['Name'].map(name_to_checked).fillna(False)
    display_df['PlayerColor'] = display_df['Name'].map(name_to_color).fillna('#CCCCCC')
    
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
            elif col in ['Health', 'Protection']:
                # Health und Protection mit Tausender-Trenner (localized)
                column_config[col] = st.column_config.NumberColumn(width=160, format="localized")
            else:
                # Normale Zahlen (Speed, etc.)
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
                
                print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Callback: Player toggled in Char Stats", file=sys.stderr)
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width=1810,
        column_config=column_config,
        height=920,
        row_height=20,
        selection_mode="single-cell",
        on_select=on_player_select,
        key="player_comparison_table_selection"
    )

@st.cache_data
def get_all_player_metrics_per_date(df_all_dates, player_base, key_relevance_filter=None, relevance_dict=None):
    """
    Berechnet ALLE Metriken (Relics, Omicrons, Speed Mods) in einem DataFrame (mit Caching).
    Wird nur einmal pro Guild berechnet, dann für alle User geteilt.
    
    Args:
        df_all_dates: Gefilterte Daten für diese Gilde (alle Datenstände, reduzierte Spalten)
        player_base: DataFrame mit [AllyCode, Name] - einheitliche Spielerliste
        key_relevance_filter: Liste ['👍', '👎'] für Key/Non-Key Character Filter
        relevance_dict: Dict mit {base_id: {'is_key': True/False}}
    
    Returns:
        DataFrame mit Spalten:
        - AllyCode, Name
        - {date}_R6, {date}_R7, {date}_R8, {date}_R9, {date}_R10
        - {date}_TWOmiCount, {date}_GACOmiCount, {date}_TBOmiCount, {date}_CQOmiCount
        - {date}_Speed10, {date}_Speed15, {date}_Speed20, {date}_Speed25
        - {date}_Mod6
    """
    available_dates = sorted(df_all_dates['date'].unique(), reverse=True)
    
    # Start mit player_base (AllyCode, Name)
    result = player_base.copy()
    
    # Für jedes Datum: Füge alle Metrik-Spalten hinzu
    for date in available_dates:
        df_date = df_all_dates[df_all_dates['date'] == date]
        
        # Nur Characters (keine Ships)
        df_chars = df_date[df_date['CombatType'] == 'Character']
        
        # Wende Key Relevance Filter an (wenn aktiv) - nur einmal pro Datum!
        if key_relevance_filter and relevance_dict:
            if '👍' in key_relevance_filter and '👎' not in key_relevance_filter:
                # Nur Key Characters (key_character == 'yes')
                key_base_ids = [base_id for base_id, value in relevance_dict.items() if value == 'yes']
                df_chars = df_chars[df_chars['BaseId'].isin(key_base_ids)]
            elif '👎' in key_relevance_filter and '👍' not in key_relevance_filter:
                # Nur Non-Key Characters (key_character == 'no')
                non_key_base_ids = [base_id for base_id, value in relevance_dict.items() if value == 'no']
                df_chars = df_chars[df_chars['BaseId'].isin(non_key_base_ids)]
            # Wenn beide oder keines: alle Characters
        
        # RELICS: Zähle jedes Relic-Level separat
        for relic_level in [6, 7, 8, 9, 10]:
            col_name = f'{date}_R{relic_level}'
            relic_counts = df_chars[df_chars['RelicLevel'] == relic_level].groupby('AllyCode').size()
            result[col_name] = result['AllyCode'].map(relic_counts)
        
        # OMICRONS: Summiere jeden Omicron-Typ
        for omicron_col in ['TWOmiCount', 'GACOmiCount', 'TBOmiCount', 'CQOmiCount']:
            col_name = f'{date}_{omicron_col}'
            omicron_sums = df_chars.groupby('AllyCode')[omicron_col].sum()
            result[col_name] = result['AllyCode'].map(omicron_sums)
        
        # SPEED MODS: Summiere jeden Speed-Threshold
        for speed_col in ['Speed10', 'Speed15', 'Speed20', 'Speed25']:
            col_name = f'{date}_{speed_col}'
            speed_sums = df_chars.groupby('AllyCode')[speed_col].sum()
            result[col_name] = result['AllyCode'].map(speed_sums)
        
        # MOD6: Summiere ModSixCount (6-Dot Mods)
        col_name = f'{date}_Mod6'
        mod6_sums = df_chars.groupby('AllyCode')['ModSixCount'].sum()
        result[col_name] = result['AllyCode'].map(mod6_sums)
    
    return result

def show_progress_tab(df_all_dates, compare_date, key_relevance_filter, relevance_dict):
    """Progress Tab - konsolidierte Ansicht für Relics, Omicrons und Speed Mods."""
    
    # Callback für Radio Button
    def on_metric_type_change():
        """Callback um Session State sofort zu aktualisieren."""
        st.session_state.progress_metric_type = st.session_state.progress_metric_radio
    
    # Hole player_base DIREKT aus Session State
    player_base = st.session_state.player_base_global
    
    # Initialize session state für Metric-Auswahl
    if 'progress_metric_type' not in st.session_state:
        st.session_state.progress_metric_type = 'Relics'
    
    # Initialize session state für Segmented Controls (falls nicht vorhanden)
    if 'player_relics_selection' not in st.session_state:
        st.session_state.player_relics_selection = ['R10', 'R9', 'R8']
    if 'player_omicrons_selection' not in st.session_state:
        st.session_state.player_omicrons_selection = ['TW', 'GAC']
    if 'player_speed_selection' not in st.session_state:
        st.session_state.player_speed_selection = ['20+', '25+']  
    if 'player_mod6_selection' not in st.session_state:
        st.session_state.player_mod6_selection = ['Mod6']
    
    # Header mit Titel, Date-Dropdown, Segmented Control und Radio
    with st.container(width=1200, horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", gap="small"):
        # Titel mit dynamischem Suffix basierend auf Key Relevance Filter
        with st.container(width=240):
            # Bestimme Titel-Suffix
            if key_relevance_filter:
                if '👍' in key_relevance_filter and '👎' not in key_relevance_filter:
                    title_suffix = " (key)"
                elif '👎' in key_relevance_filter and '👍' not in key_relevance_filter:
                    title_suffix = " (rest)"
                else:
                    title_suffix = " (all)"
            else:
                title_suffix = " (all)"
            
            st.markdown(f'<h3 style="margin-top: -12px; margin-bottom: 0;">{TAB_PROGRESS}{title_suffix}</h3>', unsafe_allow_html=True)
        
        # Compare Date Dropdown
        available_dates = sorted(df_all_dates['date'].unique(), reverse=True)
        if 'compare_date_select' not in st.session_state and len(available_dates) >= 2:
            st.session_state.compare_date_select = available_dates[1]
        
        current_value = st.session_state.get('compare_date_select', available_dates[1] if len(available_dates) >= 2 else available_dates[0])
        if current_value not in available_dates:
            current_value = available_dates[1] if len(available_dates) >= 2 else available_dates[0]
        
        compare_date = st.selectbox(
            "Compare to:",
            options=available_dates,
            index=available_dates.index(current_value),
            key="compare_date_progress",
            label_visibility="collapsed",
            width =150,
            help="Select the date to compare your current metrics against.",
            on_change=lambda: setattr(st.session_state, 'compare_date_select', st.session_state.compare_date_progress)
        )
        
        # Segmented Control abhängig vom Metric-Typ (nur anzeigen wenn Typ gesetzt)
        if st.session_state.progress_metric_type == 'Relics':
            selected = st.segmented_control(
                "Relic Levels:",
                options=['R10', 'R9', 'R8', 'R7', 'R6'],
                default=st.session_state.player_relics_selection,
                key="progress_relics_segmented",
                selection_mode="multi",
                width=250,
                label_visibility="collapsed"
            )
            if selected != st.session_state.player_relics_selection:
                st.session_state.player_relics_selection = selected
            
        elif st.session_state.progress_metric_type == 'Omis':
            selected = st.segmented_control(
                "Omicron Types:",
                options=['TW', 'GAC', 'TB', 'CQ'],
                default=st.session_state.player_omicrons_selection,
                key="progress_omicrons_segmented",
                selection_mode="multi",
                width=250,
                label_visibility="collapsed"
            )
            if selected != st.session_state.player_omicrons_selection:
                st.session_state.player_omicrons_selection = selected
                
        elif st.session_state.progress_metric_type == 'Speed':
            selected = st.segmented_control(
                "Speed Thresholds:",
                options=['25+', '20+', '15+', '10+'],
                default=st.session_state.player_speed_selection,
                key="progress_speed_segmented",
                selection_mode="multi",
                width=250,
                label_visibility="collapsed"
            )
            if selected != st.session_state.player_speed_selection:
                st.session_state.player_speed_selection = selected
        
        else:  # Mod6
            selected = st.segmented_control(
                "Mod6:",
                options=['Mod6'],
                default=st.session_state.player_mod6_selection,
                key="progress_mod6_segmented",
                selection_mode="multi",
                width=250,
                label_visibility="collapsed"
            )
            if selected != st.session_state.player_mod6_selection:
                st.session_state.player_mod6_selection = selected
        
        # Radio-Button für Metric-Typ
        metric_type = st.radio(
            "Metric:",
            options=['Relics', 'Omis', 'Speed', 'Mod6'],
            index=['Relics', 'Omis', 'Speed', 'Mod6'].index(st.session_state.progress_metric_type),
            horizontal=True,
            key="progress_metric_radio",
            label_visibility="collapsed",
            on_change=on_metric_type_change  # Callback für sofortige Aktualisierung
        )
    
    # Validierung: mindestens eine Metrik ausgewählt
    if not selected:
        st.warning("⚠️ Please select at least one metric.")
        return
    
    # OPTIMIERUNG: Skip Datenberechnung wenn nur Player-Färbung!
    if st.session_state.get('player_clicked', False):
        # Nur Styling neu anwenden - KEINE Pandas-Operationen!
        # player_overview muss aus vorherigem Run existieren
        if 'player_overview_cache' not in st.session_state:
            # Fallback: Flag war inkonsistent, berechne normal
            st.session_state.player_clicked = False
    
    if not st.session_state.get('player_clicked', False):
        # Normale Berechnung: EINMAL alle gecachten Daten holen (Mega-DataFrame!)
        player_base_minimal = player_base[['AllyCode', 'Name']].copy()
        df_all = get_all_player_metrics_per_date(df_all_dates, player_base_minimal, key_relevance_filter, relevance_dict)
        
        # Extrahiere nur relevante Spalten basierend auf Metric-Typ
        if metric_type == 'Relics':
            col_pattern = '_R'
            metric_levels = [int(r[1:]) for r in selected]  # ['R8', 'R10'] → [8, 10]
            metric_label = ' '.join(sorted(selected, key=lambda x: int(x[1:]), reverse=True))
        elif metric_type == 'Omis':
            col_pattern = 'OmiCount'
            omi_map = {'TW': 'TWOmiCount', 'GAC': 'GACOmiCount', 'TB': 'TBOmiCount', 'CQ': 'CQOmiCount'}
            metric_cols = [omi_map[s] for s in selected]
            metric_label = ' '.join(sorted(selected, reverse=True))
        elif metric_type == 'Speed':
            col_pattern = '_Speed'
            speed_map = {'10+': 'Speed10', '15+': 'Speed15', '20+': 'Speed20', '25+': 'Speed25'}
            metric_cols = [speed_map[s] for s in selected]
            metric_label = ' '.join(sorted(selected, reverse=True))
        else:  # Mod6
            col_pattern = '_Mod6'
            metric_cols = ['Mod6']
            metric_label = 'Mod6'
        
        # Finde alle Datums-Spalten für diese Metrik
        date_cols = [col for col in df_all.columns if col_pattern in col]
        available_dates = sorted(set([col.split('_')[0] for col in date_cols]), reverse=True)
        newest_date = available_dates[0]
        
        if len(available_dates) < 2:
            st.warning("⚠️ At least 2 data snapshots required for comparison.")
            return
        
        # Starte mit AllyCode und Name
        player_overview = df_all[['AllyCode', 'Name']].copy()
        
        # Für jedes Datum: Summiere die ausgewählten Metriken
        date_columns = []
        for date in available_dates:
            if metric_type == 'Relics':
                date_metric_cols = [f'{date}_R{r}' for r in metric_levels]
            elif metric_type == 'Mod6':
                date_metric_cols = [f'{date}_Mod6']
            else:
                date_metric_cols = [f'{date}_{col}' for col in metric_cols]
            
            # Summiere mit skipna=True, aber setze auf None wenn ALLE Werte NaN sind (Spieler war nicht in Gilde)
            sums = df_all[date_metric_cols].sum(axis=1, skipna=True)
            all_nan = df_all[date_metric_cols].isna().all(axis=1)
            player_overview[date] = sums.where(~all_nan, None)
            player_overview[date] = player_overview[date].astype('Int64')
            date_columns.append(date)
        
        # Berechne Delta
        if compare_date in available_dates and compare_date != newest_date:
            player_overview['Δ'] = player_overview.apply(
                lambda row: row[newest_date] - row[compare_date] 
                if pd.notna(row[newest_date]) and pd.notna(row[compare_date]) else None,
                axis=1
            )
        else:
            player_overview['Δ'] = None
        
        # Merge mit player_base_global (hat Checked/PlayerColor!)
        player_overview = player_overview.merge(
            player_base[['AllyCode', 'Checked', 'PlayerColor']], 
            on='AllyCode', 
            how='left'
        )
        
        # Füge Label-Spalte hinzu
        player_overview['Metric'] = metric_label
        
        # Sortiere nach Delta
        player_overview = player_overview.sort_values('Δ', ascending=False, na_position='last')
        player_overview = player_overview.reset_index(drop=True)
        
        # Spalten neu ordnen
        column_order = ['Name', 'AllyCode', 'Δ', 'Metric'] + date_columns
        player_overview = player_overview[column_order]
        
        # Cache für nächsten Run (falls player_clicked) - OHNE Checked/PlayerColor!
        player_overview_cache = player_overview[['Name', 'AllyCode', 'Δ', 'Metric'] + date_columns].copy()
        st.session_state.player_overview_cache = player_overview_cache
        st.session_state.date_columns_cache = date_columns
        
        # Merge AKTUELLEN Checked/PlayerColor Status (auch im normalen Pfad für Styling!)
        player_overview = player_overview.merge(
            player_base[['AllyCode', 'Checked', 'PlayerColor']], 
            on='AllyCode', 
            how='left'
        )
    else:
        # Optimierter Pfad: Nutze gecachte Daten!
        player_overview = st.session_state.player_overview_cache.copy()
        date_columns = st.session_state.date_columns_cache
        
        # Merge AKTUELLEN Checked/PlayerColor Status!
        player_overview = player_overview.merge(
            player_base[['AllyCode', 'Checked', 'PlayerColor']], 
            on='AllyCode', 
            how='left'
        )
    
    # Erstelle Mapping für Styling (nach Merge!)
    player_color_mapping = dict(zip(player_overview['Name'], player_overview['PlayerColor']))
    
    # Styling für checked players
    def highlight_checked_players(row):
        player_name = row['Name']
        is_checked = player_base.loc[player_base['Name'] == player_name, 'Checked'].iloc[0] if player_name in player_base['Name'].values else False
        
        if is_checked:
            color = player_color_mapping.get(player_name, '#CCCCCC')
            return [f'background-color: {color}99' for _ in row]
        else:
            return ['' for _ in row]
    
    styled_df = player_overview.style.apply(highlight_checked_players, axis=1)
    
    # Column configuration
    column_config = {
        'Name': st.column_config.TextColumn('Player Name', width=175),
        'AllyCode': st.column_config.TextColumn('AllyCode', width=120),
        'Δ': st.column_config.NumberColumn(
            'Δ',
            help='Change since comparison date',
            format='%+d',
            width=80
        ),
        'Metric': st.column_config.TextColumn('Metric', width=110)
    }
    
    # Date columns as numbers (mark comparison date with 📍)
    for col in date_columns:
        label = f"📍 {col}" if col == compare_date else col
        column_config[col] = st.column_config.NumberColumn(label, format='%d')
    
    # on_select Callback für Row-Selection
    def on_progress_select():
        selection = st.session_state.progress_table_selection
        
        if hasattr(selection, 'selection'):
            sel_dict = selection.selection
        elif isinstance(selection, dict):
            sel_dict = selection.get('selection', {})
        else:
            return
        
        selected_cells = sel_dict.get('cells', [])
        
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
                current_state = st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ].iloc[0]
                
                st.session_state.player_base_global.loc[
                    st.session_state.player_base_global['Name'] == player_name, 
                    'Checked'
                ] = not current_state
                
                # Setze Flag: Nur Player-Färbung, keine Neuberechnung nötig!
                st.session_state.player_clicked = True
                
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width="content",
        height=1100,
        row_height=21,
        column_order=("Name", "Δ", "Metric") + tuple(date_columns),
        column_config=column_config,
        selection_mode="single-cell",
        on_select=on_progress_select,
        key="progress_table_selection"
    )

@st.cache_data
def get_raw_mod_data(df_all_dates, player_base, relevance_dict=None):
    """
    Lädt ALLE Mod-Daten ohne Filter (mit Caching).
    Speichert pro Player → pro Character → Mod-Daten + Metadata.
    
    Args:
        df_all_dates: DataFrame mit allen Datenständen (wird gefiltert auf neuesten)
        player_base: DataFrame mit [AllyCode, Name] - NUR unveränderliche Spalten!
        relevance_dict: Optional {base_id: 'yes'/'no'} für IsKey Metadata
    
    Returns:
        Dict[AllyCode, Dict]: {
            ally_code: {
                'Name': player_name,
                'Characters': {
                    base_id: {
                        'Name': char_name,
                        'Arrow': {stat_name: count},
                        'Triangle': {...},
                        'Circle': {...},
                        'Cross': {...},
                        'Sets': {set_name: count},
                        'Categories': [list],
                        'Alignment': str,
                        'Role': str,
                        'IsKey': bool
                    }
                }
            }
        }
    """
    from data.mod_mappings import get_primary_stat_name, get_mod_set_name
    
    # Lade Character-Metadata
    char_data = load_character_data()
    char_lookup = {char['base_id']: char for char in char_data}
    
    available_dates = sorted(df_all_dates['date'].unique(), reverse=True)
    newest_date = available_dates[0]
    df_newest = df_all_dates[df_all_dates['date'] == newest_date]
    
    # Nur Characters (keine Ships)
    df_chars = df_newest[df_newest['CombatType'] == 'Character']
    
    slot_to_column = {
        SLOT_KEY_ARROW: 'PrimaryArrow',
        SLOT_KEY_TRIANGLE: 'PrimaryTriangle',
        SLOT_KEY_CIRCLE: 'PrimaryCircle',
        SLOT_KEY_CROSS: 'PrimaryCross'
    }
    
    result = {}
    for _, player_row in player_base.iterrows():
        ally_code = player_row['AllyCode']
        player_name = player_row['Name']
        
        df_player = df_chars[df_chars['AllyCode'] == ally_code]
        
        if df_player.empty:
            continue
        
        characters = {}
        
        # Iteriere über alle Characters des Spielers
        for _, char_row in df_player.iterrows():
            base_id = char_row['BaseId']
            char_name = char_row['Name']
            
            # Hole Metadata aus characters.json
            char_meta = char_lookup.get(base_id, {})
            categories = char_meta.get('categories', [])
            
            # Primary Stats für alle Slots
            primary_stats = {}
            for slot, column in slot_to_column.items():
                stat_id = char_row.get(column, 0)
                if stat_id and stat_id != 0:
                    stat_id_str = str(int(stat_id))
                    if stat_id_str != '0':
                        stat_name = get_primary_stat_name(stat_id_str)
                        primary_stats[slot] = {stat_name: 1}
                    else:
                        primary_stats[slot] = {}
                else:
                    primary_stats[slot] = {}
            
            # Mod Sets parsen
            set_counts = {}
            sets_str = char_row.get('Sets', '')
            if pd.notna(sets_str) and sets_str != '0':
                set_ids = str(sets_str).split('+')
                for set_id in set_ids:
                    set_id = set_id.strip()
                    if set_id and set_id != '0':
                        set_info = get_mod_set_name(set_id)
                        if isinstance(set_info, tuple):
                            set_name, set_size = set_info
                        else:
                            set_name = str(set_info)
                            set_size = 0
                        
                        if set_size > 0:
                            set_counts[set_name] = set_counts.get(set_name, 0) + set_size
            
            # Speichere Character-Daten
            is_key = relevance_dict.get(base_id, 'no') == 'yes' if relevance_dict else False
            
            characters[base_id] = {
                'Name': char_name,
                'Arrow': primary_stats.get(SLOT_KEY_ARROW, {}),
                'Triangle': primary_stats.get(SLOT_KEY_TRIANGLE, {}),
                'Circle': primary_stats.get(SLOT_KEY_CIRCLE, {}),
                'Cross': primary_stats.get(SLOT_KEY_CROSS, {}),
                'Sets': set_counts,
                'Categories': categories,
                'Alignment': char_meta.get('alignment', 'Unknown'),
                'Role': char_meta.get('role', 'Unknown'),
                'IsKey': is_key
            }
        
        result[ally_code] = {
            'Name': player_name,
            'Characters': characters
        }
    
    return result



def filter_and_aggregate_mod_data_simple(raw_data, analysis_type, selected_slots, filtered_base_ids):
    """
    NEUE EINFACHE VERSION: Filtert nur nach BaseId-Liste.
    Alle Character-Filter wurden bereits in der Sidebar angewendet!
    
    Args:
        raw_data: Output von get_raw_mod_data()
        analysis_type: 'Primary Stats' oder 'Mod Sets'
        selected_slots: Liste von Slots (z.B. ['Arrow', 'Triangle'])
        filtered_base_ids: Liste der erlaubten BaseIds (von Sidebar)
    
    Returns:
        Tuple[List[Dict], Set]: (Player-Stats, Alle Stats)
    """
    player_stats = []
    all_stats = set()
    
    # Konvertiere zu Set für schnellere Lookups
    allowed_base_ids = set(filtered_base_ids)
    
    for ally_code, player_data in raw_data.items():
        stat_counts = {}
        total = 0
        total_chars_counted = 0
        
        # Iteriere über alle Characters des Spielers
        for base_id, char_data in player_data['Characters'].items():
            # EINZIGER FILTER: Ist BaseId in der erlaubten Liste?
            if base_id not in allowed_base_ids:
                continue
            
            # Character ist erlaubt - aggregiere Daten
            total_chars_counted += 1
            
            if analysis_type == 'Primary Stats':
                # Aggregiere über ausgewählte Slots
                for slot in selected_slots:
                    slot_data = char_data.get(slot, {})
                    for stat_name, count in slot_data.items():
                        stat_counts[stat_name] = stat_counts.get(stat_name, 0) + count
                        total += count
                        all_stats.add(stat_name)
            else:
                # Mod Sets
                set_data = char_data.get('Sets', {})
                for set_name, count in set_data.items():
                    stat_counts[set_name] = stat_counts.get(set_name, 0) + count
                    total += count
                    all_stats.add(set_name)
        
        # Für Mod Sets: Berechne Broken Mods
        if analysis_type == 'Mod Sets' and total_chars_counted > 0:
            total_possible_mods = total_chars_counted * 6
            broken_mods = total_possible_mods - total
            if broken_mods > 0:
                stat_counts['Broken/No Set'] = broken_mods
                total += broken_mods
                all_stats.add('Broken/No Set')
        
        # Nur Spieler mit Daten hinzufügen
        if total > 0:
            player_stats.append({
                'Name': player_data['Name'],
                'AllyCode': ally_code,
                'Total': total,
                'StatCounts': stat_counts,
                'Checked': player_data['Checked'],
                'PlayerColor': player_data['PlayerColor']
            })
    
    return player_stats, all_stats


def show_mod_distribution_tab(df_newest, compare_date, key_relevance_filter, relevance_dict):
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Start: show_mod_distribution_tab", file=sys.stderr)
    
    # Callback für Radio Button
    def on_analysis_type_change():
        """Callback um Session State sofort zu aktualisieren."""
        st.session_state.mod_analysis_type = st.session_state.mod_analysis_radio
    
    # Hole player_base DIREKT aus Session State
    player_base = st.session_state.player_base_global
    
    # Initialize session state
    if 'mod_slot_selection' not in st.session_state:
        st.session_state.mod_slot_selection = [SLOT_KEY_ARROW, SLOT_KEY_TRIANGLE, SLOT_KEY_CIRCLE, SLOT_KEY_CROSS]
    if 'mod_analysis_type' not in st.session_state:
        st.session_state.mod_analysis_type = 'Primary Stats'
    if 'mod_sort_by' not in st.session_state:
        st.session_state.mod_sort_by = 'Total'
    
    # CSS: Verstecke Mod Slot Control wenn "Mod Sets" aktiv ist
    hide_control = st.session_state.mod_analysis_type != 'Primary Stats'
    st.markdown(f"""
        <style>
        .st-key-mod_slot_segmented {{
            display: {'none' if hide_control else 'block'} !important;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    # Header mit Radio und Controls
    with st.container(width=1200, horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", gap="small"):
        # Title Placeholder (wird nach Filterung aktualisiert)
        with st.container(width=410):
            title_placeholder = st.empty()

        # Sort Dropdown (wird später mit Optionen gefüllt) - feste Breite für konsistente Ausrichtung
        with st.container(width=160):
            sort_placeholder = st.empty()
        
        # Slot Selection (nur bei Primary Stats)
        if st.session_state.mod_analysis_type == 'Primary Stats':
            # CSS für größere Mod Slot Symbole (nur für dieses spezifische Control)
            st.markdown("""
                <style>
                /* Vergrößere Symbole im Mod Slot Control - nur mit key mod_slot_segmented */
                .st-key-mod_slot_segmented [aria-label="button group"] [data-testid="stIconEmoji"] {
                    font-size: 30px !important;
                }
                /* Vergrößere Markdown-Symbole - nur mit key mod_slot_segmented */
                .st-key-mod_slot_segmented [aria-label="button group"] [data-testid="stMarkdownContainer"] p {
                    font-size: 30px !important;
                    margin: 0 !important;
                }
                /* Vertikale Ausrichtung korrigieren - nur mit key mod_slot_segmented */
                .st-key-mod_slot_segmented [aria-label="button group"] {
                    margin-top: 3px !important;
                    margin-left: 10px !important;
                }
                </style>
            """, unsafe_allow_html=True)
            
            # Mapping: Display Name <-> Data Key
            slot_display_to_key = {
                SLOT_ARROW: SLOT_KEY_ARROW,
                SLOT_TRIANGLE: SLOT_KEY_TRIANGLE,
                SLOT_CIRCLE: SLOT_KEY_CIRCLE,
                SLOT_CROSS: SLOT_KEY_CROSS
            }
            slot_key_to_display = {v: k for k, v in slot_display_to_key.items()}
            
            # Konvertiere Session State Keys zu Display Values für Default
            default_display = [slot_key_to_display[key] for key in st.session_state.mod_slot_selection if key in slot_key_to_display]
            
            slot_options = [SLOT_ARROW, SLOT_TRIANGLE, SLOT_CIRCLE, SLOT_CROSS]
            selected_slots_display = st.segmented_control(
                "Mod Slot",
                options=slot_options,
                default=default_display,
                key="mod_slot_segmented",
                selection_mode="multi",
                label_visibility="collapsed"
            )
            
            # Konvertiere Display Values zurück zu Data Keys
            selected_slots = [slot_display_to_key[disp] for disp in selected_slots_display] if selected_slots_display else []
            
            # Update session state nur wenn sich Werte geändert haben
            if selected_slots != st.session_state.mod_slot_selection:
                st.session_state.mod_slot_selection = selected_slots
        else:
            selected_slots = None
            st.markdown('<div style="height: 42px;"></div>', unsafe_allow_html=True)  # Spacer

        # Radio: Primary Stats vs Mod Sets
        radio_options = ['Primary Stats', 'Mod Sets']
        current_index = radio_options.index(st.session_state.mod_analysis_type)
        analysis_type = st.radio(
            "Analysis Type",
            options=radio_options,
            index=current_index,
            horizontal=True,
            key="mod_analysis_radio",
            label_visibility="collapsed",
            on_change=on_analysis_type_change  # Callback für sofortige Aktualisierung
        )
    
    # Validierung
    if analysis_type == 'Primary Stats' and not selected_slots:
        st.warning("⚠️ Please select at least one mod slot.")
        return
    
    # Lade RAW Mod-Daten (gecacht, ohne Filter)
    # NUR unveränderliche Spalten übergeben, damit Cache nicht bei Player-Checks invalidiert wird!
    player_base_minimal = player_base[['AllyCode', 'Name']].copy()

    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Before: get_raw_mod_data", file=sys.stderr)
    raw_data = get_raw_mod_data(df_newest, player_base_minimal, relevance_dict)
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] After: get_raw_mod_data", file=sys.stderr)
    print(f"Länge raw_data: {len(raw_data)}", file=sys.stderr)

    
    if not raw_data:
        st.warning("⚠️ No mod data found.")
        return
    
    # Ergänze Checked und PlayerColor aus aktuellem player_base (nach Cache!)
    for ally_code, player_data in raw_data.items():
        player_row = player_base[player_base['AllyCode'] == ally_code]
        if not player_row.empty:
            player_data['Checked'] = player_row.iloc[0]['Checked']
            player_data['PlayerColor'] = player_row.iloc[0]['PlayerColor']
        else:
            player_data['Checked'] = False
            player_data['PlayerColor'] = '#CCCCCC'
    
    # Nutze gefilterte BaseIds aus Session State (von Sidebar berechnet)
    filtered_base_ids = st.session_state.get('filtered_base_ids', [])
    
    # Filtere und aggregiere Daten - EINFACH mit BaseId-Liste!
    player_stats, all_stats = filter_and_aggregate_mod_data_simple(
        raw_data=raw_data,
        analysis_type=analysis_type,
        selected_slots=selected_slots if analysis_type == 'Primary Stats' else [],
        filtered_base_ids=filtered_base_ids
    )
    
    # Character Count = Anzahl der gefilterten BaseIds
    total_chars = len(filtered_base_ids)
    
    # Update Titel mit Character-Anzahl
    with title_placeholder:
        if total_chars > 0:
            title = f'<h3 style="margin-top: -12px; margin-bottom: 0;">{TAB_MOD_DISTRIBUTION} ({total_chars} chars)</h3>'
        else:
            title = f'<h3 style="margin-top: -12px; margin-bottom: 0;">{TAB_MOD_DISTRIBUTION} (0 chars)</h3>'
        st.markdown(title, unsafe_allow_html=True)
    
    if not player_stats:
        st.warning("⚠️ No data found for selected options.")
        return
    
    # Sortiere Stats nach Häufigkeit (häufigste zuerst)
    stat_totals = {}
    for player in player_stats:
        for stat, count in player['StatCounts'].items():
            stat_totals[stat] = stat_totals.get(stat, 0) + count
    
    all_stats_sorted = sorted(all_stats, key=lambda x: stat_totals.get(x, 0), reverse=True)
    
    # Sort-Dropdown mit dynamischen Optionen
    with sort_placeholder:
        sort_options = ['Total', 'Player Name'] + all_stats_sorted
        sort_by = st.selectbox(
            "Sort by:",
            options=sort_options,
            index=sort_options.index(st.session_state.mod_sort_by) if st.session_state.mod_sort_by in sort_options else 0,
            key="mod_sort_select",
            width=150,
            label_visibility="collapsed"
        )
        st.session_state.mod_sort_by = sort_by
    
    # Erstelle DataFrame und sortiere
    df_stats = pd.DataFrame(player_stats)
    
    if sort_by == 'Total':
        df_stats = df_stats.sort_values(by=['Checked', 'Total'], ascending=[False, False])
    elif sort_by == 'Player Name':
        df_stats = df_stats.sort_values(by=['Checked', 'Name'], ascending=[False, True])
    else:
        # Sortiere nach spezifischer Stat
        df_stats['SortValue'] = df_stats['StatCounts'].apply(lambda x: x.get(sort_by, 0))
        df_stats = df_stats.sort_values(by=['Checked', 'SortValue'], ascending=[False, False])
        df_stats = df_stats.drop('SortValue', axis=1)
    
    df_stats = df_stats.reset_index(drop=True)
    
    # Berechne AVERAGE-Zeile
    avg_stat_counts = {}
    total_players = len(df_stats)
    
    if total_players > 0:
        for stat in all_stats:
            total_count = sum(player['StatCounts'].get(stat, 0) for player in player_stats)
            avg_stat_counts[stat] = total_count / total_players
        
        avg_total = sum(avg_stat_counts.values())
        
        avg_row = pd.DataFrame([{
            'Name': '∅ ━━━━━━━━━',
            'AllyCode': '',
            'Total': avg_total,
            'StatCounts': avg_stat_counts,
            'Checked': False,  # Wird separat behandelt
            'PlayerColor': '#FFFFFF'
        }])
        
        # Finde Position: nach letztem checked player
        last_checked_idx = df_stats[df_stats['Checked'] == True].index.max() if df_stats['Checked'].any() else -1
        insert_pos = last_checked_idx + 1 if last_checked_idx >= 0 else 0
        
        # Füge AVERAGE ein
        df_stats = pd.concat([
            df_stats.iloc[:insert_pos],
            avg_row,
            df_stats.iloc[insert_pos:]
        ]).reset_index(drop=True)
    
    # Bestimme Reihenfolge für Legend/Traces
    # Wenn nach spezifischer Stat sortiert: Diese Stat zuerst, Rest nach Häufigkeit
    if sort_by not in ['Total', 'Player Name'] and sort_by in all_stats_sorted:
        # Sortierte Stat zuerst, dann Rest nach Häufigkeit
        stats_display_order = [sort_by] + [s for s in all_stats_sorted if s != sort_by]
    else:
        # Standard: Nach Häufigkeit
        stats_display_order = all_stats_sorted
    
    # Erstelle Horizontal Stacked Bar Chart
    # Feste Farb-Zuordnung für Stats (konsistent über Primary Stats und Mod Sets)
    STAT_COLOR_MAP = {
        'Speed': "#2632D1",           # Blau - wichtigster Stat
        'Offense': '#FFA07A',         # Orange
        'Crit Damage': '#FFD700',     # Gold
        'Crit Chance': '#F7DC6F',     # Gelb
        'Health': '#4ECDC4',          # Türkis-Grün
        'Protection': '#98D8C8',      # Mint
        'Defense': '#45B7D1',         # Blau
        'Potency': '#BB8FCE',         # Lila
        'Tenacity': '#85C1E2',        # Hellblau
        'Accuracy': '#F8B88B',        # Pfirsich
        'Crit Avoidance': '#ABEBC6',  # Hellgrün
        'Broken/No Set': '#CCCCCC',   # Grau
        'Empty/Unmoded': '#E0E0E0'    # Hellgrau
    }
    
    # Fallback-Farben für unbekannte Stats
    fallback_colors = ['#D3D3D3', '#B0B0B0', '#909090']
    
    # Erstelle stat_colors dict mit festen Zuordnungen
    stat_colors = {}
    fallback_idx = 0
    for stat in all_stats_sorted:
        if stat in STAT_COLOR_MAP:
            stat_colors[stat] = STAT_COLOR_MAP[stat]
        else:
            stat_colors[stat] = fallback_colors[fallback_idx % len(fallback_colors)]
            fallback_idx += 1
    
    fig = go.Figure()
    
    # Für jede Stat: Horizontal Bar (in dynamischer Reihenfolge)
    for stat in stats_display_order:
        values = [stats.get(stat, 0) for stats in df_stats['StatCounts']]
        
        # Formatierung: Ganze Zahlen für echte Player, Dezimalzahlen für AVERAGE
        text_values = []
        for idx, val in enumerate(values):
            if df_stats.iloc[idx]['Name'] == '∅ ━━━━━━━━━':
                text_values.append(f'{val:.1f}')
            else:
                text_values.append(int(val))
        
        fig.add_trace(go.Bar(
            name=stat,
            y=df_stats['Name'],
            x=values,
            orientation='h',
            marker=dict(color=stat_colors[stat]),
            text=text_values,
            textposition='inside',
            hovertemplate=f'{stat}: %{{x:.1f}}<extra></extra>'
        ))
    
    # Layout
    fig.update_layout(
        barmode='stack',
        height=max(370, len(df_stats) * 25 - 70),
        margin=dict(l=10, r=10, t=10, b=40),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        xaxis_title="Count",
        yaxis=dict(autorange="reversed"),
        hovermode='closest'
    )
    
    # Zeige Chart
    st.plotly_chart(fig, width='stretch')


def show_settings_tab(df_all_dates):
    """Tab 7 - App Info & User Guide."""
    
    st.markdown(f'<h3 style="margin-top: -12px; margin-bottom: 0;">{TAB_INFO}</h3>', unsafe_allow_html=True)
    
    # Technische Info
    with st.expander("📊 **Technische Informationen**", expanded=False):
        st.markdown(f"""
        - **Geladene CSVs:** {len(df_all_dates['date'].unique())} Datenabzüge
        - **Verfügbare Daten:** {', '.join(sorted(df_all_dates['date'].unique(), reverse=True))}
        - **Gesamt-Einträge:** {len(df_all_dates):,} Zeilen
        - **Memory:** {df_all_dates.memory_usage(deep=True).sum() / 1024**2:.2f} MB
        - **Spieler (neueste CSV):** {df_all_dates[df_all_dates['date'] == df_all_dates['date'].max()]['AllyCode'].nunique()}
        """)
    
    # Benutzerhandbuch
    st.markdown("## 📖 Benutzerhandbuch")
    
    with st.expander("🗂️ **Datenbasis**", expanded=False):
        st.markdown("""
        - **Export von Hot Utils:** Guild > Overview > Download Data > **Download Data with Full Roster!**
        - Die CSV-Datei mit einem Datum versehen und an DrPivot senden
        - Die Dateien werden im öffentlichen GitHub Repository der App abgelegt, werden aber vorher verschlüsselt (max. 1 pro Monat und Gilde)
        - Ein manueller Export kann durch User temporär hochgeladen werden, es erfolgt aber ein "Berechtigungs-Check" gegen das Repository
        """)
    
    with st.expander("🏠 **Startbildschirm**", expanded=False):
        st.markdown("""
        - **AllyCode (rechts oben):** Wenn eingegeben, erfolgt eine Markierung des Players in den Analysen
        - **Tipp:** Nach Eingabe des AllyCodes einen Bookmark im Browser speichern (AllyCode dann vorausgefüllt)
        - **Gilde auswählen:** Verfügbare Hot-Utils-Exporte der Gilde werden angezeigt
        - **Daten auswählen:** Mehrere Exporte für Zeitvergleiche auswählen
        - **Optional:** Aktuelleren Hot-Utils-Export zusätzlich hochladen (ist nur temporär)
        """)
    
    with st.expander("🎛️ **Sidebar (Filterung)**", expanded=False):
        st.markdown("""
        - **New Selection:** Links oben - zurück zum Startbildschirm
        - **Character Filter:**
          - Combat Type, Alignment, Role, Category und Abilities (!) als die üblichen Filter
          - Category und Abilities können mit **"AND"** oder **"OR"** verknüpft werden
          - Beispiel: Sith "OR" First Order = 32 chars, aber mit "AND" nur DS Rey und Sith Trooper
        - **Key Characters:** 👍 = 173 key chars mit empfohlenem Relic-Level festgelegt
        - **Character Selection:** Unterster Filter für Auswahl eines einzelnen Characters (wirkt nur in "Char Stats")
        - **Sidebar:** Kann aus- und eingeblendet werden
        """)
    
    st.markdown("## 📊 Analysen")
    
    with st.expander(f"**{TAB_OVERVIEW}**", expanded=False):
        st.markdown("""
        **Bezieht sich auf aktuellsten Upload**
        
        - **Tabelle:** Gefilterte Chars mit:
          - Relic-Level des ausgewählten Players
          - Relic-Empfehlung mit Delta (Δ) und Kommentar
          - Anzahl Relic-Level in der Gilde (R9, R8, R7, R6, <R6)
        - **Relic-Kosten:** Benötigte Signaldaten und Relikt-Material, um die Empfehlung der gefilterten Chars zu erreichen
        - **Hinweis:** Alle Tabellen in Streamlit können nach jeder Spalte sortiert werden
        """)
    
    with st.expander(f"**{TAB_CHAR_STATS}**", expanded=False):
        st.markdown("""
        **Bezieht sich auf aktuellsten Upload**
        
        - **Diagramme:** Stats des ausgewählten Chars für alle Player der Gilde
        - **Tabelle:** Detaillierte Stats-Übersicht aller Player
        - **Interaktion:** Durch Klick auf eine Zeile können Player in Tabelle und Diagramm farblich markiert werden
        - **Analyseziel:** Ist mein XYZ vernünftig gemodded oder komplett daneben?
        """)
    
    with st.expander(f"**{TAB_PROGRESS}**", expanded=False):
        st.markdown("""
        **Vergleich von Datenexporten**
        
        - **Kennzahl-Auswahl:** Multi-Select für Relic-Level, Omicron-Typen oder Speed-Thresholds
        - **Tabelle:** Alle Player mit der ausgewählten Kennzahl
        - **Delta (Δ):** Fortschritt vom aktuellsten Datenstand zum ausgewählten Vergleichsdatum (Dropdown in Titelzeile)
        - **Sortierung:** Nach Delta sortiert (größter Fortschritt oben)
        - **Analyseziel:** Wie ist mein Fortschritt im Vergleich zu anderen in der Gilde?
        """)
    
    with st.expander(f"**{TAB_MOD_DISTRIBUTION}**", expanded=False):
        st.markdown("""
        **Bezieht sich auf aktuellsten Upload**
        
        - **Datenquelle:** Mod-Sets bzw. Primaries werden aus den HU-Daten ausgezählt (pro Character)
        - **Darstellung:** Gestapeltes Balkendiagramm für jeden Player
        - **AVERAGE-Zeile:** Mittelwert über alle Player; ausgewählte Player (aus anderen Tabs) erscheinen über dieser Zeile
        - **Sortierung:**
          - Stats im Diagramm nach rechts absteigend sortiert (z.B. bei Mod Sets: Health ganz links)
          - Über Dropdown kann eine Stat für vertikale Sortierung ausgewählt werden (erscheint dann links im Diagramm)
        - **Legende:** Stats können aus- und eingeblendet werden
        - **Filterung:** Sidebar-Filter sind wirksam
        
        **Analyseziel (Beispiel):**
        - Haben meine key char attacker genügend viele Offense Primaries auf dem Cross?
        - Passt die Verteilung meiner verfügbaren bzw. ausgerüsteten Mods, um mein Roster optimal zu modden?
        
        **Hinweis:** Es handelt sich nur um eine Tendenzaussage. Wenn jemand sehr wenig Speed Primaries auf dem Pfeil hat, sind vermutlich genügend bessere Stats mit sehr guten Speed Secondaries vorhanden!
        """)


def show_sidebar(df_newest, guild_filter, data_info, player_name, available_dates, compare_date):
    """
    Zeigt die komplette Sidebar mit allen Filtern und Controls.
    
    Args:
        df_newest: DataFrame mit neuesten Daten (für Filter-Berechnungen)
        guild_filter: Name der aktuellen Gilde
        data_info: String mit Info über geladene CSVs
        player_name: Name des Default-Spielers
        available_dates: Liste verfügbarer Daten
        compare_date: Aktuell ausgewähltes Vergleichsdatum
    
    Returns:
        Tuple: (compare_date, key_relevance_filter, alignment_filter, categories_filter, 
                role_filter, ability_classes_filter, filters_active)
    """
    # Sidebar Info (immer anzeigen)
    st.sidebar.markdown(f"**Guild:** {guild_filter}  \n**Data:** {data_info}  \n**Player:** {player_name}")
    
    # Button to go back to selection
    if st.sidebar.button("↩️ New Selection"):
        del st.session_state['analysis_started']
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🎛️ Character Filter:**")
    
    # Initialize session state for filters
    if 'combat_type_filter' not in st.session_state:
        st.session_state.combat_type_filter = ['Character']
    if 'key_relevance_filter' not in st.session_state:
        st.session_state.key_relevance_filter = ['👍']
    if 'alignment_filter' not in st.session_state:
        st.session_state.alignment_filter = []
    if 'categories_filter' not in st.session_state:
        st.session_state.categories_filter = []
    if 'role_filter' not in st.session_state:
        st.session_state.role_filter = []
    if 'ability_classes_filter' not in st.session_state:
        st.session_state.ability_classes_filter = []
    
    # Reset counter for unique keys
    if 'filter_reset_counter' not in st.session_state:
        st.session_state.filter_reset_counter = 0
    
    reset_suffix = f"_{st.session_state.filter_reset_counter}"
    
    # Check if active tab is a Player tab
    is_player_tab = st.session_state.get('active_tab', '') in [TAB_PROGRESS]
    
    # OPTIMIZATION: Bei player_clicked überspringen wir teure Berechnungen!
    player_clicked = st.session_state.get('player_clicked', False)
      
    # ============================================================================
    # HAUPTLOGIK: Player Tab vs Character Tabs
    # ============================================================================
    if is_player_tab:
        # ═══════════════════════════════════════════════════════════════════════
        # PLAYER TAB (Progress): Minimal - nur Key Relevance Filter
        # ═══════════════════════════════════════════════════════════════════════
        
        # 1. Render: Key Relevance Filter (full width)
        key_relevance_filter = st.sidebar.segmented_control(
            "Key Relevance",
            options=['👍', '👎'],
            default=st.session_state.get('key_relevance_filter', ['👍']),
            key=f"key_relevance_segmented{reset_suffix}",
            selection_mode="multi",
            label_visibility="collapsed"
        )
        if key_relevance_filter != st.session_state.get('key_relevance_filter', ['👍']):
            st.session_state.key_relevance_filter = key_relevance_filter
        
        # 2. Set: Andere Filter leer
        combat_type_filter = []
        alignment_filter = []
        categories_filter = []
        role_filter = []
        ability_classes_filter = []
        filters_active = False
        
        # 3. Calculate: available_base_ids (OPTIMIZATION: aus Cache wenn player_clicked)
        relevance_dict, _, _ = load_character_relevance_data()
        
        # OPTIMIZATION: available_base_ids aus Cache holen
        if player_clicked and 'available_base_ids_cache' in st.session_state:
            available_base_ids = st.session_state.available_base_ids_cache
        else:
            available_base_ids = set(df_newest[df_newest['CombatType'] == 'Character']['BaseId'].unique())
            st.session_state.available_base_ids_cache = available_base_ids
        
        if key_relevance_filter:
            if '👍' in key_relevance_filter and '👎' not in key_relevance_filter:
                filtered_base_ids = [base_id for base_id, value in relevance_dict.items() 
                                   if value == 'yes' and base_id in available_base_ids]
            elif '👎' in key_relevance_filter and '👍' not in key_relevance_filter:
                filtered_base_ids = [base_id for base_id, value in relevance_dict.items() 
                                   if value == 'no' and base_id in available_base_ids]
            else:
                filtered_base_ids = [base_id for base_id in relevance_dict.keys() 
                                   if base_id in available_base_ids]
        else:
            filtered_base_ids = [base_id for base_id in relevance_dict.keys() 
                               if base_id in available_base_ids]
        
    else:
        # ═══════════════════════════════════════════════════════════════════════
        # CHARACTER TABS (Overview, Char Stats, Mod Distribution): Volle Filter
        # ═══════════════════════════════════════════════════════════════════════
        
        # 1. Load: Character data (needed for all filters)
        characters_data = load_units_data()
        
        # 2. Get: Newest date for filtering (from available_dates)
        date_filter = available_dates[0]
        
        # 3. Render: CombatType + Key Relevance side by side
        col1, col2 = st.sidebar.columns([3, 2])
        with col1:
            combat_type_filter = st.segmented_control(
                "Combat Type",
                options=COMBAT_TYPES,
                default=st.session_state.get('combat_type_filter', ['Character']),
                key=f"combat_type_segmented{reset_suffix}",
                selection_mode="multi",
                label_visibility="collapsed"
            )
            if combat_type_filter != st.session_state.get('combat_type_filter', ['Character']):
                st.session_state.combat_type_filter = combat_type_filter
        
        with col2:
            key_relevance_filter = st.segmented_control(
                "Key Relevance",
                options=['👍', '👎'],
                default=st.session_state.get('key_relevance_filter', ['👍']),
                key=f"key_relevance_segmented{reset_suffix}",
                selection_mode="multi",
                label_visibility="collapsed"
            )
            if key_relevance_filter != st.session_state.get('key_relevance_filter', ['👍']):
                st.session_state.key_relevance_filter = key_relevance_filter
        
        # Filter DataFrame by CombatType
        if combat_type_filter:
            df_for_filters = df_newest[df_newest['CombatType'].isin(combat_type_filter)]
        else:
            df_for_filters = df_newest
        
        # Filter characters data for dynamic filters
        available_base_ids = set(df_for_filters['BaseId'].unique())
        characters_data_filtered = [char for char in characters_data if char.get('base_id') in available_base_ids]
        
        # Collect all available options
        all_alignments = sorted(list({char.get('alignment', '') for char in characters_data_filtered if char.get('alignment')}))
        
        # Alignment Filter
        alignment_filter = st.sidebar.segmented_control(
            "Alignment",
            options=all_alignments,
            default=st.session_state.get('alignment_filter', []),
            key=f"alignment_segmented{reset_suffix}",
            selection_mode="multi",
            label_visibility="collapsed"
        )
        if alignment_filter != st.session_state.get('alignment_filter', []):
            st.session_state.alignment_filter = alignment_filter
        
        # Filter characters for subsequent filters
        filtered_chars_for_categories = characters_data_filtered
        if alignment_filter:
            filtered_chars_for_categories = [char for char in filtered_chars_for_categories if char.get('alignment') in alignment_filter]
        
        # Available roles
        filtered_chars_for_roles = filtered_chars_for_categories
        roles_set = set()
        for char in filtered_chars_for_roles:
            role = char.get('role')
            if role and role.strip():
                if role != 'Unknown':
                    roles_set.add(role)
            else:
                roles_set.add('?')
        available_roles = sorted(list(roles_set))
        
        # Role Filter
        role_filter = st.sidebar.segmented_control(
            "Role",
            options=available_roles,
            default=[role for role in st.session_state.get('role_filter', []) if role in available_roles],
            key=f"role_segmented{reset_suffix}",
            selection_mode="multi",
            label_visibility="collapsed"
        )
        if role_filter != st.session_state.get('role_filter', []):
            st.session_state.role_filter = role_filter
        
        # Available categories
        available_categories = sorted(list({cat for char in filtered_chars_for_categories for cat in char.get('categories', [])}))
        
        # Category Filter with AND/OR toggle
        col_cat_label, col_cat_toggle = st.sidebar.columns([2, 2])
        with col_cat_label:
            st.markdown("**Categories:**")
        with col_cat_toggle:
            current_state = st.session_state.get('categories_use_and', False)
            categories_use_and = st.checkbox(
                "AND" if current_state else "OR",
                value=current_state,
                key=f"categories_and_toggle{reset_suffix}",
                help="Checked: AND logic (all selected). Unchecked: OR logic (any selected)"
            )
            if categories_use_and != current_state:
                st.session_state.categories_use_and = categories_use_and
                st.rerun()
        
        categories_filter = st.sidebar.multiselect(
            "Categories",
            options=available_categories,
            default=[cat for cat in st.session_state.get('categories_filter', []) if cat in available_categories],
            key=f"categories_multiselect{reset_suffix}",
            label_visibility="collapsed"
        )
        if categories_filter != st.session_state.get('categories_filter', []):
            st.session_state.categories_filter = categories_filter
        
        # Filter further for ability classes
        filtered_chars_for_abilities = filtered_chars_for_categories
        if role_filter:
            filtered_chars_for_abilities = [char for char in filtered_chars_for_abilities if char.get('role') in role_filter]
        if categories_filter:
            filtered_chars_for_abilities = [char for char in filtered_chars_for_abilities 
                                          if any(cat in char.get('categories', []) for cat in categories_filter)]
        
        # Available ability classes
        available_ability_classes = sorted(list({ac for char in filtered_chars_for_abilities for ac in char.get('ability_classes', [])}))
        
        # Ability Classes Filter with AND/OR toggle
        col_ac_label, col_ac_toggle = st.sidebar.columns([2, 2])
        with col_ac_label:
            st.markdown("**Ability classes:**")
        with col_ac_toggle:
            current_state = st.session_state.get('ability_classes_use_and', False)
            ability_classes_use_and = st.checkbox(
                "AND" if current_state else "OR",
                value=current_state,
                key=f"ability_classes_and_toggle{reset_suffix}",
                help="Checked: AND logic (all selected). Unchecked: OR logic (any selected)"
            )
            if ability_classes_use_and != current_state:
                st.session_state.ability_classes_use_and = ability_classes_use_and
                st.rerun()
        
        ability_classes_filter = st.sidebar.multiselect(
            "Ability classes",
            options=available_ability_classes,
            default=[ac for ac in st.session_state.get('ability_classes_filter', []) if ac in available_ability_classes],
            key=f"ability_classes_multiselect{reset_suffix}",
            label_visibility="collapsed"
        )
        if ability_classes_filter != st.session_state.get('ability_classes_filter', []):
            st.session_state.ability_classes_filter = ability_classes_filter
        
        # Reset filters button
        if st.sidebar.button("🗑️ Reset all filters"):
            st.session_state.filter_reset_counter += 1
            st.session_state.combat_type_filter = []
            st.session_state.alignment_filter = []
            st.session_state.categories_filter = []
            st.session_state.categories_use_and = False
            st.session_state.role_filter = []
            st.session_state.ability_classes_filter = []
            st.session_state.ability_classes_use_and = False
            if 'selected_character_tab2' in st.session_state:
                del st.session_state.selected_character_tab2
            st.rerun()
        
        # 4. Check: Sind Filter aktiv?
        filters_active = bool(alignment_filter or categories_filter or role_filter or ability_classes_filter)
        
        # 5. Calculate: available_base_ids (OPTIMIZATION: aus Cache wenn player_clicked)
        relevance_dict, _, _ = load_character_relevance_data()
        
        if player_clicked and 'available_base_ids_cache' in st.session_state:
            available_base_ids = st.session_state.available_base_ids_cache
        else:
            available_base_ids = set(df_newest[df_newest['CombatType'] == 'Character']['BaseId'].unique())
            st.session_state.available_base_ids_cache = available_base_ids
        
        # 6. Calculate: filtered_base_ids (mit ALLEN Filtern)
        characters_only = [char for char in characters_data if char.get('combat_type') == 1]
        
        filtered_characters = apply_filters(
            characters_only,
            alignment_filter, 
            categories_filter, 
            role_filter, 
            ability_classes_filter,
            key_relevance_filter=key_relevance_filter,
            relevance_dict=relevance_dict,
            categories_use_and=st.session_state.get('categories_use_and', False),
            ability_classes_use_and=st.session_state.get('ability_classes_use_and', False)
        )
        filtered_base_ids = [char['base_id'] for char in filtered_characters 
                           if char['base_id'] in available_base_ids]
        
        # 7. Render: Character Selection for Tab 2
        st.sidebar.markdown("---")
        st.sidebar.markdown("**☯ Character Selection:**")
        
        if filters_active:
            available_characters_tab2 = [(char['name'], char['base_id']) 
                                         for char in characters_data 
                                         if char['base_id'] in filtered_base_ids]
        else:
            available_characters_tab2 = [(char['name'], char['base_id']) for char in characters_data]
        
        character_names_tab2 = [name for name, base_id in available_characters_tab2]
        
        if character_names_tab2:
            selected_character_tab2 = st.sidebar.selectbox(
                "Character for Tab 2:",
                character_names_tab2,
                key=f"tab2_character_select{reset_suffix}"
            )
            
            if 'selected_character_tab2' not in st.session_state:
                st.session_state.selected_character_tab2 = selected_character_tab2
            else:
                if st.session_state.selected_character_tab2 != selected_character_tab2:
                    st.session_state.selected_character_tab2 = selected_character_tab2
    
    # ============================================================================
    # GEMEINSAME LOGIK: Speichere Ergebnisse
    # ============================================================================
    
    # Speichere in Session State - wird von allen Tabs verwendet!
    st.session_state.filtered_base_ids = filtered_base_ids
    st.session_state.filters_active = filters_active
    
    # Uncheck All button
    st.sidebar.markdown("---")
    if st.sidebar.button("❌ Uncheck All", key="uncheck_all_btn", width='stretch'):
        if 'player_base_global' in st.session_state:
            default_ally_code = st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE)
            st.session_state.player_base_global['Checked'] = (
                st.session_state.player_base_global['AllyCode'].astype(str) == default_ally_code
            )
            st.rerun()
    
    return (compare_date, key_relevance_filter, alignment_filter, categories_filter, 
            role_filter, ability_classes_filter, filters_active)


def show_tab_menu():
    """
    Zeigt Tab-Navigation mit Buttons.
    Returns: active_tab (string)
    """
    # Initialize active_tab
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = TAB_OVERVIEW
    
    # Tab options
    tabs = [
        TAB_OVERVIEW,
        TAB_PROGRESS,
        TAB_CHAR_STATS,
        TAB_MOD_DISTRIBUTION,
        TAB_INFO
    ]
    
    # Callback to set active tab BEFORE rerun
    def set_tab(tab_name):
        st.session_state.active_tab = tab_name
    
    # Create container with columns for buttons
    with st.container():
        cols = st.columns(5, gap="small")
        
        for i, tab in enumerate(tabs):
            with cols[i]:
                # Button type: primary if active, secondary otherwise
                button_type = "primary" if st.session_state.active_tab == tab else "secondary"
                
                # Button with callback
                st.button(
                    tab,
                    key=f"tab_btn_{i}",
                    type=button_type,
                    on_click=set_tab,
                    args=(tab,),
                    width='stretch'
                )
    
    return st.session_state.active_tab


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Start: main", file=sys.stderr)

    st.set_page_config(
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'About': "SWGOH Guild Roster Analyzer by DrPivot"
        }
    )
    
    # Custom CSS for better layout   
    st.markdown(f"""
        <style>
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
        /* Sidebar-Breite erhöhen (pills nebeneinander) - nur wenn expanded */
        section[data-testid="stSidebar"]:not([aria-expanded="false"]) {{
            width: 380px !important;
            min-width: 380px !important;
        }}
        
        /* Tab Navigation Buttons - consistent height */
        button[kind="primary"], button[kind="secondary"] {{
            height: 42px !important;
            min-height: 42px !important;
            max-height: 42px !important;
            padding-top: 0.25rem !important;
            padding-bottom: 0.25rem !important;
        }}
        
        /* Fix paragraph inside tab buttons */
        button[kind="primary"] p, button[kind="secondary"] p {{
            margin: 0 !important;
            padding: 0 !important;
            font-size: 0.875rem !important;
            line-height: 1.2 !important;
        }}
        
        /* Columns should have same height */
        div[data-testid="column"] {{
            display: flex !important;
            flex-direction: column !important;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    # Prüfe ob Analysis bereits gestartet wurde
    if 'analysis_started' not in st.session_state:
        show_start_screen()
        return  # Stop hier - zeige nur Startbildschirm
    
    # Ab hier: Analysis-Modus (nach Start-Button)
    
    # Hole gecachte Daten aus Session State (wurden beim Start geladen!)
    guild_filter = st.session_state.selected_guild
    selected_dates = st.session_state.selected_dates

    # Zeige ausgewählte Guild, Dates und Default Player
    has_upload = 'uploaded_csv_df' in st.session_state
    data_info = f"{len(selected_dates)} CSV(s)" + (" + 1 Upload" if has_upload else "")
    
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] BEFORE: Load cached DataFrames", file=sys.stderr)

    # Lade gecachte DataFrames (wurden beim Start berechnet - KEIN Pandas mehr!)
    df_newest = st.session_state.get('df_newest_cached', None)
    df_all_dates = st.session_state.get('df_all_dates_cached', None)

    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] AFTER: Load cached DataFrames", file=sys.stderr)

    if df_newest is None or df_newest.empty or df_all_dates is None:
        st.error("❌ Error loading data!")
        if df_newest is not None and df_newest.empty:
            st.error("🚫 Access denied: This guild is not in the repository!")
            st.info("💡 Only guilds from BΛ Bataillon may use this tool.")
        if st.button("↩️ Back to selection"):
            # Keep upload - only reset analysis_started
            del st.session_state['analysis_started']
            st.rerun()
        return
    
    # Nutze gecachte Werte aus Session State (wurden beim Start berechnet!)
    player_name = st.session_state.get('player_name_cached', st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE))
    available_dates = st.session_state.get('available_dates_cached', sorted(df_all_dates['date'].unique(), reverse=True))
    date_filter = st.session_state.get('newest_date_cached', available_dates[0])
    
    # Lade Charakterdaten und Schiffsdaten für dynamische Filter
    characters_data = load_units_data()
    
    # ============================================================================
    # TAB NAVIGATION - Button-based, clean and fast!
    # ============================================================================
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Before: show_tab_menu", file=sys.stderr)
    show_tab_menu()
    
    # ============================================================================
    # SIDEBAR - Clean function with all filters and controls
    # ============================================================================
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Before: show_sidebar", file=sys.stderr)
    (compare_date, key_relevance_filter, alignment_filter, categories_filter, 
     role_filter, ability_classes_filter, filters_active) = show_sidebar(
        df_newest, guild_filter, data_info, player_name, available_dates, available_dates[1] if len(available_dates) >= 2 else available_dates[0]
    )
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] After: show_sidebar", file=sys.stderr)
    
    # Lade Charakterdaten für Tab-Content
    characters_data = load_units_data()
    relevance_dict, relic_rec_dict, notes_dict = load_character_relevance_data()
    relic_costs = load_relic_costs()
    
    # Filter anwenden für gefilterte Character-Liste
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Before: apply_filters", file=sys.stderr)
    filtered_characters = apply_filters(
        characters_data, 
        alignment_filter, 
        categories_filter, 
        role_filter, 
        ability_classes_filter,
        key_relevance_filter=key_relevance_filter,
        relevance_dict=relevance_dict,
        categories_use_and=st.session_state.get('categories_use_and', False),
        ability_classes_use_and=st.session_state.get('ability_classes_use_and', False)
    )
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] After: apply_filters", file=sys.stderr)
    
    # GLOBAL PLAYER_BASE in Session State - initialize ONCE!
    # This is the central data structure for ALL Player tabs
    # Reinitialize if guild OR ally_code changed OR player list changed (upload!)
    current_ally_code = st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE)
    current_player_count = len(df_newest['AllyCode'].unique())  # Detect new players from upload!
    
    needs_reinit = (
        'player_base_global' not in st.session_state or 
        st.session_state.get('current_guild') != guild_filter or
        st.session_state.get('current_ally_code') != current_ally_code or
        st.session_state.get('current_player_count') != current_player_count  # New players?
    )
    
    if needs_reinit:
        # Use df_newest (already filtered by Guild AND newest date, includes upload!)
        player_base = df_newest[['AllyCode', 'Name']].drop_duplicates().copy()
        player_base = player_base.sort_values('Name').reset_index(drop=True)
        
        # Add PlayerColor AND Checked status
        player_base['PlayerColor'] = [
            PLAYER_COLOR_PALETTE[i % len(PLAYER_COLOR_PALETTE)] 
            for i in range(len(player_base))
        ]
        player_base['Checked'] = False  # Default: nobody checked
        
        # Automatically check default_ally_code (from session state or fallback)
        default_ally_code = st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE)
        if default_ally_code in player_base['AllyCode'].astype(str).values:
            player_base.loc[player_base['AllyCode'].astype(str) == default_ally_code, 'Checked'] = True
        
        # Save in Session State
        st.session_state.player_base_global = player_base
        st.session_state.current_guild = guild_filter
        st.session_state.current_ally_code = current_ally_code
        st.session_state.current_player_count = current_player_count  # Track player count!
    
    # Get global player_base (shared across all tabs!)
    player_base = st.session_state.player_base_global

    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Before: TAB CONTENT RENDERING", file=sys.stderr)
    # ============================================================================
    # TAB CONTENT RENDERING
    # ============================================================================
    # CONDITIONAL RENDERING - only active tab is executed!
    # Note: active_tab was already updated before sidebar rendering
    if st.session_state.active_tab == TAB_OVERVIEW:
        show_character_overview(df_newest, filtered_characters, characters_data, filters_active, key_relevance_filter, relevance_dict, relic_rec_dict, notes_dict, relic_costs)
    elif st.session_state.active_tab == TAB_PROGRESS:
        show_progress_tab(df_all_dates, compare_date, key_relevance_filter, relevance_dict)
    elif st.session_state.active_tab == TAB_CHAR_STATS:
        show_analytics_tab(df_newest, filtered_characters, characters_data, filters_active)
    elif st.session_state.active_tab == TAB_MOD_DISTRIBUTION:
        show_mod_distribution_tab(df_newest, compare_date, key_relevance_filter, relevance_dict)
    elif st.session_state.active_tab == TAB_INFO:
        show_settings_tab(df_all_dates)
    
    # Reset player_clicked Flag für nächsten Run
    st.session_state.player_clicked = False
    
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] End: main() completed", file=sys.stderr)

if __name__ == "__main__":
    main()