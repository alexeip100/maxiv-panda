# Application overview
PANDA (**Photoemission Analysis, Normalization and Data Assessment**) loads, displays, processes, calibrates, fits, and exports **PES/XPS** spectra from Scienta TXT, Igor Binary Wave (**IBW**), and SPECS/SpecsLab Prodigy **XY** files. It supports single spectra, repeated measurements, and fitted sequences.

## Mental model (how parts of the GUI relate)
The usual data path is: **load → select → inspect → process → plot or fit → export**. The left tree contains loaded data; the selected-curve tree defines the active working set. **Cross sections** and **Binding energies** are separate reference tabs: they can be used at any time and do not alter loaded spectra.

## Key terms used in the UI
- **File**: a loaded TXT, IBW, or SPECS Prodigy XY data file.
- **Region**: a spectral region, for example `S2p`, `C1s`, or another named energy window.
- **Curve / spectrum**: one 1D spectrum shown as a line.
- **Iteration**: one spectrum in a repeated sequence inside the same region.
- **Average**: an average spectrum associated with a region or sequence.
- **Selected curves**: curves copied to the right-hand selected-curve tree and used for plotting, processing, fitting, or batch fitting.
- **Map**: a 2D view assembled from several selected spectra, with energy along X and sequence/iteration along Y.
- **ROI**: rectangular region of interest used to inspect horizontal/vertical map projections and, when needed, pass the enclosed spectra to Plotted Data after truncating them to the ROI energy range.
- **BE / KE**: binding energy / kinetic energy. Binding-energy plots are normally displayed with the X axis flipped.
- **Shell / subshell / core level**: a shell groups states with the same principal quantum number (K, L, M…); a subshell also specifies orbital angular momentum (`1s`, `2p`, `3d`, etc.). In the GUI, **core level** is the practical umbrella term for selectable XPS entries, including spin-orbit components such as `Au 4f7/2`.

## Abbreviations used in the UI
- **PES**: Photoelectron Spectroscopy.
- **XPS**: X-ray Photoelectron Spectroscopy.
- **BE**: Binding Energy.
- **KE**: Kinetic Energy.
- **BG**: background.
- **FWHM**: full width at half maximum.
- **LFWHM**: Lorentzian FWHM.
- **GFWHM**: Gaussian FWHM.
- **DS alpha / Alpha**: Doniach-Šunjić asymmetry parameter.
- **IBW**: Igor Binary Wave file.


## Global controls

#### **Load**
PANDA supports three primary PES/XPS source formats:
- **TXT** - Scienta/SES text exports.
- **IBW** - Igor Binary Wave files.
- **XY (SPECS Prodigy)** - SPECS/SpecsLab Prodigy `.xy` exports.

**Recommended:** drag a supported file from the file manager directly onto the **Loaded files** tree. PANDA detects TXT, IBW, and XY automatically, so there is no file-type menu to choose first.

The **Load** button is the alternative when browsing through a file dialog is more convenient. Choose **TXT**, **IBW**, or **XY (SPECS Prodigy)** and then select the file.

All three formats enter the same PANDA Raw Data workflow after loading. Repeated spectra appear as iterations and can be handled with the same selection, map, processing, fitting, and batch-analysis tools. XY files additionally retain Prodigy Group/Spectrum metadata. When a repeated XY acquisition contains one trustworthy physical second coordinate, such as sample temperature, position, or sufficiently resolved acquisition time, PANDA exposes that coordinate through the normal map Y-axis machinery while keeping **Iteration** as the sequence coordinate. Large XY regions create individual Iteration rows only when **Iterations** is expanded.

#### **Close all**
Closes all opened files and clears loaded file content from the GUI. It also unchecks **Identify signals**, restores all signal-identification settings to their defaults, and returns the main workspace to **Raw Data**. Curves intentionally copied to **Plotted Data** are preserved and can be cleared from that panel itself.

#### **Clear all**
Clears the working selection and plots without closing loaded files. It also unchecks **Identify signals**, restores its default settings, and returns the main workspace to **Raw Data**. Curves intentionally copied to **Plotted Data** are preserved and can be cleared from that panel itself.

#### **Settings (cog)**
The cog button immediately before **Load** opens **Settings**. The **Appearance** section controls the application theme (**System**, **Light**, or **Dark**), interface density (**Automatic**, **Standard**, or **Compact**), and UI font size (current default, +1 pt, or +2 pt). Changes apply immediately. Matplotlib plot/figure fonts are not changed.

#### **Help**
Opens:
- **What is what?** - this document, describing controls and UI elements.
- **How to?** - workflow-oriented help for first-time users.
- **What's new?** - release notes for the installed version.
- **About** - version, date, license, and software description.


# Data loading and selection
The two trees separate loaded data from the spectra currently selected for display and analysis.


## Loaded files tree
The left-hand tree shows loaded files and their internal structure.

The left-hand **Loaded files** tree supports metadata inspection. Hovering a file, region, or curve entry shows the hint **Right-click for metadata and other options**. Right-click and choose **Show metadata** to open a read-only two-column metadata viewer. It groups available source/file, dimension, acquisition/instrument, manipulator, run-mode, curve/iteration, and warning information. For Scienta TXT and IBW files, manipulator coordinates including **X**, **Y**, **Z**, and **Polar** are shown when present in the source metadata. Long axis/scan-point lists are summarized rather than expanded into hundreds of values. Use the **Find / Prev / Next** controls to search parameter names and values, and **Copy selected** or **Copy all** to place displayed metadata on the clipboard.

#### Checking / selecting curves
Checking curve items adds them to the working selection and makes them available in the right-hand selected-curve tree and plot area.

#### Regions and repeated spectra
A parent region can contain many iterations. Checking the parent toggles all children in one update.

#### Drag-and-drop loading
Drag-and-drop is the quickest way to load data in normal use. Drag one or more supported **TXT**, **IBW**, or SPECS Prodigy **XY** files from the file manager onto the **Loaded files** tree. PANDA detects the format automatically and uses the same duplicate/reload protection as the **Load** menu.

Use **Load** instead when you prefer to browse for a file or explicitly choose a format.


#### Reloading an already loaded source
PANDA treats each loaded source file as a **snapshot** of the file contents at load time. Right-click a file-level entry and choose **Reload from disk** to read the current disk contents. If the snapshot has not been used for processing or derived data, PANDA can replace it in place. Once it has been used for normalization, fitting, energy calibration, or Plotted Data, PANDA protects the existing work and provenance and offers **Load updated copy**, **Replace and remove dependent data**, or **Cancel**. Loading the same full file path again through **Load** uses the same policy instead of silently creating an uncontrolled duplicate. Updated copies are labelled explicitly in the Loaded files tree while keeping the real source path in metadata.

#### Live monitor (specialized online-acquisition tool)
Right-click a loaded **IBW** or **TXT** file and choose **Open live monitor** to watch a file that is being overwritten as a 2D acquisition grows. IBW acquisition normally stores each region in its own physical file, so each IBW opens its own monitor directly. If a TXT file contains several regions, **Open live monitor** becomes a submenu listing the region names; each region can be opened in its own independent Live Monitor window, and several regions from the same TXT file can be watched at the same time. The monitor opens as an independent non-modal window, so it can be minimized or left behind the main PANDA window while acquisition continues. It does not alter the normal Raw Data selection or plot. The live-map X-axis uses the same energy title as the normal PANDA plot (for example **Binding Energy [eV]** or **Kinetic Energy [eV]**) and follows the main-window **Flip X axis** control. All 2D maps use **terrain** by default. Right-click inside the live 2D map to open the same color-palette chooser used elsewhere in PANDA. After the pointer moves onto the live map and then remains still for about one second, PANDA shows **Right-click to change palette** for about five seconds. The hint is shown only once for that Live Monitor window.

