from __future__ import annotations

import io
import math
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ALL_ICO_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)
PRESET_WINDOWS: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)
PRESET_FAVICON: tuple[int, ...] = (16, 32, 48)
PRESET_MINIMAL: tuple[int, ...] = (16, 32, 48, 256)

BgRemovalMode = Literal["none", "corners", "color"]
CropMode = Literal["fit", "fill"]
ShapeMask = Literal["none", "rounded", "squircle", "circle"]


@dataclass(slots=True)
class IconConfig:
    """Configuration parameters for icon processing and ICO export."""

    bg_removal_mode: BgRemovalMode = "none"
    bg_target_color: tuple[int, int, int] | None = None
    bg_tolerance: int = 30
    bg_contiguous: bool = True
    auto_trim: bool = True
    crop_mode: CropMode = "fit"
    padding_percent: int = 8
    shape_mask: ShapeMask = "none"
    corner_radius_percent: int = 22
    backplate_enabled: bool = False
    backplate_color: tuple[int, int, int, int] = (30, 41, 59, 255)
    stroke_enabled: bool = False
    stroke_width_percent: float = 3.0
    stroke_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    crisp_small_sizes: bool = True
    sizes: tuple[int, ...] = PRESET_WINDOWS


def parse_hex_color(value: str) -> tuple[int, int, int, int]:
    """Parse a #RRGGBB or #RRGGBBAA hex color string into an RGBA tuple."""
    cleaned = value.strip().lstrip("#")
    if len(cleaned) == 6:
        r = int(cleaned[0:2], 16)
        g = int(cleaned[2:4], 16)
        b = int(cleaned[4:6], 16)
        return (r, g, b, 255)
    if len(cleaned) == 8:
        r = int(cleaned[0:2], 16)
        g = int(cleaned[2:4], 16)
        b = int(cleaned[4:6], 16)
        a = int(cleaned[6:8], 16)
        return (r, g, b, a)
    raise ValueError(f"Invalid hex color: {value!r}")


def detect_corner_color(image: Image.Image) -> tuple[int, int, int]:
    """Sample the four image corners and return the most representative RGB color."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    corners = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((width - 1, 0)),
        rgb.getpixel((0, height - 1)),
        rgb.getpixel((width - 1, height - 1)),
    ]
    most_common, count = Counter(corners).most_common(1)[0]
    if count >= 2:
        return (int(most_common[0]), int(most_common[1]), int(most_common[2]))
    r = round(sum(c[0] for c in corners) / 4)
    g = round(sum(c[1] for c in corners) / 4)
    b = round(sum(c[2] for c in corners) / 4)
    return (r, g, b)


def remove_background(
    image: Image.Image,
    mode: BgRemovalMode,
    target_color: tuple[int, int, int] | None = None,
    tolerance: int = 30,
    contiguous: bool = True,
) -> Image.Image:
    """Remove solid or near-solid backgrounds using feathered color distance."""
    rgba = image.convert("RGBA")
    if mode == "none":
        return rgba

    target = target_color if target_color is not None else detect_corner_color(rgba)
    tol = max(0, min(255, tolerance))
    feather = max(4, tol // 4)
    upper = min(255, tol + feather)

    rgb = rgba.convert("RGB")
    target_layer = Image.new("RGB", rgb.size, target)
    diff_rgb = ImageChops.difference(rgb, target_layer)
    r_diff, g_diff, b_diff = diff_rgb.split()
    max_diff = ImageChops.lighter(ImageChops.lighter(r_diff, g_diff), b_diff)

    if upper == tol:
        lut = [0 if d <= tol else 255 for d in range(256)]
    else:
        span = upper - tol
        lut = [
            0 if d <= tol else (255 if d >= upper else round(255 * (d - tol) / span))
            for d in range(256)
        ]

    soft_alpha = max_diff.point(lut)
    orig_alpha = rgba.getchannel("A")

    if not contiguous:
        new_alpha = ImageChops.darker(orig_alpha, soft_alpha)
        result = rgba.copy()
        result.putalpha(new_alpha)
        return result

    seed_mask = max_diff.point(lambda d: 255 if d <= tol else 0)
    width, height = seed_mask.size
    seed_pixels = seed_mask.load()
    if seed_pixels is not None:
        # Floodfill from all matching perimeter pixels so edge-connected backgrounds
        # are removed while interior regions of the same color stay intact.
        for x in range(width):
            if seed_pixels[x, 0] == 255:
                ImageDraw.floodfill(seed_mask, (x, 0), 128, thresh=0)
            if height > 1 and seed_pixels[x, height - 1] == 255:
                ImageDraw.floodfill(seed_mask, (x, height - 1), 128, thresh=0)
        for y in range(1, height - 1):
            if seed_pixels[0, y] == 255:
                ImageDraw.floodfill(seed_mask, (0, y), 128, thresh=0)
            if width > 1 and seed_pixels[width - 1, y] == 255:
                ImageDraw.floodfill(seed_mask, (width - 1, y), 128, thresh=0)

    bg_mask = seed_mask.point(lambda v: 255 if v == 128 else 0)
    bg_dilated = bg_mask.filter(ImageFilter.MaxFilter(3))
    masked_soft = Image.composite(soft_alpha, Image.new("L", rgba.size, 255), bg_dilated)
    new_alpha = ImageChops.darker(orig_alpha, masked_soft)

    result = rgba.copy()
    result.putalpha(new_alpha)
    return result


def trim_transparent(image: Image.Image, alpha_threshold: int = 5) -> Image.Image:
    """Crop away outer transparent margins above the given alpha threshold."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    binary = alpha.point(lambda a: 255 if a > alpha_threshold else 0)
    bbox = binary.getbbox()
    if bbox is None:
        return rgba
    return rgba.crop(bbox)


