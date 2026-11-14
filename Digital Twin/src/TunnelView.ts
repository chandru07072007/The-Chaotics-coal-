import * as THREE from 'three';
import type { TunnelConfig } from './DataModel';

/**
 * Generates an organic subterranean rock surface texture.
 */
function createRockTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d')!;

  // Base dark charcoal rock
  ctx.fillStyle = '#1e232b';
  ctx.fillRect(0, 0, 512, 512);

  // Grain / noise
  const imgData = ctx.getImageData(0, 0, 512, 512);
  const data = imgData.data;
  for (let i = 0; i < data.length; i += 4) {
    const n = (Math.random() - 0.5) * 45;
    data[i] = Math.max(0, Math.min(255, 30 + n));     // R
    data[i + 1] = Math.max(0, Math.min(255, 35 + n)); // G
    data[i + 2] = Math.max(0, Math.min(255, 42 + n)); // B
  }
  ctx.putImageData(imgData, 0, 0);

  // Faint mineral fissures
  ctx.strokeStyle = 'rgba(15, 20, 28, 0.4)';
  ctx.lineWidth = 1.5;
  for (let c = 0; c < 20; c++) {
    ctx.beginPath();
    let cx = Math.random() * 512;
    let cy = Math.random() * 512;
    ctx.moveTo(cx, cy);
    for (let s = 0; s < 4; s++) {
      cx += (Math.random() - 0.5) * 50;
      cy += (Math.random() - 0.5) * 50;
      ctx.lineTo(cx, cy);
    }
    ctx.stroke();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(8, 2);
  return texture;
}

/**
 * Generates a procedural rock bump map for rocky crags and specular depth.
 */
