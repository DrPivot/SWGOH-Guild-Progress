---
applyTo: '**'
---
STREAMLIT CODE-STYLE:
- Verwende NIEMALS `use_container_width` (deprecated nach 2025-12-31)
- Nutze stattdessen: `width='stretch'` (statt use_container_width=True) oder `width='content'` (statt use_container_width=False)
- Bei st.plotly_chart: `width='content'` für feste Breite
- Bei st.button in sidebar: `width='stretch'` für volle Breite
- Die Anzeige ist optimiert für eine Auflösung von 2560 x 1.440 Pixel.

Analyse von HotBots SWGOH Gildendaten
- Nur für Gilden der Allianz BΛ Bataillon: https://recruit.swgoh.gg/alliance/171/bl-bataillon
- Ermöglicht die Analyse von Gildendaten, die im HotBots-Format (CSV) exportiert wurden.
- Unterstützt Vergleichsanalysen über verschiedene Zeitpunkte hinweg.

Gildenzugang
- Jede Gile muss mindestens eine Basis-CSV-Datei bereitstellen, die im GitHub-Repository gespeichert wird.
- Zusätzliche CSV-Dateien für Vergleichszeitpunkte können hinzugefügt werden.
- Es kann nur eine Gilde pro Analyse ausgewählt werden.





