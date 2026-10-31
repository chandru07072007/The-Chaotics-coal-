"""
benchmark.py — MUNKANIPPU: Model Training & Delta Benchmarking Engine
=====================================================================
MUNKANIPPU — AI-Enabled Wireless Surface Mesh Network for Real-Time Mine Subsidence Detection

Refactored Architecture:
  • Predicts incremental delta displacement (`Delta_Disp_1h` and `Delta_Disp_6h`)
    instead of raw unbounded 24h absolute levels, eliminating extrapolation failure.
  • Incorporates per-node temporal lag features and rolling window statistics.
  • Reconstructs absolute future ground deformation from predicted deltas:
      W_hat(t + Δt) = W(t) + ΔW_hat

Benchmarks four models on an 80/20 chronological split:
  • Isolation Forest          — zero-shot anomaly baseline
  • XGBoost Regressor/Classifier — gradient boosted trees
  • Temporal MLP (LSTM fallback) — multi-layer neural sequence model
  • Random Forest (TabPFN baseline) — bagging ensemble

Project : MUNKANIPPU
Date    : 2026-10-04
"""

from __future__ import annotations

import time
import warnings
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    f1_score,
    precision_recall_curve,
    auc,
    confusion_matrix,
)
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from tabulate import tabulate as tabulate_fn

warnings.filterwarnings("ignore")

# ─── Feature columns including temporal lags & rolling statistics ────────────
FEATURE_COLS = [
    "Displacement_mm",
    "Tilt_deg",
    "Vibration_RMS",
    "Temperature_C",
    "Subsidence_Velocity_mm_h",
    "Tilt_Velocity_deg_h",
    "Signal_Strength",
    "Packet_Loss_Rate",
    "Residual_Energy",
    "Strain_Gradient",
    "Vibration_Level_mean",
    "Crack_Width_mean",
    "Load_Bearing_mean",
    "Safety_Risk_mean",
    "Disp_Lag_1h",
    "Disp_Lag_2h",
    "Disp_Lag_3h",
    "Delta_Lag_1h",
    "Delta_Lag_2h",
    "Delta_Lag_3h",
    "Rolling_Mean_Delta_3h",
    "Rolling_Std_Delta_3h",
    "Rolling_Mean_Vel_6h",
    "Rolling_Mean_Vib_6h",
]

REGRESSION_TARGET_1H = "Delta_Disp_1h"
REGRESSION_TARGET_6H = "Delta_Disp_6h"
REGRESSION_TARGET = REGRESSION_TARGET_6H
CLASSIFICATION_TARGET = "Risk_Tier"


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA PREPARATION (80/20 PER-NODE CHRONOLOGICAL SPLIT)
# ═══════════════════════════════════════════════════════════════════════════════

def prepare_data(df: pd.DataFrame,
                 test_size: float = 0.20,
                 target_col: str = REGRESSION_TARGET,
                 ) -> Dict[str, Any]:
    """Prepare chronological 80/20 train/test split across all mesh nodes.

    Parameters
    ----------
    df : pd.DataFrame
        Feature-engineered DataFrame from `feature_engineering.py`.
    test_size : float
        Fraction of latest timestamps held out for testing.
    target_col : str
        Primary regression target (`Delta_Disp_6h` or `Delta_Disp_1h`).
    """
    df = df.sort_values(["Timestamp", "MeshNode_ID"]).reset_index(drop=True)
    feat_cols = [c for c in FEATURE_COLS if c in df.columns]

    X = df[feat_cols].values.astype(np.float64)
    y_reg = df[target_col].values.astype(np.float64)
    y_reg_1h = df[REGRESSION_TARGET_1H].values.astype(np.float64)
    y_reg_6h = df[REGRESSION_TARGET_6H].values.astype(np.float64)
    y_cls = df[CLASSIFICATION_TARGET].values.astype(np.int32)

    split_idx = int(len(X) * (1.0 - test_size))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_reg_train, y_reg_test = y_reg[:split_idx], y_reg[split_idx:]
    y_1h_train, y_1h_test = y_reg_1h[:split_idx], y_reg_1h[split_idx:]
    y_6h_train, y_6h_test = y_reg_6h[:split_idx], y_reg_6h[split_idx:]
    y_cls_train, y_cls_test = y_cls[:split_idx], y_cls[split_idx:]

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_reg_train": y_reg_train,
        "y_reg_test": y_reg_test,
        "y_1h_train": y_1h_train,
        "y_1h_test": y_1h_test,
        "y_6h_train": y_6h_train,
        "y_6h_test": y_6h_test,
        "y_cls_train": y_cls_train,
        "y_cls_test": y_cls_test,
        "scaler": scaler,
        "feature_names": feat_cols,
        "split_idx": split_idx,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  METRIC HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def regression_metrics(y_true: np.ndarray,
                       y_pred: np.ndarray) -> Dict[str, float]:
    """Compute MAE, RMSE, R² for delta regression predictions."""
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred = y_true[mask], y_pred[mask]
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": float(r2_score(y_true, y_pred)) if len(y_true) > 1 else 0.0,
    }


