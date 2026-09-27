from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from maxiv_panda.version import __version__
from . import fit_io, fit_models

FORMAT_NAME = "flexpes_pes_single_fit_result"
FORMAT_VERSION = 1


_PARAM_LABELS = {"E": "Energy", "H": "Height", "L": "LFWHM", "G": "GFWHM", "A": "Alpha"}
_BG_LABELS = {"b0": "b0", "b1": "b1", "b2": "b2", "bg_alpha": "alpha"}


def _clean_for_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_for_json(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_clean_for_json(v) for v in obj)
    try:
        if isinstance(obj, np.generic):
            return obj.item()
    except Exception:
        pass
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    return str(obj)


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def _param_to_dict(par: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for attr in ("value", "stderr", "min", "max", "vary", "expr", "brute_step", "init_value"):
        try:
            val = getattr(par, attr)
        except Exception:
            continue
        if attr == "expr" and val in (None, ""):
            continue
        out[attr] = _clean_for_json(val)
    return out


def suggest_single_fit_export_basename(metadata: Mapping[str, Any] | None = None) -> str:
    md = dict(metadata or {})
    parts = fit_io.compact_fit_identity_parts(
        md,
        curve_keys=("curve_label", "display_label", "curve_id"),
        include_anchor=False,
    )
    if not parts:
        title = str(md.get("payload_title") or "").strip()
        if title:
            parts.append(title)
    if not parts:
        parts.append("single_curve")
    stem = "_".join(fit_io.sanitize_filename_part(p, fallback="fit") for p in parts if p)
    if not stem.lower().endswith("_fit"):
        stem += "_fit"
    return stem


def _bg_type_label(bg_type: str) -> str:
    return str(bg_type or "background")


def build_single_fit_parameter_payload(dialog: Any, result: Any, fit_data: Mapping[str, Any], bg_type: str, status: str = "") -> Dict[str, Any]:
    metadata = dialog._current_fit_io_metadata() if hasattr(dialog, "_current_fit_io_metadata") else {}
    values = result.params.valuesdict() if result is not None else {}
    peak_areas: list[float] = []
    try:
        xu = np.asarray(fit_data.get("xu", []), dtype=float)
        yu = np.asarray(fit_data.get("yu", []), dtype=float)
        energy_scale = str(getattr(fit_data.get("payload"), "energy_scale", "") or "")
        bg_type_local = str(bg_type or "constant")
        _total, components = dialog._build_model_from_values(
            xu,
            bg_type=bg_type_local,
            values=values,
            measured_y=yu if bg_type_local == "Shirley" else None,
            energy_scale=energy_scale,
        )
        peak_areas = fit_models.integrated_component_areas(xu, components)
    except Exception:
        peak_areas = []
    metrics = {}
    try:
        metrics = dialog._compute_fit_quality_metrics(result, fit_data, bg_type)
    except Exception:
        metrics = {}
    bound_hits = sorted(str(x) for x in (getattr(dialog, "_last_fit_bound_hits", set()) or set()))
    peaks: list[dict[str, Any]] = []
    for idx, w in enumerate(getattr(dialog, "_peak_widgets", []) or [], start=1):
        try:
            label_edit = w.get("label_edit")
            label = str(label_edit.text()).strip() if label_edit is not None else f"P{idx}"
        except Exception:
            label = f"P{idx}"
        pinfo: Dict[str, Any] = {"index": idx, "label": label or f"P{idx}", "model": "Voigt/DS-Voigt", "parameters": {}}
        for prefix, human in _PARAM_LABELS.items():
            name = f"p{idx}_{prefix}"
            par = result.params.get(name) if result is not None and hasattr(result, "params") else None
            pd = _param_to_dict(par) if par is not None else {"value": _clean_for_json(values.get(name))}
            try:
                pd["mode"] = dialog._param_mode(w, prefix)
            except Exception:
                pd["mode"] = "Free" if pd.get("vary", True) else "Fixed"
            try:
                combo = w.get(f"{prefix}_mode")
                txt = str(combo.currentText()) if combo is not None else ""
                if txt:
                    pd["constraint"] = txt
            except Exception:
                pass
            if name in bound_hits:
                pd["near_or_at_bound"] = True
            pinfo["parameters"][human] = pd
        area_value = peak_areas[idx - 1] if idx - 1 < len(peak_areas) else float("nan")
        pinfo["parameters"]["Area"] = {
            "value": _clean_for_json(area_value),
            "derived": True,
            "definition": "Numerical integral of the fitted peak component over the fitted energy interval.",
        }
        peaks.append(pinfo)

    bg_params: Dict[str, Any] = {}
    for name in ("b0", "b1", "b2", "bg_alpha"):
        if result is not None and hasattr(result, "params") and name in result.params:
            bg_params[_BG_LABELS.get(name, name)] = _param_to_dict(result.params[name])
        elif name in values:
            bg_params[_BG_LABELS.get(name, name)] = {"value": _clean_for_json(values.get(name))}
    try:
        if str(bg_type) == "Shirley":
            bg_params.setdefault("alpha", {})["mode"] = "Fixed" if bool(dialog.chk_bg_alpha_fixed.isChecked()) else "Free"
    except Exception:
        pass

    try:
        nfev = int(getattr(result, "nfev", 0) or 0)
    except Exception:
        nfev = None
    try:
        success = bool(getattr(result, "success", False))
    except Exception:
        success = None
    try:
        message = str(getattr(result, "message", "") or "")
    except Exception:
        message = ""

    payload = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "software": {"name": "maxiv-panda", "version": __version__},
        "exported": datetime.now().isoformat(timespec="seconds"),
        "source": _clean_for_json(metadata),
        "fit_model": {
            "background": {"type": _bg_type_label(bg_type), "parameters": bg_params},
            "peaks": peaks,
        },
        "fit_quality": {
            "status": status or ("success" if success else "warning/failed"),
            "success": success,
            "message": message,
            "fit_evaluations": nfev,
            "rss": _clean_for_json(metrics.get("rss")),
            "rms_residual": _clean_for_json(metrics.get("rms")),
            "reduced_chi_square_poisson_estimate": _clean_for_json(metrics.get("redchi_poisson")),
            "parameters_near_or_at_bounds": bound_hits,
        },
    }
    return _clean_for_json(payload)


