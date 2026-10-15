# PANDA

**PANDA — Photoemission Analysis, Normalization and Data Assessment**

PANDA is a Python software package with an interactive graphical interface for loading, visualization, processing, analysis, and fitting of photoelectron spectroscopy (PES/XPS) data. It was developed at the FlexPES beamline at MAX IV Laboratory.

## Main capabilities

- Load and inspect Scienta/SES TXT, Igor Binary Wave (IBW), and SPECS/SpecsLab Prodigy XY data.
- Work with individual spectra, repeated acquisitions, and two-dimensional spectral maps.
- Calibrate energy scales and normalize intensities while retaining source provenance.
- Inspect maps in Simple, Lines, and ROI views, including physical second axes when available.
- Analyze photon-energy maps with BE/KE interval normalization, photon-energy reference normalization, ResPES cuts, and reference-spectrum subtraction.
- Export processed 2D maps as ASCII matrices or Igor Binary Wave files, and import those map formats.
- Identify likely photoemission signals using built-in reference data.
- Fit individual spectra using configurable peak/background models.
- Prepare and run sequence/batch fits across related spectra, including spin-orbit doublets.
- Send processed data to publication-oriented plotting workflows.
- Monitor growing TXT/IBW acquisitions with the Live Monitor.
- Browse built-in binding-energy and photoionization cross-section references.

## Supported data formats

| Format | Typical source | PANDA handling |
| --- | --- | --- |
| **TXT** | Scienta/SES text exports | Single spectra, repeated regions, metadata, Live Monitor |
| **IBW** | Igor Binary Wave | 1D/2D data, metadata, Live Monitor |
| **XY** | SPECS/SpecsLab Prodigy | Single and repeated spectra, Prodigy metadata, large lazy iteration trees, physical second axes when available |

All supported acquisition formats enter the same PANDA Raw Data workflow after loading. For 2D maps, **Export / Import** beside **Normalize** exchanges processed numerical maps as a general ASCII matrix or Igor IBW. The ASCII matrix is not a Scienta acquisition-format TXT file.

## Installation

A dedicated **conda environment** is recommended. PANDA 0.12 targets **Python 3.14** and **PyQt6**.

Create the environment once. The command below installs the important Qt/scientific dependencies explicitly from **conda-forge**:

```bash
conda create -n pes_processor -c conda-forge --strict-channel-priority python=3.14 pyqt6 pyqt6-webengine markdown matplotlib numpy scipy igor2 lmfit h5py pip
```

Activate the environment:

```bash
conda activate pes_processor
```

Then choose **one** installation method.

### From a GitHub release wheel (recommended for most users)

1. Open the PANDA repository on GitHub.
2. Open **Releases** and choose the **Latest** release.
3. Scroll to the **bottom of the release page** and expand **Assets** if necessary.
4. Download the file ending in **`.whl`**. The filename shown below is for version 0.12.5; use the wheel name of the version you downloaded.
5. Open a terminal in the folder containing the downloaded wheel and install it:

```bash
python -m pip install --upgrade maxiv_panda-0.12.5-py3-none-any.whl
```

### Install or upgrade directly from GitHub

To install the latest published PANDA release directly from GitHub, including any new dependencies, run:

```bash
python -m pip install --upgrade "maxiv-panda @ git+https://github.com/alexeip100/maxiv-panda.git@v0.12.5"
```

The GitHub release tag must exist before this command can be used. Both a fresh installation and an upgrade resolve PANDA's required **`PyQt6-WebEngine`** and **`markdown`** packages automatically. Do **not** use `--no-deps` when you want pip to install newly required dependencies.

### From the source folder

Open a terminal in the `maxiv-panda` folder and run:

```bash
python -m pip install --upgrade .
```

### Development installation

If you are modifying the source code, install it in editable mode instead:

```bash
python -m pip install --upgrade -e .
```

> Use conda-forge packages **`pyqt6`** and **`pyqt6-webengine`**, not `pyqt` (which installs PyQt5). PANDA declares WebEngine and Markdown as required dependencies, so an ordinary `pip install` (without `--no-deps`) installs missing Help dependencies automatically. The conda command above installs these first to avoid unnecessary pip/conda Qt mixing.

## Starting PANDA

After installation, start the application with:

```bash
panda
```

The equivalent long launcher is:

```bash
maxiv-panda
```

PANDA can also be launched as a Python module:

```bash
python -m maxiv_panda
```

## Quick start

1. Start PANDA.
2. **Drag and drop** a supported TXT, IBW, or XY file onto the **Loaded files** tree. This is the quickest way to load data.
3. Alternatively, use **File → Load data...** and choose the corresponding file format.
4. Select spectra or an **Average** / **Iterations** group in the Loaded files tree.
5. Use the Raw, Processed, Plotted, fitting, and reference tools as needed.

The built-in **Help** menu contains detailed descriptions of controls, workflows, and release highlights. Its document viewer uses locally bundled MathJax for offline mathematical typesetting; it requires PyQt6-WebEngine, installed by the recommended environment command or ordinary pip dependency resolution.

## Testing

The repository includes a pytest regression suite under `tests/`, using synthetic data and small anonymized reference spectra. Run it with:

```bash
python -m pytest
```

See `tests/README.md` for focused test commands and coverage information.

## Citation

A `CITATION.cff` file is included so GitHub and citation tools can generate a software citation for PANDA. A DOI may be added to the citation metadata in a future release.

## Author

**Created by:** Alexei Preobrajenski (MAX IV Laboratory)

## License

**License:** MIT

Copyright (c) 2026 Alexei Preobrajenski, MAX IV Laboratory. See [LICENSE](LICENSE).
