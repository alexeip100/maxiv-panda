# Changelog

## 0.12.2 - 2026-10-06

### Changed
- Improve survey signal identification with cross-shell element-family consistency: once an element is independently supported by at least two photoelectron families, other accessible core-level families can be recovered from real measured features, with Yeh-Lindau cross sections used only as broad relative-intensity evidence.
- Allow Live Monitor to be opened directly from individual TXT or IBW region entries while retaining the existing file-level actions.

### Fixed
- Recover strong core lines that could previously be missed when broad survey peak detection placed a provisional maximum away from the true local peak, including Na 1s in spectra where Na 2s and Na 2p already establish sodium.
- Make Clear all reliably uncheck every checkable item in the Loaded files tree, including grouped/auto-tristate entries.

## 0.12.1 - 2026-10-02

### Added
- Add `.panda` workspace sessions that restore loaded data and the main analysis state across Raw, Processed, and Plotted Data, calibration/normalization, signal identification, fitting, trace comparison, and in-progress Batch fitting.

### Fixed
- Preserve custom peak-fit ranges in saved fit configurations and restore them correctly; 0.12.0 fit-configuration files remain compatible.
- Make normalization close to spectrum boundaries robust to small rounding or energy-calibration offsets.

### Changed
- Make Batch fitting modeless so the main PANDA window remains usable while Batch fitting is open.
- Make closing the main PANDA window close all auxiliary PANDA windows and exit the application completely.

## 0.12.0 - 2026-09-27

- First public GitHub release of **PANDA — Photoemission Analysis, Normalization and Data Assessment**.
- Rewrite the README as public-facing project documentation with capabilities, supported formats, installation, quick-start, citation, authorship, and license information.
- Add `CITATION.cff` for GitHub/software citation support; a future Zenodo DOI can be added to the same citation metadata without changing the software identity.
- Implement **Help → What’s new?** as a real theme-aware release-notes page and document the 0.12.0 public baseline.
- Standardize public attribution as **Created by: Alexei Preobrajenski (MAX IV Laboratory)** and **License: MIT**, and update the MIT copyright notice accordingly.
- Strengthen `pyproject.toml` public metadata with author, keywords, classifiers, and repository/issue-tracker URLs.
- Remove the obsolete `flexpes_pes` compatibility Python namespace and release-tooling assumptions. Legacy `flexpes_pes_*` identifiers embedded in saved fit/batch file formats remain supported for backward compatibility.
- No intentional changes to scientific processing algorithms or existing data-format handling relative to 0.11.91.

## 0.11.91 - 2026-09-27

- Make Average selection instantaneous for large lazily-expanded SPECS/Prodigy `.xy` regions by updating only that one selected leaf instead of rebuilding the complete Selected-curves tree.
- Keep lazy Iterations completely untouched when Average is checked or unchecked; only the Iterations group itself can trigger materialization of hundreds or thousands of child spectra.
- Restrict the optimization to large XY Average leaves so TXT/IBW and ordinary tree-selection behavior remain on their established paths.

## 0.11.90 - 2026-09-26

- Rework Help loading guidance so TXT, IBW, and SPECS/Prodigy XY are presented as equal source formats feeding the same PANDA Raw Data workflow.
- Promote drag-and-drop as the recommended everyday loading method, with the Load menu documented as the explicit file-dialog alternative.
- Replace the mostly monochrome Help hierarchy with a theme-aware palette accent: softly tinted H1 panels, accented H2/H3 hierarchy, links, pane title, and TOC selection. The accent is blended toward the active text colour so it remains readable and elegant in both Light and Dark themes without hard-coded dark blue.
- Keep XY-specific details concise in the main loading instructions while retaining large-region and physical-Y behaviour where it is relevant.

## 0.11.89 - 2026-09-26

- Complete the current SPECS/Prodigy `.xy` support pass by exposing one trustworthy physical second Y coordinate through PANDA's existing map-axis machinery while keeping Iteration as the sequence coordinate and fallback.
- Prefer a complete varying Prodigy external channel (for example sample temperature); otherwise use exactly one varying Y/Z acquisition position, then sufficiently resolved acquisition timestamps as **Elapsed Time [s]**. Ambiguous or poorly resolved coordinates fall back to Iteration rather than being guessed.
- Collapse each external-channel block to its median value for that acquisition, so slowly changing quantities such as temperature ramps become a stable per-spectrum coordinate even when they drift slightly during one swept spectrum.
- Audit `.xy` loading and compatibility against the supplied normal XPS, snapshot, temperature-sweep, time-resolved, large mixed `AllData.xy`, empty, and other-lab exports; keep TXT/IBW parser paths unchanged and retain the existing lazy-tree handling for large `.xy` regions.
- Update Help for `.xy` physical-Y detection and add regression coverage for temperature, time, positional axes, conservative fallbacks, and malformed/empty files.

## 0.11.88 - 2026-09-26

- Make the **Iterations** group checkbox consistent for large lazily-expanded SPECS/Prodigy `.xy` regions and smaller eagerly-expanded regions.
- Checking a lazy **Iterations** group now materializes its individual iteration rows and carries the requested check state to them, so the checkbox is functional before manual expansion rather than cosmetic only.
- Reuse one helper for eager and lazy Iterations-group checkbox configuration; TXT/IBW tree construction remains on its existing eager path.

## 0.11.87 - 2026-09-26

- Fix Processed Data map view-state synchronization so **Simple** never retains controls from a previously active **Lines** or **ROI** representation.
- Centralize representation-specific control visibility: Lines shows bin/thickness and trace controls, ROI shows ROI and trace controls, and Simple hides all representation-specific groups.
- Apply the same visibility synchronization after PANDA silently resets a newly activated Processed Data map to Simple, eliminating the intermittent stale-control state without changing TXT, IBW, or XY data handling.

## 0.11.86 - 2026-09-26

- Add XY-specific lazy expansion for large SPECS/Prodigy `.xy` regions (250+ exported acquisitions): the Average and cached full iteration stack are available immediately, while individual Iteration tree leaves are created only when the user expands **Iterations**.
- Keep small `.xy` regions on the existing eager tree path so ordinary files retain the familiar PANDA tree behavior.
- Keep TXT and IBW tree construction unchanged: lazy expansion is gated strictly to `SpecsXYRegionData` and does not alter their parser, loader, or tree behavior.
- Add regression coverage proving a 300-iteration `.xy` region is lazy while an equivalently sized TXT region remains eager.

## 0.11.85 - 2026-09-25

- Harden the new SPECS/Prodigy `.xy` path against PANDA's existing downstream workflow contract without changing TXT/IBW parsing or behavior.
- Preserve Prodigy's declared ordinate convention on each adapted region (`counts/s` for the supplied exports) so later UI work can distinguish native CPS data from raw-count sources without inventing a dwell-time conversion.
- Add compact acquisition provenance to `.xy` region metadata (exported acquisition count, first/last acquisition timestamp when present, Cycle range, and Scan/Channel index kind) while keeping the full per-acquisition metadata in the XY-specific adapter object.
- Add regression coverage showing `.xy` regions feed the same 1D trace and 2D iteration-array contracts consumed by Raw Data maps, normalization, calibration/fitting payloads, and batch-map preparation.
- Keep `.xy` compatibility fixes confined to the `.xy` adapter/test boundary; existing TXT/IBW parser modules and downstream workflow modules remain unchanged.

## 0.11.84 - 2026-09-25

- First user-visible SPECS/SpecsLab Prodigy `.xy` integration.
- Added **Load → XY (SPECS Prodigy)** and `.xy` drag-and-drop support.
- `.xy` files are parsed by the isolated 0.11.82 parser and normalized by the isolated 0.11.83 adapter before entering the existing PANDA Raw Data tree/plot path.
- Reload-from-disk now recognizes `.xy` sources through the same provenance-aware reload policy.
- TXT and IBW parsers/loaders are unchanged; `.xy` remains a separate upstream format path.

## 0.11.83 - 2026-09-25

- Add an isolated SPECS/Prodigy `.xy` adapter that converts the neutral 0.11.82 parser output into PANDA's existing RegionData-style normalization contract: energy in column 0 and one or more spectra/iterations in subsequent columns.
- Preserve TXT/IBW runtime behavior: `.xy` is still not registered in loader dispatch, the Raw Data tree, plotting, or Live Monitor, and no existing TXT/IBW parser/loader modules are modified.
- Normalize repeated `.xy` acquisitions to PANDA's ordinary **Iteration** second dimension for the first integration milestone, while retaining Cycle/Curve/Scan/Channel identifiers, acquisition timestamps/parameters, Group metadata, and external-channel blocks for later use.
- Align incomplete acquisitions against the actual majority energy grid, including non-uniform SnapshotFAT axes; badly incomplete acquisitions are discarded with warnings instead of forcing a truncated common grid.
- Keep unique region names unchanged and disambiguate repeated Prodigy region names only when necessary using Spectrum ID, preparing large mixed exports such as `AllData.xy` for the existing PANDA tree/workflow model.
- Validate the adapter against all supplied real `.xy` examples, including the 109 MB `AllData.xy`, without warnings or loss of complete acquisitions.

## 0.11.82 - 2026-09-25

- Add a standalone streaming parser for SPECS/SpecsLab Prodigy `.xy` exports as an isolated first step toward future `.xy` loading; it is not yet registered in PANDA's loader dispatch or Raw Data UI.
- Preserve Prodigy file/group/region structure, Spectrum ID, Cycle/Curve/Scan/Channel identifiers, acquisition timestamps/parameters, actual sampled energy arrays (including nonuniform SnapshotFAT grids), extra numeric columns, and external-channel blocks without converting them into PANDA/TXT/IBW concepts yet.
- Treat the acquisition blocks physically present in the file as authoritative instead of trusting nominal metadata such as `Number of Scans`, and accept valid header-only/empty Prodigy exports.
- Add parser regression coverage for standard scan exports, SnapshotFAT Channel blocks, bare Curve blocks when scans are combined, repeated names/group sessions, external channels, nonuniform energy grids, extra columns, and empty files.
- Keep existing TXT and IBW runtime paths untouched; 0.11.82 is intentionally parser-only.

## 0.11.81 - 2026-09-25

- Tighten the left margin of Lines/ROI-style map layouts and move the map/bottom-trace Y-axis titles closer to their tick labels, reclaiming horizontal space for the data area while keeping the two titles aligned.
- Keep the fixed-width map cursor readout, but add a modest inset after the Matplotlib toolbar buttons and reduce the fixed field widths so the three coordinate values are more compact without crowding the tools or pushing Intensity off-screen.
- Apply the same compact margins and coordinate spacing to Live Monitor.

## 0.11.80 - 2026-09-25

- Fixed Raw Data and Processed Data **View: Simple** iteration-only maps so the mirrored left Y axis uses exactly the same Iteration values as the right Y axis; the generic scientific-intensity formatter is no longer applied to the map Y axis.
- Compacted the fixed-width map coordinate readout columns and left-anchored them after the Matplotlib toolbar buttons, keeping BE/KE, PhE/Iteration, and Intensity stable without extending unnecessarily to the far right.
- Applied the same compact coordinate layout to Live Monitor while retaining the system fixed-width font used to prevent macOS jitter.

## 0.11.79 - 2026-09-25

- 2D maps without an independent physical second dimension now show **Iteration** on the map's left Y axis as well as on the right-hand vertical trace, instead of leaving the map Y axis blank.
- Lines/ROI and Live Monitor use a fixed full left margin and identical axes-coordinate placement for the map Y title and bottom-trace **Intensity** title, keeping the two labels horizontally aligned and preventing clipping.
- Map coordinate readouts keep their non-wiggling fixed-width font on macOS, but now use the system fixed-width face at the normal toolbar text size for a more native appearance.

## 0.11.78 - 2026-09-24

- Change the 2D-map palette discovery hint from immediate-on-entry to a dwell interaction: mouse movement over a map restarts a 1 s timer, so **Right-click to change palette** appears only after the pointer has remained still on the image for about one second.
- Keep the discovery hint visible for 5 s once shown.
- Make the hint repeat once per representation visit: switching among Raw Data / Simple / Lines / ROI and later returning starts a fresh visit, while repeated cursor movement within the same uninterrupted view does not retrigger it.
- Apply the same one-second dwell behavior to Live Monitor and update Help/regression coverage.

## 0.11.77 - 2026-09-24

- Fixed the one-time 2D-map palette discovery tooltip so it is actually shown under PyQt6, and extended its display time from 2.5 s to 5 s.
- Made right-click palette selection work on 2D maps rendered through overlapping/twinned axes, notably Raw Data maps and **View: Simple**, while retaining the existing behavior in Lines, ROI, ResPES, batch maps, and Live Monitor.
- Updated Help for the five-second discovery hint and the Raw Data / Simple right-click palette workflow.

## 0.11.76 - 2026-09-24
- Make **terrain** the default palette for every PANDA 2D map, including Processed Data maps, batch Prepare maps, ResPES maps, and Live Monitor.
- Replace redundant palette buttons with one consistent interaction: **right-click inside the 2D map** to open the existing palette chooser. Right-click is kept separate from Lines/ROI/normalization/cut dragging.
- Add a brief one-time **Right-click to change palette** hover hint when the pointer first enters a map; it is not repeated for the same displayed map/Live Monitor window.
- Update Help and regression coverage for the new palette workflow.

## 0.11.75 - 2026-09-24
- Make Live Monitor cursor-coordinate presentation match Processed Data **View: Lines** exactly: H/V on-map labels now use the same sample-spacing-aware precision, including one-decimal photon-energy labels where appropriate.
- Give the Live Monitor 2D map the same Matplotlib toolbar coordinate readout as View: Lines: **BE/KE**, **PhE/Iteration**, and nearest-pixel **Intensity**, with the same fixed field widths and scientific intensity formatting.
- Use the same fixed-width toolbar font in Live Monitor so coordinate fields remain visually stable on macOS as well as Windows.
- Update Help and add regression coverage for Live Monitor coordinate parity with View: Lines.

## 0.11.74 - 2026-09-24
- Make Live Monitor Lines Y-axis handling match Processed Data **View: Lines**: genuine physical second dimensions such as photon energy are shown on the map's left Y axis, while **Iteration** remains on the right-hand vertical trace.
- Make the Live Monitor horizontal cursor label follow the map Y representation (for example **PhE = ... eV**) instead of incorrectly labelling a physical second dimension as Iteration.
- Preserve ordinary iteration-only acquisitions: iteration scales remain on the right trace and no redundant left Y axis is shown.
- Move the Live Monitor control row above the Matplotlib toolbar so only spectra/update/status diagnostics remain below the plot.
- Update Help and add regression coverage for the dual-Y-axis Live Monitor layout and control placement.

## 0.11.73 - 2026-09-24
- Add the Processed Data **View: Lines** cross-section UX to Live Monitor: horizontal trace below the growing map, vertical trace to the right, continued H/V cursor guides, coordinate labels, direct side-trace dragging, and crossing-point dragging of both cursors.
- Add Live Monitor **H thickness** and **V thickness** controls with the same odd 1-25 symmetric averaging and visible averaging bands used by View: Lines.
- Preserve the selected H/V cursor coordinates as new spectra append, while keeping palette selection and main-window **Flip X axis** synchronization intact.
- Update Help and regression coverage for the new Live Monitor Lines-style inspection workflow.

## 0.11.72 - 2026-09-24
- Fix Live Monitor recovery from the idle **Acquisition appears stopped** state: idle Auto monitoring still checks every 5 s, but once a file change is detected PANDA now switches immediately to the short settle/recheck cycle so a fast restarted acquisition cannot keep changing between sparse polls without ever being parsed.
- Keep same-filename restart handling and Auto timing relearning unchanged after the first valid snapshot of the new run is accepted.
- Rename the PANDA expansion consistently to **Photoemission Analysis, Normalization and Data Assessment** across UI/About text, Help, package metadata, historical branding text, and regression tests.
- Update Help and regression coverage for the idle-restart polling transition.

## 0.11.71 - 2026-09-24
- Add explicit Live Monitor acquisition-state feedback: **Monitoring** (green), **Acquisition appears stopped** (dark orange), and user-stopped **Stopped** (red), with the state descriptor shown in bold.
- After timing has been learned, mark an acquisition as apparently stopped after `max(30 s, 5 × learned spectrum interval)` without a successful new spectrum.
- Keep idle monitoring active so same-filename restarts are still detected automatically; in Auto, relax lightweight file-status checks to 5 s while idle.
- Reserve the Live Monitor status line for acquisition state so **Reload latest snapshot** no longer overwrites it with an action message.
- Update Help and regression coverage for the idle/stop status workflow.

## 0.11.70 - 2026-09-23
- Audit both packaged Help rubrics against the recent source-reload, Live Monitor, multi-region TXT, All-in-region, and 2D-map UX changes.
- Replace the last two stale **Flip BE** references with the current **Flip X axis** control name.
- Add a regression guard preventing the obsolete label from returning to packaged Help.

## 0.11.69 - 2026-09-23
- Fix **All in region** so unchecking the control clears the group-selected spectra from the Loaded/Selected selection and therefore removes them from the plot immediately.
- Stabilize 2D-map toolbar coordinate readouts across platforms by using a fixed-width font while MAP rendering is active; this removes the residual macOS left/right wiggle caused by proportional glyph widths.
- Restore the normal toolbar font automatically when returning to ordinary 1D plotting.
- Update Help and regression coverage for both behaviors.

## 0.11.68 - 2026-09-23
- Add independent region-defined Live Monitor windows for multi-region structured TXT acquisition files.
- Multi-region TXT files now expose an **Open live monitor** submenu listing each parsed region by name; several regions from the same physical TXT file can be monitored simultaneously.
- Propagate the selected region index through the Live Monitor window/controller/worker/core so each monitor extracts only its assigned region while retaining independent pause, timing, palette, zoom, and restart state.
- Key open Live Monitor windows by **file path + region index** and include the region name in the window/map title.
- Keep normal IBW behavior file-based, since each analyzer region is normally recorded into its own IBW file.
- Update Help and add regression coverage for region discovery, second-region extraction, UI routing, and independent monitor identities.

## 0.11.67 - 2026-09-23
- Clarify Live Monitor timing labels: **Checked every**, **Settle for**, and **New spectrum every** replace mode-specific/checking jargon while leaving the Auto timing algorithm unchanged.
- Expand Help with a precise explanation of lightweight file-status polling, the post-change settle period, and the learned spectrum interval, including the current Auto/fixed timing values.
- Make the Live Monitor X-axis use the parsed Binding/Kinetic Energy title and stay synchronized with the main PANDA **Flip X axis** control.
- Detect a new acquisition epoch when the same monitored filename restarts from the first iteration; reset only the Auto timing-learning history so the live map updates automatically and the inter-run idle gap cannot inflate the learned spectrum interval.
- Add regression coverage for restart timing, energy-axis metadata, labels, and Help documentation.

