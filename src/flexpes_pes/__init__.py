"""Compatibility namespace for PANDA releases prior to 0.10.92.

New code should import :mod:`maxiv_panda`.  This shim keeps historical
``flexpes_pes`` imports working while the project transitions to the new
namespace.
"""
from __future__ import annotations

from pathlib import Path

import maxiv_panda as _panda

__version__ = _panda.__version__
__date__ = _panda.__date__

# Allow legacy submodule imports (for example ``flexpes_pes.file_naming``) to
# resolve against the real maxiv_panda source tree without duplicating it.
__path__ = [str(Path(_panda.__file__).resolve().parent)]


def __getattr__(name: str):
    return getattr(_panda, name)
