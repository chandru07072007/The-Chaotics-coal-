"""
mqtt_bridge.py — MQTT Subscriber and Publisher Bridge for Mine Telemetry
Subscribes to: mine/node/+/telemetry
Parses payloads and feeds dual_hardware_hub directly (dual-port hardware & simulation)
"""
import json
import threading
import time
from typing import Optional, Dict, Any

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

BROKER_HOST = "localhost"
BROKER_PORT = 1883

class MQTTBridge:
    def __init__(self, host: str = BROKER_HOST, port: int = BROKER_PORT):
        self.host = host
        self.port = port
        self.client: Optional[Any] = None
        self.connected = False
        self.last_msg_time = 0.0
        self.msg_count = 0
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not mqtt:
            print("[MQTT] paho-mqtt not available.")
            return

        def _run():
            try:
                # Support both paho-mqtt v1 and v2 API
                try:
                    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "munkanippu_bridge")
                except AttributeError:
                    self.client = mqtt.Client("munkanippu_bridge")

                self.client.on_connect = self._on_connect
                self.client.on_message = self._on_message
                self.client.on_disconnect = self._on_disconnect

                print(f"[MQTT] Connecting to broker at {self.host}:{self.port}...")
                self.client.connect(self.host, self.port, keepalive=60)
                self.client.loop_forever()
            except Exception as e:
                self.connected = False
                print(f"[MQTT] Broker connection notice: {e} (MQTT offline or standby)")

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            print("[MQTT] Connected to Mosquitto broker successfully")
            client.subscribe("mine/node/+/telemetry")
            client.subscribe("mine/regional/+/telemetry")
        else:
            self.connected = False
            print(f"[MQTT] Connection returned code {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.connected = False
        print("[MQTT] Disconnected from Mosquitto broker")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self.last_msg_time = time.time()
            self.msg_count += 1

            # Try to route into dual_hardware_hub
            try:
                from dual_hardware_manager import dual_hardware_hub
                if dual_hardware_hub:
                    if "node/1" in msg.topic:
                        dual_hardware_hub.node1.data.update({
                            "hx711_raw": payload.get("hx711_raw", 0),
                            "hx711_change": payload.get("hx711_change", 0),
                            "adxl_mag": payload.get("adxl_mag", 1.0),
                            "adxl_peak": payload.get("adxl_peak", 0.0),
                        })
                    elif "node/2" in msg.topic:
                        dual_hardware_hub.node2.data.update({
                            "accel_x": payload.get("accel_x", 0.0),
                            "temperature": payload.get("temperature", 24.5),
                            "soil_raw": payload.get("soil_raw", 1780),
                            "moisture_pct": payload.get("moisture_pct", 55.0),
                        })
            except Exception as ex:
                print(f"[MQTT] Hub ingestion error: {ex}")
        except Exception as e:
            print(f"[MQTT] Parse error on {msg.topic}: {e}")

    def publish_telemetry(self, topic: str, data: Dict[str, Any]):
        if not self.connected or not self.client:
            return False
        try:
            payload = json.dumps(data)
            self.client.publish(topic, payload)
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "broker": f"{self.host}:{self.port}",
            "msg_count": self.msg_count,
            "last_msg_time": self.last_msg_time,
        }

mqtt_bridge = MQTTBridge()
