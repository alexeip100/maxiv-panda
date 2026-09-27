from __future__ import annotations

"""Source-file snapshot identity and reload-policy helpers.

This module is deliberately GUI-free.  It defines the stable identity carried by
one loaded source snapshot and small helpers used by the UI reload policy.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4


def canonical_source_path(path: str | Path) -> str:
    """Return a normalized absolute path suitable for same-file comparisons."""
    p = Path(path).expanduser()
    try:
        p = p.resolve(strict=False)
    except Exception:
        p = p.absolute()
    # Windows paths are case-insensitive in the PANDA deployment environment.
    return str(p).casefold()


@dataclass(frozen=True)
class SourceSnapshot:
    snapshot_id: str
    canonical_path: str
    physical_path: str
    file_name: str
    source_label: str
    loaded_at: str
    file_mtime_ns: int | None = None
    file_size: int | None = None

    def as_metadata(self) -> dict[str, object]:
        return {
            "source_snapshot_id": self.snapshot_id,
            "source_canonical_path": self.canonical_path,
            "source_physical_path": self.physical_path,
            "source_label": self.source_label,
            "source_loaded_at": self.loaded_at,
            "source_file_mtime_ns": self.file_mtime_ns,
            "source_file_size": self.file_size,
        }


def make_source_snapshot(path: str | Path, *, source_label: str | None = None) -> SourceSnapshot:
    p = Path(path).expanduser()
    try:
        physical = str(p.resolve(strict=False))
    except Exception:
        physical = str(p.absolute())
    try:
        st = p.stat()
        mtime_ns = int(st.st_mtime_ns)
        size = int(st.st_size)
    except OSError:
        mtime_ns = None
        size = None
    loaded_at = datetime.now().isoformat(timespec="seconds")
    return SourceSnapshot(
        snapshot_id=f"src_{uuid4().hex}",
        canonical_path=canonical_source_path(p),
        physical_path=physical,
        file_name=p.name,
        source_label=str(source_label or p.name),
        loaded_at=loaded_at,
        file_mtime_ns=mtime_ns,
        file_size=size,
    )


def updated_source_label(file_name: str, existing_labels: Iterable[str]) -> str:
    """Return a concise unique label for a later snapshot of *file_name*."""
    stamp = datetime.now().strftime("%H:%M:%S")
    base = f"{file_name} [updated {stamp}]"
    used = {str(v) for v in existing_labels}
    if base not in used:
        return base
    index = 2
    while f"{base} #{index}" in used:
        index += 1
    return f"{base} #{index}"


@dataclass(frozen=True)
class SourceDependencySummary:
    processed_curves: int = 0
    plotted_curves: int = 0
    workflow_uses: tuple[str, ...] = ()

    @property
    def has_dependencies(self) -> bool:
        return bool(self.processed_curves or self.plotted_curves or self.workflow_uses)

    def describe(self) -> str:
        rows: list[str] = []
        if self.processed_curves:
            rows.append(f"{self.processed_curves} processed curve(s)")
        if self.plotted_curves:
            rows.append(f"{self.plotted_curves} plotted curve(s)")
        if self.workflow_uses:
            rows.append("Used in: " + ", ".join(self.workflow_uses))
        return "\n".join(rows) if rows else "No derived data or processing use"
