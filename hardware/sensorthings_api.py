"""
sensorthings_api.py — OGC SensorThings API v1.1 Compliance Shim
Exposes standardized JSON-LD REST endpoints for GIS software (QGIS, ArcGIS, Cesium)
conforming to the Open Geospatial Consortium (OGC) SensorThings API standard.
"""
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

BASE_URL = "http://localhost:8080/api/v1.1"

MINE_THINGS = [
    {
        "@iot.id": 1,
        "@iot.selfLink": f"{BASE_URL}/Things(1)",
        "name": "MUNKANIPPU Extraction Portal Node (Node 1)",
        "description": "Underground portal monitoring station with load cell and 3-axis accelerometer",
        "properties": {
            "deployment": "Mine Section A - Portal Face",
            "contractor": "MUNKANIPPU Coal GeoTech Ltd",
            "sample_rate_hz": 5
        },
        "Locations@iot.navigationLink": f"{BASE_URL}/Things(1)/Locations",
        "Datastreams@iot.navigationLink": f"{BASE_URL}/Things(1)/Datastreams"
    },
    {
        "@iot.id": 2,
        "@iot.selfLink": f"{BASE_URL}/Things(2)",
        "name": "MUNKANIPPU Deep Gallery Node (Node 2)",
        "description": "Subsurface gallery station tracking strata tilt, temperature, and soil moisture",
        "properties": {
            "deployment": "Mine Gallery Level -20m",
            "rock_strata": "Hard Rock / Weathered Sandstone",
            "sample_rate_hz": 2
        },
        "Locations@iot.navigationLink": f"{BASE_URL}/Things(2)/Locations",
        "Datastreams@iot.navigationLink": f"{BASE_URL}/Things(2)/Datastreams"
    }
]

MINE_SENSORS = [
    {
        "@iot.id": 1,
        "@iot.selfLink": f"{BASE_URL}/Sensors(1)",
        "name": "HX711 24-Bit ADC Strain Gauge",
        "description": "High precision roof displacement and impact load bridge amplifier",
        "encodingType": "application/pdf",
        "metadata": "https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf"
    },
    {
        "@iot.id": 2,
        "@iot.selfLink": f"{BASE_URL}/Sensors(2)",
        "name": "ADXL345 3-Axis Digital Accelerometer",
        "description": "High resolution strata vibration and dynamic seismic shock monitor",
        "encodingType": "application/pdf",
        "metadata": "https://www.analog.com/media/en/technical-documentation/data-sheets/ADXL345.pdf"
    },
    {
        "@iot.id": 3,
        "@iot.selfLink": f"{BASE_URL}/Sensors(3)",
        "name": "MPU6500 6-Axis MotionTracking IMU",
        "description": "Precision strata tilt and angular displacement gyroscope/accelerometer",
        "encodingType": "application/pdf",
        "metadata": "https://invensense.tdk.com/download-pdf/mpu-6500-datasheet/"
    },
    {
        "@iot.id": 4,
        "@iot.selfLink": f"{BASE_URL}/Sensors(4)",
        "name": "Dallas DS18B20 + Capacitive Soil Moisture",
        "description": "Subsurface thermal gradient and rock mass moisture saturation probe",
        "encodingType": "text/html",
        "metadata": "https://datasheets.maximintegrated.com/en/ds/DS18B20.pdf"
    }
]

MINE_LOCATIONS = [
    {
        "@iot.id": 1,
        "@iot.selfLink": f"{BASE_URL}/Locations(1)",
        "name": "Jharia Dhanbad Coalfield Extraction Site",
        "description": "Primary mine shaft and subsidence monitoring grid anchor",
        "encodingType": "application/geo+json",
        "location": {
            "type": "Point",
            "coordinates": [84.1314, 23.6102, 220.0]
        }
    }
]

def get_things_response() -> Dict[str, Any]:
    return {
        "@iot.count": len(MINE_THINGS),
        "value": MINE_THINGS
    }

def get_sensors_response() -> Dict[str, Any]:
    return {
        "@iot.count": len(MINE_SENSORS),
        "value": MINE_SENSORS
    }

def get_locations_response() -> Dict[str, Any]:
    return {
        "@iot.count": len(MINE_LOCATIONS),
        "value": MINE_LOCATIONS
    }

