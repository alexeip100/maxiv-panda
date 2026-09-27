from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RegionTitleState:
    region_name: str
    map_enabled: bool
    metas: list[dict[str, Any]]


def build_plot_title(region_entries: list[RegionTitleState], *, show_processed: bool = False) -> str:
    """Build the plot title from already-collected region state."""
    if not region_entries:
        return ''
    if len(region_entries) > 1:
        return 'Multiple regions'

    entry = region_entries[0]
    avg_selected = any(
        str(m.get('kind', '')).lower() == 'average' or str(m.get('leaf_label', '')).lower() == 'average'
        for m in entry.metas
    )
    iters = sorted(
        [int(m.get('iteration')) for m in entry.metas if m.get('iteration') is not None and str(m.get('kind', '')).lower() == 'iteration']
    )

    n_traces = None
    for meta in entry.metas:
        v = meta.get('n_traces')
        if v is None:
            continue
        try:
            n_traces = int(v)
            break
        except Exception:
            continue

    iter_desc = ''
    if entry.map_enabled:
        iter_desc = 'map'
    elif iters:
        if n_traces is not None and len(iters) == n_traces:
            iter_desc = 'all iterations'
        elif len(iters) == 1:
            iter_desc = f'Iteration {iters[0]}'
        else:
            iter_desc = 'some iterations'

    if avg_selected and (not iters) and (not entry.map_enabled):
        desc = 'Average'
    elif (not avg_selected) and (iters or entry.map_enabled):
        desc = iter_desc
    elif avg_selected and (iters or entry.map_enabled):
        if iter_desc:
            desc = f'{iter_desc} + Average' if entry.map_enabled else f'Average + {iter_desc}'
        else:
            desc = 'Average'
    else:
        desc = ''

    base_title = f'{entry.region_name} ({desc})' if desc else entry.region_name
    if show_processed:
        return f'E-calibrated: {base_title}'
    return base_title


from .energy_utils import normalize_energy_xlabel
