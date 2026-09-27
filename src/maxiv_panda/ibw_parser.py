from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

import numpy as np

from .energy_utils import infer_energy_scale, normalize_energy_xlabel, extract_energy_unit
from .txt_parser import RegionData


@dataclass
class ParsedIBW:
    """Parsed representation of an IBW file.

    We keep this compatible with the UI expectations for ParsedTXT:
    - .path
    - .file_info (dict)
    - .regions (list of RegionData)

    Most IBW files contain a single wave and thus a single "region". If, in the
    future, you encounter packed IBW-like content with multiple waves, this can
    be extended to populate multiple regions.
    """

    path: Path
    file_info: dict[str, str] = field(default_factory=dict)
    regions: list[RegionData] = field(default_factory=list)


def _guess_region_name_from_filename(path: Path) -> str:
    stem = path.stem
    # Common examples:
    #   XPS_0012N1s -> N1s
    #   XPS_0011N1s_FE -> N1s_FE
    #   XPS_0005Ir4f_170eV -> Ir4f_170eV
    #   XPS_0009C1s 400eV -> C1s 400eV
    # Strategy: remove leading XPS_#### but KEEP the rest, because
    # qualifiers like "_FE" or "400eV" can be semantically important.
    s = stem
    if s.startswith("XPS_"):
        s = s[4:]
    # Remove leading digits
    while s and s[0].isdigit():
        s = s[1:]
    s = s.lstrip("_ ")
    # Normalize whitespace (but keep underscores etc.)
    s = " ".join(s.split())
    return s.strip() or stem


def _choose_region_name(note_name: str, wave_name: str, guessed: str) -> str:
    """Choose a region name, preferring more specific names.

    Notes/wave names can be generic (e.g. "C1s") while the filename may
    contain qualifiers (e.g. "C1s_FE" or "C1s 400eV"). If the note-derived
    name is a strict substring of the filename-derived name, we take the
    filename-derived one.
    """

    # Priority order: note -> wave -> filename.
    chosen = note_name.strip() or wave_name.strip() or guessed.strip()
    if not chosen:
        return "(unknown)"

    # Prefer filename-derived if it contains extra qualifiers beyond a generic name.
    if guessed and chosen and chosen != guessed:
        c_low = chosen.lower()
        g_low = guessed.lower()
        if c_low in g_low and len(guessed) > len(chosen) + 1:
            chosen = guessed
    return chosen


def _choose_region_name_from_metadata(
    note_kv: dict[str, str], wave_name: str, guessed: str
) -> str:
    """Choose the semantic IBW spectrum/region name for GUI and workflows.

    Scienta multi-region IBW exports commonly retain a generic ``Spectrum Name``
    while ``Region Name`` identifies the measured spectral window.  Prefer the
    latter to match the structured TXT representation, with conservative
    fallbacks for older/simpler IBWs.
    """
    note_name = (
        note_kv.get("Region Name")
        or note_kv.get("Region")
        or note_kv.get("Spectrum Name")
        or ""
    )
    return _choose_region_name(str(note_name), str(wave_name), str(guessed))


def _parse_note(note: Any) -> tuple[dict[str, str], str]:
    """Parse wave note.

    Returns (kv_dict, raw_string).

    Igor notes often use '\r' line separators and 'key: value' formatting.
    """

    raw = ""
    try:
        if isinstance(note, (bytes, bytearray)):
            raw = bytes(note).decode(errors="replace")
        else:
            raw = str(note)
    except Exception:
        raw = ""

    kv: dict[str, str] = {}
    # Split on CR and LF to be safe.  Scienta CIS/ResPES notes can contain
    # hundreds of ``Point N=<value> eV`` entries.  Those values define the
    # second-dimension axis and are parsed separately by
    # ``_extract_point_axis_from_note``.  Keeping every Point entry in the
    # generic metadata makes each Qt tree leaf carry a very large QVariantMap
    # and is especially expensive under PyQt6.
    point_key_re = re.compile(r"^Point\s+\d+$", re.IGNORECASE)
    for ln in raw.replace("\n", "\r").split("\r"):
        ln = ln.strip()
        if not ln:
            continue
        # Scienta notes predominantly use ``key=value`` and values may
        # themselves contain colons (Windows paths, HH:MM:SS times).  Split on
        # '=' first; otherwise ``Time=14:47:07`` would become key ``Time=14``.
        if "=" in ln:
            k, v = ln.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k and not point_key_re.match(k):
                kv[k] = v
        elif ":" in ln:
            k, v = ln.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k and not point_key_re.match(k):
                kv[k] = v
    return kv, raw