function createRockBumpMap(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d')!;
  const imgData = ctx.createImageData(512, 512);
  const data = imgData.data;
  for (let i = 0; i < data.length; i += 4) {
    const val = Math.floor(Math.random() * 255);
    data[i] = val;
    data[i + 1] = val;
    data[i + 2] = val;
    data[i + 3] = 255;
  }
  ctx.putImageData(imgData, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(16, 4);
  return texture;
}

/**
 * Generates a circular IoT sensor node badge texture.
 */
function createSensorBadgeTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;

  // Blue badge background
  ctx.fillStyle = '#0284c7';
  ctx.beginPath();
  ctx.arc(64, 64, 58, 0, Math.PI * 2);
  ctx.fill();

  // White inner rim
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 6;
  ctx.stroke();

  // White IoT / sensor glyph (antenna / data curves)
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.arc(64, 72, 12, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.arc(64, 72, 24, Math.PI * 1.2, Math.PI * 1.8);
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(64, 72, 36, Math.PI * 1.25, Math.PI * 1.75);
  ctx.stroke();

  const texture = new THREE.CanvasTexture(canvas);
  return texture;
}

export class TunnelView {
  public group: THREE.Group;
  public segments: THREE.Mesh[] = [];
  public segmentMap: Map<string, THREE.Mesh> = new Map();
  private config: TunnelConfig;

  private rockTex: THREE.CanvasTexture;
  private rockBump: THREE.CanvasTexture;
  private badgeTex: THREE.CanvasTexture;

  constructor(config: TunnelConfig) {
    this.config = config;
    this.group = new THREE.Group();

    this.rockTex = createRockTexture();
    this.rockBump = createRockBumpMap();
    this.badgeTex = createSensorBadgeTexture();
  }

  public build() {
    // Clear old
    while (this.group.children.length > 0) { 
      this.group.remove(this.group.children[0]); 
    }
    this.segments = [];
    this.segmentMap.clear();

    const segLength = this.config.length / this.config.numSegments;
    const outRadius = this.config.internalDiameter / 2 + this.config.liningThickness;
    const inRadius = this.config.internalDiameter / 2;

    const jointGap = 0.05;
    const effectiveSegLength = segLength - jointGap;

    // Structural shells
    const outerGeometry = new THREE.CylinderGeometry(outRadius, outRadius, effectiveSegLength, 32, 1, true);
    outerGeometry.rotateZ(Math.PI / 2);
    
    // Horseshoe / Arched inner rock geometry
    const innerGeometry = new THREE.CylinderGeometry(inRadius, inRadius, effectiveSegLength, 36, 1, true);
    innerGeometry.rotateZ(Math.PI / 2);

    // Subterranean Floor / Track Bed
    const floorY = -inRadius * 0.55;
    const floorWidth = 7.6;
    const floorThickness = 0.5;
    const floorGeom = new THREE.BoxGeometry(effectiveSegLength, floorThickness, floorWidth);

    // Steel Rails for Tramway
    const railGeom = new THREE.BoxGeometry(effectiveSegLength, 0.14, 0.1);
    const railMat = new THREE.MeshStandardMaterial({
      color: 0xcbd5e1, // Polished steel head
      metalness: 0.9,
      roughness: 0.2
    });

    // Timber Sleeper Tie Geometry
    const sleeperGeom = new THREE.BoxGeometry(0.32, 0.12, 3.0);
    const sleeperMat = new THREE.MeshStandardMaterial({
      color: 0x3d2817,
      roughness: 0.95
    });

    // Orange Utility Pipeline Materials (As seen in photo)
    const pipeMatOrange = new THREE.MeshStandardMaterial({
      color: 0xf97316, // Safety orange industrial pipeline
      roughness: 0.35,
      metalness: 0.6
    });

    // Yellow Electrical Box Material
    const yellowBoxMat = new THREE.MeshStandardMaterial({
      color: 0xeab308, // Hazard yellow electrical cabinet
      roughness: 0.4,
      metalness: 0.5
    });

    // Sensor Badge Material
    const badgeMat = new THREE.MeshBasicMaterial({
      map: this.badgeTex,
      transparent: true,
      side: THREE.DoubleSide
    });

    for (let i = 0; i < this.config.numSegments; i++) {
      const id = `T-${(i + 1).toString().padStart(3, '0')}`;
      const xPos = -this.config.length / 2 + (i + 0.5) * segLength;
      
      const segmentGroup = new THREE.Group();
      segmentGroup.position.set(xPos, this.config.depthZ, 0);

      // 1. Outer Lining (Status Indicator & Dynamic DGMS Heat Target)
      const outerMat = new THREE.MeshStandardMaterial({ 
        color: 0x222a36,
        side: THREE.FrontSide,
        roughness: 0.85,
        metalness: 0.15
      });
      const outerMesh = new THREE.Mesh(outerGeometry, outerMat);
      outerMesh.userData = { id, type: 'tunnel-segment', baseColor: 0x222a36 };
      outerMesh.castShadow = true;
      outerMesh.receiveShadow = true;
      segmentGroup.add(outerMesh);
      
      this.segmentMap.set(id, outerMesh);
      this.segments.push(outerMesh);
      
      // 2. Inner Rock Wall Lining (Authentic craggy shotcrete/coal tunnel face)
      const innerMat = new THREE.MeshStandardMaterial({
        map: this.rockTex,
        bumpMap: this.rockBump,
        bumpScale: 0.08,
        color: 0x333b47, // Dark rocky slate tone
        side: THREE.BackSide,
        roughness: 0.75,
        metalness: 0.2
      });
      const innerMesh = new THREE.Mesh(innerGeometry, innerMat);
      innerMesh.receiveShadow = true;
      segmentGroup.add(innerMesh);

      // 3. Subterranean Haulage Floor (Damp Coal Dust & Rock Roadway)
      const floorMat = new THREE.MeshStandardMaterial({ 
        color: 0x181e28,
        roughness: 0.9,
        metalness: 0.1
      });
      const floorMesh = new THREE.Mesh(floorGeom, floorMat);
      floorMesh.position.y = floorY;
      floorMesh.receiveShadow = true;
      segmentGroup.add(floorMesh);

      // 4. Centered Dual Steel Rails & Wooden Cross-Ties
      const leftRail = new THREE.Mesh(railGeom, railMat);
      leftRail.position.set(0, floorY + floorThickness / 2 + 0.07, -0.75);
      segmentGroup.add(leftRail);

      const rightRail = new THREE.Mesh(railGeom, railMat);
      rightRail.position.set(0, floorY + floorThickness / 2 + 0.07, 0.75);
      segmentGroup.add(rightRail);

      // 2 Timber Ties per Segment
      const tie1 = new THREE.Mesh(sleeperGeom, sleeperMat);
      tie1.position.set(-segLength * 0.25, floorY + floorThickness / 2 + 0.04, 0);
      segmentGroup.add(tie1);

      const tie2 = new THREE.Mesh(sleeperGeom, sleeperMat);
      tie2.position.set(segLength * 0.25, floorY + floorThickness / 2 + 0.04, 0);
      segmentGroup.add(tie2);

      // 5. Overhead Hanging Mine Lamps (Down the ceiling centerline)
      const lampHousingGeom = new THREE.BoxGeometry(0.24, 0.18, 0.32);
      const lampHousingMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8 });
      const lampHousing = new THREE.Mesh(lampHousingGeom, lampHousingMat);
      lampHousing.position.set(0, inRadius - 0.15, 0);
      segmentGroup.add(lampHousing);

      const lampLensGeom = new THREE.PlaneGeometry(0.2, 0.28);
      const lampLensMat = new THREE.MeshBasicMaterial({ color: 0xfffae0 });
      const lampLens = new THREE.Mesh(lampLensGeom, lampLensMat);
      lampLens.rotateX(Math.PI / 2);
      lampLens.position.set(0, inRadius - 0.245, 0);
      segmentGroup.add(lampLens);

      // Warm downward point-light every segment for continuous illuminated tunnel
      const lampLight = new THREE.PointLight(0xfff3c4, 0.85, 18, 1.4);
      lampLight.position.set(0, inRadius - 0.45, 0);
      segmentGroup.add(lampLight);

      // 6. Orange Utility Pipelines (Wall-mounted on both sides as in photo)
      // Right Wall: 3 Parallel Orange Pipes
      const pipeR = 0.08;
      const pipeGeom = new THREE.CylinderGeometry(pipeR, pipeR, effectiveSegLength, 12);
      pipeGeom.rotateZ(Math.PI / 2);

      const pR1 = new THREE.Mesh(pipeGeom, pipeMatOrange);
      pR1.position.set(0, floorY + 1.2, inRadius * 0.88);
      segmentGroup.add(pR1);

      const pR2 = new THREE.Mesh(pipeGeom, pipeMatOrange);
      pR2.position.set(0, floorY + 1.45, inRadius * 0.88);
      segmentGroup.add(pR2);

      const pR3 = new THREE.Mesh(pipeGeom, pipeMatOrange);
      pR3.position.set(0, floorY + 1.7, inRadius * 0.88);
      segmentGroup.add(pR3);

      // Left Wall: 2 Parallel Orange Pipes
      const pL1 = new THREE.Mesh(pipeGeom, pipeMatOrange);
      pL1.position.set(0, floorY + 1.35, -inRadius * 0.88);
      segmentGroup.add(pL1);

      const pL2 = new THREE.Mesh(pipeGeom, pipeMatOrange);
      pL2.position.set(0, floorY + 1.6, -inRadius * 0.88);
      segmentGroup.add(pL2);

      // Wall Mounting Bracket
      const bracketGeom = new THREE.BoxGeometry(0.08, 0.9, 0.12);
      const bracketMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8 });
      const bracketR = new THREE.Mesh(bracketGeom, bracketMat);
      bracketR.position.set(0, floorY + 1.45, inRadius * 0.92);
      segmentGroup.add(bracketR);

      // 7. Yellow Electrical Junction Cabinets & IoT Sensor Badges (Every 4 segments)
      if (i % 4 === 1) {
        // Right side yellow cabinet
        const boxGeom = new THREE.BoxGeometry(0.55, 0.75, 0.3);
        const box = new THREE.Mesh(boxGeom, yellowBoxMat);
        box.position.set(0, floorY + 0.8, inRadius * 0.86);
        segmentGroup.add(box);

        // Vertical conduit pipe
        const conduitGeom = new THREE.CylinderGeometry(0.035, 0.035, 0.7, 8);
        const conduit = new THREE.Mesh(conduitGeom, pipeMatOrange);
        conduit.position.set(0, floorY + 0.25, inRadius * 0.86);
        segmentGroup.add(conduit);

        // IoT Sensor Badge on the cabinet
        const badgeGeom = new THREE.PlaneGeometry(0.32, 0.32);
        const badge = new THREE.Mesh(badgeGeom, badgeMat);
        badge.position.set(0, floorY + 0.85, inRadius * 0.86 - 0.16);
        badge.rotateY(Math.PI);
        segmentGroup.add(badge);
      }

      if (i % 4 === 3) {
        // Left side yellow cabinet
        const boxGeom = new THREE.BoxGeometry(0.55, 0.75, 0.3);
        const box = new THREE.Mesh(boxGeom, yellowBoxMat);
        box.position.set(0, floorY + 0.9, -inRadius * 0.86);
        segmentGroup.add(box);

        // IoT Sensor Badge
        const badgeGeom = new THREE.PlaneGeometry(0.32, 0.32);
        const badge = new THREE.Mesh(badgeGeom, badgeMat);
        badge.position.set(0, floorY + 0.95, -inRadius * 0.86 + 0.16);
        segmentGroup.add(badge);
      }

      this.group.add(segmentGroup);
    }

    // 8. Turnout / Branching Siding Track (Switch track curving off to the left)
    this.createTurnoutSiding(inRadius, floorY + floorThickness / 2 + 0.07);

    // 9. Authentic Mine Cart / Haulage Ore Tub on the track
    this.createMineCart(-95, floorY + floorThickness / 2 + 0.15);

    // Concrete Portals
    this.createMiningPortal(-this.config.length / 2 - 2, outRadius);
    this.createMiningPortal(this.config.length / 2 + 2, outRadius);
  }

  /**
   * Builds the curving switch track branching off to the left.
   */
  private createTurnoutSiding(inRadius: number, railY: number) {
    const railMat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8,
      metalness: 0.85,
      roughness: 0.25
    });

    const curveLength = 32;
    const curveStartX = -125;
    const segments = 24;

    for (let j = 0; j < segments; j++) {
      const frac = j / segments;
      const x = curveStartX + frac * curveLength;
      // Parabolic turnout curve heading toward left wall
      const zOffset = -Math.pow(frac, 1.8) * (inRadius * 0.65);

      const trackPieceGeom = new THREE.BoxGeometry(curveLength / segments, 0.14, 0.1);
      const piece1 = new THREE.Mesh(trackPieceGeom, railMat);
      piece1.position.set(x, railY, -0.75 + zOffset);
      piece1.rotateY(frac * 0.22);
      this.group.add(piece1);

      const piece2 = new THREE.Mesh(trackPieceGeom, railMat);
      piece2.position.set(x, railY, 0.75 + zOffset);
      piece2.rotateY(frac * 0.22);
      this.group.add(piece2);
    }
  }

  /**
   * Builds an authentic rusted steel mining cart / ore tub sitting on the rails.
   */
  private createMineCart(xPos: number, baseY: number) {
    const cartGroup = new THREE.Group();
    cartGroup.position.set(xPos, this.config.depthZ + baseY, 0);

    // Rust iron ore hopper material
    const hopperMat = new THREE.MeshStandardMaterial({
      color: 0x7c3826, // Weathered rusty red iron
      roughness: 0.8,
      metalness: 0.4
    });

    const steelMat = new THREE.MeshStandardMaterial({
      color: 0x27272a,
      roughness: 0.6,
      metalness: 0.8
    });

    // Hopper Tub (Tapered bottom)
    const tubGeom = new THREE.BoxGeometry(3.6, 1.5, 2.0);
    const tub = new THREE.Mesh(tubGeom, hopperMat);
    tub.position.y = 1.1;
    tub.castShadow = true;
    cartGroup.add(tub);

    // Coal lumps inside the cart
    const coalMat = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.95 });
    const coalGeom = new THREE.BoxGeometry(3.2, 0.4, 1.7);
    const coal = new THREE.Mesh(coalGeom, coalMat);
    coal.position.y = 1.8;
    cartGroup.add(coal);

    // Chassis frame
    const frameGeom = new THREE.BoxGeometry(4.0, 0.2, 1.8);
    const frame = new THREE.Mesh(frameGeom, steelMat);
    frame.position.y = 0.35;
    cartGroup.add(frame);

    // 4 Steel Wheels on Axles
    const wheelGeom = new THREE.CylinderGeometry(0.32, 0.32, 0.12, 16);
    wheelGeom.rotateX(Math.PI / 2);

    const w1 = new THREE.Mesh(wheelGeom, steelMat);
    w1.position.set(-1.2, 0.2, -0.75);
    cartGroup.add(w1);

    const w2 = new THREE.Mesh(wheelGeom, steelMat);
    w2.position.set(1.2, 0.2, -0.75);
    cartGroup.add(w2);

    const w3 = new THREE.Mesh(wheelGeom, steelMat);
    w3.position.set(-1.2, 0.2, 0.75);
    cartGroup.add(w3);

    const w4 = new THREE.Mesh(wheelGeom, steelMat);
    w4.position.set(1.2, 0.2, 0.75);
    cartGroup.add(w4);

    this.group.add(cartGroup);
  }

  private createMiningPortal(xPos: number, radius: number) {
    const portalGroup = new THREE.Group();
    portalGroup.position.set(xPos, this.config.depthZ, 0);

    const portalShape = new THREE.Shape();
    const w = radius * 2 + 4;
    const h = radius * 2 + 4;
    portalShape.moveTo(-w / 2, -radius);
    portalShape.lineTo(w / 2, -radius);
    portalShape.lineTo(w / 2, h / 2);
    portalShape.lineTo(-w / 2, h / 2);
    portalShape.closePath();

    const hole = new THREE.Path();
    hole.absarc(0, 0, radius, 0, Math.PI * 2, true);
    portalShape.holes.push(hole);

    const portalGeom = new THREE.ExtrudeGeometry(portalShape, { depth: 3.5, bevelEnabled: true, bevelThickness: 0.4 });
    portalGeom.rotateY(Math.PI / 2);

    const portalMat = new THREE.MeshStandardMaterial({
      color: 0x2e3846,
      roughness: 0.85,
      metalness: 0.15
    });

    const portalMesh = new THREE.Mesh(portalGeom, portalMat);
    portalMesh.castShadow = true;
    portalMesh.receiveShadow = true;
    portalGroup.add(portalMesh);

    // Hazard Safety Warning Stripes above portal
    const stripeGeom = new THREE.BoxGeometry(0.3, 0.8, w * 0.8);
    const stripeMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b });
    const stripeMesh = new THREE.Mesh(stripeGeom, stripeMat);
    stripeMesh.position.set(xPos > 0 ? 3.6 : -3.6, radius + 1.2, 0);
    portalGroup.add(stripeMesh);

    this.group.add(portalGroup);
  }

  public updateSegmentColor(id: string, colorHex: number) {
    const mesh = this.segmentMap.get(id);
    if (!mesh) return;
    const mat = mesh.material as THREE.MeshStandardMaterial;

    if (colorHex === 0x10b981) {
      mat.color.setHex(0x222a36);
      mat.emissive.setHex(0x064e3b);
      mat.emissiveIntensity = 0.2;
    } else {
      mat.color.setHex(colorHex);
      mat.emissive.setHex(colorHex);
      mat.emissiveIntensity = 0.6;
    }
  }

  public setOpacity(opacity: number) {
    this.segments.forEach(mesh => {
      const mat = mesh.material as THREE.MeshStandardMaterial;
      mat.transparent = opacity < 1.0;
      mat.opacity = opacity;
    });
  }

  public setExteriorOpacity(opacity: number) {
    this.setOpacity(opacity);
  }

  public setVisibility(visible: boolean) {
    this.group.visible = visible;
  }
}
