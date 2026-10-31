"""
visualize_heatmap.py — MUNKANIPPU: Spatial Interpolation & 2D/3D Heatmap Visualization
======================================================================================
MUNKANIPPU — AI-Enabled Wireless Surface Mesh Network for Real-Time Mine Subsidence Detection

Generates:
  1. Current Ground Deformation Heatmap (mm) with node markers
  2. Predicted Subsidence Heatmap (t+24 hours)
  3. Subsidence Velocity / Risk Zone Map (color-coded by DGMS tiers)
  4. Multi-model Benchmark Comparison Chart

Uses scipy RBF interpolation for smooth spatial field rendering.

Project : MUNKANIPPU
Date    : 2026-10-04
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for production
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
from scipy.interpolate import RBFInterpolator
from datetime import datetime
from typing import Optional


# ─── DGMS risk thresholds ────────────────────────────────────────────────────
RISK_COLORS = {
    0: "#2ecc71",   # Green  — Stable / Safe
    1: "#f1c40f",   # Yellow — Advisory
    2: "#e67e22",   # Orange — Warning / Fissures
    3: "#e74c3c",   # Red    — Critical / Collapse Hazard
}

RISK_LABELS = {
    0: "Stable (Safe)",
    1: "Advisory",
    2: "Warning (Fissures)",
    3: "Critical (Collapse)",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  SPATIAL INTERPOLATION
# ═══════════════════════════════════════════════════════════════════════════════

def interpolate_surface(node_x: np.ndarray,
                        node_y: np.ndarray,
                        node_values: np.ndarray,
                        grid_resolution: int = 100,
                        ) -> tuple:
    """Interpolate discrete sensor readings to a continuous surface.

    Uses Radial Basis Function (RBF) interpolation for smooth field
    reconstruction across the mining panel coordinate plane.

    Parameters
    ----------
    node_x, node_y : np.ndarray
        Sensor node coordinates.
    node_values : np.ndarray
        Measured/predicted values at each node.
    grid_resolution : int
        Number of grid points per axis.

    Returns
    -------
    grid_x, grid_y : np.ndarray
        2D meshgrid coordinate arrays.
    grid_z : np.ndarray
        Interpolated surface values on the grid.
    """
    # Create interpolation grid
    xi = np.linspace(node_x.min() - 2, node_x.max() + 2, grid_resolution)
    yi = np.linspace(node_y.min() - 2, node_y.max() + 2, grid_resolution)
    grid_x, grid_y = np.meshgrid(xi, yi)

    # Flatten grid for RBF input
    grid_points = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    node_coords = np.column_stack([node_x, node_y])

    # RBF interpolation (thin-plate spline kernel)
    rbf = RBFInterpolator(
        node_coords, node_values,
        kernel="thin_plate_spline",
        smoothing=0.5,
    )
    grid_z = rbf(grid_points).reshape(grid_x.shape)

    return grid_x, grid_y, grid_z


# ═══════════════════════════════════════════════════════════════════════════════
#  HEATMAP RENDERING
# ═══════════════════════════════════════════════════════════════════════════════

def plot_subsidence_heatmaps(alert_df: pd.DataFrame,
                              features_df: pd.DataFrame,
                              panel_name: str = "Jharia Coalfield — Panel A1",
                              output_path: str = "subsidence_heatmap.png",
                              ) -> str:
    """Generate the 3-panel subsidence heatmap visualization.

    Subplot 1 : Current Ground Deformation (mm) + node markers
    Subplot 2 : Predicted Subsidence at t+24h (mm)
    Subplot 3 : Risk Zone Map (DGMS color-coded)

    Parameters
    ----------
    alert_df : pd.DataFrame
        Alert ledger from benchmark.py (Node_ID, X, Y, predictions, risk).
    features_df : pd.DataFrame
        Full feature-engineered dataset.
    panel_name : str
        Mining panel identifier for the plot title.
    output_path : str
        Path to save the output image.

    Returns
    -------
    str : Path to saved heatmap image.
    """
    print("\n" + "=" * 70)
    print("  MUNKANIPPU — HEATMAP VISUALIZATION")
    print("=" * 70)

    # Extract node data
    node_x = alert_df["X"].values.astype(float)
    node_y = alert_df["Y"].values.astype(float)
    current_disp = alert_df["Current_Displacement_mm"].values.astype(float)
    pred_sub = alert_df["Predicted_Subsidence_24h_mm"].values.astype(float)
    risk_tier = alert_df["Risk_Tier"].values.astype(int)
    ttc = alert_df["TTC_hours"].values.astype(float)

    # ── Interpolate surfaces ─────────────────────────────────────────────
    print("  Interpolating spatial fields …")
    gx1, gy1, gz_current = interpolate_surface(node_x, node_y, current_disp)
    gx2, gy2, gz_predicted = interpolate_surface(node_x, node_y, pred_sub)
    gx3, gy3, gz_risk = interpolate_surface(
        node_x, node_y, risk_tier.astype(float)
    )

    # ── Metadata ─────────────────────────────────────────────────────────
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    w_max = np.max(np.abs(pred_sub))
    min_ttc = np.min(ttc[ttc < 1e6]) if np.any(ttc < 1e6) else float("inf")
    min_ttc_str = f"{min_ttc:.1f} h" if min_ttc < 1e6 else "∞"

    # ── Figure Setup ─────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(22, 7.8), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.04, h_pad=0.06, hspace=0.05, wspace=0.04)
    fig.suptitle(
        f"MUNKANIPPU: AI-Enabled Mine Subsidence Detection — {panel_name}\n"
        f"Inference: {timestamp_str}   |   W_max = {w_max:.3f} mm   |   "
        f"Min TTC = {min_ttc_str}",
        fontsize=13, fontweight="bold",
    )

    # ── Subplot 1: Current Ground Deformation ────────────────────────────
    ax1 = axes[0]
    c1 = ax1.contourf(gx1, gy1, gz_current, levels=30, cmap="YlOrRd")
    ax1.scatter(node_x, node_y, c="black", s=18, marker="^",
                edgecolors="white", linewidth=0.5, zorder=5,
                label="Sensor Nodes")
    # Annotate critical nodes
    for i in range(len(node_x)):
        if risk_tier[i] >= 2:
            ax1.annotate(
                f"N{int(alert_df.iloc[i]['Node_ID'])}",
                (node_x[i], node_y[i]),
                fontsize=6.5, fontweight="bold", color="#4a0000",
                textcoords="offset points", xytext=(4, 4),
            )
    cbar1 = fig.colorbar(c1, ax=ax1, shrink=0.85, pad=0.02)
    cbar1.set_label("Displacement (mm)", fontsize=9)
    ax1.set_title("Current Ground Deformation", fontsize=11, fontweight="bold", pad=10)
    ax1.set_xlabel("X Coordinate (m)")
    ax1.set_ylabel("Y Coordinate (m)")
    ax1.legend(loc="lower right", fontsize=7.5)

    # ── Subplot 2: Predicted Subsidence (t+24h) ─────────────────────────
    ax2 = axes[1]
    c2 = ax2.contourf(gx2, gy2, gz_predicted, levels=30, cmap="coolwarm")
    ax2.scatter(node_x, node_y, c="black", s=18, marker="^",
                edgecolors="white", linewidth=0.5, zorder=5)
    # Mark node with max predicted subsidence
    max_idx = np.argmax(np.abs(pred_sub))
    ax2.scatter(node_x[max_idx], node_y[max_idx], c="lime", s=90,
                marker="*", edgecolors="black", linewidth=1, zorder=6,
                label=f"Max: {pred_sub[max_idx]:.3f} mm (N{int(alert_df.iloc[max_idx]['Node_ID'])})")
    cbar2 = fig.colorbar(c2, ax=ax2, shrink=0.85, pad=0.02)
    cbar2.set_label("Predicted Displacement (mm)", fontsize=9)
    ax2.set_title("Predicted Subsidence (t + 24h)", fontsize=11,
                   fontweight="bold", pad=10)
    ax2.set_xlabel("X Coordinate (m)")
    ax2.set_ylabel("Y Coordinate (m)")
    ax2.legend(loc="lower right", fontsize=7.5)

    # ── Subplot 3: Risk Zone Map ─────────────────────────────────────────
    ax3 = axes[2]

    # Create discrete risk colormap
    risk_cmap = mcolors.ListedColormap(
        [RISK_COLORS[i] for i in range(4)]
    )
    risk_norm = mcolors.BoundaryNorm([0, 0.5, 1.5, 2.5, 3.5], risk_cmap.N)

    # Clip interpolated risk to [0, 3]
    gz_risk_clipped = np.clip(gz_risk, 0, 3)

    c3 = ax3.contourf(gx3, gy3, gz_risk_clipped, levels=[0, 0.5, 1.5, 2.5, 3.5],
                       colors=[RISK_COLORS[0], RISK_COLORS[1],
                               RISK_COLORS[2], RISK_COLORS[3]])

    # Overlay node markers colored by their risk tier
    for tier in range(4):
        mask = risk_tier == tier
        if mask.any():
            ax3.scatter(
                node_x[mask], node_y[mask],
                c=RISK_COLORS[tier], s=32, marker="o",
                edgecolors="black", linewidth=0.8, zorder=5,
            )

    # Legend
    legend_patches = [
        Patch(facecolor=RISK_COLORS[i], edgecolor="black",
              label=RISK_LABELS[i])
        for i in range(4)
    ]
    ax3.legend(handles=legend_patches, loc="lower right", fontsize=7.5,
               title="DGMS Risk Tier", title_fontsize=8)

    ax3.set_title("Subsidence Risk Zones", fontsize=11, fontweight="bold", pad=10)
    ax3.set_xlabel("X Coordinate (m)")
    ax3.set_ylabel("Y Coordinate (m)")

    # ── Save ─────────────────────────────────────────────────────────────
    fig.savefig(output_path, dpi=200, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)

    print(f"  ✓ Heatmap saved → {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE PLOTLY VERSION (optional)
# ═══════════════════════════════════════════════════════════════════════════════

def plot_interactive_heatmap(alert_df: pd.DataFrame,
                              output_html: str = "subsidence_interactive.html",
                              ) -> str:
    """Generate an interactive Plotly heatmap (HTML).

    Creates an interactive version with hover information for each node.
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("  ⚠ Plotly not available — skipping interactive heatmap.")
        return ""

    node_x = alert_df["X"].values
    node_y = alert_df["Y"].values
    current_disp = alert_df["Current_Displacement_mm"].values
    pred_sub = alert_df["Predicted_Subsidence_24h_mm"].values
    risk_tier = alert_df["Risk_Tier"].values

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=(
            "Current Deformation (mm)",
            "Predicted Subsidence t+24h (mm)",
            "Risk Zones",
        ),
        horizontal_spacing=0.06,
    )

    # Interpolate for heatmap contours
    gx, gy, gz1 = interpolate_surface(node_x, node_y, current_disp, 60)
    _, _, gz2 = interpolate_surface(node_x, node_y, pred_sub, 60)
    _, _, gz3 = interpolate_surface(node_x, node_y, risk_tier.astype(float), 60)

    # Heatmap 1
    fig.add_trace(
        go.Heatmap(z=gz1, x=gx[0], y=gy[:, 0],
                    colorscale="YlOrRd", name="Deformation",
                    colorbar=dict(title="mm", x=0.28)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=node_x, y=node_y, mode="markers",
                   marker=dict(size=6, color="black", symbol="triangle-up"),
                   text=[f"N{int(alert_df.iloc[i]['Node_ID'])}: {current_disp[i]:.3f} mm"
                         for i in range(len(node_x))],
                   hoverinfo="text", showlegend=False),
        row=1, col=1,
    )

    # Heatmap 2
    fig.add_trace(
        go.Heatmap(z=gz2, x=gx[0], y=gy[:, 0],
                    colorscale="RdBu_r", name="Predicted",
                    colorbar=dict(title="mm", x=0.63)),
        row=1, col=2,
    )
    fig.add_trace(
        go.Scatter(x=node_x, y=node_y, mode="markers",
                   marker=dict(size=6, color="black", symbol="triangle-up"),
                   text=[f"N{int(alert_df.iloc[i]['Node_ID'])}: {pred_sub[i]:.3f} mm"
                         for i in range(len(node_x))],
                   hoverinfo="text", showlegend=False),
        row=1, col=2,
    )

    # Heatmap 3 — Risk
    risk_colorscale = [
        [0.0, RISK_COLORS[0]], [0.33, RISK_COLORS[1]],
        [0.66, RISK_COLORS[2]], [1.0, RISK_COLORS[3]],
    ]
    fig.add_trace(
        go.Heatmap(z=np.clip(gz3, 0, 3), x=gx[0], y=gy[:, 0],
                    colorscale=risk_colorscale, zmin=0, zmax=3,
                    name="Risk", colorbar=dict(title="Tier", x=0.98)),
        row=1, col=3,
    )
    fig.add_trace(
        go.Scatter(x=node_x, y=node_y, mode="markers",
                   marker=dict(size=6,
                               color=[RISK_COLORS.get(int(r), "#ccc")
                                      for r in risk_tier],
                               line=dict(width=1, color="black")),
                   text=[f"N{int(alert_df.iloc[i]['Node_ID'])}: "
                         f"{RISK_LABELS.get(int(risk_tier[i]), '?')}"
                         for i in range(len(node_x))],
                   hoverinfo="text", showlegend=False),
        row=1, col=3,
    )

    fig.update_layout(
        title_text="MUNKANIPPU: AI Mine Subsidence Detection — Interactive Heatmap",
        height=500, width=1500,
        template="plotly_white",
    )

    fig.write_html(output_html)
    print(f"  ✓ Interactive heatmap saved → {output_html}")
    return output_html


