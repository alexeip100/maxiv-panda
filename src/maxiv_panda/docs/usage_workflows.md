# Load and organize data
Load data and create the working selection used by plotting and analysis tools.


## Quickstart
A basic workflow is:

1. **Recommended:** drag a TXT, IBW, or SPECS Prodigy XY file from the file manager onto the **Loaded files** tree. PANDA detects the format automatically.
2. Alternatively, choose **File → Load data...**, then **TXT**, **IBW**, or **XY (SPECS Prodigy)**, and select the file.
3. Expand the file and region, for example `S2p`, `C1s`, or another core-level region.
4. Check the spectrum or spectra you want to inspect. They appear in the selected-curve tree on the right and in the main plot.
5. Use **Raw Data** first to verify that the file was read correctly.
6. Use **Processed Data** when you need simple normalization or energy-scale handling.
7. For one detailed fit, select one curve and open **Fit core-level PE spectra**.
8. For a sequence of similar spectra, select the sequence and open **Batch fitting of core-level PE spectra**.

Use **Single curve fit** to build the model, **Batch fitting** to apply it to a sequence, and **Analyze fit results** to inspect parameter trends.

**Controls used (What is what?):** *Drag-and-drop*, *File → Load data...*, *Loaded files tree*, *Selected-curve tree*, *Raw Data*, *Processed Data*, *Fit core-level PE spectra*, *Batch fitting of core-level PE spectra*

### Abbreviations used below
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


## Load TXT, IBW, or SPECS Prodigy XY data
### Recommended: drag and drop
1. In the file manager, select a supported **TXT**, **IBW**, or SPECS Prodigy **XY** file.
2. Drag it onto PANDA's **Loaded files** tree.
3. PANDA detects the format automatically and adds the file to the tree.
4. Expand the file and inspect the available regions and spectra.

This is usually faster than choosing a loader first and is the recommended everyday method. Drag-and-drop uses the same source-snapshot and duplicate/reload protection as File → Load data....

### Alternative: File menu
1. Click **File** in the top-left control area and choose **Load data...**.
2. Choose **TXT**, **IBW**, or **XY (SPECS Prodigy)**.
3. Select the file in the file dialog.
4. Wait until it appears in the **Loaded files** tree.

After loading, all three formats use the same PANDA selection and analysis workflow. TXT, IBW, and XY regions can be selected, mapped, processed, fitted, and batch-fitted through the same downstream tools.

For very large XY regions, PANDA delays creation of individual Iteration rows until you expand **Iterations**. The region data and Average are already loaded; expanding only reveals the existing spectra in the tree.

For repeated XY regions, PANDA also checks whether the acquisition carries one reliable physical Y coordinate. A varying external channel such as sample temperature is used when available; otherwise PANDA can use one varying Y/Z position coordinate or sufficiently resolved acquisition time. If no trustworthy physical coordinate is available, the Y axis remains **Iteration**. This does not change the spectra or their iteration numbering.

**If a file does not appear:** with **File → Load data...**, check that the selected loader matches the file type. With drag-and-drop, verify that the extension is one of the supported formats.

**Controls used (What is what?):** *Drag-and-drop*, *File → Load data...*, *TXT*, *IBW*, *XY (SPECS Prodigy)*, *Loaded files tree*


## Inspect file and acquisition metadata
Use metadata inspection when you need to verify how a spectrum was acquired before processing or fitting it.

1. In the **Loaded files** tree, right-click a file, region, or curve.
2. Choose **Show metadata**.
3. Browse the read-only parameter/value table. Source/file information, dimensions, acquisition and instrument settings, manipulator coordinates, run mode, curve/iteration information, and parser warnings are grouped when available.
4. Use **Find / Prev / Next** to locate a parameter quickly.
5. Use **Copy selected** or **Copy all** when the metadata should be pasted into a note, logbook, or analysis script.

For very long axis or scan-point arrays, PANDA summarizes the values rather than expanding hundreds of entries. Metadata inspection does not modify the loaded data.

**Controls used (What is what?):** *Loaded files tree*, *Show metadata*, *Find / Prev / Next*, *Copy selected*, *Copy all*



## Reload a file without losing provenance
A loaded source is a snapshot of the file at the moment it was read. Use this workflow when the physical file has changed on disk.

1. Right-click the file-level entry in **Loaded files** and choose **Reload from disk**. You can also use **File → Load data...** on the same full path; PANDA routes that through the same reload policy.
2. If no processed or plotted data depend on the current snapshot, confirm replacement to refresh it in place.
3. If the snapshot has already been used for processing or derived data, choose one of:
   - **Load updated copy** - safest/default choice; keep the old immutable snapshot and its derived data, and load the current disk contents as a clearly labelled new snapshot.
   - **Replace and remove dependent data** - deliberately discard processed/plotted data that depend on the old snapshot, then replace it.
   - **Cancel** - leave everything unchanged.

PANDA compares the canonical full path, not only the filename, so two files with the same name in different folders remain separate sources.

**Controls used (What is what?):** *Loaded files tree*, *Reload from disk*, *Load updated copy*, *Replace and remove dependent data*

## Monitor a growing 2D acquisition file
This specialized workflow is intended mainly during measurements when the analyzer repeatedly overwrites the same IBW or TXT file as new spectra are acquired.

1. Load the acquisition file once it exists; it may still contain only the first spectrum.
2. In the **Loaded files** tree, right-click either the **file-level entry** or an individual **region name** and choose **Open live monitor**. Region-level right-click works for both TXT and IBW data. At file level, an IBW opens directly, while a multi-region TXT shows an **Open live monitor** submenu with the available region names. Repeat for another region to monitor several acquisitions in separate windows.
3. Leave **Update = Auto** for normal use. The timing line has three separate meanings: **Checked every** is the lightweight file-size/modification-time check; **Settle for** is the quiet time after a detected change before PANDA copies and parses a snapshot; **New spectrum every** is the learned interval between successful acquisition updates. Auto starts checking every **0.5 s**, uses a **0.75 s** settle period, and then adapts the check interval from the observed acquisition timing. A status check alone does not reread the spectral data. The fixed **1/2/5/10 s** choices change only **Checked every** and use a **0.5 s** settle period.
4. Watch the status indicator: **Monitoring** is green. Once the spectrum interval has been learned, no successful update for **max(30 s, 5 × the learned interval)** changes it to dark-orange **Acquisition appears stopped**. PANDA still watches the file (Auto relaxes the quiet-state check to **5 s**). Once any file change is detected, PANDA immediately returns to the short settle/recheck cycle rather than waiting another 5 s, so a restarted fast acquisition under the same filename resumes automatically. **Stopped** is red and means you explicitly pressed **Stop**; polling then remains off until **Start**.
5. Watch the dedicated Lines-style map window grow as new spectra appear. The horizontal trace is shown below the map and the vertical trace to the right. Drag either dashed H/V cursor on the map, drag its continued guide directly in the corresponding trace panel, or drag near the H/V crossing point to move both together. The cursor labels and both traces update immediately. Cursor labels and the Matplotlib toolbar coordinate readout match Processed Data **View: Lines** for BE/KE, PhE/Iteration and intensity. The normal Raw Data tree, checked curves, and main plot are not modified. The monitor can be minimized or left in the background while acquisition continues. Its X-axis title and direction follow the normal PANDA energy-axis handling and the main **Flip X axis** control.
6. Adjust **H thickness** and **V thickness** exactly as in Processed Data **View: Lines** to average an odd number of neighbouring rows/columns (1, 3, 5, ..., 25). The shaded selection bands on the map and their continuations into the traces show the effective averaging width. If the file contains a genuine physical second dimension (for example photon energy), Live Monitor shows that scale on the map's left Y axis while the right trace remains labelled by Iteration, matching View: Lines. Otherwise Iteration is shown on both the map's left Y axis and the right trace.
7. The default 2D palette is **terrain**. Right-click inside the live map to choose another palette. After moving onto the map and leaving the pointer still for about one second, PANDA shows **Right-click to change palette** for about five seconds as a one-time hint for that Live Monitor window.
8. When you want the current disk contents in normal PANDA analysis, press **Reload latest snapshot**. This uses exactly the same reload/provenance policy as **Reload from disk** in the Loaded files tree, including protected choices when the existing snapshot has already been used.
9. Use **Stop / Start** when monitoring should be suspended/resumed, or **Close** to end monitoring completely.

