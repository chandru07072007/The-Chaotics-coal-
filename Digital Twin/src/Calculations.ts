import type { GeologicalLayer, SensorData } from './DataModel';

export class Calculations {
  static readonly G = 9.81; // m/s^2
  static readonly WATER_DENSITY = 1000; // kg/m^3

  /**
   * Generates realistic open-pit coal mine topography:
   * Stepped terraced benches, pit basin floor, winding haulage ramps, and surrounding quarry ridges.
   */
  static getTerrainHeight(x: number, z: number): number {
    const roadY = -22.0; 
    const absX = Math.abs(x);
    const absZ = Math.abs(z);

    // 1. Open-Pit Terraced Quarry Geometry (Stepped Benches)
    const pitRadiusX = 135.0;
    const pitRadiusZ = 68.0;
    const normDist = Math.sqrt((x / pitRadiusX) ** 2 + (z / pitRadiusZ) ** 2);

    let h = 0;

    if (normDist < 1.0) {
      // Inside the Stepped Terraced Excavation Pit
      const numBenches = 5;
      const benchFrac = normDist * numBenches;
      const bIdx = Math.floor(benchFrac);
      const subFrac = benchFrac - bIdx;

      // Bench profile: 62% flat catch bench, 38% steep cut slope
      let stepOffset = 0;
      if (subFrac > 0.62) {
        const t = (subFrac - 0.62) / 0.38;
        stepOffset = t * t * (3 - 2 * t); // Smooth hermite slope
      }

      const steppedT = (bIdx + stepOffset) / numBenches;
      // Deep pit floor at -15m up to quarry crest at +18m
      h = -15.0 + steppedT * 33.0;

      // Subtle geological rock roughness on the bench face
      const benchNoise = Math.sin(x * 0.15 + z * 0.12) * 0.45;
      h += benchNoise;

      // Winding Haulage Ramp cutting down the quarry walls
      const angle = Math.atan2(z, x);
      const rampPhase = (angle + Math.PI) / (2 * Math.PI); // 0 to 1
      const rampExpectedDist = 0.2 + rampPhase * 0.75;
      const distFromRamp = Math.abs(normDist - rampExpectedDist);
      if (distFromRamp < 0.055) {
        const rampWidthFactor = 1.0 - (distFromRamp / 0.055);
        const rampH = -15.0 + rampPhase * 33.0;
        h = h * (1.0 - rampWidthFactor * 0.75) + rampH * (rampWidthFactor * 0.75);
      }

    } else {
      // Outside the pit: Natural surrounding hillside ridges and upper quarry rim
      const excess = normDist - 1.0;
      let rimH = 18.0 + excess * 10.0;
      // Rugged mountain contours
      rimH += Math.cos((x / 200) * (Math.PI / 2)) * 6;
      rimH += Math.sin(x * 0.035 + z * 0.04) * 3.5;
      h = rimH;
    }

    // 2. Tunnel Portal Valley Approaches (At the far ends absX > 135)
    if (absX > 135) {
      const roadHalfWidth = 6.5;
      let valleyH = roadY;
      
      if (absZ > roadHalfWidth) {
        valleyH += (absZ - roadHalfWidth) * 1.4;
      }
      
      const blend = Math.max(0, Math.min((absX - 135) / 15, 1.0)); 
      h = h * (1 - blend) + Math.min(h, valleyH) * blend;
    }

    return h;
  }

  static getLayerAtDepth(layers: GeologicalLayer[], z: number): GeologicalLayer {
    for (const layer of layers) {
      if (z <= layer.topZ && z >= layer.bottomZ) {
        return layer;
      }
    }
    return layers[layers.length - 1];
  }

  static calculateOverburden(layers: GeologicalLayer[], targetZ: number, terrainZ: number): number {
    let stress = 0;
    for (const layer of layers) {
      let layerTop = layer.topZ;
      let layerBottom = layer.bottomZ;
      
      if (layer.id === 'L-1') {
        layerTop = Math.max(layerTop, terrainZ);
      } else {
        layerTop = Math.min(layerTop, terrainZ);
      }
      layerBottom = Math.min(layerBottom, terrainZ);

      if (layerTop > layerBottom) {
        if (targetZ <= layerBottom) {
          stress += layer.density * this.G * (layerTop - layerBottom);
        } else if (targetZ < layerTop && targetZ > layerBottom) {
          stress += layer.density * this.G * (layerTop - targetZ);
          break;
        }
      }
    }
    return stress / 1000;
  }

  static calculateWaterPressure(targetZ: number, waterTableZ: number): number {
    if (targetZ >= waterTableZ) return 0;
    const h = waterTableZ - targetZ;
    return (this.WATER_DENSITY * this.G * h) / 1000;
  }

  static calculateRisk(
    sensor: SensorData,
    layer: GeologicalLayer,
    weights = { stress: 0.5, def: 0.3, water: 0.2 },
    maxExpectedStress = 1000,
    maxExpectedDef = 50,
    maxExpectedWater = 500
  ): { riskScore: number; status: string; safetyFactor: number } {
    const sf = layer.allowableStress / Math.max(sensor.stress, 1);
    
    const normStress = Math.min(sensor.stress / maxExpectedStress, 1);
    const normDef = Math.min(sensor.deformation / maxExpectedDef, 1);
    const normWater = Math.min(sensor.waterPressure / maxExpectedWater, 1);
    
    const risk = (normStress * weights.stress + normDef * weights.def + normWater * weights.water) * 100;
    
    let status = 'SAFE';
    if (sf < 1.0 || risk > 80) status = 'FAILURE';
    else if (sf < 1.5 || risk > 60) status = 'CRITICAL';
    else if (sf < 2.0 || risk > 40) status = 'WARNING';
    else if (risk > 20) status = 'NORMAL';

    return { riskScore: Math.min(100, Math.max(0, risk)), status, safetyFactor: sf };
  }
}