## 0.11.66 - 2026-09-23
- Polish the Live Monitor window for normal background use: it now behaves as an independent top-level window with standard minimize/maximize controls and does not keep PANDA alive after the main window closes.
- Replace the user-facing term **cadence** with the clearer **acquisition interval**; timing details now use **check** and **stable wait** wording instead of poll/settle jargon.
- Add **Reload latest snapshot** to the Live Monitor and route it through the same provenance-aware source reload policy used by **Reload from disk** and duplicate **Load** actions.
- Add the same 🎨 color-palette chooser used by Processed Data 2D maps; the selected palette is retained across live-map resets/rebuilds.
- Update Help and regression coverage for the revised Live Monitor workflow.

## 0.11.65 - 2026-09-23
- Extend source-reload protection to workflow uses that do not create persistent processed-tree children.
- Record successful Processed Data normalization against the immutable source snapshot, so a normalized-only curve triggers the protected reload choices even when it was never sent to Plotted Data.
- Record curves handed to the single/batch peak-fitting workflow as source uses, so later reload cannot silently replace the snapshot behind fitting work.
- Keep energy-calibrated derivatives covered by the existing processed-curve dependency scan.
- Clarify the reload warning to cover both processing use and derived data.

## 0.11.64 - 2026-09-23
- Fix source-snapshot provenance being dropped when Processed Data curves are renamed for transfer to Plotted Data.
- Preserve provenance when the main plot title is rebuilt, preventing the first selected curve from silently losing its source snapshot metadata.
- Reloading a source that has a normalized/CPS curve copied to Plotted Data now triggers the derived-data warning and reports the plotted dependency.

## 0.11.63
- Introduce a general source-snapshot reload policy for all loaded TXT/IBW files.
- Detect repeated loads by canonical full path and route duplicate Load actions through the same reload decision as **Reload from disk**.
- Treat loaded sources as immutable snapshots once processed or plotted data depend on them; offer **Load updated copy**, **Replace and remove dependent data**, or **Cancel** instead of silently invalidating provenance.
- Give updated copies unique snapshot IDs/source labels while retaining the physical filename/path in metadata.
- Propagate source-snapshot provenance through loaded curve payloads, normalization, energy calibration, CPS conversion, and Plotted Data snapshots.
- Add a public provenance-aware removal API to Plotted Data so reload policy code does not depend on panel internals.
- Preserve selected/processed data belonging to unrelated files when one source snapshot is replaced.

## 0.11.62 - 2026-09-23

- Added the first complete Live Monitor frontend for growing IBW/TXT acquisition files.
- Right-click a loaded file-level tree entry and choose **Open live monitor** to open a dedicated non-modal 2D map window.
- The live window consumes the existing threaded backend reset/append events, shows spectra count, last update, status, and learned Auto poll/settle/cadence timing.
- Added Auto plus 1/2/5/10 s timing choices and reversible Start/Stop controls.
- Live updates remain isolated from the normal Raw Data selection and plot, and closing the window shuts down its worker thread cleanly.
- Updated Help for the specialized acquisition-time workflow.

## 0.11.61 — 2026-09-23

- Added the backend for monitoring a growing analyzer data file, without exposing the feature in the GUI yet.
- Added a thread-agnostic live-monitor core that detects file size/mtime changes, waits for a stable file state, parses temporary snapshots, emits only newly appended spectra, and detects acquisition restarts/replacements.
- Added Auto timing state with an adaptive metadata polling interval derived from observed acquisition cadence, plus fixed polling mode support.
- On Windows, live-file snapshots use explicit `FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE` access so PANDA never denies analyzer writes/replacements; snapshots are discarded if source metadata changes while being copied.
- Added a `LiveFileMonitorWorker` and `LiveFileMonitorController` that guarantee monitoring/parsing runs in a dedicated `QThread`, with clean Start/Stop/shutdown behavior and no modal warnings for transient read/parse failures.

## 0.11.60 — 2026-09-22

- Added reversible preview-on-highlight browsing to the Raw Data **All in region** selector: mouse hover or arrow-key highlight previews a region without changing loaded-tree check states or the selected-curve tree.
- Clicking or pressing Enter commits the chosen region; Esc/dismissing the popup restores the previously committed plot and combo selection.
- Documented the preview interaction in Help.

## 0.11.59 — 2026-09-22

- Audited and updated both packaged Help rubrics so current workflows are represented consistently, including metadata inspection, reusable fit configurations, the peak-only vs SO-doublet batch paths, derived SO-doublet rows, and next-pass versus analytical trend fitting.
- Documented that derived SO-doublet minor trends remain diagnostic/plottable but are not independent next-pass constraint targets; residual minor-energy variation may remain when SO splitting is allowed to vary.
- Routed every PANDA `QMessageBox` call site explicitly through the silent non-native wrapper, including dynamically imported calibration/processed-data warnings, so pop-up messages and warnings do not request native system sounds.
- Added regression coverage for Help workflow coverage and silent-message-box imports.

## 0.11.57 — 2026-09-22

- Refactored the Analyze-tab UI construction into focused private builder methods.
- Preserved existing widgets, signal connections, layouts, and fitting/analysis behavior.
- Kept `batch_analysis.py` and the dedicated plot/trend/constraint/export modules unchanged.

## 0.11.58

- Consolidation release after the fitting/batch-analysis refactor.
- Removed stale copied imports from batch workflow mixins and two shared batch cores.
- No fitting, batch-processing, or GUI behavior changes intended.


## 0.11.56 — 2026-09-22

- Refactor: extracted Analyze parameter-tree selection and trend plotting helpers from `batch_analysis.py` into `batch_analysis_plot.py`.
- Preserved all existing Analyze-tab method names and plotting behavior through `BatchAnalyzeMixin`; no fitting, constraint, trend-model, or export behavior is intentionally changed.
- Kept high-level Analyze-tab refresh/orchestration in `batch_analysis.py`.

## 0.11.55 — 2026-09-22

- Refactor: extracted the next-pass smoothing/constraint workflow from `batch_analysis.py` into `batch_analysis_constraints.py`.
- Preserved the existing smoothing/constraint entry points and SO-doublet derived-minor exclusion logic; no intended fitting-behavior change.
- Kept shared series identity and ordinary Analyze plotting in `batch_analysis.py`.

## 0.11.54 — 2026-09-22

- Refactor: extracted analytical batch trend-fitting and summary helpers from `batch_analysis.py` into `batch_analysis_trends.py`.
- Preserved existing trend-fit entry points and behavior; next-pass smoothing/constraint logic remains in `batch_analysis.py`.

## 0.11.53 - 2026-09-22

- Begin decomposition of `batch_analysis.py` by extracting CSV/ZIP export and export-reporting helpers into `batch_analysis_export.py`.
- Preserve the existing Analyze-tab export entry points through `BatchAnalyzeMixin`; no fitting, trend, smoothing, or next-pass constraint behavior is intentionally changed.
- Keep shared series identity in `batch_analysis.py` for now; the export module reuses it rather than duplicating the helper.

## 0.11.51 - 2026-09-22

## 0.11.52

- Fix the SO-doublet next-pass target filter by exposing the derived-minor helper methods through `BatchAnalyzeMixin`; this restores major/ordinary-peak targets while still omitting derived minor members.
- Add regression coverage for the smoothing-target helper delegation path.

- Prevent derived SO-doublet minor-member peaks from appearing in the Trend smoothing / next-pass constraint target list.
- Keep minor-member trends available for plotting and analytical diagnostics.
- Add defensive guards so stale minor-member trend models/constraints cannot be added or executed as independent next-pass constraints.
- No change to peak-only batch fitting or to the SO-doublet fit model itself.

## 0.11.50 - 2026-09-22

- Fix a batch-validation runtime regression in both peak-only and SO-doublet configuration paths: restore the explicit `datetime` import required when stamping generated batch configurations.
- Add a regression guard ensuring both path-specific batch config modules import `datetime` locally before using `datetime.now()`.
- No fitting, table-building, constraint, or batch-runner behavior changed.

## 0.11.49 - 2026-09-21

- Consolidated the batch refactor from 0.11.46–0.11.48 without changing batch-fitting behavior.
- Shared table/config/runner helpers now delegate directly to their core modules instead of being re-exported through path-specific policy modules.
- Removed stale shared-core import scaffolding and the obsolete table-module reload workaround.
- Kept all genuinely peak-only vs SO-doublet policy functions separate.

## 0.11.48 - 2026-09-21

- Refactored the batch runner into a shared path-neutral `batch_runner_core.py`.
- Both peak-only and SO-doublet batch paths now reuse 22 identical execution/navigation/constraint helpers.
- Kept `_fit_one_batch_spectrum` separate in each runner so model/state preparation remains path-specific.
- No intended fitting-behavior changes.

## 0.11.47 - 2026-09-21

- Refactored batch parameter-table construction to share 12 path-neutral helpers through `batch_table_core.py`.
- Kept item construction, row assembly, and table population separate for peak-only and SO-doublet-aware workflows.
- Preserved the frozen peak-only batch runner and added regression guards for the new table-core boundary.

## 0.11.46 - 2026-09-21

- Refactored batch configuration to share nine path-neutral helpers in `batch_config_core.py`.
- Kept doublet-aware and peak-only validation/build/interpolation logic in their separate modules.
- Preserved the frozen peak-only table builder and runner unchanged.
- Updated regression guards to validate the shared-core boundary instead of requiring the peak-only config file to remain byte-identical.

## 0.11.45

- Consolidated the single-fit dialog refactor from 0.11.40–0.11.44 without changing fitting behavior.
- Removed stale copied imports left behind when dialog responsibilities were split into focused mixins.
- Added regression coverage to keep the refactored fitting modules free of unused imports.

## 0.11.44

- Refactor only: reduced `FitCoreLevelDialog.__init__` to orchestration by extracting focused private builders for curve selection, plotting, parameter/results tabs, splitter setup, dialog buttons, and initial curve population.
- Preserved existing widget construction, signal connections, object names/attributes, layout order, and fitting behavior.

## 0.11.42

- Refactor only: extracted peak-parameter constraint and tie handling from `FitDialogFitMixin` into the dedicated `FitDialogConstraintsMixin`.
- Preserved all existing constraint method names, call paths, tie semantics, and fitting behavior.

## 0.11.38 — 2026-09-21

## 0.11.41

- Refactor: extracted fit-setup persistence and single-fit export actions from `FitDialogStateMixin` into the dedicated `FitDialogIOMixin`.
- Kept fit-setup capture/apply state logic in `FitDialogStateMixin`; behavior and public method names are unchanged.

## 0.11.40

- Refactor only: extracted spin-orbit doublet state/UI/relationship management from `FitDialogStateMixin` into `FitDialogDoubletMixin`.
- Preserved existing SO-doublet method names, call paths, and fitting behavior.


- Fix the SO-doublet batch setup crash caused by missing `BatchFitDialog` delegation for `_build_doublet_parameter_rows`.
- Add the also-required `_doublet_union_model` delegation, preventing the next runtime failure in the same doublet-aware path.
- Add a helper-surface regression test ensuring every internal `batch_table_builder.py` helper invoked through `self` is exposed by `BatchPrepareSetupMixin`.
- No peak-only batch behavior or SO-doublet fitting semantics changed.

## 0.11.37 — 2026-09-21

- Reworked SO-doublet batch preparation to mirror the established peak-only philosophy: the batch model is the union of user-labelled components across fitted anchors, so doublets may appear or disappear across a series.
- Made the user-assigned doublet label the primary batch identity; energy shifts, intensity changes and numerical fit values do not create a new component.
- Require consistent major/minor peak labels and Same/Independent L/G/Alpha relations only where the same labelled doublet is present in multiple anchors; reject ambiguous reuse of its constituent labels as ordinary peaks.
- Build Splitting/Ratio rows and generated batch doublet states from the union model rather than copying Start-anchor topology.
- Preserve grey Derived minor parameters and editable Independent minor shape parameters; standalone/manual-tied peaks remain supported in the doublet-aware path.
- Make missing components in fitted anchors contribute zero-height guide points while unfitted anchors contribute no artificial absence.
- Shorten the first-anchor reminder and clarify that peak/doublet labels define component identity across the series; add the same guidance to the SO-doublet label tooltip and Help.
- Keep the isolated 0.11.31 peak-only batch modules unchanged.

## 0.11.36 — 2026-09-21

- Restore the complete known-good 0.11.31 peak-only batch table, configuration, initial-guess, and fitting implementations as isolated legacy paths.
- Route peak-only batch setups exclusively through those preserved modules; SO-doublet batch setups use the newer doublet-aware modules.
- Prevent SO-doublet table metadata, Derived rows, or modified tie handling from affecting ordinary peak-only batch fitting.
- Preserve manual peak-level Tied relationships exactly as in the pre-doublet batch workflow.
- Add reference-hash regressions proving the isolated peak-only modules remain byte-for-byte identical to the 0.11.31 implementation.

## 0.11.35 — 2026-09-21

- Fix a regression where **Validate setup** crashed even for peak-only batch tables because `BatchFitDialog` did not expose the new `_batch_row_metadata` helper used by `batch_config.py`.
- Add a helper-surface regression check so every `batch_config.py` helper invoked through `self` must have a corresponding `BatchRunMixin` delegation.
- No batch-fit model, table-layout, or SO-doublet semantics changed in this bug-fix release.

## 0.11.34 — 2026-09-21

- Add a one-time informational note before the first anchor fit in each batch setup, explaining that explicit SO-doublet topology must remain consistent across anchors.
- Add explicit peak-only and doublet-aware batch-table modes; peak-only setups keep the previous table layout unchanged.
- In doublet-aware mode, expose SO-doublet Splitting and Ratio as editable batch parameters and show mathematically controlled minor-component parameters as disabled `Derived` rows.
- Keep Independent minor LFWHM/GFWHM/Alpha parameters editable as ordinary peak parameters.
- Validate fitted-anchor SO-doublet topology before creating or validating a batch setup, rejecting mixed peak-only/doublet anchors, changed major/minor pairings, or changed Same/Independent shape relations.
- Propagate edited doublet-level batch constraints into each generated sequence-fit state while preserving ordinary peak-level Free/Fixed/Tied behavior.

## 0.11.33 — 2026-09-21

- Fixed a batch SO-doublet regression where **Validate setup** crashed with `NameError: so_doublets is not defined`.
- Added a regression guard requiring the batch configuration module to import the shared SO-doublet helper used when generating sequence guesses.

## 0.11.32 - 2026-09-20

- Preserve SO-doublet topology from fitted Start anchors in generated batch-fit states.
- Batch fitting now honors dedicated doublet splitting, ratio, tied doublet parameters, and Same/Independent L/G/A relations through the same fit engine used by single-curve fitting.
- Free doublet splitting/ratio receive per-spectrum initial guesses from the generated constituent peaks; Fixed values retain the anchor definition.
- Store fitted SO-doublet values back into each batch result so subsequent passes retain the structured relationship.
- Update Help to describe batch support accurately; the batch setup table remains peak-oriented and does not yet expose separate doublet-level rows.

## 0.11.31 - 2026-09-20

- Make the Load fit setup dialog default to ordinary `*.json` files instead of presenting `*.fit.json` as the primary filter.
- Keep `.fit.json` as the suggested save-name convention; loading accepts any JSON filename supported by the fit schema.

## 0.11.30 - 2026-09-20

- Add an explicit versioned schema/migration layer for peak-fit setup JSON files without changing the current on-disk schema.
- Keep `FORMAT_VERSION = 1` because no real fit-setup schema change has occurred; v1 files continue to round-trip unchanged.
- Route all fit-setup loading through a canonical envelope validator before typed `FitSetupState` normalization.
- Preserve support for historical raw fit-setup dictionaries by treating them as implicit v1 input internally.
- Reject unsupported future format versions with a clear message instead of attempting to interpret them.
- Establish a one-version-at-a-time migration registry so future v2+ schema changes can be added in a controlled, testable path.

## 0.11.29 - 2026-09-20

- Refactor the single-curve peak-fit dialog into separate background, component-display, and peak-interaction mixins without changing fitting behavior or saved-state formats.
- Keep existing method names and call sites stable while reducing `fit_dialog_background_mixin.py` from ~1300 lines to a focused background-only module.
- Move calculated-spectrum rendering, Doublet-view component display, residuals, peak colors, and marker drawing into `fit_dialog_component_display_mixin.py`.
- Move draggable peak-marker behavior and peak initialization/default-placement logic into `fit_dialog_peak_interaction_mixin.py`.
- Update source-contract regression tests to follow the new module boundaries and add explicit coverage for the responsibility split.

## 0.11.27 - 2026-09-20

- Restore direct mouse control of At-BE/Area normalization bands in Lines and ROI map views.
- Resolve overlap by explicit hit priority: active Lines cursors or the ROI own clicks on their handles/area, while the normalization band remains movable/resizable everywhere else.
- Keep the established Lines/ROI drag handlers unchanged; arbitration happens only before the normalization band starts its drag.

## 0.11.28 - 2026-09-20

- Fixed Scienta IBW second-axis detection for genuine ResPES files when igor2 does not expose the trailing axis descriptor through the wave note. PANDA now uses embedded printable IBW text as a conservative metadata fallback.
- Fixed parsing of CR-separated `Point N=<photon energy> eV` records, allowing explicit ResPES photon-energy axes to be recovered correctly.
- Kept `Region Iteration` acquisitions classified as iteration-only, preventing false ResPES suggestions.

## 0.11.26 - 2026-09-20

- Fixed Lines/ROI mouse interaction when map normalization is set to Area (and At BE): normalization bands are now passive in Lines/ROI views so they cannot intercept line/ROI drags.
- Normalization-band mouse dragging remains available in Simple view; Lines/ROI normalization limits are adjusted from the existing normalization settings dialog.

## 0.11.25 — 2026-09-20

- Restored the established pre-0.11.24 2D Lines/ROI mouse interaction implementation exactly, after the 0.11.24 overlay-axis changes proved state-sensitive in real GUI use.
- Retained the independent IBW dimension-2 parser fix: `Region Iteration` is no longer mislabeled as photon energy and does not trigger ResPES suggestions.
- Removed the 0.11.24 experimental mouse-width resizing additions and their documentation/tests.

