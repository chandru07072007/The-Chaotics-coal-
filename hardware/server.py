import json
import math
import os
import re
import threading
import time
from collections import deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import serial
import serial.tools.list_ports

try:
    from mongo_manager import mongo_manager
except ImportError:
    try:
        from hardware.mongo_manager import mongo_manager
    except ImportError:
        mongo_manager = None

try:
    from python_digital_twin import python_digital_twin
except ImportError:
    try:
        from hardware.python_digital_twin import python_digital_twin
    except ImportError:
        python_digital_twin = None

try:
    from dual_hardware_manager import dual_hardware_hub
except ImportError:
    try:
        from hardware.dual_hardware_manager import dual_hardware_hub
    except ImportError:
        dual_hardware_hub = None

try:
    from mqtt_bridge import mqtt_bridge
except ImportError:
    try:
        from hardware.mqtt_bridge import mqtt_bridge
    except ImportError:
        mqtt_bridge = None

try:
    from timescale_manager import timescale_manager
except ImportError:
    try:
        from hardware.timescale_manager import timescale_manager
    except ImportError:
        timescale_manager = None

try:
    from microclimate_model import microclimate_model
except ImportError:
    try:
        from hardware.microclimate_model import microclimate_model
    except ImportError:
        microclimate_model = None

try:
    from safety_routing import dijkstra_safety
except ImportError:
    try:
        from hardware.safety_routing import dijkstra_safety
    except ImportError:
        dijkstra_safety = None

try:
    import sensorthings_api
except ImportError:
    try:
        from hardware import sensorthings_api
    except ImportError:
        sensorthings_api = None


class SerialManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.ser = None
        self.port = None
        self.port_description = ""
        self.baudrate = 115200
        self.connected = False
        self.error = None
        self.running = False
        self.reader_thread = None
        self.packet_count = 0
        self.connected_at = None
        self.last_update = None

        # Current parsed state
        self.current_section = None
        self.working_data = self._default_data()
        self.latest_data = self._default_data()
        self.raw_lines = []  # circular buffer of last 150 lines
        self.clients = []    # SSE queues

    def _default_data(self):
        return {
            "angleX": 0.0,
            "percentageX": 0.0,
            "angleY": 0.0,
            "percentageY": 0.0,
            "vibration": 0.0,
            "vibrationLevel": 0.0,
            "temperature": None,
            "humidity": None,
            "dhtOk": True,
            "soilRaw": 0,
            "moisture": 0,
            "fsrRaw": 0,
            "forceLevel": 0,
            "timestamp": None,
            "packetId": 0,
        }

    def list_ports(self):
        ports = []
        for p in serial.tools.list_ports.comports():
            desc = p.description or p.device
            hwid = p.hwid or ""
            is_usb = (
                "USB" in desc.upper()
                or "CH9102" in desc.upper()
                or "CH340" in desc.upper()
                or "CP210" in desc.upper()
                or "FTDI" in desc.upper()
                or "USB" in hwid.upper()
            )
            ports.append({
                "device": p.device,
                "description": desc,
                "hwid": hwid,
                "manufacturer": p.manufacturer or "",
                "isUsb": is_usb,
            })
        # Sort USB ports first, then by port number
        ports.sort(key=lambda x: (not x["isUsb"], x["device"]))
        return ports

    def auto_connect(self):
        ports = self.list_ports()
        usb_ports = [p for p in ports if p["isUsb"]]
        target = usb_ports[0]["device"] if usb_ports else (ports[0]["device"] if ports else None)
        if target:
            self.connect(target, 115200)

    def connect(self, port, baudrate=115200):
        self.disconnect()
        with self.lock:
            try:
                self.ser = serial.Serial(port=port, baudrate=int(baudrate), timeout=0.5)
                self.port = port
                self.baudrate = int(baudrate)
                self.connected = True
                self.error = None
                self.connected_at = time.time()
                # Find port description
                self.port_description = port
                for p in self.list_ports():
                    if p["device"].upper() == port.upper():
                        self.port_description = p["description"]
                        break

                self.running = True
                self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
                self.reader_thread.start()
                self._broadcast("status", self.get_status())
                return True, f"Connected to {self.port_description}"
            except Exception as e:
                self.connected = False
                self.error = str(e)
                self.ser = None
                self._broadcast("status", self.get_status())
                return False, str(e)

    def disconnect(self):
        self.running = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.5)
        with self.lock:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
            self.connected = False
            self.connected_at = None
        self._broadcast("status", self.get_status())

    def get_status(self):
        return {
            "connected": self.connected,
            "port": self.port,
            "portDescription": self.port_description,
            "baudrate": self.baudrate,
            "error": self.error,
            "packetCount": self.packet_count,
            "connectedAt": self.connected_at,
            "lastUpdate": self.last_update,
            "data": self.latest_data,
            "ports": self.list_ports(),
        }

    def _broadcast(self, event_type, payload):
        msg = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
        dead = []
        for q in list(self.clients):
            try:
                q.append(msg)
            except Exception:
                dead.append(q)
        for q in dead:
            if q in self.clients:
                self.clients.remove(q)

    def _parse_line(self, line):
        clean = line.strip()
        if not clean:
            return

        # Record raw line
        ts_str = time.strftime("%H:%M:%S")
        raw_entry = {"time": ts_str, "text": clean}
        self.raw_lines.append(raw_entry)
        if len(self.raw_lines) > 150:
            self.raw_lines.pop(0)
        self._broadcast("raw", raw_entry)

        # Detect section headers
        if "MPU6050" in clean and "===" in clean:
            self.current_section = "MPU6050"
            return
        elif "DHT11" in clean and "---" in clean:
            self.current_section = "DHT11"
            return
        elif "SOIL MOISTURE" in clean and "---" in clean:
            self.current_section = "SOIL"
            return
        elif "FSR" in clean and "---" in clean:
            self.current_section = "FSR"
            return
        elif "SENSOR DATA" in clean:
            self.current_section = "HEADER"
            return

        # Extract numeric value helper
        num_match = re.search(r"([-+]?\d+(?:\.\d+)?)", clean.split(":", 1)[-1] if ":" in clean else clean)
        val = float(num_match.group(1)) if num_match else None

        if clean.startswith("Angle X") and val is not None:
            if "deg" in clean:
                self.working_data["angleX"] = val
            elif "%" in clean:
                self.working_data["percentageX"] = val

        elif clean.startswith("Angle Y") and val is not None:
            if "deg" in clean:
                self.working_data["angleY"] = val
            elif "%" in clean:
                self.working_data["percentageY"] = val

        elif clean.startswith("Vibration Level") and val is not None:
            self.working_data["vibrationLevel"] = val

        elif clean.startswith("Vibration") and val is not None:
            self.working_data["vibration"] = val

        elif "DHT11 reading failed" in clean:
            self.working_data["dhtOk"] = False

        elif clean.startswith("Temperature") and val is not None:
            self.working_data["temperature"] = val
            self.working_data["dhtOk"] = True

        elif clean.startswith("Humidity") and val is not None:
            self.working_data["humidity"] = val
            self.working_data["dhtOk"] = True

        elif clean.startswith("Raw Value") and val is not None:
            if self.current_section == "SOIL":
                self.working_data["soilRaw"] = int(val)
            elif self.current_section == "FSR":
                self.working_data["fsrRaw"] = int(val)

        elif clean.startswith("Moisture") and val is not None:
            self.working_data["moisture"] = int(val)

        elif clean.startswith("Force Level") and val is not None:
            self.working_data["forceLevel"] = int(val)
            # Force Level is the final measurement in each loop iteration!
            self._commit_packet()

    def _commit_packet(self):
        now = time.time()
        self.packet_count += 1
        self.last_update = now
        self.working_data["timestamp"] = now
        self.working_data["packetId"] = self.packet_count
        self.latest_data = dict(self.working_data)

        # Persist to MongoDB
        if mongo_manager and mongo_manager.connected:
            mongo_manager.store_hardware_telemetry(self.latest_data)

        # Synchronize with Python Digital Twin Mesh
        if python_digital_twin:
            python_digital_twin.sync_hardware_packet(45, self.latest_data)

        self._broadcast("sensor_data", {
            "data": self.latest_data,
            "packetCount": self.packet_count,
            "lastUpdate": self.last_update,
            "port": self.port,
            "portDescription": self.port_description,
        })

    def _read_loop(self):
        buffer = ""
        while self.running:
            try:
                if not self.ser or not self.ser.is_open:
                    time.sleep(0.2)
                    continue
                chunk = self.ser.read(self.ser.in_waiting or 1)
                if chunk:
                    text = chunk.decode("utf-8", errors="replace")
                    buffer += text
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        self._parse_line(line)
            except serial.SerialException as e:
                self.connected = False
                self.error = f"Serial connection lost: {e}"
                self._broadcast("status", self.get_status())
                break
            except Exception as e:
                time.sleep(0.1)


