from __future__ import annotations

"""Pure helpers for sampled MAP animation sequences."""

import math


def valid_full_width_indices(total: int, thickness: int) -> list[int]:
    """Return cursor centres whose complete odd-width window fits in the map."""
    total = max(0, int(total))
    thickness = max(1, int(thickness))
    if thickness % 2 == 0:
        thickness += 1
    half = (thickness - 1) // 2
    first, last = half, total - 1 - half
    if last < first:
        return []
    return list(range(first, last + 1))


def stepped_positions(start: int, end: int, thickness: int) -> list[int]:
    """Return physical key positions separated by exactly one selected width."""
    start, end = int(start), int(end)
    step = max(1, int(thickness))
    direction = 1 if end >= start else -1
    out = list(range(start, end + direction, direction * step))
    return out or [start]


def playback_positions(base: list[int], back_and_forth: bool, loop: bool) -> list[int]:
    """Expand a one-way sweep into the requested key-position playback cycle."""
    base = list(base or [])
    if len(base) <= 1 or not back_and_forth:
        return base
    if loop:
        # Wrapping the cycle supplies the first endpoint again, so exclude both
        # endpoints from the reverse leg to avoid duplicate dwell frames.
        return base + base[-2:0:-1]
    # A single back-and-forth run explicitly returns to its starting endpoint.
    return base + base[-2::-1]


def smooth_positions(
    key_positions: list[int | float],
    *,
    frame_rate: float,
    key_steps_per_second: float,
) -> list[float]:
    """Interpolate visual frames between physical animation key positions.

    ``key_positions`` retain the scientifically meaningful step (normally the
    selected H/V averaging thickness).  Rendering can then be much smoother by
    inserting fractional display positions between those key positions.  The
    requested key-step rate controls duration while ``frame_rate`` controls
    visual smoothness, so video export can use a higher FPS without changing
    the apparent sweep speed.
    """
    keys = [float(v) for v in (key_positions or [])]
    if len(keys) <= 1:
        return keys
    fps = max(1.0, float(frame_rate))
    rate = max(1.0e-9, float(key_steps_per_second))
    frames_per_segment = max(1, int(round(fps / rate)))
    out: list[float] = [keys[0]]
    for start, end in zip(keys[:-1], keys[1:]):
        if math.isclose(start, end, rel_tol=0.0, abs_tol=1.0e-12):
            continue
        for n in range(1, frames_per_segment + 1):
            t = n / float(frames_per_segment)
            out.append(start + (end - start) * t)
    return out


def repeated_cycle_positions(cycle: list[float], cycles: int) -> list[float]:
    """Repeat a finite visual cycle without adding endpoint dwell frames."""
    seq = list(cycle or [])
    cycles = max(1, int(cycles))
    if not seq or cycles == 1:
        return seq
    out = list(seq)
    for _ in range(1, cycles):
        # Back-and-forth cycles typically end where they started.  Avoid an
        # identical repeated endpoint, while retaining the intentional B -> A
        # jump between repeated one-way cycles.
        if out and seq and math.isclose(out[-1], seq[0], rel_tol=0.0, abs_tol=1.0e-12):
            out.extend(seq[1:])
        else:
            out.extend(seq)
    return out
