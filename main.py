"""
main.py — MUNKANIPPU: Pipeline Orchestrator & Interactive CMD Analyzer
======================================================================
MUNKANIPPU — AI-Enabled Wireless Surface Mesh Network for Real-Time Mine Subsidence Detection

Single entry point that executes the complete refactored pipeline:
  1. Data loading & delta feature engineering (feature_engineering.py)
  2. Model benchmarking & chart generation    (benchmark.py + visualize_heatmap.py)
  3. Custom CMD sensor input analysis         (optional CLI flags / interactive)
  4. TTC & alert generation                   (benchmark.py)
  5. Heatmap visualization                    (visualize_heatmap.py)

Usage:
    # Full pipeline with default dataset
    python main.py

    # Pass custom sensor input in CMD to analyze predicted delta & risk
    python main.py --node-id 45 --disp 42.5 --tilt 4.2 --vib 9.85 --temp 31.0 --vel 1.8

    # Interactive prompt mode in CMD
    python main.py --interactive-input

Project : MUNKANIPPU
Date    : 2026-10-04
"""

from __future__ import annotations

import os
import sys
import time
import argparse
from datetime import datetime
import numpy as np
import pandas as pd
from tabulate import tabulate as tabulate_fn

# ─── Ensure stdout handles Unicode on Windows ────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="MUNKANIPPU — AI Mine Subsidence Detection Pipeline & CMD Analyzer"
    )
    parser.add_argument(
        "--data-dir", type=str, default="dataset",
        help="Directory containing the four CSV datasets (default: dataset)",
    )
    parser.add_argument(
        "--grid-size", type=int, default=10,
        help="Mesh grid dimension N (NxN nodes). Default: 10 → 100 nodes.",
    )
    parser.add_argument(
        "--output-dir", type=str, default="output",
        help="Directory for output artifacts (default: output)",
    )
    parser.add_argument(
        "--skip-interactive", action="store_true",
        help="Skip generating the interactive Plotly HTML heatmap.",
    )

    # ── Custom CMD Sensor Input Arguments ────────────────────────────────
    parser.add_argument(
        "--interactive-input", action="store_true",
        help="Prompt interactively in CMD for custom node sensor inputs.",
    )
    parser.add_argument(
        "--node-id", type=int, default=None,
        help="Target MeshNode_ID (1..100) to inject custom sensor telemetry.",
    )
    parser.add_argument(
        "--disp", type=float, default=None,
        help="Custom current ground displacement (mm), e.g., 42.5",
    )
    parser.add_argument(
        "--tilt", type=float, default=None,
        help="Custom current tilt angle (degrees), e.g., 4.2",
    )
    parser.add_argument(
        "--vib", type=float, default=None,
        help="Custom RMS vibration (m/s^2), e.g., 9.85",
    )
    parser.add_argument(
        "--temp", type=float, default=None,
        help="Custom surface ambient temperature (°C), e.g., 31.0",
    )
    parser.add_argument(
        "--vel", type=float, default=None,
        help="Custom subsidence velocity (mm/h), e.g., 1.8",
    )
    return parser.parse_args()


