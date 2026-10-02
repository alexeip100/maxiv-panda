# What’s new in PANDA

## PANDA 0.12.1

PANDA 0.12.1 adds workspace sessions and refines several established 0.12.0 workflows.

### Added
- **Workspace sessions (`.panda`):** save an analysis workspace and reopen it later with its loaded data and working state restored across Raw, Processed, and Plotted Data, calibration/normalization, signal identification, fitting, and trace-comparison workflows. In-progress Batch fitting, including prepared or binned sequences and fitted results, is restored as part of the session.

### Fixed
- **Custom peak-fit ranges** are now preserved in saved fit configurations and restored correctly when they are loaded again. Existing 0.12.0 fit-configuration files remain compatible.
- **Normalization close to spectrum boundaries** is more robust to small rounding or energy-calibration offsets.

### Changed
- **Batch fitting is now modeless,** so the main PANDA window remains usable while the Batch fitting window is open.
- **Closing the main PANDA window now closes all auxiliary PANDA windows and exits the application completely.**

## PANDA 0.12.0

### First public release

PANDA 0.12.0 is the first public GitHub release of **PANDA — Photoemission Analysis, Normalization and Data Assessment**.

#### Highlights
- Unified loading and analysis of **Scienta/SES TXT**, **Igor IBW**, and **SPECS/SpecsLab Prodigy XY** data.
- A common **Raw → Processed → Plotted** workflow for individual spectra and spectral series.
- Interactive 2D map inspection with **Simple**, **Lines**, and **ROI** views.
- Energy calibration and intensity normalization with source provenance retained.
- Built-in signal identification and reference tools for binding energies and photoionization cross sections.
- Configurable single-spectrum peak fitting and sequence/batch fitting, including spin-orbit doublets.
- Live monitoring of growing **TXT/IBW** acquisitions.
- Large SPECS/Prodigy XY sequences with lazy iteration loading and automatic physical second axes such as temperature or elapsed time when the source data provide a trustworthy coordinate.
- Light and Dark application themes with integrated, theme-aware Help.

### Loading data
For normal use, **drag and drop** TXT, IBW, or XY files directly onto the **Loaded files** tree. PANDA detects the supported format automatically. The **Load** menu remains available when a file dialog is more convenient.

### Public-release baseline
Version 0.12.0 establishes the first public PANDA baseline. Maintenance fixes and small compatible improvements will use the **0.12.x** series; larger feature developments will move to later minor versions such as **0.13.0**.
