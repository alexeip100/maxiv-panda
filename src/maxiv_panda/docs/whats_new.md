# What’s new in PANDA 0.12.0

## First public release
PANDA 0.12.0 is the first public GitHub release of **PANDA — Photoemission Analysis, Normalization and Data Assessment**.

### Highlights
- Unified loading and analysis of **Scienta/SES TXT**, **Igor IBW**, and **SPECS/SpecsLab Prodigy XY** data.
- A common **Raw → Processed → Plotted** workflow for individual spectra and spectral series.
- Interactive 2D map inspection with **Simple**, **Lines**, and **ROI** views.
- Energy calibration and intensity normalization with source provenance retained.
- Built-in signal identification and reference tools for binding energies and photoionization cross sections.
- Configurable single-spectrum peak fitting and sequence/batch fitting, including spin-orbit doublets.
- Live monitoring of growing **TXT/IBW** acquisitions.
- Large SPECS/Prodigy XY sequences with lazy iteration loading and automatic physical second axes such as temperature or elapsed time when the source data provide a trustworthy coordinate.
- Light and Dark application themes with integrated, theme-aware Help.

## Loading data
For normal use, **drag and drop** TXT, IBW, or XY files directly onto the **Loaded files** tree. PANDA detects the supported format automatically. The **Load** menu remains available when a file dialog is more convenient.

## Public-release baseline
Version 0.12.0 establishes the first public PANDA baseline. Maintenance fixes and small compatible improvements will use the **0.12.x** series; larger feature developments will move to later minor versions such as **0.13.0**.
