"""Energy calibration orchestration helpers.

Step-4 refactor: introduce a small host adapter so the calibration workflow
doesn't directly depend on MainWindow internals everywhere.

This module intentionally stays lightweight for now (no behavior changes).
"""

from __future__ import annotations

from ...common import CalibrationHost
from ...energy_utils import normalize_energy_xlabel

from typing import Any, Dict, Optional, Tuple


class CalibrationLogic:
    """Non-UI helpers for the calibration workflow.

    This is an incremental refactor step: we move small chunks of logic
    (like plotting helpers) out of the dialog code to reduce file size
    and improve maintainability, without changing behavior.
    """

    def __init__(self, host: CalibrationHost) -> None:
        self.host = host

    def _reconstruct_fit_curve(self, fr: Dict[str, Any], pl: Any) -> Tuple[Optional[Any], Optional[Any]]:
        """Return (fit_x, fit_y) for plotting.

        For core-level fits we intentionally rebuild the fitted curve on a dense
        grid from the saved model parameters and fit window. This makes
        multi-reference "Plot all" overlays faithfully show doublets instead of
        looking like sparse, imperfect single-peak traces.
        """
        try:
            import numpy as _np
            from .fitters import _voigt_profile

            params = fr.get("params") or {}
            kind = str(fr.get("kind") or "")
            model = str(fr.get("model") or "")

            # Core-level fits: always reconstruct on a dense grid.
            if kind == 'core_level':
                fit_window = fr.get('fit_window') or (None, None)
                x0, x1 = fit_window
                if x0 is None or x1 is None:
                    x_src = _np.asarray(getattr(pl, 'x', []), dtype=float)
                    if x_src.size == 0:
                        return None, None
                    x0 = float(_np.nanmin(x_src))
                    x1 = float(_np.nanmax(x_src))
                x0 = float(x0)
                x1 = float(x1)
                if not (_np.isfinite(x0) and _np.isfinite(x1)):
                    return None, None
                if x1 < x0:
                    x0, x1 = x1, x0
                npts = max(800, int(abs(x1 - x0) * 500))
                x = _np.linspace(x0, x1, npts)

                if model == 'doublet':
                    a1 = float(params.get('a1', 0.0))
                    a2 = params.get('a2')
                    ratio = params.get('ratio')
                    cen1 = float(params.get('cen1'))
                    cen2 = float(params.get('cen2'))
                    sigma = float(params.get('sigma', 0.15))
                    gamma = float(params.get('gamma', 0.15))
                    b = float(params.get('b', 0.0))
                    c = float(params.get('c', 0.0))
                    if ratio is not None:
                        a2f = a1 * float(ratio)
                    else:
                        a2f = float(a2 if a2 is not None else 0.0)
                    y = (_voigt_profile(x, a1, cen1, sigma, gamma)
                         + _voigt_profile(x, a2f, cen2, sigma, gamma)
                         + b + c * x)
                    return x, y

                amp = float(params.get('amp', 0.0))
                cen = float(params.get('cen'))
                sigma = float(params.get('sigma', 0.15))
                gamma = float(params.get('gamma', 0.15))
                b = float(params.get('b', 0.0))
                c = float(params.get('c', 0.0))
                y = _voigt_profile(x, amp, cen, sigma, gamma) + b + c * x
                return x, y

            # Non-core-level fits: reuse saved arrays if present.
            fx = fr.get("fit_x")
            fy = fr.get("fit_y")
            if fx is not None and fy is not None:
                return fx, fy
        except Exception:
            return None, None

        return None, None

    def plot_all_references(self, ax: Any, canvas: Any, fit_table: Any,
                            fit_results: Dict[str, Any],
                            payload_by_key: Dict[str, Any]) -> None:
        """Plot all reference curves and their fits (if available)."""
        if ax is None or canvas is None:
            return
        try:
            import numpy as _np
            from PyQt6.QtCore import Qt  # local import to avoid Qt dependency at module import time

            ax.clear()

            # Build the list of references currently listed in the table
            ref_list: list[tuple[str, str]] = []  # (ref_key, display)
            for row in range(fit_table.rowCount()):
                it0 = fit_table.item(row, 0)
                if it0 is None:
                    continue
                refk = it0.data(Qt.ItemDataRole.UserRole)
                if not isinstance(refk, str):
                    continue
                ref_list.append((refk, it0.text()))

            for refk, disp in ref_list:
                pl = payload_by_key.get(refk)
                if pl is None:
                    continue
                x = _np.asarray(pl.x, dtype=float)
                y = _np.asarray(pl.y, dtype=float)
                o = _np.argsort(x)
                x = x[o]
                y = y[o]
                ax.plot(x, y, label=f"{disp} data")

                fr = fit_results.get(refk)
                if isinstance(fr, dict):
                    fx, fy = self._reconstruct_fit_curve(fr, pl)
                    if fx is not None and fy is not None:
                        ax.plot(fx, fy, linestyle="--", label=f"{disp} fit")

            ax.set_title("Reference fits")
            scales = set()
            for refk, _ in ref_list:
                pl = payload_by_key.get(refk)
                if pl is not None:
                    scales.add(str(getattr(pl, "energy_scale", "Unknown")))
            es = scales.pop() if len(scales) == 1 else "Unknown"
            ax.set_xlabel(normalize_energy_xlabel("Energy (eV)", es, unit="eV"))
            ax.set_ylabel("Intensity")
            try:
                ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
            except Exception:
                pass
            ax.legend(loc="best")
            canvas.draw_idle()
        except Exception:
            # Keep behavior: silently ignore plotting errors.
            pass

    def plot_reference(self, ax: Any, canvas: Any, ref_key: str,
                       fit_results: Dict[str, Any],
                       payload_by_key: Dict[str, Any],
                       title: Optional[str] = None) -> None:
        """Plot one reference curve and its fit."""
        if ax is None or canvas is None:
            return
        try:
            import numpy as _np
            ax.clear()
            pl = payload_by_key.get(ref_key)
            if pl is None:
                return
            x = _np.asarray(pl.x, dtype=float)
            y = _np.asarray(pl.y, dtype=float)
            o = _np.argsort(x)
            x = x[o]
            y = y[o]
            ax.plot(x, y, label="data")

            fr = fit_results.get(ref_key)
            if isinstance(fr, dict):
                fx, fy = self._reconstruct_fit_curve(fr, pl)
                if fx is not None and fy is not None:
                    ax.plot(fx, fy, linestyle="--", label="fit")
            if title:
                ax.set_title(title)
            ax.set_xlabel("Energy (eV)")
            ax.set_ylabel("Intensity")
            try:
                ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
            except Exception:
                pass
            ax.legend(loc="best")
            canvas.draw_idle()
        except Exception:
            pass


    def fit_all_references(self,
                           ax: Any,
                           canvas: Any,
                           fit_table: Any,
                           fit_results: Dict[str, Any],
                           payload_by_key: Dict[str, Any],
                           fit_one_reference: Any,
                           busy_fit: Any,
                           btn_fit: Any,
                           btn_plot: Any) -> None:
        """Run fitting for all mapped references.

        Thin wrapper that delegates to the module-level implementation. Kept as a method
        so the dialog can call `logic.fit_all_references(...)`.
        """
        return _fit_all_references_impl(
            ax=ax,
            canvas=canvas,
            fit_table=fit_table,
            fit_results=fit_results,
            payload_by_key=payload_by_key,
            fit_one_reference=fit_one_reference,
            busy_fit=busy_fit,
            btn_fit=btn_fit,
            btn_plot=btn_plot,
        )

    def apply_calibration(
        self,
        dlg: Any,
        raw_keys: list[str],
        shifts_by_raw: Dict[str, Any],
        targets_by_raw: Dict[str, Any],
        mapping: Dict[str, str],
        measured_energy_for_ref: Any,
        ref_type_for_raw: Any,
        targets_confirmed: Dict[str, Any],
        btn_e_cal_toggle: Any = None,
        update_selected_tree_visibility: Any = None,
        update_plot_from_selected: Any = None,
        payload_by_key: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Apply calibration shifts to checked raw curves by creating calibrated children.

        This is Step-6 refactor: move the non-UI apply logic out of the dialog.
        Behavior is intended to match the pre-refactor implementation.

        Returns the number of curves to which the calibration was applied.
        """
        mw = self.host.mw

        # Require confirmed targets (locks shifts_by_raw / targets_by_raw).
        if not bool(targets_confirmed.get("value", False)):
            try:
                from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox  # type: ignore
                QMessageBox.information(dlg, "Apply calibration", "Confirm targets first.")
            except Exception:
                pass
            return 0

        # Snapshot check states of raw (uncalibrated) curves so Raw view stays unaffected.
        raw_check_state: dict[str, int] = {}
        try:
            for k, it0 in list(mw._selected_by_key.items()):
                meta0 = it0.data(0, mw.ROLE_META)
                if isinstance(meta0, dict) and bool(meta0.get("processed", False)):
                    continue
                try:
                    raw_check_state[k] = int(it0.checkState(0))
                except Exception:
                    pass
        except Exception:
            pass

        # Apply to the curves that are still checked in the Selected-curves tree.
        applied = 0
        try:
            import numpy as np  # local
            from PyQt6.QtCore import Qt  # type: ignore
            from PyQt6.QtWidgets import QTreeWidgetItem  # type: ignore
            from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox  # type: ignore
        except Exception:
            np = None  # type: ignore
            Qt = None  # type: ignore
            QTreeWidgetItem = None  # type: ignore
            QMessageBox = None  # type: ignore

        # Local import to avoid relying on host internals
        from ...ui import PlotPayload  # type: ignore

        for sel_key in list(raw_keys):
            try:
                it = mw._selected_by_key.get(sel_key)
                if it is None:
                    continue
                # Resolve source raw key if a processed (E-cal) curve was selected
                raw_key = sel_key
                base_it = it
                try:
                    meta_it = base_it.data(0, mw.ROLE_META)
                    if isinstance(meta_it, dict) and bool(meta_it.get("processed", False)):
                        rk = meta_it.get("source_key")
                        if rk and str(rk) in mw._selected_by_key:
                            raw_key = str(rk)
                            base_it = mw._selected_by_key.get(raw_key) or base_it
                except Exception:
                    pass
                if Qt is not None and it.checkState(0) != Qt.CheckState.Checked:
                    continue
                shift = shifts_by_raw.get(sel_key)
                if shift is None:
                    shift = shifts_by_raw.get(raw_key)
                if shift is None:
                    continue

                # Use the exact workflow payload that was calibrated when available.
                # In particular, if Processed-data normalization was active,
                # payload_by_key contains the virtual (Norm) curve.  Falling back
                # to the tree payload keeps the legacy/raw behavior unchanged.
                p = None
                try:
                    if isinstance(payload_by_key, dict):
                        p = payload_by_key.get(sel_key) or payload_by_key.get(raw_key)
                except Exception:
                    p = None
                if p is None:
                    p = base_it.data(0, mw.ROLE_PAYLOAD)
                if PlotPayload is not None and not isinstance(p, PlotPayload):
                    continue
                if np is None:
                    continue

                # Energy calibration changes X only.  Intensity normalization is
                # deliberately *not baked into* the persistent E-cal child: it is
                # a reversible Processed-data view state and must stay consistent
                # when the user toggles between raw and calibrated views.
                base_payload = base_it.data(0, mw.ROLE_PAYLOAD)
                if PlotPayload is not None and not isinstance(base_payload, PlotPayload):
                    base_payload = p
                x_arr = np.asarray(base_payload.x, dtype=float)
                x_new = x_arr + float(shift)

                curve_id = f"curve_{getattr(mw, '_next_curve_id', 1):05d}"
                try:
                    mw._next_curve_id = int(getattr(mw, '_next_curve_id', 1)) + 1
                except Exception:
                    mw._next_curve_id = 1

                # Build the persistent calibrated payload from the underlying
                # source intensity.  If normalization is enabled, plotting and
                # downstream workflows apply it on top of this E-cal payload just
                # as they do for the raw source curve.
                base_title = str(base_payload.title).replace("Averaged", "").replace("  ", " ").strip()
                base_title = base_title.replace(" (Norm)", "").replace("(Norm) ", "")
                if "(E-cal)" not in base_title:
                    base_title = f"{base_title} (E-cal)"
                new_payload = PlotPayload(
                    title=base_title,
                    x=x_new,
                    y=np.asarray(base_payload.y, dtype=float).copy(),
                    xlabel=base_payload.xlabel,
                    ylabel=base_payload.ylabel,
                    energy_scale=getattr(base_payload, 'energy_scale', 'Unknown'),
                    metadata=dict(getattr(base_payload, 'metadata', {}) or {}),
                )

                meta_src = base_it.data(0, mw.ROLE_META)
                meta_new: dict[str, Any] = {}
                if isinstance(meta_src, dict):
                    meta_new.update(meta_src)
                refk = mapping.get(sel_key) or mapping.get(raw_key, "")
                meas = measured_energy_for_ref(refk)
                meta_new.update(
                    {
                        "processed": True,
                        "curveID": curve_id,
                        "source_key": raw_key,
                        "reference_key": refk,
                        "ref_type": ref_type_for_raw(raw_key),
                        "measured_E": meas,
                        "target_E": targets_by_raw.get(sel_key) if sel_key in targets_by_raw else targets_by_raw.get(raw_key),
                        "energy_shift": float(shift),
                    }
                )

                parent = it.parent()
                if parent is None or QTreeWidgetItem is None:
                    continue
                # The tree item identifies the persistent energy-calibrated
                # spectrum.  Normalization remains represented by its checkbox,
                # rather than being baked into the child label/data.
                base_lbl = str(it.text(0)).replace("Averaged", "").replace("  ", " ").strip()
                base_lbl = base_lbl.replace(" (Norm)", "").replace("(Norm) ", "")
                new_label = base_lbl if "(E-cal)" in base_lbl else f"{base_lbl} (E-cal)"
                new_item = QTreeWidgetItem([new_label])
                new_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                new_item.setCheckState(0, Qt.CheckState.Checked)
                new_item.setData(0, mw.ROLE_PAYLOAD, new_payload)
                new_item.setData(0, mw.ROLE_KEY, curve_id)
                new_item.setData(0, mw.ROLE_REGION, it.data(0, mw.ROLE_REGION))
                new_item.setData(0, mw.ROLE_META, meta_new)
                try:
                    new_item.setData(0, mw.ROLE_FILE, it.data(0, mw.ROLE_FILE))
                except Exception:
                    pass
                # Keep processed children in the same numerical source-file
                # order as raw selections.  Appending here used to make E-cal
                # curves follow calibration/insertion order instead of the
                # ascending acquisition-number order used by SelectedTreeManager.
                inserted = False
                try:
                    manager = getattr(mw, "_selected_tree_manager", None)
                    insert_sorted = getattr(manager, "_insert_child_sorted", None)
                    if callable(insert_sorted):
                        source_file = it.data(0, mw.ROLE_FILE)
                        insert_sorted(
                            parent,
                            new_item,
                            source_file=str(source_file or ""),
                            display=new_label,
                        )
                        inserted = True
                except Exception:
                    inserted = False
                if not inserted:
                    parent.addChild(new_item)
                parent.setExpanded(True)

                # Register for immediate visibility updates.
                try:
                    mw._selected_by_key[curve_id] = new_item
                except Exception:
                    pass

                # An E-calibrated derivative represents the same measured
                # spectrum on a shifted energy axis, so inherit the source
                # curve's Raw/Processed color initially.  The derivative keeps
                # its own key and can subsequently be recolored independently.
                try:
                    source_color = getattr(mw, "_curve_color_map", {}).get(str(raw_key))
                    if source_color:
                        mw._curve_color_map[curve_id] = str(source_color)
                except Exception:
                    pass

                applied += 1
            except Exception:
                continue

        # After applying, default to showing calibrated curves on Processed tab if possible.
        try:
            has_processed = mw._has_any_processed_curves() if hasattr(mw, "_has_any_processed_curves") else (applied > 0)
            if btn_e_cal_toggle is not None and has_processed:
                try:
                    btn_e_cal_toggle.setChecked(True)
                except Exception:
                    pass
        except Exception:
            pass

        # Restore raw check states so Raw selection is unaffected.
        try:
            for k, st in raw_check_state.items():
                it0 = mw._selected_by_key.get(k)
                if it0 is None:
                    continue
                meta0 = it0.data(0, mw.ROLE_META)
                if isinstance(meta0, dict) and bool(meta0.get("processed", False)):
                    continue
                try:
                    it0.setCheckState(0, Qt.CheckState(st))
                except Exception:
                    pass
        except Exception:
            pass

        # Enforce visibility + update plot (match pre-refactor behavior).
        try:
            show_processed = False
            try:
                cur_is_processed_tab = (mw.data_view_splitter.parentWidget() == mw.processed_view_holder)
                has_processed = mw._has_any_processed_curves() if hasattr(mw, "_has_any_processed_curves") else (applied > 0)
                if cur_is_processed_tab and has_processed:
                    show_processed = True
            except Exception:
                show_processed = False
            if update_selected_tree_visibility is not None:
                update_selected_tree_visibility(show_processed=bool(show_processed))
            if update_plot_from_selected is not None:
                update_plot_from_selected()
        except Exception:
            pass

        if applied == 0 and QMessageBox is not None:
            try:
                QMessageBox.information(dlg, "Apply calibration", "No curves were applied (nothing selected or missing shifts).")
            except Exception:
                pass
        return applied

def _fit_all_references_impl(
                       ax: Any,
                       canvas: Any,
                       fit_table: Any,
                       fit_results: Dict[str, Any],
                       payload_by_key: Dict[str, Any],
                       fit_one_reference: Any,
                       busy_fit: Any,
                       btn_fit: Any,
                       btn_plot: Any) -> None:
    """Fit all references listed in the table and update table + plot.

    This is an incremental refactor: logic moved out of the dialog to reduce
    calibrate_dialog.py size, without changing behavior.
    """
    try:
        from PyQt6.QtWidgets import QApplication  # type: ignore
    except Exception:
        QApplication = None  # type: ignore

    # Disable fitting controls while fitting.  A visual progress bar is
    # optional; the calibration dialog intentionally omits it to save space.
    try:
        if busy_fit is not None:
            busy_fit.setRange(0, 0)
            busy_fit.setValue(0)
    except Exception:
        pass
    try:
        btn_fit.setEnabled(False)
        if btn_plot is not None:
            btn_plot.setEnabled(False)
    except Exception:
        pass

    try:
        import numpy as _np
        from PyQt6.QtCore import Qt  # type: ignore
    except Exception:
        _np = None  # type: ignore
        Qt = None  # type: ignore

    for row in range(fit_table.rowCount()):
        it0 = fit_table.item(row, 0)
        it1 = fit_table.item(row, 1)
        it2 = fit_table.item(row, 2)
        it3 = fit_table.item(row, 3)
        if it0 is None or it1 is None:
            continue

        refk = it0.data(Qt.ItemDataRole.UserRole) if Qt is not None else None
        if not isinstance(refk, str):
            continue
        typ = it1.text().strip()

        ok, status_or_msg, fr = fit_one_reference(refk, typ)

        if it2 is not None:
            it2.setText(status_or_msg if ok else "Failed")

        if it3 is not None:
            if ok and refk in fit_results:
                fr2 = fit_results.get(refk, fr) if isinstance(fit_results, dict) else fr
                if isinstance(fr2, dict) and fr2.get("kind") == "fermi_edge":
                    q = fr2.get("quality", {}) or {}
                    r2 = q.get("r2")
                    w = (fr2.get("params", {}) or {}).get("w")
                    try:
                        if r2 is not None and w is not None:
                            it3.setText(f"EF = {fr2.get('E_meas'):.4f}   w={w:.3f}   R2={r2:.4f}")
                        else:
                            it3.setText(f"EF = {fr2.get('E_meas'):.4f}")
                    except Exception:
                        it3.setText(status_or_msg)
                else:
                    try:
                        it3.setText(f"Peak = {fit_results[refk].get('E_meas'):.4f}")
                    except Exception:
                        it3.setText(status_or_msg)
            else:
                it3.setText(status_or_msg)

        # Do not redraw after every reference.  The dialog draws the complete
        # overview once after all fits finish; per-reference redraws only slow the
        # synchronous calibration pass and make the window appear unresponsive.

        # Keep UI responsive.
        try:
            if QApplication is not None:
                QApplication.processEvents()
        except Exception:
            pass

    # Restore fitting controls.
    try:
        if busy_fit is not None:
            busy_fit.setRange(0, 1)
            busy_fit.setValue(0)
    except Exception:
        pass
    try:
        btn_fit.setEnabled(True)
        if btn_plot is not None:
            btn_plot.setEnabled(True)
    except Exception:
        pass