## 0.11.24 - 2026-09-20

- Fix Scienta Add Dimension IBW detection so a second dimension labelled `Region Iteration[a.u.]` remains iteration rather than being inferred as `Photon Energy [eV]`; ResPES is therefore offered only when photon energy is explicitly identified.
- Fix Lines/ROI mouse interaction when an Average or other spectrum overlay creates a transparent Matplotlib `twinx()` axis: cursor movement, ROI movement/resizing, and normalization-band dragging now use map coordinates reconstructed from mouse pixels.
- Make visible H/V averaging-band borders draggable in Lines view to resize the corresponding odd line thickness, with the H/V thickness controls kept synchronized.
- Add regression coverage for overlay-axis cursor dragging, ROI move/resize, Lines thickness resizing, and iteration-only IBW second-dimension metadata.

## 0.11.23 - 2026-09-20

- Introduce typed internal peak-fit state models (`PeakState`, `DoubletState`, and `FitSetupState`) as the first refactoring step toward safer future fitting development.
- Route peak capture/restore, fit-setup capture/apply/load/save, and SO-doublet normalization through the shared state layer while keeping the existing dictionary interfaces used by the GUI and fit engine.
- Keep the external `.fit.json` schema at format version 1; existing v1 fit setups and manual `Tied to ...` constraints round-trip unchanged.
- Preserve sparse legacy/batch peak-state dictionaries exactly on round-trip so internal defaults cannot become accidental fit bounds or constraints.
- Add state validation for malformed numeric values/bounds and regression coverage for historical v1 setup compatibility, manual ties, SO-doublet state, and sparse states.

## 0.11.22 - 2026-09-20

- Fix the remaining duplicate-region suggestion in **Save fit setup** for real loaded-curve keys such as `Ir4f_170eV#1`: the internal `#N` region index is now kept separately while the physical region name is deduplicated against the source filename.
- Make the Save dialog use the same tested `suggest_fit_setup_path()` helper that produces its exact initial pathname.
- Also handle region-prefixed curve labels when separate region metadata is absent, and ignore a trailing `(N)` file-copy suffix for region comparison without changing the displayed source stem.

## 0.11.21 - 2026-09-19
- Pure structural cleanup with no intended GUI/fit-model behavior changes. Removed three superseded Plotted Data modules (`curve_list.py`, `dialogs.py`, `io.py`), their obsolete CSV-I/O test, the unused `FitResult` container, and two legacy FlexPES icon assets.
- Consolidated the peak-fit cancellation exception into one shared `FitCancelled` definition and updated the interruption regression accordingly.
- Centralized compact source/region/curve filename identity construction so fit-setup and single-fit export naming use the same deduplication logic.
- Added cleanup/release regression checks for obsolete files, the minimal two-file `flexpes_pes` compatibility shim, shared cancellation handling, and naming consistency.
- Added `tools/build_release.py` to validate and create clean release ZIPs from a fresh tree, excluding caches/build artifacts and rejecting known obsolete files.
- Lowered the build-system declaration from `setuptools>=68` to `setuptools>=61`, the first setuptools release supporting PEP 621 project metadata used by PANDA, to reduce unnecessary offline-install friction.

## 0.11.20 - 2026-09-19
- Extended fit-setup filename deduplication to curve/trace labels that already start with the region identity, so names such as `Ir4f_170eV#1_Trace` no longer cause the region to appear twice.
- Applied the rule whether the region is already embedded in the source filename or is added as its own filename token, while preserving the remaining trace identifier.

## 0.11.19 - 2026-09-19
- Reworked the fitting Help so the original peak-level Tied mechanism and the dedicated SO-doublet workflow are described as parallel capabilities. SO doublets are an additional structured option, not a replacement or preferred alternative.
- Restored a practical manual-tie workflow, including the actual relation semantics: Energy preserves an offset, while Height/LFWHM/GFWHM/Alpha preserve multiplicative factors.
- Clarified that Doublet view applies only to grouped SO doublets, while manually tied ordinary peaks remain individual components.
- Refined the batch caveat so only dedicated doublet-level Splitting/Ratio constraints are identified as not yet propagated; the existing per-peak Free/Fixed/Tied batch mechanism remains documented separately.

## 0.11.18 - 2026-09-19
- Reworked Help coverage for the SO-doublet fit workflow so What is what? and How to consistently describe creation from Major/Minor peaks, naming, orbital presets, bounded Fixed/Free/Tied Splitting and Ratio, Same/Independent shape relations, cloning, ungrouping, and Doublet view.
- Removed the outdated workflow guidance that taught manual peak-to-peak ties as the primary way to build spin-orbit doublets.
- Documented the current batch limitation: sequence fitting uses flattened individual peak states and does not yet propagate doublet-level Splitting/Ratio ties as batch constraints.

## 0.11.17 - 2026-09-19
- Avoid repeating a region name in suggested fit-setup JSON filenames when the source filename already ends with the same region identity.

## 0.11.16 - 2026-09-19

- Synchronized peak-parameter color swatches with the resolved colors actually used by the fit plot and draggable peak handles.
- Automatic collision-avoidance recoloring now updates the parameter table in the same redraw cycle, while stored/custom color choices remain unchanged and persistent.
- Added regression coverage for plot/table color synchronization.

## 0.11.15 - 2026-09-19

- Fixed SO-doublet ungrouping so the former minor component fully returns to an ordinary standalone peak, including re-enabling all Energy/Height/LFWHM/GFWHM/Alpha constraint-mode selectors.
- Added regression coverage for the group -> ungroup constraint-control reset.

## 0.11.14 - 2026-09-19

- Made automatic fit-component colors distinct in both individual-peak and Doublet view representations.
- Added explicit automatic-vs-custom color state: user-selected colors are preserved, while PANDA-managed colors may be reassigned to avoid visible duplicates.
- In Doublet view, summed SO doublets and standalone peaks now receive colors based on the visible grouped components rather than the underlying peak indices; the surviving major handle uses the same display color as its summed doublet.

## 0.11.13 - 2026-09-19

- Made automatic initial peak suggestions more robust to noisy/rippled spectra by requiring multi-scale persistence (or exceptionally strong fine-scale prominence).
- Initial peak heights are now estimated above the local prominence contour instead of using absolute spectrum intensity, preventing tiny background ripples from seeding huge ghost fit components.
- Added regression coverage for noisy high-background spectra and background-subtracted initial amplitudes.

## 0.11.12 - 2026-09-19

- Refined fit-parameter tooltips so they are selective and context-specific rather than attached broadly to whole cards. The SO-doublet composition tooltip now appears only on the bold doublet title.
- Added concise explanations for SO splitting, major/minor intensity ratio, tied/free/fixed constraint selectors, LFWHM/GFWHM/Alpha, and Same/Independent doublet relations. Obvious controls remain uncluttered.
- Cleaned the PANDA application icon so the canvas outside the black rounded border is transparent, while preserving the existing artwork inside the border. Regenerated PNG, ICO, and ICNS assets from the cleaned master.

## 0.11.11 - 2026-09-19

- Made SO-doublet naming independent of constituent peak naming. Named doublet families now use `Name #1`, `Name #2`, ... from the first member; unnamed doublets use `Doublet #1`, `Doublet #2`, ....
- Cloning any member of a doublet family selects the next sibling number without recursive suffixes, while legacy `(clone)` / `(N)` names are normalized when encountered.
- Constituent fit peaks now keep the simple `P1`, `P2`, `P3`, ... convention; cloning a doublet creates new members with the next `Pn` labels rather than clone-derived labels.
- Added a doublet-card tooltip identifying its constituent major and minor `Pn` peaks.

## 0.11.10 - 2026-09-19

- Replaced recursive clone labels such as `P1 (clone)(clone)` and `S 2p (2) (2)` with clean sibling numbering. Once a family is cloned, PANDA presents it as `P1 #1`, `P1 #2`, ... or `S 2p #1`, `S 2p #2`, ...; legacy suffixes are normalized when that family is cloned again.
- Added **Tied to ...** modes for SO-doublet splitting and major/minor intensity ratio, reusing PANDA's existing tied-parameter concept. Each parameter can independently be Fixed, Free within bounds, or tied exactly to the corresponding parameter of another SO doublet.
- Tied SO parameters remain synchronized in live preview and are compiled into lmfit expressions during fitting. Energy position and overall intensity of each doublet remain independent.
- Ties are preserved across save/load and cloning; if a tie source is ungrouped, dependent ties safely fall back to Fixed and remaining targets are remapped.

## 0.11.09 - 2026-09-19

- Fixed a startup crash when opening the peak-fit dialog in 0.11.08: the new Doublet-view rendering path referenced `so_doublets` without importing the module in `fit_dialog_background_mixin.py`.
- Added a regression guard that checks the Doublet-view mixin imports its helper module explicitly.

## 0.11.08 - 2026-09-19

- Added a global **Doublet view** checkbox to the single-fit controls. When enabled, every defined SO pair is drawn as the sum of its major and minor fitted components; standalone peaks remain individual, and the underlying fit model is unchanged.
- In Doublet view, minor-component markers are hidden and only each doublet's major marker remains as the existing mouse handle for shifting/rescaling the pair. Individual view restores both component curves and markers.
- Doublet view is honored by live calculated-spectrum redraws and intermediate fitting redraws, so the selected representation remains stable during optimization.
- Reorganized the compact fitting controls into three functional rows: primary fit controls; Create SO doublet / Doublet view / Save / Load; and a dedicated fit-status row. Removed the redundant explanatory text after **Create SO doublet...**.

## 0.11.07 - 2026-09-19

- Added a compact **Clone** action to every SO-doublet card, with tooltip **Clone this doublet**. The existing **Create SO doublet...** invitation retains its explanatory tooltip.
- Cloning copies the selected doublet's current splitting/ratio constraints, L/G/Alpha relationships, line-shape values, bounds, and fit modes, but creates independent new peak members.
- A clone is created visibly offset and weaker (40% initial intensity; energy shift at least 1 eV or 1.5 times the broader L/G width, with the correct BE/KE direction), so it can immediately be adjusted using the existing mouse controls instead of hiding exactly under its source.
- Clone labels are numbered automatically, and any doublet — original or cloned — can itself be cloned.

## 0.11.06 - 2026-09-19

- Added the first explicit spin-orbit-doublet workflow to single-curve peak fitting. **Create SO doublet...** asks for the major and minor existing peaks instead of trying to infer doublets automatically.
- Added `p`, `d`, `f`, and `Custom` doublet types. The orbital selector provides only the statistical starting major/minor ratio; the ratio remains editable and can be Fixed or Free within user-set min/max bounds.
- Added editable spin-orbit splitting with Fixed/Free mode and min/max bounds. Binding- and kinetic-energy spectra automatically use the correct partner-energy direction.
- Doublet members default to shared LFWHM, GFWHM, and Alpha, with each relation switchable to Independent. **Ungroup** returns the pair to ordinary peaks.
- Doublets are compiled into the existing individual-peak lmfit model via expressions, so standalone peaks and SO doublets can coexist in one fit. Doublet state is preserved in curve state and saved fit setups.
- Tightened peak-editor margins and row spacing to keep more fit parameters visible vertically.
- Sequence/batch fitting still consumes the resulting individual fitted peaks in this first implementation; higher-level doublet constraints are not yet propagated through the batch strategy UI.

## 0.11.05 - 2026-09-18

- Suppressed native message-box notification sounds by routing PANDA message boxes through Qt's non-native message-dialog implementation; file/open-save dialogs are unaffected.
- **Close all** and **Clear all** now return the main workspace to **Raw Data**.
- **Plotted Data** is deliberately preserved by the main Clear/Close actions so manually assembled comparison plots are not lost accidentally; it remains clearable from its own panel.

## 0.11.04 - 2026-09-18

- Fixed duplicate Sn 3d identification caused by an inconsistent generic Sn 3d reference being relabelled as a second resolved spin-orbit family.
- Generic condensed-state rows for already-resolved families are now kept only when they lie within a plausible chemical-shift window of the explicit main component.
- Removed the unsuccessful 0.11.03 one-to-one partner-pairing workaround and its dedicated tests; the Sn duplication was caused by competing reference definitions, not measured-peak partner reuse.

## 0.11.03 - 2026-09-18

- Attempted Sn 3d duplicate cleanup via one-to-one spin-orbit partner pairing. This did not address the reported case and is superseded and removed in 0.11.04.

## 0.11.02 - 2026-09-18

- Fixed phosphorus survey identification: light-element P 2p is now treated as an unresolved survey family when the spin-orbit separation is too small to support separate j-component labels.
- Reference-guided peak recovery no longer creates a second reference-nearer peak when the ordinary detector already found a measured peak inside the same reference search window.
- Widened local refinement specifically for 2s singlets so a real raw-data apex displaced from the smoothed survey maximum is not rejected at the refinement-window edge; this recovers P 2s in the reported CoPS3 survey.
- Added regression tests covering unresolved P 2p, guided-peak duplicate suppression, and displaced P 2s refinement.

## 0.11.01 - 2026-09-18

- Improved survey signal identification when several elements have overlapping plausible Auger regions: competing broad Auger envelopes now use survey-wide accepted photoelectron evidence as a tie-breaker, so a dominant element is preferred over a weak element when both could claim the same measured envelope.
- Fixed duplicate labels for synthesized resolved core-level families (such as Yb 5p): when a condensed-state family is resolved using atomic spin-orbit splitting, PANDA now retains the single strongest, most coherent measured family instead of showing duplicate component pairs.
- Added regression tests for a Yb-dominant / weak-S survey case and duplicate Yb 5p families.

## 0.10.99 - 2026-09-17

- Made mouse selection of the peak-fit range robust at spectrum/axes edges.
- Fit range can now be selected either by click-drag-release or by two successive click-release positions.

## 0.10.98 — 2026-09-17

- Fixed a peak-fitting regression where increasing **Number of peaks** could reset a custom fit range to **Full** during peak-editor rebuilding.
- Adding a peak now explicitly preserves the active custom fit range and derives the new peak's automatic position/intensity guess from that range.

## 0.10.97 — 2026-09-17

- Fit-range dashed boundary lines now remain visible during live/intermediate single-curve fitting redraws.
- Stopping an in-progress fit now changes the plot title to **fit interrupted** instead of leaving the transient **fitting...** title behind.
- An interrupted fit also restores the pre-fit zoom/view and redraws the fit-range boundaries.

## 0.10.96 — 2026-09-17

- Peak fitting now preserves the current Matplotlib zoom/view when **Start fit** redraws intermediate and final fit curves.
- Newly added peak guesses now use the active custom fit range, so a peak added while fitting a small core-level region is initialized in that region rather than at an unrelated stronger feature elsewhere in the curve.
- The fit range remains a data-selection range, not a hard peak-center constraint; existing/manual parameter bounds are therefore not unnecessarily narrowed.

## 0.10.95 — 2026-09-17

- Moved PANDA version/date metadata to a dedicated `maxiv_panda.version` module and made internal consumers import it directly, preventing GUI startup from depending on metadata being defined inline in `maxiv_panda.__init__`.
- `maxiv_panda.__init__` still re-exports `__version__` and `__date__` for compatibility.

## 0.10.94 — 2026-09-17

- Packaging-cleanup release: verified that `src/flexpes_pes` is only the two-file compatibility shim (`__init__.py` and `__main__.py`) and does not duplicate the real `maxiv_panda` package tree.
- Added a regression test that prevents the legacy compatibility namespace from accidentally growing into a second full package again.
- No application behaviour changes.

## 0.10.93 — 2026-09-17

- Removed the redundant inner **Peak parameters** group-box title in the Peak fitting window; the tab title now provides the single section label.

## 0.10.92 — 2026-09-17

- Migrated the primary Python package namespace from `flexpes_pes` to **`maxiv_panda`**.
- Updated both `panda` and `maxiv-panda` console launchers to use `maxiv_panda.app:main`.
- Added `python -m maxiv_panda` as the primary module launcher.
- Kept a minimal `flexpes_pes` compatibility shim so `python -m flexpes_pes` and legacy imports can continue to work during the transition.
- Updated package-data/resource lookup paths and internal/test imports to the new namespace.
- New fit exports identify the software as `maxiv-panda`; legacy `flexpes_pes_*` saved-format identifiers remain readable and unchanged for file compatibility.

# 0.10.91 — 2026-09-17

- Renamed the public Python distribution from `flexpes_pes` to **`maxiv-panda`**.
- Replaced the legacy `flexpes-pes` console command with two PANDA launchers: **`panda`** and **`maxiv-panda`**.
- Updated installation/run documentation and user-facing Help wording to use PANDA rather than the legacy package name.
- Deliberately retained the internal `flexpes_pes` Python namespace, package-resource paths, saved fit/batch format identifiers, Windows application identity, and QSettings identity for compatibility; namespace migration will be handled separately.

# 0.10.90 — 2026-09-17

- Renamed the visible application to **PANDA — Photoemission Analysis, Normalization and Data Assessment**.
- Replaced the previous FlexPES/XPS application artwork with the selected monochrome PANDA spectrum icon (smaller peak left, larger peak right).
- Added platform-specific icon assets: Windows ICO, macOS ICNS, and portable/Linux PNG.
- Updated the About dialog to identify PANDA and state **Developed at FlexPES, MAX IV**.
- Preserved the existing Python package name and QSettings storage identity so editable installs/imports and saved UI preferences remain compatible.

# 0.10.89 — 2026-09-17

- Fixed dark-theme spin-box arrows on Windows by replacing unreliable Qt/Fusion arrow painting with explicit packaged up/down indicator images.

# 0.10.88 — 2026-09-17

- Fixed dark-theme spin-box arrows again using complex-control painting, which reliably overlays visible up/down indicators on the actual spin-box button rectangles across Qt/Fusion rendering paths.

# 0.10.87 — 2026-09-17

- Fixed dark-theme spin boxes so their up/down arrows remain clearly visible.
- Raw Data now accepts TXT/IBW drag-and-drop directly on the main plot canvas, using the same loader as the Loaded files tree; dropped files are added to the tree without changing the current plot.

# 0.10.86 — 2026-09-17

- Restored Auger signal identification for IBW spectra. Photon-energy extraction now searches grouped IBW acquisition metadata (`section_meta`) as well as flat/source metadata, so `Excitation Energy` stored in an IBW `Info` section reaches the Auger matcher.
- Added regression coverage for photon-energy extraction from IBW-style grouped metadata.

# 0.10.85 — 2026-09-17

