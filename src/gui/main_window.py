from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.processor import (
    ALL_ICO_SIZES,
    PRESET_FAVICON,
    PRESET_MINIMAL,
    PRESET_WINDOWS,
    BgRemovalMode,
    CropMode,
    IconConfig,
    ShapeMask,
    export_ico,
    generate_icon_sizes,
    process_master_image,
)
from src.gui.widgets import (
    SUPPORTED_IMAGE_SUFFIXES,
    InteractivePreviewWidget,
    PreviewBgMode,
    RealContextPreviewBar,
    qimage_to_pil,
)

PREVIEW_SIZES_FOR_BAR: tuple[int, ...] = (16, 24, 32, 48, 64, 256)
PRESET_MAP: dict[str, tuple[int, ...]] = {
    "windows": PRESET_WINDOWS,
    "favicon": PRESET_FAVICON,
    "minimal": PRESET_MINIMAL,
}


def _color_swatch_style(color: tuple[int, int, int, int] | tuple[int, int, int]) -> str:
    r, g, b = color[0], color[1], color[2]
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    text_color = "#111827" if luminance > 150 else "#F9FAFB"
    return (
        f"background-color: rgb({r}, {g}, {b}); color: {text_color}; "
        "border: 1px solid #52525B; border-radius: 4px; padding: 4px 8px;"
    )