def build_single_fit_curves(dialog: Any, result: Any, fit_data: Mapping[str, Any], bg_type: str) -> tuple[list[str], list[list[Any]], Dict[str, Any]]:
    xu = np.asarray(fit_data.get("xu", []), dtype=float)
    yu = np.asarray(fit_data.get("yu", []), dtype=float)
    if xu.size == 0 or yu.size == 0 or xu.size != yu.size:
        raise ValueError("No valid fitted curve data are available for export.")
    try:
        energy_scale = str(getattr(fit_data.get("payload"), "energy_scale", "") or "")
    except Exception:
        energy_scale = ""
    vals = result.params.valuesdict() if result is not None else {}
    total, components = dialog._build_model_from_values(
        xu,
        bg_type=bg_type,
        values=vals,
        measured_y=yu if str(bg_type) == "Shirley" else None,
        energy_scale=energy_scale,
    )
    total = np.asarray(total, dtype=float)
    comp_arrays = [np.asarray(c, dtype=float) for c in (components or [])]
    peaks_sum = np.zeros_like(total)
    for c in comp_arrays:
        if c.shape == total.shape:
            peaks_sum = peaks_sum + c
    background = total - peaks_sum
    residual = yu - total
    peak_labels: list[str] = []
    for idx, w in enumerate(getattr(dialog, "_peak_widgets", []) or [], start=1):
        try:
            label_edit = w.get("label_edit")
            lab = str(label_edit.text()).strip() if label_edit is not None else ""
        except Exception:
            lab = ""
        lab = fit_io.sanitize_filename_part(lab or f"P{idx}", fallback=f"P{idx}")
        peak_labels.append(lab)
    headers = ["energy", "data", "total_fit", "background", "peaks_sum", "residual"]
    headers.extend([f"{lab}_component" for lab in peak_labels[:len(comp_arrays)]])
    rows: list[list[Any]] = []
    for i in range(xu.size):
        row = [xu[i], yu[i], total[i], background[i], peaks_sum[i], residual[i]]
        for comp in comp_arrays:
            row.append(comp[i] if comp.shape == xu.shape else float("nan"))
        rows.append(row)
    curve_meta = {
        "n_points": int(xu.size),
        "energy_scale": energy_scale,
        "columns": headers,
    }
    return headers, rows, curve_meta


