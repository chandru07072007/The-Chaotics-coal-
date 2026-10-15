import type { GeologicalLayer, SensorData } from './DataModel';

export class Calculations {
  static readonly G = 9.81; // m/s^2
  static readonly WATER_DENSITY = 1000; // kg/m^3

  static getTerrainHeight(x: number, z: number): number {
    // The road/tunnel floor world Y is around -21.75
    const roadY = -22.0; 
    const absX = Math.abs(x);
    const absZ = Math.abs(z);

    // 1. Natural mountain shape over the whole area
    // Peak at (0,0), sloping down towards ends
    let mountain = 5 + Math.cos( (x / 200) * (Math.PI / 2) ) * 20;
    
    // Rise on the Z axis (sides)
    mountain += absZ * 0.3;
    
    // Noise for realism
    const noise = Math.sin(x * 0.04 + z * 0.05) * 4 + Math.sin(x * 0.1) * 2;
    let h = mountain + noise;

    // 2. Carve out the approach valleys for the portals (absX > 140)
    if (absX > 140) {
        const roadHalfWidth = 6;
        let valleyH = roadY;
        
        if (absZ > roadHalfWidth) {
            valleyH += (absZ - roadHalfWidth) * 1.5; // Steep valley slopes (1.5 rise per 1 run)
        }
        
        // Blend between natural mountain and carved valley
        // Tunnel portal is at absX = 150.
        // At 150, we want the terrain to be just above the portal wall (around -15).
        // At 155, we want it to be fully at road level (-22).
        const blend = Math.max(0, Math.min((absX - 140) / 15, 1.0)); 
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
    // Return bottom-most if deeper
    return layers[layers.length - 1];
  }

  static calculateOverburden(layers: GeologicalLayer[], targetZ: number, terrainZ: number): number {
    let stress = 0; // Pa
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
            // full layer
            stress += layer.density * this.G * (layerTop - layerBottom);
          } else if (targetZ < layerTop && targetZ > layerBottom) {
            // partial layer
            stress += layer.density * this.G * (layerTop - targetZ);
            break;
          }
      }
    }
    return stress / 1000; // Return in kPa
  }

  static calculateWaterPressure(targetZ: number, waterTableZ: number): number {
    if (targetZ >= waterTableZ) return 0;
    const h = waterTableZ - targetZ;
    return (this.WATER_DENSITY * this.G * h) / 1000; // kPa
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

    const di = (weights.stress * normStress) + (weights.def * normDef) + (weights.water * normWater);
    const riskScore = Math.min(di * 100, 100);

    let status = 'SAFE';
    if (di >= 0.8) status = 'CRITICAL';
    else if (di >= 0.6) status = 'WARNING';
    else if (di >= 0.4) status = 'NORMAL';

    return { riskScore, status, safetyFactor: sf };
  }
}
