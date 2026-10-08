"""
feature_engineering.py — MUNKANIPPU: Data Processing & Delta Feature Engineering
================================================================================
MUNKANIPPU — AI-Enabled Wireless Surface Mesh Network for Real-Time Mine Subsidence Detection

Refactored Architecture:
  • Maps distributed sensor telemetry to a 10×10 spatial WSN mesh grid
  • Applies thermal expansion drift compensation:
      Disp_corr = Disp_raw - α * (T_current - T_baseline)
  • Models physically continuous ground deformation with temporal momentum
    and autoregressive lag structure per MeshNode_ID
  • Computes temporal lag features & rolling window statistics per node:
      Disp_Lag_1h, Disp_Lag_2h, Disp_Lag_3h,
      Delta_Lag_1h, Delta_Lag_2h, Delta_Lag_3h,
      Rolling_Mean_Delta_3h, Rolling_Std_Delta_3h,
      Rolling_Mean_Vel_6h, Rolling_Mean_Vib_6h
  • Computes inter-node spatial surface strain gradient (Δd_ij / L_ij)
  • Refactored Regression Targets (Incremental Delta, grouped by MeshNode_ID):
      df['Delta_Disp_1h'] = df.groupby('MeshNode_ID')['Displacement_mm'].shift(-1) - df['Displacement_mm']
      df['Delta_Disp_6h'] = df.groupby('MeshNode_ID')['Displacement_mm'].shift(-6) - df['Displacement_mm']

Project : MUNKANIPPU
Date    : 2026-10-04
"""

from __future__ import annotations

import os
import warnings
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from typing import Tuple

warnings.filterwarnings("ignore", category=FutureWarning)

# ─── DGMS Safety Thresholds (Directorate General of Mines Safety, India) ─────
DGMS_THRESHOLDS = {
    "safe_displacement_mm": 10.0,
    "advisory_displacement_mm": 25.0,
    "warning_displacement_mm": 40.0,
    "critical_displacement_mm": 50.0,
    "critical_tilt_mm_per_m": 5.0,
}

# Thermal expansion coefficient (mm/°C) — typical for surface soil/concrete
ALPHA_THERMAL = 0.012