def classification_metrics(y_true: np.ndarray,
                            y_pred: np.ndarray,
                            n_classes: int = 4) -> Dict[str, float]:
    """Compute F1 (macro), PR-AUC (one-vs-rest avg), False Alarm Rate."""
    present_classes = sorted(np.unique(np.concatenate([y_true, y_pred])))
    f1 = float(f1_score(y_true, y_pred, labels=present_classes, average="macro", zero_division=0))

    pr_auc_vals = []
    for cls in range(n_classes):
        y_bin_true = (y_true == cls).astype(int)
        y_bin_pred = (y_pred == cls).astype(int)
        if y_bin_true.sum() > 0:
            prec, rec, _ = precision_recall_curve(y_bin_true, y_bin_pred)
            pr_auc_vals.append(auc(rec, prec))
    pr_auc_avg = float(np.mean(pr_auc_vals)) if pr_auc_vals else 0.0

    cm = confusion_matrix(y_true, y_pred, labels=list(range(n_classes)))
    false_alarm_rates = []
    for cls in range(n_classes):
        fp = cm[:, cls].sum() - cm[cls, cls]
        tn = cm.sum() - cm[cls, :].sum() - cm[:, cls].sum() + cm[cls, cls]
        if (fp + tn) > 0:
            false_alarm_rates.append(fp / (fp + tn))
    far = float(np.mean(false_alarm_rates)) if false_alarm_rates else 0.0

    return {"F1_macro": f1, "PR_AUC": pr_auc_avg, "False_Alarm_Rate": far}


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ModelWrapper:
    """Base class for benchmark models."""
    name: str = "Base"

    def fit_regression(self, X, y): ...
    def predict_regression(self, X) -> np.ndarray: ...
    def fit_classification(self, X, y): ...
    def predict_classification(self, X) -> np.ndarray: ...


# ── 1. Isolation Forest (anomaly baseline) ───────────────────────────────────

class IsolationForestModel(ModelWrapper):
    """Zero-shot anomaly detector — uses anomaly score calibrated via linear
    scaling against training delta mean/std."""

    name = "Isolation Forest"

    def __init__(self):
        self.iso = IsolationForest(
            n_estimators=200, contamination=0.15, random_state=42, n_jobs=-1
        )
        self._reg_mean = 0.0
        self._reg_std = 1.0

    def fit_regression(self, X, y):
        self._reg_mean = float(np.nanmean(y))
        self._reg_std = float(np.nanstd(y))
        self.iso.fit(X)

    def predict_regression(self, X) -> np.ndarray:
        scores = -self.iso.decision_function(X)
        s_norm = (scores - scores.mean()) / max(scores.std(), 1e-6)
        return self._reg_mean + 0.15 * self._reg_std * s_norm

    def fit_classification(self, X, y):
        self.iso.fit(X)
        self._cls_bins = np.percentile(
            -self.iso.decision_function(X), [35, 70, 92]
        )

    def predict_classification(self, X) -> np.ndarray:
        scores = -self.iso.decision_function(X)
        return np.digitize(scores, self._cls_bins).astype(np.int32)


