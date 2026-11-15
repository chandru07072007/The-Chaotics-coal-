"""
dual_hardware_manager.py — Multi-Port Dual Hardware Serial Telemetry Hub
========================================================================
Supports concurrent dual-hardware connection over 2 distinct serial COM ports:

Node 1: ESP32 HX711 Load Cell + ADXL345 (SPI) + MPU6500 (I2C)
  - Pins: HX711 (DT:16, SCK:4), ADXL345 SPI (SCK:18, MISO:19, MOSI:23, CS:5), MPU6500 I2C (SDA:21, SCL:22, 0x68)
  - Output Stream: t_ms,raw,change,adxl_mag,adxl_peak,mpu_mag,mpu_peak
  - Impact events: "IMPACT at %lu ms | First: %s | Gap: %ld us | ADXL: %.2f g | MPU: %.2f g"

Node 2: ESP32 Mountain Trekker Safety Watch (MPU6050 + Dallas DS18B20 + Soil Moisture)
  - Pins: MPU6050 I2C (SDA:21, SCL:22, 0x68), Dallas DS18B20 1-Wire (Pin 2), Soil Moisture Analog (Pin A0 / GPIO 36)
  - Output Stream: Accel X/Y/Z (g), Gyro X/Y/Z (°/s), Temperature (°C), Soil Moisture Raw
"""

from __future__ import annotations
import json
import math
import random
import re
import threading
import time
from typing import Dict, Any, List, Optional
import serial
import serial.tools.list_ports

try:
    from mongo_manager import mongo_manager
except ImportError:
    try:
        from hardware.mongo_manager import mongo_manager
    except ImportError:
        mongo_manager = None