def create_shape_mask(
    size: int,
    shape: ShapeMask,
    corner_radius_percent: int = 22,
) -> Image.Image:
    """Create an anti-aliased grayscale shape mask of the requested dimensions."""
    if shape == "none":
        return Image.new("L", (size, size), 255)

    scale = 4
    hi_size = size * scale
    mask = Image.new("L", (hi_size, hi_size), 0)
    draw = ImageDraw.Draw(mask)

    if shape == "circle":
        draw.ellipse((0, 0, hi_size - 1, hi_size - 1), fill=255)
    elif shape == "rounded":
        clamped_radius = max(0, min(50, corner_radius_percent))
        radius_px = round(hi_size * (clamped_radius / 100.0))
        draw.rounded_rectangle((0, 0, hi_size - 1, hi_size - 1), radius=radius_px, fill=255)
    elif shape == "squircle":
        center = (hi_size - 1) / 2.0
        half = (hi_size - 1) / 2.0
        exponent = 4.0
        steps = 256
        points: list[tuple[float, float]] = []
        for idx in range(steps):
            theta = (2.0 * math.pi * idx) / steps
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            x = center + half * math.copysign(abs(cos_t) ** (2.0 / exponent), cos_t)
            y = center + half * math.copysign(abs(sin_t) ** (2.0 / exponent), sin_t)
            points.append((x, y))
        draw.polygon(points, fill=255)

    return mask.resize((size, size), Image.Resampling.LANCZOS)


def apply_stroke(
    image: Image.Image,
    stroke_width_px: int,
    stroke_color: tuple[int, int, int, int],
) -> Image.Image:
    """Render an outline stroke behind non-transparent pixels of the image."""
    rgba = image.convert("RGBA")
    if stroke_width_px <= 0:
        return rgba

    dilated_alpha = rgba.getchannel("A")
    for _ in range(stroke_width_px):
        dilated_alpha = dilated_alpha.filter(ImageFilter.MaxFilter(3))

    smoothed_alpha = dilated_alpha.filter(ImageFilter.GaussianBlur(0.6))
    stroke_alpha = ImageChops.multiply(
        smoothed_alpha,
        Image.new("L", rgba.size, stroke_color[3]),
    )
    stroke_layer = Image.new(
        "RGBA", rgba.size, (stroke_color[0], stroke_color[1], stroke_color[2], 0)
    )
    stroke_layer.putalpha(stroke_alpha)

    return Image.alpha_composite(stroke_layer, rgba)


