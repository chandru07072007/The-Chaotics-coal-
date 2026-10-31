# MUNKANIPPU Spark Pipelines

This document explains the two Spark files used by the project:

1. [`spark_feature_pipeline.py`](./spark_feature_pipeline.py)
2. [`spark_streaming_pipeline.py`](./spark_streaming_pipeline.py)

## 1. `spark_feature_pipeline.py`

This file handles **historical batch processing**. It reads a complete CSV
dataset, calculates features for every sensor record, and writes the results
as Parquet files.

### Main purpose

It prepares historical sensor data for:

- Machine-learning training
- Subsidence analysis
- DGMS risk classification
- Time-to-critical calculations
- Large-scale storage in partitioned Parquet format

### Processing flow

```text
CSV files
   |
   v
Spark DataFrame
   |
   v
Thermal drift correction
   |
   v
Per-node lag features
   |
   v
Velocity and displacement deltas
   |
   v
24-hour prediction
   |
   v
DGMS risk tier and TTC
   |
   v
Partitioned Parquet output
```

### Important functions

#### `create_spark_session()`

Creates a Spark session configured for local execution:

```python
.master("local[*]")
```

`local[*]` allows Spark to use the available CPU cores on the current machine.
The function also configures Spark shuffle partitions, Arrow optimization, and
the local Spark UI.

#### `get_raw_telemetry_schema()`

Defines the expected structure of sensor telemetry, including:

- Timestamp and node ID
- Accelerometer values
- Strain and displacement
- Temperature and humidity
- Soil saturation and force
- Battery and packet-loss information

#### `build_spark_feature_pipeline()`

This is the main batch pipeline. It:

1. Reads the input CSV into a Spark DataFrame.
2. Applies thermal drift compensation.
3. Creates per-node time windows.
4. Calculates lag features, velocity, and displacement deltas.
5. Reconstructs projected 24-hour subsidence.
6. Assigns a DGMS risk tier.
7. Calculates time-to-critical.
8. Writes partitioned Parquet output.

### Thermal drift correction

Temperature changes can create artificial displacement. The pipeline compensates
for this using:

```text
Disp_corr = Disp_raw - alpha * (temperature - 24.6)
```

The default thermal coefficient is:

```python
alpha_thermal = 0.05
```

### Per-node window processing

The pipeline creates a Spark window grouped by sensor node and ordered by time:

```python
Window.partitionBy(node_id).orderBy(timestamp)
```

This allows previous readings to be calculated independently for each node.

### Lag features and displacement deltas

The pipeline calculates:

- `Disp_Lag_1h`
- `Disp_Lag_2h`
- `Disp_Lag_3h`
- `Disp_Lag_6h`
- `Delta_Disp_1h`
- `Delta_Disp_6h`

The velocity calculation is:

```text
Subsidence_Vel_mm_h =
    Disp_corr(current) - Disp_corr(previous)
```

### 24-hour reconstruction

The six-hour displacement change is projected four times:

```text
Pred_Subsidence_24h =
    Disp_corr + 4 * Delta_Disp_6h
```

### DGMS risk tiers

| Predicted displacement | Risk |
|---:|---|
| Less than 10 mm | `SAFE` |
| 10 to less than 25 mm | `ADVISORY` |
| 25 to less than 50 mm | `WARNING` |
| 50 mm or greater | `CRITICAL` |

### Time-to-critical

The pipeline estimates the time required to reach 50 mm:

```text
TTC =
    (50 - abs(current displacement)) / velocity
```

### Output

The final DataFrame is written to:

```text
output/parquet/silver_features/
```

The output is partitioned by `DGMS_Risk_Tier`, for example:

```text
output/parquet/silver_features/DGMS_Risk_Tier=SAFE/
output/parquet/silver_features/DGMS_Risk_Tier=WARNING/
output/parquet/silver_features/DGMS_Risk_Tier=CRITICAL/
```

### Fallback mode

If PySpark is unavailable, the script uses
`execute_parquet_pipeline_fallback()`. This fallback uses Pandas and PyArrow to
reproduce the main transformations and write Parquet output. It is useful for
local testing, but it does not provide distributed Spark execution.

## 2. `spark_streaming_pipeline.py`

This file handles **live sensor data** as it arrives. Instead of reading one
complete historical CSV, it monitors a directory for new JSON telemetry files.

