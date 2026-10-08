"""
preprocess.py — MUNKANIPPU: Compatibility Wrapper for feature_engineering.py
============================================================================
MUNKANIPPU — AI-Enabled Wireless Surface Mesh Network for Real-Time Mine Subsidence Detection

Re-exports all preprocessing and delta feature engineering functions from
`feature_engineering.py`.

Project : MUNKANIPPU
Date    : 2026-10-04
"""

from feature_engineering import (
    DGMS_THRESHOLDS,
    ALPHA_THERMAL,
    load_building_health,
    load_bim_civil,
    load_temperature,
    load_wsn,
    build_mesh_grid,
    compute_displacement_from_strain,
    compute_tilt_from_accel,
    thermal_drift_compensation,
    compute_vibration_rms,
    engineer_features,
    run_preprocessing,
    run_feature_engineering,
)

__all__ = [
    "DGMS_THRESHOLDS",
    "ALPHA_THERMAL",
    "load_building_health",
    "load_bim_civil",
    "load_temperature",
    "load_wsn",
    "build_mesh_grid",
    "compute_displacement_from_strain",
    "compute_tilt_from_accel",
    "thermal_drift_compensation",
    "compute_vibration_rms",
    "engineer_features",
    "run_preprocessing",
    "run_feature_engineering",
]

if __name__ == "__main__":
    df, mesh = run_preprocessing()
    print(df.head())