def get_observations_response(dual_hub: Any = None) -> Dict[str, Any]:
    fused = {}
    node2 = {}
    if dual_hub:
        payload = dual_hub.get_unified_payload()
        fused = payload.get("fused_telemetry", {})
        node2 = payload.get("node2_trekker", {})

    now_iso = datetime.now(timezone.utc).isoformat()
    disp = float(fused.get("displacement_mm", 2.5))
    tilt = float(fused.get("tilt_deg", 0.4))
    vib = float(fused.get("vibration_level", 0.08))
    temp = float(node2.get("temperature_c", 26.2))
    moist = float(node2.get("moisture_pct", 55.0))
    tier = str(fused.get("dgms_tier", "SAFE"))

    observations = [
        {
            "@iot.id": 101,
            "@iot.selfLink": f"{BASE_URL}/Observations(101)",
            "phenomenonTime": now_iso,
            "resultTime": now_iso,
            "result": disp,
            "resultQuality": tier,
            "Datastream@iot.navigationLink": f"{BASE_URL}/Datastreams(1)"
        },
        {
            "@iot.id": 102,
            "@iot.selfLink": f"{BASE_URL}/Observations(102)",
            "phenomenonTime": now_iso,
            "resultTime": now_iso,
            "result": tilt,
            "resultQuality": "deg",
            "Datastream@iot.navigationLink": f"{BASE_URL}/Datastreams(2)"
        },
        {
            "@iot.id": 103,
            "@iot.selfLink": f"{BASE_URL}/Observations(103)",
            "phenomenonTime": now_iso,
            "resultTime": now_iso,
            "result": vib,
            "resultQuality": "g",
            "Datastream@iot.navigationLink": f"{BASE_URL}/Datastreams(3)"
        },
        {
            "@iot.id": 104,
            "@iot.selfLink": f"{BASE_URL}/Observations(104)",
            "phenomenonTime": now_iso,
            "resultTime": now_iso,
            "result": temp,
            "resultQuality": "C",
            "Datastream@iot.navigationLink": f"{BASE_URL}/Datastreams(4)"
        },
        {
            "@iot.id": 105,
            "@iot.selfLink": f"{BASE_URL}/Observations(105)",
            "phenomenonTime": now_iso,
            "resultTime": now_iso,
            "result": moist,
            "resultQuality": "%",
            "Datastream@iot.navigationLink": f"{BASE_URL}/Datastreams(5)"
        }
    ]
    return {
        "@iot.count": len(observations),
        "value": observations
    }

def get_datastreams_response() -> Dict[str, Any]:
    datastreams = [
        {
            "@iot.id": 1,
            "name": "Roof Subsidence & Displacement",
            "description": "Surface and crown downward geotechnical displacement in millimeters",
            "unitOfMeasurement": {"name": "Millimeter", "symbol": "mm", "definition": "http://unitsofmeasure.org/ucum.html#para-28"},
            "observationType": "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement"
        },
        {
            "@iot.id": 2,
            "name": "Strata Angular Tilt",
            "description": "Geotechnical angular inclination of roof pillars",
            "unitOfMeasurement": {"name": "Degree", "symbol": "deg", "definition": "http://unitsofmeasure.org/ucum.html#para-29"},
            "observationType": "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement"
        },
        {
            "@iot.id": 3,
            "name": "Dynamic Rock Mass Vibration",
            "description": "Root-mean-square seismic acceleration",
            "unitOfMeasurement": {"name": "Standard Gravity", "symbol": "g", "definition": "http://unitsofmeasure.org/ucum.html#para-30"},
            "observationType": "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement"
        },
        {
            "@iot.id": 4,
            "name": "Rock Mass Ambient Temperature",
            "description": "Ambient strata temperature inside coal mine gallery",
            "unitOfMeasurement": {"name": "Degree Celsius", "symbol": "C", "definition": "http://unitsofmeasure.org/ucum.html#para-31"},
            "observationType": "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement"
        },
        {
            "@iot.id": 5,
            "name": "Soil & Overburden Moisture Saturation",
            "description": "Volumetric water content percentage in overburden strata",
            "unitOfMeasurement": {"name": "Percent", "symbol": "%", "definition": "http://unitsofmeasure.org/ucum.html#para-32"},
            "observationType": "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement"
        }
    ]
    return {
        "@iot.count": len(datastreams),
        "value": datastreams
    }
