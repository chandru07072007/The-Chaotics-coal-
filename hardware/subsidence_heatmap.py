"""
subsidence_heatmap.py — Real-Time Spatial Heatmap & Colormap Pipeline
=====================================================================
Synchronizes:
  1. Official MUNKANIPPU Colormaps:
     - Current Deformation (YlOrRd / Ember Glow)
     - Predicted 24h Subsidence (RdBu_r / Seismic Convergence)
     - DGMS Risk Zones:
         0: Safe      (#2ecc71 / #10b981)
         1: Advisory  (#f1c40f / #facc15)
         2: Warning   (#e67e22 / #f97316)
         3: Critical  (#e74c3c / #ef4444)
  2. Live synchronization callback feeding the Python 3D Digital Twin Simulation.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

# Official DGMS Subsidence Colors
DGMS_COLORS = {
    0: "#10b981",  # Safe (<10mm)
    1: "#facc15",  # Advisory (10-25mm)
    2: "#f97316",  # Warning (25-50mm)
    3: "#ef4444",  # Critical (>=50mm)
}

# Heatmap Colormap definitions (Hex arrays for 3D continuous mapping)
HEATMAP_COLORMAPS = {
    "deformation": [
        "#ffffd4", "#fee391", "#fec44f", "#fe9929", "#ec7014", "#cc4c02", "#8c2d04"
    ],
    "prediction": [
        "#2166ac", "#4393c3", "#92c5de", "#d1e5f0", "#f7f7f7", "#fddbc7", "#f4a582", "#d6604d", "#b2182b", "#67001f"
    ],
    "risk_zones": [
        "#10b981", "#facc15", "#f97316", "#ef4444"
    ]
}


def get_heatmap_color(value: float, min_val: float = 0.0, max_val: float = 50.0, mode: str = "deformation") -> str:
    """Calculates continuous hex color for any 3D node based on active colormap."""
    palette = HEATMAP_COLORMAPS.get(mode, HEATMAP_COLORMAPS["deformation"])
    clamped = max(min_val, min(max_val, value))
    ratio = (clamped - min_val) / (max_val - min_val) if max_val > min_val else 0.0
    idx = int(ratio * (len(palette) - 1))
    return palette[idx]


def evaluate_dgms_risk(disp_mm: float) -> Tuple[int, str, str]:
    """Evaluates statutory DGMS Risk Tier, Label, and Color."""
    abs_disp = abs(disp_mm)
    if abs_disp >= 50.0:
        return 3, "CRITICAL", DGMS_COLORS[3]
    elif abs_disp >= 25.0:
        return 2, "WARNING", DGMS_COLORS[2]
    elif abs_disp >= 10.0:
        return 1, "ADVISORY", DGMS_COLORS[1]
    else:
        return 0, "SAFE", DGMS_COLORS[0]
