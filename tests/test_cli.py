from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from src.cli import run_cli


def _write_sample_png(path: Path) -> None:
    img = Image.new("RGB", (128, 128), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.ellipse((24, 24, 104, 104), fill=(37, 99, 235))
    img.save(path, format="PNG")


def test_cli_exports_ico_with_options(tmp_path: Path, capsys) -> None:
    input_png = tmp_path / "logo.png"
    output_ico = tmp_path / "dist" / "custom.ico"
    _write_sample_png(input_png)

    code = run_cli(
        [
            str(input_png),
            "-o",
            str(output_ico),
            "--bg-mode",
            "corners",
            "--tolerance",
            "35",
            "--padding",
            "10",
            "--shape",
            "squircle",
            "--backplate",
            "#111827",
            "--stroke",
            "#FFFFFF",
            "--sizes",
            "16,32,64",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert output_ico.is_file()
    assert "Icon erfolgreich erstellt" in captured.out

    with Image.open(output_ico) as ico:
        assert sorted(ico.info.get("sizes", set())) == [(16, 16), (32, 32), (64, 64)]


def test_cli_missing_input_returns_error(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "does_not_exist.png"
    code = run_cli([str(missing)])
    captured = capsys.readouterr()
    assert code == 1
    assert "Fehler" in captured.err


def test_cli_invalid_hex_color_returns_error(tmp_path: Path, capsys) -> None:
    input_png = tmp_path / "logo.png"
    _write_sample_png(input_png)
    code = run_cli([str(input_png), "--stroke", "not-a-color"])
    captured = capsys.readouterr()
    assert code == 1
    assert "Fehler" in captured.err