The Live Monitor uses the same **Lines-style cross-section layout** as Processed Data **View: Lines**: the growing 2D map is accompanied by a horizontal trace below it and a vertical trace to its right. If the acquisition contains a genuine physical second dimension, such as photon energy, that physical scale is shown on the map's **left Y axis**, while **Iteration** remains on the **right Y axis** of the vertical trace, exactly as in View: Lines. If there is no independent physical second dimension, **Iteration** is shown on both the map's left Y axis and the right-hand trace so the map never loses its Y scale. The horizontal cursor label follows the map Y representation (for example **PhE = ... eV**). The dashed H/V cursors continue into the corresponding trace panels and can be dragged either on the map or directly by their continued guides in the side traces. The on-map cursor labels and the Matplotlib toolbar coordinate readout use the same formatting as Processed Data **View: Lines**, including BE/KE, PhE/Iteration and nearest-pixel intensity. Drag close to the H/V crossing point on the map to move both cursors together. Both lines carry coordinate labels. **H thickness** and **V thickness** are exact counterparts of the View: Lines controls and average an odd, symmetric number of map rows/columns (1, 3, 5, ..., 25); the shaded cursor bands show the effective averaging width and continue into the side traces. Live Monitor intentionally exposes only these two Lines controls; animation, trace export, and trace-scale controls remain part of the normal post-acquisition map workflow. The Live Monitor control row sits directly above the Matplotlib toolbar; only spectra/update/status diagnostics remain below the plot.

The timing line deliberately separates three different quantities. **Checked every** is how often PANDA performs a lightweight file-status check using file size and modification time; this does not reread or reparse the spectrum. In **Auto**, checking starts at **0.5 s** while no acquisition interval is known and then adapts using the observed update interval (the current Auto rule is approximately one check per fifth of the learned interval, limited to 0.5-5 s). **Settle for** is the quiet period required after PANDA notices a file change before it attempts to copy and parse a snapshot: **0.75 s** in Auto and **0.5 s** in fixed mode. This protects against reading a file while the analyzer is still writing it. **New spectrum every** is the observed interval between successful spectrum updates after Auto has enough observations; it is informational and is based on the recent successful-update history. Fixed **1 s, 2 s, 5 s,** or **10 s** choices change **Checked every**, not the acquisition rate.

The status line distinguishes the acquisition state. **Monitoring** (green) means the monitor is active and recent updates are consistent with an ongoing acquisition. After PANDA has learned the spectrum interval, if no successful new spectrum arrives for **max(30 s, 5 × the learned interval)**, the status becomes **Acquisition appears stopped** (dark orange). This is deliberately not called "finished": the acquisition may have completed, been paused, or stalled. In Auto, PANDA then relaxes the lightweight file-status check to **5 s** but continues watching. As soon as any file change is detected, it temporarily returns to the short settle/recheck cycle instead of waiting another 5 s; this lets fast same-filename restarts be parsed reliably. After a valid new snapshot is read, the status returns to **Monitoring**. Pressing **Stop** gives the red **Stopped** status and really stops polling until **Start** is pressed.

**Reload latest snapshot** transfers the current file contents into normal Raw Data through PANDA's standard provenance-aware reload policy. If the loaded snapshot has already been normalized, fitted, energy-calibrated, or used for Plotted Data, the same protected choices are shown as for **Reload from disk**. **Stop** pauses monitoring without closing the window; **Start** resumes it; **Close** stops the worker and closes the monitor.

The monitor is intended for acquisition-time inspection rather than normal post-beamtime analysis. PANDA reads only a temporary snapshot of the growing file; if the source is busy, changing, incomplete, or temporarily unreadable, that cycle is skipped silently so the acquisition writer keeps priority. If a new acquisition starts again under the same filename from iteration 1, the map is reset automatically and Auto timing is relearned from the new run, so a long idle gap between runs is not interpreted as a spectrum interval.



## Selected-curve tree
The selected-curve tree contains the curves currently chosen for display and further work.

- Show / hide spectra using checkboxes.
- Check or uncheck a region parent to toggle many children at once.
- Select spectra for fitting workflows.
- Use region-level and curve-level entries to organize sequences.

### Large sequence behavior
For files with hundreds of iterations, checking or unchecking a region parent should update the plot only once after the bulk change, not after every child item.


