import * as THREE from 'three';
import type { GeologicalLayer } from './DataModel';
import { Calculations } from './Calculations';

export class GeologyView {
  public group: THREE.Group;
  private width = 420;
  private depthY = 170;
  
  public layerMeshes: THREE.Mesh[] = [];
  public surfaceMesh: THREE.Mesh | null = null;
  public treeGroup: THREE.Group;
  public surveyReticle: THREE.Group;
  public sectorPinsGroup: THREE.Group;

  private naturalColors: Float32Array | null = null;
  private rainbowSpectrumColors: Float32Array | null = null;
  private isHeatmapActive: boolean = true;
  private isRainbowSpectrum: boolean = false;
  private lastEpicenterX: number = 0;
  private lastEpicenterZ: number = 0;
  private lastIntensity: number = 0.5;

  constructor() {
    this.group = new THREE.Group();
    this.treeGroup = new THREE.Group();
    this.surveyReticle = new THREE.Group();
    this.sectorPinsGroup = new THREE.Group();
    this.group.add(this.treeGroup);
    this.group.add(this.surveyReticle);
    this.group.add(this.sectorPinsGroup);
  }

  public build(layers: GeologicalLayer[]) {
    // Clear old children
    while (this.group.children.length > 0) { 
      this.group.remove(this.group.children[0]); 
    }
    this.layerMeshes = [];
    this.treeGroup.clear();
    this.surveyReticle.clear();
    this.sectorPinsGroup.clear();
    this.group.add(this.treeGroup);
    this.group.add(this.surveyReticle);
    this.group.add(this.sectorPinsGroup);

    // High resolution grid for crisp stepped benches
    const segmentsX = 140;
    const segmentsZ = 90;
    const surfGeom = new THREE.PlaneGeometry(this.width, this.depthY, segmentsX, segmentsZ);
    surfGeom.rotateX(-Math.PI / 2);

    const positions = surfGeom.attributes.position.array as Float32Array;
    const colors = new Float32Array(positions.length);
    const color = new THREE.Color();

    const pitRadiusX = 135.0;
    const pitRadiusZ = 68.0;

    for (let i = 0; i < positions.length; i += 3) {
      const x = positions[i];
      const z = positions[i + 2];
      
      const y = Calculations.getTerrainHeight(x, z);
      positions[i + 1] = y;

      const normDist = Math.sqrt((x / pitRadiusX) ** 2 + (z / pitRadiusZ) ** 2);
      const absX = Math.abs(x);
      const absZ = Math.abs(z);

      // Outside Portal Roads
      if (absX > 140 && absZ < 7) {
        color.setHex(0x23272e); // Asphalt/compacted haulage entry
      } else if (normDist < 0.95 && x < 85) {
        // Open-Pit Geotechnical Elevation / Subsidence Gradient (Matching user's reference photo)
        // Deep pit floor: Blue/Cyan -> Mid Benches: Cyan/Green -> Upper Benches: Bright Lime Green
        if (y < -10) {
          color.setHex(0x0077b6); // Deep pit basin azure
        } else if (y < -5) {
          color.setHex(0x00b4d8); // Deep cyan floor
        } else if (y < 0) {
          color.setHex(0x06b6d4); // Electric turquoise bench
        } else if (y < 5) {
          color.setHex(0x10b981); // Emerald green bench
        } else if (y < 11) {
          color.setHex(0x22c55e); // Bright spring green bench
        } else {
          color.setHex(0x84cc16); // High crest lime green
        }

        // Add subtle scanline/point cloud contrast
        const scanGrid = (Math.sin(x * 2.5) + Math.cos(z * 2.5)) * 0.04;
        color.r = Math.max(0, Math.min(1, color.r + scanGrid));
        color.g = Math.max(0, Math.min(1, color.g + scanGrid));
        color.b = Math.max(0, Math.min(1, color.b + scanGrid));

      } else {
        // Realistic Natural Quarry Wall & Surrounding Rim (Right side of reference photo)
        // Sedimentary rock strata in warm tan, beige, gravel, and dark shale bands
        const layerBands = Math.sin(y * 0.45 + x * 0.05);
        if (layerBands > 0.4) {
          color.setHex(0x8c7e6c); // Tan sandstone face
        } else if (layerBands > -0.2) {
          color.setHex(0x6e6355); // Weathered gravel slope
        } else {
          color.setHex(0x423d35); // Dark shale/clay stratum
        }

        // Subtle vegetation on high outer ridges
        if (y > 20 && Math.sin(x * 0.2 + z * 0.2) > 0.3) {
          color.setHex(0x365314); // Dark evergreen scrub
        }
      }
      
      colors[i] = color.r;
      colors[i + 1] = color.g;
      colors[i + 2] = color.b;
    }

    surfGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    surfGeom.computeVertexNormals();

    this.naturalColors = new Float32Array(colors);

    // Precompute Topographic Rainbow Geotechnical Spectrum matching user photo media_1794596835063_0650c3c7.jpg:
    // Vertical scale 0m to 19m:
    // 0m (trench baseline, y ~ -14m): Red (#ef4444)
    // 5m: Orange / Amber (#f97316 -> #facc15)
    // 10m: Green (#22c55e)
    // 15m: Sky Blue / Cyan (#06b6d4 -> #2563eb)
    // 19m: Violet / Magenta (#d946ef / #c026d3)
    const specColors = new Float32Array(positions.length);
    const specColor = new THREE.Color();
    for (let i = 0; i < positions.length; i += 3) {
      const vx = positions[i];
      const vy = positions[i + 1];
      const vz = positions[i + 2];

      const normH = Math.max(0, Math.min(1.0, (vy - (-13.5)) / 32.5));

      if (normH <= 0.20) {
        specColor.lerpColors(new THREE.Color(0xef4444), new THREE.Color(0xf97316), normH / 0.20);
      } else if (normH <= 0.35) {
        specColor.lerpColors(new THREE.Color(0xf97316), new THREE.Color(0xfacc15), (normH - 0.20) / 0.15);
      } else if (normH <= 0.50) {
        specColor.lerpColors(new THREE.Color(0xfacc15), new THREE.Color(0x22c55e), (normH - 0.35) / 0.15);
      } else if (normH <= 0.68) {
        specColor.lerpColors(new THREE.Color(0x22c55e), new THREE.Color(0x06b6d4), (normH - 0.50) / 0.18);
      } else if (normH <= 0.82) {
        specColor.lerpColors(new THREE.Color(0x06b6d4), new THREE.Color(0x2563eb), (normH - 0.68) / 0.14);
      } else {
        specColor.lerpColors(new THREE.Color(0x2563eb), new THREE.Color(0xd946ef), Math.min(1.0, (normH - 0.82) / 0.18));
      }

      // Add delicate point-cloud LiDAR scan pattern visible in reference photo
      const scanGrid = (Math.sin(vx * 2.2) * Math.cos(vz * 2.2)) * 0.045;
      specColors[i] = Math.max(0, Math.min(1, specColor.r + scanGrid));
      specColors[i + 1] = Math.max(0, Math.min(1, specColor.g + scanGrid));
      specColors[i + 2] = Math.max(0, Math.min(1, specColor.b + scanGrid));
    }
    this.rainbowSpectrumColors = specColors;

    const surfMat = new THREE.MeshStandardMaterial({ 
      vertexColors: true,
      side: THREE.DoubleSide, 
      roughness: 0.85,
      metalness: 0.12
    });
    
    const surface = new THREE.Mesh(surfGeom, surfMat);
    surface.receiveShadow = true;
    surface.castShadow = true;
    this.surfaceMesh = surface;
    this.group.add(surface);

    // 3D Tree Clusters on Upper Benches & Rim (As shown in reference photo)
    this.createVegetationClusters();

    // Central Geotechnical Survey Benchmark Reticle in Pit Basin (Yellow crosshair in photo)
    this.createSurveyReticle();

    // 3D Holographic Ground Beacons for Portal Sectors (Matching media_1794596835063_0650c3c7.jpg)
    this.createSectorBeacons();

    // Geological Cross-Section Layers Beneath Quarry
    layers.forEach(layer => {
      const thickness = layer.topZ - layer.bottomZ;
      const centerY = layer.topZ - thickness / 2;

      const geom = new THREE.BoxGeometry(this.width, thickness, this.depthY, 80, 1, 50);
      
      const layerPos = geom.attributes.position.array as Float32Array;
      for (let j = 0; j < layerPos.length; j += 3) {
        const lx = layerPos[j];
        const lz = layerPos[j+2];
        const worldY = centerY + layerPos[j+1];
        const terrainY = Calculations.getTerrainHeight(lx, lz);
        const cappedWorldY = Math.min(worldY, terrainY);
        layerPos[j+1] = cappedWorldY - centerY;
      }
      geom.computeVertexNormals();

      const mat = new THREE.MeshStandardMaterial({
        color: layer.color,
        transparent: true,
        opacity: 0.45,
        roughness: 0.85,
        metalness: 0.15,
        depthWrite: false
      });
      
      const clipShader = (shader: any) => {
        shader.vertexShader = shader.vertexShader.replace(
          '#include <common>',
          `#include <common>\n varying vec3 vWorldPos;`
        ).replace(
          '#include <worldpos_vertex>',
          `#include <worldpos_vertex>\n vWorldPos = (modelMatrix * vec4(transformed, 1.0)).xyz;`
        );
        
        shader.fragmentShader = shader.fragmentShader.replace(
          '#include <common>',
          `#include <common>\n varying vec3 vWorldPos;`
        ).replace(
          'void main() {',
          `void main() {\n float dist = length(vec2(vWorldPos.y - (-20.0), vWorldPos.z));\n if (dist < 3.35) discard;\n`
        );
      };
      mat.onBeforeCompile = clipShader;
      
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.set(0, centerY, 0);
      mesh.userData = { id: layer.id, name: layer.name };
      mesh.receiveShadow = true;
      mesh.castShadow = true;
      
      this.group.add(mesh);
      this.layerMeshes.push(mesh);
      
      // Wireframe border
      const edges = new THREE.EdgesGeometry(geom);
      const lineMat = new THREE.LineBasicMaterial({ color: 0x475569, transparent: true, opacity: 0.2 });
      lineMat.onBeforeCompile = clipShader;
      const line = new THREE.LineSegments(edges, lineMat);
      mesh.add(line);
    });
  }

