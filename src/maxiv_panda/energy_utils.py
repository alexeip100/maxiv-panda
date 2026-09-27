from __future__ import annotations

import re
from typing import Iterable


def infer_energy_scale(explicit_scale: str | None = None, hints: Iterable[str] = ()) -> str:
    """Infer energy scale from an explicit field and auxiliary text hints.

    Returns one of: ``Binding``, ``Kinetic``, ``Unknown``.
    The explicit scale, when present and recognizable, takes priority.
    """
    exp = str(explicit_scale or '').strip().lower()
    if exp.startswith('bind') or 'binding' in exp:
        return 'Binding'
    if exp.startswith('kin') or 'kinetic' in exp:
        return 'Kinetic'

    joined = ' '.join(str(h or '') for h in hints).strip().lower()
    if not joined:
        return 'Unknown'

    if 'binding energy' in joined:
        return 'Binding'
    if 'kinetic energy' in joined:
        return 'Kinetic'

    normalized = joined.replace('[', ' ').replace(']', ' ').replace('(', ' ').replace(')', ' ')
    normalized = normalized.replace('_', ' ').replace('-', ' ')
    normalized = ' '.join(normalized.split())
    if re.search(r'(^|\s)be(\s|$)', normalized):
        return 'Binding'
    if re.search(r'(^|\s)ke(\s|$)', normalized):
        return 'Kinetic'
    if 'binding' in normalized:
        return 'Binding'
    if 'kinetic' in normalized:
        return 'Kinetic'
    return 'Unknown'


def extract_energy_unit(label: str | None, default: str = 'eV') -> str:
    raw = str(label or '')
    m = re.search(r'\[([^\]]+)\]', raw)
    if m:
        unit = m.group(1).strip()
        if unit:
            return unit
    m = re.search(r'\(([^\)]+)\)', raw)
    if m:
        unit = m.group(1).strip()
        if unit:
            return unit
    return default


def normalize_energy_xlabel(xlabel: str | None, energy_scale: str | None, unit: str | None = None) -> str:
    """Return a canonical scale-aware x-label.

    Generic labels such as ``Energy`` or ``x`` are upgraded to explicit
    Binding/Kinetic labels when the scale is known.
    """
    raw = str(xlabel or '').strip()
    if unit is None:
        unit = extract_energy_unit(raw, default='eV')
    low = raw.lower()
    es = str(energy_scale or '').strip().lower()
    generic = (
        (not low)
        or low in {'x', 'energy', f'energy [{unit.lower()}]', f'energy ({unit.lower()})'}
        or ('binding' not in low and 'kinetic' not in low and low.startswith('energy'))
    )
    if es.startswith('bind'):
        return raw if (not generic and 'binding' in low) else f'Binding Energy [{unit}]'
    if es.startswith('kin'):
        return raw if (not generic and 'kinetic' in low) else f'Kinetic Energy [{unit}]'
    return raw or f'Energy [{unit}]'


def default_flip_for_energy_scale(energy_scale: str | None) -> bool | None:
    """Return the default x-axis flip for a recognized energy scale.

    ``True`` for Binding Energy, ``False`` for Kinetic Energy, ``None`` when
    the scale is unknown.
    """
    es = str(energy_scale or '').strip().lower()
    if es.startswith('bind'):
        return True
    if es.startswith('kin'):
        return False
    return None
