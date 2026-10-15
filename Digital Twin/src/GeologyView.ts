import * as THREE from 'three';
import type { GeologicalLayer } from './DataModel';
import { Calculations } from './Calculations';

export class GeologyView {
  public group: THREE.Group;
  private width = 400;
  private depthY = 150;
  
  public layerMeshes: THREE.Mesh[] = [];

  constructor() {
    this.group = new THREE.Group();
  }

  public build(layers: GeologicalLayer[]) {
    while(this.group.children.length > 0) { 
        this.group.remove(this.group.children[0]); 
    }
    this.layerMeshes = [];

    // Procedural terrain generation
    const segmentsX = 100;
    const segmentsZ = 60;
    const surfGeom = new THREE.PlaneGeometry(this.width, this.depthY, segmentsX, segmentsZ);
    surfGeom.rotateX(-Math.PI / 2);

    const positions = surfGeom.attributes.position.array as Float32Array;
    const colors = new Float32Array(positions.length);
    const color = new THREE.Color();

    for (let i = 0; i < positions.length; i += 3) {
      const x = positions[i];
      const z = positions[i + 2];
      
      const y = Calculations.getTerrainHeight(x, z);
      positions[i + 1] = y;

      const absX = Math.abs(x);
      const absZ = Math.abs(z);
      const roadHalfWidth = 6;
      
      // Outside tunnel (absX > 140) and near road (absZ < roadHalfWidth + 2)
      if (absX > 140 && absZ < roadHalfWidth + 1) {
        if (absZ < roadHalfWidth) {
           color.setHex(0x2a2a2a); // dark asphalt
        } else {
           color.setHex(0x444433); // shoulder
        }
      } else {
        // Mountain slopes
        if (y < -10) {
          color.setHex(0x3a6b24); // Lush green valley
        } else if (y < 5) {
          color.setHex(0x4a7a2e); // Bright green grass
        } else if (y < 20) {
          color.setHex(0x3e6928); // Medium green slopes
        } else {
          const rocky = Math.sin(x * 0.3 + z * 0.5) > 0.3;
          color.setHex(rocky ? 0x666655 : 0x4a6a30);
        }
      }
      
      colors[i] = color.r;
      colors[i + 1] = color.g;
      colors[i + 2] = color.b;
    }

    surfGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    surfGeom.computeVertexNormals(); // Recalculate lighting

    const surfMat = new THREE.MeshStandardMaterial({ 
      vertexColors: true,
      side: THREE.DoubleSide, 
      roughness: 0.9,
      metalness: 0.05
    });
    
    const surface = new THREE.Mesh(surfGeom, surfMat);
    surface.receiveShadow = true;
    surface.castShadow = true;
    this.group.add(surface);

    layers.forEach(layer => {
      const thickness = layer.topZ - layer.bottomZ;
      const centerY = layer.topZ - thickness / 2;

      const geom = new THREE.BoxGeometry(this.width, thickness, this.depthY, segmentsX, 1, segmentsZ);
      
      // Cap layer vertices to follow terrain (creating a true geological cutaway block)
      const layerPos = geom.attributes.position.array as Float32Array;
      for (let j = 0; j < layerPos.length; j += 3) {
        const lx = layerPos[j];
        const lz = layerPos[j+2];
        const worldY = centerY + layerPos[j+1];
        const terrainY = Calculations.getTerrainHeight(lx, lz);
        
        // Cap the world Y at the terrain height
        const cappedWorldY = Math.min(worldY, terrainY);
        
        // Assign local Y
        layerPos[j+1] = cappedWorldY - centerY;
      }
      geom.computeVertexNormals();

      const mat = new THREE.MeshStandardMaterial({
        color: layer.color,
        transparent: true,
        opacity: 0.6,
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
      mesh.position.set(0, centerY, 0); // World Z = 0 for center
      mesh.userData = { id: layer.id, name: layer.name };
      mesh.receiveShadow = true;
      mesh.castShadow = true;
      
      this.group.add(mesh);
      this.layerMeshes.push(mesh);
      
      // Wireframe helper
      const edges = new THREE.EdgesGeometry(geom);
      const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.2 });
      lineMat.onBeforeCompile = clipShader;
      const line = new THREE.LineSegments(edges, lineMat);
      mesh.add(line);
    });
  }

  public setOpacity(opacity: number) {
    this.layerMeshes.forEach(mesh => {
      (mesh.material as THREE.MeshStandardMaterial).opacity = opacity;
    });
  }

  public setVisibility(visible: boolean) {
    this.group.visible = visible;
  }
}
