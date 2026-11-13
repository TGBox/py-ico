from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.core.processor import (
    ALL_ICO_SIZES,
    PRESET_FAVICON,
    PRESET_MINIMAL,
    PRESET_WINDOWS,
    IconConfig,
    export_ico,
    parse_hex_color,
)

PRESETS: dict[str, tuple[int, ...]] = {
    "windows": PRESET_WINDOWS,
    "favicon": PRESET_FAVICON,
    "minimal": PRESET_MINIMAL,
}


def _get_version() -> str:
    try:
        return version("py-ico")
    except PackageNotFoundError:
        return "0.1.0"


def _parse_sizes(raw: str) -> tuple[int, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("Keine gültigen Größen angegeben.")
    sizes: list[int] = []
    for part in parts:
        val = int(part)
        if not (1 <= val <= 256):
            raise ValueError(f"Ungültige Icon-Größe '{val}' (erlaubt: 1 bis 256).")
        sizes.append(val)
    return tuple(sorted(set(sizes)))


def build_parser() -> argparse.ArgumentParser:
    """Build the German CLI argument parser for py-ico."""
    parser = argparse.ArgumentParser(
        prog="py-ico",
        description="Erzeugt aus Eingabebildern optimierte Multi-Size-.ico-Dateien.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Pfad zum Eingabebild (z. B. PNG, JPG, WebP, BMP).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Ausgabepfad für die .ico-Datei (Standard: Eingabename mit .ico).",
    )
    parser.add_argument(
        "--bg-mode",
        choices=["none", "corners", "color"],
        default="none",
        help="Hintergrundentfernung: 'none' (aus), 'corners' (Eckenfarbe), 'color' (feste Farbe).",
    )
    parser.add_argument(
        "--bg-color",
        type=str,
        default=None,
        help="Zielfarbe für --bg-mode=color im Hex-Format (#RRGGBB).",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=30,
        help="Farbtoleranz für die Hintergrundentfernung (0 bis 255, Standard: 30).",
    )
    parser.add_argument(
        "--global-bg",
        action="store_true",
        help="Hintergrundfarbe bildweit statt nur vom Rand zusammenhängend entfernen.",
    )
    parser.add_argument(
        "--no-trim",
        action="store_true",
        help="Leere/transparente Ränder nicht automatisch abschneiden.",
    )
    parser.add_argument(
        "--crop",
        choices=["fit", "fill"],
        default="fit",
        help="Einpassungsmodus: 'fit' (vollständig einpassen) oder 'fill' (quadratisch füllen).",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=8,
        help="Innenabstand in Prozent (0 bis 45, Standard: 8).",
    )
    parser.add_argument(
        "--shape",
        choices=["none", "rounded", "squircle", "circle"],
        default="none",
        help="Form-Maske für das Icon (Standard: none).",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=22,
        help="Eckenradius in Prozent bei --shape=rounded (0 bis 50, Standard: 22).",
    )
    parser.add_argument(
        "--backplate",
        type=str,
        default=None,
        help="Aktiviert eine Hintergrund-Kachel mit der angegebenen Hex-Farbe (#RRGGBB[AA]).",
    )
    parser.add_argument(
        "--stroke",
        type=str,
        default=None,
        help="Aktiviert eine Außenkontur mit der angegebenen Hex-Farbe (#RRGGBB[AA]).",
    )
    parser.add_argument(
        "--stroke-width",
        type=float,
        default=3.0,
        help="Konturdicke in Prozent der Icon-Größe (0.5 bis 12.0, Standard: 3.0).",
    )
    parser.add_argument(
        "--no-crisp",
        action="store_true",
        help="Nachschärfen für kleine Icon-Größen (16–32 px) deaktivieren.",
    )
    parser.add_argument(
        "--preset",
        choices=list(PRESETS.keys()),
        default="windows",
        help="Größen-Preset: 'windows', 'favicon' oder 'minimal' (Standard: windows).",
    )
    parser.add_argument(
        "--sizes",
        type=str,
        default=None,
        help=f"Kommagetrennte Pixelgrößen (z. B. {','.join(str(s) for s in ALL_ICO_SIZES)}).",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Programmversion anzeigen und beenden.",
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> IconConfig:
    bg_target: tuple[int, int, int] | None = None
    if args.bg_color is not None:
        r, g, b, _ = parse_hex_color(args.bg_color)
        bg_target = (r, g, b)

    backplate_enabled = args.backplate is not None
    backplate_color = (
        parse_hex_color(args.backplate) if args.backplate is not None else (30, 41, 59, 255)
    )

    stroke_enabled = args.stroke is not None
    stroke_color = parse_hex_color(args.stroke) if args.stroke is not None else (255, 255, 255, 255)

    sizes = _parse_sizes(args.sizes) if args.sizes is not None else PRESETS[args.preset]

    return IconConfig(
        bg_removal_mode=args.bg_mode,
        bg_target_color=bg_target,
        bg_tolerance=max(0, min(255, args.tolerance)),
        bg_contiguous=not args.global_bg,
        auto_trim=not args.no_trim,
        crop_mode=args.crop,
        padding_percent=max(0, min(45, args.padding)),
        shape_mask=args.shape,
        corner_radius_percent=max(0, min(50, args.radius)),
        backplate_enabled=backplate_enabled,
        backplate_color=backplate_color,
        stroke_enabled=stroke_enabled,
        stroke_width_percent=max(0.5, min(12.0, args.stroke_width)),
        stroke_color=stroke_color,
        crisp_small_sizes=not args.no_crisp,
        sizes=sizes,
    )


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Execute the py-ico command-line interface and return an exit code."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.version:
        print(f"py-ico {_get_version()}")
        return 0

    if args.input is None:
        parser.print_help()
        return 1

    input_path: Path = args.input
    if not input_path.is_file():
        print(f"Fehler: Eingabedatei nicht gefunden: {input_path}", file=sys.stderr)
        return 1

    output_path: Path = args.output if args.output is not None else input_path.with_suffix(".ico")

    try:
        config = _config_from_args(args)
    except ValueError as exc:
        print(f"Fehler in den Parametern: {exc}", file=sys.stderr)
        return 1

    try:
        with Image.open(input_path) as loaded:
            export_ico(loaded, output_path, config)
    except UnidentifiedImageError:
        print(f"Fehler: Datei konnte nicht als Bild gelesen werden: {input_path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Fehler beim Lesen oder Speichern: {exc}", file=sys.stderr)
        return 1

    sizes_text = ", ".join(f"{s}×{s}" for s in config.sizes)
    print(f"Icon erfolgreich erstellt: {output_path} (Größen: {sizes_text})")
    return 0
