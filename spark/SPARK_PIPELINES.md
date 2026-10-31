# Spark Pipelines: How to Run and Understand Them

This guide covers the two Spark entry points in this directory:

- [`spark_feature_pipeline.py`](./spark_feature_pipeline.py)
- [`spark_streaming_pipeline.py`](./spark_streaming_pipeline.py)

## Prerequisites

Install the project dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

PySpark is optional on Windows in the current dependency file. If PySpark is
not installed, the batch script uses its PyArrow/Pandas fallback and the
streaming script runs its deterministic simulation demo.

To install PySpark explicitly for local Spark execution:

```powershell
python -m pip install pyspark pyarrow
```

## Batch feature pipeline

### Run it

From this directory:

```powershell
python spark_feature_pipeline.py
```

The script selects `output/processed_features.csv` when it exists. Otherwise
it uses `dataset/WSN_Dataset.csv`. Its default output is:

```text
output/parquet/silver_features/
```

### Use it from Python

```python
from spark_feature_pipeline import (
    create_spark_session,
    build_spark_feature_pipeline,
)

spark = create_spark_session()
try:
    features = build_spark_feature_pipeline(
        spark,
        input_csv_path="output/processed_features.csv",
        output_parquet_dir="output/parquet/silver_features",
    )
finally:
    spark.stop()
```

### Important output columns

The batch DataFrame can contain:

- `Disp_corr`
- `Disp_Lag_1h`, `Disp_Lag_2h`, `Disp_Lag_3h`, `Disp_Lag_6h`
- `Subsidence_Vel_mm_h`
- `Tilt_Vel_deg_h`
- `Delta_Disp_1h`
- `Delta_Disp_6h`
- `Pred_Subsidence_24h`
- `DGMS_Risk_Tier`
- `Time_To_Critical_Hours`

### Fallback behavior

If importing `pyspark` fails, the script does not silently stop. It explicitly
calls `execute_parquet_pipeline_fallback`, which reproduces the main
correction, lag, risk, and Parquet-writing steps with Pandas and PyArrow.

The fallback is useful for verification on a workstation, but it is not a
distributed Spark execution plan.

## Streaming pipeline

### Input contract

The stream expects JSON records matching this schema:

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

The hardware server writes compatible records into:

```text
stream_input/
```

### Run it

From this directory:

```powershell
python spark_streaming_pipeline.py
```

When PySpark is installed, the script:

1. Creates a Structured Streaming session.
2. Monitors `stream_input/`.
3. Reads at most 50 new files per trigger.
4. Applies a 10-second event-time watermark.
5. Processes records every 20 seconds.
6. Uses `output/spark_checkpoints/` for restart recovery.
7. Sends each micro-batch to `process_micro_batch`.

Stop the process with `Ctrl+C`. The script stops the streaming query and Spark
session gracefully.

### Demo mode without PySpark

When PySpark is unavailable:

```powershell
python spark_streaming_pipeline.py
```

runs `run_streaming_simulation_demo`. The demo evaluates three representative
nodes and prints the calculated tier, TTC, and downstream `main.py` command.
It validates the business logic but does not monitor a directory or create a
Spark streaming query.

## Micro-batch processing

`process_micro_batch` is the integration point for downstream actions. For
each event in a non-empty micro-batch it:

1. Prints the node's displacement, tilt, vibration, risk tier, and TTC.
2. Builds a standard command:

```text
python main.py --node-id <id> --disp <disp> --tilt <tilt> \
  --vib <vib> --temp <temp> --vel <vel>
```

In a production deployment, this callback is the natural place to publish an
alert to a queue or call a controlled inference service. Any such integration
should preserve audit logging and avoid blocking the streaming callback.

## Operational checks

Before running a pipeline:

1. Confirm that the input path exists.
2. Confirm that timestamps are parseable.
3. Confirm that each event has a node identifier.
4. Check that the output and checkpoint directories are writable.
5. Use a new checkpoint location when changing the streaming query's schema or
   stateful logic in an incompatible way.

Useful Windows checks:

```powershell
Test-Path .\output\processed_features.csv
Test-Path .\dataset\WSN_Dataset.csv
Get-ChildItem .\stream_input
```

## Batch versus streaming

| Concern | Batch pipeline | Streaming pipeline |
|---|---|---|
| Entry point | `spark_feature_pipeline.py` | `spark_streaming_pipeline.py` |
| Input | CSV | JSON files arriving over time |
| Processing | Full historical dataset | Incremental micro-batches |
| Main state | Window lags by node | Event-time watermark and checkpoint |
| Output | Partitioned Silver Parquet | Console alerts and downstream commands |
| Default cadence | One complete run | 20 seconds |
| No-PySpark behavior | PyArrow/Pandas fallback | Simulation demo |

## Limitations to know

The current streaming callback collects each micro-batch to the driver for
printing and command generation. That is suitable for the demonstration scale
of this project, but large deployments should replace driver-side collection
with a distributed sink or a bounded, asynchronous alert publisher.

The batch and streaming paths use compatible risk thresholds, but their
displacement inputs differ: batch processing generally starts from a measured
displacement column, while streaming derives a displacement proxy from force
and temperature. This distinction should be retained when comparing results.
