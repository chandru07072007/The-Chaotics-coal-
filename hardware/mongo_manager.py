"""
mongo_manager.py — MongoDB Persistence Manager for MUNKANIPPU Platform
========================================================================
Connects to: mongodb://localhost:27017
Database:    munkanippu_db

Collections:
  1. hardware_telemetry    -> Raw & filtered ESP32 sensor packets (Tilt, Vib, Temp, Soil, FSR)
  2. aiml_predictions      -> Downstream AI/ML inference records, DGMS Risk Tiers, and TTC
  3. heatmap_nodes         -> Spatial 10x10 surface mesh node coordinates, strains & risk levels
  4. system_alerts         -> Real-time safety escalation logs
"""

from __future__ import annotations
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    import pymongo
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


class MongoManager:
    def __init__(self, uri: str = "mongodb://localhost:27017", db_name: str = "munkanippu_db"):
        self.uri = uri
        self.db_name = db_name
        self.client: Optional[MongoClient] = None
        self.db = None
        self.connected = False

        self._connect()

    def _connect(self):
        if not PYMONGO_AVAILABLE:
            print("[MongoDB] Warning: pymongo not installed.")
            return

        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=2000)
            # Ping database to confirm connection
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.connected = True
            self._ensure_indexes()
            print(f"[MongoDB] Connected successfully to {self.uri}/{self.db_name}")
        except Exception as e:
            self.connected = False
            print(f"[MongoDB] Notice: Could not connect to {self.uri}: {e}")

    def _ensure_indexes(self):
        if not self.connected or self.db is None:
            return
        try:
            self.db.hardware_telemetry.create_index([("timestamp", pymongo.DESCENDING)])
            self.db.hardware_telemetry.create_index([("node_id", pymongo.ASCENDING)])
            self.db.aiml_predictions.create_index([("timestamp", pymongo.DESCENDING)])
            self.db.aiml_predictions.create_index([("node_id", pymongo.ASCENDING)])
            self.db.heatmap_nodes.create_index([("node_id", pymongo.ASCENDING)], unique=True)
            self.db.system_alerts.create_index([("timestamp", pymongo.DESCENDING)])
        except Exception as e:
            print(f"[MongoDB] Index creation warning: {e}")

    def store_hardware_telemetry(self, packet: Dict[str, Any]) -> bool:
        """Stores ESP32 hardware telemetry packet."""
        if not self.connected or self.db is None:
            return False
        try:
            doc = {
                "timestamp": datetime.utcnow(),
                "node_id": packet.get("node_id", 45),
                "angle_x": packet.get("angleX", 0.0),
                "angle_y": packet.get("angleY", 0.0),
                "vibration": packet.get("vibration", 0.0),
                "temperature": packet.get("temperature", 25.0),
                "humidity": packet.get("humidity", 60.0),
                "soil_moisture": packet.get("moisture", 0.0),
                "force_level": packet.get("forceLevel", 0.0),
                "packet_id": packet.get("packetId", 0),
                "raw_timestamp": packet.get("timestamp")
            }
            self.db.hardware_telemetry.insert_one(doc)
            return True
        except Exception as e:
            print(f"[MongoDB] Error inserting hardware telemetry: {e}")
            return False

    def store_dual_telemetry(self, payload: Dict[str, Any]) -> bool:
        """Stores unified dual-node telemetry snapshot (Node 1 HX711/Impact + Node 2 Trekker + Fused)."""
        if not self.connected or self.db is None:
            return False
        try:
            doc = {
                "timestamp": datetime.utcnow(),
                "node1": payload.get("node1_hx711_impact", {}),
                "node2": payload.get("node2_trekker", {}),
                "fused": payload.get("fused_telemetry", {}),
                "source": "dual_hardware_hub"
            }
            self.db.hardware_telemetry.insert_one(doc)
            return True
        except Exception as e:
            print(f"[MongoDB] Error inserting dual telemetry: {e}")
            return False

    def store_aiml_prediction(self, prediction: Dict[str, Any]) -> bool:
        """Stores AI/ML subsidence forecast, DGMS risk tier and TTC."""
        if not self.connected or self.db is None:
            return False
        try:
            doc = {
                "timestamp": datetime.utcnow(),
                "node_id": prediction.get("node_id", 45),
                "disp_corr_mm": prediction.get("disp_corr_mm", 0.0),
                "tilt_deg": prediction.get("tilt_deg", 0.0),
                "vibration_rms": prediction.get("vibration_rms", 0.0),
                "temp_c": prediction.get("temp_c", 25.0),
                "velocity_mm_h": prediction.get("velocity_mm_h", 0.0),
                "pred_subsidence_24h_mm": prediction.get("pred_subsidence_24h_mm", 0.0),
                "dgms_risk_tier": prediction.get("dgms_risk_tier", "SAFE"),
                "ttc_hours": prediction.get("ttc_hours", 999.0),
                "cli_command": prediction.get("cli_command", "")
            }
            self.db.aiml_predictions.insert_one(doc)
            return True
        except Exception as e:
            print(f"[MongoDB] Error inserting AI/ML prediction: {e}")
            return False

    def store_heatmap_nodes(self, nodes: List[Dict[str, Any]]) -> bool:
        """Stores or updates 10x10 surface grid heatmap nodes."""
        if not self.connected or self.db is None:
            return False
        try:
            for n in nodes:
                node_id = n.get("node_id", n.get("id"))
                if node_id is None:
                    continue
                self.db.heatmap_nodes.update_one(
                    {"node_id": node_id},
                    {"$set": {
                        "node_id": node_id,
                        "x": n.get("x", 0),
                        "y": n.get("y", 0),
                        "disp_mm": n.get("disp_mm", 0.0),
                        "risk_tier": n.get("risk_tier", "SAFE"),
                        "last_updated": datetime.utcnow()
                    }},
                    upsert=True
                )
            return True
        except Exception as e:
            print(f"[MongoDB] Error updating heatmap nodes: {e}")
            return False

    def store_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Stores system alert or emergency trigger."""
        if not self.connected or self.db is None:
            return False
        try:
            doc = {
                "timestamp": datetime.utcnow(),
                "node_id": alert_data.get("node_id", 45),
                "level": alert_data.get("level", "WARNING"),
                "message": alert_data.get("message", ""),
                "acknowledged": False
            }
            self.db.system_alerts.insert_one(doc)
            return True
        except Exception as e:
            print(f"[MongoDB] Error inserting alert: {e}")
            return False

    def store_dual_telemetry(self, payload: Dict[str, Any]) -> bool:
        """Stores consolidated dual-hardware telemetry frame into MongoDB."""
        if not self.connected or self.db is None:
            return False
        try:
            n1 = payload.get("node1_hx711_impact", {})
            n2 = payload.get("node2_trekker", {})
            fused = payload.get("fused_telemetry", {})
            doc = {
                "timestamp": datetime.utcnow(),
                "time_str": payload.get("timestamp", time.strftime("%H:%M:%S")),
                "node1": {
                    "raw_load": n1.get("raw_load", 0),
                    "load_change": n1.get("load_change", 0),
                    "zero_offset": n1.get("zero_offset", 0),
                    "adxl_mag": n1.get("adxl_mag", 1.0),
                    "adxl_peak": n1.get("adxl_peak", 0.0),
                    "mpu_mag": n1.get("mpu_mag", 1.0),
                    "mpu_peak": n1.get("mpu_peak", 0.0),
                    "last_impact": n1.get("last_impact")
                },
                "node2": {
                    "accel": n2.get("accel", [0.0, 0.0, 1.0]),
                    "gyro": n2.get("gyro", [0.0, 0.0, 0.0]),
                    "temperature_c": n2.get("temperature_c", 25.0),
                    "soil_raw": n2.get("soil_raw", 0),
                    "moisture_pct": n2.get("moisture_pct", 0)
                },
                "fused": {
                    "displacement_mm": fused.get("displacement_mm", 0.0),
                    "tilt_deg": fused.get("tilt_deg", 0.0),
                    "vibration_level": fused.get("vibration_level", 0.0),
                    "temperature_c": fused.get("temperature_c", 25.0),
                    "moisture_pct": fused.get("moisture_pct", 0.0),
                    "force_level": fused.get("force_level", 0),
                    "ttc_hours": fused.get("ttc_hours", 0.0),
                    "dgms_tier": fused.get("dgms_tier", "SAFE")
                }
            }
            self.db.hardware_telemetry.insert_one(doc)
            return True
        except Exception as e:
            print(f"[MongoDB] Error inserting dual telemetry: {e}")
            return False

    def get_recent_hardware_records(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieves recent telemetry records for web display."""
        if not self.connected or self.db is None:
            return []
        try:
            records = []
            cursor = self.db.hardware_telemetry.find().sort("timestamp", pymongo.DESCENDING).limit(limit)
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                if isinstance(doc.get("timestamp"), datetime):
                    doc["timestamp_iso"] = doc["timestamp"].isoformat()
                    doc["timestamp"] = doc["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                records.append(doc)
            return records
        except Exception as e:
            print(f"[MongoDB] Error reading records: {e}")
            return []

    def get_latest_stats(self) -> Dict[str, Any]:
        """Returns collection document counts."""
        if not self.connected or self.db is None:
            return {"connected": False}
        return {
            "connected": True,
            "hardware_telemetry_count": self.db.hardware_telemetry.count_documents({}),
            "aiml_predictions_count": self.db.aiml_predictions.count_documents({}),
            "heatmap_nodes_count": self.db.heatmap_nodes.count_documents({}),
            "system_alerts_count": self.db.system_alerts.count_documents({})
        }


# Singleton instance
mongo_manager = MongoManager()