manager = SerialManager()
ai_sample_window = deque(maxlen=20)
ai_sample_lock = threading.Lock()


def record_ai_sample(payload):
    """Keep one-second dual-node samples for the next 20-second AI average."""
    fused = payload.get("fused_telemetry", {})
    node2 = payload.get("node2_trekker", {})
    sample = {
        "displacement": float(fused.get("displacement_mm") or 2.5),
        "tilt": float(fused.get("tilt_deg") or 0.0),
        "vibration_g": float(fused.get("vibration_level") or 0.1),
        "temperature": float(node2.get("temperature_c") or 25.0),
    }
    with ai_sample_lock:
        ai_sample_window.append(sample)


def average_ai_samples():
    with ai_sample_lock:
        samples = list(ai_sample_window)
    if not samples:
        return None, 0
    return {
        key: sum(sample[key] for sample in samples) / len(samples)
        for key in samples[0]
    }, len(samples)


class DashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet standard polling logs
        pass

    @staticmethod
    def _project_root():
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    @classmethod
    def _first_existing_file(cls, candidates):
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static_file(self, filepath, content_type=None):
        if not os.path.isfile(filepath):
            self.send_error(404, "File Not Found")
            return
        if content_type is None:
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".js": "application/javascript",
                ".css": "text/css",
                ".json": "application/json",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
            }
            content_type = content_types.get(
                os.path.splitext(filepath)[1].lower(),
                "application/octet-stream",
            )
        with open(filepath, "rb") as file:
            content = file.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def end_headers(self):
        self.send_header("X-Frame-Options", "ALLOWALL")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/dual/status":
            if dual_hardware_hub:
                payload = dual_hardware_hub.get_unified_payload()
                record_ai_sample(payload)
                self._send_json(payload)
            else:
                self._send_json({"ok": False, "error": "Dual hardware hub unavailable"})
            return
        elif parsed.path == "/api/dual/connect":
            node_idx = int(query.get("node", ["1"])[0])
            port_name = query.get("port", [""])[0]
            baud_val = int(query.get("baud", ["115200"])[0])
            if dual_hardware_hub:
                if node_idx == 1:
                    res = dual_hardware_hub.node1.connect(port_name, baud_val)
                else:
                    res = dual_hardware_hub.node2.connect(port_name, baud_val)
                self._send_json({"ok": res, "connected": res, "node": node_idx, "port": port_name})
            else:
                self._send_json({"ok": False, "error": "Dual hardware hub not available"})
            return
        elif parsed.path == "/api/status":
            self._send_json(manager.get_status())
            return
        elif parsed.path == "/api/telemetry":
            self._send_json({
                "ok": True,
                "latest": manager.latest_data,
                "packetCount": manager.packet_count,
                "lastUpdate": manager.last_update,
                "connected": manager.connected,
                "port": manager.port,
            })
            return
        elif parsed.path == "/api/ai_prediction":
            if dual_hardware_hub:
                telemetry = dual_hardware_hub.get_unified_payload()
                node2 = telemetry.get("node2_trekker", {})
                fused = telemetry.get("fused_telemetry", {})
                averaged, sample_count = average_ai_samples()
                source = averaged or {
                    "displacement": float(fused.get("displacement_mm") or 2.5),
                    "tilt": float(fused.get("tilt_deg") or 0.0),
                    "vibration_g": float(fused.get("vibration_level") or 0.1),
                    "temperature": float(node2.get("temperature_c") or 25.0),
                }
                tilt = round(source["tilt"], 2)
                vibration_g = source["vibration_g"]
                vibration = round(vibration_g * 9.81, 2)
                temperature = round(source["temperature"], 2)
                displacement = round(source["displacement"], 2)
            else:
                data = manager.latest_data
                tilt = round(
                    (data.get("angleX", 0) ** 2 + data.get("angleY", 0) ** 2) ** 0.5,
                    2,
                )
                vibration = float(data.get("vibration") or 0.1)
                force = float(data.get("forceLevel") or 5.0)
                temperature = float(data.get("temperature") or 25.0)
                displacement = round((force * 0.5) - (temperature - 24.6) * 0.05, 2)
            velocity = round(vibration * 0.18, 2)
            predicted_24h = round(displacement + velocity * 24.0, 2)

            if abs(predicted_24h) >= 50.0:
                risk_tier = "CRITICAL"
            elif abs(predicted_24h) >= 25.0:
                risk_tier = "WARNING"
            elif abs(predicted_24h) >= 10.0:
                risk_tier = "ADVISORY"
            else:
                risk_tier = "SAFE"

            if abs(displacement) >= 50.0:
                ttc = 0.0
            elif velocity > 0.05:
                ttc = round((50.0 - abs(displacement)) / velocity, 2)
            else:
                ttc = 999.0
            command = (
                f"python main.py --node-id 45 --disp {displacement:.1f} "
                f"--tilt {tilt:.1f} --vib {vibration:.2f} "
                f"--temp {temperature:.1f} --vel {velocity:.1f}"
            )
            prediction_payload = {
                "ok": True,
                "node_id": 45,
                "disp_corr_mm": displacement,
                "tilt_deg": tilt,
                "vibration_rms": vibration,
                "temp_c": temperature,
                "velocity_mm_h": velocity,
                "pred_subsidence_24h_mm": predicted_24h,
                "dgms_risk_tier": risk_tier,
                "ttc_hours": ttc,
                "cli_command": command,
                "updated_at": time.time(),
                "refresh_interval_seconds": 20,
                "averaging_window_seconds": 20,
                "sample_count": sample_count if dual_hardware_hub else 1,
            }
            if mongo_manager and mongo_manager.connected:
                mongo_manager.store_aiml_prediction(prediction_payload)

            self._send_json(prediction_payload)
            return
        elif parsed.path == "/api/heatmap":
            nodes = []
            data = manager.latest_data
            force = float(data.get("forceLevel") or 0)
            for row in range(10):
                for column in range(10):
                    node_id = row * 10 + column
                    distance = ((column - 5) ** 2 + (row - 4) ** 2) ** 0.5
                    factor = max(0.0, 1.0 - distance / 5.5)
                    displacement = round(
                        factor * (force * 0.45) + (1.0 - factor) * 4.2,
                        2,
                    )
                    nodes.append({
                        "node_id": node_id,
                        "grid_x": column * 10.0,
                        "grid_y": row * 10.0,
                        "disp_mm": displacement,
                        "intensity": round(displacement / 50.0, 3),
                    })
            if mongo_manager and mongo_manager.connected:
                mongo_manager.store_heatmap_nodes(nodes)
            self._send_json({"ok": True, "nodes": nodes})
            return
        elif parsed.path == "/api/spatial/nodes":
            nodes = []
            fused = {}
            node1 = {}
            node2 = {}
            if dual_hardware_hub:
                payload = dual_hardware_hub.get_unified_payload()
                fused = payload.get("fused_telemetry", {})
                node1 = payload.get("node1_crusher", {})
                node2 = payload.get("node2_trekker", {})
            else:
                fused = {"displacement_mm": 2.5, "tilt_deg": 0.4, "vibration_level": 0.08, "dgms_tier": "SAFE"}

            base_lat = 23.6102
            base_lon = 84.1314
            curr_disp = float(fused.get("displacement_mm", 2.5))
            curr_tier = str(fused.get("dgms_tier", "SAFE"))
            curr_tilt = float(fused.get("tilt_deg", 0.4))
            curr_vib = float(fused.get("vibration_level", 0.08))

            nodes.append({
                "node_id": 1,
                "name": "Node 1 - Extraction Portal",
                "lat": base_lat,
                "lon": base_lon,
                "displacement_mm": curr_disp,
                "risk_tier": curr_tier,
                "tilt_deg": curr_tilt,
                "vibration_level": curr_vib,
                "temperature_c": float(node2.get("temperature_c", 26.2))
            })
            nodes.append({
                "node_id": 2,
                "name": "Node 2 - Subsurface Gallery",
                "lat": round(base_lat + 0.0035, 6),
                "lon": round(base_lon + 0.0042, 6),
                "displacement_mm": round(curr_disp * 0.85 + 1.2, 2),
                "risk_tier": "WARNING" if curr_disp > 20 else curr_tier,
                "tilt_deg": round(curr_tilt * 1.1, 2),
                "vibration_level": round(curr_vib * 0.9, 3),
                "temperature_c": float(node2.get("temperature_c", 27.5))
            })
            offsets = [
                (3, "North Adit Surface", 0.0062, -0.0028, 0.4, "SAFE"),
                (4, "East Ventilation Shaft", 0.0021, 0.0078, 1.2, "ADVISORY" if curr_disp > 15 else "SAFE"),
                (5, "West Haulage Ramp", -0.0051, -0.0044, 0.6, "SAFE"),
                (6, "South Overburden Dump", -0.0072, 0.0031, 1.8, "WARNING" if curr_disp > 25 else "ADVISORY"),
                (7, "Tailings Dam Perimeter", -0.0038, 0.0089, 0.9, "SAFE"),
                (8, "Settlement Observation Pillar", 0.0055, 0.0049, 1.5, "ADVISORY")
            ]
            for nid, name, dlat, dlon, scale, tier in offsets:
                nodes.append({
                    "node_id": nid,
                    "name": name,
                    "lat": round(base_lat + dlat, 6),
                    "lon": round(base_lon + dlon, 6),
                    "displacement_mm": round(curr_disp * scale + 0.8, 2),
                    "risk_tier": tier,
                    "tilt_deg": round(curr_tilt * scale, 2),
                    "vibration_level": round(curr_vib * scale, 3),
                    "temperature_c": round(25.0 + scale * 1.5, 1)
                })
            self._send_json({"ok": True, "count": len(nodes), "nodes": nodes})
            return
        elif parsed.path == "/api/dem":
            lat = float(query.get("lat", ["23.6102"])[0])
            lon = float(query.get("lon", ["84.1314"])[0])
            width, height = 32, 32
            elevations = []
            for r in range(height):
                for c in range(width):
                    d = ((r - 16)**2 + (c - 16)**2)**0.5
                    elev = round(220.0 + math.sin(r * 0.3) * 15.0 + math.cos(c * 0.3) * 15.0 - d * 1.5, 2)
                    elevations.append(elev)
            self._send_json({
                "ok": True,
                "center_lat": lat,
                "center_lon": lon,
                "width": width,
                "height": height,
                "min_elev": min(elevations),
                "max_elev": max(elevations),
                "elevations": elevations,
                "bounds": {
                    "north": lat + 0.05,
                    "south": lat - 0.05,
                    "east": lon + 0.05,
                    "west": lon - 0.05
                }
            })
            return
        elif parsed.path == "/api/mqtt/status":
            stat = mqtt_bridge.get_status() if mqtt_bridge else {"connected": False, "installed": False}
            self._send_json({"ok": True, "mqtt": stat})
            return
        elif parsed.path == "/api/timescale/status":
            stat = timescale_manager.get_status() if timescale_manager else {"connected": False}
            self._send_json({"ok": True, "timescale": stat})
            return
        elif parsed.path == "/api/microclimate":
            temp = 25.0
            moist = 55.0
            if dual_hardware_hub:
                p = dual_hardware_hub.get_unified_payload()
                n2 = p.get("node2_trekker", {})
                temp = float(n2.get("temperature_c", 25.0))
                moist = float(n2.get("moisture_pct", 55.0))
            if microclimate_model:
                microclimate_model.update(temperature=temp, moisture_pct=moist)
                summ = microclimate_model.get_summary()
                self._send_json({"ok": True, "summary": summ})
            else:
                self._send_json({"ok": False, "error": "Microclimate model unavailable"})
            return
        elif parsed.path == "/api/routing/evacuation":
            try:
                start_r = int(query.get("start_r", ["4"])[0])
                start_c = int(query.get("start_c", ["5"])[0])
                center_r = int(query.get("center_r", ["4"])[0])
                center_c = int(query.get("center_c", ["5"])[0])
                stress_mult = float(query.get("stress", ["1.0"])[0])

                risk_grid = [[0.2] * 10 for _ in range(10)]
                for r in range(10):
                    for c in range(10):
                        dist = ((c - center_c)**2 + (r - center_r)**2)**0.5
                        hazard = math.exp(-(dist**2) / (2 * (3.0**2))) * (15.0 * stress_mult)
                        risk_grid[r][c] = round(hazard, 2)

                if dijkstra_safety:
                    evac_result = dijkstra_safety(risk_grid, start=(start_r, start_c))
                    self._send_json({
                        "ok": True,
                        "evacuation": evac_result,
                        "risk_grid": risk_grid
                    })
                else:
                    self._send_json({"ok": False, "error": "Routing engine unavailable"})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)})
            return
        elif parsed.path.startswith("/api/v1.1/Things"):
            if sensorthings_api:
                self._send_json(sensorthings_api.get_things_response())
            else:
                self._send_json({"ok": False, "error": "OGC SensorThings module not loaded"})
            return
        elif parsed.path.startswith("/api/v1.1/Sensors"):
            if sensorthings_api:
                self._send_json(sensorthings_api.get_sensors_response())
            else:
                self._send_json({"ok": False, "error": "OGC SensorThings module not loaded"})
            return
        elif parsed.path.startswith("/api/v1.1/Locations"):
            if sensorthings_api:
                self._send_json(sensorthings_api.get_locations_response())
            else:
                self._send_json({"ok": False, "error": "OGC SensorThings module not loaded"})
            return
        elif parsed.path.startswith("/api/v1.1/Observations"):
            if sensorthings_api:
                self._send_json(sensorthings_api.get_observations_response(dual_hardware_hub))
            else:
                self._send_json({"ok": False, "error": "OGC SensorThings module not loaded"})
            return
        elif parsed.path.startswith("/api/v1.1/Datastreams"):
            if sensorthings_api:
                self._send_json(sensorthings_api.get_datastreams_response())
            else:
                self._send_json({"ok": False, "error": "OGC SensorThings module not loaded"})
            return
        elif parsed.path == "/api/twin/analytics":
            if python_digital_twin:
                # Sync with latest data before emitting
                python_digital_twin.sync_hardware_packet(45, manager.latest_data)
                analytics = python_digital_twin.get_separated_analytics()
                self._send_json(analytics)
            else:
                self._send_json({"ok": False, "error": "Python Digital Twin engine unavailable"})
            return
        elif parsed.path == "/api/twin/node":
            node_id = int(query.get("id", ["45"])[0])
            if python_digital_twin and node_id in python_digital_twin.nodes:
                self._send_json({"ok": True, "node": python_digital_twin.nodes[node_id].to_dict()})
            else:
                self._send_json({"ok": False, "error": f"Node #{node_id} not found"})
            return
        elif parsed.path == "/api/twin/whatif":
            try:
                stress_mult = float(query.get("stress", ["1.0"])[0])
                water_pct = float(query.get("water", ["50.0"])[0])
                vib_g = float(query.get("vib", ["0.05"])[0])
                hours = float(query.get("hours", ["24.0"])[0])
                center_node = int(query.get("center", ["45"])[0])

                center_r = center_node // 10
                center_c = center_node % 10

                sim_nodes = []
                max_disp = 0.0
                crit_count = 0
                warn_count = 0

                for r in range(10):
                    for c in range(10):
                        nid = r * 10 + c
                        dist = ((c - center_c) ** 2 + (r - center_r) ** 2) ** 0.5
                        trough_i = 3.2
                        influence = math.exp(-(dist ** 2) / (2 * (trough_i ** 2)))

                        # Base ground deformation
                        base_disp = 12.0 + (32.0 * influence)
                        
                        # What-if factor scaling
                        stress_factor = stress_mult
                        water_factor = 1.0 + (water_pct / 100.0) * 0.45
                        vib_factor = 1.0 + (vib_g * 0.35)
                        time_factor = 1.0 + (hours / 24.0) * 0.28

                        sim_disp = round(base_disp * stress_factor * water_factor * vib_factor * time_factor, 2)
                        delta = round(sim_disp - base_disp, 2)

                        if sim_disp >= 50.0:
                            tier = "CRITICAL"
                            color = "#ef4444"
                            crit_count += 1
                        elif sim_disp >= 25.0:
                            tier = "WARNING"
                            color = "#f97316"
                            warn_count += 1
                        elif sim_disp >= 10.0:
                            tier = "ADVISORY"
                            color = "#facc15"
                        else:
                            tier = "SAFE"
                            color = "#10b981"

                        if sim_disp > max_disp:
                            max_disp = sim_disp

                        sim_nodes.append({
                            "node_id": nid,
                            "r": r,
                            "c": c,
                            "x": c * 10.0,
                            "y": r * 10.0,
                            "base_disp": base_disp,
                            "sim_disp": sim_disp,
                            "delta": delta,
                            "risk_tier": tier,
                            "color": color
                        })

                # Simulated TTC
                ttc = round(max(0.4, 24.0 / (1.0 + max_disp * 0.08 + vib_g * 4.0)), 2)
                dgms_overall = "CRITICAL" if max_disp >= 50.0 else ("WARNING" if max_disp >= 25.0 else "ADVISORY")

                self._send_json({
                    "ok": True,
                    "max_disp_mm": max_disp,
                    "delta_max_mm": round(max_disp - 44.0, 2),
                    "affected_area_m2": (crit_count + warn_count) * 100,
                    "crit_count": crit_count,
                    "warn_count": warn_count,
                    "ttc_hours": ttc,
                    "dgms_tier": dgms_overall,
                    "nodes": sim_nodes
                })
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)})
            return
        elif parsed.path == "/api/mongo":
            stats = mongo_manager.get_latest_stats() if mongo_manager else {"connected": False}
            self._send_json({"ok": True, "mongo": stats})
            return
        elif parsed.path == "/api/mongo/records":
            limit_val = int(query.get("limit", ["25"])[0])
            records = mongo_manager.get_recent_hardware_records(limit=limit_val) if mongo_manager else []
            stats = mongo_manager.get_latest_stats() if mongo_manager else {"connected": False}
            self._send_json({"ok": True, "stats": stats, "records": records, "count": len(records)})
            return
        elif parsed.path == "/api/ports":
            self._send_json({"ports": manager.list_ports()})
            return
        elif parsed.path == "/api/raw":
            self._send_json({"lines": manager.raw_lines})
            return
        elif parsed.path.startswith("/twin"):
            project_root = self._project_root()
            relative_path = parsed.path[len("/twin"):].lstrip("/")
            twin_dist = os.path.join(project_root, "tunnel-digital-twin", "dist")
            repository_twin = os.path.join(project_root, "Digital Twin")
            candidates = [
                os.path.join(twin_dist, relative_path) if relative_path else
                os.path.join(twin_dist, "index.html"),
                os.path.join(repository_twin, relative_path) if relative_path else
                os.path.join(repository_twin, "index.html"),
            ]
            target = self._first_existing_file(candidates)
            if target:
                self._serve_static_file(target)
                return
            self.send_error(404, "Digital Twin file not found")
            return
        elif parsed.path in {"/gis", "/gis/", "/heatmap", "/heatmap/"}:
            project_root = self._project_root()
            gis_file = self._first_existing_file([
                os.path.join(project_root, "output", "subsidence_interactive.html"),
                os.path.join(project_root, "..", "output", "subsidence_interactive.html"),
            ])
            if gis_file:
                self._serve_static_file(
                    gis_file,
                    content_type="text/html; charset=utf-8",
                )
                return
            self.send_error(404, "GIS dashboard not found")
            return
        elif parsed.path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            q = []
            manager.clients.append(q)
            try:
                # Send initial status immediately
                init_msg = f"event: status\ndata: {json.dumps(manager.get_status())}\n\n"
                self.wfile.write(init_msg.encode("utf-8"))
                self.wfile.flush()

                while True:
                    while q:
                        msg = q.pop(0)
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    time.sleep(0.08)
            except Exception:
                pass
            finally:
                if q in manager.clients:
                    manager.clients.remove(q)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if parsed.path == "/api/connect":
            port = payload.get("port")
            baudrate = payload.get("baudrate", 115200)
            if not port:
                self._send_json({"ok": False, "message": "Port is required"}, 400)
                return
            ok, msg = manager.connect(port, baudrate)
            self._send_json({"ok": ok, "message": msg, "status": manager.get_status()})
            return

        elif parsed.path == "/api/disconnect":
            manager.disconnect()
            self._send_json({"ok": True, "message": "Disconnected", "status": manager.get_status()})
            return

        self._send_json({"ok": False, "message": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    manager.auto_connect()
    port_num = 8080
    server = ThreadingHTTPServer(("0.0.0.0", port_num), DashboardHandler)
    print(f"ESP32 Real-Time Sensor Dashboard running at http://localhost:{port_num}")
    if manager.connected:
        print(f"Auto-connected to {manager.port} ({manager.port_description}) @ {manager.baudrate} baud")
    if mqtt_bridge:
        mqtt_bridge.start()
    server.serve_forever()