class SinglePortReader:
    def __init__(self, node_type: str, default_id: int):
        self.node_type = node_type  # "NODE_1_IMPACT_LOAD" or "NODE_2_TREKKER"
        self.node_id = default_id
        self.port = None
        self.baudrate = 115200
        self.ser = None
        self.connected = False
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        self.packet_count = 0
        self.last_update = None
        self.data: Dict[str, Any] = self._init_data()
        self.raw_lines: List[Dict[str, str]] = []
        self.impact_history: List[Dict[str, Any]] = []

    def _init_data(self) -> Dict[str, Any]:
        if self.node_type == "NODE_1_IMPACT_LOAD":
            return {
                "t_ms": 0,
                "zero_offset": 8344000,
                "hx711_raw": 8345420,
                "hx711_change": 1420,
                "adxl_mag": 1.002,
                "adxl_peak": 0.045,
                "mpu_mag": 0.998,
                "mpu_peak": 0.038,
                "last_impact": None,
                "last_impact_parsed": {
                    "at_ms": 0,
                    "first": "ADXL345",
                    "gap_us": 120,
                    "adxl_g": 0.85,
                    "mpu_g": 0.62
                },
                "connected": False
            }
        else:
            return {
                "accel_x": 0.02,
                "accel_y": -0.01,
                "accel_z": 0.98,
                "gyro_x": 0.12,
                "gyro_y": -0.08,
                "gyro_z": 0.05,
                "temperature": 24.62,
                "soil_raw": 1780,
                "moisture_pct": 56.5,
                "connected": False
            }

    def connect(self, port_name: str, baud: int = 115200) -> bool:
        self.disconnect()
        if not port_name or port_name == "SIMULATED":
            return False
        with self.lock:
            try:
                self.ser = serial.Serial(port_name, baud, timeout=1.0)
                self.port = port_name
                self.baudrate = baud
                self.connected = True
                self.running = True
                self.thread = threading.Thread(target=self._loop, daemon=True)
                self.thread.start()
                print(f"[{self.node_type}] Connected to {port_name} at {baud} baud")
                return True
            except Exception as e:
                print(f"[{self.node_type}] Connection failed to {port_name}: {e}")
                self.connected = False
                return False

    def disconnect(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.8)
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            self.connected = False

    def _loop(self):
        buffer = ""
        while self.running:
            try:
                if not self.ser or not self.ser.is_open:
                    time.sleep(0.1)
                    continue
                chunk = self.ser.read(self.ser.in_waiting or 1)
                if chunk:
                    text = chunk.decode("utf-8", errors="replace")
                    buffer += text
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        self._parse_line(line.strip())
            except Exception:
                time.sleep(0.1)

    def _parse_line(self, line: str):
        if not line:
            return
        ts = time.strftime("%H:%M:%S")
        self.raw_lines.append({"time": ts, "text": line})
        if len(self.raw_lines) > 50:
            self.raw_lines.pop(0)

        # Parse Node 1: CSV format: t_ms,raw,change,adxl_mag,adxl_peak,mpu_mag,mpu_peak
        if self.node_type == "NODE_1_IMPACT_LOAD":
            if line.startswith("HX711 Zero Offset:"):
                try:
                    val = int(re.search(r"[-+]?\d+", line).group(0))
                    self.data["zero_offset"] = val
                except Exception:
                    pass
                return

            if line.startswith("IMPACT at"):
                self.data["last_impact"] = line
                # Parse: "IMPACT at 12345 ms | First: ADXL345 | Gap: 240 us | ADXL: 1.25 g | MPU: 0.98 g"
                try:
                    at_match = re.search(r"IMPACT at (\d+)", line)
                    first_match = re.search(r"First:\s*([^|]+)", line)
                    gap_match = re.search(r"Gap:\s*(\d+)", line)
                    adxl_match = re.search(r"ADXL:\s*([\d\.]+)", line)
                    mpu_match = re.search(r"MPU:\s*([\d\.]+)", line)
                    
                    impact_obj = {
                        "time": ts,
                        "at_ms": int(at_match.group(1)) if at_match else int(time.time()*1000),
                        "first": first_match.group(1).strip() if first_match else "Unknown",
                        "gap_us": int(gap_match.group(1)) if gap_match else 0,
                        "adxl_g": float(adxl_match.group(1)) if adxl_match else 0.0,
                        "mpu_g": float(mpu_match.group(1)) if mpu_match else 0.0,
                        "raw_line": line
                    }
                    self.data["last_impact_parsed"] = impact_obj
                    self.impact_history.append(impact_obj)
                    if len(self.impact_history) > 20:
                        self.impact_history.pop(0)
                except Exception as e:
                    print("Impact parse error:", e)
                return

            parts = line.split(",")
            if len(parts) == 7:
                try:
                    self.data["t_ms"] = int(parts[0])
                    self.data["hx711_raw"] = int(parts[1])
                    self.data["hx711_change"] = int(parts[2])
                    self.data["adxl_mag"] = float(parts[3])
                    self.data["adxl_peak"] = float(parts[4])
                    self.data["mpu_mag"] = float(parts[5])
                    self.data["mpu_peak"] = float(parts[6])
                    self.packet_count += 1
                    self.last_update = time.time()
                except ValueError:
                    pass

        # Parse Node 2: Mountain Trekker Safety Watch (MPU6050 + Dallas + Soil)
        elif self.node_type == "NODE_2_TREKKER":
            try:
                if line.startswith("Accel X:"):
                    self.data["accel_x"] = float(re.search(r"[-+]?\d*\.\d+|\d+", line).group(0))
                elif line.startswith("Accel Y:"):
                    self.data["accel_y"] = float(re.search(r"[-+]?\d*\.\d+|\d+", line).group(0))
                elif line.startswith("Accel Z:"):
                    self.data["accel_z"] = float(re.search(r"[-+]?\d*\.\d+|\d+", line).group(0))
                elif line.startswith("Gyro X:"):
                    self.data["gyro_x"] = float(re.search(r"[-+]?\d*\.\d+|\d+", line).group(0))
                elif line.startswith("Gyro Y:"):
                    self.data["gyro_y"] = float(re.search(r"[-+]?\d*\.\d+|\d+", line).group(0))
                elif line.startswith("Gyro Z:"):
                    self.data["gyro_z"] = float(re.search(r"[-+]?\d*\.\d+|\d+", line).group(0))
                elif line.startswith("Temperature:"):
                    self.data["temperature"] = float(re.search(r"[-+]?\d*\.\d+|\d+", line).group(0))
                elif line.startswith("Raw Value:"):
                    val = int(re.search(r"\d+", line).group(0))
                    self.data["soil_raw"] = val
                    # Approximate percentage: 4095 is dry, ~1200 is saturated
                    pct = round(max(0.0, min(100.0, ((4095 - val) / 2895.0) * 100.0)), 1)
                    self.data["moisture_pct"] = pct
                    self.packet_count += 1
                    self.last_update = time.time()
            except Exception:
                pass


