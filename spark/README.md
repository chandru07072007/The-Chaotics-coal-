# MUNKANIPPU ML and Spark Pipelines

This folder contains the project's machine-learning pipeline, Spark batch
processing, Spark Structured Streaming, and related documentation.

## Folder contents

### Machine-learning pipeline

- [`main.py`](./main.py) - complete ML pipeline and command-line analyzer
- [`feature_engineering.py`](./feature_engineering.py) - cleaning, feature
  engineering, temporal lags, and displacement targets
- [`benchmark.py`](./benchmark.py) - model benchmarking and TTC alert
  generation
- [`preprocess.py`](./preprocess.py) - compatibility wrapper for feature
  engineering
- [`visualize_heatmap.py`](./visualize_heatmap.py) - heatmap and benchmark
  visualizations
- [`kalman_filter.py`](./kalman_filter.py) - recursive telemetry filtering

### Spark pipeline

- [`spark_feature_pipeline.py`](./spark_feature_pipeline.py) - historical
  batch feature engineering
- [`spark_streaming_pipeline.py`](./spark_streaming_pipeline.py) - live JSON
  telemetry processing with Structured Streaming

### Documentation

- [`SPARK_ARCHITECTURE.md`](./SPARK_ARCHITECTURE.md) - system architecture,
  data flow, formulas, and Spark design
- [`SPARK_PIPELINES.md`](./SPARK_PIPELINES.md) - execution and operations
  guide
- [`spark_readme.md`](./spark_readme.md) - detailed explanation of the two
  Spark files

## Repository layout

The commands in this README are run from the repository root:

```text
Ml for project coal/
├── dataset/                         # Input CSV datasets
├── output/                          # Generated model and visualization files
├── hardware/                        # ESP32 serial bridge and dashboard
├── tunnel-digital-twin/             # Digital Twin frontend
└── spark/                           # This folder
```

The Spark scripts use repository-root paths for input and output by default.
When running a script from this folder, use the commands shown below so Python
can resolve the package imports correctly.

## Installation

From the repository root:

```powershell
python -m pip install -r requirements.txt
```

PySpark is optional for local development. If it is not installed:

- `spark_feature_pipeline.py` uses its Pandas/PyArrow fallback.
- `spark_streaming_pipeline.py` runs its streaming simulation demo.

To run actual Spark locally:

```powershell
python -m pip install pyspark pyarrow
```

## Run the ML pipeline

From the repository root:

```powershell
python spark\main.py --skip-interactive
```

Run the custom command-line analyzer:

```powershell
python spark\main.py --node-id 45 --disp 42.5 --tilt 4.2 --vib 9.85 --temp 31.0 --vel 1.8
```

The main pipeline reads data from `dataset/` and writes generated artifacts
to `output/`.

## Run the Spark batch pipeline

From the repository root:

```powershell
python spark\spark_feature_pipeline.py
```

The script uses `output/processed_features.csv` when available and otherwise
falls back to `dataset/WSN_Dataset.csv`. Its default output is:

```text
output/parquet/silver_features/
```

The output is partitioned by `DGMS_Risk_Tier`.

## Run the Spark streaming pipeline

The hardware bridge writes live JSON packets to `stream_input/`. Start the
streaming pipeline from the repository root:

```powershell
python spark\spark_streaming_pipeline.py
```

The live pipeline:

1. Reads new JSON files from `stream_input/`.
2. Validates them using an explicit telemetry schema.
3. Applies a 10-second event-time watermark.
4. Calculates tilt, displacement, velocity, risk tier, and TTC.
5. Processes micro-batches every 20 seconds.
6. Stores progress in `output/spark_checkpoints/`.
7. Prints downstream commands for `main.py`.

Example input:

```json
{
  "timestamp": "2026-10-31T20:50:00",
  "node_id": 45,
  "angle_x": 3.8,
  "angle_y": 1.7,
  "vibration": 9.85,
  "temperature": 31.0,
  "humidity": 60.0,
  "soil_raw": 1200,
  "moisture_pct": 70.0,
  "fsr_raw": 3000,
  "force_level_pct": 85.0
}
```

If PySpark is unavailable, the same command runs the deterministic simulation
demo instead of opening a live streaming query.

## Processing formulas

Thermal correction:

```text
Disp_corr = Disp_raw - alpha * (temperature - 24.6)
```

Projected 24-hour subsidence:

```text
Pred_Subsidence_24h = Disp_corr + 4 * Delta_Disp_6h
```

DGMS project risk tiers:

| Absolute projected displacement | Tier |
|---:|---|
| `< 10 mm` | `SAFE` |
| `10 to < 25 mm` | `ADVISORY` |
| `25 to < 50 mm` | `WARNING` |
| `>= 50 mm` | `CRITICAL` |

These are decision-support thresholds. Operational mine-safety decisions must
be reviewed by qualified safety personnel.

## Related documentation

See the repository-level documentation for the complete system overview:

- [`../hardware/`](../hardware/)
- [`../tunnel-digital-twin/`](../tunnel-digital-twin/)
- [`SPARK_ARCHITECTURE.md`](./SPARK_ARCHITECTURE.md)
- [`SPARK_PIPELINES.md`](./SPARK_PIPELINES.md)
- [`spark_readme.md`](./spark_readme.md)