class MainWindow(QMainWindow):
    """Main desktop window for py-ico."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("py-ico – Icon Generator")
        self.resize(1120, 740)

        self._source_image: Image.Image | None = None
        self._preview_source: Image.Image | None = None
        self._source_path: Path | None = None
        self._source_name: str = "icon"

        self._bg_target_color: tuple[int, int, int] = (255, 255, 255)
        self._backplate_color: tuple[int, int, int, int] = (30, 41, 59, 255)
        self._stroke_color: tuple[int, int, int, int] = (255, 255, 255, 255)
        self._show_original = False

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(25)
        self._preview_timer.timeout.connect(self._update_preview_now)

        self._size_checkboxes: dict[int, QCheckBox] = {}
        self._updating_presets = False

        self._setup_toolbar()
        self._setup_central_ui()
        self._setup_shortcuts()
        self._sync_control_states()
        self.statusBar().showMessage("Bereit – Bild laden, hineinziehen oder mit Strg+V einfügen.")

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Hauptwerkzeugleiste", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._action_open = QAction("Bild öffnen…", self)
        self._action_open.setToolTip("Eingabebild auswählen (Strg+O)")
        self._action_open.triggered.connect(self._on_open_clicked)
        toolbar.addAction(self._action_open)

        self._action_paste = QAction("Einfügen (Strg+V)", self)
        self._action_paste.setToolTip("Bild aus der Zwischenablage einfügen (Strg+V)")
        self._action_paste.triggered.connect(self.paste_from_clipboard)
        toolbar.addAction(self._action_paste)

        toolbar.addSeparator()

        self._action_pipette = QAction("Pipette", self)
        self._action_pipette.setCheckable(True)
        self._action_pipette.setToolTip("Hintergrundfarbe direkt im Bild anklicken")
        self._action_pipette.toggled.connect(self._on_pipette_toggled)
        toolbar.addAction(self._action_pipette)

        self._action_reset = QAction("Zurücksetzen", self)
        self._action_reset.setToolTip("Alle Einstellungen auf Standardwerte zurücksetzen")
        self._action_reset.triggered.connect(self.reset_settings)
        toolbar.addAction(self._action_reset)

        toolbar.addSeparator()

        self._action_export = QAction("Als .ico speichern…", self)
        self._action_export.setToolTip("Multi-Size-.ico-Datei exportieren (Strg+S)")
        self._action_export.triggered.connect(self._on_export_clicked)
        toolbar.addAction(self._action_export)

    def _setup_central_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(splitter)

        # Left side: preview canvas + real-size context bar
        left_panel = QWidget(splitter)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        view_header = QHBoxLayout()
        self._btn_view_preview = QPushButton("Bearbeitete Vorschau", left_panel)
        self._btn_view_preview.setCheckable(True)
        self._btn_view_preview.setChecked(True)
        self._btn_view_preview.clicked.connect(lambda: self._set_show_original(False))

        self._btn_view_original = QPushButton("Originalbild", left_panel)
        self._btn_view_original.setCheckable(True)
        self._btn_view_original.clicked.connect(lambda: self._set_show_original(True))

        self._image_info_label = QLabel("Kein Bild geladen", left_panel)
        self._image_info_label.setStyleSheet("color: #A1A1AA;")

        view_header.addWidget(self._btn_view_preview)
        view_header.addWidget(self._btn_view_original)
        view_header.addStretch(1)
        view_header.addWidget(self._image_info_label)
        left_layout.addLayout(view_header)

        self._canvas = InteractivePreviewWidget(left_panel)
        self._canvas.file_dropped.connect(self.load_file)
        self._canvas.color_picked.connect(self._on_canvas_color_picked)
        left_layout.addWidget(self._canvas, stretch=1)

        self._context_bar = RealContextPreviewBar(left_panel)
        self._context_bar.background_changed.connect(self._on_preview_bg_changed)
        self._canvas.set_background_mode(self._context_bar.background_mode)
        left_layout.addWidget(self._context_bar)

        # Right side: scrollable settings panel
        scroll = QScrollArea(splitter)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(360)
        scroll.setMaximumWidth(450)

        controls_container = QWidget(scroll)
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(10)

        controls_layout.addWidget(self._build_bg_group(controls_container))
        controls_layout.addWidget(self._build_geometry_group(controls_container))
        controls_layout.addWidget(self._build_style_group(controls_container))
        controls_layout.addWidget(self._build_sizes_group(controls_container))
        controls_layout.addStretch(1)

        scroll.setWidget(controls_container)
        splitter.addWidget(left_panel)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

    def _build_bg_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("1. Freistellen & Hintergrund", parent)
        form = QFormLayout(group)

        self._combo_bg_mode = QComboBox(group)
        self._combo_bg_mode.addItem("Aus (Original behalten)", "none")
        self._combo_bg_mode.addItem("Automatisch (Bildecken)", "corners")
        self._combo_bg_mode.addItem("Ausgewählte Farbe", "color")
        self._combo_bg_mode.currentIndexChanged.connect(self._on_setting_changed)
        form.addRow("Modus:", self._combo_bg_mode)

        color_row = QHBoxLayout()
        self._btn_bg_color = QPushButton("#FFFFFF", group)
        self._btn_bg_color.clicked.connect(self._pick_bg_color_dialog)
        self._btn_bg_pipette = QPushButton("Pipette", group)
        self._btn_bg_pipette.setCheckable(True)
        self._btn_bg_pipette.toggled.connect(self._action_pipette.setChecked)
        self._action_pipette.toggled.connect(self._btn_bg_pipette.setChecked)
        color_row.addWidget(self._btn_bg_color, stretch=1)
        color_row.addWidget(self._btn_bg_pipette)
        form.addRow("Zielfarbe:", color_row)

        tol_row = QHBoxLayout()
        self._slider_tolerance = QSlider(Qt.Orientation.Horizontal, group)
        self._slider_tolerance.setRange(0, 255)
        self._slider_tolerance.setValue(30)
        self._slider_tolerance.valueChanged.connect(self._on_setting_changed)
        self._label_tolerance = QLabel("30", group)
        self._label_tolerance.setMinimumWidth(32)
        tol_row.addWidget(self._slider_tolerance, stretch=1)
        tol_row.addWidget(self._label_tolerance)
        form.addRow("Toleranz:", tol_row)

        self._check_contiguous = QCheckBox("Nur zusammenhängenden Rand entfernen", group)
        self._check_contiguous.setChecked(True)
        self._check_contiguous.toggled.connect(self._on_setting_changed)
        form.addRow("", self._check_contiguous)

        return group

    def _build_geometry_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("2. Zuschneiden & Abstand", parent)
        form = QFormLayout(group)

        self._check_auto_trim = QCheckBox("Leere Ränder automatisch abschneiden", group)
        self._check_auto_trim.setChecked(True)
        self._check_auto_trim.toggled.connect(self._on_setting_changed)
        form.addRow("", self._check_auto_trim)

        self._combo_crop_mode = QComboBox(group)
        self._combo_crop_mode.addItem("Vollständig einpassen (Fit)", "fit")
        self._combo_crop_mode.addItem("Quadratisch füllen (Fill)", "fill")
        self._combo_crop_mode.currentIndexChanged.connect(self._on_setting_changed)
        form.addRow("Einpassung:", self._combo_crop_mode)

        pad_row = QHBoxLayout()
        self._slider_padding = QSlider(Qt.Orientation.Horizontal, group)
        self._slider_padding.setRange(0, 45)
        self._slider_padding.setValue(8)
        self._slider_padding.valueChanged.connect(self._on_setting_changed)
        self._label_padding = QLabel("8 %", group)
        self._label_padding.setMinimumWidth(36)
        pad_row.addWidget(self._slider_padding, stretch=1)
        pad_row.addWidget(self._label_padding)
        form.addRow("Innenabstand:", pad_row)

        return group

    def _build_style_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("3. Form & Dark-Mode-Kontrast", parent)
        form = QFormLayout(group)

        self._combo_shape = QComboBox(group)
        self._combo_shape.addItem("Keine (Quadrat)", "none")
        self._combo_shape.addItem("Abgerundete Ecken", "rounded")
        self._combo_shape.addItem("Squircle (App-Icon)", "squircle")
        self._combo_shape.addItem("Kreis", "circle")
        self._combo_shape.currentIndexChanged.connect(self._on_setting_changed)
        form.addRow("Form-Maske:", self._combo_shape)

        rad_row = QHBoxLayout()
        self._slider_radius = QSlider(Qt.Orientation.Horizontal, group)
        self._slider_radius.setRange(0, 50)
        self._slider_radius.setValue(22)
        self._slider_radius.valueChanged.connect(self._on_setting_changed)
        self._label_radius = QLabel("22 %", group)
        self._label_radius.setMinimumWidth(36)
        rad_row.addWidget(self._slider_radius, stretch=1)
        rad_row.addWidget(self._label_radius)
        form.addRow("Eckenradius:", rad_row)

        backplate_row = QHBoxLayout()
        self._check_backplate = QCheckBox("Hintergrund-Kachel", group)
        self._check_backplate.toggled.connect(self._on_setting_changed)
        self._btn_backplate_color = QPushButton("Farbe", group)
        self._btn_backplate_color.clicked.connect(self._pick_backplate_color_dialog)
        backplate_row.addWidget(self._check_backplate)
        backplate_row.addWidget(self._btn_backplate_color)
        form.addRow("Backplate:", backplate_row)

        stroke_row = QHBoxLayout()
        self._check_stroke = QCheckBox("Außenkontur", group)
        self._check_stroke.toggled.connect(self._on_setting_changed)
        self._btn_stroke_color = QPushButton("Farbe", group)
        self._btn_stroke_color.clicked.connect(self._pick_stroke_color_dialog)
        stroke_row.addWidget(self._check_stroke)
        stroke_row.addWidget(self._btn_stroke_color)
        form.addRow("Kontur:", stroke_row)

        sw_row = QHBoxLayout()
        self._slider_stroke_width = QSlider(Qt.Orientation.Horizontal, group)
        self._slider_stroke_width.setRange(1, 24)  # represents 0.5% .. 12.0%
        self._slider_stroke_width.setValue(6)  # 3.0%
        self._slider_stroke_width.valueChanged.connect(self._on_setting_changed)
        self._label_stroke_width = QLabel("3.0 %", group)
        self._label_stroke_width.setMinimumWidth(42)
        sw_row.addWidget(self._slider_stroke_width, stretch=1)
        sw_row.addWidget(self._label_stroke_width)
        form.addRow("Konturdicke:", sw_row)

        return group

    def _build_sizes_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("4. ICO-Größen & Qualität", parent)
        layout = QVBoxLayout(group)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:", group))
        self._combo_preset = QComboBox(group)
        self._combo_preset.addItem("Windows Standard (16–256)", "windows")
        self._combo_preset.addItem("Web Favicon (16, 32, 48)", "favicon")
        self._combo_preset.addItem("Kompakt (16, 32, 48, 256)", "minimal")
        self._combo_preset.addItem("Benutzerdefiniert", "custom")
        self._combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self._combo_preset, stretch=1)
        layout.addLayout(preset_row)

        sizes_row1 = QHBoxLayout()
        sizes_row2 = QHBoxLayout()
        for idx, size in enumerate(ALL_ICO_SIZES):
            cb = QCheckBox(f"{size}×{size}", group)
            cb.setChecked(size in PRESET_WINDOWS)
            cb.toggled.connect(self._on_size_checkbox_toggled)
            self._size_checkboxes[size] = cb
            if idx < 4:
                sizes_row1.addWidget(cb)
            else:
                sizes_row2.addWidget(cb)
        sizes_row2.addStretch(1)
        layout.addLayout(sizes_row1)
        layout.addLayout(sizes_row2)

        self._check_crisp = QCheckBox("Kleine Größen nachschärfen (16–32 px)", group)
        self._check_crisp.setChecked(True)
        self._check_crisp.toggled.connect(self._on_setting_changed)
        layout.addWidget(self._check_crisp)

        return group

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self._on_open_clicked)
        QShortcut(QKeySequence.StandardKey.Paste, self, activated=self.paste_from_clipboard)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self._on_export_clicked)

    def _sync_control_states(self) -> None:
        bg_mode = self._combo_bg_mode.currentData()
        bg_enabled = bg_mode != "none"
        self._btn_bg_color.setEnabled(bg_mode == "color")
        self._slider_tolerance.setEnabled(bg_enabled)
        self._check_contiguous.setEnabled(bg_enabled)

        self._label_tolerance.setText(str(self._slider_tolerance.value()))
        self._label_padding.setText(f"{self._slider_padding.value()} %")
        self._label_radius.setText(f"{self._slider_radius.value()} %")
        self._label_stroke_width.setText(f"{self._slider_stroke_width.value() * 0.5:.1f} %")

        self._slider_radius.setEnabled(self._combo_shape.currentData() == "rounded")
        self._btn_backplate_color.setEnabled(self._check_backplate.isChecked())
        stroke_on = self._check_stroke.isChecked()
        self._btn_stroke_color.setEnabled(stroke_on)
        self._slider_stroke_width.setEnabled(stroke_on)

        self._btn_bg_color.setStyleSheet(_color_swatch_style(self._bg_target_color))
        self._btn_bg_color.setText(
            f"#{self._bg_target_color[0]:02X}{self._bg_target_color[1]:02X}{self._bg_target_color[2]:02X}"
        )
        self._btn_backplate_color.setStyleSheet(_color_swatch_style(self._backplate_color))
        self._btn_backplate_color.setText(
            f"#{self._backplate_color[0]:02X}{self._backplate_color[1]:02X}{self._backplate_color[2]:02X}"
        )
        self._btn_stroke_color.setStyleSheet(_color_swatch_style(self._stroke_color))
        self._btn_stroke_color.setText(
            f"#{self._stroke_color[0]:02X}{self._stroke_color[1]:02X}{self._stroke_color[2]:02X}"
        )

        has_image = self._source_image is not None
        self._action_export.setEnabled(has_image)
        self._action_pipette.setEnabled(has_image)
        self._btn_bg_pipette.setEnabled(has_image)

    def _set_show_original(self, show_original: bool) -> None:
        self._show_original = show_original
        self._btn_view_original.setChecked(show_original)
        self._btn_view_preview.setChecked(not show_original)
        self._schedule_preview_update()

    def _on_preview_bg_changed(self, mode: str) -> None:
        if mode in ("dark", "light", "checker"):
            typed_mode: PreviewBgMode = mode  # type: ignore[assignment]
            self._canvas.set_background_mode(typed_mode)
            self._update_preview_now()

    def _on_pipette_toggled(self, active: bool) -> None:
        if active and self._source_image is None:
            self._action_pipette.setChecked(False)
            return
        self._canvas.set_pipette_active(active)
        if active:
            self._set_show_original(True)
            self.statusBar().showMessage(
                "Pipette aktiv: Hintergrundfarbe im Originalbild anklicken."
            )
        else:
            self.statusBar().showMessage("Pipette deaktiviert.")

    def _on_canvas_color_picked(self, r: int, g: int, b: int) -> None:
        self._bg_target_color = (r, g, b)
        idx = self._combo_bg_mode.findData("color")
        if idx >= 0:
            self._combo_bg_mode.setCurrentIndex(idx)
        self._action_pipette.setChecked(False)
        self._set_show_original(False)
        self._sync_control_states()
        self._schedule_preview_update()
        self.statusBar().showMessage(f"Hintergrundfarbe ausgewählt: #{r:02X}{g:02X}{b:02X}")

    def _pick_bg_color_dialog(self) -> None:
        initial = QColor(*self._bg_target_color)
        chosen = QColorDialog.getColor(initial, self, "Hintergrundfarbe wählen")
        if chosen.isValid():
            self._bg_target_color = (chosen.red(), chosen.green(), chosen.blue())
            self._sync_control_states()
            self._schedule_preview_update()

    def _pick_backplate_color_dialog(self) -> None:
        initial = QColor(*self._backplate_color)
        chosen = QColorDialog.getColor(
            initial,
            self,
            "Backplate-Farbe wählen",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if chosen.isValid():
            self._backplate_color = (chosen.red(), chosen.green(), chosen.blue(), chosen.alpha())
            self._sync_control_states()
            self._schedule_preview_update()

    def _pick_stroke_color_dialog(self) -> None:
        initial = QColor(*self._stroke_color)
        chosen = QColorDialog.getColor(
            initial,
            self,
            "Konturfarbe wählen",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if chosen.isValid():
            self._stroke_color = (chosen.red(), chosen.green(), chosen.blue(), chosen.alpha())
            self._sync_control_states()
            self._schedule_preview_update()

    def _on_preset_changed(self) -> None:
        preset_key = self._combo_preset.currentData()
        if preset_key in PRESET_MAP:
            target_sizes = set(PRESET_MAP[preset_key])
            self._updating_presets = True
            try:
                for size, cb in self._size_checkboxes.items():
                    cb.setChecked(size in target_sizes)
            finally:
                self._updating_presets = False
            self._schedule_preview_update()

    def _on_size_checkbox_toggled(self) -> None:
        if self._updating_presets:
            return
        selected = tuple(sorted(s for s, cb in self._size_checkboxes.items() if cb.isChecked()))
        matched_key = "custom"
        for key, preset_sizes in PRESET_MAP.items():
            if selected == preset_sizes:
                matched_key = key
                break
        idx = self._combo_preset.findData(matched_key)
        if idx >= 0 and self._combo_preset.currentIndex() != idx:
            self._combo_preset.blockSignals(True)
            self._combo_preset.setCurrentIndex(idx)
            self._combo_preset.blockSignals(False)
        self._schedule_preview_update()

    def _on_setting_changed(self) -> None:
        self._sync_control_states()
        self._schedule_preview_update()

    def _schedule_preview_update(self) -> None:
        if self._source_image is not None:
            self._preview_timer.start()

    def _update_preview_now(self) -> None:
        if self._preview_source is None:
            self._canvas.set_image(None)
            self._context_bar.update_frames({}, set())
            return

        config = self.build_config()
        master = process_master_image(self._preview_source, config, master_size=512)
        bar_sizes = sorted(set(PREVIEW_SIZES_FOR_BAR) | set(config.sizes))
        frames = generate_icon_sizes(master, bar_sizes, crisp_small=config.crisp_small_sizes)

        self._canvas.set_image(self._preview_source if self._show_original else master)
        self._context_bar.update_frames(frames, set(config.sizes))

    def build_config(self) -> IconConfig:
        """Build an IconConfig reflecting all current GUI control values."""
        bg_mode: BgRemovalMode = self._combo_bg_mode.currentData()
        crop_mode: CropMode = self._combo_crop_mode.currentData()
        shape_mask: ShapeMask = self._combo_shape.currentData()
        selected_sizes = tuple(
            sorted(s for s, cb in self._size_checkboxes.items() if cb.isChecked())
        )
        if not selected_sizes:
            selected_sizes = (256,)

        return IconConfig(
            bg_removal_mode=bg_mode,
            bg_target_color=self._bg_target_color if bg_mode == "color" else None,
            bg_tolerance=self._slider_tolerance.value(),
            bg_contiguous=self._check_contiguous.isChecked(),
            auto_trim=self._check_auto_trim.isChecked(),
            crop_mode=crop_mode,
            padding_percent=self._slider_padding.value(),
            shape_mask=shape_mask,
            corner_radius_percent=self._slider_radius.value(),
            backplate_enabled=self._check_backplate.isChecked(),
            backplate_color=self._backplate_color,
            stroke_enabled=self._check_stroke.isChecked(),
            stroke_width_percent=self._slider_stroke_width.value() * 0.5,
            stroke_color=self._stroke_color,
            crisp_small_sizes=self._check_crisp.isChecked(),
            sizes=selected_sizes,
        )

    def reset_settings(self) -> None:
        """Reset all processing controls back to default values."""
        self._bg_target_color = (255, 255, 255)
        self._backplate_color = (30, 41, 59, 255)
        self._stroke_color = (255, 255, 255, 255)

        self._combo_bg_mode.setCurrentIndex(0)
        self._slider_tolerance.setValue(30)
        self._check_contiguous.setChecked(True)
        self._check_auto_trim.setChecked(True)
        self._combo_crop_mode.setCurrentIndex(0)
        self._slider_padding.setValue(8)
        self._combo_shape.setCurrentIndex(0)
        self._slider_radius.setValue(22)
        self._check_backplate.setChecked(False)
        self._check_stroke.setChecked(False)
        self._slider_stroke_width.setValue(6)
        self._combo_preset.setCurrentIndex(0)
        self._on_preset_changed()
        self._check_crisp.setChecked(True)
        self._action_pipette.setChecked(False)
        self._set_show_original(False)
        self._sync_control_states()
        self._schedule_preview_update()
        self.statusBar().showMessage("Einstellungen auf Standard zurückgesetzt.")

    def load_image(
        self,
        image: Image.Image,
        source_name: str = "icon",
        source_path: Path | None = None,
    ) -> None:
        """Load a Pillow image into the editor and refresh previews."""
        normalized = ImageOps.exif_transpose(image).convert("RGBA")
        self._source_image = normalized
        self._source_path = source_path
        self._source_name = source_name

        preview = normalized.copy()
        if max(preview.width, preview.height) > 1024:
            preview.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        self._preview_source = preview

        self._image_info_label.setText(f"{source_name} ({normalized.width}×{normalized.height} px)")
        self._action_pipette.setChecked(False)
        self._set_show_original(False)
        self._sync_control_states()
        self._update_preview_now()
        self.statusBar().showMessage(f"Bild geladen: {source_name}")

    def load_file(self, path: Path) -> bool:
        """Load an image file from disk and display errors in German if loading fails."""
        try:
            with Image.open(path) as img:
                self.load_image(img, source_name=path.name, source_path=path)
            return True
        except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
            QMessageBox.critical(
                self,
                "Fehler beim Öffnen",
                f"Das Bild konnte nicht geladen werden:\n{path}\n\nDetails: {exc}",
            )
            return False

    def paste_from_clipboard(self) -> bool:
        """Paste an image or local image file URL from the system clipboard."""
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime is not None:
            if mime.hasImage():
                qimg = clipboard.image()
                if not qimg.isNull():
                    self.load_image(qimage_to_pil(qimg), source_name="Zwischenablage")
                    return True
            if mime.hasUrls():
                for url in mime.urls():
                    if url.isLocalFile():
                        path = Path(url.toLocalFile())
                        if path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
                            return self.load_file(path)

        self.statusBar().showMessage("Kein Bild in der Zwischenablage gefunden.")
        return False

    def export_to_path(self, output_path: Path) -> Path:
        """Process the full-resolution source image and export it to an .ico file."""
        if self._source_image is None:
            raise RuntimeError("Kein Bild geladen.")
        return export_ico(self._source_image, output_path, self.build_config())

    def _on_open_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Eingabebild auswählen",
            str(self._source_path.parent) if self._source_path else "",
            "Bilder (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.ico);;Alle Dateien (*.*)",
        )
        if file_path:
            self.load_file(Path(file_path))

    def _on_export_clicked(self) -> None:
        if self._source_image is None:
            return
        selected_sizes = [s for s, cb in self._size_checkboxes.items() if cb.isChecked()]
        if not selected_sizes:
            QMessageBox.warning(
                self,
                "Keine Größe ausgewählt",
                "Bitte wähle mindestens eine Icon-Größe für den Export aus.",
            )
            return

        default_path = (
            self._source_path.with_suffix(".ico")
            if self._source_path is not None
            else Path.home() / f"{self._source_name}.ico"
        )
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Icon als .ico speichern",
            str(default_path),
            "Windows Icon (*.ico)",
        )
        if not target:
            return

        output_path = Path(target)
        if output_path.suffix.lower() != ".ico":
            output_path = output_path.with_suffix(".ico")

        try:
            self.export_to_path(output_path)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Fehler beim Speichern",
                f"Die .ico-Datei konnte nicht gespeichert werden:\n{output_path}\n\nDetails: {exc}",
            )
            return

        self.statusBar().showMessage(f"Icon gespeichert: {output_path}")
        QMessageBox.information(
            self,
            "Export erfolgreich",
            f"Die Icon-Datei wurde erfolgreich gespeichert:\n{output_path}",
        )