def analyze_custom_cmd_input(args, features_df: pd.DataFrame, best_models: dict) -> pd.DataFrame:
    """If custom sensor inputs are provided via CMD flags or interactive prompt,
    inject them into the target node, update its lag/rolling features, run AI
    delta inference, and print a detailed analysis report.
    """
    has_cli_custom = any(
        v is not None for v in (args.node_id, args.disp, args.tilt, args.vib, args.temp, args.vel)
    )
    if not has_cli_custom and not args.interactive_input:
        return features_df

    print("\n" + "=" * 70)
    print("  MUNKANIPPU — CUSTOM CMD SENSOR INPUT & AI DELTA RISK PREDICTION")
    print("=" * 70)

    if args.interactive_input:
        try:
            nid_str = input("  Enter Target Node ID [1-100, default=45]: ").strip()
            node_id = int(nid_str) if nid_str else 45
            disp_str = input("  Enter Current Displacement (mm) [default=42.5]: ").strip()
            disp_val = float(disp_str) if disp_str else 42.5
            tilt_str = input("  Enter Current Tilt (deg) [default=4.2]: ").strip()
            tilt_val = float(tilt_str) if tilt_str else 4.2
            vib_str = input("  Enter Vibration RMS (m/s^2) [default=9.85]: ").strip()
            vib_val = float(vib_str) if vib_str else 9.85
            temp_str = input("  Enter Ambient Temperature (°C) [default=31.0]: ").strip()
            temp_val = float(temp_str) if temp_str else 31.0
            vel_str = input("  Enter Subsidence Velocity (mm/h) [default=1.8]: ").strip()
            vel_val = float(vel_str) if vel_str else 1.8
        except EOFError:
            node_id, disp_val, tilt_val, vib_val, temp_val, vel_val = 45, 42.5, 4.2, 9.85, 31.0, 1.8
    else:
        node_id = args.node_id if args.node_id is not None else 45
        disp_val = args.disp if args.disp is not None else 42.5
        tilt_val = args.tilt if args.tilt is not None else 4.2
        vib_val = args.vib if args.vib is not None else 9.85
        temp_val = args.temp if args.temp is not None else 31.0
        vel_val = args.vel if args.vel is not None else 1.8

    node_mask = features_df["MeshNode_ID"] == node_id
    if not node_mask.any():
        node_id = int(features_df["MeshNode_ID"].iloc[0])
        node_mask = features_df["MeshNode_ID"] == node_id

    latest_idx = features_df[node_mask].sort_values("Timestamp").index[-1]

    # Inject custom values and consistent lag/rolling features for the node
    features_df.loc[latest_idx, "Displacement_mm"] = disp_val
    features_df.loc[latest_idx, "Tilt_deg"] = tilt_val
    features_df.loc[latest_idx, "Vibration_RMS"] = vib_val
    features_df.loc[latest_idx, "Temperature_C"] = temp_val
    features_df.loc[latest_idx, "Subsidence_Velocity_mm_h"] = vel_val
    features_df.loc[latest_idx, "Disp_Lag_1h"] = disp_val - vel_val
    features_df.loc[latest_idx, "Disp_Lag_2h"] = disp_val - 2.0 * vel_val
    features_df.loc[latest_idx, "Disp_Lag_3h"] = disp_val - 3.0 * vel_val
    features_df.loc[latest_idx, "Delta_Lag_1h"] = vel_val
    features_df.loc[latest_idx, "Delta_Lag_2h"] = vel_val
    features_df.loc[latest_idx, "Delta_Lag_3h"] = vel_val
    features_df.loc[latest_idx, "Rolling_Mean_Delta_3h"] = vel_val
    features_df.loc[latest_idx, "Rolling_Mean_Vel_6h"] = vel_val

    feat_cols = best_models["feature_names"]
    scaler = best_models["scaler"]
    reg_model_6h = best_models["regression"]
    reg_model_1h = best_models.get("regression_1h", reg_model_6h)
    cls_model = best_models["classification"]

    row_feats = features_df.loc[[latest_idx], feat_cols].values.astype(np.float64)
    row_scaled = scaler.transform(row_feats)

    pred_delta_1h = float(reg_model_1h.predict_regression(row_scaled)[0])
    pred_delta_6h = float(reg_model_6h.predict_regression(row_scaled)[0])
    pred_sub_6h = disp_val + pred_delta_6h
    pred_sub_24h = disp_val + 4.0 * pred_delta_6h

    pred_risk_tier = int(np.clip(cls_model.predict_classification(row_scaled)[0], 0, 3))
    risk_labels = {
        0: "Safe (Tier 0)",
        1: "Advisory (Tier 1)",
        2: "Warning (Tier 2)",
        3: "Critical (Tier 3)",
    }

    eff_rate = max(abs(vel_val), abs(pred_delta_6h) / 6.0)
    remaining_mm = 50.0 - abs(disp_val)
    if eff_rate > 1e-6 and remaining_mm > 0:
        ttc_h = remaining_mm / eff_rate
        ttc_str = f"{ttc_h:.2f} hours"
    elif remaining_mm <= 0:
        ttc_str = "0.0 hours (BREACHED)"
    else:
        ttc_str = "∞ (Stable)"

    gx = features_df.loc[latest_idx, "Grid_X"]
    gy = features_df.loc[latest_idx, "Grid_Y"]

    summary_rows = [
        ["Target Mesh Node ID", f"Node {node_id} at ({gx:.1f}m, {gy:.1f}m)"],
        ["Input: Displacement (mm)", f"{disp_val:.3f} mm"],
        ["Input: Tilt Angle (deg)", f"{tilt_val:.3f}°"],
        ["Input: Vibration RMS (m/s²)", f"{vib_val:.3f} m/s²"],
        ["Input: Ambient Temp (°C)", f"{temp_val:.2f} °C"],
        ["Input: Subsidence Velocity", f"{vel_val:.3f} mm/h"],
        ["Predicted Delta_Disp_1h", f"+{pred_delta_1h:.4f} mm ({reg_model_1h.name})"],
        ["Predicted Delta_Disp_6h", f"+{pred_delta_6h:.4f} mm ({reg_model_6h.name})"],
        ["Reconstructed Subsidence (t+6h)", f"{pred_sub_6h:.3f} mm"],
        ["Reconstructed Subsidence (t+24h)", f"{pred_sub_24h:.3f} mm"],
        ["Predicted DGMS Risk Level", f"{risk_labels[pred_risk_tier]} ({cls_model.name})"],
        ["Estimated Time-To-Critical (TTC)", ttc_str],
    ]
    print(tabulate_fn(summary_rows, headers=["Parameter / Output", "Value"], tablefmt="grid"))
    return features_df


