import * as THREE from 'three';
import type { TunnelConfig } from './DataModel';
import { Calculations } from './Calculations';

export class SensorView {
  public group: THREE.Group;
  private crackGroup: THREE.Group;
  private projectionLine: THREE.Line | null = null;
  private failureMarker: THREE.Mesh | null = null;
  private tunnelConfig: TunnelConfig;

  constructor(tunnelConfig: TunnelConfig) {
    this.tunnelConfig = tunnelConfig;
    this.group = new THREE.Group();
    this.crackGroup = new THREE.Group();
    this.group.add(this.crackGroup);
  }

  public updateFailurePrediction(segmentX: number, segmentZ: number, riskScore: number) {
    // Clear old
    this.crackGroup.clear();
    if (this.projectionLine) {
        this.group.remove(this.projectionLine);
    }
    if (this.failureMarker) {
        this.group.remove(this.failureMarker);
    }

    if (riskScore < 60) return; // Only show if at least WARNING

    // Create marker at roof of tunnel
    // Three.js Y is data Z
    const radius = this.tunnelConfig.internalDiameter / 2 + this.tunnelConfig.liningThickness;
    const failY = segmentZ + radius;
    
    // Marker
    const markGeom = new THREE.SphereGeometry(1.5, 32, 32);
    const markMat = new THREE.MeshBasicMaterial({ color: 0xff0000 });
    this.failureMarker = new THREE.Mesh(markGeom, markMat);
    this.failureMarker.position.set(segmentX, failY, 0);
    this.group.add(this.failureMarker);

    // Warning light
    const pointLight = new THREE.PointLight(0xff0000, 200, 50);
    pointLight.position.set(segmentX, failY, 0);
    this.failureMarker.add(pointLight); // Attach so it's removed with marker

    // Surface projection line
    const surfaceY = Calculations.getTerrainHeight(segmentX, 0);
    const points = [];
    points.push(new THREE.Vector3(segmentX, failY, 0));
    points.push(new THREE.Vector3(segmentX, surfaceY, 0));
    const lineGeom = new THREE.BufferGeometry().setFromPoints(points);
    const lineMat = new THREE.LineDashedMaterial({ color: 0xff0000, dashSize: 1, gapSize: 0.5 });
    this.projectionLine = new THREE.Line(lineGeom, lineMat);
    this.projectionLine.computeLineDistances();
    this.group.add(this.projectionLine);

    // Crack visualization (simple rings)
    if (riskScore >= 80) {
        const crackGeom = new THREE.TorusGeometry(radius + 0.1, 0.2, 8, 20);
        const crackMat = new THREE.MeshBasicMaterial({ color: 0xff0000, wireframe: true });
        const crack = new THREE.Mesh(crackGeom, crackMat);
        crack.position.set(segmentX, segmentZ, 0);
        crack.rotation.y = Math.PI / 2;
        this.crackGroup.add(crack);
    }
  }
}
