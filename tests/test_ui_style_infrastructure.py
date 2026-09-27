from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "maxiv_panda"


def test_application_style_is_centralised_and_keeps_baseline_policy():
    app = (PKG / "app.py").read_text(encoding="utf-8")
    style = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert "apply_application_style(app)" in app
    assert 'app.setStyle("Fusion")' in style
    assert "BASELINE_FONT_INCREMENT = 2" in style
    assert "BASELINE_FONT_INCREMENT + int(config.font_offset_pt)" in style


def test_density_api_has_distinct_standard_and_compact_profiles():
    metrics = (PKG / "ui_metrics.py").read_text(encoding="utf-8")
    assert 'AUTOMATIC = "automatic"' in metrics
    assert 'STANDARD = "standard"' in metrics
    assert 'COMPACT = "compact"' in metrics
    assert "STANDARD_METRICS = UiMetrics(" in metrics
    assert "COMPACT_METRICS = UiMetrics(" in metrics
    assert "resolve_automatic_density" in metrics


def test_development_audit_is_not_shipped():
    assert not (ROOT / "docs" / "ui_style_audit.md").exists()