If the acquisition software has the file busy or PANDA encounters an intermediate write, PANDA keeps the last valid map and simply tries again later. If the same filename starts a new acquisition again from iteration 1, Live Monitor resets the map automatically and clears the old Auto timing history, so the idle time between the two runs is not learned as an unrealistically long spectrum interval.

**Controls used (What is what?):** *Loaded files tree*, *Open live monitor*, *Update*, *Auto*, *Checked every*, *Settle for*, *New spectrum every*, *Flip X axis*, *H thickness*, *V thickness*, *right-click palette chooser*, *Reload latest snapshot*, *Stop / Start*, *Close*


## Select spectra for plotting
1. In the **Loaded files** tree, expand the file and region.
2. Check one or more spectra.
3. The checked spectra are copied to the selected-curve tree on the right.
4. The plot updates to show the selected spectra.

For a region with many iterations, you can check the parent region item to select all children at once.

The selected-curve tree can:

- show or hide spectra;
- select which spectrum should be fitted;
- select a sequence for batch fitting;
- check or uncheck an entire region group.

**Tip:** for large sequences, first select the parent region and then hide/show children from the selected-curve tree if needed.

**Controls used (What is what?):** *Loaded files tree*, *Selected-curve tree*, *Region*, *Iteration*


## Work with many iterations of one region
For repeated spectra, such as annealing, dosing, irradiation, or time series:

1. Load the file.
2. Expand the region with many iterations.
3. Check the parent region item to select all iterations.
4. Confirm that the selected-curve tree on the right contains the full sequence.
5. Use the plot to identify obvious outliers.
6. If the sequence is very dense, use the map/sequence tools in the batch window rather than trying to inspect all curves in one normal line plot.

Parent selection updates large sequences in one plot refresh.

**Controls used (What is what?):** *Region*, *Iteration*, *Selected-curve tree*, *Batch fitting of core-level PE spectra*


# Inspect spectra and use references
Use the three data tabs in sequence when preparing spectra. The two right-aligned reference tabs are independent lookup tools and may be opened without loading data.


## Inspect raw spectra
Use **Raw Data** to verify the energy range, axis direction, signal quality, and sequence consistency before processing or fitting.

Look for:

- whether the energy axis is correct;
- whether the spectra have the expected region and energy range;
- whether the binding-energy axis is displayed in the conventional direction;
- whether any spectra are obviously bad or empty;
- whether repeated spectra form a sensible sequence.

Displaying several iterations reveals drift, changing peaks, and outliers.

**If the BE axis direction looks wrong:** check the energy scale and the available BE/KE or flip controls. Binding-energy spectra are normally displayed from high BE to low BE.

**Controls used (What is what?):** *Raw Data tab*, *Selected-curve tree*, *BE / KE*, *Flip X axis*


## Compare atomic photoionization cross sections
Use the **Cross sections** tab as a reference when judging which core levels should be relatively strong at a chosen photon energy. No spectrum needs to be loaded.

1. Open **Cross sections**.
2. Enter the photon energy of interest.
3. Keep the E-vector-analyzer angle at the FlexPES default **48°**, or enter the geometry relevant to another experiment.
4. Click each element of interest in the periodic-table selector.
5. Check the desired core levels in the compact wrapping list; the curves and values appear immediately and update with every checkbox change.
6. Read the curves and the exact values table below the plot. The dashed vertical line marks the chosen photon energy, and the small curve-coloured intersection circles move with it as the photon energy changes.

The database contains Yeh-Lindau atomic subshell cross sections σ and angular-asymmetry parameters β. The program multiplies σ by the dipole angular factor `1 + β/2 × (3 cos²θ − 1)` for the selected E-vector-analyzer angle. The common `1/(4π)` factor is omitted, so both atomic and geometry-weighted values remain in Mb. These are reference values for broad intensity expectations, not predictions of measured peak areas: analyzer transmission, attenuation, sample depth, morphology, diffraction, chemistry, broadening, and overlaps can all alter experimental ratios. Hover over the table headings for concise definitions.

**Controls used (What is what?):** *Cross sections tab*, *Photon energy*, *E-vector-analyzer angle*, *Elements*, *Available core levels*


## Look up XPS binding energies and optional Auger candidates
Use **Binding energies** as an independent reference browser.

1. To browse known elements, select one or more elements and then check the desired **core levels**. **Select all** and **Clear all** operate on the available core-level checkboxes.
2. To identify an unknown feature, enter the **BE from** / **to** region visible in the spectrum and click **Find**. By default the result contains core-level PE candidates only.
3. When Auger candidates are also relevant, check **Include Auger signals**, enter the **Photon energy**, and click **Find** again. Auger KE regions are then converted to their apparent BE positions and added to the same result table.
4. Compare the signal type, level/family, reference energy, BE position, chemical-state information, and source. Selecting an element or core level returns the table to the normal BE-reference view.

Auger families are intentionally kept out of the browsing list and, when requested, are shown as broad reference regions rather than every individual multiplet transition. Treat all matches as candidates because chemical state and experimental conditions can shift measured energies.

**Controls used (What is what?):** *Binding energies tab*, *Elements*, *Available core levels*, *BE from*, *BE to*, *Include Auger signals*, *Photon energy*, *Find*


# Identify signals
Use measured evidence, expected elements, charging assistance, and PE/Auger consistency to interpret a survey spectrum.


## Identify signals in a survey spectrum

**Reference sources:** identification uses the LBNL X-Ray Data Booklet for elemental/atomic core-level energies and Yeh-Lindau cross sections, the XPS International Handbook for condensed-phase and experimental Auger references, and supplementary EADL 2025 atomic-relaxation data. These are reference constraints rather than an exact calculated spectrum.

> **Chemical-state pairs:** If the same element appears in more than one chemical state, several peaks can carry the same core-level label. The program keeps them only when a second core-level family shows the same separation, as for paired Si 2p and Si 2s components from Si and SiOx.