# ── 2. XGBoost ───────────────────────────────────────────────────────────────

class XGBoostModel(ModelWrapper):
    """XGBoost regressor and classifier."""

    name = "XGBoost"

    def __init__(self):
        import xgboost as xgb
        self.reg = xgb.XGBRegressor(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.85, colsample_bytree=0.85,
            random_state=42, verbosity=0, n_jobs=-1,
        )
        self.cls = xgb.XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.85, colsample_bytree=0.85,
            random_state=42, verbosity=0, n_jobs=-1,
            eval_metric="mlogloss",
        )
        self._le = None

    def fit_regression(self, X, y):
        self.reg.fit(X, y)

    def predict_regression(self, X) -> np.ndarray:
        return self.reg.predict(X)

    def fit_classification(self, X, y):
        from sklearn.preprocessing import LabelEncoder
        self._le = LabelEncoder()
        y_enc = self._le.fit_transform(y)
        self.cls.fit(X, y_enc)

    def predict_classification(self, X) -> np.ndarray:
        preds = self.cls.predict(X)
        if self._le is not None:
            return self._le.inverse_transform(preds.astype(int))
        return preds


# ── 3. LSTM / Temporal MLP ───────────────────────────────────────────────────

class TemporalModel(ModelWrapper):
    """Temporal MLP capturing non-linear multi-lag dynamics."""

    name = "Temporal MLP (LSTM fallback)"

    def __init__(self):
        from sklearn.neural_network import MLPRegressor, MLPClassifier
        self.reg = MLPRegressor(
            hidden_layer_sizes=(128, 64, 32),
            activation="relu",
            max_iter=300,
            early_stopping=True,
            random_state=42,
            verbose=False,
        )
        self.cls = MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation="relu",
            max_iter=300,
            early_stopping=True,
            random_state=42,
            verbose=False,
        )

    def fit_regression(self, X, y):
        self.reg.fit(X, y)

    def predict_regression(self, X) -> np.ndarray:
        return self.reg.predict(X)

    def fit_classification(self, X, y):
        self.cls.fit(X, y)

    def predict_classification(self, X) -> np.ndarray:
        return self.cls.predict(X)


# ── 4. Random Forest (TabPFN baseline) ──────────────────────────────────────

class RandomForestModel(ModelWrapper):
    """Random Forest ensemble baseline."""

    name = "Random Forest (TabPFN baseline)"

    def __init__(self):
        self.reg = RandomForestRegressor(
            n_estimators=250, max_depth=14, min_samples_leaf=3,
            random_state=42, n_jobs=-1,
        )
        self.cls = RandomForestClassifier(
            n_estimators=250, max_depth=14, min_samples_leaf=3,
            random_state=42, n_jobs=-1,
        )

    def fit_regression(self, X, y):
        self.reg.fit(X, y)

    def predict_regression(self, X) -> np.ndarray:
        return self.reg.predict(X)

    def fit_classification(self, X, y):
        self.cls.fit(X, y)

    def predict_classification(self, X) -> np.ndarray:
        return self.cls.predict(X)


