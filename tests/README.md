# Test suite

The initial suite uses only synthetic spectra and temporary files. No experimental data are required.

## Install test dependencies

From the project directory, with the intended conda environment activated:

```bash
python -m pip install -e ".[test]"
```

The normal application dependencies may instead be installed through conda first, followed by:

```bash
python -m pip install pytest pytest-cov
python -m pip install -e .
```

## Run all tests

```bash
python -m pytest
```

Useful variants:

```bash
python -m pytest -q
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest --cov=maxiv_panda --cov-report=term-missing
```

The `tests/gui` directory is reserved for later PyQt tests. GUI tests will require a graphical environment or the Qt offscreen platform.

## Experimental reference datasets

Small anonymized regression spectra live under `tests/data/reference/`. Each dataset has a stable folder name plus `metadata.json` and `expected.json`. The reference datasets include `oxide_mixture_survey_700ev`, which checks charging-assisted Ti identification, and `graphene_ir_survey_750ev`, which verifies that charging assistance remains inactive when a valid unshifted Ir anchor is already present. The `carbon_au_survey_1000ev` dataset checks that both resolved Au 4f components are placed on their own measured maxima, even on a coarse survey grid.


## Current suite

Version 0.7.73 contains 28 tests, including a GUI-path regression that verifies the charging checkbox changes Ti identification on the oxide-mixture survey.

Version 0.7.74 adds regression coverage for charging-assisted Auger identification. A PE-derived element shift must move the corresponding Auger-family region toward higher apparent binding energy and broaden its allowance; checkbox OFF must retain the original region.

## Experimental single-spectrum fit reference

`tests/data/reference/peak_fitting/ir111_ir4f_clean_170ev/` contains a clean-Ir(111) Ir 4f spectrum and a final four-component fit setup. The integration tests verify IBW import, setup/constraint restoration, convergence, peak positions, spin-orbit and surface-shift relations, and fit quality.