Use this workflow after the raw spectrum has been inspected and the energy scale looks sensible.

1. Keep exactly one spectrum active in the selected-curves tree.
2. On **Raw Data**, click **Signals…** and select the elements reasonably expected in the sample. At least one element is required.
   The dialog opens with settings and the result table in a wide left pane and the element selector in a narrow right pane. Drag the divider when more room is needed for either area.
3. Check the **Photon energy**. It is normally read from file metadata, but it can be entered manually.
4. Keep **Matching tolerance** at the default **5 eV** initially. The tolerance creates candidates; companion-line, ambiguity, and consistency checks decide whether a label is accepted.
5. Adjust **Peak prominence** only when real weak peaks are missed or noise maxima are detected. The default is **0.5% of the signal range**.
6. Keep the **Valence-band cutoff** at **15 eV BE** unless another protected range is justified. The region is labelled **VB** and is excluded from atomic-level matching.
7. Choose the appropriate **Reference mode**. **Automatic (prefer solids)** is suitable for most solid samples; use **Gas phase** for molecular spectra.
8. Keep **Include Auger lines** enabled when photon energy is known. Reference positions provide broad search ranges only. When a broad measured Auger-like excess is found, the observed component is shaded with a strong central core and fading, potentially asymmetric tails. Several separated components may share one family label.
9. Click **Apply and identify** to refresh both the plot and the result table while keeping the identification panel open. Adjust the settings and apply again as needed; click **Close** when finished. Peaks without sufficiently reliable assignments remain unlabelled. For some families, such as Ca 2p, the solid-state reference fixes the main line position while the atomic table supplies only the doublet separation. A strong spin-orbit component can trigger a more sensitive search for its partner, but the partner still needs an independent local maximum above the measured noise. A weak but coherent peak can therefore be labelled, whereas a random fluctuation at an expected reference energy cannot. PE guide lines are placed at the measured maxima rather than at the database positions. Auger regions require a broad, noise-significant measured excess after accepted narrow PE lines are suppressed; element identification alone does not activate them. The faded edges communicate uncertain tails and must not be read as exact compound-specific band limits.
10. Uncheck **Identify signals** to remove all annotations.

### How to read the result table
- **Peak** is the energy of the detected maximum on the displayed BE or KE scale.
- **Best assignment** is the top-ranked candidate that also passed the confidence, ambiguity, and companion-line checks. **Unassigned** means that no candidate passed all checks.
- **Type** distinguishes a photoelectron line (**PE**) from an Auger-family match (**Auger**).
- On the plot, separated bands belonging to one Auger family share one colour and are linked to their family label by a thin branched connector. The branches point to measured band centres, not exact boundaries.
- **Reference** is the nearest compatible tabulated position after conversion to the displayed scale. For Auger entries it is the nearest reference to the dominant measured component, not a calculated band centre or boundary.
- **ΔE** is `Peak − Reference` in eV. It describes numerical energy mismatch and is independent of whether the X axis is visually reversed.
- **Reliability** is a 0-100% comparative indicator. Hover over the row for a color-coded six-factor breakdown, including the common element shift and residual mismatch when available. The exact weighted formula and definitions are given in **What is what? → Signal identification → Reliability calculation**; the value is not a statistical probability.
- The assignment table is sorted by peak energy by default. Click **Peak**, **Type**, or **Reliability** to sort, and click the same heading again to reverse the direction.
- **Alternatives / reason** lists other considered candidates, or explains why the peak was left unassigned.

### Interpret complex surveys
For transition-metal oxides, the identifier evaluates broad 2p doublets as element-level families, using one common shift and the expected component separation. It also applies a cross-section-aware rule that suppresses an `s` label when the corresponding `p` family has no measured support. More generally, when two independent PE families already establish an element, PANDA can use that family evidence to look for another accessible core level that has a real measured local maximum near its expected energy. Yeh-Lindau cross sections provide only a broad relative-intensity plausibility check, not a required measured ratio. This can recover a strong line missed by the initial broad survey detector without allowing a single tentative assignment to generate extra labels. Broad Auger shading may coexist with PE lines or a different Auger family when their energy ranges physically overlap; for example, O KLL is not removed simply because it overlaps transition-metal 2p/LMM structure.


# Process and calibrate spectra
Prepare spectra before fitting and correct their energy scale from Fermi-edge or core-level references.


## Apply simple processing before fitting
Use **Processed Data** when the displayed spectra need simple treatment before calibration or fitting. Hover the vertical **Intensity** axis title for a hint and double-click it when you need to compare ordinary spectra in **Counts** or **CPS**. The Processed Data choice follows spectra into downstream plotting/fitting/calibration workflows, while MAP representations remain in counts.

Typical tasks include:

- choosing the displayed energy scale;
- applying basic intensity normalization;
- retaining signal-identification annotations while the displayed intensity is normalized;
- preparing spectra for calibration or fitting;
- checking whether processed curves still look physically reasonable.

For fitting, avoid over-processing unless you know why it is needed. Peak fitting normally needs the original spectral shape, a meaningful background model, and a reliable energy axis.

A safe beginner workflow is:

1. Inspect the curve in **Raw Data**.
2. Switch to **Processed Data**.
3. Set **Norm E:** at a stable reference region and choose a compact **E span:**. The default is 1% of the full spectrum range.
4. Enable normalization. Near either spectrum edge, the averaging interval shifts inward automatically.
5. Apply only the processing needed for your task.
6. Confirm that peak shapes and relative intensities are not distorted.
7. Then proceed to energy calibration or fitting. While normalization remains enabled, those workflows use the displayed normalized variants (labelled **(Norm)**) rather than the underlying unnormalized curves. Switching between raw and E-calibrated Processed views does not turn normalization off.

**Controls used (What is what?):** *Processed Data tab*, *Normalization*, *BE / KE*


## Inspect a sequence as a 2D map
Use the Processed Data **Map** view when several compatible spectra form a sequence and you want to inspect how spectral features change across it.

