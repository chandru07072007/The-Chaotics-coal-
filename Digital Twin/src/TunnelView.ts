import * as THREE from 'three';
import type { TunnelConfig } from './DataModel';

export class TunnelView {
  public group: THREE.Group;
  public segments: THREE.Mesh[] = [];
  public segmentMap: Map<string, THREE.Mesh> = new Map();
  private config: TunnelConfig;

  constructor(config: TunnelConfig) {
    this.config = config;
    this.group = new THREE.Group();
  }

  public build() {
    // Clear old
    while(this.group.children.length > 0) { 
        this.group.remove(this.group.children[0]); 
    }
    this.segments = [];
    this.segmentMap.clear();

    const segLength = this.config.length / this.config.numSegments;
    const outRadius = this.config.internalDiameter / 2 + this.config.liningThickness;
    const inRadius = this.config.internalDiameter / 2;

    // We make the cylinder slightly shorter than segLength to create visible joint lines
    const jointGap = 0.05;
    const effectiveSegLength = segLength - jointGap;

    const outerGeometry = new THREE.CylinderGeometry(outRadius, outRadius, effectiveSegLength, 32, 1, true);
    outerGeometry.rotateZ(Math.PI / 2);
    
    const innerGeometry = new THREE.CylinderGeometry(inRadius, inRadius, effectiveSegLength, 32, 1, true);
    innerGeometry.rotateZ(Math.PI / 2);

    // Floor (Roadway) - road inside tunnel matches the outside road width
    const floorY = -inRadius * 0.5;
    const floorWidth = 8; // ~8m road inside tunnel
    const floorThickness = 0.5;
    const floorGeom = new THREE.BoxGeometry(effectiveSegLength, floorThickness, floorWidth);
    
    // Walkways / curbs (removed unused base geom, created in loop)
    
    // Light fixtures (removed unused base geom, created in loop)

    for (let i = 0; i < this.config.numSegments; i++) {
      const id = `T-${(i + 1).toString().padStart(3, '0')}`;
      const xPos = -this.config.length / 2 + (i + 0.5) * segLength;
      
      const segmentGroup = new THREE.Group();
      segmentGroup.position.set(xPos, this.config.depthZ, 0);

      // 1. Outer Lining (Status Indicator)
      const outerMat = new THREE.MeshPhysicalMaterial({ 
        color: 0x888888, 
        side: THREE.FrontSide,
        roughness: 0.85,
      });
      const outerMesh = new THREE.Mesh(outerGeometry, outerMat);
      outerMesh.userData = { id, type: 'tunnel-segment', baseColor: 0x888888 };
      outerMesh.castShadow = true;
      outerMesh.receiveShadow = true;
      segmentGroup.add(outerMesh);
      
      this.segmentMap.set(id, outerMesh);
      this.segments.push(outerMesh);
      
      // 2. Inner Lining (Rough Shotcrete / Rock)
      const innerMat = new THREE.MeshStandardMaterial({
        color: 0x4a4036,
        side: THREE.BackSide,
        roughness: 1.0,
        metalness: 0.0
      });
      const innerMesh = new THREE.Mesh(innerGeometry, innerMat);
      innerMesh.receiveShadow = true;
      segmentGroup.add(innerMesh);

      // Steel/Timber Support Rib (instead of a flat joint gap)
      // Make it protrude inward slightly
      const ribRadius = inRadius - 0.05;
      const ribThickness = 0.3;
      const ribGeom = new THREE.CylinderGeometry(ribRadius, ribRadius, ribThickness, 32, 1, true);
      ribGeom.rotateZ(Math.PI / 2);
      const ribMat = new THREE.MeshStandardMaterial({ 
        color: 0x2a1a10, // Dark wood/rusty steel
        side: THREE.DoubleSide,
        roughness: 0.9,
        metalness: 0.1
      });
      const ribMesh = new THREE.Mesh(ribGeom, ribMat);
      ribMesh.position.x = segLength / 2;
      segmentGroup.add(ribMesh);

      // 3. Floor (Dirt / Gravel)
      const dirtMat = new THREE.MeshStandardMaterial({ 
        color: 0x3a3025,
        roughness: 1.0,
      });
      const roadMesh = new THREE.Mesh(floorGeom, dirtMat);
      roadMesh.position.y = floorY - floorThickness / 2;
      roadMesh.receiveShadow = true;
      segmentGroup.add(roadMesh);
      
      // Removed asphalt markings and curbs for mining aesthetic

      // 4. Lighting Fixtures (Warm industrial lights, hung from ceiling)
      const fixtureMat = new THREE.MeshStandardMaterial({
        color: 0xffddaa,
        emissive: 0xff7700,
        emissiveIntensity: 2.0,
        roughness: 0.4
      });
      
      // Small hanging bulb housing
      const lightGeom = new THREE.CylinderGeometry(0.1, 0.2, 0.3, 8);
      
      if (i % 2 === 0) { // Place a hanging light every 2 segments
        const centerLight = new THREE.Mesh(lightGeom, fixtureMat);
        centerLight.position.set(0, inRadius - 0.2, 0); // Hanging from top center
        segmentGroup.add(centerLight);

        // Interior point lights (Warm yellowish-orange)
        const interiorLight = new THREE.PointLight(0xff9933, 200, 30);
        interiorLight.position.set(0, inRadius - 0.5, 0);
        segmentGroup.add(interiorLight);
      }

      // 6. Sensor Elements (4 boxes around the lining)
      const sensorGeom = new THREE.BoxGeometry(0.3, 0.3, 0.1);
      const sensorMat = new THREE.MeshStandardMaterial({ 
        color: 0x222222,
        emissive: 0x10b981, // Safe green by default
        emissiveIntensity: 2.0,
        roughness: 0.7 
      });

      const sensorMeshes: THREE.Mesh[] = [];
      const angles = [Math.PI / 2.2, -Math.PI / 2.2, Math.PI / 6, -Math.PI / 6];
      angles.forEach((angle, idx) => {
        const sMesh = new THREE.Mesh(sensorGeom, sensorMat.clone());
        sMesh.position.set(0, Math.cos(angle) * (inRadius - 0.05), Math.sin(angle) * (inRadius - 0.05));
        sMesh.lookAt(0, 0, 0); // Point the local Z axis towards the center of the tunnel
        sMesh.userData = { id, type: 'sensor-box', sensorIdx: idx };
        segmentGroup.add(sMesh);
        sensorMeshes.push(sMesh);
      });
      
      // Store sensors in map so we can update their colors
      this.segmentMap.set(`${id}_sensors`, sensorMeshes as any);

      this.group.add(segmentGroup);
    }

    // === TUNNEL PORTALS ===
    this.buildPortal(-this.config.length / 2, outRadius, inRadius, true);
    this.buildPortal(this.config.length / 2, outRadius, inRadius, false);

    // === APPROACH ROADS (outside tunnel) ===
    this.buildApproachRoad(-this.config.length / 2, -1);
    this.buildApproachRoad(this.config.length / 2, 1);
  }

