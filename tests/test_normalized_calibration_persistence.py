from pathlib import Path


def test_ecal_keeps_normalization_as_reversible_view_state():
    root = Path(__file__).resolve().parents[1]
    logic = (root / "src" / "maxiv_panda" / "workflows" / "calibration" / "calibrate_logic.py").read_text(encoding="utf-8")
    dialog = (root / "src" / "maxiv_panda" / "workflows" / "calibration" / "calibrate_dialog.py").read_text(encoding="utf-8")
    controller = (root / "src" / "maxiv_panda" / "processed_controller.py").read_text(encoding="utf-8")

    # Calibration is still fitted against the workflow payload (which may be normalized).
    assert "payload_by_key: Optional[Dict[str, Any]] = None" in logic
    assert "p = payload_by_key.get(sel_key) or payload_by_key.get(raw_key)" in logic
    assert "payload_by_key=payload_by_key" in dialog

    # Apply stores only the X-axis transform; Y comes from the underlying source.
    assert "base_payload = base_it.data(0, mw.ROLE_PAYLOAD)" in logic
    assert "y=np.asarray(base_payload.y, dtype=float).copy()" in logic
    assert "Normalization remains represented by its checkbox" in logic

    # Raw and E-cal children share one logical normalization signature.
    assert 'source_key = meta.get("source_key")' in controller
    assert "key_str = source_key" in controller
