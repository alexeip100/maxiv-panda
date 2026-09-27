from maxiv_panda.signal_identification.reference_data import (
    auger_eadl_records, auger_handbook_records, auger_records,
)


def test_auger_sources_load_separately():
    handbook = auger_handbook_records()
    eadl = auger_eadl_records()
    assert handbook and eadl
    assert all("XPS International Handbook" in str(r.get("source", "")) for r in handbook)
    assert all("EADL" in str(r.get("source", "")) for r in eadl)


def test_eadl_complements_co_lmm_without_replacing_handbook():
    handbook = [r for r in auger_handbook_records() if r.get("element") == "Co" and r.get("family") == "LMM"]
    combined = [r for r in auger_records() if r.get("element") == "Co" and r.get("family") == "LMM"]
    assert len(combined) >= len(handbook)
    assert any("EADL" in str(r.get("source", "")) for r in combined)
    energies = [float(r["kinetic_energy_eV"]) for r in combined]
    assert any(640 <= e <= 670 for e in energies)
    assert any(700 <= e <= 730 for e in energies)
    assert any(760 <= e <= 800 for e in energies)


def test_eadl_oxygen_kll_has_three_theoretical_clusters():
    values = [r for r in auger_eadl_records() if r.get("element") == "O" and r.get("family") == "KLL"]
    assert len(values) >= 3
    energies = sorted(float(r["kinetic_energy_eV"]) for r in values)
    assert energies[0] < 485 and energies[-1] > 505
