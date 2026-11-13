# py-ico

Eine schlanke Python-Desktop-App und CLI-Anwendung, um aus beliebigen Eingabebildern schnell freigestellte, auch in kleinen Größen scharfe und im Dark Mode gut sichtbare Windows-`.ico`-Dateien zu erzeugen.

## Features

- **Flexible Eingabe:** Bild öffnen, per Drag & Drop ins Fenster ziehen oder direkt mit `Strg+V` aus der Zwischenablage einfügen.
- **Hintergrundentfernung:** Automatische Erkennung der Bildecken oder exakte Farbauswahl per Pipette/Farbwähler mit weicher Kante und Toleranzregler.
- **Geometrie & Zuschnitt:** Auto-Trim (leere Ränder entfernen), `Fit`/`Fill`-Einpassung und prozentualer Innenabstand (Padding).
- **Form & Dark-Mode-Kontrast:** Form-Masken (`Abgerundet`, `Squircle`, `Kreis`), optionale Hintergrund-Kachel (Backplate) und Außenkontur (Stroke).
- **Echtgrößen-Vorschau:** Live-Vorschau in `16×16` bis `256×256` auf umschaltbarem dunklem, hellem und Schachbrett-Hintergrund.
- **Crisp-Downsampling & Multi-Size-ICO:** Nachschärfung für kleine Größen (`16–32 px`) sowie Presets (`Windows Standard`, `Favicon`, `Kompakt`) und individuelle Größenauswahl.

## Tech-Stack

- **Sprache:** Python 3.11+
- **Bildverarbeitung:** Pillow
- **Desktop-GUI:** PySide6 (Qt6)
- **Build / Packaging:** uv & PyInstaller
- **Qualität & Tests:** Ruff & Pytest

## Ordnerstruktur

```text
py-ico/
├── docs/ideas/py-ico.md
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   └── processor.py
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── main_window.py
│   │   └── widgets.py
│   ├── __init__.py
│   ├── build.py
│   ├── cli.py
│   ├── main.py
│   └── tools.py
├── tests/
│   ├── test_cli.py
│   ├── test_gui.py
│   ├── test_main.py
│   └── test_processor.py
├── pyproject.toml
└── README.md
```

## Quickstart

```bash
git clone <repo-url>
cd py-ico
uv sync --all-groups

# Desktop-GUI starten
uv run py-ico

# CLI verwenden
uv run py-ico input.png -o output.ico --bg-mode corners --shape squircle --padding 10

# Alle CLI-Optionen anzeigen
uv run py-ico --help

# Tests & Linting ausführen
uv run pytest
uv run lint

# Windows-Executable mit PyInstaller erstellen
uv run build
```

## CLI-Beispiele

```bash
# Einfarbiges Logo (Eckenfarbe entfernen), Squircle-Form und weiße Außenkontur für Dark Mode
uv run py-ico logo.png -o app.ico --bg-mode corners --shape squircle --stroke "#FFFFFF"

# Web-Favicon (16, 32, 48 px) mit fester Hintergrundfarbe und quadratischem Zuschnitt
uv run py-ico foto.jpg -o favicon.ico --crop fill --padding 0 --shape rounded --preset favicon
```