  /**
   * Generates dense clusters of 3D foliage and trees on the upper quarry benches and crest.
   */
  private createVegetationClusters() {
    const foliageGeom = new THREE.DodecahedronGeometry(1.8, 1);
    const foliageColors = [0x22c55e, 0x16a34a, 0x4ade80, 0x15803d, 0x84cc16];

    // Seed trees along upper bench contours and quarry crests
    const treePositions: { x: number; z: number }[] = [];

    // Left high rim
    for (let x = -130; x <= -40; x += 6) {
      for (let z = -55; z <= -25; z += 6) {
        if (Math.random() < 0.65) treePositions.push({ x: x + (Math.random() - 0.5) * 4, z: z + (Math.random() - 0.5) * 4 });
      }
    }

    // Top high bench ridge
    for (let x = 30; x <= 125; x += 6) {
      for (let z = -55; z <= -20; z += 6) {
        if (Math.random() < 0.7) treePositions.push({ x: x + (Math.random() - 0.5) * 4, z: z + (Math.random() - 0.5) * 4 });
      }
    }

    // Far right quarry crest
    for (let x = 90; x <= 145; x += 7) {
      for (let z = 20; z <= 65; z += 7) {
        if (Math.random() < 0.6) treePositions.push({ x: x + (Math.random() - 0.5) * 4, z: z + (Math.random() - 0.5) * 4 });
      }
    }

    treePositions.forEach(pos => {
      const y = Calculations.getTerrainHeight(pos.x, pos.z);
      if (y < 4) return; // Only on upper benches and rims

      const colHex = foliageColors[Math.floor(Math.random() * foliageColors.length)];
      const mat = new THREE.MeshStandardMaterial({
        color: colHex,
        roughness: 0.9,
        metalness: 0.05,
        flatShading: true
      });

      const mesh = new THREE.Mesh(foliageGeom, mat);
      const scale = 0.8 + Math.random() * 0.9;
      mesh.scale.set(scale, scale * (1.0 + Math.random() * 0.4), scale);
      mesh.position.set(pos.x, y + scale * 1.2, pos.z);
      mesh.castShadow = true;
      mesh.receiveShadow = true;

      this.treeGroup.add(mesh);
    });
  }

