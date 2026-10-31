import json
import os
import re
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import serial
import serial.tools.list_ports


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
        self.send_header("Access-Control-Allow-Origin", "*")
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
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
            data = manager.latest_data
            tilt = round(
                (data.get("angleX", 0) ** 2 + data.get("angleY", 0) ** 2) ** 0.5,
                2,
            )
            vibration = float(data.get("vibration") or 0)
            force = float(data.get("forceLevel") or 0)
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

            ttc = (
                round((50.0 - abs(displacement)) / velocity, 2)
                if velocity > 0.05
                else 999.0
            )
            command = (
                f"python main.py --node-id 45 --disp {displacement:.1f} "
                f"--tilt {tilt:.1f} --vib {vibration:.2f} "
                f"--temp {temperature:.1f} --vel {velocity:.1f}"
            )
            self._send_json({
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
            })
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
            self._send_json({"ok": True, "nodes": nodes})
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
            self.send_header("Access-Control-Allow-Origin", "*")
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


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    manager.auto_connect()
    port_num = 8080
    server = ThreadingHTTPServer(("0.0.0.0", port_num), DashboardHandler)
    print(f"ESP32 Real-Time Sensor Dashboard running at http://localhost:{port_num}")
    if manager.connected:
        print(f"Auto-connected to {manager.port} ({manager.port_description}) @ {manager.baudrate} baud")
    server.serve_forever()