# ═══════════════════════════════════════════════════════════════════════════════
#  BENCHMARK RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_benchmark(df: pd.DataFrame) -> Tuple[List[Dict], Dict[str, Any]]:
    """Run full benchmark across all models on incremental delta targets
    (`Delta_Disp_1h` and `Delta_Disp_6h`) and DGMS Risk_Tier classification.
    """
    print("=" * 70)
    print("  MUNKANIPPU — BENCHMARK ENGINE (DELTA TARGET FORMULATION)")
    print("=" * 70)

    data = prepare_data(df, target_col=REGRESSION_TARGET_6H)
    X_tr, X_te = data["X_train"], data["X_test"]
    y_1h_tr, y_1h_te = data["y_1h_train"], data["y_1h_test"]
    y_6h_tr, y_6h_te = data["y_6h_train"], data["y_6h_test"]
    y_cls_tr, y_cls_te = data["y_cls_train"], data["y_cls_test"]

    models_6h: List[ModelWrapper] = [
        IsolationForestModel(),
        XGBoostModel(),
        TemporalModel(),
        RandomForestModel(),
    ]
    models_1h: List[ModelWrapper] = [
        IsolationForestModel(),
        XGBoostModel(),
        TemporalModel(),
        RandomForestModel(),
    ]

    results = []
    best_reg_r2 = -np.inf
    best_reg_model = None
    best_reg_1h_model = None
    best_cls_f1 = -np.inf
    best_cls_model = None

    for model_6h, model_1h in zip(models_6h, models_1h):
        print(f"\n{'─' * 55}")
        print(f"  Training: {model_6h.name}")
        print(f"{'─' * 55}")
        row: Dict[str, Any] = {"Model": model_6h.name}

        # ── Regression (Delta_Disp_1h & Delta_Disp_6h) ───────────────────
        try:
            # 1h Delta fit & eval
            model_1h.fit_regression(X_tr, y_1h_tr)
            y_1h_pred = model_1h.predict_regression(X_te)
            met_1h = regression_metrics(y_1h_te, y_1h_pred)
            row["MAE_1h"] = met_1h["MAE"]
            row["RMSE_1h"] = met_1h["RMSE"]
            row["R2_1h"] = met_1h["R2"]

            # 6h Delta fit & eval (primary benchmark metric)
            t0 = time.perf_counter()
            model_6h.fit_regression(X_tr, y_6h_tr)
            _ = time.perf_counter() - t0

            t0 = time.perf_counter()
            y_6h_pred = model_6h.predict_regression(X_te)
            infer_time_reg = (time.perf_counter() - t0) / len(X_te) * 1000.0

            reg_met = regression_metrics(y_6h_te, y_6h_pred)
            row.update(reg_met)
            row["Reg_Infer_ms"] = infer_time_reg

            print(f"    Delta_Disp_1h — MAE: {met_1h['MAE']:.5f} mm, "
                  f"RMSE: {met_1h['RMSE']:.5f} mm, R²: {met_1h['R2']:.4f}")
            print(f"    Delta_Disp_6h — MAE: {reg_met['MAE']:.5f} mm, "
                  f"RMSE: {reg_met['RMSE']:.5f} mm, R²: {reg_met['R2']:.4f}")

            if reg_met["R2"] > best_reg_r2:
                best_reg_r2 = reg_met["R2"]
                best_reg_model = model_6h
                best_reg_1h_model = model_1h
        except Exception as e:
            print(f"    ⚠ Regression failed: {e}")
            row.update({
                "MAE": np.nan, "RMSE": np.nan, "R2": np.nan,
                "MAE_1h": np.nan, "RMSE_1h": np.nan, "R2_1h": np.nan,
                "Reg_Infer_ms": np.nan,
            })

        # ── Classification (DGMS Risk_Tier) ──────────────────────────────
        try:
            t0 = time.perf_counter()
            model_6h.fit_classification(X_tr, y_cls_tr)
            _ = time.perf_counter() - t0

            t0 = time.perf_counter()
            y_cls_pred = model_6h.predict_classification(X_te)
            infer_time_cls = (time.perf_counter() - t0) / len(X_te) * 1000.0

            y_cls_pred = np.clip(y_cls_pred, 0, 3).astype(int)
            cls_met = classification_metrics(y_cls_te, y_cls_pred)
            row.update(cls_met)
            row["Cls_Infer_ms"] = infer_time_cls

            print(f"    Classification — F1: {cls_met['F1_macro']:.4f}, "
                  f"PR-AUC: {cls_met['PR_AUC']:.4f}, "
                  f"FAR: {cls_met['False_Alarm_Rate']:.4f}")

            if cls_met["F1_macro"] > best_cls_f1:
                best_cls_f1 = cls_met["F1_macro"]
                best_cls_model = model_6h
        except Exception as e:
            print(f"    ⚠ Classification failed: {e}")
            row.update({
                "F1_macro": np.nan, "PR_AUC": np.nan,
                "False_Alarm_Rate": np.nan, "Cls_Infer_ms": np.nan,
            })

        results.append(row)

    # ── Print ASCII comparison table ─────────────────────────────────────
    print("\n" + "=" * 70)
    print("  MUNKANIPPU — BENCHMARK RESULTS (DELTA REGRESSION & CLASSIFICATION)")
    print("=" * 70)

    table_data = []
    for r in results:
        table_data.append([
            r["Model"],
            f"{r.get('R2_1h', 0):.4f}",
            f"{r.get('MAE', 0):.4f}",
            f"{r.get('RMSE', 0):.4f}",
            f"{r.get('R2', 0):.4f}",
            f"{r.get('F1_macro', 0):.4f}",
            f"{r.get('PR_AUC', 0):.4f}",
            f"{r.get('False_Alarm_Rate', 0):.4f}",
            f"{r.get('Reg_Infer_ms', 0):.4f}",
        ])

    headers = [
        "Model", "R² (1h Δ)", "MAE (6h Δ)", "RMSE (6h Δ)", "R² (6h Δ)",
        "F1 (macro)", "PR-AUC", "FAR", "Reg ms/node",
    ]
    print(tabulate_fn(table_data, headers=headers, tablefmt="grid"))

    print(f"\n★ Best Delta Regressor : {best_reg_model.name if best_reg_model else 'N/A'} "
          f"(R²_6h = {best_reg_r2:.4f})")
    print(f"★ Best Classifier      : {best_cls_model.name if best_cls_model else 'N/A'} "
          f"(F1 = {best_cls_f1:.4f})")

    best_models = {
        "regression": best_reg_model,
        "regression_1h": best_reg_1h_model,
        "classification": best_cls_model,
        "scaler": data["scaler"],
        "feature_names": data["feature_names"],
    }

    return results, best_models


