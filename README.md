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

A dedicated **conda environment** is recommended for PANDA. The following setup uses Python 3.14.

Create and activate the environment:

```bash
conda create -n pes_processor python=3.14
conda activate pes_processor
```

Install the main scientific and graphical dependencies with conda:

```bash
conda install -y PyQt6 matplotlib numpy scipy igor2 lmfit h5py
```

Download the PANDA wheel (`.whl`) from the GitHub release and install it with pip without replacing the packages already installed by conda:

```bash
python -m pip install --no-deps "<path-to-file>\maxiv_panda-0.12.0-py3-none-any.whl"
```

### Development installation

If you are working from a cloned or downloaded source tree, activate the same environment, open a terminal in the PANDA project directory, and install PANDA in editable mode:

```bash
conda activate pes_processor
python -m pip install --no-deps -e .
```

### Updating PANDA

To update PANDA later in the same environment, download the newer release and run:

```bash
conda activate pes_processor
python -m pip install --no-deps --upgrade "<path-to-new-release>"
```

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
3. Alternatively, use **Load** and choose the corresponding file format.
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