def fit_to_square(
    image: Image.Image,
    canvas_size: int = 512,
    crop_mode: CropMode = "fit",
    padding_percent: int = 8,
    extra_margin_px: int = 0,
) -> Image.Image:
    """Fit or fill an image onto a transparent square canvas with optional padding."""
    rgba = image.convert("RGBA")
    clamped_pad = max(0, min(45, padding_percent))
    inner_size = max(
        1,
        round(canvas_size * (1.0 - 2.0 * clamped_pad / 100.0)) - 2 * max(0, extra_margin_px),
    )

    if crop_mode == "fill":
        src_w, src_h = rgba.size
        side = min(src_w, src_h)
        left = (src_w - side) // 2
        top = (src_h - side) // 2
        cropped = rgba.crop((left, top, left + side, top + side))
        resized = cropped.resize((inner_size, inner_size), Image.Resampling.LANCZOS)
    else:
        src_w, src_h = rgba.size
        scale = inner_size / max(src_w, src_h)
        target_w = max(1, round(src_w * scale))
        target_h = max(1, round(src_h * scale))
        resized = rgba.resize((target_w, target_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    offset_x = (canvas_size - resized.width) // 2
    offset_y = (canvas_size - resized.height) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas


def process_master_image(
    image: Image.Image,
    config: IconConfig,
    master_size: int = 512,
) -> Image.Image:
    """Run the full icon preparation pipeline and return a square RGBA master image."""
    prepared = ImageOps.exif_transpose(image).convert("RGBA")

    if config.bg_removal_mode != "none":
        prepared = remove_background(
            prepared,
            mode=config.bg_removal_mode,
            target_color=config.bg_target_color,
            tolerance=config.bg_tolerance,
            contiguous=config.bg_contiguous,
        )

    if config.auto_trim:
        prepared = trim_transparent(prepared)

    stroke_px = (
        max(1, round(master_size * (config.stroke_width_percent / 100.0)))
        if config.stroke_enabled
        else 0
    )

    canvas = fit_to_square(
        prepared,
        canvas_size=master_size,
        crop_mode=config.crop_mode,
        padding_percent=config.padding_percent,
        extra_margin_px=stroke_px,
    )

    if config.stroke_enabled:
        canvas = apply_stroke(canvas, stroke_width_px=stroke_px, stroke_color=config.stroke_color)

    if config.backplate_enabled:
        backplate = Image.new("RGBA", (master_size, master_size), config.backplate_color)
        canvas = Image.alpha_composite(backplate, canvas)

    if config.shape_mask != "none":
        shape_mask = create_shape_mask(
            size=master_size,
            shape=config.shape_mask,
            corner_radius_percent=config.corner_radius_percent,
        )
        combined_alpha = ImageChops.multiply(canvas.getchannel("A"), shape_mask)
        canvas.putalpha(combined_alpha)

    return canvas


def generate_icon_sizes(
    master: Image.Image,
    sizes: Sequence[int],
    crisp_small: bool = True,
) -> dict[int, Image.Image]:
    """Generate downsampled RGBA frames for each requested ICO size."""
    unique_sizes = sorted({int(s) for s in sizes if 1 <= int(s) <= 256})
    if not unique_sizes:
        raise ValueError("At least one valid icon size (1..256) must be specified.")

    master_rgba = master.convert("RGBA")
    frames: dict[int, Image.Image] = {}

    for size in unique_sizes:
        resized = master_rgba.resize((size, size), Image.Resampling.LANCZOS)
        if crisp_small and size <= 32:
            alpha = resized.getchannel("A")
            sharpened_rgb = resized.convert("RGB").filter(
                ImageFilter.UnsharpMask(radius=0.8, percent=85, threshold=2)
            )
            resized = sharpened_rgb.convert("RGBA")
            resized.putalpha(alpha)
        frames[size] = resized

    return frames


def save_ico_frames(frames: Mapping[int, Image.Image], output_path: Path) -> Path:
    """Write pre-rendered RGBA frames as PNG-encoded entries into a Windows .ico file."""
    if not frames:
        raise ValueError("Cannot save an .ico file without any frames.")

    sorted_sizes = sorted(frames.keys())
    png_blobs: list[tuple[int, bytes]] = []
    for size in sorted_sizes:
        if not (1 <= size <= 256):
            raise ValueError(f"Unsupported ICO size: {size}")
        frame = frames[size].convert("RGBA")
        if frame.size != (size, size):
            frame = frame.resize((size, size), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG", optimize=True)
        png_blobs.append((size, buffer.getvalue()))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<HHH", 0, 1, len(png_blobs))
    data_offset = 6 + 16 * len(png_blobs)

    entries: list[bytes] = []
    current_offset = data_offset
    for size, blob in png_blobs:
        dim_byte = 0 if size >= 256 else size
        entry = struct.pack(
            "<BBBBHHII",
            dim_byte,
            dim_byte,
            0,
            0,
            1,
            32,
            len(blob),
            current_offset,
        )
        entries.append(entry)
        current_offset += len(blob)

    with output_path.open("wb") as handle:
        handle.write(header)
        for entry in entries:
            handle.write(entry)
        for _, blob in png_blobs:
            handle.write(blob)

    return output_path


def export_ico(
    image: Image.Image,
    output_path: Path,
    config: IconConfig,
) -> Path:
    """Process an input image with the given config and write a multi-size .ico file."""
    master = process_master_image(image, config, master_size=512)
    frames = generate_icon_sizes(master, config.sizes, crisp_small=config.crisp_small_sizes)
    return save_ico_frames(frames, output_path)