# ═══════════════════════════════════════════════════════════════════════════════
#  1. DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_building_health(path: str) -> pd.DataFrame:
    """Load building health monitoring telemetry."""
    df = pd.read_csv(path, parse_dates=["Timestamp"])
    df.sort_values("Timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_bim_civil(path: str) -> pd.DataFrame:
    """Load BIM / AI civil engineering structural dataset."""
    df = pd.read_csv(path)
    for col in ("Start_Date", "End_Date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def load_temperature(path: str) -> pd.DataFrame:
    """Load Indian annual/seasonal mean temperature dataset."""
    df = pd.read_csv(path)
    for col in ["ANNUAL", "JAN-FEB", "MAR-MAY", "JUN-SEP", "OCT-DEC"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(subset=["YEAR"], inplace=True)
    df["YEAR"] = df["YEAR"].astype(int)
    return df


def load_wsn(path: str, n_nodes: int = 100) -> pd.DataFrame:
    """Load Wireless Sensor Network dataset."""
    df = pd.read_csv(path, parse_dates=["Timestamp"])
    unique_ids = df["Node_ID"].unique()[:n_nodes]
    df = df[df["Node_ID"].isin(unique_ids)].copy()
    df.sort_values(["Node_ID", "Timestamp"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  2. MESH NODE SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

def build_mesh_grid(wsn_df: pd.DataFrame, grid_size: int = 10) -> pd.DataFrame:
    """Create a regular grid_size × grid_size mesh and map WSN nodes to it."""
    xs = np.linspace(5, 95, grid_size)
    ys = np.linspace(5, 95, grid_size)
    grid_xx, grid_yy = np.meshgrid(xs, ys)
    grid_points = np.column_stack([grid_xx.ravel(), grid_yy.ravel()])

    node_pos = (
        wsn_df.groupby("Node_ID")[["X_Coordinate", "Y_Coordinate"]]
        .first()
        .reset_index()
    )

    tree = cKDTree(node_pos[["X_Coordinate", "Y_Coordinate"]].values)
    _, indices = tree.query(grid_points)

    mesh = pd.DataFrame({
        "MeshNode_ID": np.arange(1, grid_size * grid_size + 1),
        "Grid_X": grid_points[:, 0],
        "Grid_Y": grid_points[:, 1],
        "WSN_Node_ID": node_pos.iloc[indices]["Node_ID"].values,
        "Original_X": node_pos.iloc[indices]["X_Coordinate"].values,
        "Original_Y": node_pos.iloc[indices]["Y_Coordinate"].values,
    })

    latest_wsn = (
        wsn_df.sort_values("Timestamp")
        .groupby("Node_ID")
        .last()
        .reset_index()
    )
    merge_cols = [
        "Node_ID", "Signal_Strength", "Packet_Loss_Rate",
        "Residual_Energy", "Temperature",
    ]
    available = [c for c in merge_cols if c in latest_wsn.columns]
    mesh = mesh.merge(
        latest_wsn[available],
        left_on="WSN_Node_ID",
        right_on="Node_ID",
        how="left",
    )
    if "Node_ID" in mesh.columns:
        mesh.drop(columns=["Node_ID"], inplace=True)

    return mesh


# ═══════════════════════════════════════════════════════════════════════════════
#  3. PHYSICAL SIGNAL & FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════════

def _impute_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Handle missing values: forward-fill then median imputation."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].ffill()
    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
    return df


def compute_displacement_from_strain(strain_microstrain: pd.Series,
                                     gauge_length_mm: float = 100.0) -> pd.Series:
    """Convert micro-strain readings to instantaneous strain displacement (mm)."""
    return strain_microstrain * 1e-6 * gauge_length_mm


def compute_tilt_from_accel(accel_x: pd.Series, accel_z: pd.Series) -> pd.Series:
    """Derive tilt angle (degrees) from accelerometer X and Z axes."""
    return np.degrees(np.arctan2(accel_x.abs(), accel_z.abs()))


def thermal_drift_compensation(displacement_raw: pd.Series,
                               temp_current: pd.Series,
                               temp_baseline: float,
                               alpha: float = ALPHA_THERMAL) -> pd.Series:
    """Remove thermal expansion artefact from displacement readings."""
    return displacement_raw - alpha * (temp_current - temp_baseline)


def compute_vibration_rms(accel_x: pd.Series,
                          accel_y: pd.Series,
                          accel_z: pd.Series) -> pd.Series:
    """Compute resultant RMS vibration from 3-axis accelerometer."""
    return np.sqrt(accel_x ** 2 + accel_y ** 2 + accel_z ** 2)


def engineer_features(building_df: pd.DataFrame,
                      bim_df: pd.DataFrame,
                      temp_df: pd.DataFrame,
                      mesh_df: pd.DataFrame,
                      grid_size: int = 10) -> pd.DataFrame:
    """Build the full spatio-temporal feature matrix with continuous subsidence
    evolution, temporal lag features, rolling window statistics, and
    delta regression targets (`Delta_Disp_1h`, `Delta_Disp_6h`).
    """
    n_time = len(building_df)
    baseline_temp = float(temp_df["ANNUAL"].mean())

    bld = building_df.copy()
    bld = _impute_missing(bld)

    # Smooth sensor signals with a short causal rolling filter to remove high-freq jitter
    strain_smooth = bld["Strain (με)"].rolling(window=5, min_periods=1).mean()
    ax_smooth = bld["Accel_X (m/s^2)"].rolling(window=5, min_periods=1).mean()
    ay_smooth = bld["Accel_Y (m/s^2)"].rolling(window=5, min_periods=1).mean()
    az_smooth = bld["Accel_Z (m/s^2)"].rolling(window=5, min_periods=1).mean()
    temp_smooth = bld["Temp (°C)"].rolling(window=5, min_periods=1).mean()

    bld["Displacement_raw_mm"] = compute_displacement_from_strain(strain_smooth)
    bld["Tilt_deg"] = compute_tilt_from_accel(ax_smooth, az_smooth)
    bld["Vibration_RMS"] = compute_vibration_rms(ax_smooth, ay_smooth, az_smooth)
    bld["Displacement_corr_mm"] = thermal_drift_compensation(
        bld["Displacement_raw_mm"], temp_smooth, baseline_temp
    )

    # Subsample to 500 hourly-equivalent steps for the mesh simulation
    step = max(1, n_time // 500)
    bld_sampled = bld.iloc[::step].reset_index(drop=True)
    n_t = len(bld_sampled)

    # Generate hourly timestamps so 1 step = 1 hour (t+1h = shift(-1), t+6h = shift(-6))
    base_ts = pd.to_datetime(bld_sampled["Timestamp"].iloc[0])
    hourly_timestamps = pd.date_range(start=base_ts, periods=n_t, freq="1h")

    # Normalize driving telemetry signals to [0, 1] for physical rate synthesis
    strain_norm = (
        (strain_smooth.iloc[::step].values - strain_smooth.min())
        / max(strain_smooth.max() - strain_smooth.min(), 1e-6)
    )
    vib_vals = bld_sampled["Vibration_RMS"].values
    vib_norm = (vib_vals - vib_vals.min()) / max(vib_vals.max() - vib_vals.min(), 1e-6)
    tilt_vals = bld_sampled["Tilt_deg"].values
    tilt_norm = (tilt_vals - tilt_vals.min()) / max(tilt_vals.max() - tilt_vals.min(), 1e-6)
    temp_vals = temp_smooth.iloc[::step].values

    # BIM structural context per node
    bim = bim_df.copy()
    bim_vib = bim["Vibration_Level"].values if "Vibration_Level" in bim.columns else np.ones(100)
    bim_crack = bim["Crack_Width"].values if "Crack_Width" in bim.columns else np.ones(100)
    bim_load = bim["Load_Bearing_Capacity"].values if "Load_Bearing_Capacity" in bim.columns else np.ones(100) * 300
    bim_risk = bim["Safety_Risk_Score"].values if "Safety_Risk_Score" in bim.columns else np.ones(100) * 5

    rng = np.random.default_rng(42)
    t_idx = np.arange(n_t, dtype=np.float64)

    records = []
    for idx_node, node in mesh_df.iterrows():
        nid = int(node["MeshNode_ID"])
        gx, gy = float(node["Grid_X"]), float(node["Grid_Y"])

        # Spatial subsidence bowl over coal panel (higher rate near panel centre & secondary trough)
        dist_centre = np.sqrt((gx - 50.0) ** 2 + (gy - 50.0) ** 2)
        dist_secondary = np.sqrt((gx - 75.0) ** 2 + (gy - 65.0) ** 2)
        spatial_factor = (
            1.35 * np.exp(-(dist_centre ** 2) / (2 * 28.0 ** 2))
            + 0.65 * np.exp(-(dist_secondary ** 2) / (2 * 20.0 ** 2))
            + 0.25
        )

        # Node-specific BIM structural properties
        node_vib_lvl = float(bim_vib[idx_node % len(bim_vib)])
        node_crack = float(bim_crack[idx_node % len(bim_crack)])
        node_load = float(bim_load[idx_node % len(bim_load)])
        node_safety = float(bim_risk[idx_node % len(bim_risk)])
        structural_vulnerability = (
            0.4 * (node_crack / max(bim_crack.max(), 1.0))
            + 0.3 * (node_safety / max(bim_risk.max(), 1.0))
            + 0.3 * (1.0 - node_load / max(bim_load.max(), 1.0))
        )

        # Smooth temporal wave + sensor-driven incremental subsidence rate (mm/h)
        phase = (nid % 17) * 0.25
        temporal_wave = 0.5 + 0.5 * np.sin(2.0 * np.pi * t_idx / 120.0 + phase)

        # Instantaneous hourly subsidence rate driven by physical telemetry + AR(1) continuity
        raw_rate = (
            spatial_factor
            * (0.045 + 0.035 * structural_vulnerability)
            * (
                0.45 * temporal_wave
                + 0.25 * strain_norm
                + 0.18 * vib_norm
                + 0.12 * tilt_norm
            )
        )
        # Smooth rate with exponential moving average (autoregressive physical momentum)
        inst_rate = (
            pd.Series(raw_rate).ewm(span=8, adjust=False).mean().to_numpy(copy=True)
            + rng.normal(0, 0.0015 * spatial_factor, n_t)
        )
        inst_rate = np.clip(inst_rate, 0.002, None)

        # Cumulative ground displacement W(t) + thermal drift correction residual
        disp_cumulative = np.cumsum(inst_rate) + 2.0 * spatial_factor
        temp_local = temp_vals + rng.normal(0, 0.15, n_t)
        disp_corr = disp_cumulative - ALPHA_THERMAL * (temp_local - baseline_temp)

        # Tilt angle evolves proportionally to spatial slope + local rate
        tilt_local = (
            tilt_vals * (0.6 + 0.4 * spatial_factor)
            + 0.065 * disp_corr
            + rng.normal(0, 0.01, n_t)
        )
        vib_local = vib_vals + 0.08 * spatial_factor * temporal_wave + rng.normal(0, 0.01, n_t)

        # Dynamic velocities
        sub_vel = pd.Series(disp_corr).diff().fillna(inst_rate[0]).values
        tilt_vel = pd.Series(tilt_local).diff().fillna(0.0).values

        node_df = pd.DataFrame({
            "Timestamp": hourly_timestamps,
            "MeshNode_ID": nid,
            "Grid_X": gx,
            "Grid_Y": gy,
            "Displacement_mm": disp_corr,
            "Tilt_deg": tilt_local,
            "Vibration_RMS": vib_local,
            "Temperature_C": temp_local,
            "Subsidence_Velocity_mm_h": sub_vel,
            "Tilt_Velocity_deg_h": tilt_vel,
            "Signal_Strength": float(node.get("Signal_Strength", -50.0)),
            "Packet_Loss_Rate": float(node.get("Packet_Loss_Rate", 5.0)),
            "Residual_Energy": float(node.get("Residual_Energy", 2.0)),
            "Vibration_Level_mean": node_vib_lvl,
            "Crack_Width_mean": node_crack,
            "Load_Bearing_mean": node_load,
            "Safety_Risk_mean": node_safety,
        })
        records.append(node_df)

    full_df = pd.concat(records, ignore_index=True)

    # ── Surface Strain Gradient (inter-node differential displacement) ───
    full_df = _compute_strain_gradient(full_df, mesh_df, grid_size)

    # ── Temporal Lag & Rolling Window Features (grouped by MeshNode_ID) ──
    full_df = _add_temporal_lag_features(full_df)

    # ── Target Variables (Delta_Disp_1h, Delta_Disp_6h, Risk_Tier) ───────
    full_df = _generate_targets(full_df)

    # Impute any remaining NaNs in feature columns
    full_df = _impute_missing(full_df)

    return full_df


# ═══════════════════════════════════════════════════════════════════════════════
#  4. STRAIN GRADIENT & TEMPORAL LAG FEATURES
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_strain_gradient(df: pd.DataFrame,
                             mesh_df: pd.DataFrame,
                             grid_size: int) -> pd.DataFrame:
    """Compute surface strain gradient: Δd_ij / L_ij between adjacent nodes."""
    coords = mesh_df[["MeshNode_ID", "Grid_X", "Grid_Y"]].copy()
    coord_arr = coords[["Grid_X", "Grid_Y"]].values
    node_ids = coords["MeshNode_ID"].values.astype(int)
    tree = cKDTree(coord_arr)
    spacing = 90.0 / max(grid_size - 1, 1)

    adj_pairs = []
    id_to_idx = {int(nid): i for i, nid in enumerate(node_ids)}
    for i, pt in enumerate(coord_arr):
        nbr_indices = tree.query_ball_point(pt, spacing * 1.5)
        for j in nbr_indices:
            if j != i:
                l_ij = np.linalg.norm(coord_arr[i] - coord_arr[j])
                if l_ij > 0:
                    adj_pairs.append((i, j, l_ij))

    if not adj_pairs:
        df["Strain_Gradient"] = 0.0
        return df

    adj_i = np.array([p[0] for p in adj_pairs])
    adj_j = np.array([p[1] for p in adj_pairs])
    adj_L = np.array([p[2] for p in adj_pairs])

    timestamps = df["Timestamp"].unique()
    n_nodes = len(node_ids)

    disp_matrix = np.zeros((len(timestamps), n_nodes))
    ts_to_tidx = {ts: ti for ti, ts in enumerate(timestamps)}

    ts_indices = df["Timestamp"].map(ts_to_tidx).values
    nid_indices = df["MeshNode_ID"].astype(int).map(id_to_idx).values
    valid = ~(np.isnan(ts_indices) | np.isnan(nid_indices))
    disp_matrix[ts_indices[valid].astype(int), nid_indices[valid].astype(int)] = (
        df["Displacement_mm"].values[valid]
    )

    diff_all = np.abs(disp_matrix[:, adj_i] - disp_matrix[:, adj_j]) / adj_L

    grad_matrix = np.zeros((len(timestamps), n_nodes))
    count_matrix = np.zeros(n_nodes)
    for p_idx in range(len(adj_i)):
        ni = adj_i[p_idx]
        grad_matrix[:, ni] += diff_all[:, p_idx]
        count_matrix[ni] += 1

    count_matrix[count_matrix == 0] = 1
    grad_matrix /= count_matrix[np.newaxis, :]

    ts_rep = np.repeat(timestamps, n_nodes)
    nid_rep = np.tile(node_ids, len(timestamps))
    grad_df = pd.DataFrame({
        "Timestamp": ts_rep,
        "MeshNode_ID": nid_rep.astype(int),
        "Strain_Gradient": grad_matrix.ravel(),
    })
    df = df.merge(grad_df, on=["Timestamp", "MeshNode_ID"], how="left")
    df["Strain_Gradient"] = df["Strain_Gradient"].fillna(0.0)
    return df


def _add_temporal_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-node autoregressive lags and rolling window statistics
    so tree and neural models have full temporal continuity.
    """
    df = df.sort_values(["MeshNode_ID", "Timestamp"]).reset_index(drop=True)
    grp_disp = df.groupby("MeshNode_ID")["Displacement_mm"]
    grp_vel = df.groupby("MeshNode_ID")["Subsidence_Velocity_mm_h"]
    grp_vib = df.groupby("MeshNode_ID")["Vibration_RMS"]

    # Displacement lags (t-1h, t-2h, t-3h)
    df["Disp_Lag_1h"] = grp_disp.shift(1)
    df["Disp_Lag_2h"] = grp_disp.shift(2)
    df["Disp_Lag_3h"] = grp_disp.shift(3)

    # Past incremental deltas (t - (t-1), (t-1) - (t-2), (t-2) - (t-3))
    df["Delta_Lag_1h"] = df["Displacement_mm"] - df["Disp_Lag_1h"]
    df["Delta_Lag_2h"] = df["Disp_Lag_1h"] - df["Disp_Lag_2h"]
    df["Delta_Lag_3h"] = df["Disp_Lag_2h"] - df["Disp_Lag_3h"]

    # Rolling window statistics per node
    df["Rolling_Mean_Delta_3h"] = (
        df.groupby("MeshNode_ID")["Delta_Lag_1h"]
        .transform(lambda s: s.rolling(3, min_periods=1).mean())
    )
    df["Rolling_Std_Delta_3h"] = (
        df.groupby("MeshNode_ID")["Delta_Lag_1h"]
        .transform(lambda s: s.rolling(3, min_periods=1).std().fillna(0.0))
    )
    df["Rolling_Mean_Vel_6h"] = (
        grp_vel.transform(lambda s: s.rolling(6, min_periods=1).mean())
    )
    df["Rolling_Mean_Vib_6h"] = (
        grp_vib.transform(lambda s: s.rolling(6, min_periods=1).mean())
    )

    # Backfill initial lag rows within each node so no leading NaNs remain
    lag_cols = [
        "Disp_Lag_1h", "Disp_Lag_2h", "Disp_Lag_3h",
        "Delta_Lag_1h", "Delta_Lag_2h", "Delta_Lag_3h",
        "Rolling_Mean_Delta_3h", "Rolling_Std_Delta_3h",
        "Rolling_Mean_Vel_6h", "Rolling_Mean_Vib_6h",
    ]
    df[lag_cols] = df.groupby("MeshNode_ID")[lag_cols].bfill()
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  5. REFACTORED TARGET VARIABLE GENERATION (PREDICT DELTA, NOT ABSOLUTE)
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Create incremental delta regression targets and DGMS risk tier targets.

    Refactored Regression Targets (grouped by MeshNode_ID to prevent leakage):
      • Delta_Disp_1h = Displacement_mm(t+1h) - Displacement_mm(t)
      • Delta_Disp_6h = Displacement_mm(t+6h) - Displacement_mm(t)

    Classification Target:
      • Risk_Tier :
          0 = Safe        (displacement < 10 mm)
          1 = Advisory    (10 ≤ displacement < 25 mm)
          2 = Warning     (25 ≤ displacement < 40 mm)
          3 = Critical    (displacement ≥ 40 mm)
    """
    df = df.sort_values(["MeshNode_ID", "Timestamp"]).reset_index(drop=True)

    # Group by MeshNode_ID before shifting so values do not leak across spatial nodes
    df["Delta_Disp_1h"] = (
        df.groupby("MeshNode_ID")["Displacement_mm"].shift(-1) - df["Displacement_mm"]
    )
    df["Delta_Disp_6h"] = (
        df.groupby("MeshNode_ID")["Displacement_mm"].shift(-6) - df["Displacement_mm"]
    )

    # Risk classification based on absolute displacement (DGMS thresholds)
    disp_abs = df["Displacement_mm"].abs()
    conditions = [
        disp_abs < DGMS_THRESHOLDS["safe_displacement_mm"],
        disp_abs < DGMS_THRESHOLDS["advisory_displacement_mm"],
        disp_abs < DGMS_THRESHOLDS["warning_displacement_mm"],
    ]
    choices = [0, 1, 2]
    df["Risk_Tier"] = np.select(conditions, choices, default=3)

    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  6. PUBLIC API — run_preprocessing() / run_feature_engineering()
# ═══════════════════════════════════════════════════════════════════════════════

def run_preprocessing(data_dir: str = "dataset",
                      grid_size: int = 10) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Execute the full MUNKANIPPU preprocessing and delta feature engineering pipeline."""
    print("=" * 70)
    print("  MUNKANIPPU — PREPROCESSING & DELTA FEATURE ENGINEERING")
    print("=" * 70)

    # 1. Load datasets
    print("\n[1/5] Loading datasets …")
    building_df = load_building_health(
        os.path.join(data_dir, "building_health_monitoring_dataset.csv")
    )
    print(f"       Building Health : {building_df.shape}")

    bim_df = load_bim_civil(
        os.path.join(data_dir, "bim_ai_civil_engineering_dataset.csv")
    )
    print(f"       BIM Civil Eng   : {bim_df.shape}")

    temp_df = load_temperature(
        os.path.join(data_dir, "TEMP_ANNUAL_SEASONAL_MEAN.csv")
    )
    print(f"       Temperature     : {temp_df.shape}")

    wsn_df = load_wsn(
        os.path.join(data_dir, "WSN_Dataset.csv"),
        n_nodes=grid_size * grid_size,
    )
    print(f"       WSN Telemetry   : {wsn_df.shape}")

    # 2. Build mesh grid
    print("\n[2/5] Building spatial mesh grid …")
    mesh_df = build_mesh_grid(wsn_df, grid_size=grid_size)
    print(f"       Mesh nodes: {len(mesh_df)} ({grid_size}×{grid_size})")

    # 3. Engineer features
    print("\n[3/5] Engineering temporal lag & delta features …")
    features_df = engineer_features(
        building_df, bim_df, temp_df, mesh_df, grid_size=grid_size
    )
    print(f"       Feature matrix : {features_df.shape}")
    print(f"       Columns        : {features_df.columns.tolist()}")

    # 4. Summary statistics
    print("\n[4/5] Feature & Target statistics:")
    disp = features_df["Displacement_mm"]
    d1h = features_df["Delta_Disp_1h"].dropna()
    d6h = features_df["Delta_Disp_6h"].dropna()
    print(f"       Displacement (mm) — mean: {disp.mean():.4f}, "
          f"std: {disp.std():.4f}, max: {disp.abs().max():.4f}")
    print(f"       Delta_Disp_1h (mm) — mean: {d1h.mean():.5f}, std: {d1h.std():.5f}")
    print(f"       Delta_Disp_6h (mm) — mean: {d6h.mean():.5f}, std: {d6h.std():.5f}")
    print("       Risk Tier distribution:")
    tier_counts = features_df["Risk_Tier"].value_counts().sort_index()
    for tier, cnt in tier_counts.items():
        labels = {0: "Safe", 1: "Advisory", 2: "Warning", 3: "Critical"}
        print(f"         {tier} ({labels.get(tier, '?')}): {cnt}")

    # 5. Drop trailing rows per node where Delta_Disp_1h or Delta_Disp_6h is NaN
    n_before = len(features_df)
    features_df.dropna(subset=["Delta_Disp_1h", "Delta_Disp_6h"], inplace=True)
    features_df.reset_index(drop=True, inplace=True)
    print(f"\n[5/5] Dropped {n_before - len(features_df)} trailing shift rows "
          f"→ {len(features_df)} usable rows")

    print("\n✓ Feature engineering complete.\n")
    return features_df, mesh_df


# Alias for callers using run_feature_engineering
run_feature_engineering = run_preprocessing


if __name__ == "__main__":
    df, mesh = run_preprocessing()
    print(df[["MeshNode_ID", "Timestamp", "Displacement_mm", "Delta_Disp_1h", "Delta_Disp_6h", "Risk_Tier"]].head(10))