# ═══════════════════════════════════════════════════════════════════════════════
#  PREDICTION ENGINE — Time-to-Critical (TTC) & Alert Ledger
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ttc_and_alerts(df: pd.DataFrame,
                           best_models: Dict[str, Any],
                           W_threshold: float = 50.0,
                           tilt_threshold: float = 5.0) -> pd.DataFrame:
    """Compute Time-to-Critical (TTC) and generate alert ledger using
    reconstructed subsidence from predicted deltas:
      W_hat(t+24h) = W(t) + 4 * Delta_Disp_6h_hat
    """
    print("\n" + "=" * 70)
    print("  MUNKANIPPU — TIME-TO-CRITICAL (TTC) & EARLY WARNING")
    print("=" * 70)

    latest = (
        df.sort_values("Timestamp")
        .groupby("MeshNode_ID")
        .last()
        .reset_index()
    )

    feat_cols = best_models["feature_names"]
    scaler = best_models["scaler"]
    reg_model_6h = best_models["regression"]
    reg_model_1h = best_models.get("regression_1h", reg_model_6h)
    cls_model = best_models["classification"]

    available_feats = [c for c in feat_cols if c in latest.columns]
    X_latest = latest[available_feats].values.astype(np.float64)
    if len(available_feats) < len(feat_cols):
        missing_count = len(feat_cols) - len(available_feats)
        X_latest = np.hstack([X_latest, np.zeros((len(X_latest), missing_count))])

    X_scaled = scaler.transform(X_latest)

    # Predict 1h and 6h incremental deltas
    pred_delta_1h = reg_model_1h.predict_regression(X_scaled)
    pred_delta_6h = reg_model_6h.predict_regression(X_scaled)

    # Reconstruct absolute subsidence at t+6h and t+24h from current displacement + delta
    current_disp = latest["Displacement_mm"].values
    pred_subsidence_6h = current_disp + pred_delta_6h
    pred_subsidence_24h = current_disp + 4.0 * pred_delta_6h

    pred_risk = cls_model.predict_classification(X_scaled)
    pred_risk = np.clip(pred_risk, 0, 3).astype(int)

    risk_labels = {0: "Safe", 1: "Advisory", 2: "Warning", 3: "Critical"}

    # Compute TTC using predicted delta rate (mm/h) combined with measured velocity
    sub_velocity = latest["Subsidence_Velocity_mm_h"].values
    pred_rate_mm_h = np.maximum(np.abs(pred_delta_6h) / 6.0, np.abs(sub_velocity))

    ttc_hours = np.full(len(latest), np.inf)
    for i in range(len(latest)):
        remaining = W_threshold - abs(current_disp[i])
        vel = pred_rate_mm_h[i]
        if vel > 1e-6 and remaining > 0:
            ttc_hours[i] = remaining / vel
        elif remaining <= 0:
            ttc_hours[i] = 0.0

    alert_df = pd.DataFrame({
        "Node_ID": latest["MeshNode_ID"].values,
        "X": latest["Grid_X"].values,
        "Y": latest["Grid_Y"].values,
        "Current_Tilt_deg": latest["Tilt_deg"].values,
        "Current_Displacement_mm": current_disp,
        "Predicted_Delta_1h_mm": pred_delta_1h,
        "Predicted_Delta_6h_mm": pred_delta_6h,
        "Predicted_Subsidence_6h_mm": pred_subsidence_6h,
        "Predicted_Subsidence_24h_mm": pred_subsidence_24h,
        "Risk_Level": [risk_labels.get(r, "Unknown") for r in pred_risk],
        "Risk_Tier": pred_risk,
        "TTC_hours": ttc_hours,
    })

    alert_df = alert_df.sort_values("TTC_hours").reset_index(drop=True)

    print(f"\n{'─' * 72}")
    print("  ALERT LEDGER (sorted by urgency — TTC ascending)")
    print(f"{'─' * 72}")

    display_df = alert_df.copy()
    display_df["TTC_hours"] = display_df["TTC_hours"].apply(
        lambda x: f"{x:.1f}" if x < 1e6 else "∞"
    )

    table = tabulate_fn(
        display_df[[
            "Node_ID", "X", "Y", "Current_Displacement_mm",
            "Predicted_Delta_6h_mm", "Predicted_Subsidence_24h_mm",
            "Risk_Level", "TTC_hours",
        ]].round(3).values.tolist(),
        headers=[
            "Node", "X", "Y", "Curr(mm)", "Δ6h(mm)",
            "Pred24h(mm)", "Risk", "TTC(h)",
        ],
        tablefmt="grid",
        maxcolwidths=12,
    )
    lines = table.split("\n")
    max_lines = min(len(lines), 45)
    print("\n".join(lines[:max_lines]))
    if len(lines) > max_lines:
        print(f"  … ({len(alert_df)} total nodes — showing top 20 most urgent)")

    min_ttc = alert_df["TTC_hours"].replace(np.inf, np.nan).min()
    max_sub = alert_df["Predicted_Subsidence_24h_mm"].max()
    critical_count = int((alert_df["Risk_Tier"] >= 3).sum())
    warning_count = int((alert_df["Risk_Tier"] >= 2).sum())

    print(f"\n  ⚡ Minimum TTC               : {min_ttc:.1f} hours")
    print(f"  ⚡ Max Predicted Subsidence  : {max_sub:.4f} mm (reconstructed t+24h)")
    print(f"  ⚡ Critical Nodes (Tier 3)   : {critical_count}")
    print(f"  ⚡ Warning+ Nodes (Tier ≥2)  : {warning_count}")

    return alert_df


if __name__ == "__main__":
    from feature_engineering import run_preprocessing

    df, mesh = run_preprocessing()
    results, best_models = run_benchmark(df)
    alerts = compute_ttc_and_alerts(df, best_models)