  /**
   * Creates the yellow/gold survey target crosshair reticle seen in the pit basin floor.
   */
  private createSurveyReticle() {
    const pitCenterX = 5;
    const pitCenterZ = 8;
    const pitY = Calculations.getTerrainHeight(pitCenterX, pitCenterZ) + 0.15;

    const reticleGroup = new THREE.Group();
    reticleGroup.position.set(pitCenterX, pitY, pitCenterZ);

    const reticleMat = new THREE.MeshBasicMaterial({ color: 0xfacc15, side: THREE.DoubleSide });

    // Concentric Ring
    const ringGeom = new THREE.RingGeometry(1.6, 2.0, 32);
    ringGeom.rotateX(-Math.PI / 2);
    const ringMesh = new THREE.Mesh(ringGeom, reticleMat);
    reticleGroup.add(ringMesh);

    // Crosshair Lines (+)
    const lineGeomH = new THREE.PlaneGeometry(6.0, 0.35);
    lineGeomH.rotateX(-Math.PI / 2);
    const lineH = new THREE.Mesh(lineGeomH, reticleMat);
    reticleGroup.add(lineH);

    const lineGeomV = new THREE.PlaneGeometry(0.35, 6.0);
    lineGeomV.rotateX(-Math.PI / 2);
    const lineV = new THREE.Mesh(lineGeomV, reticleMat);
    reticleGroup.add(lineV);

    // Center Golden Pulse Point
    const centerPointGeom = new THREE.CircleGeometry(0.5, 16);
    centerPointGeom.rotateX(-Math.PI / 2);
    const centerPoint = new THREE.Mesh(centerPointGeom, reticleMat);
    reticleGroup.add(centerPoint);

    this.surveyReticle.add(reticleGroup);
  }