> **See also:** [Data tabs and plot area](#data-tabs-and-plot-area) for the shared plot and tab-specific controls.


# Data tabs and plot area
The selectors are arranged as two visual groups. **Raw Data**, **Processed Data**, and **Plotted Data** form the data workflow on the left. **Cross sections** and **Binding energies** form independent reference tools on the far right. Only one panel is active at a time.


## Raw Data
Use **Raw Data** to inspect unprocessed spectra, control the displayed energy direction, and activate **Identify signals** for one active spectrum.

When **All in region** is checked, the adjacent region selector chooses all Average/Trace curves with the same region name across the loaded files. Unchecking **All in region** clears that group selection and removes those spectra from the plot. Open the selector to browse quickly: moving the highlight with the mouse or **↑ / ↓** temporarily previews the highlighted region in the plot while the list remains open. **Click / Enter** commits the region; **Esc** or dismissing the list without choosing restores the previously committed plot and selection. Previewing does not change the checked curves or the selected-curve tree.

> **See also:** [Signal identification](#signal-identification) for settings, PE/Auger algorithms, reliability, and references.


## Processed Data
Use **Processed Data** for basic intensity and energy handling, interactive 2D maps of selected sequences, and for passing prepared curves to calibration, plotting, and fitting workflows.

> **See also:** [Processed Data controls](#processed-data-controls), [Processing and energy calibration](#processing-and-energy-calibration), [Plotted Data controls](#plotted-data-controls), and [Spectrum fitting](#spectrum-fitting).


## Plotted Data
Use **Plotted Data** to compose a final multi-curve figure from independent snapshots passed from Processed Data or imported from CSV. Curve order, visibility, line appearance, legend, annotation, waterfall offset, and CSV exchange are controlled here without changing the source curves. **Check all** and **Uncheck all** provide one-click visibility control for the complete plotted set.

> **See also:** [Plotted Data controls](#plotted-data-controls) for all controls and [Compose and export curves in Plotted Data](#compose-and-export-curves-in-plotted-data) in **How to?**.


## Cross sections
The **Cross sections** tab is a standalone Yeh-Lindau reference tool. It does not depend on open data and contains element/core-level selection, reference conditions, a Matplotlib plot, and numerical values.

> **See also:** [Cross-section reference](#cross-section-reference) for the complete panel description and physical definitions.


## Binding energies
The **Binding energies** tab is a standalone XPS reference browser placed beside **Cross sections** at the right of the tab bar. Its normal browsing view contains core-level binding energies (BE) only. Auger families can be added optionally when searching a binding-energy region.

> **See also:** [Binding-energy reference](#binding-energy-reference) for the controls, sources, and interpretation note.


## Shared plot area
The data tabs use Matplotlib plot areas for the selected or composed curves. The standard toolbar provides zoom, pan, save, reset-view, and **Edit axis, curve and image parameters** tools. Toolbar edits apply to the currently displayed Matplotlib figure; when the application rebuilds that plot after changing tabs/views, its normal application-defined appearance is restored. The two reference tabs have their own independent plots or tables and do not use the selected-curve tree.

### Binding-energy direction
For binding-energy spectra, the X axis is normally shown in the conventional high-to-low direction. The GUI uses the detected energy scale and the **Flip X axis** control where available.


# Signal identification
Signal identification is entered from **Raw Data**, but it is a substantial subsystem with its own dialog, measured-feature detection, element-consistency logic, Auger-family analysis, and reference sources.

> **See also:** [Raw Data](#raw-data) for its location in the main window.

## Reference sources and scope
The packaged identification references come from three sources:
- **LBNL X-Ray Data Booklet** - elemental/atomic core-level binding energies and Yeh-Lindau atomic photoionization cross sections;
- **XPS International Handbook of the Elements and Native Oxides** - condensed-phase, native-oxide, common-compound, and experimental Auger reference positions;
- **EADL 2025** - supplementary atomic-relaxation data used mainly to support Auger-family plausibility where handbook coverage is incomplete.

These sources are reference constraints, not a calculated spectrum. Chemical state, charging, calibration, solid-state effects, and line-shape changes can shift or reshape measured features. Important assignments should therefore be checked against expected composition, companion core levels, relative intensities, and higher-resolution spectra.

The **Identify signals** checkbox is next to **Flip X axis** on the **Raw Data** tab. It is enabled only when exactly one ordinary spectrum is active. Click **Signals…** to select expected elements and adjust the identification settings. The adjacent **Show Auger** checkbox is checked by default and is enabled only while **Identify signals** is active. Uncheck it to hide Auger-family shading, connectors, and labels while keeping the PE annotations; re-checking it restores the cached Auger annotations immediately without rerunning identification.

## Identification dialog and settings
- **Photon energy** - read from metadata when available and required for converting between PE/Auger kinetic energies and the displayed BE/KE scale. It is refreshed whenever the active spectrum changes. If the new spectrum has no photon-energy metadata, the field is cleared rather than reusing the previous value. A manual value remains associated with the current spectrum.
- **Matching tolerance** - maximum energy mismatch considered during candidate generation. The default is **5 eV**; ambiguity and companion-line checks remain stricter than a simple tolerance match.
- **Peak prominence** - minimum prominence used for detecting spectral structures. The default is **0.5% of the signal range**.
- **Valence-band cutoff** - protects the topmost valence region from atomic-level assignments. The default interval is **0-15 eV BE**, shown once as **VB** at the centre of a purple shaded region, visually distinct from Auger-family envelopes.
- **Reference mode** - chooses whether condensed-phase, gas-phase, or both kinds of references are considered.
- **Include second-order photoemission** - also considers second-order PE positions when the photon energy is known.
- **Small charging possible** - unchecked by default. When enabled on a binding-energy spectrum, charging assistance is used only as a fallback. A satisfactory normal assignment is not replaced by a charging-shifted line of another element. This is important in crowded regions such as the 3p lines of neighbouring transition metals. Only when the normal interpretation is inadequate may the program search up to **+10 eV** toward higher binding energy for a physically consistent strongest-line anchor. Resolved doublets must have the expected ordering and splitting; weaker lines are accepted only when they support approximately the same positive element shift. Once a PE anchor is established, the corresponding Auger-family search region is also shifted toward higher apparent binding energy and broadened to allow for chemical-state and differential-charging effects. Auger shifting is never used to establish an element by itself. After identification, a compact one-line summary above the results table reports each reliably inferred element shift and whether its Auger family was adjusted; hover it for the supporting-line details.
- **Expected elements** - at least one element must be selected. The program deliberately does not search the entire periodic table without user guidance.

The **Signals…** window uses a movable vertical splitter. Identification settings and the result table are on the left; the expected-element selector is on the right. The initial position shows five element tiles per row on a typical display. Drag the divider to redistribute space; minimum pane widths prevent accidental collapse. The settings use two compact columns to leave more height for the result table.

## Displayed assignments and results
### Plot annotations
Accepted PE lines are labelled above the corresponding measured peak maxima; the database position is used for assignment, not for placing the guide line. Weak PE lines remain eligible, including companion components found with increased sensitivity, but every visible PE label must correspond to an independent local maximum that rises above the measured point-to-point noise. Expected reference positions alone never create labels. Spin-orbit components are shown separately only when their reference splitting is resolvable in a survey spectrum; otherwise the family label is used, for example **Al 2p** rather than an arbitrary **Al 2p1/2** component. Auger signals are shown as experimentally supported broad subregions such as **KLL**, **LMM**, or **MNN**. Several separated subregions may share one family label. Each shaded subregion has a stronger central core and independently fading left/right tails; these are support indicators, not exact compound-specific band boundaries. Every visible Auger family receives one plot-local colour shared by its label and all of its subregions. A thin branched connector points from the label to the measured centre of each associated subregion without implying sharp band limits. Uncertain or conflicting candidates remain unlabelled.

### Assignment table
The result table contains:
- **Peak** - energy of the detected spectral maximum on the currently displayed BE or KE scale;
- **Best assignment** - highest-ranked candidate that passed the confidence, ambiguity, and companion-line checks; **Unassigned** means that none passed;
- **Type** - **PE** for a photoelectron line or **Auger** for an Auger-family match;
- **Reference** - nearest compatible reference position converted to the displayed scale. For an Auger family, this is the nearest tabulated atomic/handbook position to the dominant measured subregion; it is not the centre or boundary of a calculated compound-specific line shape;
- **ΔE** - `Peak − Reference`, in eV. Its sign therefore follows the displayed energy axis values, not the visual left/right direction;
- **Reliability** - an estimated assignment reliability from **0 to 100%**. Hover over any row to see the six component values used for that assignment. The displayed number is not a statistical probability; it is a transparent comparative indicator for the current spectrum, selected elements, settings, and bundled reference data;
- **Alternatives / reason** - other considered candidates when an assignment is accepted, or the reason why a detected peak was rejected.


### Reliability calculation
For each accepted assignment, six factors are calculated on a 0-1 scale and combined as:

`Reliability = round[100 × (0.25 C + 0.25 P + 0.20 S + 0.15 U + 0.10 A + 0.05 Q)]`

where:
- **C - line-pattern consistency:** for PE lines supported by at least two candidate structures of the same element, the program first calculates a robust common shift, `Δcommon`, as the prominence-weighted median of `Peak − Reference` for those structures. For the current line, the residual mismatch is `r = |ΔE − Δcommon|`, and `C = clip[1 − r / tolerance, 0, 1]`. A coherent shift shared by several lines therefore does not reduce this factor. With only one PE line, C measures how closely that line matches its absolute reference position. For an Auger family, C reflects how many distinct broad measured subregions support the family (full value at three or more);
- **P - measured peak evidence:** mainly compares the peak prominence with other detected features. A clear, close and unique PE match receives a minimum evidence value, so a C 1s peak is not rated poorly only because the metal substrate peaks are much stronger;
- **S - element support:** normally increases when several structures support the same element. For B, C, N, O, F and Ne, a selected and well-matched 1s line is treated as a valid standalone core-level anchor because no companion core line is expected outside the valence region;
- **U - assignment uniqueness:** 1 when no competing assignment exists. Otherwise it is `clip[(score margin) / 1.5, 0, 1]`, where the score margin is the difference between the internal ranking scores of the nearest competitor and the accepted candidate;
- **A - absolute-shift plausibility:** this is deliberately a weak factor because chemical state, charging, or calibration can shift all PE lines together. For the magnitude `s = |Δcommon|`, A is 1.00 through 2 eV, then decreases linearly to 0.70 at 5 eV, 0.30 at 10 eV, and 0 at 15 eV. With one isolated PE line, its own ΔE is used only for this weak plausibility factor. For Auger families, A is neutral at 0.75 because Auger chemical shifts need not track PE shifts one-to-one;
- **Q - reference quality:** 1.00 for an elemental handbook reference or a high-coverage Auger family, 0.90 for a compound handbook reference or medium-coverage Auger family, 0.80 for an X-Ray Data Booklet reference or low-coverage Auger family, and 0.75 when the reference category is unspecified.

For Auger-family rows, the dedicated family-level weighting is `100 × (0.35 C + 0.30 P + 0.20 S + 0.15 Q)`, where C is the number of distinct measured broad subregions (clipped at three), P is the broad-residual significance, S is the number of supporting PE assignments for the element (clipped at three), and Q reflects handbook coverage. Auger reliability therefore measures family-level experimental support; it does not compare an observed solid or compound spectrum with a calculated atomic line shape.

The common shift is a robust pattern descriptor, not a fitted oxidation-state correction. A 3-4 eV common displacement can therefore coexist with high reliability when several lines preserve their expected relative spacing. Conversely, mutually inconsistent shifts lower the line-pattern factor even when every individual line lies within the broad matching window.

The **Reliability** cell uses a restrained color scale: pale green for strong values, pale yellow for plausible values, pale orange for weak values, and pale red for uncertain values. The row tooltip applies the same colors separately to all six factors and also reports the common shift and residual mismatch when available. Numerical values remain visible, so color is not the only indicator.

The peak-assignment table is sorted by **Peak energy** by default. Click the **Peak**, **Type**, or **Reliability** column heading to sort by that quantity; click the same heading again to reverse the order. Other columns are informational and do not change the sorting.

An internal score resolves competing candidates. The displayed **Reliability** is a comparative support indicator, not a statistical probability. It may change with tolerance, prominence, selected elements, and companion lines.

Suggested interpretation: **90-100% very strong**, **75-89% strong**, **55-74% plausible**, **35-54% weak**, and **below 35% uncertain**.

## Identification evidence and acceptance rules
### Photoelectron and companion-line rules
Once one component is confidently assigned, the expected position of its partner is searched with increased sensitivity. Weak partners are retained when their local hump is reproducible above the measured noise; random fluctuations, smooth backgrounds, and neighbouring peak tails remain unlabelled. The plotted guide line is placed at the observed local maximum rather than at the tabulated reference energy. When two chemical states produce repeated components of the same transition, the program may keep both. It requires a matching separation in another core-level family of the same element, for example two Si 2p peaks and two Si 2s peaks separated by nearly the same energy. This paired evidence prevents genuine Si/SiOx components from being removed as duplicate labels.
### Auger-family rules
The handbook and EADL positions define broad energy ranges where an element/family is physically plausible; they do not define the displayed line shape. Inside those ranges, the program interpolates through accepted narrow PE lines, estimates a slowly varying local background, and looks for broad measured excess at several smoothing scales. The noise estimate is taken mainly from the high-frequency remainder, so real structured Auger intensity in a noisy survey does not raise its own rejection threshold. A narrow feature is still rejected unless it has unusually strong broad-scale support. The observed envelope determines the strong core and softer asymmetric tails. Identifying the element from PE lines alone is not sufficient. EADL normally supplements handbook families. It may also introduce an EADL-only family when the element is already supported by at least two confident PE lines and the spectrum contains a broad, noise-significant excess in the predicted range. EADL-only assignments keep low reference confidence and capped reliability; weak atomic clusters are ignored. Overlapping candidates that do not add independent evidence remain unlabelled. Distinct accepted subregions are shaded separately, with only one label per element/family. Family names use consistent atomic-shell notation, such as KLL, LMM, and MNN.
### Label placement and family links
PE, VB, and Auger labels use a consistent font size. Close PE labels may combine or separate according to the visible energy range. Overlapping Auger-family labels are automatically stacked in adjacent rows. Each Auger family uses a shared colour for its label, soft envelopes, and a thin connector branched to the centres of its individual measured subregions; colour is therefore reinforced by geometry rather than used alone.

## Reference-data interpretation and limitations
Auger data are fundamentally kinetic-energy references and are converted using the photon energy. An isolated atom, an elemental solid, and different compounds of the same element can have substantially different Auger shapes. The identifier therefore does not calculate an exact expected Auger spectrum. It uses reference energies as plausibility constraints and derives visible subregions from broad structures in the measured spectrum. It also does not determine an exact oxidation state or chemical environment from a survey alone.

### Auger reference provenance
Auger references are kept in separate source-specific files. The XPS International Handbook database remains the primary experimental source. EADL 2025 theoretical atomic-relaxation clusters are supplementary energy guides. An EADL-only family can be considered only when several confident PE lines establish the element and a broad measured feature supports the prediction; such assignments are lower confidence. Weak clusters are excluded from detection priors, and neither source is broadened into a predicted gas-, solid-, or compound-specific line shape.

### Cross-section-aware signal consistency
Signal identification also uses the packaged Yeh-Lindau core-level photoionization cross sections as relative evidence. At the spectrum photon energy, they help rank complete spin-orbit families and check whether a shallow `s` assignment has the stronger corresponding `p` support. Cross sections never create a line without a measured local feature.

Before matching, generic family references and component-specific references are normalized into one consistent internal family. When the condensed-state database gives only the main family position, that value sets the absolute binding energy. Atomic data may supply the spin-orbit separation when the components should be resolvable in a survey, as for Ca 2p. Shallow families with small atomic splittings, such as transition-metal 3p, remain unresolved and are labelled by the generic family. Resolved spin-orbit families use a sibling-safe partner search whose window stops before the neighbouring component, preventing a strong component from being mistaken for its weaker partner.


# Processing and energy calibration


## Processed Data controls

### Counts and CPS for spectra
On ordinary 1D spectra in **Raw Data** or **Processed Data**, hover the vertical **Intensity** axis title for a hint and double-click it to choose **Counts** or **CPS** (counts per second). Counts is the default. CPS divides each spectrum by its own `Time per Spectrum Channel` acquisition metadata. Raw and Processed Data keep independent choices. The Processed Data choice propagates to ordinary downstream spectra passed to Plotted Data, fitting, and energy-calibration workflows. **MAP views always remain in counts**, irrespective of the current Processed Data spectra setting.

Purpose: apply basic processing and prepare spectra for further treatment.

#### Intensity normalization
The controls are grouped in the **Normalization** box on the Processed Data tab. **Norm E:** sets the centre of the normalization interval. **E span:** sets its width as a percentage of each spectrum's full energy range. Each curve is divided by the mean intensity over that interval. Near an energy edge, the interval shifts inward while keeping the same width. Normalization is a reversible Processed-data view transform: while it is enabled, energy calibration and single/batch fitting use the same normalized numerical curves that are displayed. The normalization state is independent of the E-calibrated/raw view, so switching between those views keeps normalization enabled and applies it consistently to either energy axis. These virtual workflow inputs are marked **(Norm)**; turning normalization off returns downstream workflows to the unnormalized selected curves. Signal-identification labels and guide lines remain attached to the same features.

#### Energy handling
The tab respects the detected energy scale and display convention. For binding-energy data, the X axis can be flipped for the standard PES representation.

#### Re-running energy calibration
If E-calibrated curves already exist, starting **Calibrate Energy** again first shows a **Redo energy calibration** warning. **Redo** deletes the existing E-calibrated derivatives and starts a fresh calibration from the default state; closing/cancelling the warning leaves the current calibration untouched. This prevents old and newly recalibrated curve sets from coexisting accidentally.

#### Passing data to plotting and fitting workflows
**Pass to plotting** copies the curves currently selected in Processed Data to **Plotted Data**. The copies preserve the displayed energy calibration and intensity normalization and are independent of later changes in Processed Data. The same selected curves can also be used for energy calibration, single-curve fitting, or batch fitting.

#### 2D Map workflow
A **MAP** button is shown only for a genuine multi-iteration dataset with at least two iteration curves from the same source group. Synthetic **All in...** collections of independent spectra and ordinary multi-spectrum groups do not show MAP. MAP mode is entered only after a valid 2D image has been constructed; otherwise the interface stays in ordinary spectra mode. Use the **View** selector to choose **Simple**, **Lines**, or **ROI**. All 2D maps use **terrain** by default. Right-click directly inside the 2D image to open a chooser with a gradient preview for each available palette. After the pointer moves onto a displayed map and then remains still for about one second, PANDA shows **Right-click to change palette** for about five seconds. The hint is shown once per representation visit: switching between Raw Data, Simple, Lines, ROI (or another map representation) and later returning starts a fresh visit, so the hint can appear again after the one-second dwell. This right-click workflow also applies to 2D maps shown on the **Raw Data** tab and in **View: Simple**, even though Simple uses overlapping Matplotlib axes internally. Simple is the unobstructed full-map view. Lines adds draggable horizontal and vertical cursors with the corresponding 1D traces below and to the right. The cursors can be dragged either on the 2D map or directly from their continued guides in the bottom/right traces. Dragging near the H/V crossing point on the 2D map moves both cursors together. **H thickness** and **V thickness** average an odd, symmetric number of rows/columns (1, 3, 5, ..., 25) around the cursor; the strongly shaded, outlined cursor bands show the effective averaging footprint on the map. The H and V cursor guides, including their averaging widths, continue onto the corresponding side traces for precise positioning on intensity peaks. ROI adds one movable/resizable rectangular region with horizontal and vertical projections.

The normal Y coordinate is **Iteration**. When no independent physical second dimension exists, **Iteration** is displayed on both the map's **left Y axis** and the vertical trace's **right Y axis**. When the imported sequence contains a physical second-dimension scale, for example photon energy, temperature, or time, the map's left Y axis instead shows that physical scale while **Iteration** remains on the right-hand trace. This applies consistently to Raw Data maps and to Simple, Lines, and ROI. In Lines/ROI-style layouts, the left-side axis titles are positioned close to their tick labels with a compact shared margin so more figure width is available to the map and traces.

In **Lines** view, **Bin size** uses the same consecutive complete-bin rule as batch fitting; **1** is the unbinned default and values above 1 enable binning directly. Each non-overlapping group of the chosen size is averaged row-by-row; an incomplete trailing group is discarded. The displayed Iteration coordinate and any physical second-dimension coordinate are represented by the mean coordinate of the source rows in each bin. Binning affects only the Lines map and its live/stored traces; it does not alter the stored spectra or the Simple/ROI views.

In **Lines** view, the lower-right corner contains separate **Auto scale H** and **Auto scale V** checkboxes for the live side traces, with **Animation...** below them. Both autoscale options are checked by default. **Auto scale H** controls the intensity axis of the horizontal/bottom trace; **Auto scale V** controls the intensity axis of the vertical/right trace. Uncheck either one to fix only that trace to the minimum and maximum intensity of the currently displayed MAP dataset; the fixed range is recalculated when the displayed map itself changes, but not when the corresponding cursor moves. **Animation...** opens a compact non-modal controller for moving either cursor through the map. Choose H or V, use the full valid range or a custom From/To interval, select the speed in physical thickness-steps per second, and choose **One way** or **Back and forth** with optional **Loop**. H and V keep their own custom range settings when you switch between them. The physical/key step is always the currently selected H/V thickness, but intermediate cursor, band and trace profiles are interpolated for smooth visual motion. Only key positions where the complete selected width fits inside the map are used. The panel shows the current physical coordinate and **Frame n / N** and provides first, play, pause, stop, and last controls. **Speed** and **Loop** can be changed during playback without stopping the animation. Path-defining changes such as H/V selection, range, From/To, mode, or H/V thickness stop/rebuild playback; changing thickness also immediately updates the animation step.

The **Video** section exports presentation-ready MP4/H.264 movies. **Frame rate** controls the saved movie FPS, **Cycles** sets a finite number of complete one-way or back-and-forth cycles, and **Sequence** chooses whether to export the **Current line** only or a combined **H then V** movie. The live **Loop** checkbox does not make video export infinite. When **H then V** is selected, the exporter uses the saved H range/settings first and then the saved V range/settings in the same MP4; switch between H and V beforehand if you want to define different custom ranges for the two scans. **Save video...** first opens the native filename dialog, then immediately renders the same Matplotlib figure area as the toolbar's **Save figure** action (2D map plus H and V traces, excluding Qt controls). A progress dialog reports the active H/V sweep together with frame and cycle number and provides **Cancel**; incomplete files are removed after cancellation. Video export requires FFmpeg (for a conda environment: `conda install -c conda-forge ffmpeg`).

The Matplotlib status readout reports physical map coordinates and the nearest map-pixel intensity in all map views. The three fixed-width fields use a small inset after the toolbar buttons and compact spacing between values so the readout is visually separated from the tools while the Intensity value remains visible in narrower windows. For example, it shows BE/KE together with `PhE` (or Iteration when no physical second axis exists) and `Intensity = ...`. Physical energy coordinates use a fixed one-decimal representation and intensity uses fixed scientific notation; while a map is displayed, the toolbar coordinate readout uses the system fixed-width font at the normal toolbar text size so the fields remain visually stationary on Windows and macOS as their values change. The draggable Lines cursors display their current coordinates directly on the map and update continuously: the vertical cursor shows BE/KE, while the horizontal cursor shows the physical second-dimension value (for example `PhE = 585.00 eV`) when available, otherwise `Iteration = N`. The labels automatically switch contrast for the active map palette. Lines cursor positions are remembered for each map when the palette changes, when you leave and return to Lines, when you switch away from and back to the Raw/Processed Data tabs, and when **Bin size** changes. If the map dimensions change, the nearest available physical positions are restored.

The ROI initially spans about 20% of the full X and Y ranges. Drag inside it to move it or drag an edge to resize it; the compact X/Y centre and width fields provide the same control numerically. Trace axes follow the current ROI extent. **Full width** and **Full height** temporarily expand one ROI dimension to the complete map range; unpressing either button restores its previous extent. **Pass to plotting**, placed below the extent buttons, copies every spectrum inside the ROI Y range to Plotted Data and truncates each copy to the ROI X range. These independent derived curves are labelled `[ROI]`; any active MAP normalization is preserved while the original spectra remain unchanged.

**Normalize** is available in all three map views and acts row-by-row on the displayed 2D map without changing the stored 1D spectra. **At BE** divides every row by its mean intensity within an energy interval centred on the chosen BE; **Area** divides every row by its integrated intensity between two energy limits. Selecting either method opens its settings dialog automatically. To reopen the settings later, choose the already active **At BE** or **Area** entry again from **Normalize**. Invalid values are rejected and the previous valid settings remain active.

The selected normalization interval is shown by default as a distinct full-height vertical band. For **At BE**, the BE and width controls use 0.1 eV steps. In **Simple**, **Lines**, and **ROI** map views, drag the band interior to move the interval or drag either vertical edge to resize it; the dialog and map stay synchronized. In Lines/ROI views, clicks on the active line cursors or ROI take priority when they overlap the normalization band, so both interactions remain available. **Show normalization range on map** hides or shows the band, while **Reset** restores the method-specific defaults without turning normalization off. Normalization defaults are re-seeded when the active map dataset changes and after **Clear all** or **Close all**. The normalization-settings dialog remembers its last screen position during the session.

In Lines and ROI, **Plot H-trace** and **Plot V-trace** snapshot the corresponding displayed trace into the shared **Trace comparison** window. A horizontal trace uses the map X quantity, normally Binding Energy for XPS/PES. The right-hand vertical trace uses **Iteration** by default. When a genuine physical second Y coordinate is available, for example photon energy, double-click the right-hand Y axis or its title to switch between Iteration and that physical coordinate; a tooltip appears when hovering over that axis or its title. If only Iteration is available, this selector is disabled. **Plot V-trace** uses the Y representation currently shown on the right-hand trace. Stored traces are independent snapshots: moving a cursor/ROI or changing normalization afterwards does not alter a trace that has already been added.

#### ResPES analysis
When the physical second dimension is **Photon Energy**, **ResPES analysis** is available in Simple view only. Opening it adds compact controls to the right of the map and a dedicated intensity-versus-photon-energy trace below the map. Switching to Lines or ROI hides the ResPES button, controls, cut, and live trace without discarding their state; returning to Simple restores them.

Use **Energy axis** in the **Map energy axis** group to redraw the same ResPES data on either **Binding energy (BE)** or **Kinetic energy (KE)**. The measured map may itself be stored on either BE or KE; the program detects the source scale and converts in either direction row-by-row using `KE = hν - BE - Φ`. **Analyzer WF** defaults to 4.5 eV (allowed range 2.5-6.5 eV) and remains editable because it is also needed for cuts expressed on the energy scale opposite to the measured one. With keyboard tracking off, a typed WF value is applied when you press Enter or leave the field; spin arrows update immediately. Switching axis never modifies the stored spectra. Because different photon-energy rows cover different transformed energy ranges, unmeasured parts of a converted rectangular display remain blank rather than being extrapolated.

**Constant BE** follows a finite-width, non-dispersing binding-energy region. **Constant KE** follows a physical fixed-kinetic-energy trajectory using the same analyzer work function. **Constant PhE** draws a horizontal band at a selected excitation energy and returns the corresponding spectrum versus the currently displayed BE or KE axis. Drag any cut band to move it or drag either edge to change its width. The position/width controls and the map overlay stay synchronized, and the live cut trace is calculated from the same currently normalized map that is displayed. If a BE-defined normalization range is shown, its band is displayed in BE view; KE view keeps the normalized intensities but does not draw that BE interval as an incorrect vertical band.

Use **Plot trace** to snapshot the current ResPES trace into Trace comparison. The automatic name reflects the selected cut coordinate, for example `Trace at BE = ...`, `Trace at KE = ...`, or `Trace at PhE = ...`. This allows Constant-BE, Constant-KE, and Constant-PhE traces to be preserved and compared without changing the generic Lines/ROI traces.

#### Trace comparison
**Trace comparison** is a lightweight, shared window for 2D-derived traces from Lines, ROI, and ResPES analysis. It contains a standard Matplotlib toolbar, optional legend, trace selector, **Rename...**, **Export CSV**, and **Clear all**. Lines and ResPES traces receive coordinate-aware automatic names such as `Trace at BE = ...`, `Trace at KE = ...`, `Trace at PhE = ...`, or `Trace at Iteration = ...`. Any trace can still be renamed for the legend and export.

Only traces with compatible X quantities are combined in one comparison plot. Different numerical grids are allowed, but a Binding-Energy trace is not silently mixed with, for example, a Temperature or Photon-Energy trace. If an incompatible trace is added, the program asks before starting a new comparison.

Closing the comparison window with its title-bar X only hides it; stored traces remain available. Changing map view or dataset also preserves them. **Clear all** or **Close all** in the main application, or **Clear all** in the comparison window, ends the comparison session and forgets the stored traces. CSV export writes the stored traces without silently interpolating different X grids.

The Processed Data Map is an interactive analysis view; it is separate from map/sequence previews used inside calibration and batch-fitting dialogs.

## Plotted Data controls
Purpose: compose, arrange, style, label, import, and export curves intended for a final plot.

#### Plot and toolbar
The Matplotlib canvas shows the current composition. Use the standard toolbar for pan, zoom, home/reset, subplot adjustment, and saving the figure.

#### Legend
**Legend:** selects **None**, **Curve name**, or **Custom (TeX)**. **Curve name** uses the immutable original names shown in the curve list. In **Custom (TeX)** mode, click a legend title to enter a new legend/export name. TeX-style notation such as `S 2p$_{3/2}$`, `Fe$^{3+}$`, and `$\alpha$` is supported; use the **?** button in the custom legend-name editor for a compact syntax reference. An undefined title is shown as `<select curve name>`. The legend itself can be dragged on the plot.

**Legend style...** controls transparency, margins, font size, bold, italic, and underline.

#### Reverse X and grid
**Reverse X** changes the horizontal-axis direction. **Grid:** selects no grid or increasingly fine major/minor grids.

#### Annotation
**Annotation...** adds or edits one draggable text annotation. Its dialog controls text, font, color, background, border, margins, and common symbols.

#### Plotted curves list
Each row contains:
- a drag handle and a wide original-name area; drag either to reorder curves;
- **×** to remove the curve after confirmation;
- a checkbox to show or hide the curve;
- a color button;
- line-style selection;
- line width or marker size;
- optional **Fixed width**, which displays all curves with one common line width (or marker size for marker-only curves) without overwriting their individual settings;
- the original curve name, which is fixed and never edited.

The curve color links the fixed original name in the list to its current legend title. Reordering also changes plot, legend, and CSV column order.

#### Waterfall
**Waterfall** adds a uniform vertical offset between visible curves. **Offset** sets the step as a percentage of the combined visible intensity range. The Offset slider adapts to the number of visible curves: it spans 0-100% for up to 30 curves and then progressively narrows for dense plots, while the linked numeric field supports fractional percentages. With very large curve sets, the slider value updates while dragging and the plot redraws when the handle is released so the control remains responsive. **Filling** controls an optional background-colored fill beneath each displaced spectrum: 0% (default) gives the ordinary line waterfall, while increasing the slider progressively hides curves behind foreground ridges; 100% is fully opaque. **Fixed color** is optional and disabled by default, so waterfall plots preserve the individual curve colors. Enable it for dense sequences when a single monochrome outline gives a clearer surface-like view, and use the adjacent color button to choose that color.

#### Export / Import
The menu contains **Export CSV** and **Import CSV**. Both dialogs start in the current data-loading folder, then remember the most recently used CSV folder.

**Export CSV** writes only visible curves, in current list order, as separate Energy/Intensity column pairs without interpolation. Headers use the active legend naming mode. In Custom mode, undefined `<select curve name>` entries trigger an OK/Cancel warning.

**Import CSV** appends curves from either the paired-column export format or a shared-energy-column CSV. Imported headers become curve names.

#### Clear plotted
**Check all** and **Uncheck all** at the right end of the top control row show or hide every plotted curve at once.

**Clear plotted** removes all curves and the plot annotation from this tab and switches Waterfall off. It does not remove or alter data in Raw Data or Processed Data.


## Energy calibration
The energy-calibration dialog is used to determine and apply energy shifts.

### Map tab
Purpose: inspect calibration candidates over a sequence or map-like set of spectra.

#### Typical use
Use this tab to track a reference feature across a sequence.

### Fit tab
Purpose: fit calibration references such as a Fermi edge or reference peak. **Fit references** fits every mapped reference and, when fitting finishes, automatically overlays all reference curves and their fits in the plot.

#### Expected EF / target energy
Optional expected reference values can stabilize the calibration and help identify problematic spectra. For Fermi-edge fitting, the default relative fit window is **-1.0 to +0.4 eV** around the expected EF; the tighter high-binding-energy side helps reduce interference from nearby valence-band features. Adjust the window when the reference spectrum requires it.

### Targets tab
Purpose: review and apply calibration targets.

#### Typical use
Use the Targets tab to check which curves will be corrected and how the correction will be applied.



# Cross-section reference
The Cross sections tab provides photon-energy-dependent atomic reference curves and angular corrections independently of loaded spectra.

> **See also:** [Cross sections](#cross-sections) for its location among the main tabs.

Purpose: browse the bundled Yeh-Lindau atomic core-level photoionization data without loading or selecting any spectrum. This tab is a standalone reference aid and does not read values from the Raw or Processed tabs.

## Data source
The packaged HDF5 database contains the atomic subshell photoionization cross sections and angular-asymmetry parameters tabulated by **J. J. Yeh and I. Lindau** for core levels. The data are atomic reference values: they are useful for comparing which lines should be relatively strong at a chosen photon energy, but they are not a quantitative model of a measured solid or molecular sample.

For each selected subshell, the database supplies:
- **Photon energy** - incident photon energy in eV.
- **σ atomic** - total atomic photoionization cross section in megabarns (**Mb**, where 1 Mb = 10⁻¹⁸ cm²).
- **β** - dipole angular-asymmetry parameter describing how photoelectron intensity varies with emission direction for linearly polarized light.

Cross sections are interpolated in log(σ) versus log(photon energy); β is interpolated versus log(photon energy). Values outside the tabulated range are reported as **N/A** rather than extrapolated.

## Reference conditions
The compact conditions box is above the plot on the right side of the draggable divider.

- **Photon energy** - sets the dashed vertical marker in the plot and the energy used for the numerical values table. The default is **1000 eV**. The marker can also be dragged horizontally with the mouse; the numerical field and values table update with it.
- **E-vector-analyzer angle (θ)** - angle between the electric-field vector of the linearly polarized radiation and the analyzer axis. The default is **48°**, corresponding to the standard FlexPES geometry.

The angular factor is

`F(β,θ) = 1 + β/2 × (3 cos²θ − 1)`

and the displayed geometry-weighted value is

`σgeometry = σatomic × F(β,θ)`

The common `1/(4π)` differential-cross-section factor is intentionally omitted. Consequently, `σgeometry` remains in **Mb** and can be compared directly with `σatomic`. At the magic angle, approximately 54.7°, the β-dependent term vanishes and the angular factor equals 1.

The angular factor describes only the dipole emission geometry. It does **not** include analyzer transmission, kinetic-energy-dependent attenuation, sample depth distribution, morphology, elastic diffraction, chemical-state effects, peak broadening, or spectral overlap. Therefore, the values should guide relative intensity expectations rather than predict measured peak areas exactly.

## Elements and available core levels
The left pane uses the same color-coded element tiles as signal identification. Its default width is just sufficient for five element tiles per row and can be changed with the vertical splitter.

1. Click one or more element tiles.
2. Available tabulated core levels are appended below as compact checkboxes, for example **Au 4f5/2** and **Au 4f7/2**.
3. Core-level checkboxes fill each row from left to right and wrap onto additional rows.
4. Checking or unchecking a core level immediately adds or removes its curve and numerical row.

**Select all** checks every available core level for the currently selected elements. **Clear all** keeps the selected elements but unchecks all core levels and clears the plot and values table. **Clear elements** resets the complete reference view.

## Plot and values table
The plot uses a dedicated Matplotlib canvas and the standard Matplotlib navigation toolbar. It shows:
- one geometry-weighted curve for each checked core level;
- a small circle on each curve where it crosses the selected photon energy; the circles move along the curves when photon energy changes;
- a mouse-draggable legend, which can be shown or hidden with **Legend**;
- a mouse-draggable dashed vertical line at the selected photon energy;
- prominent major and minor grids;
- a logarithmic cross-section axis when curves are present.

The compact table below the plot reports:
- **Core level** - selected element and tabulated level;
- **σ atomic (Mb)** - Yeh-Lindau total atomic cross section at the selected photon energy;
- **β** - interpolated angular-asymmetry parameter;
- **Angular factor** - `F(β,θ)` for the selected geometry;
- **σ geometry (Mb)** - `σatomic × F(β,θ)`.

Hover over a table heading to see its definition. Changing photon energy or angle refreshes all currently selected curves and numerical values immediately.


# Binding-energy reference
The **Binding energies** tab is a pure reference tool and does not read or modify loaded spectra. At the top, **Method** explicitly selects one of two independent workflows: **Elements / core levels** or **BE range**. The inactive workflow is disabled so that the source of the displayed table is always clear. Auger families are deliberately kept out of the element/core-level browser and are available only as an optional addition to a BE-range search.

## Elements / core levels
- **Elements** selects one or more elements. **Clear elements** resets the selection and table.
- **Available core levels** lists the reference entries available for the selected elements. Selecting an element alone only reveals the available checkboxes; the table remains empty until at least one is checked.
- **Select all** checks every currently available core level.
- **Clear all** clears all of these checkboxes while keeping the element selection.
- The browsing table contains photoelectron (**PE**) core-level references and their tabulated binding energies.

## BE range
- **BE from** and **to** define the binding-energy region of interest.
- **Include Auger signals** - off by default. When enabled, Auger-family candidates are added to the energy-region search.
- **Photon energy** - used only for optional Auger lookup and therefore enabled only when **Include Auger signals** is checked. It converts Auger KE regions to their apparent BE positions.
- **Find** returns core-level PE candidates by default; when **Include Auger signals** is checked it adds Auger candidates that can occur in the same BE interval.

For PE candidates, the tabulated core-level BE is compared directly with the requested region. For Auger candidates, the tabulated KE interval is converted to its position on the binding-energy scale using `BE = hν − KE`, consistent with the convention used elsewhere in the program.

The result table reports **Element**, **Signal**, **Level / family**, **Reference energy**, **Position on BE scale**, **Environment / state**, **Phase**, and **Source**. For PE rows, **Reference energy** is a BE; for Auger rows it is a KE interval. Experimental XPS International Handbook Auger positions are grouped into broad family ranges, while supplementary EADL entries retain their clustered atomic-relaxation intervals. These are reference regions rather than exact compound-specific line shapes, and all matches should be treated as candidates.


# Spectrum fitting
The **Fit core-level PE spectra** window is for detailed fitting of one spectrum at a time.

## General purpose
Build and test a peak model for one selected spectrum before applying it to a sequence. When a fresh spectrum is opened without a saved/anchor fit state, PANDA makes conservative automatic initial peak suggestions from resolved maxima (up to five). These are starting guesses only: shoulders are deliberately not over-interpreted, and the user remains responsible for the physical model.

## Main plot and residual plot
The upper plot shows:
- measured data,
- peak components,
- background,
- total fit.

A **Legend** checkbox beside the plot toolbar is checked by default and shows/hides the legend for these curves. The legend is draggable, and each peak component uses its editable peak **Label** as the legend name (falling back to Peak N when the label is blank).

The lower plot shows the residual:

`residual = data - total_fit`

## Peak parameters
Typical peak parameters are:
- **Energy** - peak position. Drag a colored component marker horizontally to move that component; its Energy field updates continuously.
- **Height** - editable component peak maximum. Drag the same marker vertically to change Height; values are constrained between zero and the maximum measured intensity of the active spectrum. Energy and Height remain independently draggable when the corresponding parameter is not tied.
- **Area** - derived integrated intensity of the fitted peak component over the fitted energy interval. It is reported after fitting and is normally the more useful quantity for comparing peak intensities.
- **LFWHM** - Lorentzian full width at half maximum.
- **GFWHM** - Gaussian full width at half maximum.
- **Alpha** - Doniach-Sunjic (DS) asymmetry parameter.

## Peak line shapes
With **Alpha = 0**, a component is a **Voigt** profile: Lorentzian and Gaussian broadening are combined into one symmetric peak. **LFWHM** and **GFWHM** control those two broadening contributions.

With **Alpha > 0**, the component uses a **Doniach-Sunjic (DS)** asymmetric line shape with Gaussian broadening. The DS form is useful for asymmetric metallic photoemission peaks; increasing **Alpha** increases the asymmetry.

**Height** and **Area** are not generally equivalent: changing the widths or asymmetry changes the area associated with a given peak height. PANDA therefore keeps **Height** as the editable fit parameter but calculates **Area** from the final fitted component. For DS peaks, Area means the numerical integral over the actual fitted energy interval.

## Parameter modes
Parameters may be:
- **Free** - optimized independently.
- **Fixed** - kept constant during fitting.
- **Tied** - constrained relative to another parameter.

**Tied** is the general peak-level linking mechanism and remains available independently of SO-doublet grouping. For an ordinary peak, an Energy tie preserves the current offset to the corresponding Energy of another peak. Height, LFWHM, GFWHM, and Alpha ties preserve the current multiplicative factor to the corresponding parameter of another peak. Each parameter can be tied separately, so this mechanism can describe manually constrained spin-orbit-like pairs as well as other linked-peak models.

### SO doublets
**Create SO doublet...** is an additional structured option for treating two existing peaks as one physical spin-orbit pair. It does not replace the general peak-level **Tied** mechanism described above. PANDA does not guess doublets automatically. In the creation dialog choose the existing **Major peak** and **Minor peak**, optionally enter a family label, and select `p`, `d`, `f`, or `Custom`. The orbital type supplies only an initial statistical major/minor height ratio. If no label is entered, PANDA uses **Doublet #1**, **Doublet #2**, and so on. A named family such as `S 2p` is displayed as **S 2p #1**, with clones numbered **S 2p #2**, **S 2p #3**, and so on. Constituent peaks keep their simple `P1`, `P2`, ... labels.

Each SO-doublet card controls the relationship between its two constituent peaks:
- **Splitting** is the energy separation between major and minor components. It can be **Fixed**, **Free** within editable min/max limits, or **Tied to** the splitting of another SO doublet.
- **Ratio** is the major/minor peak-height ratio. The statistical `p`, `d`, or `f` value is only a starting estimate; Ratio can likewise be **Fixed**, **Free** within limits, or **Tied to** another doublet.
- **LFWHM**, **GFWHM**, and **Alpha** default to **Same** for both members, but each relationship may be changed to **Independent**.

The minor energy and height are derived from the major component and the current splitting/ratio constraints. Hover the bold doublet title to see which `Pn` peaks are its major and minor members. **Ungroup** returns both members to ordinary standalone peaks with their normal parameter controls restored.

**Clone** creates a new peer doublet with the current shape, constraints, splitting, and ratio preserved. The clone starts weaker and slightly energy-shifted so it is visible rather than exactly overlapping its source. Use the normal mouse handles to reposition and rescale it. Any doublet, including a clone, can be cloned again.

**Doublet view** changes only the component representation on the plot. Unchecked, major and minor members are drawn as individual peak curves. Checked, each SO pair is replaced by its summed doublet curve while standalone peaks remain individual. Only the major marker is shown for a grouped doublet and acts as the existing mouse handle for shifting/rescaling the whole pair. The selected representation remains active during live fitting redraws. User-selected component colors are preserved; otherwise PANDA assigns distinct automatic colors to the currently visible peak or doublet components.

A major/minor **Height** ratio is equivalent to an **Area** ratio only when both members have the same line shape and widths.

## Background models
The background section controls the baseline contribution. The fitted background is shown separately and is also included in the total fit.

## Fit range
The top row shows **Fit range: Full** or **Fit range: Custom** with an **Edit** button. The editor provides **Min**, **Max**, **Select on plot**, **Full**, and **Close**. Valid numeric edits apply immediately. **Select on plot** lets you drag the desired interval directly on the spectrum and completes the action when the drag ends; accepted range boundaries can also be dragged directly on the main plot. The exact custom limits remain available in the editor/status tooltip without crowding the top row.

## Start fit and Undo fit
**Start fit** runs the nonlinear fit. After the fit, the result table and diagnostic messages indicate whether the fit converged and whether any parameters approached bounds. **Undo fit** restores the complete fit state from immediately before the most recent fit attempt, including peak/background settings, fit range, displayed model, and previous fit-result state.

## Save and Load fit configuration
The single-fit window uses compact **Save** and **Load** menus.

**Save** contains:
- **Save config snapshot** - keep the current fit configuration temporarily in memory; curves are not stored.
- **Save config to file...** - save the fit configuration to a reusable JSON file; curves are not stored.
- **Save config + curves...** - export the fit configuration together with calculated fit curves. This command becomes available after a fit result exists.

**Load** contains:
- **Load config snapshot** - restore the configuration previously saved in memory.
- **Load config from file...** - load a configuration from JSON. Calculated curves are regenerated automatically from the loaded configuration.

The configuration includes the peak model and parameters, constraints, background settings, and related fit setup. The curves-inclusive export writes fit information as JSON and numerical curves such as energy, data, total fit, background, residual, and peak components as CSV.


# Sequence fitting and analysis
The batch-fitting window is for fitting a sequence of spectra from the same or similar region.

## Prepare sequence fit tab
Purpose: choose and inspect the spectra that form the sequence.

### Selected spectra tree
The left side lists the spectra included in the batch workflow.

### Binning
Binning averages adjacent spectra before fitting. **Bin size 1** is the unbinned default; increasing the value enables binning directly. If the number of spectra is not divisible by the bin size, the remainder at the end is discarded and reported.

### Map / sequence display
The plot can show individual curves or a map-like representation of the sequence. This helps confirm that the selected spectra form a meaningful sequence.

### Anchor spectra
Anchor spectra such as **Start**, **Middle**, and **End** define fit setups and initial guesses across the sequence. The first **Fit anchor...** action in a new batch dialog shows a short component-identity reminder: **labels define component identity across the series**. A labelled peak or doublet is treated as the same evolving component even when its energy or intensity changes, and a component may be absent from one or more anchors.

There are two supported preparation paths:
- **Ordinary peaks only** - the established peak-oriented batch table is used. Ordinary peak-only anchors keep the existing batch parameter table unchanged.
- **SO doublets, optionally mixed with standalone peaks** - PANDA builds a doublet-aware table from the union of labelled components present in the fitted anchors.

For the SO-doublet path, each doublet exposes editable **Splitting** and **Ratio** rows. Minor **Energy** and **Height**, and any minor LFWHM/GFWHM/Alpha controlled by a **Same** relation, are shown as grey read-only **Derived** entries because they are not independent fit parameters. Minor shape parameters remain ordinary editable rows when their doublet relation is **Independent**. For a given doublet label, keep the same major/minor pairings (the same major/minor peak labels) and the same Same/Independent shape relationships across anchors. Numerical values may vary between anchors. General per-peak Free/Fixed/Tied relationships remain available alongside the doublet constraints; the batch table is the final place where sequence-fit constraints are reviewed.

## Run sequence fit tab
Purpose: define the batch parameter table and run fitting passes.

### Batch parameter table
The table contains one row per peak/background parameter and columns such as:
- **Start / Middle / End** - anchor-derived values.
- **Initial** - value used as a default or fallback.
- **Initial strategy** - how values are generated along the sequence.
- **Min / Max** - parameter bounds.
- **Mode** - Free, Fixed, or Tied.
- **Tie / Link** - textual tie definition.
- **Notes** - warnings or inherited constraint information.

Column widths are manually adjustable by dragging header separators.

### Strategy
The **Strategy** selector defines which batch pass recipe will be run:
- independent first pass from Start/Middle/End guesses;
- later constrained passes prepared from analyzed trends.

### Run batch fit
Runs the selected strategy. The Run tab always shows fitting progress, including constrained passes prepared on the Analyze tab.

### Store all fit results
Optional and off by default. When checked before a pass is run, the program retains the full fitted curves for every spectrum, including data, total fit, background, residual, and individual peak components. This uses more memory, but enables post-run fit navigation and **Export all fits...** for that pass.

### Stop
Requests stopping after the current spectrum finishes. Completed spectra remain stored in memory.

### Monitor plot
The monitor plot updates after each completed spectrum. It shows:
- data,
- total fit,
- peak components,
- residual.

The main and residual Y axes use scientific notation.

If **Store all fit results** was enabled for the completed pass, the controls below the monitor become active. Use the left/right arrows to step through stored fits, or enter a fit number directly to jump to that spectrum. The monitor redraws the selected spectrum with its stored fit components and residual.

## Analyze fit results tab
Purpose: inspect fitted parameter trends, prepare selected smoothing constraints, fit analytical trend curves, and export trends.

### Result pass
Selects which completed pass to analyze, for example:
- **Pass 1: independent**
- **Pass 2: constrained**

### Y parameter
Selects the type of trend to plot, such as:
- peak energy,
- peak height,
- peak area,
- LFWHM,
- GFWHM,
- alpha,
- fit-quality diagnostics.

When a parameter type is selected, available curves are checked and plotted by default.

### Polynomial smoothing / next-pass constraints
Polynomial smoothing prepares **fixed parameter values for the next batch pass**. It is deliberately separate from analytical trend fitting used only for interpretation and export.

The target selector contains only parameters that are independent in the fit model. For an explicit SO doublet, derived minor-member parameters such as the minor **Energy** and **Height** remain available for plotting and diagnostic trend analysis, but they are **not offered as next-pass constraint targets**. Constrain the corresponding major parameter instead. If the SO splitting is allowed to vary, the derived minor energy can still show small point-to-point variation even when the major energy is fixed to a smooth polynomial; this is expected and reflects the fitted splitting rather than a failure of the major constraint.

### Trend analysis and export panel
The right-hand trend-analysis panel is for descriptive trend fitting and CSV export only. It does not change batch-fit constraints.

It provides:
- trend-curve selector,
- analytical model selector,
- model formula display,
- fit selected trend,
- accept/store fit for export,
- clear selected or all stored fits,
- normalized RMSE as fit-quality number,
- Export CSV.

Stored analytical trend fits are exported together with the raw plotted trends.

### Export all fits...
Available only when the selected result pass was run with **Store all fit results** enabled. It writes one ZIP archive containing `batch_manifest.csv` and one plain CSV file per stored spectrum fit. Each fit CSV contains energy, data, total fit, background, peak sum, residual, and the individual peak-component curves.

### Export CSV
Exports the currently plotted raw trend curves and any accepted analytical fitted curves. The CSV contains spectrum number and trend columns, while the metadata header records pass history, binning, model choices, and fitted parameters.


# Output and conventions


## Plot styling conventions
Several plots use common PES display conventions:
- binding-energy axes are flipped when appropriate;
- total fit curves are drawn on top of data and components;
- residual plots are shown below fit plots;
- scientific notation is used for intensity-like Y axes where useful;
- grid and toolbar controls are kept consistent across windows.


## Export formats

### CSV
CSV is used for numerical arrays and curves because it is easy to open in Igor Pro, Origin, Excel, Python, MATLAB, and similar tools.

Examples:
- raw and fitted trend curves from batch analysis;
- single-fit energy/data/model/component curves.

### JSON
JSON is used for structured fit metadata and parameters because it preserves nested information such as:
- peak components,
- parameter bounds,
- fixed/tied/free modes,
- background model,
- fit diagnostics,
- source metadata.


## Practical fitting notes
- Use the single-curve fit workflow to develop a robust fit model before applying it to a sequence.
- For batch anchors, use labels consistently: labels determine whether a peak or SO doublet is treated as the same component across the series.
- Use batch Pass 1 to find unstable parameters before imposing sequence-wide constraints.
- Use **Analyze fit results** to inspect trends and decide which **independent** parameters need smoothing or constraints.
- Derived SO-doublet minor parameters can be inspected as trends but are not independent next-pass targets.
- Use analytical trend fits for interpretation/export; use polynomial next-pass smoothing only when you deliberately want to stabilize a later fitting pass.