def main():
    """Execute the full MUNKANIPPU mine subsidence detection pipeline."""
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    start_time = time.perf_counter()

    print("\n" + "█" * 70)
    print("█                                                                    █")
    print("█   MUNKANIPPU — AI-ENABLED WIRELESS SURFACE MESH NETWORK            █")
    print("█   FOR REAL-TIME MINE SUBSIDENCE DETECTION                         █")
    print("█                                                                    █")
    print("█" * 70)
    print(f"\n  Pipeline start  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Data directory  : {os.path.abspath(args.data_dir)}")
    print(f"  Grid size       : {args.grid_size}×{args.grid_size} "
          f"({args.grid_size ** 2} nodes)")
    print(f"  Output directory: {os.path.abspath(args.output_dir)}")

    # ═════════════════════════════════════════════════════════════════════
    #  STAGE 1: PREPROCESSING & DELTA FEATURE ENGINEERING
    # ═════════════════════════════════════════════════════════════════════
    from feature_engineering import run_preprocessing

    features_df, mesh_df = run_preprocessing(
        data_dir=args.data_dir,
        grid_size=args.grid_size,
    )

    features_path = os.path.join(args.output_dir, "processed_features.csv")
    features_df.to_csv(features_path, index=False)
    print(f"  → Processed features saved: {features_path}")

    # ═════════════════════════════════════════════════════════════════════
    #  STAGE 2: MODEL BENCHMARKING & BENCHMARK IMAGE
    # ═════════════════════════════════════════════════════════════════════
    from benchmark import run_benchmark
    from visualize_heatmap import (
        plot_subsidence_heatmaps,
        plot_interactive_heatmap,
        plot_benchmark_results,
    )

    results, best_models = run_benchmark(features_df)

    benchmark_img_path = os.path.join(args.output_dir, "benchmark_chart.png")
    plot_benchmark_results(results, output_path=benchmark_img_path)

    # ═════════════════════════════════════════════════════════════════════
    #  STAGE 2.5: OPTIONAL CUSTOM CMD INPUT & RISK ANALYSIS
    # ═════════════════════════════════════════════════════════════════════
    features_df = analyze_custom_cmd_input(args, features_df, best_models)

    # ═════════════════════════════════════════════════════════════════════
    #  STAGE 3: TTC & EARLY WARNING ALERTS
    # ═════════════════════════════════════════════════════════════════════
    from benchmark import compute_ttc_and_alerts

    alert_df = compute_ttc_and_alerts(features_df, best_models)

    alerts_path = os.path.join(args.output_dir, "alert_ledger.csv")
    alert_df.to_csv(alerts_path, index=False)
    print(f"\n  → Alert ledger saved: {alerts_path}")

    # ═════════════════════════════════════════════════════════════════════
    #  STAGE 4: HEATMAP VISUALIZATION
    # ═════════════════════════════════════════════════════════════════════
    heatmap_path = os.path.join(args.output_dir, "subsidence_heatmap.png")
    plot_subsidence_heatmaps(
        alert_df=alert_df,
        features_df=features_df,
        panel_name="Jharia Coalfield — Panel A1",
        output_path=heatmap_path,
    )

    if not args.skip_interactive:
        interactive_path = os.path.join(
            args.output_dir, "subsidence_interactive.html"
        )
        plot_interactive_heatmap(
            alert_df=alert_df,
            output_html=interactive_path,
        )

    # ═════════════════════════════════════════════════════════════════════
    #  PIPELINE SUMMARY
    # ═════════════════════════════════════════════════════════════════════
    elapsed = time.perf_counter() - start_time

    print("\n" + "█" * 70)
    print("█  MUNKANIPPU PIPELINE COMPLETE                                      █")
    print("█" * 70)
    print(f"\n  Total runtime   : {elapsed:.1f} seconds")
    print(f"  Nodes processed : {len(alert_df)}")
    print(f"  Best Regressor  : {best_models['regression'].name}")
    print(f"  Best Classifier : {best_models['classification'].name}")
    print(f"\n  Output files:")
    print(f"    • {features_path}")
    print(f"    • {alerts_path}")
    print(f"    • {benchmark_img_path}")
    print(f"    • {heatmap_path}")
    if not args.skip_interactive:
        print(f"    • {os.path.join(args.output_dir, 'subsidence_interactive.html')}")
    print()


if __name__ == "__main__":
    main()

