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
    """Gibt alle verfügbaren Daten für eine Guild zurück."""
    pattern = f"hu_data/*{guild_name}Full.csv"
    files = glob.glob(pattern)
    
    dates_info = []
    for file in files:
        filename = os.path.basename(file)
        match = re.match(r'(\d{4}-\d{2}-\d{2})\s+.+?Full\.csv', filename)
        if match:
            date_str = match.group(1)
            dates_info.append({'Datum': date_str})
    
    # Sortiere nach Datum (neueste zuerst)
    dates_df = pd.DataFrame(dates_info)
    if not dates_df.empty:
        dates_df = dates_df.sort_values('Datum', ascending=False)
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

def get_final_df(guild_filter, selected_dates):
    """Kombiniert gecachte Daten + optionalen Upload."""
    # Lade gecachte CSVs
    df_cached = load_guild_data(guild_filter, tuple(selected_dates))
    
    if df_cached is None:
        return None
    
    # Füge Upload hinzu (falls vorhanden)
    if 'uploaded_csv_df' in st.session_state:
        df_upload = st.session_state.uploaded_csv_df.copy()
        df_upload['guild'] = guild_filter
        df_upload['date'] = datetime.now().strftime('%Y-%m-%d')
        
        # Kombiniere beide
        df_final = pd.concat([df_upload, df_cached], ignore_index=True)
        st.sidebar.success(f"✅ Upload ({len(df_upload)} Zeilen) hinzugefügt!")
    else:
        df_final = df_cached
    
    return df_final

def show_start_screen():
    """Zeigt Startbildschirm mit Guild-Auswahl, Date-Auswahl und CSV-Upload."""
    
    # Optional: Logo/Header-Image
    st.image("assets/bataillon_logo.png", width=400)  # Uncomment wenn du ein Logo hast
    
    st.title("🎮 SWGOH Guild Progress")
    st.markdown("---")
    
    # Schritt 1: Guild auswählen
    st.subheader("📋 Schritt 1: Wähle deine Gilde")
    
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
        on_select=lambda: None,  # Callback kommt unten
        key="guild_selection",
        use_container_width=True
    )
    
    # Extrahiere ausgewählte Guild
    selected_guild_rows = guild_selection.selection.rows if hasattr(guild_selection, 'selection') else []
    
    if selected_guild_rows:
        selected_guild_idx = selected_guild_rows[0]
        selected_guild = guilds_df.iloc[selected_guild_idx]['Guild Name']
        st.session_state.selected_guild = selected_guild
    
    st.markdown("---")
    
    # Schritt 2: Dates auswählen (nur wenn Guild gewählt)
    if 'selected_guild' in st.session_state:
        st.subheader(f"📅 Schritt 2: Wähle Daten für {st.session_state.selected_guild}")
        
        dates_df = get_dates_for_guild(st.session_state.selected_guild)
        
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
                use_container_width=True
            )
            
            # Extrahiere ausgewählte Dates
            selected_date_rows = dates_selection.selection.rows if hasattr(dates_selection, 'selection') else []
            
            if selected_date_rows:
                selected_dates = [dates_df.iloc[idx]['Datum'] for idx in selected_date_rows]
                st.session_state.selected_dates = selected_dates
                st.info(f"✅ {len(selected_dates)} Datum/Daten ausgewählt")
            
            st.markdown("---")
            
            # Schritt 3: Optional CSV hochladen
            st.subheader("📤 Schritt 3: Neue CSV hochladen (optional)")
            
            uploaded_file = st.file_uploader(
                "Neue CSV-Datei hochladen",
                type=['csv'],
                help="Optional: Lade eine neue CSV hoch (wird als neuestes Datum behandelt)"
            )
            
            if uploaded_file is not None:
                try:
                    df_upload = pd.read_csv(uploaded_file)
                    st.session_state.uploaded_csv_df = df_upload
                    st.success(f"✅ {len(df_upload)} Zeilen hochgeladen! (Datum: heute)")
                except Exception as e:
                    st.error(f"❌ Fehler beim Laden der CSV: {e}")
            
            st.markdown("---")
            
            # Schritt 4: Start-Button
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("▶️ Start Analysis", type="primary", use_container_width=True):
                    if 'selected_dates' in st.session_state and st.session_state.selected_dates:
                        st.session_state.analysis_started = True
                        st.rerun()
                    else:
                        st.warning("⚠️ Bitte mindestens ein Datum auswählen!")
    else:
        st.info("👆 Bitte zuerst eine Gilde auswählen")

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
    st.subheader("📊 Character Overview")
    
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
    # row_height=22 ermöglicht ca. 50 Zeilen bei 1140px Container-Höhe
    st.dataframe(char_overview, hide_index=True, width="stretch", height=1140, row_height=22)

