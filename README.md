# PANDA

**PANDA — Photoemission Analysis, Normalization and Data Assessment**

PANDA is a Python software package with an interactive graphical interface for loading, visualization, processing, analysis, and fitting of photoelectron spectroscopy (PES/XPS) data. It was developed at the FlexPES beamline at MAX IV Laboratory.

## Main capabilities

- Load and inspect Scienta/SES TXT, Igor Binary Wave (IBW), and SPECS/SpecsLab Prodigy XY data.
- Work with individual spectra, repeated acquisitions, and two-dimensional spectral maps.
- Calibrate energy scales and normalize intensities while retaining source provenance.
- Inspect maps in Simple, Lines, and ROI views, including physical second axes when available.
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

All supported formats enter the same PANDA Raw Data workflow after loading.

## Installation

A dedicated **conda environment** is recommended. PANDA 0.12 targets **Python 3.14** and **PyQt6**.

Create the environment once. The command below installs the important Qt/scientific dependencies explicitly from **conda-forge**:

```bash
conda create -n pes_processor -c conda-forge --strict-channel-priority python=3.14 pyqt6 matplotlib numpy scipy igor2 lmfit h5py pip
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
4. Download the file ending in **`.whl`**.
5. Open a terminal in the folder containing the downloaded wheel and install it:

```bash
pip install --no-deps maxiv_panda-*.whl
```

### From the source folder

Open a terminal in the `maxiv-panda` folder and run:

```bash
pip install . --no-deps
```

### Development installation

If you are modifying the source code, install it in editable mode instead:

```bash
pip install -e . --no-deps
```

> Use the conda-forge package **`pyqt6`**, not `pyqt` (which installs PyQt5). Keeping Qt and the scientific dependencies under conda and using `--no-deps` for PANDA avoids mixed pip/conda Qt installations.

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

The built-in **Help** menu contains detailed descriptions of controls, workflows, and release highlights.

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
