# CSV-Verschlüsselung Setup

## 🔐 Übersicht

CSV-Dateien im Repository werden verschlüsselt, um Gildendaten zu schützen.

- **Ein Master-Key** für alle Gilden
- **Automatische Verschlüsselung** via Python-Skript
- **Transparente Entschlüsselung** in der App
- **Manuelle Uploads** bleiben unverschlüsselt

---

## 🚀 Erstmalige Einrichtung

### 1. Dependencies installieren

```bash
pip install cryptography tomli
```

### 2. Encryption-Key generieren

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Beispiel-Output:**
```
r4Jz3kP9mN2vQ8wX5tY7bA1cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8c=
```

### 3. Key in `.streamlit/secrets.toml` eintragen

**Lokal** (für encrypt_csvs.py):
```toml
[encryption]
key = "r4Jz3kP9mN2vQ8wX5tY7bA1cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8c="
```

**Streamlit Cloud** (für App):
1. Gehe zu: `https://share.streamlit.io/` → Deine App → ⚙️ Settings
2. Klicke auf "Secrets"
3. Füge hinzu:
```toml
[encryption]
key = "r4Jz3kP9mN2vQ8wX5tY7bA1cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8c="
```

**⚠️ WICHTIG:** Key NIEMALS committen! `.streamlit/secrets.toml` ist in `.gitignore`.

---

## 📦 Workflow: Neue CSVs verschlüsseln

### Schritt 1: CSV in Input-Ordner legen

```bash
hu_data/input/2025-01-15 101st Beskar BataillonFull.csv
```

**Dateinamen-Format:**
```
YYYY-MM-DD <GuildName>Full.csv
```

### Schritt 2: Verschlüsselungs-Skript ausführen

```bash
python encrypt_csvs.py
```

**Beispiel-Output:**
```
============================================================
🔐 SWGOH CSV-Verschlüsselungs-Helper
============================================================
✅ Encryption-Key geladen aus .streamlit\secrets.toml

📂 Gefundene CSV-Dateien: 2
------------------------------------------------------------

📄 2025-01-15 101st Beskar BataillonFull.csv
  📅 Datum: 2025-01-15
  🏰 Gilde: 101st Beskar Bataillon
  🔐 Verschlüssele...
  ✅ Gespeichert: 2025-01-15 101st Beskar BataillonFull.csv.encrypted

📄 2025-01-15 670th GUARD BataillonFull.csv
  📅 Datum: 2025-01-15
  🏰 Gilde: 670th GUARD Bataillon
  🔐 Verschlüssele...
  ✅ Gespeichert: 2025-01-15 670th GUARD BataillonFull.csv.encrypted

============================================================
📊 Zusammenfassung:
  ✅ Verschlüsselt: 2
  ⏭️  Übersprungen: 0
  ❌ Fehler: 0
============================================================

💡 Nächste Schritte:
   1. Überprüfe verschlüsselte Dateien in hu_data/
   2. Committe verschlüsselte Dateien ins Git-Repo
   3. Original-CSVs aus hu_data/input/ löschen (manuell)
```

### Schritt 3: Git Commit

```bash
git add hu_data/*.encrypted
git commit -m "Add encrypted CSVs for 2025-01-15"
git push
```

### Schritt 4: Cleanup

```bash
# Lösche Original-CSVs aus input/ (nur wenn erfolgreich committed!)
rm hu_data/input/*.csv
```

---

## 🔄 Bestehende CSVs verschlüsseln

**Einmalige Aktion** zum Verschlüsseln aller bestehenden CSVs:

```bash
# Kopiere alle CSVs nach input/
cp hu_data/*.csv hu_data/input/

# Verschlüssele
python encrypt_csvs.py

# Lösche alte Plain-CSVs (BACKUP VORHER!)
# rm hu_data/*.csv  # Nur wenn du sicher bist!

# Committe encrypted
git add hu_data/*.encrypted
git commit -m "Encrypt all existing CSVs"
```

---

## 🔓 App-Verhalten

### Mit verschlüsselten CSVs

- ✅ App lädt automatisch `.encrypted` Dateien
- ✅ Entschlüsselung im RAM (keine Temp-Dateien)
- ✅ Key aus `st.secrets["encryption"]["key"]`

### Mit unverschlüsselten CSVs

- ✅ Funktioniert weiterhin (Abwärtskompatibilität)
- ⚠️ Plain `.csv` werden bevorzugt, wenn keine `.encrypted` existiert

### Manuelle Uploads

- ✅ Bleiben **unverschlüsselt** (nur in Session)
- ✅ Werden **nicht** ins Repo committed

---

## 🛠️ Troubleshooting

### Fehler: "Encryption-Key nicht gefunden"

**Lösung:**
```bash
# Prüfe ob secrets.toml existiert
cat .streamlit/secrets.toml

# Falls nicht: Erstelle und füge Key hinzu
mkdir -p .streamlit
echo "[encryption]" > .streamlit/secrets.toml
echo 'key = "DEIN-KEY-HIER"' >> .streamlit/secrets.toml
```

### Fehler: "Import cryptography could not be resolved"

**Lösung:**
```bash
pip install cryptography tomli
```

### Fehler: "Ungültiges CSV-Format"

**Prüfung:**
- Dateiname muss Format `YYYY-MM-DD <Guild>Full.csv` haben
- CSV muss Spalten `AllyCode`, `Name`, `BaseId` enthalten

---

## 📊 Dateistruktur

```
SWGOH-Guild-Progress/
├── hu_data/
│   ├── input/                              # ← Neue CSVs hier ablegen
│   │   └── 2025-01-15 101st...Full.csv    # (wird NICHT committed)
│   ├── 2025-01-15 101st...Full.csv.encrypted  # ← Verschlüsselt (committed)
│   └── 2024-11-02 101st...Full.csv.encrypted
├── .streamlit/
│   └── secrets.toml                        # ← Key hier (NICHT committed)
├── encrypt_csvs.py                         # ← Verschlüsselungs-Skript
└── requirements.txt                        # ← Dependencies
```

---

## 🔒 Sicherheit

### Was ist geschützt?
✅ CSV-Inhalte im GitHub-Repo (verschlüsselt)  
✅ Keine Plain-Text-Spielerdaten öffentlich sichtbar

### Was ist NICHT geschützt?
❌ Dateinamen (Datum + Gildenname sichtbar)  
❌ Dateigrößen (kann Spieleranzahl verraten)  
❌ Commit-History (wann welche Gilde aktualisiert wurde)

### Key-Management
⚠️ **SINGLE POINT OF FAILURE**: Wenn Key verloren geht, sind alle CSVs unlesbar!  
💾 **Backup empfohlen**: Key sicher speichern (z.B. Password Manager)

---

**Letzte Aktualisierung:** 2025-11-22