  public setOpacity(opacity: number) {
    this.layerMeshes.forEach(mesh => {
      (mesh.material as THREE.MeshStandardMaterial).opacity = opacity;
    });
  }

  public setVisibility(visible: boolean) {
    this.group.visible = visible;
  }

  public setHeatmapActive(active: boolean) {
    this.isHeatmapActive = active;
    if (!this.surfaceMesh || !this.naturalColors) return;

    const geom = this.surfaceMesh.geometry;
    const colors = geom.attributes.color.array as Float32Array;

    if (!active) {
      colors.set(this.naturalColors);
      geom.attributes.color.needsUpdate = true;
    } else {
      this.updateSurfaceHeatmap(this.lastEpicenterX, this.lastEpicenterZ, this.lastIntensity);
    }
  }

  public updateSurfaceHeatmap(epicenterX: number, epicenterZ: number, intensity: number, radius: number = 65) {
    this.lastEpicenterX = epicenterX;
    this.lastEpicenterZ = epicenterZ;
    this.lastIntensity = intensity;

    if (!this.surfaceMesh || !this.naturalColors || !this.isHeatmapActive) return;

    const geom = this.surfaceMesh.geometry;
    const positions = geom.attributes.position.array as Float32Array;
    const colors = geom.attributes.color.array as Float32Array;
    const natural = this.naturalColors;

    const normIntensity = Math.max(0.05, Math.min(1.0, intensity));

    for (let i = 0; i < positions.length; i += 3) {
      const vx = positions[i];
      const vz = positions[i + 2];

      const dx = vx - epicenterX;
      const dz = vz - epicenterZ;
      const dist = Math.sqrt(dx * dx + dz * dz);

      const decay = Math.exp(-((dist * dist) / (2 * radius * radius)));
      const localRisk = normIntensity * decay;

      if (localRisk < 0.06) {
        colors[i] = natural[i];
        colors[i + 1] = natural[i + 1];
        colors[i + 2] = natural[i + 2];
      } else {
        // DGMS Warning overlay on the quarry benches
        let hr = 0.06, hg = 0.72, hb = 0.50; // Emerald Safe
        if (localRisk >= 0.70) {
          hr = 0.88; hg = 0.18; hb = 0.18; // Deep Crimson Red
        } else if (localRisk >= 0.45) {
          hr = 0.92; hg = 0.40; hb = 0.08; // Burnt Orange
        } else if (localRisk >= 0.20) {
          hr = 0.85; hg = 0.65; hb = 0.08; // Amber Gold
        }

        const blend = Math.min(1.0, localRisk * 1.2);
        colors[i] = natural[i] * (1 - blend) + hr * blend;
        colors[i + 1] = natural[i + 1] * (1 - blend) + hg * blend;
        colors[i + 2] = natural[i + 2] * (1 - blend) + hb * blend;
      }
    }

    geom.attributes.color.needsUpdate = true;
  }