- Fixed a signal-identification crash during annotation drawing when photon energy had to be read from spectrum metadata: `annotation_plotting.py` now imports the shared `extract_photon_energy` helper it calls.
- Added regression coverage for the annotation path with `settings.photon_energy` unset and `Excitation Energy` supplied through curve metadata.

# 0.10.84 — 2026-09-16

- Fixed the Raw/Processed Intensity-axis Counts/CPS hover hint: the tooltip is now shown explicitly when the mouse is over the Matplotlib Y-axis title instead of relying on a Qt canvas tooltip that was not triggered reliably.

# 0.10.83 — 2026-09-16

- MAP actions now appear only for coherent multi-iteration datasets (at least two iteration curves from one source group); synthetic `All in...` collections of independent spectra no longer expose a misleading MAP button.
- MAP activation is now transactional: if a valid 2D image cannot be built, the toggle is reverted and the ordinary spectra controls/plot remain active.
- Raw Data and Processed Data intensity-axis titles now show a hover tooltip instructing users to double-click for the Counts/CPS selector.

# 0.10.82 — 2026-09-16

- Removed misleading **MAP** actions from standalone 1D spectrum groups in Selected curves. A MAP button now appears only after a group contains at least two selected curves, and disappears again if the group shrinks back to one curve.
- Kept existing MAP construction/compatibility logic unchanged once a multi-curve group is available.

# 0.10.81 — 2026-09-16

- Improved IBW spectrum naming for Scienta multi-region acquisitions: when an IBW note contains both a generic **Spectrum Name** (for example `XPS_022_2`) and a meaningful **Region Name** (for example `S2p_700eV`), the parser now uses **Region Name** as the spectrum identity shown in the Loaded files and Selected curves trees.
- Kept conservative fallbacks to `Region`, `Spectrum Name`, wave name, and filename-derived names for older/simple IBW files, so existing single-region IBW workflows remain supported.

# 0.10.80 — 2026-09-16

- Fixed Counts/CPS conversion for loaded TXT spectra by promoting **Time per Spectrum Channel** to explicit per-curve metadata instead of relying only on a nested tree-metadata dictionary.
- Made acquisition-time lookup robust to nested/legacy Scienta metadata layouts, so the value survives Raw → Selected → Processed tree copies.
- Applied the same metadata path to IBW-derived curves; Scienta IBW wave notes carrying **Time per Spectrum Channel** are now propagated to CPS conversion in the same way as TXT data.

# 0.10.79 — 2026-09-16

- Added spectra-only intensity representation in **Raw Data** and **Processed Data**: double-click the Y-axis title to switch between **Counts** and **CPS** (counts per second).
- CPS uses the acquisition metadata field **Time per Spectrum Channel** independently for each spectrum; stored source arrays remain unchanged in counts.
- Raw and Processed Data remember their intensity representation independently.
- Ordinary spectra passed from Processed Data to Plotted Data, fitting, and energy-calibration workflows inherit the Processed Data intensity representation.
- MAP views deliberately remain in counts, even when Processed Data spectra are displayed in CPS.
- If CPS is requested for a spectrum without a valid time-per-channel value, the application keeps Counts and reports the affected curve instead of mixing units.

# 0.10.78 — 2026-09-16

- Preserved a manually dragged single-fit legend position across fitting-plot redraws and increased the legend font from 8 pt to 9 pt.
- Prevented Return/Enter in editable peak-label fields from activating the dialog default OK button; Enter now leaves the fitting window open while the edited label remains applied to the legend.
- Improved the TeX label-reference subscript preview to use a fraction slash (`₃⁄₂`) so the separator visually matches the subscript digits instead of appearing full-sized.

# 0.10.77 — 2026-09-16

- Made the Cross sections photon-energy intersection circles move live along their curves whenever photon energy changes, including while dragging the photon-energy line.
- Added consistent horizontal padding to application drop-down menu entries, including the Load TXT/IBW and Help menus.
- Made the single-fit legend draggable and changed peak-component legend names to use each peak's editable Label value (falling back to Peak N when blank).
- Fixed the Plotted Data Custom (TeX) symbol reference so Matplotlib math commands insert a single backslash (for example `\alpha`, `\pm`, `\circ`, `\times`) rather than invalid doubled backslashes.

# 0.10.76 — 2026-09-16

- Removed the redundant MAP normalization cog from the top control row; selecting **At BE** or **Area** still opens its editor automatically, and re-selecting the active normalization entry reopens it later.
- Added a **Legend** checkbox to the single-spectrum fitting window, checked by default; the legend identifies measured data, background, peak components, and total fit.
- Added small curve-coloured circle markers where the selected photon-energy line intersects each Cross sections reference curve.
- Replaced the combined MAP Lines **Auto scale** control with independent **Auto scale H** and **Auto scale V** checkboxes, both enabled by default.
- Fixed MAP Lines cursor restoration across bin-size changes by treating the display-only `— binned by N` title suffix as the same underlying map identity.

# 0.10.75 — 2026-09-16

- Replaced the temporary blue-filled Dark-theme checkbox indicators with conventional high-contrast check marks for ordinary checkboxes and tree/list item check states.
- Fixed multi-region Scienta TXT files whose regions share the same generic `Spectrum Name`: the parser now prefers the actual `[Region N]` `Region Name` for display/identity.
- Made raw curve keys include the region index when available, preventing one checked spectrum from overwriting another when several regions from the same file have otherwise identical labels.
- This restores simultaneous Raw and Processed visualization of several checked spectra from one multi-region TXT file.

# 0.10.74 — 2026-09-16

- Fixed the remaining Dark-theme Help contrast problems by deriving heading, inline-code, blockquote, table, and link colours from the active Qt palette instead of fixed light-theme colours.
- Added explicit Dark-theme checked/unchecked indicators for ordinary checkboxes and for tree/list item check states, so unchecked entries remain visible in loaded/selected curve trees.
- Fixed the MAP Lines **Auto scale** overlay checkbox on the light Matplotlib canvas so checked and unchecked states are visually distinct in every Qt theme.
- Kept layout, density behaviour, scientific controls, and Matplotlib figure styling unchanged.

# 0.10.73 — 2026-09-16

- Performed a broader Dark-theme contrast cleanup across standard Qt controls and previously light-only custom widgets.
- Restored clear visual separation between neighbouring tabs in Dark mode with explicit padding, borders, and stronger selected/inactive contrast.
- Fixed Plotted Data curve-name fields and drag handles so their text/background follow the active palette instead of remaining light-theme-only.
- Added explicit Dark-theme contrast for editors, combo/spin boxes, item views, menus, radio buttons, scrollbars, headers, disabled controls, hover states, and selections.
- Made Help, signal-identification/reference panels, normalization/ResPES group chrome, and peak-fit result tables palette-aware.
- Preserved semantic warning/status colours while adding explicit readable foreground colours where pale backgrounds are intentionally retained.
- Kept Matplotlib figures light and did not change scientific layout or density behaviour.

# 0.10.72 — 2026-09-16

- Fixed Dark-theme unchecked checkboxes that could render nearly black-on-black by giving the unchecked indicator a visible neutral outline while leaving checked indicators native.
- Increased disabled-control text contrast in the Dark theme.
- Fixed the MAP Lines **Auto scale** overlay label so it remains readable on the intentionally light Matplotlib canvas even when the surrounding application uses the Dark theme.
- Kept layout, density behaviour, and Matplotlib figure styling unchanged.

# 0.10.71 — 2026-09-16

- Polished only the **Dark** Qt theme contrast, without changing layout, density behaviour, or Matplotlib figure styling.
- Improved disabled-text readability while retaining a visibly disabled state.
- Increased splitter/separator and scrollbar-handle contrast, including hover feedback.
- Added restrained Dark-theme hover/active differentiation for ordinary buttons, tool buttons, tabs, and headers.
- Kept all scientific-panel geometry and the light Matplotlib canvas unchanged.

# 0.10.70 — 2026-09-16

- Moved Appearance out of Help into a compact top-left **Settings** cog immediately before **Load**.
- Simplified the Settings dialog to a concise **Appearance** section with Theme, Interface density, and UI font size controls.
- Added live, persistent **System / Light / Dark** Qt palette themes. Theme changes do not alter Matplotlib plot styling.
- Kept the Settings button square and density/font-aware so it consumes minimal horizontal space.

# 0.10.68 — 2026-09-16

- Restored Standard-density geometry close to the proven 0.10.63 baseline while keeping the centralized appearance infrastructure.
- Fixed a regression where generic live metrics could overwrite larger feature-specific minimum sizes, notably shrinking periodic-table element tiles. Generic accessibility sizing now only enlarges controls and never reduces their original minimum height.
- Removed hard-coded 11/13 pt fonts from signal-identification/reference panels so they follow the global accessibility font coherently.
- Reference-condition controls can now grow with larger fonts; fixed height caps no longer clip labels/spin boxes.
- Automatic density is more conservative: normal laptop-sized logical screens retain Standard; Compact is reserved for genuinely constrained displays.
- Compact density now focuses on reclaiming whitespace rather than reducing functional control geometry.

## 0.10.89 - 2026-09-17

- Fixed Dark-theme spin-box arrows on Windows by replacing unreliable native/Fusion arrow painting with explicit packaged up/down indicator images.


## 0.10.69 — 2026-09-16

- Reset legacy appearance-test font offsets once so the established FlexPES font is again the initial Default (current) baseline after upgrading. New font choices continue to persist normally.
- Made five-column periodic-table panes expand with +1/+2 pt accessibility fonts, and adjust their horizontal splitter when needed so the fifth element column stays visible.


## 0.10.67 - 2026-09-16

### Fixed
- Appearance preferences now apply immediately when the Appearance dialog is accepted; restarting the application is no longer required.
- UI font enlargement is now enforced coherently across existing Qt widgets through the shared application stylesheet, fixing mixed large/small text in the main window (including labels, trees, headers, tabs, menus, and ordinary controls).
- Reapplying font settings no longer compounds the +2 pt FlexPES baseline: the original platform QApplication font is retained as an immutable baseline for the session.

### Changed
- Standard/Compact density changes now refresh registered main-window layout margins/spacing and generic pane/control metrics live.
- Main Raw/Processed strips, processing groups, loaded/selected trees, and shared progress geometry participate in the live metrics refresh; feature-specific Matplotlib/MAP plot geometry remains untouched.

## 0.10.66 - 2026-09-16

### Changed
- Made the shared FlexPES style visibly active across the main Qt interface while retaining the platform palette: buttons now use one restrained rounded treatment, and common tabs, menus, trees/tables, inputs, and tool buttons share centralized spacing metrics.
- **Compact** density now materially reduces non-functional whitespace in the main window: outer margins, Raw/Processed control-strip margins and spacing, group-box contents, tab/item padding, and generic tree-pane minimum widths are reduced without shrinking the font.
- Accessibility font enlargement now also expands shared control heights and vertical item/tab/menu padding, so **+1 pt** and **+2 pt** remain readable without squeezing text into baseline-size widgets.
- The main Raw Data and ordinary Processed Data/Fitting controls now consume the central UI metrics; MAP internals retain their established feature-specific geometry except for the shared outer strip, reducing regression risk.
- **Automatic** density continues to resolve once at startup from the available logical screen size and remains stable for the session.

## 0.10.65 - 2026-09-16

### Added
- Added **Help -> Appearance...** with persistent interface-density and accessibility font-size preferences.
- Added **Standard**, **Compact**, and **Automatic** density profiles; Standard remains the default so existing installations keep the current spacing unless the user chooses otherwise.
- Added restricted UI font enlargement relative to the current FlexPES baseline: **Default**, **+1 pt**, and **+2 pt**. Matplotlib figure fonts are intentionally unaffected.

### Changed
- Help and Metadata now use the shared dialog metrics/control sizing layer as the first low-risk migration toward a unified cross-platform GUI style.
- Generic control sizing uses minimum rather than fixed heights so accessibility font enlargement can request additional space without clipping text.
- Appearance changes are applied on the next application start, avoiding partial resizing of an already-open scientific workspace.

### Packaging
- Internal GUI-audit notes are no longer included in release archives; development-only files remain outside the distributed package.

## 0.10.64 - 2026-09-16

### Changed
- Added a central, lightweight UI style/metrics infrastructure as the non-destructive foundation for later GUI unification and adaptive density.
- Moved the existing application-level Fusion style, palette, and +2 baseline font handling into the shared UI style layer without intentionally changing the visible GUI.
- Preserved the current FlexPES font size as the baseline; future accessibility scaling will enlarge from this baseline rather than making the default interface smaller.

### Development
- Added a UI styling/geometry audit identifying generic candidates for staged migration while explicitly retaining functional fixed geometry locally.
- Added the `Automatic`, `Standard`, and `Compact` density API; all modes intentionally resolve to the current Standard metrics in this foundation release, so no density behavior changes yet.

## 0.10.63 - 2026-09-15

### Added
- Metadata viewer search strip with **Find**, **Prev**, and **Next**; searches both parameter names and values and wraps through matches.
- Structured display of auxiliary Scienta metadata sections such as **Manipulator** and **Run mode** for TXT and IBW sources.

### Fixed
- TXT metadata parsing now preserves indexed auxiliary sections including manipulator **X**, **Y**, **Z**, and **Polar**.
- IBW metadata parsing now preserves bracketed wave-note sections, including manipulator coordinates and run-mode information.
- IBW key/value parsing now prefers `=` before `:` so values containing colons (for example times and Windows paths) are parsed correctly.
- Large CIS/ResPES `Point N` lists remain compact in tree metadata and are represented by point count and range rather than duplicated in every curve.

## 0.10.62 - 2026-09-15

### Added
- Raw Data loaded-file tree context menu with **Show metadata** for file, region, and curve entries.
- Read-only grouped metadata viewer with **Copy selected** and **Copy all** actions.
- Tree hint: **Right-click for metadata and other options**.

### Changed
- Long metadata axis/scan-point lists are summarized in the metadata viewer instead of expanding into very large rows.
- Reverted the unsuccessful session-level persistence of Matplotlib toolbar appearance edits; plots again use the standard Matplotlib toolbar behavior and application-defined appearance after rebuilds.

## 0.10.61 - 2026-09-15

### Changed
- Simplified the Help -> About window title to avoid repeating the application name.
- Reverted the earlier lazy initialization of Plotted Data, Cross sections, Binding energies, and signal identification. These components are again prepared during startup so their first use does not introduce an unexpected delay.
- Matplotlib toolbar appearance edits in the Raw/Processed plot are now remembered per dataset/view for the current session and reapplied after plot rebuilds or tab/view switches. This includes axis limits/labels/scales, curve styles, and image colormap/intensity-limit edits exposed by the standard figure-options dialog.

## 0.10.60 - 2026-09-15

### Changed
- MAP -> Lines animation now allows **Speed** and **Loop** to be changed during live playback without stopping the animation.
- Video-only settings remain independent of live preview. Path-defining controls still stop/rebuild playback for predictable behavior.

## 0.10.59 - 2026-09-15

### Fixed
- MAP -> Lines: re-checking **Auto scale** now immediately re-enables Matplotlib autoscaling on both live side-trace intensity axes after **Full range** mode.

## 0.10.58 - 2026-09-15

### Changed
- MAP -> Lines: replace the long two-state Trace scale button with a compact native **Auto scale** checkbox. Checked keeps per-trace autoscaling; unchecked uses the full displayed MAP intensity range.
- Move the **Auto scale** and **Animation...** controls farther down and right in the lower-right corner to separate them visually from the live traces.

## 0.10.57 - 2026-09-15

### Changed
- Replaced the MAP -> Lines **Trace scale** label + combo box with a compact native two-state button: **Trace scale: Auto** / **Trace scale: Full range**. Clicking the button toggles the live side-trace intensity scaling mode, with a tooltip explaining both states.
- Kept **Animation...** directly below the Trace scale control for a cleaner lower-right corner layout.

## 0.10.56 - 2026-09-15

### Added
- MAP -> Lines now has a **Trace scale** selector for the live bottom/right traces: **Auto** keeps the existing per-trace autoscaling, while **Full range** fixes both intensity axes to the minimum and maximum of the currently displayed MAP dataset.

### Changed
- The **Trace scale** selector occupies the upper part of the free lower-right corner and **Animation...** is positioned below it, keeping the live-trace scaling control visually separate from the Plot H/V trace actions.

## 0.10.55 - 2026-09-15

### Changed
- MAP -> Lines now remembers the last H/V cursor positions per map across palette redraws, switching to other map views, and Raw/Processed tab changes. Restored positions are matched by physical coordinates and safely clamped to the nearest available samples if map dimensions change.

## 0.10.54 - 2026-09-15

### Fixed
- Peak/component color changes now update the existing draggable Energy/Height marker artist in place, including single-spectrum and anchor fitting, and the canvas is flushed immediately so the marker cannot retain its stale color.

## 0.10.53 - 2026-09-15

### Added
- MAP -> Lines cursors can now be dragged directly from their continued guides in the bottom and right 1D traces.
- Dragging near the H/V crossing point on the 2D map moves both Lines cursors together.

## 0.10.52 - 2026-09-15

### Fixed
- Keep each draggable peak Energy/Height marker synchronized with its component color immediately after changing the peak color. This applies to both single-spectrum and anchor fitting because they share the same fit dialog.
- On macOS, prevent the peak-fit window from falling behind other application windows after closing the peak color picker by using the Qt color dialog and restoring the fit window focus/stacking.

## 0.10.51 - 2026-09-15

### Fixed
- Fix PyQt6 compatibility in the Signal Identification dialog: use the scoped `QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint` enum so opening **Identify signals** no longer raises an `AttributeError`.

## 0.10.50 - 2026-09-15

### Fixed
- Keep the bottom-trace **Intensity** Y-axis title at a fixed horizontal position in MAP **Lines** (and ROI) so changing tick-label widths no longer makes the title jump left/right.

### Documentation
- Refresh MAP animation/video Help for separate H/V custom ranges and combined **H then V** export.

## 0.10.49 - 2026-09-14

### Added
- Video export **Sequence** option with **Current line** and **H then V**. The combined option writes the configured horizontal sweep followed by the configured vertical sweep into one MP4.

### Changed
- The Lines animation dialog now remembers separate custom H and V sweep ranges while switching between the two lines, so combined **H then V** export uses the currently configured settings for both.
- Video export progress now reports the active **H** or **V** sweep together with frame and cycle counters.

## 0.10.48 - 2026-09-14

