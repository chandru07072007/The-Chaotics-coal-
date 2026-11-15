"""
timescale_manager.py — TimescaleDB & PostgreSQL Spatio-Temporal Storage Manager
Writes to hypertable: sensor_readings in parallel with MongoDB
"""
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    import psycopg2
except ImportError:
    psycopg2 = None

TIMESCALE_DSN = "postgresql://munkanippu:password@localhost:5432/munkanippu_spatial"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    time            TIMESTAMPTZ NOT NULL,
    node_id         INTEGER,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    displacement_mm DOUBLE PRECISION,
    tilt_deg        DOUBLE PRECISION,
    vibration       DOUBLE PRECISION,
    temperature     DOUBLE PRECISION,
    moisture_pct    DOUBLE PRECISION,
    dgms_tier       TEXT
);
"""

CREATE_HYPERTABLE_SQL = """
SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);
"""

class TimescaleManager:
    def __init__(self, dsn: str = TIMESCALE_DSN):
        self.dsn = dsn
        self.conn = None
        self.connected = False
        self.records_stored = 0
        self.last_write_time = 0.0
        self._connect()

    def _connect(self):
        if not psycopg2:
            return
        try:
            self.conn = psycopg2.connect(self.dsn, connect_timeout=3)
            self.conn.autocommit = True
            with self.conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
                try:
                    cur.execute(CREATE_HYPERTABLE_SQL)
                except Exception:
                    pass
            self.connected = True
            print("[TimescaleDB] Successfully connected to PostgreSQL / TimescaleDB")
        except Exception as e:
            self.connected = False
            self.conn = None
            # Soft fallback message
            print(f"[TimescaleDB] Connection standby: {e} (MongoDB primary active)")

    def store(self, payload: Dict[str, Any]):
        if not self.connected or not self.conn:
            return

        fused = payload.get("fused_telemetry", {})
        node2 = payload.get("node2_trekker", {})
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sensor_readings
                    (time, node_id, lat, lon, displacement_mm, tilt_deg,
                     vibration, temperature, moisture_pct, dgms_tier)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    datetime.now(timezone.utc),
                    1,
                    23.6102,
                    84.1314,
                    float(fused.get("displacement_mm", 0.0)),
                    float(fused.get("tilt_deg", 0.0)),
                    float(fused.get("vibration_level", 0.0)),
                    float(node2.get("temperature_c", 25.0)),
                    float(node2.get("moisture_pct", 55.0)),
                    str(fused.get("dgms_tier", "SAFE")),
                ))
            self.records_stored += 1
            self.last_write_time = time.time()
        except Exception as e:
            print(f"[TimescaleDB] Write failed: {e}")
            self.connected = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "records_stored": self.records_stored,
            "last_write": self.last_write_time,
            "dsn": self.dsn.split("@")[-1] if "@" in self.dsn else "localhost:5432"
        }

timescale_manager = TimescaleManager()