class DualHardwareHub:
    """Manages simultaneous two-port connections and feeds the single unified platform."""
    def __init__(self):
        self.node1 = SinglePortReader("NODE_1_IMPACT_LOAD", default_id=1)
        self.node2 = SinglePortReader("NODE_2_TREKKER", default_id=2)
        self.simulation_enabled = True
        self._sim_thread = threading.Thread(target=self._sim_worker, daemon=True)
        self._sim_thread.start()

    def list_available_ports(self) -> List[Dict[str, Any]]:
        ports = []
        for p in serial.tools.list_ports.comports():
            desc = p.description or p.device
            ports.append({
                "device": p.device,
                "description": desc,
                "hwid": p.hwid or ""
            })
        ports.sort(key=lambda x: x["device"])
        return ports

    def auto_connect_if_available(self):
        """Auto detects 2 distinct USB COM ports if plugged in."""
        ports = [p["device"] for p in self.list_available_ports()]
        if len(ports) >= 1 and not self.node1.connected:
            self.node1.connect(ports[0])
        if len(ports) >= 2 and not self.node2.connected:
            self.node2.connect(ports[1])

    def _sim_worker(self):
        """Generates realistic synthetic telemetry lines when physical ports are not connected."""
        t_ms = 1000
        sim_raw = 8344000
        while True:
            time.sleep(0.2)
            now_ts = time.strftime("%H:%M:%S")

            # Simulate Node 1 if not connected
            if not self.node1.connected and self.simulation_enabled:
                t_ms += 200
                drift = int(random.gauss(0, 15))
                sim_raw += drift
                offset = self.node1.data.get("zero_offset", 8344000)
                change = sim_raw - offset
                
                adxl_mag = round(1.0 + random.gauss(0, 0.015), 3)
                mpu_mag = round(1.0 + random.gauss(0, 0.012), 3)
                adxl_peak = round(abs(adxl_mag - 1.0) + random.uniform(0.01, 0.04), 3)
                mpu_peak = round(abs(mpu_mag - 1.0) + random.uniform(0.01, 0.03), 3)

                line = f"{t_ms},{sim_raw},{change},{adxl_mag:.3f},{adxl_peak:.3f},{mpu_mag:.3f},{mpu_peak:.3f}"
                self.node1.data.update({
                    "t_ms": t_ms,
                    "hx711_raw": sim_raw,
                    "hx711_change": change,
                    "adxl_mag": adxl_mag,
                    "adxl_peak": adxl_peak,
                    "mpu_mag": mpu_mag,
                    "mpu_peak": mpu_peak,
                })
                self.node1.raw_lines.append({"time": now_ts, "text": line})
                if len(self.node1.raw_lines) > 50:
                    self.node1.raw_lines.pop(0)

                # Periodic micro-seismic shock simulation
                if random.random() < 0.04:
                    gap_us = random.randint(45, 320)
                    adxl_g = round(random.uniform(0.65, 1.45), 2)
                    mpu_g = round(random.uniform(0.55, 1.30), 2)
                    first_sensor = "ADXL345" if random.random() > 0.5 else "MPU6500"
                    imp_line = f"IMPACT at {t_ms} ms | First: {first_sensor} | Gap: {gap_us} us | ADXL: {adxl_g:.2f} g | MPU: {mpu_g:.2f} g"
                    self.node1.data["last_impact"] = imp_line
                    imp_obj = {
                        "time": now_ts,
                        "at_ms": t_ms,
                        "first": first_sensor,
                        "gap_us": gap_us,
                        "adxl_g": adxl_g,
                        "mpu_g": mpu_g,
                        "raw_line": imp_line
                    }
                    self.node1.data["last_impact_parsed"] = imp_obj
                    self.node1.impact_history.append(imp_obj)
                    if len(self.node1.impact_history) > 20:
                        self.node1.impact_history.pop(0)
                    self.node1.raw_lines.append({"time": now_ts, "text": imp_line})

            # Simulate Node 2 if not connected
            if not self.node2.connected and self.simulation_enabled:
                ax = round(random.gauss(0.02, 0.01), 3)
                ay = round(random.gauss(-0.01, 0.01), 3)
                az = round(random.gauss(0.98, 0.01), 3)
                gx = round(random.gauss(0.05, 0.08), 2)
                gy = round(random.gauss(-0.02, 0.07), 2)
                gz = round(random.gauss(0.04, 0.06), 2)
                temp = round(24.5 + random.gauss(0, 0.15), 2)
                soil_raw = int(1750 + random.gauss(0, 20))
                pct = round(max(0.0, min(100.0, ((4095 - soil_raw) / 2895.0) * 100.0)), 1)

                self.node2.data.update({
                    "accel_x": ax,
                    "accel_y": ay,
                    "accel_z": az,
                    "gyro_x": gx,
                    "gyro_y": gy,
                    "gyro_z": gz,
                    "temperature": temp,
                    "soil_raw": soil_raw,
                    "moisture_pct": pct
                })

                lines_to_add = [
                    "--- MPU6050 ---",
                    f"Accel X: {ax:.4f} g",
                    f"Accel Y: {ay:.4f} g",
                    f"Accel Z: {az:.4f} g",
                    f"Gyro X: {gx:.2f}",
                    f"Gyro Y: {gy:.2f}",
                    f"Gyro Z: {gz:.2f}",
                    "--- DALLAS DS18B20 ---",
                    f"Temperature: {temp:.2f} C",
                    "--- SOIL MOISTURE ---",
                    f"Raw Value: {soil_raw}",
                    "============================"
                ]
                for l in lines_to_add:
                    self.node2.raw_lines.append({"time": now_ts, "text": l})
                if len(self.node2.raw_lines) > 50:
                    self.node2.raw_lines = self.node2.raw_lines[-50:]

    def get_unified_payload(self) -> Dict[str, Any]:
        """Merges telemetry from both ports into a single consolidated dashboard packet."""
        n1 = self.node1.data
        n2 = self.node2.data

        # Combined fused metrics for MUNKANIPPU Subsidence & Digital Twin:
        # Load cell strain + ADXL vibration + MPU6050 tilt + Dallas temp + Soil moisture
        tilt = round(math.sqrt(n2.get("accel_x", 0.0)**2 + n2.get("accel_y", 0.0)**2) * 10.0, 2)
        vibration = round(max(n1.get("adxl_peak", 0.0), n1.get("mpu_peak", 0.0), abs(n2.get("gyro_z", 0.0))), 3)
        load_change = n1.get("hx711_change", 0)
        temp = n2.get("temperature", 24.6)
        moisture = n2.get("moisture_pct", 55.0)
        
        # Ground displacement proxy (mm)
        disp = round(abs(load_change) * 0.02 + tilt * 0.8 + 38.5, 2)
        # Force percentage (0-100)
        force_level = max(5, min(98, int(abs(load_change) / 25.0) + 40))

        # Time To Critical (hrs) estimation
        ttc = round(max(0.8, 12.0 - (disp * 0.18) - (vibration * 4.0)), 2)

        # DGMS Risk classification
        if disp > 80 or vibration > 0.5:
            dgms = "CRITICAL"
        elif disp > 50 or vibration > 0.25:
            dgms = "WARNING"
        elif disp > 30:
            dgms = "ADVISORY"
        else:
            dgms = "SAFE"

        payload = {
            "ok": True,
            "timestamp": time.strftime("%H:%M:%S"),
            "node1_hx711_impact": {
                "port": self.node1.port,
                "connected": self.node1.connected,
                "packets": self.node1.packet_count,
                "t_ms": n1.get("t_ms", 0),
                "zero_offset": n1.get("zero_offset", 8344000),
                "raw_load": n1.get("hx711_raw", 0),
                "load_change": n1.get("hx711_change", 0),
                "adxl_mag": n1.get("adxl_mag", 1.0),
                "adxl_peak": n1.get("adxl_peak", 0.0),
                "mpu_mag": n1.get("mpu_mag", 1.0),
                "mpu_peak": n1.get("mpu_peak", 0.0),
                "last_impact": n1.get("last_impact"),
                "last_impact_parsed": n1.get("last_impact_parsed"),
                "impact_history": self.node1.impact_history[-5:],
                "recent_lines": self.node1.raw_lines[-15:]
            },
            "node2_trekker": {
                "port": self.node2.port,
                "connected": self.node2.connected,
                "packets": self.node2.packet_count,
                "accel": [n2.get("accel_x", 0.0), n2.get("accel_y", 0.0), n2.get("accel_z", 1.0)],
                "gyro": [n2.get("gyro_x", 0.0), n2.get("gyro_y", 0.0), n2.get("gyro_z", 0.0)],
                "temperature_c": temp,
                "soil_raw": n2.get("soil_raw", 0),
                "moisture_pct": moisture,
                "recent_lines": self.node2.raw_lines[-15:]
            },
            "fused_telemetry": {
                "displacement_mm": disp,
                "tilt_deg": tilt,
                "vibration_level": vibration,
                "temperature_c": temp,
                "moisture_pct": moisture,
                "force_level": force_level,
                "ttc_hours": ttc,
                "dgms_tier": dgms
            }
        }

        # Auto-persist snapshot to MongoDB
        if mongo_manager and mongo_manager.connected:
            try:
                mongo_manager.store_dual_telemetry(payload)
            except Exception as e:
                print("[MongoDB Auto-Persist Error]:", e)

        # Parallel write to TimescaleDB
        try:
            from timescale_manager import timescale_manager
            if timescale_manager and timescale_manager.connected:
                timescale_manager.store(payload)
        except Exception:
            pass

        return payload


dual_hardware_hub = DualHardwareHub()
