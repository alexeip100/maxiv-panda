from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_dark_contrast_polish_is_dark_only():
    source = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert "if theme is not UiTheme.DARK" in source
    assert "QSplitter::handle { background: #5d5d5d; }" in source
    assert "QScrollBar::handle:vertical, QScrollBar::handle:horizontal" in source
    assert "QTabBar::tab:selected" in source


def test_dark_tabs_are_visually_separated_and_readable():
    source = (PKG / "ui_style.py").read_text(encoding="utf-8")
    dark = source.split('dark_contrast = """', 1)[1].split('"""', 1)[0]
    assert "padding: 4px 10px" in dark
    assert "margin-right: 2px" in dark
    assert "color: #dddddd" in dark
    assert "color: #ffffff" in dark


def test_dark_disabled_palette_is_readable_for_window_and_control_text():
    source = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert "disabled_text = QtGui.QColor(184, 184, 184)" in source
    assert "ColorRole.WindowText, disabled_text" in source
    assert "ColorRole.Text, disabled_text" in source
    assert "ColorRole.ButtonText, disabled_text" in source


def test_application_stylesheet_receives_active_theme():
    source = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert "theme=config.theme" in source


def test_dark_checkboxes_use_conventional_proxy_checkmarks_and_radios_remain_visible():
    source = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert "class FlexPESCheckStyle" in source
    assert "PE_IndicatorCheckBox" in source
    assert "PE_IndicatorItemViewItemCheck" in source
    assert "painter.drawPath(path)" in source
    assert "QCheckBox:disabled { color: #bdbdbd; }" in source
    assert "QRadioButton::indicator:unchecked" in source


def test_dark_editors_and_item_views_have_explicit_contrast():
    source = (PKG / "ui_style.py").read_text(encoding="utf-8")
    dark = source.split('dark_contrast = """', 1)[1].split('"""', 1)[0]
    assert "QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox" in dark
    assert "QTreeView, QTableView, QListView, QListWidget, QTreeWidget, QTableWidget" in dark
    assert "selection-background-color: #3069aa" in dark


def test_plotted_curve_row_uses_palette_aware_text_and_background():
    source = (PKG / "workflows" / "plotting" / "curve_item.py").read_text(encoding="utf-8")
    assert "background: palette(base)" in source
    assert "color: palette(text)" in source
    assert "background: #f5f5f5" not in source


def test_reference_panels_use_palette_surfaces_instead_of_fixed_light_surfaces():
    for name in ("cross_section_reference.py", "binding_energy_reference.py", "dialogs.py"):
        source = (PKG / "signal_identification" / name).read_text(encoding="utf-8")
        assert "background: palette(base)" in source or "background: palette(window)" in source
        assert "#ffffff" not in source.lower()
        assert "#eef1f4" not in source.lower()


def test_peakfit_result_tables_do_not_force_white_cells():
    source = (PKG / "workflows" / "peakfit" / "fit_widgets.py").read_text(encoding="utf-8")
    assert "background: palette(base)" in source
    assert 'QColor("white")' not in source
    assert 'QColor("black")' not in source


def test_map_overlay_checkbox_stays_readable_on_light_canvas():
    source = (PKG / "ui_map_plot_mixin.py").read_text(encoding="utf-8")
    assert 'QCheckBox { color: #202020; spacing: 5px; }' in source
    assert 'QCheckBox:disabled { color: #606060; }' in source
    assert 'QCheckBox::indicator' not in source[source.index('def _create_map_qt_overlay_checkbox'):source.index('def ', source.index('def _create_map_qt_overlay_checkbox') + 10)]


def test_dark_tree_and_list_item_check_indicators_use_same_proxy_checkmark():
    source = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert "PE_IndicatorItemViewItemCheck" in source
    assert "State_On" in source
    assert "State_NoChange" in source
    assert "background: #4c9bd6" not in source


def test_dark_checkbox_checked_state_is_conventional_check_mark():
    source = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert "path.moveTo" in source
    assert "path.lineTo" in source
    assert "painter.drawPath(path)" in source


def test_help_rich_text_uses_active_palette_colors():
    source = (PKG / "utils" / "help_text.py").read_text(encoding="utf-8")
    assert "def _help_palette_colors" in source
    assert 'pal.color(role.Text).name()' in source
    assert 'pal.color(role.AlternateBase).name()' in source
    assert '#174f82' not in source
    assert '#eaf4fb' not in source


def test_map_overlay_checkbox_uses_shared_checkmark_indicator():
    source = (PKG / "ui_map_plot_mixin.py").read_text(encoding="utf-8")
    block = source[source.index('def _create_map_qt_overlay_checkbox'):]
    assert "QCheckBox::indicator" not in block[:block.index('def ', 10)]
