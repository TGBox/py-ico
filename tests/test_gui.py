from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PIL import Image, ImageDraw

from src.core.processor import PRESET_FAVICON

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    existing = QtWidgets.QApplication.instance()
    if isinstance(existing, QtWidgets.QApplication):
        return existing
    return QtWidgets.QApplication([])


def test_pil_qimage_roundtrip() -> None:
    from src.gui.widgets import pil_to_qimage, qimage_to_pil

    src = Image.new("RGBA", (32, 24), (12, 128, 250, 200))
    qimg = pil_to_qimage(src)
    restored = qimage_to_pil(qimg)
    assert restored.size == (32, 24)
    assert restored.getpixel((10, 10)) == (12, 128, 250, 200)


def test_main_window_load_configure_and_export(qt_app: QApplication, tmp_path: Path) -> None:
    from src.gui.main_window import MainWindow

    window = MainWindow()
    try:
        sample = Image.new("RGBA", (160, 160), (255, 255, 255, 255))
        draw = ImageDraw.Draw(sample)
        draw.rectangle((40, 40, 120, 120), fill=(16, 185, 129, 255))

        window.load_image(sample, source_name="sample.png")
        assert window._action_export.isEnabled()

        # Select corners bg removal, squircle shape, backplate, stroke, and favicon preset
        window._combo_bg_mode.setCurrentIndex(window._combo_bg_mode.findData("corners"))
        window._combo_shape.setCurrentIndex(window._combo_shape.findData("squircle"))
        window._check_backplate.setChecked(True)
        window._check_stroke.setChecked(True)
        window._combo_preset.setCurrentIndex(window._combo_preset.findData("favicon"))
        window._update_preview_now()

        cfg = window.build_config()
        assert cfg.bg_removal_mode == "corners"
        assert cfg.shape_mask == "squircle"
        assert cfg.backplate_enabled is True
        assert cfg.stroke_enabled is True
        assert cfg.sizes == PRESET_FAVICON

        out_ico = tmp_path / "gui_export.ico"
        window.export_to_path(out_ico)
        assert out_ico.is_file()

        with Image.open(out_ico) as ico:
            assert sorted(ico.info.get("sizes", set())) == [(s, s) for s in PRESET_FAVICON]
    finally:
        window.close()
