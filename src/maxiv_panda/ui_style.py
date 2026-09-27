from __future__ import annotations

"""Application-level UI configuration and styling helpers."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore

from .ui_metrics import (
    InterfaceDensity,
    UiMetrics,
    STANDARD_METRICS,
    metrics_for_density,
    metrics_with_font_offset,
    resolve_automatic_density,
)


# Existing FlexPES behaviour before 0.10.64 was: take the platform/QApplication
# font and enlarge it by two points (or two pixels where point size is absent).
# This remains the default that users already find comfortable.
BASELINE_FONT_INCREMENT = 2
ALLOWED_FONT_OFFSETS = (0, 1, 2)
SETTINGS_ORGANIZATION = "MAX IV"
SETTINGS_APPLICATION = "FlexPES PES Processor"
SETTINGS_GROUP = "appearance"
FONT_BASELINE_MIGRATION_KEY = "font_baseline_schema"
FONT_BASELINE_SCHEMA = 1


class UiTheme(str, Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class UiConfiguration:
    density: InterfaceDensity = InterfaceDensity.STANDARD
    # Accessibility enlargement relative to the current FlexPES baseline.
    font_offset_pt: int = 0
    theme: UiTheme = UiTheme.SYSTEM


_LAYOUT_ROLE = "flexpes_ui_layout_role"
_WIDGET_ROLE = "flexpes_ui_widget_role"
_BASE_APPLICATION_FONT: QtGui.QFont | None = None
_BASE_APPLICATION_PALETTE: QtGui.QPalette | None = None


def register_layout_role(layout, role: str) -> None:
    """Mark a layout whose generic spacing/margins may be changed live."""

    try:
        layout.setProperty(_LAYOUT_ROLE, str(role))
    except Exception:
        pass


def register_widget_role(widget: QtWidgets.QWidget, role: str) -> None:
    """Mark a widget whose generic minimum geometry may be changed live."""

    try:
        widget.setProperty(_WIDGET_ROLE, str(role))
    except Exception:
        pass


def _settings() -> QtCore.QSettings:
    return QtCore.QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def load_ui_configuration() -> UiConfiguration:
    """Load the persisted appearance preference, falling back safely."""

    settings = _settings()
    settings.beginGroup(SETTINGS_GROUP)
    density_raw = settings.value("density", InterfaceDensity.STANDARD.value)
    theme_raw = settings.value("theme", UiTheme.SYSTEM.value)
    # 0.10.65--0.10.68 were development versions of the appearance system.
    # A +1/+2 test choice could therefore become the next launch's apparent
    # "default" via QSettings.  Reset that legacy state once when moving to
    # the stable baseline schema; choices made from 0.10.69 onward persist.
    try:
        schema = int(settings.value(FONT_BASELINE_MIGRATION_KEY, 0) or 0)
    except (TypeError, ValueError):
        schema = 0
    if schema < FONT_BASELINE_SCHEMA:
        font_raw = 0
        settings.setValue("font_offset_pt", 0)
        settings.setValue(FONT_BASELINE_MIGRATION_KEY, FONT_BASELINE_SCHEMA)
        settings.sync()
    else:
        font_raw = settings.value("font_offset_pt", 0)
    settings.endGroup()
    try:
        density = InterfaceDensity(str(density_raw))
    except (TypeError, ValueError):
        density = InterfaceDensity.STANDARD
    try:
        font_offset = int(font_raw)
    except (TypeError, ValueError):
        font_offset = 0
    if font_offset not in ALLOWED_FONT_OFFSETS:
        font_offset = 0
    try:
        theme = UiTheme(str(theme_raw))
    except (TypeError, ValueError):
        theme = UiTheme.SYSTEM
    return UiConfiguration(density=density, font_offset_pt=font_offset, theme=theme)


def save_ui_configuration(config: UiConfiguration) -> None:
    """Persist a validated appearance preference."""

    density = config.density
    if not isinstance(density, InterfaceDensity):
        try:
            density = InterfaceDensity(str(density))
        except (TypeError, ValueError):
            density = InterfaceDensity.STANDARD
    font_offset = int(config.font_offset_pt)
    theme = config.theme
    if not isinstance(theme, UiTheme):
        try:
            theme = UiTheme(str(theme))
        except (TypeError, ValueError):
            theme = UiTheme.SYSTEM
    if font_offset not in ALLOWED_FONT_OFFSETS:
        font_offset = 0
    settings = _settings()
    settings.beginGroup(SETTINGS_GROUP)
    settings.setValue("density", density.value)
    settings.setValue("font_offset_pt", font_offset)
    settings.setValue("theme", theme.value)
    settings.endGroup()
    settings.sync()


def _screen_size(app: QtWidgets.QApplication) -> tuple[int | None, int | None]:
    try:
        screen = app.primaryScreen()
        if screen is None:
            return None, None
        geometry = screen.availableGeometry()
        return int(geometry.width()), int(geometry.height())
    except Exception:
        return None, None


def resolve_density(app: QtWidgets.QApplication, density: InterfaceDensity) -> InterfaceDensity:
    if density is not InterfaceDensity.AUTOMATIC:
        return density
    width, height = _screen_size(app)
    return resolve_automatic_density(available_width=width, available_height=height)


class FlexPESCheckStyle(QtWidgets.QProxyStyle):
    """Fusion proxy that draws conventional high-contrast check marks in Dark mode."""

    def __init__(self, base_style: str = "Fusion") -> None:
        super().__init__(base_style)
        self.dark_mode = False


    def drawPrimitive(self, element, option, painter, widget=None):  # noqa: N802
        checkbox_elements = {
            QtWidgets.QStyle.PrimitiveElement.PE_IndicatorCheckBox,
            QtWidgets.QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,
        }
        if not self.dark_mode or element not in checkbox_elements:
            return super().drawPrimitive(element, option, painter, widget)

        rect = QtCore.QRectF(option.rect).adjusted(1.0, 1.0, -1.0, -1.0)
        enabled = bool(option.state & QtWidgets.QStyle.StateFlag.State_Enabled)
        checked = bool(option.state & QtWidgets.QStyle.StateFlag.State_On)
        partial = bool(option.state & QtWidgets.QStyle.StateFlag.State_NoChange)
        hover = bool(option.state & QtWidgets.QStyle.StateFlag.State_MouseOver)

        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        background = QtGui.QColor("#303030" if enabled else "#383838")
        border = QtGui.QColor("#eeeeee" if hover and enabled else ("#b8b8b8" if enabled else "#858585"))
        painter.setBrush(background)
        painter.setPen(QtGui.QPen(border, 1.0))
        painter.drawRoundedRect(rect, 2.0, 2.0)

        mark = QtGui.QColor("#ffffff" if enabled else "#a7a7a7")
        painter.setPen(QtGui.QPen(mark, 1.8, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))
        if checked:
            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            path = QtGui.QPainterPath()
            path.moveTo(x + 0.22 * w, y + 0.53 * h)
            path.lineTo(x + 0.43 * w, y + 0.74 * h)
            path.lineTo(x + 0.80 * w, y + 0.28 * h)
            painter.drawPath(path)
        elif partial:
            inset = rect.adjusted(rect.width() * 0.22, rect.height() * 0.43, -rect.width() * 0.22, -rect.height() * 0.43)
            painter.drawLine(inset.topLeft(), inset.topRight())
        painter.restore()


def _application_stylesheet(
    metrics: UiMetrics,
    *,
    font_size_pt: int | None = None,
    theme: UiTheme = UiTheme.SYSTEM,
) -> str:
    """Return conservative shared styling without overriding feature geometry.

    Standard density intentionally stays close to the proven 0.10.63 Fusion
    geometry. Density affects whitespace/layout metrics; font size is global.
    Feature-specific controls keep their own minimum sizes and size hints.

    The Dark-theme additions below are contrast-only: they deliberately avoid
    padding/size rules so scientific-panel geometry and Matplotlib canvases are
    unaffected.
    """

    font_rule = "" if not font_size_pt or font_size_pt <= 0 else f"font-size: {font_size_pt}pt;"
    common = f"""
        QWidget {{ {font_rule} }}
        QMenu {{ {font_rule} }}
        QToolTip {{ {font_rule} }}
        QMenu::item {{ padding: {metrics.menu_v_padding}px 10px; }}
    """
    if theme is not UiTheme.DARK:
        return common

    # Small contrast polish for the Qt chrome only.  Do not style generic
    # widget padding/minimum sizes here: several scientific panels have
    # carefully tuned geometry that must remain unchanged.
    dark_contrast = """
        /* Core surfaces and text.  Keep this palette-driven wherever possible
           so custom widgets inherit the same dark appearance. */
        QGroupBox { color: #eeeeee; }
        QLabel { color: #eeeeee; }
        QAbstractItemView { color: #eeeeee; }

        QSplitter::handle { background: #5d5d5d; }
        QSplitter::handle:hover { background: #787878; }

        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
            background: #737373;
            border-radius: 3px;
        }
        QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
            background: #8a8a8a;
        }
        QScrollBar::add-page, QScrollBar::sub-page { background: #292929; }

        QPushButton, QToolButton {
            color: #eeeeee;
            border: 1px solid #626262;
            background: #3b3b3b;
        }
        QPushButton:hover, QToolButton:hover {
            background: #4a4a4a;
            border-color: #858585;
        }
        QPushButton:pressed, QToolButton:pressed { background: #303030; }
        QPushButton:checked, QToolButton:checked {
            background: #505050;
            border-color: #929292;
        }
        QPushButton:disabled, QToolButton:disabled {
            color: #bdbdbd;
            background: #353535;
            border-color: #515151;
        }

        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
            color: #eeeeee;
            background: #262626;
            border: 1px solid #666666;
            selection-background-color: #3069aa;
            selection-color: white;
        }
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
        QDoubleSpinBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
            color: #b8b8b8;
            background: #303030;
            border-color: #505050;
        }
        QComboBox QAbstractItemView {
            color: #eeeeee;
            background: #262626;
            selection-background-color: #3069aa;
            selection-color: white;
        }

        /* Explicit spin-box arrow images: do not rely on platform/Fusion
           primitive painting, which can render invisible arrows on Windows. */
        QSpinBox::up-button, QDoubleSpinBox::up-button {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 14px;
            background: #303030;
            border-left: 1px solid #555555;
            border-bottom: 1px solid #444444;
        }
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 14px;
            background: #303030;
            border-left: 1px solid #555555;
            border-top: 1px solid #444444;
        }
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
            background: #444444;
        }
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
            image: url(__FLEXPES_SPIN_UP__);
            width: 9px; height: 6px;
        }
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
            image: url(__FLEXPES_SPIN_DOWN__);
            width: 9px; height: 6px;
        }

        /* Checkbox indicators are painted by FlexPESCheckStyle in Dark mode.
           Keep only text/spacing in QSS so the conventional check mark remains
           visible instead of being replaced by a filled selection square. */
        QCheckBox { color: #eeeeee; spacing: 5px; }
        QCheckBox:disabled { color: #bdbdbd; }

        QRadioButton { color: #eeeeee; spacing: 5px; }
        QRadioButton:disabled { color: #bdbdbd; }
        QRadioButton::indicator { width: 13px; height: 13px; }
        QRadioButton::indicator:unchecked {
            background: #292929;
            border: 1px solid #b0b0b0;
            border-radius: 7px;
        }
        QRadioButton::indicator:unchecked:hover { border-color: #ededed; }
        QRadioButton::indicator:unchecked:disabled { border-color: #858585; }

        /* Tabs need explicit spacing in Dark mode.  Without it the Fusion
           theme makes neighbouring titles read like one continuous word. */
        QTabBar::tab {
            color: #dddddd;
            background: #343434;
            border: 1px solid #5b5b5b;
            border-bottom-color: #676767;
            padding: 4px 10px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            color: #ffffff;
            background: #505050;
            border-color: #808080;
            border-bottom-color: #505050;
        }
        QTabBar::tab:hover:!selected {
            color: #ffffff;
            background: #424242;
            border-color: #747474;
        }

        QHeaderView::section {
            color: #eeeeee;
            background: #3c3c3c;
            border-color: #5e5e5e;
        }
        QTreeView, QTableView, QListView, QListWidget, QTreeWidget, QTableWidget {
            color: #eeeeee;
            background: #1f1f1f;
            alternate-background-color: #292929;
            border-color: #555555;
        }
        QTreeView::item:hover, QTableView::item:hover,
        QListView::item:hover, QListWidget::item:hover,
        QTreeWidget::item:hover, QTableWidget::item:hover { background: #363d45; }
        QTreeView::item:selected, QTableView::item:selected,
        QListView::item:selected, QListWidget::item:selected,
        QTreeWidget::item:selected, QTableWidget::item:selected {
            background: #3069aa;
            color: white;
        }

        QMenu { color: #eeeeee; background: #2d2d2d; border: 1px solid #555555; }
        QMenu::item:selected { background: #3069aa; color: white; }
        QToolTip { color: #202020; background: #f1f1f1; border: 1px solid #888888; }
    """
    data_dir = (Path(__file__).resolve().parent / "data")
    up_icon = (data_dir / "spin_up_light.png").as_posix()
    down_icon = (data_dir / "spin_down_light.png").as_posix()
    dark_contrast = dark_contrast.replace("__FLEXPES_SPIN_UP__", up_icon)
    dark_contrast = dark_contrast.replace("__FLEXPES_SPIN_DOWN__", down_icon)
    return common + dark_contrast


def _light_palette(app: QtWidgets.QApplication) -> QtGui.QPalette:
    try:
        return QtGui.QPalette(app.style().standardPalette())
    except Exception:
        return QtGui.QPalette(app.palette())


def _dark_palette() -> QtGui.QPalette:
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(235, 235, 235))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(42, 42, 42))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(245, 245, 245))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(235, 235, 235))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(52, 52, 52))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(235, 235, 235))
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor(255, 90, 90))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(48, 105, 170))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(105, 175, 235))
    palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor(150, 150, 150))
    # Disabled controls should remain clearly readable without looking active.
    disabled_text = QtGui.QColor(184, 184, 184)
    palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, disabled_text)
    palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, disabled_text)
    return palette


def _apply_theme_palette(app: QtWidgets.QApplication, theme: UiTheme) -> None:
    global _BASE_APPLICATION_PALETTE
    if _BASE_APPLICATION_PALETTE is None:
        _BASE_APPLICATION_PALETTE = QtGui.QPalette(app.palette())
    if theme is UiTheme.DARK:
        app.setPalette(_dark_palette())
    elif theme is UiTheme.LIGHT:
        app.setPalette(_light_palette(app))
    else:
        app.setPalette(QtGui.QPalette(_BASE_APPLICATION_PALETTE))


def apply_application_style(
    app: QtWidgets.QApplication,
    config: UiConfiguration | None = None,
) -> UiMetrics:
    """Apply FlexPES application styling and return the resolved UI metrics."""

    config = config or load_ui_configuration()

    try:
        style = FlexPESCheckStyle("Fusion")
        style.dark_mode = config.theme is UiTheme.DARK
        app.setStyle(style)
    except Exception:
        try:
            app.setStyle("Fusion")
        except Exception:
            pass

    try:
        _apply_theme_palette(app, config.theme)
    except Exception:
        pass

    font_size_pt = None
    try:
        global _BASE_APPLICATION_FONT
        if _BASE_APPLICATION_FONT is None:
            _BASE_APPLICATION_FONT = QtGui.QFont(app.font())
        base_font = QtGui.QFont(_BASE_APPLICATION_FONT)
        font = QtGui.QFont(base_font)
        point_size = int(base_font.pointSize())
        requested_increment = BASELINE_FONT_INCREMENT + int(config.font_offset_pt)
        if point_size > 0:
            font_size_pt = point_size + requested_increment
            font.setPointSize(font_size_pt)
        else:
            pixel_size = int(base_font.pixelSize())
            if pixel_size > 0:
                font.setPixelSize(pixel_size + requested_increment)
        # QApplication.setFont affects newly created widgets; the matching
        # stylesheet font-size below also updates already-created widgets.
        app.setFont(font)
    except Exception:
        pass

    resolved_density = resolve_density(app, config.density)
    metrics = metrics_with_font_offset(
        metrics_for_density(resolved_density), config.font_offset_pt
    )
    try:
        app.setStyleSheet(_application_stylesheet(metrics, font_size_pt=font_size_pt, theme=config.theme))
    except Exception:
        pass

    # Make the current configuration/metrics available without introducing a
    # global singleton dependency into dialogs.
    app.setProperty("flexpes_ui_density_preference", config.density.value)
    app.setProperty("flexpes_ui_density_resolved", resolved_density.value)
    app.setProperty("flexpes_ui_font_offset_pt", int(config.font_offset_pt))
    app.setProperty("flexpes_ui_theme", config.theme.value)
    app.setProperty("flexpes_ui_metrics", metrics)
    return metrics


def current_ui_metrics() -> UiMetrics:
    """Return metrics resolved at application startup, or Standard as fallback."""

    app = QtWidgets.QApplication.instance()
    if app is not None:
        try:
            value = app.property("flexpes_ui_metrics")
            if isinstance(value, UiMetrics):
                return value
        except Exception:
            pass
    return metrics_for_density(InterfaceDensity.STANDARD)


def apply_control_metrics(widget: QtWidgets.QWidget) -> None:
    """Ensure accessibility fonts have room without shrinking tuned controls.

    The original minimum geometry of every control is remembered the first
    time it is seen. Generic metrics may enlarge a control, but never reduce a
    feature-specific minimum (for example the periodic-table element tiles).
    """

    metrics = current_ui_metrics()
    app = QtWidgets.QApplication.instance()
    try:
        font_offset = int(app.property("flexpes_ui_font_offset_pt") or 0) if app is not None else 0
    except Exception:
        font_offset = 0
    # Functional controls retain at least the Standard baseline. Compact mode
    # should reclaim whitespace rather than make buttons/spin boxes tiny.
    target_height = STANDARD_METRICS.standard_control_height + 2 * max(0, font_offset)
    control_types = (
        QtWidgets.QPushButton,
        QtWidgets.QComboBox,
        QtWidgets.QLineEdit,
        QtWidgets.QSpinBox,
        QtWidgets.QDoubleSpinBox,
    )
    try:
        controls = widget.findChildren(QtWidgets.QWidget)
    except Exception:
        controls = []
    for control in controls:
        if isinstance(control, control_types):
            try:
                original = control.property("flexpes_original_min_height")
                if original is None:
                    original = int(control.minimumHeight())
                    control.setProperty("flexpes_original_min_height", original)
                control.setMinimumHeight(max(int(original), target_height))
            except Exception:
                pass
    try:
        icon_size = QtCore.QSize(metrics.icon_size, metrics.icon_size)
        for button_type in (QtWidgets.QPushButton, QtWidgets.QToolButton):
            for button in widget.findChildren(button_type):
                button.setIconSize(icon_size)
    except Exception:
        pass


def _apply_registered_layout(layout, metrics: UiMetrics) -> None:
    try:
        role = str(layout.property(_LAYOUT_ROLE) or "")
    except Exception:
        role = ""
    try:
        if role == "panel":
            layout.setContentsMargins(metrics.panel_margin, metrics.panel_margin, metrics.panel_margin, metrics.panel_margin)
            layout.setSpacing(metrics.layout_spacing)
        elif role == "plain":
            layout.setSpacing(metrics.layout_spacing)
        elif role == "compact":
            layout.setSpacing(metrics.compact_spacing)
        elif role == "strip":
            layout.setContentsMargins(
                metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
                metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
            )
            layout.setSpacing(metrics.strip_spacing)
        elif role == "group":
            layout.setContentsMargins(
                metrics.group_margin_h, metrics.group_margin_top,
                metrics.group_margin_h, metrics.group_margin_bottom,
            )
            layout.setSpacing(metrics.group_spacing)
        elif role == "dialog":
            layout.setContentsMargins(metrics.dialog_margin, metrics.dialog_margin, metrics.dialog_margin, metrics.dialog_margin)
            layout.setSpacing(metrics.layout_spacing)
        elif role == "dialog_compact":
            layout.setContentsMargins(metrics.dialog_margin, metrics.dialog_margin, metrics.dialog_margin, metrics.dialog_margin)
            layout.setSpacing(metrics.compact_spacing)
    except Exception:
        pass


def refresh_existing_widgets(app: QtWidgets.QApplication | None = None) -> None:
    """Reapply shared metrics to existing windows after an appearance change."""

    app = app or QtWidgets.QApplication.instance()
    if app is None:
        return
    metrics = current_ui_metrics()
    try:
        widgets = list(app.allWidgets())
    except Exception:
        widgets = []
    for widget in widgets:
        try:
            role = str(widget.property(_WIDGET_ROLE) or "")
            if role == "loaded_tree":
                widget.setMinimumWidth(metrics.loaded_tree_min_width)
            elif role == "selected_tree":
                widget.setMinimumWidth(metrics.selected_tree_min_width)
            elif role == "progress":
                widget.setFixedHeight(metrics.progress_bar_height)
            elif role == "settings_button":
                widget.setFixedSize(metrics.standard_control_height, metrics.standard_control_height)
            elif role == "element_tile":
                try:
                    offset = int(app.property("flexpes_ui_font_offset_pt") or 0)
                except Exception:
                    offset = 0
                tile_min = 48 + 3 * max(0, offset)
                tile_max = 58 + 3 * max(0, offset)
                widget.setMinimumSize(tile_min, tile_min)
                widget.setMaximumHeight(tile_max)
            elif role == "periodic_table_pane":
                try:
                    offset = int(app.property("flexpes_ui_font_offset_pt") or 0)
                except Exception:
                    offset = 0
                # Five element columns must remain fully visible as their
                # accessibility-scaled tiles grow.  The 15 px/pt increment
                # corresponds to five columns growing by 3 px per font step.
                pane_min = 305 + 15 * max(0, offset)
                widget.setMinimumWidth(pane_min)
                parent = widget.parentWidget()
                if isinstance(parent, QtWidgets.QSplitter):
                    sizes = parent.sizes()
                    index = parent.indexOf(widget)
                    if 0 <= index < len(sizes) and sizes[index] < pane_min:
                        delta = pane_min - sizes[index]
                        sizes[index] = pane_min
                        # Preserve the total splitter width where possible by
                        # taking the extra room from the largest other pane.
                        others = [i for i in range(len(sizes)) if i != index]
                        if others:
                            donor = max(others, key=lambda i: sizes[i])
                            sizes[donor] = max(1, sizes[donor] - delta)
                        parent.setSizes(sizes)
            layout = widget.layout()
            if layout is not None:
                _apply_registered_layout(layout, metrics)
            widget.updateGeometry()
            widget.update()
        except Exception:
            pass
    # Apply control minimum sizes once per top-level window. Calling it for
    # every child would repeatedly traverse the same widget tree.
    try:
        for window in app.topLevelWidgets():
            apply_control_metrics(window)
    except Exception:
        pass
    try:
        app.processEvents()
    except Exception:
        pass


def apply_ui_configuration_live(config: UiConfiguration) -> UiMetrics:
    """Apply and persist an appearance configuration to the running GUI."""

    app = QtWidgets.QApplication.instance()
    if app is None:
        save_ui_configuration(config)
        return metrics_for_density(InterfaceDensity.STANDARD)
    save_ui_configuration(config)
    metrics = apply_application_style(app, config)
    refresh_existing_widgets(app)
    return metrics


def current_ui_configuration() -> UiConfiguration:
    """Return the persisted user preference."""

    return load_ui_configuration()


def apply_dialog_metrics(layout, *, compact: bool = False) -> None:
    """Apply shared margins/spacing to a dialog layout."""

    metrics = current_ui_metrics()
    margin = metrics.dialog_margin
    spacing = metrics.compact_spacing if compact else metrics.layout_spacing
    register_layout_role(layout, "dialog_compact" if compact else "dialog")
    try:
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(spacing)
    except Exception:
        pass
