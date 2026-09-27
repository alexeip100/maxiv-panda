from pathlib import Path

from maxiv_panda.ibw_parser import (
    _detect_dim2_label_from_note,
    _extract_point_axis_from_note,
    _read_ibw_text_fallback,
)


def test_scienta_cr_separated_respes_points_are_extracted(tmp_path: Path):
    payload = (
        b"binary\x00junk"
        b"Counts [a.u.]Binding Energy [eV]Photon Energy [eV]\r"
        b"[Run Mode Information]\rName=CIS\r"
        b"Point 1=770 eV\rPoint 2=770.1 eV\rPoint 3=770.2 eV\r"
    )
    path = tmp_path / "respes.ibw"
    path.write_bytes(payload)
    text = _read_ibw_text_fallback(path)

    assert _detect_dim2_label_from_note({}, text) == "Photon Energy [eV]"
    assert _extract_point_axis_from_note(text, 3) == [770.0, 770.1, 770.2]


def test_iteration_axis_is_not_promoted_to_photon_energy(tmp_path: Path):
    payload = (
        b"binary\x00junk"
        b"Counts [a.u.]Binding Energy [eV]Region Iteration[a.u.]\r"
        b"[Run Mode Information]\rName=Add Dimension\r"
    )
    path = tmp_path / "iteration.ibw"
    path.write_bytes(payload)
    text = _read_ibw_text_fallback(path)

    assert _detect_dim2_label_from_note({}, text) == "Region Iteration [a.u.]"
    assert _extract_point_axis_from_note(text) is None