- Smooth MAP Lines animation by interpolating cursor/band positions and neighbouring H/V trace profiles between the physical thickness-spaced key positions.
- Separate animation speed (physical thickness-steps per second) from visual render frame rate, preserving the selected line thickness as the physical animation step while removing jumpy playback.
- Add presentation-video export to the Lines Animation panel: MP4/H.264 output of the same Matplotlib figure area saved by the toolbar (2D map plus both traces), configurable video FPS and finite cycle count, native filename dialog, progress/cycle indication, and Cancel with incomplete-file cleanup.
- Video export uses FFmpeg when available and provides a conda-forge installation hint when it is missing.

## 0.10.47 - 2026-09-14

- Keep MAP coordinate values visually stable by using fixed decimal formatting for BE/KE and photon energy plus fixed scientific notation for intensity.
- Replace the Lines Animation and ROI Full width / Full height / Pass to plotting Matplotlib controls with native Qt push buttons, giving them exactly the same platform font and style as the application's ordinary control-row buttons.

## 0.10.46 - 2026-09-14

- Restored the original full MAP Lines binning status text.
- Kept the status label out of horizontal minimum-size calculations so changing binning cannot force the main window wider on macOS.

## 0.10.45 - 2026-09-14

- Match the MAP overlay action-button font to the native Qt push-button font on each platform.
- Hide the ResPES side panel immediately when switching from Processed Data to Raw Data.
- Keep Lines binning status compact so it cannot force the main window wider on macOS.
- Pad MAP cursor coordinate fields so X, Y, and Intensity start at stable horizontal positions while the cursor moves.

## 0.10.44 - 2026-09-14

- MAP Lines: keep cursor coordinate labels fully inside the 2D map by flipping their text anchoring near plot edges.
- Restrict the right-trace Y-axis tooltip to the actual axis/title hover area instead of the whole Matplotlib canvas.
- Give the Lines Animation launcher and ROI Full width / Full height / Pass to plotting overlay buttons a consistent Qt-like action-button appearance.
- Add more whitespace around the Lines Animation launcher and provide a dedicated animation tooltip.

## 0.10.43 - 2026-09-14

- Add a non-modal MAP -> Lines animation controller, launched from the free corner between the H and V side traces.
- Animate either H or V over the full valid range or a custom From/To interval at 1-30 fps.
- Support one-way and back-and-forth playback, optional looping, first/play/pause/stop/last transport controls, live coordinate readout, and Frame n / N status.
- Define each animation step by the selected H/V thickness and keep every frame on a complete full-width averaging window.
- Route animation through the same cursor/profile update path as manual dragging, preparing the controller for later movie export.

## 0.10.42 - 2026-09-14

- MAP Lines: thickness=1 now uses only a thin dashed centre guide; shaded averaging bands appear only for thickness > 1, including the continued guides on the side traces.

## 0.10.41 - 2026-09-14

- Rename MAP/ResPES trace actions from Extract to Plot terminology.
- In MAP -> Lines, continue the H/V cursor centre lines and their averaging-width bands onto the corresponding side traces for precise peak alignment.
- In MAP -> Lines and ROI, allow the right-hand trace Y representation to switch between Iteration and an available physical second axis by double-clicking the right Y axis/title; disable this interaction for iteration-only maps.
- Make Plot V-trace preserve the right-hand Y representation currently displayed.

## 0.10.40 - 2026-09-14

- Fixed ResPES analysis for maps measured directly on a kinetic-energy scale (resonant-Auger style scans).
- ResPES now detects whether the source X axis is BE or KE and performs BE<->KE map conversion in either direction using the analyzer work function.
- Constant BE and Constant KE cuts are evaluated in the correct physical coordinate system regardless of the source energy scale.
- Added regression coverage for KE-source ResPES maps and inverse KE-to-BE conversion.

## 0.10.39 - 2026-09-13


- Fix Help search on PyQt6 by using `QTextDocument.FindFlag` instead of the removed Qt5-style `FindFlags`/`FindBackward` attributes.
- Preserve forward search with an explicit empty `FindFlag(0)` value and backward search with `FindFlag.FindBackward`.

## 0.10.38 - 2026-09-13

- Audit and refresh both Help documents against the current application controls and workflows.
- Document the current MAP cursor readout (BE/KE, PhE/Iteration, and nearest-pixel Intensity), ROI-to-Plotted-Data workflow, and coordinate-aware ResPES trace naming.
- Document conservative automatic initial peak suggestions, the current Fit range / Select on plot workflow, Undo fit, and the energy-calibration Redo safeguard.
- Clarify ROI terminology, remove a duplicated Height description, and clean the remaining Help punctuation inconsistency that broke the Help structure test.

## 0.10.37 - 2026-09-13

- MAP -> ROI now has a **Pass to plotting** action below **Full height**.
- Passing a ROI creates independent `[ROI]` copies of all spectra inside the ROI Y range, truncated to the ROI X range, while preserving the displayed MAP normalization and leaving source curves untouched.
- ROI-derived plotted curves carry internal provenance metadata (`derived_type = roi` and ROI bounds).

## 0.10.36 - 2026-09-13

- MAP → Lines: make H/V averaging thickness much easier to see by strengthening the shaded footprint, adding a clear opaque outline, and slightly emphasizing the dashed centre cursor.

## 0.10.35 - 2026-09-13

- MAP → Lines: show the H/V averaging footprint as translucent horizontal/vertical bands whose width follows the effective selected thickness.
- Extend H thickness and V thickness from 11 to 25 samples (odd values 1, 3, 5, …, 25).

## 0.10.34 - 2026-09-13

- Rename ResPES **Add trace** to **Extract trace**.
- Rename Lines **Add H-trace / Add V-trace** to **Extract H-trace / Extract V-trace**.
- Give extracted ResPES traces coordinate-aware automatic names matching Lines behavior, e.g. `Trace at BE = 284.500 eV`, `Trace at KE = ...`, or `Trace at PhE = ...`, instead of generic `Trace N` names.

## 0.10.33 - 2026-09-13

- Make MAP cursor readout consistent across Simple, Lines, ROI, and ResPES by reporting the nearest map-pixel intensity directly alongside the physical X/Y coordinates.
- Fix missing intensity in Simple MAP view, where mouse events are intentionally handled by a transparent primary Axes rather than the image Axes.
- Disable Matplotlib's separate bracketed image-value cursor suffix for MAP images; this removes the duplicated/vertically clipped intensity readout seen in Lines, ROI, and ResPES.

## 0.10.32 - 2026-09-13

- Reduce application cold-start work by lazily constructing Signal identification only when the feature is first used.
- Lazily construct the Plotted Data panel when its tab is first opened or curves are passed to plotting, avoiding a second Matplotlib canvas during startup.
- Lazily construct the Cross sections and Binding energies reference browsers only when selected, avoiding reference-data/HDF5 setup and hundreds of Qt widgets during launch.
- Preserve lightweight signal-control availability checks before the full identification controller is loaded.

## 0.10.31 - 2026-09-13

- Simplify MAP cursor coordinates: Binding Energy is shown to one decimal place (for example `BE = 2.3 eV`) and photon energy is abbreviated as `PhE`.
- Rename the ResPES cut selector from **Constant photon energy** to **Constant PhE** for consistent terminology.
- Increase the lower margin of the ResPES map/trace layout so the lower intensity-axis readout is no longer clipped.

## 0.10.30 - 2026-09-13

- Fix the Matplotlib MAP cursor/status readout so it reports the physical horizontal energy coordinate (BE/KE) and the actual second map coordinate (for example photon energy, otherwise iteration) instead of internal image-row coordinates from twinned axes.
- Add **Constant photon energy** to ResPES cuts. It is displayed as a draggable horizontal finite-width band and extracts the corresponding spectrum versus the currently displayed BE or KE axis.
- Constant-photon-energy cut position/width stay synchronized with the ResPES controls and can be stored in Trace comparison like the existing BE/KE cuts.

## 0.10.27 - 2026-09-13
- Make the Plotted Data waterfall Offset slider keep the full 0–100% range for up to 30 visible curves, then taper as `3000/N` with a 5% floor for very dense plots.
- Keep the waterfall Offset slider responsive with hundreds of curves by updating its numeric value during a drag and redrawing the plot when the handle is released.
- Fix **Clear plotted** so it also clears the stored plot annotation state; old annotations no longer reappear when new curves are passed to plotting.
- Change **Fixed width** stepping from 0.5 pt to 0.2 pt.

## 0.10.29 - 2026-09-13

- Fixed a regression introduced in 0.10.28 where the ResPES side panel could collapse to zero width when opened.
- The panel keeps a zero hard minimum (to avoid the macOS main-window resize) but now uses a Preferred horizontal size policy, so Qt allocates its natural control width by taking space from the plot instead of hiding the controls or enlarging the top-level window.

## 0.10.28 - 2026-09-13

- Prevent the embedded ResPES control panel from increasing the main-window minimum width when it is shown.
- The ResPES side panel now uses a zero hard minimum and an ignored horizontal size hint, allowing the existing plot area to give up space instead of forcing top-level window growth. This targets the macOS issue where opening **ResPES analysis** could enlarge even a maximized main window.
- No ResPES analysis, map, or numerical behavior changed.


## 0.10.26 - 2026-09-13
- Plotted Data waterfall Offset now uses an adaptive slider scale based on the number of visible curves: 0–100% for up to 10 curves, then approximately 1000/N %, with a 5% minimum range for 200 or more curves.
- Increased waterfall-offset resolution to support fractional percentages; the synchronized numeric control now accepts two decimal places and remains the authoritative displayed offset.
- The slider tooltip reports its current adaptive percentage range and visible-curve count.

## 0.10.25 - 2026-09-13
- Removed the duplicate TeX-reference **?** button from the main Plotted Data control row. TeX support remains discoverable through **Custom (TeX)** and its tooltip; the **?** reference remains in the custom legend-name editor where it is needed.
- Plotted Data annotations are now drawn at a dedicated high z-order so they stay in front of waterfall curves and opaque/semi-opaque waterfall filling at every Filling value.

## 0.10.24 - 2026-09-13
- Plotted Data legend mode **Custom** is now shown as **Custom (TeX)** so TeX-style label formatting is discoverable without opening Help.
- Added tooltips and an example placeholder (`S 2p$_{3/2}$`) for custom legend-name editing.
- Added a compact **?** TeX label reference beside the Legend control and inside the custom legend-name editor. The reference lists common subscript, superscript, Greek-symbol and math-label syntax; double-clicking an entry inserts it in the name editor or copies it from the standalone reference.
- Replaced the generic custom-name input box with a dedicated legend-name editor that exposes the TeX reference while preserving existing custom-name behavior.

## 0.10.23 - 2026-09-13
- Cross-section reference: the dashed photon-energy marker is mouse-draggable and updates the photon-energy field and values table live.
- Cross-section reference: the legend is mouse-draggable and can be hidden with a compact Legend checkbox.
- Binding-energy reference: added an explicit Method selector separating Elements / core levels browsing from BE range searching; the inactive workflow is disabled to reduce ambiguity for first-time users.
- Help updated for the reference-tab interaction changes.