def write_single_fit_parameters_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_clean_for_json(dict(payload)), indent=2, ensure_ascii=False), encoding="utf-8")


def _format_csv_value(value: Any) -> Any:
    try:
        v = float(value)
        if math.isfinite(v):
            return f"{v:.12g}"
        return ""
    except Exception:
        return value


def write_single_fit_curves_csv(
    path: str | Path,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    metadata: Mapping[str, Any] | None = None,
    include_metadata_header: bool = True,
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        if include_metadata_header:
            md = metadata or {}
            f.write("# PANDA single-curve fit curve export\n")
            f.write(f"# software_version: {__version__}\n")
            f.write(f"# exported: {datetime.now().isoformat(timespec='seconds')}\n")
            source = md.get("source") if isinstance(md.get("source"), dict) else {}
            if isinstance(source, dict):
                for key in ("source_file", "region", "curve_label", "display_label", "energy_scale"):
                    val = source.get(key)
                    if val:
                        f.write(f"# {key}: {val}\n")
            params_file = md.get("parameters_file")
            if params_file:
                f.write(f"# parameters_file: {params_file}\n")
            f.write("# columns: " + ", ".join(str(h) for h in headers) + "\n")
            f.write("\n")
        writer = csv.writer(f)
        writer.writerow(list(headers))
        for row in rows:
            writer.writerow([_format_csv_value(v) for v in row])


class SingleFitExportDialog(QDialog):
    def __init__(self, parent: Any, *, default_dir: Path, default_base: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export single-curve fit results")
        self.setModal(True)
        self.resize(620, 330)
        self._default_dir = Path(default_dir)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        intro = QLabel(
            "Choose a base name and output folder. The selected files below will be created with the corresponding extensions.",
            self,
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.ed_base = QLineEdit(default_base, self)
        form.addRow("Base name:", self.ed_base)

        folder_row = QHBoxLayout()
        self.ed_folder = QLineEdit(str(self._default_dir), self)
        self.btn_browse = QPushButton("Browse...", self)
        self.btn_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.ed_folder, 1)
        folder_row.addWidget(self.btn_browse, 0)
        form.addRow("Output folder:", folder_row)
        lay.addLayout(form)

        gb = QGroupBox("Files to be created", self)
        gb_lay = QVBoxLayout(gb)
        self.chk_json = QCheckBox("", gb)
        self.chk_json.setChecked(True)
        self.chk_json.setToolTip("Complete fit parameters, constraints, bounds, metadata, and fit-quality values.")
        self.chk_csv = QCheckBox("", gb)
        self.chk_csv.setChecked(True)
        self.chk_csv.setToolTip("Energy, data, total fit, background, residual, and peak component curves.")
        gb_lay.addWidget(self.chk_json)
        gb_lay.addWidget(QLabel("    Fit parameters, constraints, bounds, quality metrics, metadata", gb))
        gb_lay.addWidget(self.chk_csv)
        gb_lay.addWidget(QLabel("    Energy, data, total fit, background, residual, peak components", gb))
        lay.addWidget(gb)

        self.chk_csv_header = QCheckBox("Include metadata header in CSV", self)
        self.chk_csv_header.setChecked(False)
        lay.addWidget(self.chk_csv_header)

        self.lbl_preview = QLabel("", self)
        self.lbl_preview.setWordWrap(True)
        try:
            self.lbl_preview.setStyleSheet("QLabel { color: palette(mid); }")
        except Exception:
            pass
        lay.addWidget(self.lbl_preview)

        self.ed_base.textChanged.connect(self._update_preview)
        self.chk_json.toggled.connect(self._update_preview)
        self.chk_csv.toggled.connect(self._update_preview)
        self._update_preview()

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        try:
            bb.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        except Exception:
            pass
        bb.accepted.connect(self._accept_if_valid)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.ed_folder.text() or str(self._default_dir))
        if folder:
            self.ed_folder.setText(folder)
            self._update_preview()

    def _base(self) -> str:
        return fit_io.sanitize_filename_part(self.ed_base.text(), fallback="single_curve_fit")

    def selected_paths(self) -> Dict[str, Path]:
        folder = Path(self.ed_folder.text().strip() or str(self._default_dir))
        base = self._base()
        paths: Dict[str, Path] = {}
        if self.chk_json.isChecked():
            paths["json"] = folder / f"{base}_parameters.json"
        if self.chk_csv.isChecked():
            paths["csv"] = folder / f"{base}_curves.csv"
        return paths

    def include_csv_metadata(self) -> bool:
        return bool(self.chk_csv_header.isChecked())

    def _update_preview(self) -> None:
        paths = self.selected_paths()
        if not paths:
            self.lbl_preview.setText("No files selected.")
            return
        text = "Will create:\n" + "\n".join(f"• {p.name}" for p in paths.values())
        self.lbl_preview.setText(text)
        try:
            self.chk_json.setText(paths.get("json", Path("<not selected>")).name if self.chk_json.isChecked() else "JSON parameters file")
            self.chk_csv.setText(paths.get("csv", Path("<not selected>")).name if self.chk_csv.isChecked() else "CSV curves file")
        except Exception:
            pass

    def _accept_if_valid(self) -> None:
        if not self.chk_json.isChecked() and not self.chk_csv.isChecked():
            QMessageBox.warning(self, "Nothing selected", "Select at least one file to export.")
            return
        folder = Path(self.ed_folder.text().strip() or ".")
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.critical(self, "Invalid folder", f"Could not create/use output folder:\n\n{exc}")
            return
        existing = [p.name for p in self.selected_paths().values() if p.exists()]
        if existing:
            msg = "The following file(s) already exist and will be overwritten:\n\n" + "\n".join(existing) + "\n\nContinue?"
            if QMessageBox.question(self, "Overwrite existing files?", msg, QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Ok:
                return
        self.accept()


def export_single_fit_results(dialog: Any) -> None:
    result = getattr(dialog, "_last_fit_result", None)
    fit_data = getattr(dialog, "_last_fit_data", None)
    bg_type = getattr(dialog, "_last_fit_bg_type", None)
    if result is None or fit_data is None or not bg_type:
        QMessageBox.warning(dialog, "No fit results", "Run a successful fit before exporting fit results.")
        return
    metadata = dialog._current_fit_io_metadata() if hasattr(dialog, "_current_fit_io_metadata") else {}
    default_base = suggest_single_fit_export_basename(metadata)
    try:
        default_dir = dialog._fit_io_default_dir()
    except Exception:
        default_dir = Path.home()
    dlg = SingleFitExportDialog(dialog, default_dir=Path(default_dir), default_base=default_base)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    paths = dlg.selected_paths()
    written: list[Path] = []
    try:
        param_payload = build_single_fit_parameter_payload(
            dialog,
            result,
            fit_data,
            str(bg_type),
            status=str(getattr(dialog, "_last_fit_status", "") or ""),
        )
        if "json" in paths:
            write_single_fit_parameters_json(paths["json"], param_payload)
            written.append(paths["json"])
        if "csv" in paths:
            headers, rows, curve_meta = build_single_fit_curves(dialog, result, fit_data, str(bg_type))
            csv_meta = dict(param_payload)
            csv_meta["curve_export"] = curve_meta
            if "json" in paths:
                csv_meta["parameters_file"] = paths["json"].name
            write_single_fit_curves_csv(
                paths["csv"],
                headers,
                rows,
                metadata=csv_meta,
                include_metadata_header=dlg.include_csv_metadata(),
            )
            written.append(paths["csv"])
        if written:
            try:
                if hasattr(dialog, "_remember_fit_io_dir"):
                    dialog._remember_fit_io_dir(str(written[0]))
            except Exception:
                pass
            msg = "Export completed.\n\nCreated:\n" + "\n".join(f"{i+1}. {p.name}" for i, p in enumerate(written))
            QMessageBox.information(dialog, "Export completed", msg)
    except Exception as exc:
        QMessageBox.critical(dialog, "Export failed", f"Could not export fit results:\n\n{exc}")
