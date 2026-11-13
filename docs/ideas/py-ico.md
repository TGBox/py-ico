# py-ico – Smart Icon Generator

## Statement of Intent

- **Outcome:** Eine hybride Desktop- und CLI-App (`py-ico`), die beliebige Input-Bilder (Datei, Drag & Drop oder `Strg+V`) mit wenigen Klicks freistellt, zuschneidet, optisch für helle wie dunkle Hintergründe aufbereitet und als scharfe Multi-Resolution-`.ico`-Datei exportiert.
- **User:** Entwickler und Power-User unter Windows, die für eigene Projekte, PyInstaller-Exes oder Desktop-Verknüpfungen schnell hochwertige Icons benötigen.
- **Why now:** Das Projektgerüst steht bereit; bestehende Workflows über große Grafikprogramme oder unflexible Online-Konverter kosten unnötig Zeit und liefern bei kleinen Größen (16×16 / 32×32) oder im Dark Mode oft schwache Ergebnisse.
- **Success:** Ein kopiertes oder hineingezogenes Bild ist in unter 15 Sekunden freigestellt, in der Echtgrößen-Vorschau (16×16 bis 256×256 auf Hell/Dunkel) geprüft und als fertige `.ico`-Datei gespeichert – ohne externe Tools.
- **Constraint:** Leichtgewichtig ohne schwere KI-/ML-Modelle (`Pillow` + `PySide6`), saubere Trennung zwischen englischsprachiger Kernlogik und deutschsprachiger UI/CLI, paketierbar als eigenständige Windows-Anwendung via PyInstaller (`uv run build`).
- **Out of scope:** Keine KI-Bildgenerierung oder neuronalen Freisteller (`rembg`), kein vollwertiges Zeichen-/Pixel-Art-Studio, keine macOS-`.icns`- oder Mobile-Asset-Pipelines im MVP.

---

## Problem Statement

Wie können wir aus beliebigen Ausgangsbildern in Sekunden perfekt freigestellte, auch auf 16×16 Pixeln scharfe und im Dark Mode gut sichtbare Windows-Icons (`.ico`) erzeugen – ohne den Umweg über komplexe Bildbearbeitungsprogramme oder Online-Tools?

## Recommended Direction

Eine fokussierte Desktop-App auf Basis von **PySide6** und **Pillow** (ergänzt um ein Headless-CLI für Skripte), die nach dem Prinzip „Reinwerfen → Prüfen → Speichern“ funktioniert:

1. **Input ohne Reibung:** Bild per Drag & Drop, Dateidialog oder direkt per `Strg+V` aus der Zwischenablage laden.
2. **Aufbereitungs-Pipeline (in Echtzeit):**
   - **Freistellen:** Einfarbigen Hintergrund entfernen (automatisch von den 4 Bildecken oder per Pipetten-Klick im Bild + Toleranz-Slider mit weicher Kante/Anti-Aliasing).
   - **Geometrie:** Auto-Trim (leere Ränder abschneiden), quadratisches Einpassen (Zentrieren/Zuschneiden) und Padding-Slider (Innenabstand in %).
   - **Form & Dark-Mode-Kontrast:** Optionale Form-Maske (Rechteck, Abgerundete Ecken mit Radius-Slider, Squircle, Kreis), optionale Hintergrund-Kachel (Backplate-Farbe) und optionale Außenkontur (Stroke-Farbe & -Dicke).
   - **Crisp-Export:** LANCZOS-Skalierung mit gezielter Nachschärfung (*Unsharp Mask*) für kleine Stufen (16×16, 24×24, 32×32) und Export als kombinierte `.ico`-Datei mit wählbaren Größen-Presets (Standard Windows: `16, 24, 32, 48, 64, 128, 256` oder Favicon: `16, 32, 48`).
3. **Echtzeit-Qualitätskontrolle:** Eine Vorschauleiste zeigt das Ergebnis simultan in echter Pixelgröße (16×16 bis 256×256) auf umschaltbarem hellem, dunklem und Schachbrett-Hintergrund.

## Key Assumptions to Validate

- [ ] **Freistell-Qualität:** Ein Flood-Fill-/Farbdistanz-Algorithmus mit weicher Übergangszone (Alpha-Feathering) reicht für 90 % typischer Icon-Vorlagen ohne Treppcheneffekte aus.
- [ ] **Deterministische Pipeline:** Die Reihenfolge `Hintergrund entfernen → Auto-Trim → Quadratisch einpassen & Padding → Außenkontur (Stroke) → Backplate → Form-Maske → Multi-Size-Skalierung & Nachschärfen` liefert konsistente, nicht abgeschnittene Ergebnisse.
- [ ] **UI-Performance:** Ein zwischengespeichertes Arbeitsbild für die Live-Vorschau mit kurzem Debounce verhindert Ruckler bei Slider-Bewegungen, während der Export auf voller Quellauflösung basiert.

## MVP Scope

- **Core-Modul (`src/core/`):** Reine, UI-unabhängige Bildverarbeitungs-Pipeline mit `Pillow` (vollständig per `pytest` testbar).
- **GUI (`src/gui/`):** PySide6-Fenster mit Drag & Drop, `Strg+V`, interaktiver Vorschau (inkl. Pipetten-Klick), Reglern für Freistellung/Trim/Padding/Form/Backplate/Kontur, Hell/Dunkel-Größenvorschau und `.ico`-Speicherdialog.
- **CLI (`src/cli.py`):** Aufrufbar via `uv run py-ico input.png -o output.ico` mit Flags für alle Pipeline-Optionen.
- **Packaging (`src/build.py`):** PyInstaller-Build für eigenständige Windows-Auslieferung.

## Not Doing (and Why)

- **Keine KI-Hintergrundentfernung (`rembg` / `onnxruntime`):** Spart ~150 MB Build-Größe und lange Startzeiten.
- **Kein freies Pinsel-/Radiergummi-Werkzeug:** Würde die App in ein halbes Zeichenprogramm verwandeln; Fokus bleibt auf parametrischer 1-Klick-Aufbereitung.
- **Keine SVG-Rasterschicht (`cairosvg`):** Benötigt unter Windows externe C-Bibliotheken (Cairo DLLs), die PyInstaller-Builds unnötig fragil machen.
- **Keine Batch-Listen-Verwaltung in der GUI:** Batch-Verarbeitung läuft sauber und skriptbar über das CLI; die GUI bleibt auf das Einzelbild fokussiert.