  private buildPortal(xPos: number, outRadius: number, _inRadius: number, facingPositiveX: boolean) {
    const portalGroup = new THREE.Group();
    portalGroup.position.set(xPos, this.config.depthZ, 0);

    // Portal ring - thick concrete arch frame
    const portalThickness = 1.5;
    const portalGeom = new THREE.CylinderGeometry(outRadius + 1.0, outRadius + 1.0, portalThickness, 32, 1, true);
    portalGeom.rotateZ(Math.PI / 2);
    const portalMat = new THREE.MeshStandardMaterial({ 
      color: 0xaaaaaa,
      roughness: 0.7,
      metalness: 0.1
    });
    const portalRing = new THREE.Mesh(portalGeom, portalMat);
    portalRing.position.x = facingPositiveX ? -portalThickness / 2 : portalThickness / 2;
    portalRing.castShadow = true;
    portalRing.receiveShadow = true;
    portalGroup.add(portalRing);

    // Portal face wall (flat concrete wall around the tunnel mouth)
    const wallHeight = outRadius * 2.5;
    const wallWidth = outRadius * 3;
    const wallGeom = new THREE.PlaneGeometry(wallWidth, wallHeight);
    const wallMat = new THREE.MeshStandardMaterial({ 
      color: 0x8a7a6a, // Stone/concrete
      roughness: 0.95,
      side: THREE.DoubleSide
    });
    const wall = new THREE.Mesh(wallGeom, wallMat);
    wall.position.set(facingPositiveX ? -portalThickness : portalThickness, 0, 0);
    wall.rotation.y = Math.PI / 2;
    wall.receiveShadow = true;
    portalGroup.add(wall);

    // Retaining walls on sides - stonework
    const retainingMat = new THREE.MeshStandardMaterial({
      color: 0x7a6a5a,
      roughness: 1.0
    });

    for (const side of [1, -1]) {
      const retainGeom = new THREE.BoxGeometry(3, wallHeight * 0.6, 1);
      const retainWall = new THREE.Mesh(retainGeom, retainingMat);
      retainWall.position.set(
        facingPositiveX ? -2 : 2,
        -wallHeight * 0.15,
        side * (outRadius + 1.5)
      );
      retainWall.castShadow = true;
      portalGroup.add(retainWall);
    }

    this.group.add(portalGroup);
  }