1. Check at least two compatible curves in the selected-curve tree and activate **Map**. Start with **View: Simple** for an unobstructed overview. If the file contains a physical second dimension, such as photon energy, temperature, or time, read it from the left Y axis; iteration remains on the right.
2. Choose **View: Lines** to inspect individual horizontal or vertical cuts. Drag either cursor on the 2D map, or drag its continued guide directly in the corresponding side trace; the trace updates immediately. Dragging close to the H/V intersection on the 2D map moves both cursors together. For dense sequences, increase **Bin size** above 1; complete consecutive groups are averaged exactly as in batch fitting, while an incomplete final group is discarded. **Bin size 1** is the unbinned default. Use **H thickness** and **V thickness** to average an odd number of map rows/columns symmetrically around the corresponding cursor (1, 3, 5, ..., 25); the strongly shaded, outlined bands on the map and their continuations onto the side traces show the effective averaging width. Use **Auto scale H** and **Auto scale V** independently in the lower-right corner; both are checked by default. Unchecking one fixes only that trace intensity axis to the displayed MAP dataset minimum/maximum. Use **Animation...** below it to sweep either H or V through the full valid range or a custom interval. H and V remember separate custom ranges when you switch between them. Physical key positions advance by exactly the selected line thickness, while intermediate line/band positions and traces are interpolated for smooth playback. Playback can be one-way or back-and-forth, once or looped, and the panel reports the current coordinate and frame number. **Speed** and **Loop** may be changed live without stopping playback; path-defining controls still rebuild the animation. The **Video** controls save a finite number of cycles as an MP4 at the selected frame rate. **Sequence** can export either the currently selected line or a combined **H then V** movie, using the separately configured H and V sweeps in that order. **Save video...** asks for a filename and then renders the complete Matplotlib Lines figure with progress/cancel feedback. Use **Plot H-trace** or **Plot V-trace** when a trace should be preserved for comparison; Lines traces are named from their cursor coordinate automatically. The H/V cursor positions are remembered when Lines is temporarily left or the map is redrawn, including palette and tab changes.
3. Choose **View: ROI** to inspect projections from a rectangular region. Move or resize it with the mouse or numerical centre/width controls. Use **Full width** or **Full height** when one dimension should cover the complete map; unpressing restores the previous extent. Use **Pass to plotting** to copy the spectra within the ROI Y range, truncated to its X range, into Plotted Data with an `[ROI]` suffix. Use **Plot H-trace** or **Plot V-trace** to preserve either current ROI projection. The right-hand trace uses Iteration by default; when a genuine physical second Y coordinate exists, double-click its Y axis or title to switch representation. The selector is unavailable for iteration-only maps.
4. If needed, choose **Normalize: At BE** or **Area**. Its settings dialog opens automatically. The normalization interval is shown on the map. In Simple, Lines, and ROI views it can be moved or resized directly with the mouse. Where it overlaps Lines/ROI controls, the active line cursor or ROI takes priority, while the rest of the normalization band remains draggable. Invalid settings revert to the previous valid interval rather than disabling normalization.
5. Added traces open in the shared **Trace comparison** window. Rename traces as needed, show or hide the legend, use the Matplotlib toolbar for normal plot interaction, and export one or several stored traces with **Export CSV**. Closing this window hides it without losing the comparison; main **Clear all** / **Close all** ends the comparison session.

**Controls used (What is what?):** *Map*, *View*, *Simple*, *Lines*, *ROI*, *Bin size*, *Auto scale H*, *Auto scale V*, *Animation...*, *Normalize*, *Full width*, *Full height*, *Plot H-trace*, *Plot V-trace*, *Trace comparison*

## Compare ResPES excitation profiles
For a 2D map whose physical second dimension is **Photon Energy**, use **ResPES analysis** in Simple view to compare non-dispersing and dispersing photoemission channels through the resonance.

1. Activate **MAP** and choose **View: Simple**. The **ResPES analysis** control appears only for photon-energy maps.
2. Open ResPES analysis. In **Map energy axis**, choose **Energy axis: BE** or **KE**. The source map may be measured on either scale; conversion uses `KE = hν - BE - Φ`. **Analyzer WF** defaults to 4.5 eV, is adjustable from 2.5 to 6.5 eV, and remains available for BE/KE conversion and cross-scale cuts. Typed WF changes are applied on Enter or focus change.
3. Choose **Constant BE** for a non-dispersing binding-energy feature, **Constant KE** for a fixed-kinetic-energy Auger-like feature, or **Constant PhE** to extract a spectrum at one excitation energy. Position the finite-width cut by dragging the band on the map or editing its position/width controls. Drag an edge to resize it. BE/KE cuts produce intensity versus photon energy; a photon-energy cut produces intensity versus the displayed BE or KE axis.
4. Press **Plot trace** when the current excitation profile should be kept. Move the cut to another feature, change cut type if needed, and add further traces in the same way.
5. Use the separate **Trace comparison** window to rename the stored profiles, compare them with an optional legend, navigate the graph with the standard Matplotlib toolbar, and export the stored traces to CSV.
6. Switching temporarily to Lines or ROI hides the ResPES controls and overlay but preserves the ResPES state. Return to Simple to continue from the same cut settings.

Stored ResPES traces are snapshots of the displayed, currently normalized map at the moment **Plot trace** is pressed. Later cut movement or normalization changes therefore do not modify profiles already stored in Trace comparison.

**Controls used (What is what?):** *ResPES analysis*, *Energy axis*, *Analyzer WF*, *Constant BE*, *Constant KE*, *Constant PhE*, *Plot trace*, *Trace comparison*, *Rename...*, *Export CSV*

## Compose and export curves in Plotted Data
Use this workflow after processing when several spectra should be arranged and prepared as one figure.

1. In **Processed Data**, select the curves to use and click **Pass to plotting**. Repeating this adds further curves without clearing those already present.
2. Open **Plotted Data** and use the checkboxes to choose which curves are visible.
3. Drag the handle or original curve name to set the desired curve and legend order.
4. Set color, line style, and line width or marker size for each curve. Use **Check all** / **Uncheck all** to change the visibility of the whole plotted set at once, or enable **Fixed width** to display every curve with one common width while preserving the individual widths.
5. Choose **Legend: Curve name**, **Custom (TeX)**, or **None**. In Custom (TeX) mode, click each legend title that needs renaming; use the **?** reference in the custom legend-name editor for common TeX-style subscript, superscript, and symbol syntax (Matplotlib commands are inserted with a single backslash); the original names remain fixed in the list for reference.
6. Optionally enable **Waterfall** and choose the offset. The offset slider automatically uses a finer percentage range as more curves are shown, and the numeric field can be used for exact fractional-percent offsets. Use the **Filling** slider (0% by default) to add progressively opaque background filling beneath each displaced spectrum when stronger foreground features should hide curves behind them. Optionally enable **Fixed color** (and choose a waterfall color) for dense sequences; you can also reverse the X axis, adjust the grid, move the legend, or add an annotation.
7. Use **Export / Import → Export CSV** to save the visible curves in their current order. Undefined Custom names produce a confirmation warning.

Use **Export / Import → Import CSV** to append previously exported curves or a conventional shared-energy-column CSV. **Clear plotted** starts a new composition without affecting loaded or processed data.

**Controls used (What is what?):** *Pass to plotting*, *Legend*, *Legend style...*, *Reverse X*, *Annotation...*, *Plotted curves list*, *Check all*, *Uncheck all*, *Waterfall*, *Offset*, *Filling*, *Fixed color*, *Fixed width*, *Grid*, *Export / Import*, *Clear plotted*


## Calibrate an energy scale
Use the energy-calibration workflow when the energy axis needs to be shifted or aligned.

A typical case is a Fermi edge or a known reference peak.

1. Select the calibration spectrum or spectra.
2. Open the energy-calibration workflow.
3. Use the **Map** tab if you need to inspect a sequence or many possible calibration targets.
4. Use the **Fit** tab to fit the reference feature.
5. Provide an expected Fermi level or target energy if available.
6. Inspect the fitted shifts.
7. Use the **Targets** tab to check which spectra will be corrected.
8. Apply the calibration only when the target list and shifts make sense. If E-calibrated curves already exist and you start calibration again, the program asks whether to **Redo** it; Redo removes the old E-calibrated derivatives and restarts calibration from defaults.

