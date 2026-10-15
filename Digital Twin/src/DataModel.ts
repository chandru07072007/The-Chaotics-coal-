export interface TunnelConfig {
  length: number;
  internalDiameter: number;
  liningThickness: number;
  depthZ: number;
  numSegments: number;
}

export interface GeologicalLayer {
  id: string;
  name: string;
  topZ: number; // e.g. 0
  bottomZ: number; // e.g. -2
  density: number; // kg/m3
  cohesion: number; // kPa
  frictionAngle: number; // degrees
  allowableStress: number; // kPa
  color: number; // hex
}

export interface SensorData {
  id: string;
  segmentId: string;
  stress: number; // kPa
  deformation: number; // mm
  waterPressure: number; // kPa
}

export interface SegmentAnalysis {
  id: string;
  centerX: number;
  centerZ: number;
  geoLayer: GeologicalLayer;
  overburdenStress: number; // kPa
  effectiveStress: number; // kPa
  stressRatio: number;
  safetyFactor: number;
  damageIndex: number;
  riskScore: number;
  status: 'SAFE' | 'NORMAL' | 'WARNING' | 'CRITICAL' | 'FAILURE';
  sensor: SensorData;
}