def _parse_note_sections(raw: str) -> dict[str, dict[str, str]]:
    """Parse bracketed Scienta metadata blocks from an Igor wave note.

    The note starts with ordinary acquisition key/value lines, followed by
    blocks such as ``[Run Mode Information]`` and ``[Manipulator]``.  Keep
    those blocks grouped for the metadata viewer.  Large ``Point N`` lists are
    compacted by the same helper used for TXT exports.
    """
    from .txt_parser import _compact_section_metadata

    out: dict[str, dict[str, str]] = {}
    current: str | None = None
    current_values: dict[str, str] = {}

    def flush() -> None:
        nonlocal current, current_values
        if current is not None:
            compact = _compact_section_metadata(current_values)
            if compact:
                out[current] = compact
        current = None
        current_values = {}

    for line in str(raw or "").replace("\n", "\r").split("\r"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]") and len(line) > 2:
            flush()
            current = line[1:-1].strip()
            continue
        if current is None:
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        key = key.strip()
        if key:
            current_values[key] = value.strip()
    flush()
    return out


def _read_ibw_text_fallback(path: Path) -> str:
    """Best-effort printable-text fallback for Scienta metadata embedded in IBW.

    Some igor2 versions/export variants do not expose all trailing Scienta text
    through ``wave["note"]``.  The binary file still contains the axis descriptor
    and CIS/ResPES ``Point N=<value> eV`` sequence as plain ASCII.  Decode only
    for metadata recovery; wave data still comes from igor2.
    """
    try:
        raw = path.read_bytes()
    except Exception:
        return ""
    # Preserve CR/LF and printable ASCII, replace binary bytes with spaces so
    # regex matching cannot accidentally bridge binary regions.
    chars = []
    for b in raw:
        if b in (9, 10, 13) or 32 <= b <= 126:
            chars.append(chr(b))
        else:
            chars.append(" ")
    return "".join(chars)


def _detect_dim2_label_from_note(note_kv: dict[str, str], note_raw: str) -> str:
    """Return a positively identified second-dimension label for an IBW note.

    Do not infer photon energy merely because dimension 2 has a numeric Igor
    scale.  Ordinary Scienta Add Dimension acquisitions often use dimension 2
    for repeated iterations and may still have a perfectly valid affine scale.
    ResPES must therefore require explicit photon-energy evidence.
    """
    explicit = str(
        note_kv.get("Dimension 2 name")
        or note_kv.get("Dimension 2 Name")
        or note_kv.get("Dimension 2")
        or ""
    ).strip()
    if explicit:
        return explicit

    raw = " ".join(str(note_raw or "").split())
    low = raw.lower()
    if "photon energy" in low:
        return "Photon Energy [eV]"
    if re.search(r"\bregion\s+iteration\s*(?:\[[^\]]*\])?", raw, re.IGNORECASE):
        return "Region Iteration [a.u.]"
    if re.search(r"\biteration\s*(?:\[[^\]]*\])", raw, re.IGNORECASE):
        return "Iteration [a.u.]"
    return ""


def _extract_point_axis_from_note(note: str, expected_n: int | None = None) -> list[float] | None:
    """Extract an explicit Scienta ``Point N=<value> eV`` axis from a wave note.

    CIS notes may contain a coarse point list followed by the actual fine scan.
    Later occurrences of the same point number replace earlier ones, so the
    final complete sequence is retained.
    """
    import re

    values: dict[int, float] = {}
    # Scienta notes commonly use bare carriage returns (\r) as record
    # separators.  Python's multiline anchors recognize \n boundaries, not
    # bare \r, so normalize line endings before matching Point records.
    normalized_note = str(note or "").replace("\r\n", "\n").replace("\r", "\n")
    pattern = re.compile(
        r"(?im)^\s*Point\s+(\d+)\s*=\s*([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)\s*eV\s*$"
    )
    for match in pattern.finditer(normalized_note):
        try:
            values[int(match.group(1))] = float(match.group(2))
        except Exception:
            continue
    if not values:
        return None
    n = int(expected_n) if expected_n is not None else max(values)
    if n <= 0 or any(i not in values for i in range(1, n + 1)):
        return None
    return [values[i] for i in range(1, n + 1)]