**Good practice:** do not blindly apply an energy shift to a whole sequence before inspecting whether the reference fit succeeded for all spectra.

**Controls used (What is what?):** *Energy calibration workflow*, *Map tab*, *Fit tab*, *Targets tab*


# Fit one spectrum
Develop and validate a robust peak/background model on one spectrum before using it on a sequence.


## Fit one core-level spectrum
Use **Fit core-level PE spectra** when you want to build or refine a model for one spectrum.

This is the best starting point before batch fitting.

1. Select one spectrum in the selected-curve tree.
2. Open **Fit core-level PE spectra**. For a fresh spectrum, the program proposes a conservative set of initial components from clearly resolved maxima; treat these only as starting guesses and add/remove/edit components as required by the physics.
3. Choose or create the background model.
4. Add, remove, or adjust the required peak components.
5. Set approximate starting values for peak position, height, width, and alpha.
6. If only part of the spectrum should be fitted, use **Fit range: Edit**. Enter Min/Max, use **Select on plot**, or drag the accepted range boundaries directly on the spectrum; **Full** restores the complete range.
7. The current model is calculated and displayed automatically. The colored component markers remain interactive: drag horizontally for Energy and vertically for Height. Energy/Height edits update the component curves, summed model, and residual live.
8. Check whether the preview is at least qualitatively close to the data.
9. Press **Start fit**. If the result is worse than the previous state, **Undo fit** restores the setup and result state from immediately before that fit attempt.
10. Inspect the fitted curve, components, background, and residual.
11. Check the result table and warnings. Use **Area** rather than Height when you need to compare fitted component intensities.

A good fit should normally have:

- a total fit following the measured spectrum;
- physically reasonable peak positions and widths;
- no important parameter stuck at a bound unless intended;
- residuals without clear peak-shaped structure.

**Controls used (What is what?):** *Fit core-level PE spectra*, *Fit range*, *Edit*, *Select on plot*, *Start fit*, *Undo fit*, *Peak parameters*, *Background models*, *Residual plot*


## Choose starting peak parameters
Starting parameters do not need to be perfect, but they must be reasonable enough for the optimizer to find the correct minimum. **Height** remains the editable intensity parameter because it is easy to estimate directly from the spectrum; **Area** is calculated from the fitted component afterwards.

For a first fit:

1. Place **Energy** near the visible peak maximum or shoulder. You can type the value or drag the corresponding colored vertical marker horizontally in the spectrum; the Energy spin box follows the marker live.
2. Set **Height** to a realistic peak amplitude.
3. Use moderate **LFWHM** and **GFWHM** values.
4. Start with **Alpha = 0** unless you deliberately need DS asymmetry.
5. Use bounds wide enough to allow fitting, but not so wide that the optimizer can find unphysical solutions.

From this point, linked peak models can be built in either of two ways. The general **Tied** mechanism can relate ordinary peak parameters directly, including a manually constrained spin-orbit pair. The separate **Create SO doublet...** workflow described below is an additional structured option that packages common spin-orbit relationships into dedicated controls. Both mechanisms remain available.

**Controls used (What is what?):** *Energy*, *Height*, *LFWHM*, *GFWHM*, *Alpha*, *Free / Fixed / Tied*


## Link ordinary peaks manually with Tied
The original peak-level **Tied** mechanism remains fully supported. It is a general tool for building relationships between ordinary peaks and is independent of the SO-doublet grouping feature.

1. Leave the components as ordinary `Pn` peaks.
2. Set reasonable starting values before creating the tie. The current values define the relationship that PANDA will preserve.
3. For the dependent peak, choose **Tied to Energy_N**, **Tied to Height_N**, **Tied to LFWHM_N**, **Tied to GFWHM_N**, or **Tied to Alpha_N** as required.
4. An Energy tie preserves the current energy **offset** to the target peak. Height, LFWHM, GFWHM, and Alpha ties preserve the current **multiplicative factor** to the corresponding target parameter.
5. Tie only the parameters for which the relationship is physically justified. Other parameters may remain Free or Fixed independently.
6. Fit normally. The tied relationships are enforced by the fit model.

This mechanism can be used to construct a spin-orbit-like pair manually, for example by tying the minor peak Energy to the major peak with a fixed offset and tying Height and selected shape parameters by fixed factors. It is equally useful for other linked-peak models that are not spin-orbit doublets. Because these peaks remain ordinary components, they continue to appear as individual peaks and are not combined by **Doublet view**.

**Controls used (What is what?):** *Free*, *Fixed*, *Tied*, *Tied to Energy_N*, *Tied to Height_N*, *Tied to LFWHM_N*, *Tied to GFWHM_N*, *Tied to Alpha_N*


## Build and fit SO doublets
PANDA starts from ordinary peak components and leaves the physical interpretation to the user. It does not automatically decide that two peaks form a spin-orbit doublet. **Create SO doublet...** is an additional structured way to manage a pair; it does not replace the manual peak-level **Tied** mechanism described above.

1. Place or adjust the two peak components that should form the pair.
2. Press **Create SO doublet...**.
3. Choose the **Major peak** and **Minor peak**. Enter a useful family label such as `S 2p` if desired; an empty label is allowed and produces `Doublet #1`, `Doublet #2`, and so on.
4. Choose `p`, `d`, `f`, or `Custom`. For `p`, `d`, and `f`, PANDA inserts the statistical major/minor height ratio only as an initial value.
5. Set the SO **Splitting**. Use **Fixed** for a known value, **Free** with min/max limits when some variation is justified, or **Tied to** when several similar doublets should share the same fitted splitting.
6. Set the major/minor **Ratio** in the same way. Ratio may be Fixed, Free within limits, or Tied to another doublet independently of Splitting.
7. Leave **LFWHM**, **GFWHM**, and **Alpha** at **Same** when both members should share those shape parameters, or switch an individual relation to **Independent** when the physics or data justify separate values.
8. Fit normally with **Start fit**. The doublet constraints are part of the actual fit model, not just display relationships.

A named family is numbered from its first member: `S 2p #1`, then `S 2p #2`, `S 2p #3`, and so on. The underlying peaks remain `P1`, `P2`, ... . Hover the bold doublet title to see which peaks are the major and minor members.

For repeated chemical states with a similar line shape, press **Clone** on an existing doublet. The clone inherits the current doublet shape and constraints but appears weaker and slightly energy-shifted so it can be seen and moved immediately. Reposition/rescale it with the existing mouse handles, then refit. Any clone can itself be cloned. Use **Ungroup** to return a doublet to two ordinary independent peaks.

Use **Doublet view** when several doublets make the component plot crowded. With it unchecked, major and minor curves are shown separately. With it checked, each pair is shown only as the summed doublet curve; standalone peaks remain individual and only the major marker is kept as the handle for shifting/rescaling the pair. Doublet view stays active during fitting.

For a major/minor branching-ratio constraint, remember that Ratio acts on **Height**. It represents the same ratio in **Area** only when the paired components use the same widths and line shape.