### Main purpose

It provides near-real-time processing for:

- Incoming ESP32 sensor packets
- Live displacement estimation
- Live risk classification
- Time-to-critical alerts
- Downstream AI inference commands

### Processing flow

```text
ESP32 sensors
   |
   v
hardware/server.py
   |
   v
stream_input/packet_<id>.json
   |
   v
Spark Structured Streaming
   |
   v
Telemetry enrichment
   |
   v
Risk and TTC calculation
   |
   v
Micro-batch callback
   |
   v
AI inference command
```

### Important functions

#### `create_streaming_spark_session()`

Creates a streaming Spark session:

```python
.master("local[2]")
```

This uses two local CPU threads by default and enables graceful shutdown.

#### `get_stream_schema()`

Defines the expected JSON structure:

```json
{
  "timestamp": "...",
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

The explicit schema prevents Spark from repeatedly guessing data types for
incoming files.

#### `start_streaming_pipeline()`

The streaming pipeline monitors:

```text
stream_input/
```

It uses:

```python
spark.readStream \
    .schema(schema) \
    .option("maxFilesPerTrigger", 50) \
    .json(stream_source_dir)
```

At most 50 new JSON files are read during one trigger.

### Watermarking

The pipeline applies:

```python
withWatermark("timestamp", "10 seconds")
```

Wireless packets can arrive late or out of order. The watermark allows bounded
lateness and prevents streaming state from growing without limit.

### Live telemetry calculations

Tilt is calculated as:

```text
tilt_angle = sqrt(angle_x² + angle_y²)
```

Because a live packet does not contain direct displacement, the pipeline uses a
force-and-temperature proxy:

```text
disp_corr =
    (force_level_pct * 0.5)
    - (temperature - 24.6) * 0.05
```

Velocity is estimated from vibration:

```text
velocity = vibration * 0.18
```

The same risk categories are used:

```text
SAFE
ADVISORY
WARNING
CRITICAL
```

TTC is calculated as:

```text
TTC_hours = (50 - abs(disp_corr)) / velocity
```

If velocity is too low, the pipeline uses `999.0` as a stable/no-action value.

### `process_micro_batch()`

This callback runs once for every processed micro-batch. It:

1. Counts incoming events.
2. Prints the batch ID and event count.
3. Displays node telemetry and risk status.
4. Generates an AI inference command.

Example:

```text
python main.py --node-id 45 --disp 42.1 --tilt 4.2 --vib 9.85 --temp 31.0 --vel 1.8
```

### Checkpoints

The streaming job stores progress in:

```text
output/spark_checkpoints/
```

Checkpoints allow Spark to remember which input files have already been
processed after a restart. A new checkpoint location should be used when the
streaming schema or stateful logic changes incompatibly.

### Demo mode without PySpark

If PySpark is unavailable, the file runs
`run_streaming_simulation_demo()`. The demo uses sample events and prints:

- Calculated tilt
- Estimated displacement
- Estimated velocity
- DGMS risk tier
- TTC
- Downstream AI command

This validates the calculation logic but does not create a real Spark streaming
query.

## Main difference between the two files

| Feature | `spark_feature_pipeline.py` | `spark_streaming_pipeline.py` |
|---|---|---|
| Processing type | Batch | Real-time streaming |
| Input | Historical CSV | New JSON files |
| Data volume | Complete dataset | Incremental events |
| Spark API | `spark.read` | `spark.readStream` |
| Main use | Training and historical analysis | Live monitoring and alerts |
| Time behavior | One complete execution | Runs continuously |
| Output | Partitioned Parquet | Console alerts and AI commands |
| State handling | Node-based window functions | Watermarks and checkpoints |
| Default trigger | One complete run | Every 20 seconds |
| No-PySpark fallback | Pandas/PyArrow | Simulation demo |

In summary:

- `spark_feature_pipeline.py` answers:
  **“What does the historical sensor data tell us?”**
- `spark_streaming_pipeline.py` answers:
  **“What is happening with the sensors right now?”**

For the broader system design, see
[`SPARK_ARCHITECTURE.md`](./SPARK_ARCHITECTURE.md). For commands and operational
details, see [`SPARK_PIPELINES.md`](./SPARK_PIPELINES.md).