  private buildApproachRoad(tunnelEndX: number, direction: number) {
    const roadLength = 60;
    const roadWidth = 10;
    const roadY = this.config.depthZ - this.config.internalDiameter / 2 * 0.5 - 0.25;

    const roadGeom = new THREE.PlaneGeometry(roadLength, roadWidth);
    roadGeom.rotateX(-Math.PI / 2);
    const roadMat = new THREE.MeshStandardMaterial({ 
      color: 0x333333,
      roughness: 0.9 
    });
    const road = new THREE.Mesh(roadGeom, roadMat);
    road.position.set(tunnelEndX + direction * roadLength / 2, roadY, 0);
    road.receiveShadow = true;
    this.group.add(road);

    // Center dashed line on approach road
    for (let d = 0; d < roadLength; d += 4) {
      const dashGeom = new THREE.PlaneGeometry(2, 0.15);
      dashGeom.rotateX(-Math.PI / 2);
      const dashMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const dash = new THREE.Mesh(dashGeom, dashMat);
      dash.position.set(tunnelEndX + direction * (d + 1), roadY + 0.02, 0);
      this.group.add(dash);
    }

    // Edge lines
    for (const side of [1, -1]) {
      const edgeGeom = new THREE.PlaneGeometry(roadLength, 0.15);
      edgeGeom.rotateX(-Math.PI / 2);
      const edgeMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const edge = new THREE.Mesh(edgeGeom, edgeMat);
      edge.position.set(tunnelEndX + direction * roadLength / 2, roadY + 0.02, side * (roadWidth / 2 - 0.5));
      this.group.add(edge);
    }
  }

  public updateSegmentColor(id: string, color: number) {
    const mesh = this.segmentMap.get(id);
    if (mesh) {
      (mesh.material as THREE.MeshStandardMaterial).color.setHex(color);
      mesh.userData.currentColor = color;
    }

    const sensors = this.segmentMap.get(`${id}_sensors`) as unknown as THREE.Mesh[];
    if (sensors && Array.isArray(sensors)) {
      sensors.forEach(sensorMesh => {
        if (sensorMesh.material && (sensorMesh.material as THREE.MeshStandardMaterial).emissive) {
            (sensorMesh.material as THREE.MeshStandardMaterial).emissive.setHex(color);
        }
      });
    }
  }

  public setExteriorOpacity(opacity: number) {
    this.segments.forEach(mesh => {
      const mat = mesh.material as THREE.MeshPhysicalMaterial;
      if (opacity < 1.0) {
        mat.transparent = true;
        mat.opacity = opacity;
      } else {
        mat.transparent = false;
        mat.opacity = 1.0;
      }
      mat.needsUpdate = true;
    });
  }
}