**Controls used (What is what?):** *Create SO doublet...*, *Major peak*, *Minor peak*, *Splitting*, *Ratio*, *Same / Independent*, *Clone*, *Ungroup*, *Doublet view*


## Use Fixed and Tied parameters safely
Parameter constraints are not just technical details. They define the physical assumptions of the fit.

Use **Fixed** when a parameter should not change during fitting. Examples:

- a known spin-orbit splitting;
- a known intensity ratio;
- an instrumental Gaussian width;
- DS alpha fixed to zero for symmetric peaks.

Use **Tied** on an ordinary peak when that peak parameter should maintain a defined relationship to the corresponding parameter of another ordinary peak. Energy ties preserve an offset; Height, LFWHM, GFWHM, and Alpha ties preserve a multiplicative factor.

The dedicated SO-doublet card has a separate **Tied to** choice for **Splitting** and **Ratio**. In that case the selected doublets share the same fitted splitting and/or the same fitted ratio while keeping their absolute energies and intensities independent. These doublet-level ties are an additional mechanism, not a replacement for ordinary peak ties.

Avoid unnecessary constraints at the beginning. A good workflow is:

1. Start with a physically sensible but not over-constrained model.
2. Fit one spectrum.
3. Inspect which parameters are unstable or highly correlated.
4. Add fixed/tied constraints where they represent real physical knowledge.
5. Refit and check whether the residual improves or at least remains acceptable.

**Controls used (What is what?):** *Free*, *Fixed*, *Tied*, *Tie / Link*, *Fit results table*


## Check whether a single fit is good enough
After pressing **Start fit**, do not look only at whether the fit “succeeded”. A mathematically successful fit can still be physically poor.

Check these items:

1. **Total fit vs data** - does the red/total fit follow the measured spectrum?
2. **Components** - do individual peaks sit in plausible places?
3. **Background** - does the background behave reasonably below the peak envelope?
4. **Residual** - is it mostly noise-like, or does it still contain peak-shaped features?
5. **Parameter values** - are positions, widths, and intensities physically reasonable?
6. **Bounds warnings** - did any parameter end up very close to a min/max bound?

If a parameter hits a bound, consider whether:

- the bound is too strict;
- the starting value is poor;
- the peak is not really present;
- the model has too many free parameters;
- the background model is absorbing peak intensity.

**Controls used (What is what?):** *Fit results table*, *Residual plot*, *Warnings*, *Parameter bounds*


## Save and reuse a fit configuration
Use fit-configuration save/load when you want to reuse the model itself rather than export final fitted curves.

- **Save config snapshot** stores the current setup temporarily in memory for the open fitting session.
- **Load config snapshot** restores that in-memory setup.
- **Save config to file...** writes the model to JSON so it can be reused later.
- **Load config from file...** restores a JSON setup and regenerates the calculated component/sum/background curves from the loaded parameters.

The saved configuration includes peaks, explicit SO-doublet definitions, parameter bounds and Free/Fixed/Tied choices, background settings, fit range, and related fit setup. It is therefore useful for transferring a tested model to another similar spectrum before making spectrum-specific adjustments.

This is different from **Save config + curves...**, which is a result export intended to preserve both the configuration and numerical fit curves after a successful fit.

**Controls used (What is what?):** *Save config snapshot*, *Load config snapshot*, *Save config to file...*, *Load config from file...*


## Export a single-curve fit
Once a single fit is satisfactory, use **Save > Save config + curves...**.

1. Run a successful single-curve fit.
2. Choose **Save > Save config + curves...**.
3. Choose an output folder.
4. Check the suggested base name.
5. Confirm which files will be created.
6. Export.

The export can create two files:

- `*_parameters.json` - full structured fit information, including model, parameters, constraints, bounds, metadata, and fit quality;
- `*_curves.csv` - numerical curves for external plotting and analysis.

The CSV is intended to be easy to open in Igor Pro, Origin, Excel, Python, MATLAB, and similar programs. It contains columns such as:

- energy;
- data;
- total fit;
- background;
- peaks sum;
- residual;
- individual peak components.

**Controls used (What is what?):** *Save > Save config + curves...*, *JSON parameters file*, *CSV curves file*



# Fit a sequence
Prepare, initialize, run, stop, and refine multi-pass fits in chronological order.


## Start a batch fit from a good single fit
Batch fitting works best when you first understand the single-spectrum model.

A recommended beginner workflow is:

1. Pick one representative spectrum.
2. Fit it in **Fit core-level PE spectra**.
3. Decide which peaks, background, constraints, and bounds make sense.
4. Then open **Batch fitting of core-level PE spectra** for the full sequence.
5. Use anchor spectra to define how starting values should evolve through the sequence.

Do not start batch fitting with a model you have never tested. If one spectrum cannot be fitted sensibly, a whole sequence will not be more reliable.

**Controls used (What is what?):** *Single curve fit workflow*, *Batch fitting of core-level PE spectra*, *Anchor spectra*


## Choose the peak-only or SO-doublet batch path
PANDA supports two preparation paths that lead to the same Run/Analyze workflow.

**Peak-only path**
- Use ordinary individual peaks in all fitted anchors.
- The familiar peak-oriented parameter table is used.
- Free/Fixed/Tied peak constraints work exactly as in single-spectrum fitting.

**SO-doublet path (with optional standalone peaks)**
- Create explicit SO doublets in one or more fitted anchors; ordinary standalone peaks may be present at the same time.
- PANDA switches to the doublet-aware batch table automatically. Splitting and Ratio are exposed as editable batch parameters.
- Derived rows are intentionally read-only: minor-component parameters controlled by the doublet are shown as greyed-out **Derived** entries and cannot be edited independently.
- Minor LFWHM/GFWHM/Alpha remain editable when their relationship is **Independent**.

In both paths, **labels are the primary component identity**. Give the same evolving chemical component the same peak or doublet label across Start/Middle/End, even if it shifts or changes intensity. A component may be absent from an anchor; PANDA uses the union of labelled components across the fitted anchors. For a repeated SO-doublet label, keep the same major/minor peak labels and Same/Independent shape relationships. Ordinary per-peak Free/Fixed/Tied relationships remain available alongside the SO-doublet relationships.

This distinction affects only how the parameter table is prepared. After validation, both paths use the same sequence-running, monitoring, multi-pass analysis, and export workflow.

**Controls used (What is what?):** *Create SO doublet...*, *Anchor spectra*, *Batch parameter table*, *Splitting*, *Ratio*, *Derived*


## Prepare a sequence for batch fitting
Use the **Prepare sequence fit** tab to make sure the selected spectra form a meaningful sequence.

1. Select the curves/iterations in the main window.
2. Open **Batch fitting of core-level PE spectra**.
3. Inspect the selected spectra tree on the left.
4. Confirm that the spectra are in the expected order.
5. Choose the **Bin size**. Leave it at 1 for no binning; values above 1 average consecutive spectra.
6. Use the sequence plot or map display to check the overall trend.
7. Select anchor spectra, typically **Start**, **Middle**, and **End**.
8. On the first **Fit anchor...** action, read the one-time component-identity reminder. Peak and doublet labels identify the same component across anchors. A component may be absent from some anchors; if the same labelled doublet is present in several anchors, keep its major/minor peak labels and Same/Independent shape relations consistent.

