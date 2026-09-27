from __future__ import annotations

from typing import Any, Callable

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem

from .txt_parser import region_to_traces
from .selection_tree import collect_region_names, is_average_or_trace, iter_curve_leaves
from .file_naming import derive_file_tag, format_curve_source_label, make_loaded_curve_key
from .energy_utils import normalize_energy_xlabel
from .specs_xy_adapter import SpecsXYRegionData


class LoadedTreeController:
    def __init__(
        self,
        *,
        tree: Any,
        files_root: Any,
        role_payload: int,
        role_key: int,
        role_region: int,
        role_file: int,
        role_meta: int,
        payload_factory: Callable[..., Any],
        region_iteration_stack: dict[tuple[str, str], Any],
    ):
        self.tree = tree
        self.files_root = files_root
        self.role_payload = role_payload
        self.role_key = role_key
        self.role_region = role_region
        self.role_file = role_file
        self.role_meta = role_meta
        self.payload_factory = payload_factory
        self.region_iteration_stack = region_iteration_stack
        # Large SPECS .xy regions are expanded lazily so native Prodigy files
        # with thousands of cycles do not create tens of thousands of Qt tree
        # items at load time.  TXT/IBW regions never enter this path.
        self._xy_lazy_regions: dict[int, dict[str, Any]] = {}
        try:
            self.tree.itemExpanded.connect(self._on_item_expanded)
            self.tree.itemChanged.connect(self._on_lazy_item_changed)
        except Exception:
            pass



    XY_LAZY_ITERATION_THRESHOLD = 250

    @staticmethod
    def _configure_iterations_root(item: Any, state: Any = Qt.CheckState.Unchecked) -> None:
        """Give every Iterations branch the same group-checkbox behavior."""
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable |
            Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate
        )
        item.setCheckState(0, state)

    def _should_lazy_expand_xy(self, region: Any) -> bool:
        """Return True only for large SPECS .xy multi-iteration regions."""
        if not isinstance(region, SpecsXYRegionData) or region.data is None:
            return False
        # Column 0 is energy; remaining columns are exported acquisitions.
        return max(0, int(region.data.shape[1]) - 1) >= self.XY_LAZY_ITERATION_THRESHOLD

    def _cache_region_iteration_stack_from_region(self, *, parsed: Any, region: Any, source_label: str) -> None:
        """Cache a large XY region without first manufacturing per-iteration dicts."""
        try:
            mat = region.data
            if mat is None or mat.ndim != 2 or mat.shape[1] < 3:
                return
            x = mat[:, 0]
            Y = [mat[:, idx] for idx in range(1, mat.shape[1])]
            energy_scale = str(region.info_meta.get('Energy Scale', 'Unknown'))
            xlabel = normalize_energy_xlabel(region.dim1_name(), energy_scale)
            vals = region.dim2_scale()
            dim2_values = list(vals) if vals is not None and len(vals) == len(Y) else None
            self.region_iteration_stack[(str(source_label), region.region_name)] = (
                x, Y, xlabel, dim2_values, region.dim2_name()
            )
        except Exception:
            pass

    def _trace_common_from_region(self, region: Any) -> dict[str, Any]:
        """Metadata shared by lazily-created traces, matching region_to_traces()."""
        energy_scale = str(region.info_meta.get('Energy Scale', 'Unknown'))
        source_metadata = {
            k: v for k, v in region.region_meta.items()
            if k not in {'Dimension 2 scale', 'Wave note'}
        }
        source_metadata.update({k: v for k, v in region.info_meta.items() if k != 'Wave note'})
        source_sections = {
            str(name): dict(values)
            for name, values in (getattr(region, 'section_meta', {}) or {}).items()
            if values
        }
        return {
            'xlabel': normalize_energy_xlabel(region.dim1_name(), energy_scale),
            'ylabel': 'Intensity',
            'energy_scale': energy_scale,
            'region_index': region.index,
            'n_traces': int(region.data.shape[1] - 1),
            'source_metadata': source_metadata,
            'section_meta': source_sections,
            'time_per_spectrum_channel': source_metadata.get('Time per Spectrum Channel'),
        }

    def _add_xy_region_children_lazy(
        self, *, parsed: Any, region: Any, region_item: Any, source_label: str, snapshot_meta: dict[str, Any]
    ) -> None:
        """Add Average immediately; materialize large XY Iterations only on expansion."""
        mat = region.data
        if mat is None or mat.ndim != 2 or mat.shape[1] < 3:
            traces = region_to_traces(region)
            self._add_region_children(
                parsed=parsed, region=region, region_item=region_item, traces=traces,
                source_label=source_label, snapshot_meta=snapshot_meta,
            )
            return

        common = self._trace_common_from_region(region)
        x = mat[:, 0]
        ys = mat[:, 1:]
        avg = {
            **common,
            'kind': 'average',
            'x': x,
            'y': np.nanmean(ys, axis=1),
            'title': f"{region.region_name} (Average)",
        }
        file_tag = self._derive_file_tag(parsed.path.stem)
        region_item.addChild(self.make_curve_leaf(
            label='Average', t=avg, region_name=region.region_name, file_tag=file_tag,
            file_name=source_label, physical_file_name=parsed.path.name,
            snapshot_meta=snapshot_meta, region_index=region.index,
        ))

        it_root = QTreeWidgetItem(['Iterations'])
        self._configure_iterations_root(it_root)
        it_root.setToolTip(0, f"{ys.shape[1]} iterations; expand to show individual spectra")
        placeholder = QTreeWidgetItem([f"({ys.shape[1]} spectra - expand to show)"])
        placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)
        it_root.addChild(placeholder)
        region_item.addChild(it_root)
        it_root.setExpanded(False)
        self._xy_lazy_regions[id(it_root)] = {
            'root': it_root, 'parsed': parsed, 'region': region, 'source_label': source_label,
            'snapshot_meta': dict(snapshot_meta),
        }

    def _on_item_expanded(self, item: Any) -> None:
        self._materialize_lazy_iterations(item)

    def _on_lazy_item_changed(self, item: Any, column: int) -> None:
        """A lazy Iterations checkbox must behave like an eager group checkbox."""
        if column != 0 or id(item) not in self._xy_lazy_regions:
            return
        if item.checkState(0) != Qt.CheckState.Unchecked:
            self._materialize_lazy_iterations(item)

    def _materialize_lazy_iterations(self, item: Any) -> None:
        state = self._xy_lazy_regions.pop(id(item), None)
        if state is None:
            return
        region = state['region']
        parsed = state['parsed']
        source_label = state['source_label']
        snapshot_meta = state['snapshot_meta']
        mat = region.data
        if mat is None:
            return
        requested_state = item.checkState(0)
        try:
            self.tree.blockSignals(True)
            item.takeChildren()
            self._configure_iterations_root(item, requested_state)
            common = self._trace_common_from_region(region)
            dim2_name = region.dim2_name()
            dim2_scale = region.dim2_scale()
            file_tag = self._derive_file_tag(parsed.path.stem)
            x = mat[:, 0]
            for idx in range(1, mat.shape[1]):
                iteration = idx
                t = {
                    **common,
                    'kind': 'iteration',
                    'iteration': iteration,
                    'x': x,
                    'y': mat[:, idx],
                    'title': f"{region.region_name} (Iteration {iteration})",
                    'iteration_axis_name': dim2_name,
                    'iteration_axis_value': (
                        dim2_scale[iteration - 1]
                        if dim2_scale is not None and iteration - 1 < len(dim2_scale)
                        else None
                    ),
                }
                leaf = self.make_curve_leaf(
                    label=f"Iteration {iteration}", t=t, region_name=region.region_name,
                    file_tag=file_tag, file_name=source_label, physical_file_name=parsed.path.name,
                    snapshot_meta=snapshot_meta, region_index=region.index,
                )
                if requested_state != Qt.CheckState.Unchecked:
                    leaf.setCheckState(0, requested_state)
                item.addChild(leaf)
        finally:
            self.tree.blockSignals(False)

    def collect_region_names(self) -> list[str]:
        return collect_region_names(self.files_root)

    def iter_curve_leaves(self) -> list[Any]:
        return iter_curve_leaves(self.files_root, role_payload=self.role_payload, payload_type=self.payload_factory)

    def add_parsed_to_tree(self, parsed: Any, snapshot: Any = None) -> None:
        self.tree.blockSignals(True)
        try:
            source_label = str(getattr(snapshot, 'source_label', '') or parsed.path.name)
            snapshot_meta = dict(snapshot.as_metadata()) if snapshot is not None else {}
            file_item = QTreeWidgetItem([source_label])
            file_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            file_item.setToolTip(0, "Right-click for metadata and other options")
            file_item.setData(0, self.role_file, source_label)
            file_item.setData(0, self.role_meta, {
                'metadata_scope': 'file',
                'file_name': parsed.path.name,
                'file_path': str(parsed.path),
                'file_info': dict(getattr(parsed, 'file_info', {}) or {}),
                **snapshot_meta,
            })
            self.files_root.addChild(file_item)
            file_item.setExpanded(True)

            for region in parsed.regions:
                region_item = QTreeWidgetItem([region.region_name])
                region_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                region_item.setToolTip(0, "Right-click for metadata and other options")
                region_item.setData(0, self.role_file, source_label)
                region_item.setData(0, self.role_region, region.region_name)
                region_item.setData(0, self.role_meta, {
                    'metadata_scope': 'region',
                    'file_name': parsed.path.name,
                    'file_path': str(parsed.path),
                    'region_name': region.region_name,
                    'region_index': getattr(region, 'index', None),
                    'file_info': dict(getattr(parsed, 'file_info', {}) or {}),
                    'region_meta': dict(getattr(region, 'region_meta', {}) or {}),
                    'info_meta': dict(getattr(region, 'info_meta', {}) or {}),
                    'section_meta': {
                        str(name): dict(values)
                        for name, values in (getattr(region, 'section_meta', {}) or {}).items()
                    },
                    'warnings': list(getattr(region, 'warnings', []) or []),
                    **snapshot_meta,
                })
                file_item.addChild(region_item)
                region_item.setExpanded(True)

                if self._should_lazy_expand_xy(region):
                    self._cache_region_iteration_stack_from_region(
                        parsed=parsed, region=region, source_label=source_label
                    )
                    self._add_xy_region_children_lazy(
                        parsed=parsed,
                        region=region,
                        region_item=region_item,
                        source_label=source_label,
                        snapshot_meta=snapshot_meta,
                    )
                else:
                    traces = region_to_traces(region)
                    self._cache_region_iteration_stack(parsed=parsed, region=region, traces=traces, source_label=source_label)
                    self._add_region_children(
                        parsed=parsed,
                        region=region,
                        region_item=region_item,
                        traces=traces,
                        source_label=source_label,
                        snapshot_meta=snapshot_meta,
                    )
                self._add_region_warnings(region_item=region_item, warnings=region.warnings)

            self.files_root.setExpanded(True)
        finally:
            self.tree.blockSignals(False)

    def apply_all_in_region_selection(self, *, region: str, leaves: list[Any]) -> None:
        if not region:
            return
        try:
            self.tree.blockSignals(True)
            for leaf in leaves:
                meta = leaf.data(0, self.role_meta)
                leaf_region = leaf.data(0, self.role_region)
                is_target = is_average_or_trace(meta if isinstance(meta, dict) else None, leaf.text(0))
                if is_target and isinstance(leaf_region, str) and leaf_region == region:
                    leaf.setCheckState(0, Qt.CheckState.Checked)
                else:
                    leaf.setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            self.tree.blockSignals(False)

    def clear_curve_selection(self, *, leaves: list[Any]) -> None:
        """Uncheck all curve leaves as the inverse of a group selection mode."""
        try:
            self.tree.blockSignals(True)
            for leaf in leaves:
                leaf.setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            self.tree.blockSignals(False)

    def _cache_region_iteration_stack(self, *, parsed: Any, region: Any, traces: list[dict[str, Any]], source_label: str | None = None) -> None:
        try:
            it_traces = [t for t in traces if t.get('kind') == 'iteration' and t.get('iteration') is not None]
            if it_traces:
                it_traces = sorted(it_traces, key=lambda d: int(d.get('iteration')))
                x = it_traces[0].get('x')
                xlabel_raw = str(it_traces[0].get('xlabel', 'x'))
                energy_scale = str(it_traces[0].get('energy_scale', 'Unknown'))
                xlabel = normalize_energy_xlabel(xlabel_raw, energy_scale)
                Y = [list(t.get('y')) for t in it_traces]
                dim2_values = None
                dim2_name = ""
                try:
                    vals = region.dim2_scale()
                    if vals is not None and len(vals) == len(Y):
                        dim2_values = list(vals)
                        dim2_name = region.dim2_name()
                except Exception:
                    pass
                self.region_iteration_stack[(str(source_label or parsed.path.name), region.region_name)] = (
                    x, Y, xlabel, dim2_values, dim2_name
                )
        except Exception:
            pass

    def _add_region_children(self, *, parsed: Any, region: Any, region_item: Any, traces: list[dict[str, Any]], source_label: str | None = None, snapshot_meta: dict[str, Any] | None = None) -> None:
        if not traces:
            warn = QTreeWidgetItem(['(no plottable data)'])
            warn.setFlags(Qt.ItemFlag.ItemIsEnabled)
            region_item.addChild(warn)
            return

        source_label = str(source_label or parsed.path.name)
        snapshot_meta = dict(snapshot_meta or {})
        file_tag = self._derive_file_tag(parsed.path.stem)
        only_trace = [t for t in traces if t.get('kind') == 'trace']
        if only_trace:
            t = only_trace[0]
            leaf = self.make_curve_leaf(
                label='Trace',
                t=t,
                region_name=region.region_name,
                file_tag=file_tag,
                file_name=source_label,
                physical_file_name=parsed.path.name,
                snapshot_meta=snapshot_meta,
                region_index=region.index,
            )
            region_item.addChild(leaf)
            return

        avg = next((t for t in traces if t.get('kind') == 'average'), None)
        if avg is not None:
            leaf = self.make_curve_leaf(
                label='Average',
                t=avg,
                region_name=region.region_name,
                file_tag=file_tag,
                file_name=source_label,
                physical_file_name=parsed.path.name,
                snapshot_meta=snapshot_meta,
                region_index=region.index,
            )
            region_item.addChild(leaf)

        it_root = QTreeWidgetItem(['Iterations'])
        self._configure_iterations_root(it_root)
        region_item.addChild(it_root)

        for t in traces:
            if t.get('kind') != 'iteration':
                continue
            label = f"Iteration {t.get('iteration', '')}".strip()
            leaf = self.make_curve_leaf(
                label=label,
                t=t,
                region_name=region.region_name,
                file_tag=file_tag,
                file_name=source_label,
                physical_file_name=parsed.path.name,
                snapshot_meta=snapshot_meta,
                region_index=region.index,
            )
            it_root.addChild(leaf)
        it_root.setExpanded(False)

    def _add_region_warnings(self, *, region_item: Any, warnings: list[str]) -> None:
        if not warnings:
            return
        wroot = QTreeWidgetItem(['Warnings'])
        wroot.setFlags(Qt.ItemFlag.ItemIsEnabled)
        region_item.addChild(wroot)
        for w in warnings:
            wi = QTreeWidgetItem([w])
            wi.setFlags(Qt.ItemFlag.ItemIsEnabled)
            wroot.addChild(wi)
        wroot.setExpanded(False)

    def make_curve_leaf(
        self,
        *,
        label: str,
        t: dict[str, Any],
        region_name: str,
        file_tag: str,
        file_name: str,
        physical_file_name: str | None = None,
        snapshot_meta: dict[str, Any] | None = None,
        region_index: int | None = None,
    ) -> Any:
        leaf = QTreeWidgetItem([label])
        leaf.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
        leaf.setToolTip(0, "Right-click for metadata and other options")
        leaf.setCheckState(0, Qt.CheckState.Unchecked)

        energy_scale = str(t.get('energy_scale', 'Unknown'))
        xlabel = normalize_energy_xlabel(t.get('xlabel', 'x'), energy_scale)
        payload = self.payload_factory(
            title=t['title'],
            x=t['x'],
            y=t['y'],
            xlabel=xlabel,
            ylabel=t.get('ylabel', 'Intensity'),
            energy_scale=energy_scale,
            metadata={**dict(snapshot_meta or {}), 'source_label': file_name, 'source_file': str(physical_file_name or file_name), 'region': region_name, 'curve_label': label},
        )
        leaf.setData(0, self.role_payload, payload)

        meta = {
            'metadata_scope': 'curve',
            'file_name': str(physical_file_name or file_name),
            'source_label': file_name,
            'region_name': region_name,
            'kind': str(t.get('kind', '')),
            'iteration': t.get('iteration'),
            'n_traces': t.get('n_traces'),
            'leaf_label': label,
            # Keep the physical second-dimension value on each iteration leaf
            # as well as in the region stack.  This survives creation of
            # Processed Data copies and provides a robust fallback for map axes.
            'iteration_axis_name': t.get('iteration_axis_name'),
            'iteration_axis_value': t.get('iteration_axis_value'),
            'source_metadata': dict(t.get('source_metadata') or {}),
            # Explicit CPS acquisition time.  Do not rely only on the nested
            # source_metadata QVariant surviving subsequent tree copies.
            'time_per_spectrum_channel': t.get('time_per_spectrum_channel'),
            **dict(snapshot_meta or {}),
            'section_meta': {
                str(name): dict(values)
                for name, values in (t.get('section_meta') or {}).items()
            },
        }
        leaf.setData(0, self.role_meta, meta)

        display = format_curve_source_label(file_name, region_name)
        if label.lower() not in ('trace',):
            display = format_curve_source_label(file_name, region_name, label)
        key = make_loaded_curve_key(file_name, region_name, label, region_index)
        leaf.setData(0, self.role_key, (key, display))
        leaf.setData(0, self.role_region, region_name)
        leaf.setData(0, self.role_file, file_name)
        return leaf

    @staticmethod
    def _derive_file_tag(stem: str) -> str:
        """Return the acquisition/file identifier used in curve labels.

        Keep this identical to the selected-tree naming rule.  In particular,
        filenames such as ``XPS_0070S2p_260.ibw`` must yield ``0070`` rather
        than the trailing numeric region qualifier ``260``.
        """
        return derive_file_tag(stem)