# ═══════════════════════════════════════════════════════════════════════════════
#  BENCHMARK COMPARISON CHART (IMAGE)
# ═══════════════════════════════════════════════════════════════════════════════

def plot_benchmark_results(results: list,
                           output_path: str = "output/benchmark_chart.png"
                           ) -> str:
    """Render a multi-panel visual benchmark comparison image for all models.

    Subplot 1 : Delta Regression R² Score (1h & 6h Horizons — Higher is Better)
    Subplot 2 : Delta Regression Error (MAE & RMSE in mm — Lower is Better)
    Subplot 3 : Classification Performance (F1-Macro, PR-AUC, False Alarm Rate)
    """
    print("\n" + "=" * 70)
    print("  MUNKANIPPU — BENCHMARK VISUALIZATION")
    print("=" * 70)

    models = [
        r["Model"]
        .replace(" (LSTM fallback)", "\n(MLP)")
        .replace(" (TabPFN baseline)", "\n(RF)")
        for r in results
    ]
    r2_1h = [max(r.get("R2_1h", 0.0), -0.2) for r in results]
    r2_6h = [max(r.get("R2", 0.0), -0.2) for r in results]
    mae = [r.get("MAE", 0.0) for r in results]
    rmse = [r.get("RMSE", 0.0) for r in results]
    f1 = [r.get("F1_macro", 0.0) for r in results]
    pr_auc = [r.get("PR_AUC", 0.0) for r in results]
    far = [r.get("False_Alarm_Rate", 0.0) for r in results]

    x = np.arange(len(models))
    fig, axes = plt.subplots(1, 3, figsize=(21, 6.6), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.04, h_pad=0.06, hspace=0.05, wspace=0.04)
    fig.suptitle(
        "MUNKANIPPU: AI Model Benchmarking — Delta Subsidence Regression & DGMS Risk Classification",
        fontsize=14, fontweight="bold",
    )

    # ── Subplot 1: Delta Regression R² (1h & 6h) ─────────────────────────
    ax1 = axes[0]
    w1 = 0.35
    b_r1 = ax1.bar(x - w1 / 2, r2_1h, w1, label="R² (Delta_Disp_1h) ↑", color="#2980b9", edgecolor="black")
    b_r6 = ax1.bar(x + w1 / 2, r2_6h, w1, label="R² (Delta_Disp_6h) ↑", color="#16a085", edgecolor="black")
    ax1.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax1.set_title("Delta Regression R² Score (Higher is Better)", fontsize=11, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, fontsize=9)
    ax1.set_ylabel("R² Score")
    ax1.set_ylim(min(min(r2_1h), min(r2_6h), 0.0) - 0.1, 1.12)
    ax1.legend(fontsize=8)
    ax1.grid(axis="y", linestyle="--", alpha=0.5)
    for idx_b, bar in enumerate(b_r1):
        raw_v = results[idx_b].get("R2_1h", 0.0)
        ax1.annotate(f"{raw_v:.3f}",
                     (bar.get_x() + bar.get_width() / 2, max(bar.get_height(), 0.01)),
                     ha="center", va="bottom", fontsize=8, xytext=(0, 2),
                     textcoords="offset points")
    for idx_b, bar in enumerate(b_r6):
        raw_v = results[idx_b].get("R2", 0.0)
        ax1.annotate(f"{raw_v:.3f}",
                     (bar.get_x() + bar.get_width() / 2, max(bar.get_height(), 0.01)),
                     ha="center", va="bottom", fontsize=8, xytext=(0, 2),
                     textcoords="offset points")

    # ── Subplot 2: Regression Error (MAE & RMSE on Delta_Disp_6h) ────────
    ax2 = axes[1]
    w2 = 0.35
    b1 = ax2.bar(x - w2 / 2, mae, w2, label="MAE 6h Δ (mm) ↓", color="#3498db", edgecolor="black")
    b2 = ax2.bar(x + w2 / 2, rmse, w2, label="RMSE 6h Δ (mm) ↓", color="#e74c3c", edgecolor="black")
    ax2.set_title("Delta Regression Error (Lower is Better)", fontsize=11, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(models, fontsize=9)
    ax2.set_ylabel("Error (mm)")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", linestyle="--", alpha=0.5)
    for bar in b1:
        ax2.annotate(f"{bar.get_height():.4f}",
                     (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     ha="center", va="bottom", fontsize=8, xytext=(0, 2),
                     textcoords="offset points")
    for bar in b2:
        ax2.annotate(f"{bar.get_height():.4f}",
                     (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     ha="center", va="bottom", fontsize=8, xytext=(0, 2),
                     textcoords="offset points")

    # ── Subplot 3: Classification Metrics (F1, PR-AUC, FAR) ──────────────
    ax3 = axes[2]
    w3 = 0.25
    b3 = ax3.bar(x - w3, f1, w3, label="F1 (Macro) ↑", color="#2ecc71", edgecolor="black")
    b4 = ax3.bar(x, pr_auc, w3, label="PR-AUC ↑", color="#9b59b6", edgecolor="black")
    b5 = ax3.bar(x + w3, far, w3, label="False Alarm Rate ↓", color="#f39c12", edgecolor="black")
    ax3.set_title("Classification Metrics (DGMS Risk Tiers)", fontsize=11, fontweight="bold")
    ax3.set_xticks(x)
    ax3.set_xticklabels(models, fontsize=9)
    ax3.set_ylabel("Score")
    ax3.set_ylim(0, 1.15)
    ax3.legend(fontsize=8)
    ax3.grid(axis="y", linestyle="--", alpha=0.5)
    for bars in (b3, b4, b5):
        for bar in bars:
            ax3.annotate(f"{bar.get_height():.3f}",
                         (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                         ha="center", va="bottom", fontsize=7.5, xytext=(0, 2),
                         textcoords="offset points")

    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✓ Benchmark chart saved → {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    alert_csv = os.path.join("output", "alert_ledger.csv")
    feat_csv = os.path.join("output", "processed_features.csv")
    if os.path.exists(alert_csv) and os.path.exists(feat_csv):
        alerts = pd.read_csv(alert_csv)
        feats = pd.read_csv(feat_csv)
        plot_subsidence_heatmaps(
            alert_df=alerts,
            features_df=feats,
            panel_name="Jharia Coalfield — Panel A1",
            output_path=os.path.join("output", "subsidence_heatmap.png"),
        )
        plot_interactive_heatmap(
            alert_df=alerts,
            output_html=os.path.join("output", "subsidence_interactive.html"),
        )
    else:
        print("Run via main.py for full MUNKANIPPU pipeline execution.")


