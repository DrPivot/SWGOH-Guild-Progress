"""
CSV-Verschlüsselungs-Helper für SWGOH Guild Progress
====================================================

Verschlüsselt neue CSV-Dateien aus data/hotutils/input/ nach data/hotutils/ (verschlüsselt).

Usage:
    python encrypt_csvs.py

Anforderungen:
    - Neue CSVs in data/hotutils/input/ ablegen
    - Dateiformat: YYYY-MM-DD <GuildName>Full.csv
    - Key in .streamlit/secrets.toml: [encryption] key = "..."
"""

import os
import glob
import re
from pathlib import Path
from cryptography.fernet import Fernet
import tomli

# Pfade
INPUT_DIR = Path("data/hotutils/input")
OUTPUT_DIR = Path("data/hotutils")
SECRETS_FILE = Path(".streamlit/secrets.toml")

def load_encryption_key():
    """Lädt Encryption-Key aus secrets.toml."""
    if not SECRETS_FILE.exists():
        print(f"❌ Fehler: {SECRETS_FILE} nicht gefunden!")
        print("\nErstelle Datei mit folgendem Inhalt:")
        print('[encryption]')
        print('key = "<dein-fernet-key>"')
        print("\nKey generieren mit: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        exit(1)
    
    with open(SECRETS_FILE, "rb") as f:
        secrets = tomli.load(f)
    
    key = secrets.get("encryption", {}).get("key")
    if not key:
        print(f"❌ Fehler: 'encryption.key' nicht in {SECRETS_FILE} gefunden!")
        exit(1)
    
    return key.encode()

def extract_date_from_filename(filename):
    """Extrahiert Datum aus Dateinamen: YYYY-MM-DD <GuildName>Full.csv"""
    match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(.+?)Full\.csv', filename)
    if match:
        return match.group(1), match.group(2)  # (date, guild_name)
    return None, None

def is_already_encrypted(date, guild_name):
    """Prüft ob verschlüsselte Version bereits existiert."""
    pattern = f"{date} {guild_name}Full.csv.encrypted"
    encrypted_file = OUTPUT_DIR / pattern
    return encrypted_file.exists()

def validate_csv_format(filepath):
    """Validiert CSV-Format (Basic Check)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            header = f.readline()
            # Prüfe ob HotUtils-Format (bekannte Spalten)
            required_columns = ['AllyCode', 'Name', 'BaseId']
            return all(col in header for col in required_columns)
    except Exception as e:
        print(f"  ⚠️  Format-Validierung fehlgeschlagen: {e}")
        return False

def encrypt_file(input_path, output_path, cipher):
    """Verschlüsselt eine Datei."""
    try:
        with open(input_path, 'rb') as f:
            plaintext = f.read()
        
        encrypted = cipher.encrypt(plaintext)
        
        with open(output_path, 'wb') as f:
            f.write(encrypted)
        
        return True
    except Exception as e:
        print(f"  ❌ Verschlüsselung fehlgeschlagen: {e}")
        return False

def main():
    """Hauptfunktion: Verarbeitet alle CSVs in input/."""
    print("=" * 60)
    print("🔐 SWGOH CSV-Verschlüsselungs-Helper")
    print("=" * 60)
    
    # Prüfe Verzeichnisse
    if not INPUT_DIR.exists():
        print(f"\n📁 Erstelle Input-Verzeichnis: {INPUT_DIR}")
        INPUT_DIR.mkdir(parents=True)
        print(f"✅ Lege neue CSVs in {INPUT_DIR}/ ab und führe das Skript erneut aus.")
        return
    
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)
    
    # Lade Encryption-Key
    key = load_encryption_key()
    cipher = Fernet(key)
    print(f"✅ Encryption-Key geladen aus {SECRETS_FILE}")
    
    # Finde alle CSV-Dateien in input/
    csv_files = list(INPUT_DIR.glob("*.csv"))
    
    if not csv_files:
        print(f"\n📭 Keine CSV-Dateien in {INPUT_DIR}/ gefunden.")
        return
    
    print(f"\n📂 Gefundene CSV-Dateien: {len(csv_files)}")
    print("-" * 60)
    
    processed = 0
    skipped = 0
    errors = 0
    
    for csv_file in sorted(csv_files):
        filename = csv_file.name
        print(f"\n📄 {filename}")
        
        # Extrahiere Datum und Guild
        date, guild_name = extract_date_from_filename(filename)
        
        if not date or not guild_name:
            print(f"  ⚠️  Ungültiges Dateiformat (erwartet: YYYY-MM-DD <Guild>Full.csv)")
            errors += 1
            continue
        
        print(f"  📅 Datum: {date}")
        print(f"  🏰 Gilde: {guild_name}")
        
        # Prüfe ob bereits verschlüsselt
        if is_already_encrypted(date, guild_name):
            print(f"  ⏭️  Übersprungen (bereits verschlüsselt vorhanden)")
            skipped += 1
            continue
        
        # Validiere CSV-Format
        if not validate_csv_format(csv_file):
            print(f"  ❌ Ungültiges CSV-Format (AllyCode/Name/BaseId fehlen)")
            errors += 1
            continue
        
        # Verschlüssele
        output_file = OUTPUT_DIR / f"{filename}.encrypted"
        print(f"  🔐 Verschlüssele...")
        
        if encrypt_file(csv_file, output_file, cipher):
            print(f"  ✅ Gespeichert: {output_file.name}")
            processed += 1
            
            # Optional: Original-Datei löschen (auskommentiert für Sicherheit)
            # csv_file.unlink()
            # print(f"  🗑️  Original gelöscht")
        else:
            errors += 1
    
    # Zusammenfassung
    print("\n" + "=" * 60)
    print("📊 Zusammenfassung:")
    print(f"  ✅ Verschlüsselt: {processed}")
    print(f"  ⏭️  Übersprungen: {skipped}")
    print(f"  ❌ Fehler: {errors}")
    print("=" * 60)
    
    if processed > 0:
        print("\n💡 Nächste Schritte:")
        print("   1. Überprüfe verschlüsselte Dateien in data/hotutils/")
        print("   2. Committe verschlüsselte Dateien ins Git-Repo")
        print("   3. Original-CSVs aus data/hotutils/input/ löschen (manuell)")

if __name__ == "__main__":
    main()