def show_analytics_tab(df, filtered_characters, characters_data, filters_active, selected_player):
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
    
    st.subheader(f"📊 Character Stats für {selected_character_name}")
    
    # Alle Stats aus der Tabelle für Diagramme (CritChance vor CritDamage)
    stats_columns = ['Speed', 'Health', 'Protection', 'Armor', 'Damage', 'CritChance', 'CritDamage', 'Potency', 'Tenacity', 'RelicLevel']
    
    # Hilfsfunktion: Farbe für Spieler ermitteln - nutzt player_base['Checked']
    def get_player_color(player_name):
        """Gibt Farbe für Spieler zurück: Checked = feste Farbe aus player_base, sonst dunkelgrau."""
        # Prüfe in player_base ob gecheckt
        is_checked = player_base.loc[player_base['Name'] == player_name, 'Checked'].iloc[0] if player_name in player_base['Name'].values else False
        if is_checked:
            color = player_base.loc[player_base['Name'] == player_name, 'PlayerColor'].iloc[0]
            return color
        else:
            return "#222222"  # Sehr dunkles Grau für unchecked
    
    # Hilfsfunktion: Hex zu RGBA mit Transparenz
    def hex_to_rgba(hex_color, opacity=0.6):
        """Konvertiert Hex-Farbe zu RGBA mit Transparenz."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f'rgba({r},{g},{b},{opacity})'
    
    # Diagramme in einem Container mit fester Breite (Player: 168px + 32 für row-select + 10*180 = 1975px)
    with st.container(width=2000, gap=None):
        
        # Diagramme nebeneinander anzeigen - wie gewünscht!
        
        # Charts mit perfekter Ausrichtung anzeigen (jetzt 10 Stats)
        # KEINE Checkbox-Spalte mehr! Nur Player: 168px + 32 für row-select
        chart_cols = st.columns([200] + [180] * 10, gap=None)
        
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
            
            # Farben für Balken: Checked players = gedämpfte RGBA-Farbe, andere = dunkelgrau
            # Prüfe für jeden Spieler ob in player_base['Checked'] == True
            colors = []
            for name in stat_data['Name']:
                is_checked = player_base.loc[player_base['Name'] == name, 'Checked'].iloc[0] if name in player_base['Name'].values else False
                if is_checked:
                    # Checked: RGBA-Farbe
                    color = player_base.loc[player_base['Name'] == name, 'PlayerColor'].iloc[0]
                    colors.append(hex_to_rgba(color, 0.6))
                else:
                    # Unchecked: dunkelgrau
                    colors.append(get_player_color(name))
            
            # Hover-Text erstellen: Name + Wert
            hover_texts = [
                f"{row['Name']}<br>{stat}: {row[stat]:.0f}"
                for _, row in stat_data.iterrows()
            ]
            
            # Chart erstellen mit plotly - exakt 180px Breite
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
                width=180,  # Chart-Breite: 180px
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
    
    # Spalten-Konfiguration: 32px für row-select + Player (168px) + Stats mit Prozenten wo nötig
    column_config = {
        'Player': st.column_config.TextColumn(width=168)
    }
    
    for col in display_df_clean.columns:
        if col != 'Player':
            if col in percent_columns:
                # Prozent-Spalten
                column_config[col] = st.column_config.NumberColumn(width=180, format="%.1f %%")
            else:
                # Normale Zahlen
                column_config[col] = st.column_config.NumberColumn(width=180, format="%.0f")
    
    # on_select Callback für Row-Selection
    def on_player_select():
        """Callback wenn Spieler ausgewählt/abgewählt wird - toggle nur die geklickten Rows."""
        print(f"\n[ON_SELECT CALLBACK] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
        
        # Hole Selection-Event
        selection = st.session_state.player_comparison_table_selection
        selected_rows = selection.get('selection', {}).get('rows', [])
        
        print(f"[ON_SELECT] Selected rows: {selected_rows}", file=sys.stderr)
        
        # Toggle nur die selected rows (User-Click = Toggle!)
        for row_idx in selected_rows:
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
        
        print(f"[ON_SELECT CALLBACK END] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width=2000,
        column_config=column_config,
        height=900,
        row_height=22,
        selection_mode="single-row",
        on_select=on_player_select,
        key="player_comparison_table_selection"
    )

@st.cache_data
def get_guild_filtered_data(df_all, guild_filter):
    """
    Filtert Daten für eine spezifische Gilde (mit Caching).
    Wird von allen Usern derselben Gilde geteilt.
    
    Args:
        df_all: Kompletter DataFrame mit allen Guilds und Daten
        guild_filter: Ausgewählte Gilde
    
    Returns:
        DataFrame: Gefilterte Daten nur für diese Gilde
    """
    return df_all[df_all['guild'] == guild_filter]

@st.cache_data
def get_player_base_data(df_guild, guild_filter, available_dates_per_guild):
    """
    Bereitet gemeinsame Basis-Daten für Player-Tabs vor (MIT Caching, pro Guild).
    Verwendet bereits gecachte df_guild und available_dates.
    
    Args:
        df_guild: Gefilterte Daten für diese Gilde (aus Cache)
        guild_filter: Name der Gilde (für Cache-Key)
        available_dates_per_guild: Dict mit Dates pro Guild (gecacht aus load_guild_data)
    
    Returns:
        Tuple: (available_dates, newest_date, player_base)
        - available_dates: Sortierte Liste aller Daten (neueste zuerst) - aus gecachtem Dict!
        - newest_date: Neustes verfügbares Datum
        - player_base: DataFrame mit [AllyCode, Name] aus neuester CSV (OHNE PlayerColor)
    """
    # Hole Dates aus gecachtem Dict (bereits sortiert, neueste zuerst!)
    available_dates = available_dates_per_guild[guild_filter]
    newest_date = available_dates[0]  # Erstes Element = neuestes Datum
    
    # Spielerliste aus neuestem Datum
    df_newest = df_guild[df_guild['date'] == newest_date]
    player_base = df_newest[['AllyCode', 'Name']].drop_duplicates().copy()
    
    # Spieler alphabetisch sortieren für konsistente Reihenfolge
    player_base = player_base.sort_values('Name').reset_index(drop=True)
    
    return available_dates, newest_date, player_base

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
                # Spieler nicht in diesem Datum - 0 Counts
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    'R10': 0, 'R9': 0, 'R8': 0, 'R7': 0, 'R6': 0
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
        print(f"[CALCULATE RELIC:] SKIPPED - recalculate=False", file=sys.stderr)
        # Hole gecachtes Ergebnis aus Session State
        if 'player_overview_relics' in st.session_state:
            # Dummy return - wird nicht verwendet, da player_overview bereits in Session State
            return st.session_state.player_overview_relics, [], []
    
    print(f"[CALCULATE RELIC:] len(player_base) = {len(player_base)}", file=sys.stderr)
    print(f"[CALCULATE RELIC END] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    
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
        
        # Summiere nur die gewählten Relic-Levels
        df_date_counts['RelicCount'] = df_date_counts[relic_cols].sum(axis=1)
        
        col_name = date
        date_columns.append(col_name)
        
        player_overview = player_overview.merge(
            df_date_counts[['AllyCode', 'RelicCount']],
            on='AllyCode',
            how='left'
        )
        player_overview = player_overview.rename(columns={'RelicCount': col_name})
        
        if i == 0:
            player_overview[col_name] = player_overview[col_name].fillna(0).astype(int)
        else:
            player_overview[col_name] = player_overview[col_name].astype('Int64')
    
    # Berechne Delta
    if compare_date in available_dates and compare_date != newest_date:
        compare_col = compare_date
        player_overview['Δ'] = player_overview.apply(
            lambda row: row[date_columns[0]] - row[compare_col] 
            if pd.notna(row[compare_col]) else None,
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
                # Spieler nicht in diesem Datum - 0 Counts
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    **{col: 0 for col in omicron_cols}
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
        print(f"[CALCULATE OMIS:] SKIPPED - recalculate=False", file=sys.stderr)
        if 'player_overview_omicrons' in st.session_state:
            return st.session_state.player_overview_omicrons, [], []
    
    print(f"[CALCULATE OMIS:] len(player_base) = {len(player_base)}", file=sys.stderr)
    print(f"[CALCULATE OMIS END] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    
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
        
        # Summiere nur die gewählten Omicron-Typen
        df_date_counts['OmicronCount'] = df_date_counts[omicron_columns].sum(axis=1)
        
        col_name = date
        date_columns.append(col_name)
        
        player_overview = player_overview.merge(
            df_date_counts[['AllyCode', 'OmicronCount']],
            on='AllyCode',
            how='left'
        )
        player_overview = player_overview.rename(columns={'OmicronCount': col_name})
        
        if i == 0:
            player_overview[col_name] = player_overview[col_name].fillna(0).astype(int)
        else:
            player_overview[col_name] = player_overview[col_name].astype('Int64')
    
    # Berechne Delta
    if compare_date in available_dates and compare_date != newest_date:
        compare_col = compare_date
        player_overview['Δ'] = player_overview.apply(
            lambda row: row[date_columns[0]] - row[compare_col] 
            if pd.notna(row[compare_col]) else None,
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

    print(f"[get mods:] len(player_base) = {len(player_base)}", file=sys.stderr)
    
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
                # Spieler nicht in diesem Datum - 0 Counts
                counts = {
                    'AllyCode': ally_code,
                    'Name': player_name,
                    **{col: 0 for col in speed_cols}
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
        print(f"[CALCULATE MODS:] SKIPPED - recalculate=False", file=sys.stderr)
        if 'player_overview_speed_mods' in st.session_state:
            return st.session_state.player_overview_speed_mods, [], []
    
    print(f"[CALCULATE MODS:] len(player_base) = {len(player_base)}", file=sys.stderr)
    print(f"[CALCULATE MODS END] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    
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
        
        # Summiere nur die gewählten Speed-Thresholds
        df_date_counts['SpeedModCount'] = df_date_counts[speed_columns].sum(axis=1)
        
        col_name = date
        date_columns.append(col_name)
        
        player_overview = player_overview.merge(
            df_date_counts[['AllyCode', 'SpeedModCount']],
            on='AllyCode',
            how='left'
        )
        player_overview = player_overview.rename(columns={'SpeedModCount': col_name})
        
        if i == 0:
            player_overview[col_name] = player_overview[col_name].fillna(0).astype(int)
        else:
            player_overview[col_name] = player_overview[col_name].astype('Int64')
    
    # Berechne Delta
    if compare_date in available_dates and compare_date != newest_date:
        compare_col = compare_date
        player_overview['Δ'] = player_overview.apply(
            lambda row: row[date_columns[0]] - row[compare_col] 
            if pd.notna(row[compare_col]) else None,
            axis=1
        )
    else:
        player_overview['Δ'] = None
    
    return player_overview, date_columns, available_dates

def show_player_overview_tab(df_all, guild_filter, selected_player, compare_date):
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
            st.subheader("🏆 Player Relics")
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
    
    # Berechne player_overview
    df_guild = get_guild_filtered_data(df_all, guild_filter)
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
    
    # on_select Callback für Row-Selection
    def on_relics_select():
        """Callback wenn Spieler ausgewählt/abgewählt wird - toggle nur die geklickten Rows."""
        print(f"\n[RELICS ON_SELECT] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
        
        # Hole Selection-Event
        selection = st.session_state.player_relics_table_selection
        selected_rows = selection.get('selection', {}).get('rows', [])
        
        print(f"[RELICS] Selected rows: {selected_rows}", file=sys.stderr)
        
        # Toggle nur die selected rows (User-Click = Toggle!)
        for row_idx in selected_rows:
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
        
        print(f"[RELICS ON_SELECT END] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width="content",
        height=1140,
        row_height=22,
        column_config=column_config,
        selection_mode="single-row",
        on_select=on_relics_select,
        key="player_relics_table_selection"
    )


def show_player_omicrons_tab(df_all, guild_filter, selected_player, compare_date):
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
            st.subheader("🏆 Player Omicrons")
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
    
    # Berechne player_overview
    df_guild = get_guild_filtered_data(df_all, guild_filter)
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
    
    # on_select Callback für Row-Selection
    def on_omicrons_select():
        """Callback wenn Spieler ausgewählt/abgewählt wird - toggle nur die geklickten Rows."""
        print(f"\n[OMICRONS ON_SELECT] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
        
        # Hole Selection-Event
        selection = st.session_state.player_omicrons_table_selection
        selected_rows = selection.get('selection', {}).get('rows', [])
        
        print(f"[OMICRONS] Selected rows: {selected_rows}", file=sys.stderr)
        
        # Toggle nur die selected rows (User-Click = Toggle!)
        for row_idx in selected_rows:
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
        
        print(f"[OMICRONS ON_SELECT END] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width="content",
        height=1140,
        row_height=22,
        column_config=column_config,
        selection_mode="single-row",
        on_select=on_omicrons_select,
        key="player_omicrons_table_selection"
    )


def show_player_speed_mods_tab(df_all, guild_filter, selected_player, compare_date):
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
            st.subheader("⚡ Player Speed Mods")
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
    
    # Berechne player_overview
    df_guild = get_guild_filtered_data(df_all, guild_filter)
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
    
    # on_select Callback für Row-Selection
    def on_speed_mods_select():
        """Callback wenn Spieler ausgewählt/abgewählt wird."""
        print(f"\n[SPEED MODS ON_SELECT] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
        
        # Hole Selection-Event
        selection = st.session_state.player_speed_mods_table_selection
        selected_rows = selection.get('selection', {}).get('rows', [])
        
        print(f"[SPEED MODS] Selected rows: {selected_rows}", file=sys.stderr)
        
    # on_select Callback für Row-Selection
    def on_speed_mods_select():
        """Callback wenn Spieler ausgewählt/abgewählt wird - toggle nur die geklickten Rows."""
        print(f"\n[SPEED MODS ON_SELECT] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
        
        # Hole Selection-Event
        selection = st.session_state.player_speed_mods_table_selection
        selected_rows = selection.get('selection', {}).get('rows', [])
        
        print(f"[SPEED MODS] Selected rows: {selected_rows}", file=sys.stderr)
        
        # Toggle nur die selected rows (User-Click = Toggle!)
        for row_idx in selected_rows:
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
        
        print(f"[SPEED MODS ON_SELECT END] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    
    # Tabelle mit on_select
    st.dataframe(
        styled_df,
        hide_index=True,
        width="content",
        height=1140,
        row_height=22,
        column_config=column_config,
        selection_mode="single-row",
        on_select=on_speed_mods_select,
        key="player_speed_mods_table_selection"
    )


def show_settings_tab(df):
    """Tab 6 - Settings & Data Management."""
    st.header("⚙️ Settings")
    
    # UI Settings
    st.subheader("🎨 UI Einstellungen")
    
    # Toggle für Streamlit Header (Deploy-Button, Clear Cache)
    if 'show_header' not in st.session_state:
        st.session_state.show_header = False
    
    show_header = st.toggle(
        "Streamlit Menü anzeigen (Deploy, Clear Cache)",
        value=st.session_state.show_header,
        help="Blendet das Streamlit-Menü oben rechts ein/aus"
    )
    
    if show_header != st.session_state.show_header:
        st.session_state.show_header = show_header
        st.rerun()
    
    st.divider()
    
    st.subheader("📥 Update Character Data")
    
    # Zeige aktuelles Datum der characters.json
    characters_file = 'data/characters.json'
    if os.path.exists(characters_file):
        mod_time = os.path.getmtime(characters_file)
        mod_date = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        st.info(f"**Aktuelle Version:** {mod_date}")
    else:
        st.warning("⚠️ characters.json nicht gefunden!")
    
    st.markdown("""
    **So aktualisierst du die Charakterdaten:**
    1. Öffne im Browser: [https://swgoh.gg/api/characters/](https://swgoh.gg/api/characters/)
    2. Rechtsklick → "Seite speichern unter" → als `characters.json` speichern
    3. Datei unten hochladen
    
    **Wann nutzen?**
    - Nach Release neuer Characters
    - Einmal pro Monat zur Sicherheit
    - Wenn neue Categories/Rollen hinzugefügt wurden
    """)
    
    # File Upload
    uploaded_file = st.file_uploader(
        "� characters.json hochladen", 
        type=['json'],
        help="Lade die von swgoh.gg heruntergeladene JSON-Datei hoch"
    )
    
    if uploaded_file is not None:
        try:
            # Parse JSON
            characters = json.load(uploaded_file)
            
            # Validierung: Prüfe ob es ein Array ist und erste Einträge sinnvoll aussehen
            if isinstance(characters, list) and len(characters) > 0:
                if 'base_id' in characters[0] and 'name' in characters[0]:
                    # Speichere in data/characters.json
                    with open(characters_file, 'w', encoding='utf-8') as f:
                        json.dump(characters, f, indent=2, ensure_ascii=False)
                    
                    st.success(f"✅ {len(characters)} Characters erfolgreich aktualisiert!")
                    st.info("💡 **Bitte App neu laden** (F5) um die neuen Daten zu sehen.")
                else:
                    st.error("❌ Datei scheint keine gültige characters.json zu sein (fehlende Felder)!")
            else:
                st.error("❌ Datei scheint keine gültige characters.json zu sein!")
                
        except json.JSONDecodeError:
            st.error("❌ Fehler beim Parsen der JSON-Datei!")
        except Exception as e:
            st.error(f"❌ Fehler beim Verarbeiten: {e}")
    
    st.divider()
    
    # Info-Bereich
    st.subheader("ℹ️ App Information")
    st.markdown(f"""
    - **Geladene CSVs:** {len(df['date'].unique())} Datenabzüge
    - **Verfügbare Daten:** {', '.join(sorted(df['date'].unique(), reverse=True))}
    - **Gesamt-Einträge:** {len(df):,} Zeilen
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
        st.session_state.show_header = False
    
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
            padding-top: 1rem;
            padding-bottom: 1rem;
        }}
        /* Fix für collapsed label bei segmented_control */
        div[data-testid="stSegmentedControl"] {{
            margin-top: 1rem;
        }}
        /* Sidebar kompakter und breiter */
        section[data-testid="stSidebar"] > div {{
            padding-top: 0rem;
        }}
        /* Sidebar-Breite erhöhen (pills nebeneinander) */
        section[data-testid="stSidebar"] {{
            width: 390px !important;
            min-width: 390px !important;
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
    
    print(f"\n[Start data loading] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    df = get_final_df(guild_filter, selected_dates)
    print(f"\n[Stop data loading] {datetime.now().strftime('%H:%M:%S.%f')}", file=sys.stderr)
    
    if df is None:
        st.error("❌ Fehler beim Laden der Daten!")
        if st.button("↩️ Zurück zur Auswahl"):
            del st.session_state['analysis_started']
            st.rerun()
        return
    
    print(f"Shape: {df.shape}", file=sys.stderr)
    print(f"Memory: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB", file=sys.stderr)
    
    # Seitenleiste für Filter
    st.sidebar.subheader("🎛️ Filter")
    
    # Zeige ausgewählte Guild und Dates
    st.sidebar.info(f"**Gilde:** {guild_filter}\n\n**Daten:** {len(selected_dates)} CSV(s)")
    
    # Button um zurück zur Auswahl zu gehen
    if st.sidebar.button("↩️ Neue Auswahl"):
        # Clear session state
        del st.session_state['analysis_started']
        if 'uploaded_csv_df' in st.session_state:
            del st.session_state['uploaded_csv_df']
        st.rerun()
    
    st.sidebar.divider()
    
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
    all_categories = sorted(list({cat for char in characters_data_filtered for cat in char.get('categories', [])}))
    all_roles = sorted(list({char.get('role', '') for char in characters_data_filtered if char.get('role')}))
    all_ability_classes = sorted(list({ac for char in characters_data_filtered for ac in char.get('ability_classes', [])}))
    
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
    available_roles = sorted(list({char.get('role', '') for char in filtered_chars_for_roles if char.get('role')}))
    
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
    
    # Player-Filter (ganz unten in der Sidebar)
    st.sidebar.markdown("---")  # Trennlinie
    st.sidebar.markdown("**👤 Player Filter:**")
    
    # Alle verfügbaren Spielernamen aus dem gefilterten DataFrame
    available_players = sorted(df_filtered['Name'].unique())
    
    # Player-Auswahl mit Session State
    if available_players:
        # Standard: DEFAULT_PLAYER falls verfügbar, sonst erster Spieler
        if 'selected_player' not in st.session_state or st.session_state.selected_player not in available_players:
            # Versuche DEFAULT_PLAYER zu setzen, falls in Liste
            if DEFAULT_PLAYER in available_players:
                st.session_state.selected_player = DEFAULT_PLAYER
            else:
                st.session_state.selected_player = available_players[0]
        
        selected_player = st.sidebar.selectbox(
            "Spieler hervorheben:",
            available_players,
            index=available_players.index(st.session_state.selected_player) if st.session_state.selected_player in available_players else 0,
            key="player_select"
        )
        
        # Session State aktualisieren
        st.session_state.selected_player = selected_player
    else:
        selected_player = None
    
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
        if selected_player in player_base['Name'].values:
            player_base.loc[player_base['Name'] == selected_player, 'Checked'] = True
        
        # Speichere in Session State
        st.session_state.player_base_global = player_base
        st.session_state.current_guild = guild_filter
    
    # Hole globales player_base (shared across all tabs!)
    player_base = st.session_state.player_base_global
    
    # Tab-Navigation mit Segmented Control - NUR aktiver Tab wird gerendert!
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "📊 Character Overview"
    
    selected_tab = st.segmented_control(
        "Navigation",
        options=["📊 Character Overview", "📈 Character Stats", "🔟 Player Relics", 
                 "🏐 Player Omicrons", "🎲 Player Speed Mods", "⚙️ Settings"],
        default=st.session_state.active_tab,
        key="main_navigation",
        selection_mode="single",
        label_visibility="collapsed"
    )
    
    # Update active tab
    st.session_state.active_tab = selected_tab
    
    # CONDITIONAL RENDERING - nur aktiver Tab wird ausgeführt!
    if selected_tab == "📊 Character Overview":
        show_character_overview(df_filtered, filtered_characters, characters_data, filters_active)
    elif selected_tab == "📈 Character Stats":
        show_analytics_tab(df_filtered, filtered_characters, characters_data, filters_active, selected_player)
    elif selected_tab == "🔟 Player Relics":
        show_player_overview_tab(df, guild_filter, selected_player, compare_date)
    elif selected_tab == "🏐 Player Omicrons":
        show_player_omicrons_tab(df, guild_filter, selected_player, compare_date)
    elif selected_tab == "🎲 Player Speed Mods":
        show_player_speed_mods_tab(df, guild_filter, selected_player, compare_date)
    elif selected_tab == "⚙️ Settings":
        show_settings_tab(df)

if __name__ == "__main__":
    main()