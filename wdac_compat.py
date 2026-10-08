"""
wdac_compat.py — Windows Application Control (WDAC / Smart App Control) Compatibility Shim
==========================================================================================
Provides pure-Python implementations of `pandas._libs.indexing` and `pandas._libs.reshape`
when Windows Application Control policies block those two Cython `.pyd` extensions.
"""

from __future__ import annotations

import sys
import types
import numpy as np


class NDFrameIndexerBase:
    """Pure-Python equivalent of pandas._libs.indexing.NDFrameIndexerBase."""

    def __init__(self, name: str, obj) -> None:
        self.name = name
        self.obj = obj

    @property
    def ndim(self) -> int:
        return self.obj.ndim


def unstack(
    values: np.ndarray,
    mask: np.ndarray,
    stride: int,
    length: int,
    width: int,
    new_values: np.ndarray,
    new_mask: np.ndarray,
) -> None:
    """Pure-Python/NumPy equivalent of pandas._libs.reshape.unstack."""
    n = len(mask)
    for i in range(n):
        if mask[i]:
            row = i // stride
            col = i % stride
            for j in range(width):
                new_values[row, j * stride + col] = values[i, j]
                new_mask[row, j * stride + col] = 1


def explode(values: np.ndarray):
    """Pure-Python/NumPy equivalent of pandas._libs.reshape.explode."""
    out = []
    counts = np.empty(len(values), dtype=np.int64)
    for i, val in enumerate(values):
        if isinstance(val, (list, tuple, set, np.ndarray)) and len(val) > 0:
            out.extend(val)
            counts[i] = len(val)
        elif isinstance(val, (list, tuple, set, np.ndarray)) and len(val) == 0:
            out.append(np.nan)
            counts[i] = 1
        else:
            out.append(val)
            counts[i] = 1
    return np.array(out, dtype=object), counts


def apply_pandas_wdac_shim() -> None:
    """Pre-register pure-Python shims for `pandas._libs.indexing` and
    `pandas._libs.reshape` in `sys.modules` if their `.pyd` binaries are blocked
    by Windows Smart App Control / WDAC.
    """
    for mod_name, attrs in (
        ("pandas._libs.indexing", {"NDFrameIndexerBase": NDFrameIndexerBase}),
        ("pandas._libs.reshape", {"unstack": unstack, "explode": explode}),
    ):
        if mod_name not in sys.modules:
            try:
                __import__(mod_name)
            except ImportError:
                shim = types.ModuleType(mod_name)
                for k, v in attrs.items():
                    setattr(shim, k, v)
                sys.modules[mod_name] = shim


# Auto-apply on import
apply_pandas_wdac_shim()
