from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from src.core.processor import (
    PRESET_FAVICON,
    PRESET_WINDOWS,
    IconConfig,
    apply_stroke,
    create_shape_mask,
    detect_corner_color,
    export_ico,
    fit_to_square,
    generate_icon_sizes,
    parse_hex_color,
    process_master_image,
    remove_background,
    trim_transparent,
)


def _create_logo_with_interior_white() -> Image.Image:
    """Create a 120x120 image with white background, dark ring, and white center hole."""
    img = Image.new("RGBA", (120, 120), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((25, 25, 95, 95), fill=(20, 40, 80, 255))
    draw.rectangle((45, 45, 75, 75), fill=(255, 255, 255, 255))
    return img


def test_parse_hex_color() -> None:
    assert parse_hex_color("#1E293B") == (30, 41, 59, 255)
    assert parse_hex_color("ff00aa80") == (255, 0, 170, 128)
    with pytest.raises(ValueError):
        parse_hex_color("#12345")


def test_detect_corner_color() -> None:
    img = Image.new("RGB", (64, 64), (10, 200, 30))
    draw = ImageDraw.Draw(img)
    draw.rectangle((16, 16, 48, 48), fill=(250, 10, 10))
    assert detect_corner_color(img) == (10, 200, 30)


def test_remove_background_contiguous_preserves_interior_color() -> None:
    img = _create_logo_with_interior_white()
    cleaned = remove_background(img, mode="corners", tolerance=20, contiguous=True)

    # Outer white corner becomes transparent
    assert cleaned.getpixel((0, 0))[3] == 0
    # Dark ring stays opaque
    assert cleaned.getpixel((30, 30))[3] == 255
    # Interior white hole (enclosed by dark ring) stays opaque
    assert cleaned.getpixel((60, 60))[3] == 255


def test_remove_background_global_removes_interior_color() -> None:
    img = _create_logo_with_interior_white()
    cleaned = remove_background(
        img,
        mode="color",
        target_color=(255, 255, 255),
        tolerance=20,
        contiguous=False,
    )
    assert cleaned.getpixel((0, 0))[3] == 0
    assert cleaned.getpixel((60, 60))[3] == 0
    assert cleaned.getpixel((30, 30))[3] == 255


def test_trim_transparent() -> None:
    img = Image.new("RGBA", (100, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 10, 59, 49), fill=(255, 0, 0, 255))

    trimmed = trim_transparent(img)
    assert trimmed.size == (40, 40)

    empty = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    assert trim_transparent(empty).size == (32, 32)


def test_fit_to_square_fit_and_fill() -> None:
    rect = Image.new("RGBA", (200, 100), (255, 0, 0, 255))

    fitted = fit_to_square(rect, canvas_size=100, crop_mode="fit", padding_percent=0)
    assert fitted.size == (100, 100)
    # Top row is transparent because 2:1 aspect ratio centers vertically (y=25..75)
    assert fitted.getpixel((50, 5))[3] == 0
    assert fitted.getpixel((50, 50))[3] == 255

    filled = fit_to_square(rect, canvas_size=100, crop_mode="fill", padding_percent=0)
    assert filled.size == (100, 100)
    assert filled.getpixel((50, 5))[3] == 255


@pytest.mark.parametrize("shape", ["rounded", "squircle", "circle"])
def test_create_shape_mask_cuts_corners_and_keeps_center(shape: str) -> None:
    mask = create_shape_mask(128, shape=shape, corner_radius_percent=25)  # type: ignore[arg-type]
    assert mask.size == (128, 128)
    assert mask.getpixel((0, 0)) == 0
    assert mask.getpixel((64, 64)) == 255


def test_apply_stroke_expands_alpha_halo() -> None:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((24, 24, 40, 40), fill=(0, 0, 0, 255))

    stroked = apply_stroke(img, stroke_width_px=3, stroke_color=(255, 255, 255, 255))
    # Just outside original rect (24..40) at (22, 32) should now have stroke pixels
    assert stroked.getpixel((22, 32))[3] > 0
    assert stroked.getpixel((22, 32))[:3] == (255, 255, 255)
    # Center remains black
    assert stroked.getpixel((32, 32))[:3] == (0, 0, 0)


def test_process_master_image_and_export_ico(tmp_path: Path) -> None:
    img = _create_logo_with_interior_white()
    config = IconConfig(
        bg_removal_mode="corners",
        bg_tolerance=25,
        auto_trim=True,
        padding_percent=10,
        shape_mask="squircle",
        backplate_enabled=True,
        backplate_color=(15, 23, 42, 255),
        stroke_enabled=True,
        stroke_width_percent=2.5,
        stroke_color=(255, 255, 255, 255),
        sizes=PRESET_WINDOWS,
    )

    master = process_master_image(img, config, master_size=512)
    assert master.size == (512, 512)
    # Corner clipped by squircle mask
    assert master.getpixel((0, 0))[3] == 0

    frames = generate_icon_sizes(master, PRESET_FAVICON, crisp_small=True)
    assert list(frames.keys()) == [16, 32, 48]

    output_ico = tmp_path / "app.ico"
    export_ico(img, output_ico, config)
    assert output_ico.is_file()

    with Image.open(output_ico) as ico:
        embedded_sizes = sorted(ico.info.get("sizes", set()))
        assert embedded_sizes == [(s, s) for s in PRESET_WINDOWS]