The purpose of this tab is not fitting yet. The purpose is to answer:

- Are these the spectra I really want to fit?
- Are they ordered correctly?
- Do I need binning to improve signal-to-noise?
- Which spectra are good anchors for defining starting values?

**Controls used (What is what?):** *Prepare sequence fit tab*, *Bin size*, *Map / sequence display*, *Anchor spectra*


## Use binning in batch fitting
Binning averages adjacent spectra before fitting.

Use binning when:

- individual spectra are noisy;
- the physical trend is slow compared with the acquisition step;
- you want a more stable batch fit and can sacrifice some sequence resolution.

Example:

- bin size 1: no binning;
- bin size 3: spectra 1-3 become one averaged spectrum, spectra 4-6 become the next, and so on.

If the number of spectra is not divisible by the bin size, the remainder at the end is discarded and reported.

Use binning carefully if the sequence changes very rapidly. A large bin size can smear out real changes.

**Controls used (What is what?):** *Binning*, *Bin size*, *Prepare sequence fit tab*


## Choose Start / Middle / End anchors
Anchor spectra define how the initial guesses are generated across a sequence.

A simple strategy is:

1. Use **Start** for the first representative spectrum.
2. Use **Middle** for a spectrum near the middle of the sequence.
3. Use **End** for the final representative spectrum.
4. Fit or define the model for each anchor. Component markers in the anchor fit work exactly as in the single-spectrum fit: drag horizontally for **Energy** and vertically for **Height**; the fields and calculated component/sum/residual update live.
5. Proceed to the batch setup table.

The batch initial guesses are then interpolated from the anchor values. This is useful when peaks grow, disappear, shift, or change width through the sequence.

For example:

- a disappearing component can have high height at Start and low height at End;
- an appearing component can have low height at Start and high height at End;
- a peak shift can be represented by different Start/Middle/End energies.

**Controls used (What is what?):** *Start*, *Middle*, *End*, *Initial strategy*, *Batch parameter table*


## Understand the batch parameter table
The batch parameter table is where the sequence fit becomes explicit. Review it before the first run; it is not merely a summary of the anchors.

Important columns include:

- **Start / Middle / End** - anchor values used to generate per-spectrum initial guesses;
- **Initial** - fallback or representative initial value;
- **Initial strategy** - how the starting value evolves through the sequence;
- **Min / Max** - bounds;
- **Mode** - Free, Fixed, or Tied;
- **Tie / Link** - relationship to another parameter;
- **Notes** - warnings or inherited constraint information.

For ordinary peaks, the independent values are editable. In the SO-doublet path, independent doublet parameters such as **Splitting** and **Ratio** are also editable, while parameters controlled by the doublet relationship appear as grey **Derived** rows. A derived row is intentionally read-only; edit its controlling major/doublet parameter instead.

The **Mode** should reflect the intended physical constraint. If a parameter was fixed or tied in the anchor setup, the batch table should inherit that logic. If anchor modes disagree, the table may fall back to Free and add a note.

A good first pass usually keeps uncertain independent parameters free unless there is a strong reason to fix them. Later constrained passes can then stabilize selected trends deliberately.

**Controls used (What is what?):** *Run sequence fit tab*, *Batch parameter table*, *Free / Fixed / Tied*, *Tie / Link*


## Run the first independent batch pass
The first batch pass fits every spectrum independently using the batch table and anchor-derived initial guesses.

1. Go to **Run sequence fit**.
2. Check the **Strategy** selector. For the first run it should be something like **Pass 1: independent**.
3. Inspect the batch parameter table.
4. Press **Run batch fit**.
5. Watch the monitor plot and progress bar.
6. Wait for the sequence to finish.
7. Check the status message for failures or warnings.

During fitting, the monitor shows:

- the current spectrum;
- total fit;
- peak components;
- residual;
- progress through the sequence.

The first pass is intentionally independent. This lets you see which parameters are stable and which ones scatter unphysically.

If you may need to inspect or export every fitted spectrum afterwards, check **Store all fit results** before pressing **Run batch fit**. After the pass finishes, use the left/right arrows below the monitor to step through the stored fits, or type a fit number to jump directly to it.

**Controls used (What is what?):** *Run sequence fit tab*, *Strategy*, *Store all fit results*, *Run batch fit*, *Monitor plot*, *Fit navigation*, *Progress bar*


## Stop a long batch fit safely
If a batch run is taking too long or something looks wrong, use **Stop**.

1. Press **Stop**.
2. The program finishes the current spectrum if needed.
3. The batch run stops before starting the next spectrum.
4. Completed results remain available in memory.

Use this if:

- the model is clearly wrong;
- many spectra are failing;
- the wrong strategy was selected;
- you want to change constraints before continuing.

**Controls used (What is what?):** *Stop*, *Run sequence fit tab*, *Pass status*


## Smooth a scattered parameter and prepare a constrained pass
Sometimes an **independent** fit parameter scatters because it is weakly determined in individual spectra. A common example is **GFWHM**.

The intended workflow is:

1. Run **Pass 1: independent**.
2. Open **Analyze fit results**.
3. Plot the unstable parameter, for example **P3 GFWHM**.
4. In the next-pass smoothing controls, select the independent target.
5. Fit a simple polynomial trend, often order 0 or 1 for widths.
6. Add/update the constraint.
7. Press **Prepare next pass**.
8. PANDA switches back to **Run sequence fit** and pre-selects the new strategy.
9. Press **Run batch fit** to run the constrained pass.

The constrained pass starts from the previous pass results, fixes the selected parameter to the polynomial-predicted value for each spectrum, and refits the remaining free parameters.

For SO doublets, **derived minor-member parameters are intentionally absent from the next-pass target list**. They remain plottable for diagnosis, but they cannot be constrained independently. For example, if a doublet major Energy is smoothed and fixed while the SO splitting is still allowed to vary, the minor Energy can retain a small amount of wobble. That is expected: the minor is derived from the fixed major plus the fitted splitting.

This smoothing workflow is different from **Trend analysis and export** on the right-hand side of Analyze: analytical trend fits there are descriptive only and never change a batch fit.

**Controls used (What is what?):** *Polynomial smoothing*, *Add/update constraint*, *Prepare next pass*, *Strategy*, *Run batch fit*


## Run Pass 2, Pass 3, and later constrained passes
Batch fitting can use multiple passes.

A typical sequence is:

1. **Pass 1: independent** - find the raw fitted trends.
2. **Pass 2: constrained** - fix one unstable trend, such as GFWHM.
3. **Pass 3: constrained** - optionally add another constraint, such as alpha or another width.

Prepared strategies appear in the **Strategy** selector on the **Run sequence fit** tab.

If the program prepares a new recommended strategy and you manually select another one, it may ask for confirmation before running. This prevents accidental reruns of the wrong pass.

**Good practice:** after every constrained pass, return to **Analyze fit results** and check whether the constraint improved the fit without creating new problems.

**Controls used (What is what?):** *Strategy*, *Pass status*, *Analyze fit results*, *Constrained pass*


# Analyze and export results
Inspect parameter trends, fit descriptive models, and export data for external plotting or reporting.