## 0.10.22 - 2026-09-13
- Rebalanced the peak-fit controls: the primary row now contains only peak count, fit-range controls, **Start fit**, and **Undo fit**.
- Moved the live fitting activity indicator and fit diagnostic/result message to the second row beside **Save**/**Load**, preserving the activity indicator behavior during optimization.
- Changed single-fit CSV export so **Include metadata header in CSV** is unchecked by default, making exported CSV files easier to open directly in Igor Pro; the option remains available.

## 0.10.21 - 2026-09-13
- Replaced the crowded single-fit setup row with compact **Save** and **Load** drop-down menus.
- Save menu: **Save config snapshot**, **Save config to file...**, and **Save config + curves...**.
- Load menu: **Load config snapshot** and **Load config from file...**.
- Added explanatory tooltips that distinguish configuration-only storage from curves-inclusive export.
- Snapshot restore remains disabled until an in-memory configuration snapshot exists; curves-inclusive export remains disabled until fit results exist.
- Removed the old setup-status label; saved/loaded configurations are applied directly and recalculated as before.

## 0.10.20 - 2026-09-13

- **Select on plot** now completes the fit-range edit: the range dialog stays closed after the mouse drag instead of reopening and requiring an extra **Close** click.
- Simplified the peak-fit top-row range status to **Fit range: Full** or **Fit range: Custom**. Exact custom limits remain available in the status tooltip and in the **Fit range** editor, avoiding long six-decimal labels in the main controls.

## 0.10.19 - 2026-09-13

- Redesigned the peak-fit range controls for a shorter, clearer workflow: the main fit panel now shows `Fit range: <status>` plus a separate **Edit** button instead of a long stateful button caption.
- Simplified the **Fit range** dialog to **Min**, **Max**, **Select on plot**, **Full**, and **Close**. Removed Accept/Cancel and the Enter-to-preview instruction.
- Fit-range numeric edits now apply live as soon as they form a valid interval; **Full** also applies immediately.
- **Select on plot** temporarily hides the dialog while the user drags on the spectrum, then restores it automatically after selection.
- Existing direct dragging of the dashed fit-range boundaries remains available and synchronized with the dialog fields.

## 0.10.17 - 2026-09-13

## 0.10.18 - 2026-09-13

- Fixed artificial component/sum-curve kinks at custom fit-range boundaries for asymmetric Doniach-Sunjic peaks. Gaussian broadening is now evaluated on a padded energy grid and cropped back to the selected fit interval, so the mathematical line shape is no longer zero-padded at the fit limits.
- The live calculated spectrum and the actual fitting model now use the same boundary-safe DS broadening routine.
- Added regression tests verifying that a DS component inside a cropped fit range agrees with the same component evaluated on a wider energy grid and does not collapse at either boundary.


- Fit-range dialog now opens over the parameter side of the fit window rather than covering the spectrum plot.
- Replaced cubic display interpolation of calculated fit curves with shape-preserving PCHIP interpolation to avoid endpoint overshoot artifacts at restricted fit-range boundaries.
- Added **Undo fit** immediately after **Start fit**. It restores the peak/background configuration, fit range, displayed model, and previous fit-result state from immediately before the last fit attempt.

## 0.10.15 - 2026-09-13

## 0.10.16 - 2026-09-13

- Peak-fit model display is now always active: removed the **Calculate spectrum** toggle and continuously show component curves, summed model, background, and residual.
- Preserved backwards compatibility with older saved fit states containing `calc_on`; that field is now ignored and captured as `true`.
- Reduced conservative automatic peak-suggestion minimum separation from 0.5 eV to 0.3 eV, while retaining the 0.5 eV edge guard, five-peak cap, prominence/noise criteria, and shoulder rejection.

- Fix initial peak-fit dialog startup so fresh spectra actually use the conservative automatic peak-suggestion routine instead of retaining the constructor's single default peak.
- Preserve explicit supplied anchor fit states unchanged; automatic suggestions are used only when no prior fit state is supplied.

## 0.10.14 - 2026-09-13

- Added conservative automatic initial peak suggestions when a new peak-fit curve is opened.
- Detects only resolved maxima using light Savitzky-Golay smoothing, strong prominence/noise filtering, a minimum 0.5 eV separation, a 0.5 eV edge guard, and a maximum of five automatic peaks.
- Shoulders are deliberately ignored; if no convincing maximum is found, one interior fallback marker is created.
- Initial peak heights are taken from the original unsmoothed spectrum near each accepted maximum.

## 0.10.13 - 2026-09-13

- Make the standalone peak-fit editor a genuinely independent top-level window (no Qt parent/owner), so clicking the main application window can bring it in front of the fit window normally.
- Preserve the modeless fit workflow and the explicit application-owned lifetime reference introduced in 0.10.12.
- No fitting or numerical behavior changes.

## 0.10.12 - 2026-09-13

- Make the standalone peak-fit editor modeless so the main application window remains active and usable while a fit window is open (for example, to open Help).
- Keep explicit application-owned references to open peak-fit windows and release them when they close, avoiding premature garbage collection without using a blocking `exec()` event loop.
- No fitting or numerical behavior changes.

## 0.10.11 - 2026-09-13

- Peak-marker Height/Energy mouse dragging is now relative to the press point, so clicking a marker without moving no longer changes its parameters.
- Fit-range editor is modeless and adds **Select with mouse** for direct drag selection on the spectrum plot.
- Accepted fit-range boundary lines are directly mouse-draggable; the range fields and live calculated spectrum update while dragging.
- Fit-range boundary lines are redrawn after calculated-spectrum refreshes and after fitting, so they remain visible and interactive.

## 0.10.10 - 2026-09-13

- Fixed a PyQt6 crash when opening the peak-fit range editor: `QDoubleValidator.StandardNotation` was a Qt5-style enum access and is now `QDoubleValidator.Notation.StandardNotation`.
- Added a regression test that instantiates the fit-range dialog and verifies the validator uses standard notation.
- No fitting, numerical, or UI behavior changes beyond restoring the Fit range dialog.

## 0.10.9 - 2026-09-13

- Fixed Shirley-background plotting/fitting artifacts caused by pointwise clipping of the smooth integral background to noisy measured intensities. The Shirley background now remains smooth and bounded by its physical endpoint levels, so the analytical sum no longer acquires raw-data oscillations.
- Restored Matplotlib's standard live mouse-coordinate readout on the single/anchor fit toolbar while retaining the custom suppression of Qt's stray toolbar extension control.
- No changes to peak line shapes, fitting parameter definitions, or non-Shirley backgrounds.

## 0.10.8 - 2026-09-12

- Extend peak guess-marker mouse control from horizontal Energy dragging to two-dimensional Energy + Height dragging in both single-spectrum fitting and batch anchor fitting.
- Clamp component Height/intensity to the physical range from zero to the maximum measured intensity of the active spectrum; the same upper bound is applied to the Height controls.
- Keep colored Energy/Height guess markers visible and draggable while **Calculate spectrum** is active.
- Recalculate the affected component curves, total model, and residual live when Energy or Height changes by mouse drag or direct field editing.
- Enable keyboard tracking for Energy and Height value fields so the live model responds during typed edits.
- Preserve existing tied-parameter behavior: Energy and Height are independently draggable only when that parameter is not tied.

## 0.10.6 - 2026-09-10
## 0.10.7

- Improved large multi-iteration loading/selection performance, especially for IBW CIS/ResPES data under PyQt6.
- IBW parser no longer duplicates the complete raw Igor wave note or hundreds of `Point N` axis entries into every curve leaf; the physical second-dimension axis is still preserved explicitly.
- `region_to_traces` now parses the second-dimension scale once per region instead of once per iteration.
- Selected-curve rebuilding now has a fast append path for already ordered curves, avoiding quadratic metadata scans when hundreds of iterations are selected.
- No changes to spectral values, iteration ordering, map axes, or user-visible metadata required by analysis workflows.

- Modernize the package installation requirements after validation of the Python 3.14 / PyQt6 environment.
- Raise the supported Python floor from 3.9 to 3.11.
- Update conservative dependency minimums to PyQt6>=6.8, matplotlib>=3.8, numpy>=1.26, scipy>=1.13, lmfit>=1.3, h5py>=3.10, and igor2>=0.5.12.
- These are minimum compatible requirements rather than pins to the exact newest versions; installers may resolve newer compatible releases.
- No application, workflow, or numerical behavior changes.

## 0.10.5 - 2026-09-10
- PyQt6 normalization compatibility fix: connect the Processed Data normalization checkbox through `QCheckBox.toggled(bool)` rather than comparing the integer `stateChanged` payload with a Qt6 `CheckState` enum.
- Restores immediate normalization/redrawing when **Norm E** is checked under PyQt6, without changing the normalization algorithm or stored data.
- Synchronize the package `__version__` with the project version.

## 0.10.4 - 2026-09-09
- PyQt6 layout compatibility follow-up based on the third full Qt6 test run.
- Make the shared `Select all` / `Clear all` core-level action buttons truly equal-width under Qt6 by ignoring label-dependent horizontal size hints while retaining equal layout stretch.
- No intended workflow or numerical behavior changes.

## 0.10.3 - 2026-09-09
- PyQt6 migration follow-up based on the second full Qt6 test run.
- Import `QFrame` in the shared reference widgets module so `QFrame.Shape.NoFrame` is available at runtime.
- No intended application, workflow, or numerical behavior changes.

## 0.10.2 - 2026-09-09
- Second PyQt6 compatibility cleanup based on the first full Qt6 test run.
- Replace Qt5-style `QScrollArea.NoFrame` with the Qt6 scoped `QFrame.Shape.NoFrame` in reference-panel scroll areas.
- Update the Plotted Data read-only text-interaction test to compare directly with `Qt.TextInteractionFlag.NoTextInteraction`.
- No intended application, workflow, or numerical behavior changes.

## 0.10.1 - 2026-09-09
- First PyQt6 migration pass: source and tests now target PyQt6, Qt6 scoped enums, Qt6 dialog execution APIs, and Matplotlib's Qt-agnostic backend.
- `pyproject.toml` now depends on PyQt6 instead of PyQt5.
- No intended workflow or numerical behavior changes.

## 0.10.0

- Start of the modern-environment compatibility line: Python 3.14 and current scientific-package versions are being validated while retaining PyQt5 for this stage.
- Modernization test cleanup only; no application behavior was intentionally changed.
- Relax two GUI tests that required exact one-pixel button-width equality, making them robust to Qt/font-metric rounding differences.
- Make the Plotted Data read-only text-interaction assertion robust to PyQt flag-wrapper behavior.
- Update the Qt-free Selected-tree test stub to provide `QSize`, matching the current MAP-button implementation.
- Dependency minimums in `pyproject.toml` are intentionally unchanged pending completion of compatibility validation.

## 0.9.59

- Help review after 0.9.44: made a small set of consistency updates without expanding the Help structure.
- Map Help now reflects MAP availability, the preview palette chooser, palette-preserved Lines cursor positions, and the current live coordinate wording.
- Batch Help now describes bin size 1 as the unbinned state instead of referring to enabling binning, and notes that draggable peak-position markers are also available in anchor fits.
- Plotted Data Help clarifies that Fixed width also acts as a common marker size for marker-only curves.

## 0.9.58

- Peak fit: colored vertical peak-position guess markers can now be dragged horizontally with the mouse. The corresponding Energy spin box updates continuously while dragging.
- Peak fit: draggable markers respect the Energy spin-box bounds; tied Energy parameters remain controlled by their source peak and are not independently draggable.
- Peak fit: slightly stronger marker lines improve mouse targeting without changing fit calculations.

## 0.9.57

- MAP Lines: format ResPES horizontal cursor/trace captions as `Photon energy = ... eV`.
- MAP Lines: preserve the current horizontal and vertical cursor positions when the map is redrawn for a palette change (and other cosmetic redraws of the same map).
- Plotted Data: add **Check all** and **Uncheck all** buttons at the right end of the top control row.
- Plotted Data: add optional **Fixed width** display control to apply one common line width to all plotted curves while preserving their individual stored widths.

## 0.9.56
- MAP Lines cursor labels now simplify iteration-only second axes to `Iteration = N`.
- Lines comparison traces receive coordinate-aware default names such as `Trace at BE = ...` or `Trace at Iteration = ...`.
- Added independent H/V Lines thickness controls (odd widths 1, 3, 5, ..., 11); profiles are symmetric averages about the cursor and update immediately.

## 0.9.55

- Processed Data **Map → View: Lines** now shows live coordinate labels directly on the map: the vertical cursor reports its X coordinate (BE/KE as appropriate), while the horizontal cursor reports the physical second-dimension coordinate when available, otherwise Iteration.
- Cursor labels update continuously while dragging and automatically use a high-contrast light/dark label box based on the selected map palette and local map intensity.

## 0.9.54

- Ensured the enlarged **MAP** button is fully visible in the default Selected curves geometry by reserving a fixed MAP column while allowing the curve-label column to stretch; this does not widen the Selected curves pane.
- Replaced the text-only colormap chooser with a visual palette chooser that shows a gradient preview beside every available curated Matplotlib colormap.
- Reused the same preview chooser in batch-map palette selection for GUI consistency.

## 0.9.53

- Processed Data: moved the map color-palette button from the Selected curves tree to the Map control row, immediately after **View**.
- Made the per-region **MAP** toggle substantially more prominent without increasing the selected-tree footprint: uppercase label, larger/bolder font, taller button, wider use of the space freed by the removed palette column, and restrained blue enabled/hover/checked styling.
- The MAP button remains disabled whenever the existing map-eligibility logic says a 2D map cannot be shown.

## 0.9.52

- ResPES: removed the explanatory text block below the map energy-axis controls; the existing tooltips now carry the guidance.
- ResPES: styled the **Map energy axis** and **ResPES cuts** groups to match the compact framed Normalization workflow controls for a consistent Processed Data GUI.

## 0.9.51

- Reorganized ResPES analysis controls into separate **Map energy axis** and **ResPES cuts** groups.
- Analyzer WF is enabled only for the KE map representation; BE view keeps it disabled.
- Added an inline WF hint explaining the 2.50–6.50 eV allowed range and that typed values redraw on Enter/focus change.
- Increased the ResPES map right margin so the right-side **Iteration** axis title is no longer clipped.

## 0.9.50
- Added a BE/KE energy-axis switch to Simple-view ResPES analysis.
- KE maps are rebuilt row-by-row from the original BE data using `KE = hν - BE - Φ`; unmeasured regions are left blank rather than extrapolated.
- Added an exposed Analyzer WF control (default 4.5 eV, range 2.5–6.5 eV).
- Updated Constant KE cuts to use the same physical analyzer-work-function convention and synchronized their overlays in both BE and KE map views.
- Stored ResPES trace metadata now records the map energy axis and analyzer work function.

## 0.9.49 - 2026-09-08

- Simplified binning controls in both batch fitting and Processed Data **Map → View: Lines**: removed the redundant **Enable binning** checkboxes.
- **Bin size = 1** is now the explicit unbinned/default state; any value above 1 enables the existing consecutive complete-bin averaging directly.
- Binning status text is hidden at bin size 1 and shown only when binning is active, saving additional GUI space.

## 0.9.48 - 2026-09-07

- Plotted Data waterfall: added a **Filling** slider, disabled at 0% by default.
- Filling progressively adds background-colored area beneath each displaced spectrum; 0% is the ordinary line waterfall and 100% gives full foreground occlusion.
- Filled waterfall spectra are rendered back-to-front using each curve's own minimum-intensity offset baseline so strong foreground ridges can hide curves behind them without changing the data.
- Individual curve colors remain the default; optional **Fixed color** behavior is unchanged.

## 0.9.47
- Plotted Data waterfall: **Fixed color** is now disabled by default, preserving each curve's individual color unless the user explicitly enables monochrome waterfall display.

## 0.9.46 - 2026-09-07

- Plotted Data: replaced `tight_layout()` with stable explicit margins to avoid layout warnings and clipping, including after **Clear plotted**.
- Plotted Data waterfall: added batch-style **Fixed color** mode with a color picker; fixed color is enabled by default for waterfall display to avoid repeating categorical colors in long sequences.
- Overlay mode continues to use each curve's individual color.

## 0.9.45 - 2026-09-07

- Added batch-style binning to Processed Data **Map → View: Lines**.
- **Enable binning** and **Bin size** average consecutive, non-overlapping complete groups; an incomplete trailing group is discarded, matching batch fitting.
- Binned Lines maps use the mean source iteration and, when available, the mean physical second-dimension coordinate for each bin.
- Binning is reversible and Lines-only: stored spectra and the Simple/ROI map views are not modified.


## 0.9.44 - 2026-09-07

- Fixed numeric ordering of iteration curves in Selected curves: iterations now sort as 1, 2, 3, ... rather than lexicographically as 1, 10, 100, ... .
- Plotted Data inherits the corrected Selected-curves order when curves are passed from Processed Data.


## 0.9.42

- Signal identification: fixed small-charging inference for resolved spin-orbit doublets when compound-state references coexist with elemental references. Charging anchors now use one stable resolved elemental/reference doublet rather than mixing chemical-state absolute energies, so a coherent common shift is recovered correctly.
- Restored the charged Ti 2p3/2 / 2p1/2 anchor pair in the 700 eV oxide-mixture regression spectrum and propagation of the PE-derived shift to Ti LMM Auger-family regions.


## 0.9.43 - 2026-09-06

- Fixed signal identification of unresolved Si 2p peaks in coarse survey spectra.
- Dominant resolved-family locking now requires spin-orbit components to be experimentally separable on the sampled energy grid and to correspond to distinct measured maxima.
- Added a regression test using the supplied 1215 eV survey where Si 2p is observed at about 102 eV with its Si 2s companion.

## 0.9.41

- Keep 1D normalization state active when switching between raw and E-calibrated Processed Data views.
- Keep E-calibration as an X-axis transform only; normalized intensities are no longer baked into persistent E-cal children, preventing checkbox/data-state inconsistencies.

# Changelog

## 0.9.35 — 2026-09-04

- Batch fitting: removed the Matplotlib constrained-layout/subplots-adjust warning by disabling the automatic layout engine before applying batch-specific subplot margins.
- Peak fitting: batch preparation now uses the exact visible, checked selection passed from the main window, so hidden raw curves are not reintroduced when only E-calibrated curves are shown.
- Energy calibration: selected curves are collected in visual tree order and newly created E-calibrated curves use the same numeric source-file sorting as the main Selected-curves tree.

## 0.9.34 — 2026-09-04

- Selected-curve labels now use the acquisition number first, for example `0070: S2p_260`, consistently for TXT and IBW sources.
- Selected curves are kept in ascending numeric acquisition/file-number order, independent of the order in which the user selects them; grouped children are sorted by source file number as well.

## 0.9.33 — 2026-09-04

- Fixed IBW acquisition-tag extraction for filenames such as `XPS_0070S2p_260.ibw`; the selected-curve label now uses `0070` rather than the region suffix `260`.

## 0.9.32 — 2026-09-04

- Fixed the persistent stray control overlay in supplied/anchor single-fit windows. The hidden curve-selection pane was still a visible unmanaged Qt child when omitted from the splitter; it is now explicitly hidden in supplied-spectrum mode.

## 0.9.31 — 2026-09-04

- Single-fit window: explicitly suppress the `QToolBar::handle` sub-control with a fit-specific Qt stylesheet. This removes the small Windows 11 slider/grip that can remain visible even when the embedded Matplotlib toolbar is non-movable.
- Synchronized the runtime package version with the distribution version.

## 0.9.30 — 2026-09-04

- Single-fit window: replaced the standard embedded Matplotlib toolbar instance with a fit-specific toolbar that disables the coordinate widget and explicitly hides Qt's private `qt_toolbar_ext_button`, including after resize/layout updates. This targets the persistent stray toolbar control seen on Windows.

## 0.9.29 — 2026-09-04

- Single-fit window: disabled the movable/floatable QToolBar behavior of the Matplotlib navigation toolbar, removing the stray Windows drag-handle control at the far left.
- Help: added concise documentation for **Store all fit results**, post-run fit navigation, and **Export all fits...** ZIP export of per-spectrum fit CSV files plus `batch_manifest.csv`.

## 0.9.28 — 2026-09-04

- Application icon: added a Windows AppUserModelID before QApplication creation so command-line launches are identified as FlexPES rather than generic Python.
- Application icon: explicitly sends both large and small native icons to the Windows HWND with WM_SETICON immediately after show and on two Qt event-loop refreshes.
- Kept Qt application/window icon setup as the cross-platform path for Linux/macOS, and added a bundled PNG icon for non-Windows desktops.

## 0.9.27 — 2026-09-04

- Batch fitting: compacted the Run sequence fit controls into two short rows so the controls no longer crowd or overlap when the splitter pane is narrow.
- Single-fit window: corrected the Matplotlib toolbar parent/layout to prevent a stray control from appearing over the left side of the toolbar on some Qt/Matplotlib configurations.

## 0.9.26 — 2026-09-04

- Batch fitting: added optional **Store all fit results** retention for every spectrum.
- Added post-run fit navigation below the batch monitor with previous/next buttons and direct fit-number selection.
- Added conditional **Export all fits...** ZIP export for the selected pass, with one plain CSV per stored fit plus `batch_manifest.csv`.
- Default batch fitting remains lightweight by discarding full curve arrays unless explicitly requested.

## 0.9.25 — 2026-09-02
- Fixed EADL-only Auger-family detection for elements established by multiple confident PE lines.
- Removed an over-restrictive requirement that a theoretical Auger band had to overlap a PE line of the same element (or produce multiple separate broad subregions). This suppressed valid remote Auger bands such as S LMM near apparent BE 853 eV at hν = 1000 eV.
- EADL-only Auger assignments still require at least two confident PE assignments for the element, a broad noise-significant measured excess, and a measured maximum within 12 eV of the EADL atomic-cluster reference. Reference confidence remains low and reliability remains capped at 70%.
- Added a regression test for a strong S LMM band separated by hundreds of eV from the supporting S 2s/2p photoelectron lines.

## 0.9.24
- Updated **What is what?** and **How to?** for the current 2D-map workflow after the ResPES and generic trace-comparison additions.
- Documented the compact View selector, Add H-trace / Add V-trace snapshots, shared Trace comparison window, axis-compatibility behavior, session lifetime, and CSV export from the comparison window.
- Added a concise dedicated ResPES workflow covering Constant BE / Constant KE cuts, interactive positioning and width, Add trace snapshots, comparison, and restoration when returning to Simple view.
- Removed obsolete Help instructions for direct CSV export from Lines/ROI and the ResPES side panel.

## 0.9.23
- Replaced the three Simple / Lines / ROI radio buttons with a compact **View** combo box while preserving the established internal map-view behavior.
- Renamed the generic map snapshot controls to the clearer **Add H-trace** and **Add V-trace**.
- Fixed stored horizontal comparison traces so the source X-axis direction is preserved; XPS Binding Energy therefore remains conventionally decreasing from left to right in the comparison window.
- Kept ResPES analysis and the generic comparison-session behavior unchanged.

## 0.9.22
- Extended the generic trace-comparison workflow to ordinary 2D **Lines** and **ROI** views.
- Added compact **Add H** and **Add V** controls in Lines/ROI to snapshot the currently displayed horizontal or vertical trace into the shared comparison window.
- Removed the redundant direct Lines/ROI CSV-export control; 2D trace export is now centralized in Trace comparison.
- Horizontal snapshots keep the map X quantity (for example Binding Energy); vertical snapshots use the physical second dimension when available, otherwise Iteration.
- Comparison traces carry Lines/ROI selection metadata and current map-normalization metadata.
- Incompatible X quantities are never mixed silently: the user can explicitly clear the current comparison and start a new one.
- Compacted ROI labels and spin boxes to make room for the new trace controls without expanding the control strip.
- ResPES analysis and its Add trace workflow are unchanged.

## 0.9.21
- Fixed trace renaming in the generic comparison window so **Rename...** acts on whichever trace is selected in the trace selector, not only the most recently added trace.
- Made the trace-comparison window an independent normal top-level window with minimize/maximize/close controls; it can now be minimized and moved behind the main application window. Closing with X still only hides the window and preserves the comparison session.

## 0.9.20

- Refactored the ResPES comparison window into a generic, axis-agnostic trace-comparison subsystem for future reuse by any 2D workflow.
- Added a generic `ComparisonTrace` snapshot model carrying X/Y arrays, display labels, X-axis quantity/unit identity, and arbitrary producer metadata.
- Kept the existing ResPES workflow unchanged: `Add trace` now sends a generic Photon Energy trace to the shared comparison window.
- Removed the redundant direct single-trace CSV export from the ResPES side panel; CSV export is now owned by the comparison window for one or many traces.
- Main Clear all / Close all now terminate the generic comparison session at application level rather than through ResPES-specific ownership.
- Help text intentionally unchanged in this release.

## 0.9.19

- Added a lightweight non-modal ResPES trace-comparison window.
- `Add trace` snapshots the current Constant-BE/Constant-KE excitation profile without tying it to later cut or normalization changes.
- Comparison window includes the standard Matplotlib toolbar, optional draggable legend, generic Trace 1/2/... labels with rename, CSV export, and Clear all.
- Closing the comparison window hides it and preserves traces; main Clear all / Close all terminate the comparison session and reset numbering.
- Comparison CSV exports paired photon-energy/intensity columns for each trace, preserving different photon-energy grids without interpolation.

## 0.9.18

- Added dedicated CSV export for the Simple-view ResPES cut trace.
- Export records photon energy/intensity together with dataset, cut type/position/width, and active map-normalization metadata.

## 0.9.17

- Fixed ResPES cut spin boxes so typed/stepped values update the cut and trace immediately, without an extra Enter.
- Fixed mouse dragging/resizing of Constant-BE and Constant-KE cut bands in Simple ResPES view.
- Restored the Binding Energy tick labels/title on the 2D map when the dedicated ResPES trace is visible below it.
- Clear all / Close all now reset the ResPES workflow and return Processed Data from 2D-map controls to the ordinary Spectra controls.

## 0.9.16 — 2026-08-31

- Added the first isolated ResPES analysis workflow for Processed Data 2D maps whose physical second dimension is Photon Energy.
- ResPES analysis is available only in Simple view; its button and side panel disappear in Lines/ROI and return with the previous state when switching back to Simple.
- Added compact right-side controls for Constant BE and Constant KE cuts with editable position and width.
- Added draggable/resizable cut overlays and a dedicated intensity-vs-photon-energy trace below the 2D map.
- Constant KE cuts follow the fixed trajectory `BE = hν - C`, parameterized as `hν - BE` so no analyzer work-function assumption is required.
- ResPES cuts operate on the same normalized map matrix that is currently displayed and coexist with the interactive normalization band without stealing its unrelated mouse drags.

## 0.9.15

- Remember the normalization settings dialog position during the session and restore it when reopening At BE or Area normalization.
- Switching normalization to None, using the dialog Close button, or closing the window via its title bar now preserves the user's chosen dialog placement.

## 0.9.10 — 2026-08-30

## 0.9.14 — 2026-08-31

- Made the Area-normalization band interactive in Simple, Lines, and ROI views: drag the band to move it and drag either edge to resize it.
- Map-normalization defaults are now dataset-specific and are re-seeded when the active map dataset changes.
- Clear all and Close all now clear map-normalization state and close an open normalization settings dialog, so the next dataset starts with correct defaults.


## 0.9.13

- Fixed At-BE normalization-band mouse dragging in the **Simple** 2D map view.
- The interactive normalization band is now attached to the topmost map Axes that actually receives mouse events, matching Lines and ROI behavior.


## 0.9.12

- Fix missing imports introduced by the 0.9.11 map-subsystem refactor (`FuncFormatter` in map plotting and `QHBoxLayout` in map controls).
- Add a static global-name check for the extracted map modules during release verification to catch this class of refactor regression.

## 0.9.11 - 2026-08-30

- Refactored the Processed Data 2D-map subsystem without changing its intended GUI workflow.
- Moved map-specific Matplotlib rendering and mouse interaction out of `ui.py` into `ui_map_plot_mixin.py`.
- Moved map normalization, ROI synchronization and trace-export actions out of `ui_processed_data_mixin.py` into `ui_map_controls_mixin.py`.
- Centralized the physical-left / iteration-right Y-axis construction shared by Simple, Lines and ROI views.
- Added regression tests for the shared map-axis helper, including resonant-PES photon-energy labels.

- Updated Help to match the current 2D Map workflow: Simple/Lines/ROI, physical second-dimension (for example photon-energy) Y axis, interactive map normalization, normalization-dialog behavior, and trace export.
- Kept the workflow description concise and aligned with the level of detail used elsewhere in Help.

## 0.9.09 — 2026-08-30

- Disabled normalization settings for `None` and close any open normalization settings dialog when switching to `None`.

## 0.9.08 - 2026-08-30
- Map At-BE normalization controls now step by 0.1 eV.
- The At-BE normalization band can be moved by dragging its interior and resized by dragging either vertical edge; the settings dialog stays synchronized.

## 0.9.07 - 2026-08-30

- Fixed stale duplicate Close/Reset buttons occasionally appearing in the 2D map normalization settings dialogs.
- Dialog repopulation now recursively clears nested layouts and immediately hides/detaches obsolete widgets before deletion.

## 0.9.05

## 0.9.06

- Fixed the Simple 2D map physical Y-axis formatter: photon-energy labels are no longer overwritten by the generic scientific-notation intensity formatter.
- Simple ResPES maps now keep Photon Energy [eV] on the left and Iteration on the right, matching Lines and ROI.

- Fixed dual Y-axis rendering for resonant-PES 2D maps.
- Lines view no longer shares the Matplotlib YAxis object between the map and right trace, preventing iteration tick labels from overwriting the left photon-energy scale.
- Simple view now uses the otherwise-unused main axes for the left physical second-dimension scale instead of stacking a third twin axis, eliminating overprinted photon-energy/iteration labels.
- ROI behavior is unchanged and remains the reference layout: photon energy on the left, iteration on the right.

## 0.9.04

- Fixed Scienta ResPES/CIS photon-energy axes in IBW maps by extracting the explicit `Point N=<energy> eV` sequence from the IBW wave note when available.
- The recovered physical second-dimension scale is propagated to Simple, Lines, and ROI map views.

## 0.9.03 - 2026-08-30

- Renamed the Processed 2D map view **None** to **Simple**.
- Added a dedicated left-hand physical second-dimension axis to the Simple map renderer, so resonant-PES maps can show **Photon Energy [eV]** while keeping **Iteration** on the right.
- Kept the physical second-dimension scale available in Simple, Lines, and ROI views.

## 0.9.00

## 0.9.02

- Fixed missing physical second-dimension axis in Processed 2D maps by recovering Dimension 2 name/scale directly from preserved iteration source metadata when the cached map stack does not provide it.
- Added extra left margin in Lines/ROI map layouts when a physical Y axis (for example Photon Energy [eV]) is displayed.


## 0.9.01

- Fixed loss of physical second-dimension metadata (for example Photon Energy [eV]) when 2D map normalization was active.
- The left-hand physical Y axis now survives both At BE and Area normalization in Simple, Lines, and ROI map views.

- Added support for physical second-dimension axes on Processed Data 2D maps.
- Scienta resonant-photoemission datasets with a Photon Energy second dimension now show Photon Energy [eV] on the left Y axis while retaining Iteration on the right.
- Photon-energy values are read directly from structured TXT Dimension 2 metadata and from IBW second-dimension scaling/labels.
- Selected/non-contiguous map iterations retain their corresponding physical second-axis values.

## 0.8.101

- Fixed 2D normalization dialogs so pressing Enter after typing a spin-box value commits the value instead of triggering Reset.
- Selecting **At BE** or **Area** normalization now opens its settings dialog immediately; the cog button still reopens it later.

## 0.8.100 - 2026-08-30
- Added a full-height normalization-range band to Processed Data maps in Simple, Lines, and ROI views.
- At-BE map normalization now uses an explicit averaging width in eV; the complete interval must exist in the spectra.
- Expanded map-normalization dialogs with available/selected ranges, explanatory text, a Show normalization range toggle, and Reset/Close controls.
- Reset restores method-specific defaults for the current map without disabling normalization; Area resets to the full spectral range.
- Updated map-normalization CSV metadata and Help text for the absolute-width workflow.

## 0.8.99 - 2026-08-30
- Map normalization settings are now validated against the actual spectral energy range before being accepted.
- Invalid At-BE or Area limits show a warning and restore the previous valid setting without switching normalization to None.
- Area normalization no longer silently clips out-of-range limits to the map range.

## 0.8.98 - 2026-08-30
- Added independent 2D-map intensity normalization controls in Processed Data.
- Map normalization methods: None, At BE, and Area.
- At BE reuses the established 1D mean-over-energy-interval algorithm and percentage span.
- Area normalizes each spectral row to the integrated intensity within a user-selected energy range.
- A compact settings button opens a non-modal parameter dialog; changes redraw the map and active Lines/ROI traces immediately.
- Map normalization is display/analysis-only and does not modify the stored 1D processed spectra.
- Trace CSV export now records the active map-normalization method and parameters.

## 0.8.97 - 2026-08-28

- Fixed stale Full width / Full height Matplotlib button hit areas remaining active after leaving ROI mode.
- ROI-only button event connections are now explicitly disconnected before the figure is rebuilt.
- Any mouse grab held by an ROI extent button is released during mode changes, preventing the "Another Axes already grabs mouse input" error in Lines/None views.

## 0.8.96 - 2026-08-28

- Expanded Help with the Processed Data 2D Map workflow.
- Documented None, Lines, ROI, live ROI projections, full-width/full-height toggles, and trace CSV export.
- Added a concise How to? workflow for inspecting a spectral sequence as a 2D map.
- Clarified that the Processed Data map is distinct from calibration and batch-fitting sequence previews.

## 0.8.95
- Added a compact Export CSV drop-down to Processed Data Map controls.
- Export is enabled in both Lines and ROI modes and disabled in None mode.
- Horizontal/vertical exports contain exactly the currently displayed trace data plus cursor/ROI metadata.

## 0.8.94 - 2026-08-28

- ROI Full width / Full height controls are now true two-state toggles.
- Activating a full-extent toggle stores the exact previous ROI extent; unpressing it restores that extent.
- The extent controls are figure-overlay buttons in the unused lower-right corner, so they do not take layout space from either trace plot or its axis titles.
- Refined compact pressed/unpressed styling for the two ROI extent buttons.
- Manual ROI resizing releases the corresponding full-extent toggle; moving the ROI preserves any active full dimension.

## 0.8.87

## 0.8.93 - 2026-08-28

- Added compact **Full W** and **Full H** buttons in the unused lower-right corner of the Processed Data Map ROI layout.
- **Full W** expands the active rectangular ROI across the complete X range while preserving its current Y extent.
- **Full H** expands the active rectangular ROI across the complete Y/iteration range while preserving its current X extent.
- ROI numeric controls and both summed projection traces update immediately after either action.

## 0.8.92 - 2026-08-28

- Fixed startup regression by restoring package `__date__` metadata required by the UI/About imports.

## 0.8.91

- Processed Data Map ROI projections now display only the current rectangular ROI span: the bottom X axis and right Y/iteration axis update live as the ROI is moved or resized.
- ROI trace data are now true projections of the rectangular ROI itself (not full-map stripes).
- Increased the default ROI size from about 5% to about 20% of the full X and Y ranges.

## 0.8.90

- Added a neutral **None** analysis mode to Processed Data 2D maps.
- **None** is now the default whenever Processed Data Map mode is entered; it shows the full 2D map without crosshairs, ROI, or profile traces.
- **Lines** and **ROI** remain mutually exclusive opt-in analysis modes.

## 0.8.89

- Added mutually exclusive **Lines** and **ROI** analysis modes to Processed Data map view.
- Added one rectangular 2D ROI with mouse dragging and edge resizing.
- Added compact numeric controls for ROI X/Y center and width, synchronized with mouse edits.
- ROI mode shows summed projections: bottom trace sums selected Y rows; right trace sums selected X columns.
- ROI defaults to the current Lines cursor position on first activation, with a modest data-aware width.
- ROI interaction snaps to measured map samples and is clamped to map boundaries.

## 0.8.88

- Fixed the Map+Lines horizontal-profile scientific-notation multiplier so it is always visible inside the bottom trace panel and never overlaps the 2D map.
- Increased the grid-line thickness on both 1D map trace plots.

- Kept the horizontal cross-section scientific-notation multiplier fully inside the bottom trace panel, preventing any overlap with the 2D map.
- Added grids to both Processed Data Map cross-section trace plots.

## 0.8.86

- Added a small fixed gap between the Processed Map 2D panel and both 1D cross-section traces.
- Repositioned the horizontal-profile scientific-notation multiplier into that gap so it remains fully visible without overlapping the 2D map.
- Kept the Map+Lines axes geometry fixed during cursor dragging.

## 0.8.85

- Moved the scientific-notation multiplier for the Processed Map horizontal cross-section profile into the profile panel, so it no longer overlaps the 2D map when the map and bottom profile touch with zero spacing.

## 0.8.82

## 0.8.84

- Raw Data Map view is now always a plain 2D map: Processed Data `Lines` crosshairs and 1D side/bottom profiles are no longer shown on the Raw tab.


## 0.8.83

- Stabilized the Processed Data Map `Lines` layout while dragging cross-section cursors: profile tick-label changes no longer resize the 2D map.
- Forced scientific notation on the two 1D profile intensity axes for compact, stable labels.
- Removed the vertical gap between the 2D map and the horizontal profile.

- Added the first 2D Processed Data control: **Lines**, enabled by default in Map mode.
- With Lines enabled, the map uses an aligned three-panel cross-section layout: 2D map, horizontal-line spectrum below, and vertical-line profile on the right.
- Added draggable horizontal and vertical map cursors. Cursors snap to the nearest actual map row/column and update the corresponding 1D profile live.
- Unchecking Lines restores the existing full-size map representation.

## 0.8.81

- Replaced fixed Raw/Processed Matplotlib subplot margins with constrained layout.
- Plot titles, axis labels, scientific-offset text, and right-side Map iteration labels now reserve the space they actually need instead of being clipped by aggressive fixed margins.
- Kept layout padding small so the axes still use the maximum safe canvas area.

## 0.8.78 - 2026-08-27

- Removed the outer Qt margins and spacing around the shared Raw/Processed plot container so the plot uses all available space within its splitter pane.
- Kept Matplotlib's internal axes padding unchanged so tick labels and axis labels remain visible.
- Synchronized the runtime package version with the release version.

## 0.8.77 - 2026-08-27

- Processed Data now switches its control strip to an empty, same-height 2D placeholder page whenever a selected-region Map toggle is active.
- Toggling Map off restores the existing 1D controls unchanged.
- This establishes the GUI shell for future 2D map controls without changing the existing map enable/disable rules in the selected-curves tree.

## 0.8.76 - 2026-08-27
- Added the bundled FlexPES XPS logo to the About dialog at 96×96 px.

## 0.8.75
- Fix Fit range decimal entry on locales that use a comma decimal separator: numeric validators now use the C locale, matching the dot-decimal values displayed and parsed by the dialog (for example `58.5`).

## 0.8.74
- Added a compact `Fit range: Full...` control to single-curve fitting.
- Added a modal E-min/E-max editor with validated Enter-key dashed-line preview, Accept/Cancel behavior, and a Full range shortcut.
- Custom fit ranges mask the data supplied to optimization, residuals, fit metrics, Shirley/background calculation, and calculated fit curves; data outside the interval remain visible but are ignored by the fit.
- Custom ranges reset to Full whenever another spectrum is selected for fitting.

## 0.8.73
- Lock dominant coherent resolved PE families before evaluating weaker overlapping families.
- Preserve separately measured strong components of weak families such as Ir 5p3/2 even when the weak partner is obscured.
- Suppress recovery of a weak spin-orbit partner when its predicted energy is occupied by a much stronger established family (for example Ir 5p1/2 under Ir 4f).
- Add Ir 4f/5p overlap regression coverage from XPS_0076 and XPS_0122.

## 0.8.72 - 2026-08-24

- Recover close, intense resolved spin-orbit doublets from measured family geometry when global survey peak spacing collapses them into one provisional maximum.
- Strong-component refinement now tests raw local maxima against the tabulated spin-orbit splitting before rejecting a resolved-family anchor; it does not lower the global peak-spacing threshold.
- Added the supplied Ir(111) 700 eV survey as a regression requiring Ir 4f7/2 near 60.5 eV and Ir 4f5/2 near 63.0 eV.

## 0.8.71

- Make resolved spin-orbit consistency asymmetric: a reliable stronger component may remain assigned when the weaker partner is not measurable, provided the element is independently established by another PE family.
- Keep the reverse rule strict: a weaker j component cannot survive without the stronger family member.
- Apply a soft missing-partner reliability penalty scaled by the expected weak/strong Yeh-Lindau cross-section ratio (statistical-weight fallback).
- Add Ir 4p regression coverage for 700 eV surveys where 4p3/2 is visible but 4p1/2 is weak/broad.

## 0.8.70

- Weak 1s refinement now uses the same peak-excluded, detrended local evidence model as reference-guided discovery, preventing C 1s/O 1s from disappearing in otherwise similar low-count surveys.
- Auger-family priors now enforce excitation-energy accessibility of the initial vacancy shell (for example, Ir MMN is suppressed at 700 eV because Ir M-shell ionization is inaccessible).
- Very broad EADL aggregate ranges are treated as local atomic-cluster priors instead of continuous Auger bands, and nearby theoretical clusters are kept separate.
- Auger plotting now labels each experimentally supported subregion locally rather than drawing one connector across distant components of the same family.
- Added paired Ir/h-BN 700 eV survey regressions for weak C/O recovery and cluster-local Ir NOO behavior.

## 0.8.69 - 2026-08-22

- Added a **Show Auger** checkbox beside **Signals…** on the Raw Data tab. It is checked by default.
- The control is display-only: unchecking it hides Auger-family shading, connectors and labels while keeping PE annotations and all cached assignments unchanged; checking it again restores the Auger annotations without rerunning identification.
- **Show Auger** is disabled whenever **Identify signals** is unchecked or signal identification is unavailable for the current selection.
- Clear/Close reset **Show Auger** to its default checked state.

## 0.8.68 - 2026-08-22

- Fixed weak reference-guided singlets (notably C 1s) being rejected when their own peak flanks and local survey curvature inflated the short-window first-difference noise estimate.
- Reference-guided discovery now uses a peak-excluded, locally detrended background noise estimate (linear for short sidebands, quadratic when enough background points are available).
- The improved estimator is intentionally scoped to initial reference-guided discovery so existing family-recovery/conflict scoring for already assigned peaks is unchanged.
- Added an Ir(111)/h-BN survey regression requiring weak C 1s near 284 eV together with O 1s, N 1s and B 1s.

## 0.8.67 - 2026-08-22
- Changed transition-metal 2p duplicate handling to family-pair-first: competing measured 2p3/2 anchors are preserved until element consistency can test their measured 2p1/2 partners.
- The winning strong component is selected primarily by spin-orbit coherence, then by measured prominence, instead of by proximity to one absolute compound reference.
- Losing strong-component hypotheses remain visible as measured peak rows but lose the duplicate Ni/TM label.
- Fixed the supplied native-oxide survey where the prominent Ni 2p family is now assigned near 853/870 eV rather than losing 853 eV to a weaker ~855.5 eV shoulder and rejecting the whole family.
- Added an anonymized native-oxide 1215 eV survey regression for the Ni 2p family; previous mixed-TM Mn/Fe/Ni regression tests remain passing.

## 0.8.65 - 2026-08-22
- Fixed transition-metal shallow-line competition when more than one neighbouring metal has convincing 2p evidence: 3p/3s identity is now decided first by coherent 2p support and then by consistency with that element's measured deep-core shift, rather than by processing order or absolute family cross section.
- Prevented a later TM shallow-recovery pass from overwriting an already better-supported 3p/3s assignment at the same measured maximum; the 49 eV feature in the mixed Mn/Fe/Co/Ni survey now remains Mn 3p rather than being replaced by Fe 3p.
- Fixed loss of sharp transition-metal 2p partners: family recovery now reuses an already detected measured peak at the expected spin-orbit separation before falling back to the broad multiplet-smoothed detector. This restores the Ni 2p3/2 / 2p1/2 pair near 858.5 / 876 eV in the supplied mixed-metal survey.
- Added an anonymized mixed-transition-metal 1215 eV survey regression and synthetic tests for both the Mn/Fe 3p competition and sharp Ni 2p partner recovery.
- The new consistency checks reuse existing assignments and do not add another full-spectrum scan; repeated identification runtime is unchanged within benchmark noise relative to 0.8.64.

## 0.8.64 - 2026-08-22
- Added transition-metal shallow-line consistency: a measured 2p family now establishes the element before 3p/3s recovery, and ambiguous neighbouring-metal 3p/3s assignments receive a strong prior from independent deep-core evidence.
- Missing 2p evidence does not automatically reject an otherwise uncontested shallow line; the new rule is asymmetric and acts primarily when transition-metal shallow assignments compete for the same measured feature.
- Transition-metal 3p and 3s companions are searched using the measured element shift from deep-core anchors, with a soft several-eV allowance and mandatory measured local-maximum evidence.
- Extended the HER_0005 Mn survey regression to require Mn 3p near 49 eV and reject Fe 3p for that feature.
- Reduced Identify-signals runtime by building resolved-family matching context once per identification pass, pre-filtering core references to selected elements, and restricting spin-orbit companion searches to families actually observed in the spectrum.
- Avoided a redundant full matcher/refinement pass when companion recovery proposes no genuinely new measured peak.

## 0.8.63 - 2026-08-22
- Changed resolved spin-orbit identification to a strong-component-first strategy: only the statistically stronger j component receives an absolute reference-guided search window (for example Mn 2p3/2, Au 4f7/2, d5/2, f7/2).
- Weaker spin-orbit partners are now searched from the measured stronger-component position plus the tabulated relative splitting, so common chemical shifts or charging do not redirect the search to an accidental feature near the unshifted weak-component reference.
- Transition-metal 2p recovery now ignores incompatible provisional weaker-component assignments and can replace them with a broad measured partner at the correct family separation.
- Generalized the stronger-partner consistency rule from p doublets to resolved p, d, and f families.
- Applied relative spin-orbit offsets with the correct sign on both binding- and kinetic-energy axes.
- Added the HER_0005 1215 eV Mn survey as a permanent regression case and updated the Au 4f regression to exercise the complete strong-first companion-recovery pipeline.

## 0.8.62
- Made duplicate-transition resolution charging-aware: coherent spin-orbit geometry and measured prominence can outweigh absolute binding-energy proximity.
- Prevents weak accidental shoulders near unshifted references from suppressing strong, consistently shifted doublet components.
- Added a regression test based on the OCV 1215 eV Mn 2p survey case.

## 0.8.61

- Signal identification now treats tabulated spin-orbit splitting as a family-level constraint instead of independently snapping each j component to nearby maxima.
- Missing or mis-positioned partners are searched relative to an established measured component, making the logic robust to common chemical shifts and charging.
- Resolved-component assignments without a partner at the tabulated separation are rejected while the measured peak remains in the peak table.

## 0.8.60

- Signal identification: when a survey-resolvable family already has explicit condensed-state spin-orbit components, unresolved condensed handbook entries (for example `Mn 2p`) are normalized to the main lower-binding-energy component instead of remaining as a third observable line label.
- This preserves useful chemical-state reference energies while preventing simultaneous `2p`, `2p3/2`, and `2p1/2` labels for one physical doublet.

## 0.8.58

## 0.8.59
- Signal identification: same-peak conflict scoring now counts independent companion core-level families rather than resolved spin-orbit components, preventing doublets from receiving duplicate consistency weight (e.g. Co 2p3/2 + 2p1/2 no longer count as two independent companions against Si 2p/2s).

- Signal identification now canonicalizes refined PE assignments so multiple reference-guided windows that converge on the same measured local maximum produce one peak-table row with merged candidate alternatives.
- This prevents same-feature duplicate rows from suppressing coherent companion-line assignments such as Si 2p / Si 2s in crowded surveys.

## 0.8.57

- Signal identification: preserve every experimentally detected peak row when later element/family consistency rules reject an assignment. Rejected candidates now become **Unassigned** with a reason instead of making the measured peak disappear from the peak table.
- Same-shell `np`/`ns` companion recovery now considers several plausible alternative PE candidates at each measured feature rather than only the single top-ranked candidate. This lets an element-specific p/s separation resolve crowded overlaps in a general way.
- Recovery reuses the nearest existing peak-table row instead of creating/removing duplicate rows for the same measured maximum.
- Added regression tests for non-leading p candidates and for peak-row preservation through conflict, s/p-companion, and spin-orbit consistency filters.

## 0.8.55

## 0.8.56
- Signal identification: added a general same-shell `np`/`ns` companion-pair recovery rule. An individually ambiguous p-family peak can now establish an element when an independent s-family feature is found at the expected separation. The separation test is insensitive to a common charging shift and requires measured local maxima for both lines; it is not element-specific.
- This fixes prominent Si 2p/2s pairs being dropped in crowded surveys when neither line passed the earlier single-peak ambiguity gate.


- Fix Ir 4f identification when the strong 4f doublet overlaps the much weaker Ir 5p1/2 reference.
- Use a tighter local refinement window for explicit spin-orbit components so neighbouring doublet members do not corrupt the local baseline.
- Resolve same-peak core-level conflicts using family photoionization cross-section support instead of an orbital-letter preference.
- Add an Ir/BN 700 eV regression window verifying Ir 4f7/2 and Ir 4f5/2 are retained while Ir 5p1/2 is rejected.

## 0.8.54

- Fixed the actual cross-environment selected-curve swatch failure: Matplotlib `Line2D.get_color()` can return RGB/RGBA tuples, and the previous code stringified them before later color conversion.
- Preserve native Matplotlib color objects through plotting and convert them only at the Qt boundary.
- Added defensive support for legacy stringified RGB/RGBA tuples and a regression test for that representation.

## 0.8.53

- Fixed curve color swatches disappearing on some PyQt5/Windows installations by converting Matplotlib colors to standard hex strings before constructing `QColor`.
- Applied the portable conversion consistently to selected-curve icons, batch-selection icons, and Plotted Data color dialogs.

## 0.8.52

- Make curve-color swatches portable across Qt/Matplotlib environments by converting Matplotlib color specifications (including `C0` and `tab:*`) to explicit RGBA values before passing them to Qt.
- Apply the same conversion to main selected-curve icons, batch-fitting selected-curve icons, and Plotted Data color controls.

## 0.8.51 — 2026-08-14
- Added derived fitted peak Area while keeping Height as the editable optimization parameter.
- Single-fit results and JSON export now report the numerical component area over the fitted energy interval.
- Batch fitting stores peak Area and Analyze can plot/export Peak area trends; Area is not offered as a next-pass constraint because it is derived rather than independently fitted.
- Expanded Help with concise Voigt/DS line-shape descriptions and guidance on Height versus Area.

## 0.8.50
- Added a draggable vertical splitter between the Elements and Available core levels panes on both reference tabs.
- Unified the core-level selector appearance and scrolling behavior between Cross sections and Binding energies through a shared widget.

## 0.8.49 — 2026-08-14

- Made the Binding energies **Available core levels** selector vertically scrollable when many elements are selected, while preserving the compact wrapped checkbox layout and keeping Select all / Clear all visible.

## 0.8.48 — 2026-08-14

- Restored the Binding energies element browser to core-level BE references only.
- Made Auger candidates an optional energy-region search feature, disabled by default.
- Photon energy is now enabled only when optional Auger lookup is requested.
- Updated Help for the cleaner BE-first workflow.

## 0.8.47 — 2026-08-14
- Help now opens as an independent top-level window rather than an owned dialog, so it can move behind the main window normally.
- Added the standard minimize, maximize, and close window controls while preserving the single modeless Help-window behavior.

## 0.8.46 — 2026-08-14
- Replaced the separate core-level-BE and Auger-KE lookup modes with one XPS-oriented search by binding-energy region and photon energy.
- Find now returns PE and Auger candidates together on the same BE scale; Auger KE intervals are converted with BE = hν − KE.
- Updated the Binding energies result table and Help to distinguish raw reference energy from position on the BE scale.

## 0.8.45
- Binding energies reference now includes Auger-family kinetic-energy regions alongside core-level binding energies.
- Added separate Core-level BE / Auger KE energy-search modes and explicit energy-type columns.
- Experimental handbook Auger positions are grouped into broad family ranges; supplementary EADL clustered regions remain distinct.

# Changelog

## 0.9.29 — 2026-09-04

- Single-fit window: disabled the movable/floatable QToolBar behavior of the Matplotlib navigation toolbar, removing the stray Windows drag-handle control at the far left.
- Help: added concise documentation for **Store all fit results**, post-run fit navigation, and **Export all fits...** ZIP export of per-spectrum fit CSV files plus `batch_manifest.csv`.

## 0.8.44 — 2026-08-14

- Fixed Raw/Processed Data selection rebuilding so changing checkboxes in the loaded-data tree no longer checks every curve in the selected-curves list.
- Existing selected curves preserve their individual checked/visible state; only newly added curves start checked by default.

## 0.8.43 — 2026-08-14

- Added an OK/Cancel confirmation before **Clear plotted** removes all curves from the Plotted Data tab.
- The confirmation is skipped when the plotted list is already empty.

## 0.8.42 — 2026-08-14

- Reorganized Help so signal-identification reference sources are introduced before they are used, Binding energies is a top-level reference section, and signal-specific scientific notes live with signal identification.
- Cleaned the end of How to?, including a duplicated spin-orbit note, a duplicated Cross sections step, speculative export wording, and the misleading “complete workflow” title.
- Replaced user-facing “core shell” wording with the more accurate “core level” in the two reference tabs and Help; added a short shell/subshell/core-level terminology note.


## 0.8.41 — 2026-07-23

- Made the Help browser modeless so it can remain open while the main window is used normally.
- Reuse/replace the single Help window instead of accumulating multiple Help dialogs.

## 0.8.40 — 2026-07-23

- Replaced the bundled application icon with the new FlexPES XPS doublet icon.
- Kept the existing native title-bar, taskbar, and application icon behavior unchanged.

## 0.8.39 — 2026-07-23

- Added the bundled FlexPES XPS icon as the application and main-window icon.
- Included the icon as package data so installed builds do not depend on an external file path.

## 0.8.38 - 2026-07-22

- Reviewed Help for coherent coverage of all five main tabs.
- Clarified the three-tab data workflow versus the two independent right-aligned reference tools.
- Corrected the Binding energies instructions so element selection reveals shells, while table rows appear only after at least one shell is selected.
- Aligned the What is what? and How to? descriptions of reference-tab behavior.

## 0.8.37 - 2026-07-22

- Fixed stray text above the Raw Data selector when a reference tab was active by excluding hidden reference-page tabs from the custom inactive tab-bar paint pass.

## 0.8.36 - 2026-07-22
- Fixed the first click on Cross sections when the reference selector group is inactive.

## 0.8.35 - 2026-07-22
- Fixed the split tab selector state so only the active data or reference group paints a selected tab.

## 0.8.34 - 2026-07-22

- Replaced the custom reference-tab buttons with a native secondary tab bar so their borders match the data tabs.
- Properly hid the underlying reference page tabs, removing stray label text over the Plotted Data selector.

## 0.8.33 — 2026-07-22

- Fixed an unbounded horizontal main-window growth caused by a tab-bar size-hint feedback loop.
- Moved the reference-page selectors into the tab widget's top-right corner while keeping data tabs in the main tab bar.

## 0.8.32 — 2026-07-22

- Made the custom main tab bar span the full tab-widget width so the Cross sections and Binding energies selectors align against the far-right edge.

## 0.8.31 - 2026-07-22

- Pushed the Cross sections and Binding energies tab selectors to the far-right edge of the main tab bar while keeping the three data tabs on the left.
- Left-aligned all values in both reference result tables.
- Matched the Binding energies element-pane default width to the compact five-tiles-per-row Cross sections layout.
- Made Binding energies Select all and Clear all buttons equally share the full available row width.
- Replaced the fixed-height Cross sections shell selector with the same dynamically growing wrapped selector used by Binding energies.

## 0.8.30 - 2026-07-22

- Visually separated the three data tabs from the two reference tabs, with the reference selectors aligned at the right edge of the tab bar.
- Replaced Binding energies **Clear shells** with matching **Select all** and **Clear all** controls.
- Binding-energy element selection now exposes shells without filling the result table until at least one shell is selected.
- Removed the ambiguous **Show selected** action; element/shell interaction automatically restores the selected-shell result view after an energy search.
- Made column widths manually adjustable in both Binding energies and Cross sections result tables.

## 0.8.29 - 2026-07-22

- Added a standalone Binding energies reference tab beside Cross sections.
- Added element/core-shell lookup and reverse search by binding energy with tolerance and ΔE sorting.
- Kept LBNL and XPS International reference entries separate, including environment, phase, source, and energy ranges.
- Grouped the Cross sections and Binding energies reference tabs at the right end of the main tab bar.
- Added concise What is what? and How to? documentation for the new reference workflow.

## 0.8.28 - 2026-07-22

- Added a concise Plotted Data control reference to What is what?.
- Added a practical Plotted Data composition and CSV workflow to How to?.
- Documented all current plotting controls while preserving the existing Help hierarchy.

## 0.8.27 - 2026-07-22

- Plotted Data: curve names no longer show a tooltip.
- Plotted Data: dragging on a curve name now forwards the mouse gesture to the native list view, giving the same row movement and drop indicator behavior as flexpes_nexafs.
- Plotted Data: removing a curve now requires confirmation with OK / Cancel.

## 0.8.26 - 2026-07-22

- Kept the Plotted Data curve list fixed to one original, immutable curve name in every legend mode.
- Removed custom legend/export names from the curve rows to avoid visual crowding.
- Made the full original-name field a non-clickable drag target while retaining the explicit drag handle.

## 0.8.25 - 2026-07-22

- Keep original Plotted Data curve names read-only and visible when custom legend/export names are used.
- Refresh curve-list names when the legend mode changes.
- Make CSV headers follow the names displayed for the active legend mode.
- Combine Export CSV and Import CSV into one Export / Import menu button.

## 0.8.24 - 2026-07-22

- Added Plotted Data CSV import, load-folder defaults, placeholder-name export warning, and explicit drag handles.

## 0.8.23

- Fixed custom-legend editing for every visible curve by handling renaming after mouse release.
- Prevented legends from remaining attached to the cursor or leaving a duplicate drag image after OK or Cancel.
- Custom legend entries now start as `<select curve name>`.
- Clear plotted now switches Waterfall off.

## 0.8.21 - 2026-07-22

- Make the Plotted Data legend draggable and preserve its dragged position across redraws.
- Update Custom legend labels immediately while curve names are edited.
- Remove the redundant Axes and Export figure buttons; use the Matplotlib navigation toolbar for these actions.
- Make Finest the default grid.
- Prefix transferred curve names with the source file tag and make any remaining duplicates unique.
- Help is unchanged.

## 0.8.20

- Added Stage 3 figure-finishing tools to Plotted Data: draggable annotations, legend styling, axis labels/font sizes/manual limits, and high-resolution PNG/PDF/SVG export.
- Kept plot-finishing state independent from processed curve data and CSV export.

## 0.8.19 - 2026-07-22

- Add Stage 2 CSV export to **Plotted Data**.
- Export visible curves in current list and legend order using edited names.
- Preserve each curve's original X grid as a separate Energy/Intensity column pair without interpolation.
- Make duplicate display names unique in exported headers.
- Help is unchanged.

## 0.8.18 - 2026-07-21

- Build the first full composition controls for the **Plotted Data** tab.
- Add curve visibility, removal, color, style, thickness, custom names, and drag-and-drop order.
- Add legend modes, reversible X direction, grid levels, uniform waterfall display, and **Clear plotted**.
- Keep curves already plotted when additional Processed Data curves are passed.
- Keep the plotting implementation modular under `workflows/plotting/`; Help is unchanged.

## 0.8.16 - 2026-07-21

- Grouped the Processed Data workflow controls into compact **Energy calibration**, **Normalization**, and **Fitting** boxes.
- Moved **Fit selected** out of the normalization row so each control belongs to the correct workflow.

## 0.8.15 - 2026-07-21

- Normalize Processed Data curves to the mean over a percentage-based energy span.
- Shift the full averaging interval inward near spectrum edges.
- Add compact Norm E and E span controls with an eV-width indicator.

## 0.8.14 - 2026-07-21

- Restored fast signal identification after the general spin-orbit-family update.
- Cached normalized core-reference families and repeated line-position lookups used by guided detection and family recovery.
- Kept the general partner-recovery behaviour introduced in v0.8.13 unchanged.

## 0.8.13

- Recover missing members of any resolvable spin-orbit family using a sibling-safe local search window.
- Prevent co-located provisional component labels from falsely counting as a complete family.
- Keep the recovery generic across p, d, and f families rather than applying a Ca-specific exception.

## 0.8.12
- Normalize mixed generic and component-specific core-level references before all identification stages.
- Use condensed-state family energies as absolute anchors and atomic data only for resolvable spin-orbit separations.
- Keep shallow, unresolved families such as transition-metal 3p as one generic survey label instead of allowing atomic j components to compete.
- Apply the same normalized family records in guided detection, matching, companion recovery, and element-consistency checks.


## 0.8.11
- Identify resolved solid-state doublets such as Ca 2p by anchoring the absolute energy to condensed-state handbook data while using atomic references only for the spin-orbit splitting.
- Keep guided detection and final matching consistent in automatic solid-state mode.


## 0.8.10
- Recover paired chemical-state components when two core-level families of the same element show the same separation, such as Si/SiOx double components in both Si 2p and Si 2s.
- Keep multiple measured components of the same transition when they are mutually supported by a second core-level family instead of removing them as duplicates.

## 0.8.66
- Added a soft, confidence-weighted relative TM 2p intensity prior for resolving ambiguous 3p/3s identities.
- 2p strength uses measured peak prominence normalized by Yeh-Lindau family cross section; the bonus is deliberately bounded so energy/deep-core shift consistency remains primary.
- Down-weighted the intensity prior for single-component, low-reliability, or strongly distorted 2p doublets, reducing sensitivity to Auger masking and overlap.
- Added regression tests showing that 2p intensity can break close Mn/Fe shallow-line ties but cannot override a clearly better energy/shift match.