  private createSectorBeacons() {
    this.sectorPinsGroup.clear();

    const sectorLocs = [
      { id: 'SEC-C', x: -85, z: -38, color: 0x38bdf8 },
      { id: 'SEC-B', x: 55, z: -32, color: 0xfacc15 },
      { id: 'SEC-A', x: -75, z: 22, color: 0xef4444 },
      { id: 'SEC-D', x: 65, z: 30, color: 0x10b981 }
    ];

    sectorLocs.forEach(sec => {
      const y = Calculations.getTerrainHeight(sec.x, sec.z);
      const bGroup = new THREE.Group();
      bGroup.position.set(sec.x, y, sec.z);

      // 1. Ground Ring
      const ringGeom = new THREE.RingGeometry(2.5, 3.5, 32);
      ringGeom.rotateX(-Math.PI / 2);
      const ringMat = new THREE.MeshBasicMaterial({ 
        color: sec.color, 
        side: THREE.DoubleSide, 
        transparent: true, 
        opacity: 0.85 
      });
      const ring = new THREE.Mesh(ringGeom, ringMat);
      ring.position.y = 0.2;
      bGroup.add(ring);

      // 2. Vertical Pin Pillar
      const pinGeom = new THREE.CylinderGeometry(0.3, 0.3, 8, 16);
      const pinMat = new THREE.MeshBasicMaterial({ 
        color: sec.color, 
        transparent: true, 
        opacity: 0.7 
      });
      const pin = new THREE.Mesh(pinGeom, pinMat);
      pin.position.y = 4.0;
      bGroup.add(pin);

      // 3. Top Glowing Beacon Sphere
      const sphereGeom = new THREE.SphereGeometry(1.2, 16, 16);
      const sphereMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const sphere = new THREE.Mesh(sphereGeom, sphereMat);
      sphere.position.y = 8.0;
      bGroup.add(sphere);

      this.sectorPinsGroup.add(bGroup);
    });

    // Default visibility in sync with spectrum mode
    this.sectorPinsGroup.visible = this.isRainbowSpectrum;
  }

  public setRainbowSpectrumMode(active: boolean) {
    this.isRainbowSpectrum = active;
    if (!this.surfaceMesh) return;

    const geom = this.surfaceMesh.geometry;
    const colors = geom.attributes.color.array as Float32Array;

    if (active && this.rainbowSpectrumColors) {
      colors.set(this.rainbowSpectrumColors);
    } else if (this.naturalColors) {
      colors.set(this.naturalColors);
    }
    geom.attributes.color.needsUpdate = true;
    this.sectorPinsGroup.visible = active;
  }
}