## Analyze fitted-parameter trends
After a batch pass, use **Analyze fit results**. Plotting is diagnostic and is broader than the next-pass constraint target list: derived SO-doublet minor trends may be displayed here even though they cannot be constrained independently.

1. Select the result pass, for example **Pass 1: independent**.
2. Choose a parameter family, for example **Peak area**, **Peak height**, **Gaussian FWHM**, or **Normalized RMS residual**.
3. Check the curves you want to show.
4. Inspect the trend plot.

Useful things to look for:

- peak areas increasing or decreasing;
- peak heights changing because of either intensity or width changes;
- peak positions shifting;
- widths scattering too much;
- alpha values becoming unstable;
- fit-quality diagnostics peaking at problematic spectra;
- parameters repeatedly hitting bounds.

For fit quality, **Normalized RMS residual** is usually more directly useful than raw fit evaluations. **Fit evaluations** mainly tells you how hard the optimizer had to work.

**Controls used (What is what?):** *Analyze fit results tab*, *Result pass*, *Y parameter*, *Normalized RMS residual*, *Fit evaluations*


## Fit analytical trend curves for analysis and export
The right-hand side of **Analyze fit results** contains **Trend analysis and export** tools. These are for describing plotted trends and exporting fitted trend curves. They do not affect batch-fit constraints.

A typical workflow is:

1. Plot one or more raw parameter trends.
2. In **Trend curve**, select one displayed curve.
3. Choose a trend model, for example:
   - **Polynomial**;
   - **Single exponential to plateau**;
   - **Stretched exponential to plateau**.
4. Press **Fit selected trend**.
5. Inspect the fitted curve and the normalized RMSE.
6. Try another model if needed.
7. When satisfied, press **Accept/store fit for export**.
8. Move to the next trend curve and repeat.
9. Press **Export CSV**.

Only accepted/stored analytical trend fits are exported together with the raw trends.

Use this when you want to describe how a fitted parameter changes through a sequence, for example peak height approaching a plateau or a width following a smooth trend.

**Controls used (What is what?):** *Trend analysis and export*, *Trend curve*, *Model*, *Fit selected trend*, *Accept/store fit for export*, *Export CSV*


## Export batch trend data
Use **Export CSV** in **Analyze fit results** when you want the plotted trends in an external program.

The export contains:

- spectrum number;
- the raw trend curves currently shown on the plot;
- accepted analytical fitted trend curves, if any.

The CSV metadata header can include:

- package version;
- selected result pass;
- parameter family;
- binning information;
- pass history;
- analytical trend models and fitted parameters.

A suggested filename is generated from the parameter family, original data file, and region, for example:

`Peak_height_trends_for_XPS0108_S2p.csv`

**Controls used (What is what?):** *Export CSV*, *Analyze fit results*, *Trend analysis and export*


## Use exported files in Igor Pro or another plotter
For simple plotting and further analysis, use CSV exports.

Single-curve fit export:

- use `*_curves.csv` for energy, data, total fit, background, residual, and components;
- use `*_parameters.json` when you need the complete fit metadata and constraints.

Batch trend export:

- use the trend CSV for parameter values versus spectrum number;
- use fitted trend columns if you accepted analytical trend fits before export.

Full batch-fit export:

- run the pass with **Store all fit results** enabled;
- in **Analyze fit results**, select that result pass and press **Export all fits...**;
- the resulting ZIP contains `batch_manifest.csv` plus one CSV per spectrum with energy, data, total fit, background, peak sum, residual, and individual peak components.

The CSV column names are intentionally simple so that external programs can import them as waves or columns.

**Controls used (What is what?):** *Export fit results*, *Export CSV*, *CSV curves file*, *JSON parameters file*


# Troubleshooting and fitting workflow
Use these pages when a fit is unstable or when you want one conservative end-to-end fitting checklist.


## Troubleshooting: the fit fails or gives strange parameters
If a fit fails or produces unphysical values, try this checklist.

1. Check the energy scale and axis direction.
2. Check whether the background model is appropriate.
3. Check starting peak positions and heights.
4. Narrow unreasonable bounds, but do not make them so narrow that the fit is forced to a wrong answer.
5. Fix or tie parameters that are known physically.
6. Remove unnecessary weak components.
7. Fit a simpler model first, then add complexity.
8. Inspect the residual instead of only the success message.

For batch fitting, first debug the model in the single-curve fit window. A batch fit is not a magic correction for a poor single-spectrum model.

**Controls used (What is what?):** *Start fit*, *Fit results table*, *Bounds*, *Residual plot*, *Single curve fit workflow*


## Troubleshooting: batch results scatter too much
If fitted parameters jump from spectrum to spectrum:

1. Plot the parameter in **Analyze fit results**.
2. Check whether the scatter is real or likely a fitting artifact.
3. Look at fit-quality diagnostics for the same spectra.
4. Check whether the parameter is weakly determined or correlated with another one.
5. Consider fixing/tieing it physically in a new constrained pass.
6. Use polynomial smoothing for next-pass constraints only when the smooth trend is physically justified.
7. Rerun the constrained pass and compare results.

Common candidates for stabilization are:

- GFWHM;
- LFWHM;
- Alpha;
- weak component heights;
- poorly determined background parameters.

Do not over-constrain too early. The first independent pass is useful exactly because it shows where the model is unstable.

**Controls used (What is what?):** *Analyze fit results*, *Polynomial smoothing*, *Prepare next pass*, *Constrained pass*


## A safe complete fitting workflow for new users
If you are unsure how to approach fitting a spectrum or sequence, use this conservative workflow:

1. Load the file.
2. Select one region and inspect it in **Raw Data**.
3. Check the energy scale and axis direction.
4. If needed, calibrate the energy scale.
5. Select one representative spectrum.
6. Build a single-curve fit model.
7. Fit it and inspect components, background, residual, and warnings.
8. Export the single-curve fit if it is important as a reference.
9. Open batch fitting for the full sequence.
10. Prepare the sequence and decide on binning.
11. Choose the peak-only path or build explicit SO doublets (optionally mixed with standalone peaks); keep component labels consistent across anchors.
12. Fit Start/Middle/End anchors.
13. Inspect the batch parameter table, including any grey Derived SO-doublet rows.
14. If you want to review or export every spectrum fit later, enable **Store all fit results**.
15. Run **Pass 1: independent**.
16. If full results were stored, step through the completed fits with the navigation controls below the monitor.
17. Analyze parameter trends.
18. If needed, prepare constrained Pass 2 using only independent targets; derived SO-doublet minor parameters remain diagnostic-only.
19. Compare Pass 1 and Pass 2 trends and fit-quality diagnostics.
20. Fit analytical trend curves only for reporting/export, not for constraints.
21. Export trend data as CSV, and use **Export all fits...** when the complete stored fit curves are needed.

This workflow is longer than what experienced users will need, but it reduces the risk of fitting many spectra with an untested model.

**Controls used (What is what?):** *Load*, *Raw Data*, *Energy calibration*, *Single curve fit*, *Batch fitting*, *Analyze fit results*, *Export fit results*, *Export CSV*

