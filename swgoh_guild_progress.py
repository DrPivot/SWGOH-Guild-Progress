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
    """Lädt nur ausgewählte CSVs der Gilde (mit Caching)."""
    
    # Suche nur nach CSVs dieser Guild
    pattern = f"hu_data/*{guild_filter}Full.csv"
    files = glob.glob(pattern)
    
    if not files:
        st.error(f"❌ No CSV files found for {guild_filter}!")
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
        # df_upload['guild'] = guild_filter   ### Nicht nötig, da nur Daten der gleichen Gilde hochgeladen werden können
        df_upload['date'] = upload_date if upload_date else datetime.now().strftime('%Y-%m-%d')
        
        df_final = pd.concat([df_upload, df_cached], ignore_index=True)
    else:
        df_final = df_cached
    
    return df_final

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
                        st.session_state.analysis_started = True
                        st.rerun()
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

def show_character_overview(df, filtered_characters, characters_data, filters_active, key_relevance_filter=None, relevance_dict=None, relic_rec_dict=None, notes_dict=None, relic_costs=None):
    # Falls Filter angewendet wurden, nur gefilterte Charaktere anzeigen
    if filters_active:
        if filtered_characters:
            filtered_base_ids = [char['base_id'] for char in filtered_characters]
            df_filtered = df[df['BaseId'].isin(filtered_base_ids)]
        else:
            # Filter aktiv aber keine Treffer - leere Ergebnismenge
            df_filtered = df[df['BaseId'].isin([])]  # Leerer DataFrame
    else:
        # Keine Filter aktiv - ABER Key Relevance Filter könnte aktiv sein!
        if key_relevance_filter and relevance_dict and len(key_relevance_filter) == 1:
            # Filtere auf Key oder 👎
            if '👍' in key_relevance_filter:
                key_base_ids = [base_id for base_id, is_key in relevance_dict.items() if is_key == 'yes']
                df_filtered = df[df['BaseId'].isin(key_base_ids)]
            elif '👎' in key_relevance_filter:
                other_base_ids = [base_id for base_id, is_key in relevance_dict.items() if is_key == 'no']
                df_filtered = df[df['BaseId'].isin(other_base_ids)]
            else:
                df_filtered = df
        else:
            # Keine Filter aktiv - alle anzeigen
            df_filtered = df
    
    if df_filtered.empty:
        st.warning("❌ No data found for the selected filters.")
        return
    
    # Zähle Characters und Ships für Titel
    char_count = len(df_filtered[df_filtered['CombatType'] == 'Character']['BaseId'].unique())
    ship_count = len(df_filtered[df_filtered['CombatType'] == 'Ship']['BaseId'].unique())
    
    # Erstelle Titel mit Anzahl
    title_parts = []
    if char_count > 0:
        title_parts.append(f"{char_count} char{'s' if char_count != 1 else ''}")
    if ship_count > 0:
        title_parts.append(f"{ship_count} ship{'s' if ship_count != 1 else ''}")
    
    if title_parts:
        count_text = " & ".join(title_parts)
        title = f'<h3 id="character-overview" style="margin-top: -12px; margin-bottom: 0;">📋 Character Overview ({count_text})</h3>'
    else:
        title = '<h3 id="character-overview" style="margin-top: -12px; margin-bottom: 0;">📋 Character Overview (0 rows)</h3>'
    
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
            lambda x: sum(x == 9),    # R9
            lambda x: sum(x == 8),    # R8  
            lambda x: sum(x == 7),    # R7
            lambda x: sum(x == 6),    # R6
            lambda x: sum(x < 6),     # <R6
            'count'                   # Total count
        ]
    }).round(0)  # Keine Nachkommastellen
    
    # Spalten strukturieren - alle als Integer
    # Einmal base_ids auslesen statt mehrfach iterieren
    base_ids = char_stats.index.tolist()
    
    char_overview = pd.DataFrame({
        'Character': [base_id_to_name.get(base_id, base_id) for base_id in base_ids],
        'Player relic level': [player_relic_dict.get(base_id, None) for base_id in base_ids],
        'Recommended level': [relic_rec_dict.get(base_id, None) if relic_rec_dict else None for base_id in base_ids],
        'Δ': [
            (rec - player if rec and player and rec > player else 0)
            for rec, player in zip(
                [relic_rec_dict.get(base_id, None) if relic_rec_dict else None for base_id in base_ids],
                [player_relic_dict.get(base_id, None) for base_id in base_ids]
            )
        ],
        'Comment': [notes_dict.get(base_id, None) if notes_dict else None for base_id in base_ids],
        'Count': char_stats['RelicLevel']['count'].astype(int),
        'R9': char_stats['RelicLevel']['<lambda_0>'].astype(int),
        'R8': char_stats['RelicLevel']['<lambda_1>'].astype(int), 
        'R7': char_stats['RelicLevel']['<lambda_2>'].astype(int),
        'R6': char_stats['RelicLevel']['<lambda_3>'].astype(int),
        '<R6': char_stats['RelicLevel']['<lambda_4>'].astype(int)
    })
    
    # Sortierung? Aplhabetisch nach Character (wie übergeben) oder nach irgendeiner Spalte? => tbd
    # char_overview = char_overview.sort_values('xxx', ascending=False)
    
    # Berechne Relic-Kosten (vor reset_index, da BaseId noch im Index ist!)
    if relic_costs:
        total_costs = calculate_total_relic_costs(char_overview, player_relic_dict, relic_rec_dict, relic_costs)
    else:
        total_costs = None
    
    # Index zurücksetzen um BaseId zu entfernen
    char_overview = char_overview.reset_index(drop=True)
    
    # Zwei-Spalten-Layout: Character Overview (links) + Relic Costs (rechts)
    col_chars, col_costs = st.columns([2, 2], gap="medium")
    
    with col_chars:
        # Tabelle anzeigen mit kleiner Zeilenhöhe für mehr sichtbare Zeilen
        # row_height=21 ermöglicht ca. 50 Zeilen bei 1140px Container-Höhe
        st.dataframe(char_overview, hide_index=True, width="content", height=1100, row_height=21)
    
    with col_costs:
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
        st.warning("❌ No characters available.")
        return
    
    # Character for Tab 2 from Session State
    selected_character_name = st.session_state.selected_character_tab2
    selected_base_id = next((base_id for name, base_id in available_characters if name == selected_character_name), None)
    
    if not selected_base_id:
        st.warning("❌ No valid character selected.")
        return
    
    # Filter data for the selected character
    df_character = df[df['BaseId'] == selected_base_id].copy()
    
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
        st.warning("⚠️ Please select at least one relic level.")
        return
    
    # Calculate player_overview (df_guild is already filtered!)
    player_base_minimal = player_base[['AllyCode', 'Name']].copy()
    player_overview, date_columns, available_dates = calculate_player_relic_overview(
        df_guild, player_base_minimal, relic_levels, compare_date
    )
    
    if len(available_dates) < 2:
        st.warning("⚠️ At least 2 data snapshots required for comparison.")
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
    
    # Column configuration - NO checkbox column!
    column_config = {
        'Name': st.column_config.TextColumn('Player Name', width=175),
        'AllyCode': st.column_config.TextColumn('AllyCode', width=120),
        'Δ': st.column_config.NumberColumn(
            'Δ',
            help='Change since last data snapshot (only for players in both CSVs)',
            format='%+d',
            width=80
        ),
        'Metric': st.column_config.TextColumn('Metric', width=110)
    }
    
    # Date columns as numbers (mark comparison date with 📍)
    for col in date_columns:
        label = f"📍 {col}" if col == compare_date else col
        column_config[col] = st.column_config.NumberColumn(label, format='%d', width=120)
    
    # on_select Callback for Cell-Selection
    def on_relics_select():
        """Callback when player cell is selected - toggle the player of the row."""
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
        st.warning("⚠️ Please select at least one omicron type.")
        return
    
    # Calculate player_overview (df_guild is already filtered!)
    player_base_minimal = player_base[['AllyCode', 'Name']].copy()
    player_overview, date_columns, available_dates = calculate_player_omicron_overview(
        df_guild, player_base_minimal, omicron_columns, compare_date
    )
    
    if len(available_dates) < 2:
        st.warning("⚠️ At least 2 data snapshots required for comparison.")
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
    
    # Datums-Spalten als Zahlen (Vergleichsdatum mit 📍 markieren)
    for col in date_columns:
        label = f"📍 {col}" if col == compare_date else col
        column_config[col] = st.column_config.NumberColumn(label, format='%d', width=120)
    
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
        st.warning("⚠️ Please select at least one speed threshold.")
        return
    
    # Calculate player_overview (df_guild is already filtered!)
    player_base_minimal = player_base[['AllyCode', 'Name']].copy()
    player_overview, date_columns, available_dates = calculate_player_speed_mod_overview(
        df_guild, player_base_minimal, speed_columns, compare_date
    )
    
    if len(available_dates) < 2:
        st.warning("⚠️ At least 2 data snapshots required for comparison.")
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
    
    # Datums-Spalten als Zahlen (Vergleichsdatum mit 📍 markieren)
    for col in date_columns:
        label = f"📍 {col}" if col == compare_date else col
        column_config[col] = st.column_config.NumberColumn(label, format='%d', width=120)
       
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
    st.markdown('<h3 style="margin-top: -12px; margin-bottom: 0;">🎨 UI Settings</h3>', unsafe_allow_html=True)
    
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

    # Zeige ausgewählte Guild, Dates und Default Player
    has_upload = 'uploaded_csv_df' in st.session_state
    data_info = f"{len(selected_dates)} CSV(s)" + (" + 1 Upload" if has_upload else "")
    
    # Bereite Upload-Daten für Cache vor (falls vorhanden)
    upload_csv_data = None
    upload_date = None
    upload_guild = None
    if has_upload:
        # Nutze bereits gespeicherten CSV-String (wurde beim Upload erstellt!)
        upload_csv_data = st.session_state.get('uploaded_csv_data', None)
        upload_date = st.session_state.get('uploaded_csv_date', datetime.now().strftime('%Y-%m-%d'))
        upload_guild = st.session_state.get('uploaded_csv_guild', None)
    
    # Load data (CACHED - Upload stored in cache!)
    df = get_final_df(guild_filter, tuple(selected_dates), upload_csv_data, upload_date, upload_guild)

    if df is None or df.empty:
        st.error("❌ Error loading data!")
        if df is not None and df.empty:
            st.error("🚫 Access denied: This guild is not in the repository!")
            st.info("💡 Only guilds from BΛ Bataillon may use this tool.")
        if st.button("↩️ Back to selection"):
            # Keep upload - only reset analysis_started
            del st.session_state['analysis_started']
            st.rerun()
        return
    
    # Get player name for sidebar info (need to lookup from df before player_base_global exists)
    default_ally_code = st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE)
    available_dates_temp = sorted(df['date'].unique(), reverse=True)
    df_newest_temp = df[df['date'] == available_dates_temp[0]]
    player_name_match = df_newest_temp[df_newest_temp['AllyCode'].astype(str) == default_ally_code]['Name'].unique()
    player_name = player_name_match[0] if len(player_name_match) > 0 else default_ally_code
    
    # Update sidebar info with player name
    st.sidebar.markdown(f"**Guild:** {guild_filter}  \n**Data:** {data_info}  \n**Player:** {player_name}")
    
    # Button to go back to selection
    if st.sidebar.button("↩️ New Selection"):
        # Clear ONLY analysis_started - keep upload!
        del st.session_state['analysis_started']
        st.rerun()
        
    # Seitenleiste für Filter
        
    # Verfügbare Daten aus geladenen CSVs
    available_dates = sorted(df['date'].unique(), reverse=True)
    date_filter = available_dates[0]  # Neuestes Datum
    
    # Date for delta comparison
    default_compare_index = 1 if len(available_dates) >= 2 else 0
    compare_date = st.sidebar.selectbox(
        "Date for Delta Comparison:", 
        available_dates, 
        index=default_compare_index,
        key="compare_date_select"
    )
    
    # Filtere DataFrame nach Date (Guild ist bereits gefiltert durch get_final_df!)
    df_filtered = df[df['date'] == date_filter]
    
    if df_filtered.empty:
        st.error("❌ No data found for the selected date.")
        return
    
    # Lade Charakterdaten und Schiffsdaten für dynamische Filter
    characters_data = load_units_data()
    
    # Dynamic filters with mutual influence
    st.sidebar.markdown("---")  # Separator line
    st.sidebar.markdown("**🎛️ Character Filter:**")
    
    # Initialize session state for filters
    if 'combat_type_filter' not in st.session_state:
        st.session_state.combat_type_filter = ['Character']
    if 'key_relevance_filter' not in st.session_state:
        st.session_state.key_relevance_filter = ['👍']  # Default: only Key Characters
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
    
    # Unique keys based on reset counter
    reset_suffix = f"_{st.session_state.filter_reset_counter}"
    
    # CombatType Filter + Key Relevance Filter in one line
    available_combat_types = sorted(df_filtered['CombatType'].unique())
    
    col1, col2 = st.sidebar.columns([3, 2])
    with col1:
        # Segmented Control für CombatType
        combat_type_filter = st.segmented_control(
            "Combat Type",
            options=available_combat_types,
            default=st.session_state.get('combat_type_filter', ['Character']),
            key=f"combat_type_segmented{reset_suffix}",
            selection_mode="multi",
            label_visibility="collapsed"
        )
        # Update session state only if value has changed
        if combat_type_filter != st.session_state.get('combat_type_filter', ['Character']):
            st.session_state.combat_type_filter = combat_type_filter
    
    with col2:
        # Key Relevance Segmented Control (multi-select)
        key_relevance_filter = st.segmented_control(
            "Key Relevance",
            options=['👍', '👎'],
            default=st.session_state.get('key_relevance_filter', ['👍']),
            key=f"key_relevance_segmented{reset_suffix}",
            selection_mode="multi",
            label_visibility="collapsed"
        )
        # Update session state only if value has changed
        if key_relevance_filter != st.session_state.get('key_relevance_filter', ['👍']):
            st.session_state.key_relevance_filter = key_relevance_filter
    
    # Filter DataFrame by CombatType
    if combat_type_filter:
        df_filtered = df_filtered[df_filtered['CombatType'].isin(combat_type_filter)]
    
    # Filter characters_data to BaseIds that exist in current df_filtered
    # This ensures only relevant options (e.g., only Ships) are shown in filters
    available_base_ids = set(df_filtered['BaseId'].unique())
    characters_data_filtered = [char for char in characters_data if char.get('base_id') in available_base_ids]
    
    # Collect all available options (only from units present in DataFrame)
    all_alignments = sorted(list({char.get('alignment', '') for char in characters_data_filtered if char.get('alignment')}))
    
    # Alignment Filter (Segmented Control)
    alignment_filter = st.sidebar.segmented_control(
        "Alignment",
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
    
    # Role Filter (Segmented Control) - now before Category
    role_filter = st.sidebar.segmented_control(
        "Role",
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
    # Label + Checkbox in zwei Spalten
    col_cat_label, col_cat_toggle = st.sidebar.columns([2, 2])
    with col_cat_label:
        st.markdown("**Categories:**")
    with col_cat_toggle:
        # Checkbox-Label dynamisch setzen basierend auf aktuellem Zustand
        current_state = st.session_state.get('categories_use_and', False)
        categories_use_and = st.checkbox(
            "AND" if current_state else "OR",
            value=current_state,
            key=f"categories_and_toggle{reset_suffix}",
            help="Checked: AND logic (all selected). Unchecked: OR logic (any selected)"
        )
        # Update session state und force rerun wenn geändert
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
    # Label + Checkbox in zwei Spalten
    col_ac_label, col_ac_toggle = st.sidebar.columns([2, 2])
    with col_ac_label:
        st.markdown("**Ability classes:**")
    with col_ac_toggle:
        # Checkbox-Label dynamisch setzen basierend auf aktuellem Zustand
        current_state = st.session_state.get('ability_classes_use_and', False)
        ability_classes_use_and = st.checkbox(
            "AND" if current_state else "OR",
            value=current_state,
            key=f"ability_classes_and_toggle{reset_suffix}",
            help="Checked: AND logic (all selected). Unchecked: OR logic (any selected)"
        )
        # Update session state und force rerun wenn geändert
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
    # Update session state nur wenn sich Wert geändert hat
    if ability_classes_filter != st.session_state.get('ability_classes_filter', []):
        st.session_state.ability_classes_filter = ability_classes_filter
    
    # Reset filters button
    if st.sidebar.button("🗑️ Reset all filters"):
        # Increase reset counter for new widget keys
        st.session_state.filter_reset_counter += 1
        # Reset session state - Sidebar filters AND selected_character_tab2
        # IMPORTANT: key_chars_filter is NOT reset!
        st.session_state.combat_type_filter = []
        st.session_state.alignment_filter = []
        st.session_state.categories_filter = []
        st.session_state.categories_use_and = False
        st.session_state.role_filter = []
        st.session_state.ability_classes_filter = []
        st.session_state.ability_classes_use_and = False
        # Delete selected_character_tab2 so it gets reinitialized
        if 'selected_character_tab2' in st.session_state:
            del st.session_state.selected_character_tab2
        st.rerun()
    
    # Lade character_relevance_data
    relevance_dict, relic_rec_dict, notes_dict = load_character_relevance_data()
    
    # Lade relic_costs
    relic_costs = load_relic_costs()
    
    # Filter anwenden
    filtered_characters = apply_filters(
        characters_data, 
        alignment_filter, 
        categories_filter, 
        role_filter, 
        ability_classes_filter,
        key_relevance_filter=st.session_state.key_relevance_filter,
        relevance_dict=relevance_dict,
        categories_use_and=st.session_state.get('categories_use_and', False),
        ability_classes_use_and=st.session_state.get('ability_classes_use_and', False)
    )
    
    # Prüfe ob irgendwelche Filter aktiv sind (key_chars_filter wird NICHT als "Filter aktiv" gezählt)
    filters_active = bool(alignment_filter or categories_filter or role_filter or ability_classes_filter)
    
    st.sidebar.markdown("---")  # Separator line
    
    # Character Filter for Tab 2
    st.sidebar.markdown("**☯ Character Selection:**")
    if filters_active:
        if filtered_characters:
            available_characters_tab2 = [(char['name'], char['base_id']) for char in filtered_characters]
        else:
            available_characters_tab2 = []  # Filter active but no matches
    else:
        available_characters_tab2 = [(char['name'], char['base_id']) for char in characters_data]
    
    character_names_tab2 = [name for name, base_id in available_characters_tab2]
    
    if character_names_tab2:
        # Character Dropdown for Tab 2 - Key with reset_suffix so it gets reset
        selected_character_tab2 = st.sidebar.selectbox(
            "Character for Tab 2:",
            character_names_tab2,
            key=f"tab2_character_select{reset_suffix}"
        )
        
        # Update Session State
        if 'selected_character_tab2' not in st.session_state:
            st.session_state.selected_character_tab2 = selected_character_tab2
        else:
            if st.session_state.selected_character_tab2 != selected_character_tab2:
                st.session_state.selected_character_tab2 = selected_character_tab2
    
    # Player Uncheck Button at end of Sidebar
    st.sidebar.markdown("---")
    if st.sidebar.button("❌ Uncheck All", key="uncheck_all_btn", width='stretch'):
        if 'player_base_global' in st.session_state:
            # Get default_ally_code from session state
            default_ally_code = st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE)
            
            # Uncheck all EXCEPT default_ally_code
            st.session_state.player_base_global['Checked'] = (
                st.session_state.player_base_global['AllyCode'].astype(str) == default_ally_code
            )
            st.rerun()
    
    # GLOBAL PLAYER_BASE in Session State - initialize ONCE!
    # This is the central data structure for ALL Player tabs
    # Reinitialize if guild OR ally_code changed
    current_ally_code = st.session_state.get('default_ally_code', DEFAULT_ALLY_CODE)
    needs_reinit = (
        'player_base_global' not in st.session_state or 
        st.session_state.get('current_guild') != guild_filter or
        st.session_state.get('current_ally_code') != current_ally_code
    )
    
    if needs_reinit:
        # Use df (already filtered by Guild!)
        available_dates_list = sorted(df['date'].unique(), reverse=True)
        newest_date = available_dates_list[0]
        df_newest = df[df['date'] == newest_date]
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
    
    # Get global player_base (shared across all tabs!)
    player_base = st.session_state.player_base_global
    
    # Tab Navigation with Segmented Control - ONLY active tab is rendered!
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
    
    # CONDITIONAL RENDERING - only active tab is executed!
    if selected_tab == "📋 Character Overview":
        show_character_overview(df_filtered, filtered_characters, characters_data, filters_active, st.session_state.key_relevance_filter, relevance_dict, relic_rec_dict, notes_dict, relic_costs)
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