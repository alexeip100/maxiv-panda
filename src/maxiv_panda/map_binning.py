from __future__ import annotations

"""Pure helpers for consecutive-row binning of 2D map payloads.

The algorithm deliberately mirrors batch-fit binning: selected rows are grouped
in consecutive, non-overlapping chunks of ``bin_size``; only complete chunks
are retained; each chunk is replaced by its arithmetic mean.  In map form the
energy axis is shared by all rows, so only the row intensities and optional
second-dimension coordinates need averaging.
"""

from typing import Any

import numpy as np


def bin_map_image(image: tuple[Any, ...], bin_size: int) -> tuple[tuple[Any, ...], int, int, int]:
    """Return a binned map image and (original, effective, discarded) counts.

    ``image`` follows the application convention::

        (x, y, Z, title, xlabel[, cmap[, secondary_y, secondary_label]])

    Binning is consecutive and non-overlapping.  Incomplete trailing rows are
    discarded, matching the batch-fitting workflow.  The displayed Iteration
    coordinate and any physical second-dimension coordinate are represented by
    the mean coordinate of the source rows in each bin.
    """
    size = max(1, int(bin_size))
    if len(image) < 5:
        raise ValueError("map image payload must contain at least five fields")

    x, y, Z, title, xlabel = image[:5]
    cmap = image[5] if len(image) >= 6 else None
    secondary_y = image[6] if len(image) >= 7 else None
    secondary_label = image[7] if len(image) >= 8 else ""

    Z_arr = np.asarray(Z, dtype=float)
    if Z_arr.ndim == 1:
        Z_arr = Z_arr.reshape(1, -1)
    elif Z_arr.ndim > 2:
        Z_arr = Z_arr.reshape(Z_arr.shape[0], -1)
    rows = int(Z_arr.shape[0])

    try:
        y_arr = np.asarray(list(y), dtype=float).reshape(-1)
        if y_arr.size != rows:
            raise ValueError
    except Exception:
        y_arr = np.arange(1, rows + 1, dtype=float)

    sec_arr = None
    if secondary_y is not None:
        try:
            candidate = np.asarray(list(secondary_y), dtype=float).reshape(-1)
            if candidate.size == rows:
                sec_arr = candidate
        except Exception:
            sec_arr = None

    if size <= 1 or rows == 0:
        return tuple(image), rows, rows, 0

    usable = (rows // size) * size
    discarded = rows - usable
    effective = usable // size
    if usable <= 0:
        # This should normally be prevented by the GUI spin-box maximum, but a
        # well-defined empty result keeps the helper safe for programmatic use.
        empty_Z = np.empty((0, Z_arr.shape[1]), dtype=float)
        fields: list[Any] = [x, [], empty_Z, f"{title} — binned by {size}", xlabel]
        if len(image) >= 6:
            fields.append(cmap)
        if len(image) >= 7:
            fields.append([] if sec_arr is not None else None)
        if len(image) >= 8:
            fields.append(secondary_label)
        if len(image) > 8:
            fields.extend(image[8:])
        return tuple(fields), rows, 0, discarded

    Z_use = Z_arr[:usable]
    Z_binned = np.nanmean(Z_use.reshape(effective, size, Z_use.shape[1]), axis=1)
    y_binned = np.nanmean(y_arr[:usable].reshape(effective, size), axis=1)
    sec_binned = None
    if sec_arr is not None:
        sec_binned = np.nanmean(sec_arr[:usable].reshape(effective, size), axis=1)

    fields = [x, y_binned.tolist(), Z_binned, f"{title} — binned by {size}", xlabel]
    if len(image) >= 6:
        fields.append(cmap)
    if len(image) >= 7:
        fields.append(sec_binned.tolist() if sec_binned is not None else None)
    if len(image) >= 8:
        fields.append(secondary_label)
    if len(image) > 8:
        fields.extend(image[8:])
    return tuple(fields), rows, effective, discarded