def parse_ibw(path: Path) -> ParsedIBW:
    """Parse an Igor Binary Wave (.ibw) file using igor2.

    This requires the `igor2` package.

    Returns a ParsedIBW that is compatible with the GUI tree/plot logic.
    """

    try:
        from igor2 import binarywave  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "The 'igor2' package is required to load IBW files. "
            "Install it in your environment (e.g. pip install igor2)."
        ) from exc

    ibw = binarywave.load(str(path))

    wave = ibw.get("wave", {})
    wdata = wave.get("wData")
    if wdata is None:
        raise ValueError("IBW file does not contain wave data (wData).")

    data = np.asarray(wdata)

    # Extract scaling for each dimension.
    # According to igor2's return structure, these live in wave_header.
    wh = wave.get("wave_header", {})
    sfA = np.asarray(wh.get("sfA", [1.0, 1.0, 1.0, 1.0]), dtype=float)
    sfB = np.asarray(wh.get("sfB", [0.0, 0.0, 0.0, 0.0]), dtype=float)
    nDim = np.asarray(wh.get("nDim", list(data.shape) + [0, 0, 0, 0]), dtype=int)

    # Dimension units (concatenated string with per-dim sizes in bin_header).
    dim_units = ""
    try:
        dim_units = wave.get("dimension_units", b"").decode(errors="replace")
    except Exception:
        try:
            dim_units = str(wave.get("dimension_units", ""))
        except Exception:
            dim_units = ""

    # Notes and region name
    note_kv, note_raw = _parse_note(wave.get("note"))
    note_sections = _parse_note_sections(note_raw)
    file_text_fallback = _read_ibw_text_fallback(path)

    # Determine Energy Scale metadata if possible.
    # Prefer explicit scale metadata and explicit axis-label text.
    # Do not let generic fields such as "Energy Unit" override a clear scale declaration.
    energy_scale_field = (
        note_kv.get("Energy Scale")
        or note_kv.get("EnergyScale")
        or note_kv.get("Scale Representation")
        or note_kv.get("X Scale")
        or note_kv.get("XScale")
        or ""
    ).strip()

    axis_label_hint = (
        str(note_kv.get("Axis Label") or "")
        or str(note_kv.get("X Label") or "")
        or str(note_kv.get("Label") or "")
    ).strip()

    # Some Scienta/SES exports do not store a dedicated x-label key, but they do
    # embed the axis label into the trailing raw note text, e.g.
    #   "Counts [a.u.]Binding Energy [eV]"
    # or
    #   "Counts [a.u.]Kinetic Energy [eV]"
    # Use this only as an extra hint when explicit label keys are absent.
    if not axis_label_hint and note_raw:
        raw_compact = " ".join(str(note_raw).split())
        if "Binding Energy" in raw_compact:
            axis_label_hint = "Binding Energy [eV]"
        elif "Kinetic Energy" in raw_compact:
            axis_label_hint = "Kinetic Energy [eV]"

    guessed_from_filename = _guess_region_name_from_filename(path)
    _hint_parts = [
        str(note_kv.get("Spectrum Name") or ""),
        str(note_kv.get("Region") or ""),
        str(note_kv.get("Region Name") or ""),
        guessed_from_filename,
    ]
    low = " ".join(_hint_parts).lower()
    raw_low = (note_raw or "").lower()
    axis_low = axis_label_hint.lower()

    energy_scale = infer_energy_scale(
        energy_scale_field,
        hints=[axis_label_hint, raw_low, low],
    )

    # Build an explicit x-label. Once the scale is known, prefer a concrete label
    # over a generic "Energy" fallback.
    preferred_label = axis_label_hint or "Energy [eV]"
    unit = dim_units.strip() if dim_units.strip() and len(dim_units.strip()) <= 12 else extract_energy_unit(preferred_label, default="eV")
    xlabel = normalize_energy_xlabel(preferred_label, energy_scale, unit=unit)


    # Detect the second-dimension identity from explicit metadata/note text.
    # A numeric Igor dimension scale alone is not evidence of photon energy:
    # ordinary Add Dimension acquisitions can use the same mechanism for
    # repeated Region Iteration scans.
    dim2_label = _detect_dim2_label_from_note(note_kv, note_raw)
    if not dim2_label and file_text_fallback:
        dim2_label = _detect_dim2_label_from_note({}, file_text_fallback)

    # Wave name (may be bytes)
    wave_name = None
    for key in ("wave_name", "name"):
        if key in wave:
            wave_name = wave.get(key)
            break
    if wave_name is None and "bname" in wave:
        wave_name = wave.get("bname")

    wname_str = ""
    if wave_name is not None:
        try:
            if isinstance(wave_name, (bytes, bytearray)):
                wname_str = wave_name.decode(errors="replace")
            else:
                wname_str = str(wave_name)
        except Exception:
            wname_str = ""

    # Scienta multi-region acquisitions exported as separate IBW waves often
    # keep a generic ``Spectrum Name``/wave name (for example ``XPS_022_2``)
    # but also store the actual spectral region in ``Region Name`` (for
    # example ``S2p_700eV``).  Match the structured TXT parser and prefer that
    # semantic region name.  Fall back to the older fields for IBWs that do not
    # provide it.
    region_name = _choose_region_name_from_metadata(
        note_kv, wname_str, guessed_from_filename
    )

    parsed = ParsedIBW(path=path)
    parsed.file_info = {
        "Format": "IBW",
        "Wave name": wname_str.strip() or "(unknown)",
    }

    reg = RegionData(index=1)
    reg.info_meta["Spectrum Name"] = region_name
    reg.info_meta["Wave name"] = wname_str.strip()
    reg.info_meta["Energy Scale"] = energy_scale
    # Do not retain the complete raw wave note in per-curve metadata.  On
    # large CIS/ResPES waves it contains hundreds of Point entries and can be
    # hundreds of kilobytes long.  All metadata needed downstream has already
    # been extracted above, including the energy scale and second-dimension
    # axis.  Avoiding the raw note keeps Qt tree-item metadata compact.

    # Preserve bracketed acquisition metadata (Manipulator, Run Mode, ...)
    # as grouped sections.  Keep the traditional flat note mapping for
    # compatibility, but avoid duplicating section-only keys in info_meta.
    reg.section_meta = {name: dict(values) for name, values in note_sections.items()}
    section_keys = {key for values in note_sections.values() for key in values}
    for k, v in note_kv.items():
        if k not in reg.info_meta and k not in section_keys:
            reg.info_meta[k] = v

    # Provide dimension hints.
    reg.region_meta["Dimension 1 name"] = xlabel
    reg.region_meta["Dimension 1 size"] = str(int(data.shape[0]) if data.size else 0)

    # Build numeric matrix compatible with TXT traces conversion.
    # - If 1D: two columns: x, y
    # - If 2D: first column x, then columns for each iteration
    # - If >2D: flatten remaining dims into iteration index
    if data.ndim == 1:
        n = data.shape[0]
        x = sfB[0] + sfA[0] * np.arange(n)
        mat = np.column_stack([x, data.astype(float)])
    else:
        n = data.shape[0]
        x = sfB[0] + sfA[0] * np.arange(n)
        yblock = data
        if data.ndim > 2:
            # Flatten dims 1.. into iterations
            yblock = data.reshape((n, int(np.prod(data.shape[1:]))))
            reg.warnings.append(
                f"Wave has {data.ndim} dimensions; flattened dims 2.. into {yblock.shape[1]} iterations."
            )
        # Ensure 2D (n, m)
        if yblock.shape[0] != n:
            # If orientation seems swapped, try transpose.
            if yblock.shape[1] == n:
                yblock = yblock.T
                reg.warnings.append("Transposed wave data to match x dimension.")
            else:
                reg.warnings.append(
                    f"Unexpected wave shape {data.shape}; using first axis as x dimension."
                )
        mat = np.column_stack([x, yblock.astype(float)])
        dim2_n = int(mat.shape[1] - 1)
        reg.region_meta["Dimension 2 size"] = str(dim2_n)
        if dim2_n > 0:
            # Scienta CIS/ResPES IBWs commonly preserve the actual photon
            # energies explicitly in the wave note as ``Point N=<value> eV``.
            # Prefer that sequence over generic Igor affine dimension scaling:
            # some Scienta exports have incomplete/unreliable sfA/sfB metadata
            # for dimension 2 even though the CIS point list is complete.
            dim2_vals = _extract_point_axis_from_note(note_raw or "", dim2_n)
            if dim2_vals is None and file_text_fallback:
                dim2_vals = _extract_point_axis_from_note(file_text_fallback, dim2_n)
            if dim2_vals is None:
                try:
                    affine_vals = sfB[1] + sfA[1] * np.arange(dim2_n, dtype=float)
                    if np.all(np.isfinite(affine_vals)) and abs(float(sfA[1])) > 0:
                        dim2_vals = [float(v) for v in affine_vals]
                except Exception:
                    dim2_vals = None
            if dim2_vals is not None:
                reg.region_meta["Dimension 2 scale"] = " ".join(f"{v:.12g}" for v in dim2_vals)
            if dim2_label:
                reg.region_meta["Dimension 2 name"] = dim2_label

    reg.data = mat
    parsed.regions.append(reg)
    return parsed
