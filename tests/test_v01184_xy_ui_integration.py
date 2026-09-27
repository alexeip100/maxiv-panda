from __future__ import annotations

from pathlib import Path

from maxiv_panda.specs_xy_adapter import parse_and_adapt_specs_xy
from maxiv_panda.txt_parser import region_to_traces


def _write_series(path: Path) -> Path:
    path.write_text(
        """# Energy Axis: Binding Energy
# Group: XPS
# Region: O1s
# Spectrum ID: 42
# Cycle: 0, Curve: 0, Scan: 0
# ColumnLabels: energy counts/s
535 10
534 20
# Cycle: 1, Curve: 0, Scan: 1
# ColumnLabels: energy counts/s
535 30
534 40
""",
        encoding="latin-1",
    )
    return path


def test_xy_adapter_output_is_ready_for_existing_raw_tree_trace_contract(tmp_path):
    parsed = parse_and_adapt_specs_xy(_write_series(tmp_path / "series.xy"))
    assert parsed.path.suffix == ".xy"
    assert len(parsed.regions) == 1
    region = parsed.regions[0]
    traces = region_to_traces(region)
    assert region.region_name == "O1s"
    assert [t["kind"] for t in traces] == ["average", "iteration", "iteration"]
    assert region.dim2_name() == "Iteration"
    assert region.dim2_scale() == [1.0, 2.0]


def test_ui_shell_registers_xy_without_routing_it_through_txt_or_ibw_parsers():
    root = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"
    loaders = (root / "loaders.py").read_text(encoding="utf-8")
    ui = (root / "ui.py").read_text(encoding="utf-8")
    actions = (root / "ui_actions_mixin.py").read_text(encoding="utf-8")
    reloads = (root / "ui_source_reload_mixin.py").read_text(encoding="utf-8")

    assert "parse_and_adapt_specs_xy" in loaders
    assert "if kind == 'XY'" in loaders
    assert "XY (SPECS Prodigy)" in ui
    assert "endswith('.xy')" in ui
    assert "'.xy'" in actions and "'XY'" in actions
    assert 'suffix == ".xy"' in reloads and '"XY"' in reloads


def test_txt_and_ibw_parser_modules_have_no_xy_specific_logic():
    root = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"
    txt = (root / "txt_parser.py").read_text(encoding="utf-8").lower()
    ibw = (root / "ibw_parser.py").read_text(encoding="utf-8").lower()
    assert "specs_xy" not in txt and ".xy" not in txt
    assert "specs_xy" not in ibw and ".xy" not in ibw
