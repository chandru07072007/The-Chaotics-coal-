import GUI from 'lil-gui';
import type { TunnelConfig, GeologicalLayer, SensorData, SegmentAnalysis } from './DataModel';
import { Calculations } from './Calculations';
import { ThreeScene } from './ThreeScene';
import { TunnelView } from './TunnelView';
import { GeologyView } from './GeologyView';
import { SensorView } from './SensorView';
import { UIManager } from './UIManager';
import * as THREE from 'three';

export class DigitalTwinManager {
  private tunnelConfig: TunnelConfig;
  private layers: GeologicalLayer[];
  private sensors: SensorData[] = [];
  private analysis: SegmentAnalysis[] = [];

  private sceneWrapper: ThreeScene;
  private tunnelView: TunnelView;
  private geologyView: GeologyView;
  private sensorView: SensorView;
  private uiManager: UIManager;

  private params = {
    waterTableZ: -12,
    simulationActive: false,
    stressMult: 1.0,
    waterMult: 1.0,
    defMult: 1.0,
    weightStress: 0.5,
    weightDef: 0.3,
    weightWater: 0.2,
    layerOpacity: 0.6,
    tunnelOpacity: 1.0,
    showGeology: true
  };

  private raycaster = new THREE.Raycaster();
  private mouse = new THREE.Vector2();

  constructor() {
    this.tunnelConfig = {
      length: 300,
      internalDiameter: 6,
      liningThickness: 0.4,
      depthZ: -20,
      numSegments: 60
    };

    this.layers = [
      { id: 'L-1', name: 'Topsoil', topZ: 0, bottomZ: -2, density: 1600, cohesion: 10, frictionAngle: 25, allowableStress: 100, color: 0x8B4513 },
      { id: 'L-2', name: 'Loose Sand', topZ: -2, bottomZ: -7, density: 1800, cohesion: 5, frictionAngle: 30, allowableStress: 180, color: 0xDAA520 },
      { id: 'L-3', name: 'Stiff Clay', topZ: -7, bottomZ: -12, density: 1900, cohesion: 50, frictionAngle: 20, allowableStress: 250, color: 0xD2691E },
      { id: 'L-4', name: 'Weathered Rock', topZ: -12, bottomZ: -17, density: 2200, cohesion: 150, frictionAngle: 35, allowableStress: 1000, color: 0x808080 },
      { id: 'L-5', name: 'Hard Rock', topZ: -17, bottomZ: -50, density: 2700, cohesion: 1000, frictionAngle: 45, allowableStress: 5000, color: 0x404040 }
    ];

    this.sceneWrapper = new ThreeScene('canvas-container');
    this.uiManager = new UIManager();
    this.tunnelView = new TunnelView(this.tunnelConfig);
    this.geologyView = new GeologyView();
    this.sensorView = new SensorView(this.tunnelConfig);

    this.sceneWrapper.scene.add(this.tunnelView.group);
    this.sceneWrapper.scene.add(this.geologyView.group);
    this.sceneWrapper.scene.add(this.sensorView.group);

    this.setupGUI();
    this.initSensors();
    this.build3D();
    this.updateAnalysis();
    this.setupEvents();
    this.setupCameraControls();

    this.loop();
  }

  private setupGUI() {
    const gui = new GUI({ title: 'Digital Twin Controls' });
    
    const fTunnel = gui.addFolder('Tunnel Parameters');
    fTunnel.add(this.tunnelConfig, 'depthZ', -40, 0, 1).name('Tunnel Depth').onChange(() => this.rebuildAll());
    fTunnel.add(this.params, 'tunnelOpacity', 0.1, 1).name('Exterior Opacity').onChange((v: number) => this.tunnelView.setExteriorOpacity(v));
    
    const fGeo = gui.addFolder('Geology Parameters');
    fGeo.add(this.params, 'showGeology').name('Show Geology').onChange((v: boolean) => this.geologyView.setVisibility(v));
    fGeo.add(this.params, 'layerOpacity', 0.1, 1).name('Layer Opacity').onChange((v: number) => this.geologyView.setOpacity(v));

    const fEnv = gui.addFolder('Environmental');
    fEnv.add(this.params, 'waterTableZ', -50, 0, 1).name('Groundwater Lvl').onChange(() => this.updateAnalysis());

    const fSim = gui.addFolder('Simulation');
    fSim.add(this.params, 'simulationActive').name('Run Simulation');
    fSim.add(this, 'resetSimulation').name('Reset Values');
    fSim.add({ addStress: () => { this.params.stressMult += 0.1; this.updateAnalysis(); } }, 'addStress').name('Stress +10%');
    fSim.add({ addWater: () => { this.params.waterMult += 0.1; this.updateAnalysis(); } }, 'addWater').name('Water +10%');
    fSim.add({ addDef: () => { this.params.defMult += 0.1; this.updateAnalysis(); } }, 'addDef').name('Deformation +10%');
  }

  private setupCameraControls() {
    document.getElementById('cam-iso')?.addEventListener('click', () => {
      this.sceneWrapper.camera.position.set(150, 80, 100);
      this.sceneWrapper.controls.target.set(0, -15, 0);
    });
    document.getElementById('cam-top')?.addEventListener('click', () => {
      this.sceneWrapper.camera.position.set(0, 200, 1);
      this.sceneWrapper.controls.target.set(0, 0, 0);
    });
    document.getElementById('cam-front')?.addEventListener('click', () => {
      // Looking at the tunnel portal from outside (like the reference photo)
      this.sceneWrapper.camera.position.set(-180, 5, 15);
      this.sceneWrapper.controls.target.set(-150, this.tunnelConfig.depthZ, 0);
    });
    document.getElementById('cam-side')?.addEventListener('click', () => {
      this.sceneWrapper.camera.position.set(0, 20, 120);
      this.sceneWrapper.controls.target.set(0, this.tunnelConfig.depthZ, 0);
    });
    document.getElementById('cam-inside')?.addEventListener('click', () => {
      let maxA = this.analysis[0];
      for(const a of this.analysis) {
        if(a.riskScore > maxA.riskScore) maxA = a;
      }
      if (maxA) {
        // Place camera inside the tunnel, slightly before the failure segment, looking down the tunnel
        this.sceneWrapper.camera.position.set(maxA.centerX - 10, maxA.centerZ - 0.5, 0);
        this.sceneWrapper.controls.target.set(maxA.centerX, maxA.centerZ - 0.5, 0);
      }
    });
    document.getElementById('cam-failure')?.addEventListener('click', () => {
      let maxA = this.analysis[0];
      for(const a of this.analysis) {
        if(a.riskScore > maxA.riskScore) maxA = a;
      }
      if (maxA) {
        this.sceneWrapper.camera.position.set(maxA.centerX + 20, maxA.centerZ + 20, 20);
        this.sceneWrapper.controls.target.set(maxA.centerX, maxA.centerZ, 0);
      }
    });
  }

  private setupEvents() {
    window.addEventListener('click', (e) => {
      if ((e.target as HTMLElement).tagName !== 'CANVAS') return;
      this.mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      this.mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
      
      this.raycaster.setFromCamera(this.mouse, this.sceneWrapper.camera);
      const intersects = this.raycaster.intersectObjects(this.tunnelView.group.children, true);
      
      if (intersects.length > 0) {
        let object = intersects[0].object;
        while(object.parent && !object.userData.id) {
          object = object.parent;
        }
        const id = object.userData.id;
        if (id) {
          const a = this.analysis.find(an => an.id === id);
          this.uiManager.showSelectedSegment(a || null);
        }
      } else {
        this.uiManager.showSelectedSegment(null);
      }
    });
  }

  private initSensors() {
    this.sensors = [];
    for (let i = 0; i < this.tunnelConfig.numSegments; i++) {
      const id = `T-${(i + 1).toString().padStart(3, '0')}`;
      
      // Default baseline values
      let stress = 100 + Math.random() * 50;
      let def = 1 + Math.random() * 2;
      let wp = 20 + Math.random() * 20;

      // Create an artificial critical zone at T-030
      if (id === 'T-030') {
        stress = 500;
        def = 25;
        wp = 180;
      } else if (id === 'T-029' || id === 'T-031') {
        stress = 400 + Math.random() * 50;
        def = 15 + Math.random() * 5;
        wp = 140 + Math.random() * 20;
      }

      this.sensors.push({
        id: `S-${(i+1).toString().padStart(3, '0')}`,
        segmentId: id,
        stress,
        deformation: def,
        waterPressure: wp
      });
    }
  }

  public resetSimulation() {
    this.params.stressMult = 1.0;
    this.params.waterMult = 1.0;
    this.params.defMult = 1.0;
    this.initSensors();
    this.updateAnalysis();
  }

  private build3D() {
    this.tunnelView.build();
    this.geologyView.build(this.layers);
  }

  private rebuildAll() {
    this.build3D();
    this.updateAnalysis();
  }

  private updateAnalysis() {
    this.analysis = [];
    let maxRiskScore = -1;
    let maxRiskSegment: SegmentAnalysis | null = null;
    const segLength = this.tunnelConfig.length / this.tunnelConfig.numSegments;
    for (let i = 0; i < this.tunnelConfig.numSegments; i++) {
      const segId = `T-${(i + 1).toString().padStart(3, '0')}`;
      const xPos = -this.tunnelConfig.length / 2 + (i + 0.5) * segLength;
      
      const terrainZ = Calculations.getTerrainHeight(xPos, 0);
      const layer = Calculations.getLayerAtDepth(this.layers, this.tunnelConfig.depthZ);
      const overburden = Calculations.calculateOverburden(this.layers, this.tunnelConfig.depthZ, terrainZ);
      const wpIdeal = Calculations.calculateWaterPressure(this.tunnelConfig.depthZ, this.params.waterTableZ);
      
      const baseSensor = this.sensors.find(s => s.segmentId === segId)!;
      const sensor = {
        ...baseSensor,
        stress: baseSensor.stress * this.params.stressMult,
        deformation: baseSensor.deformation * this.params.defMult,
        waterPressure: baseSensor.waterPressure * this.params.waterMult
      };

      const weights = { stress: this.params.weightStress, def: this.params.weightDef, water: this.params.weightWater };
      const risk = Calculations.calculateRisk(sensor, layer, weights, layer.allowableStress, 50, wpIdeal * 2 || 200);

      const a: SegmentAnalysis = {
        id: segId,
        centerX: xPos,
        centerZ: this.tunnelConfig.depthZ,
        geoLayer: layer,
        overburdenStress: overburden,
        effectiveStress: overburden - wpIdeal,
        stressRatio: sensor.stress / layer.allowableStress,
        safetyFactor: risk.safetyFactor,
        damageIndex: risk.riskScore / 100, // simplified mapping
        riskScore: risk.riskScore,
        status: risk.status as any,
        sensor
      };

      this.analysis.push(a);

      if (a.riskScore > maxRiskScore) {
        maxRiskScore = a.riskScore;
        maxRiskSegment = a;
      }

      // Update segment color
      let color = 0x10b981; // SAFE - green
      if (a.status === 'NORMAL') color = 0x3b82f6; // blue
      else if (a.status === 'WARNING') color = 0xf59e0b; // yellow
      else if (a.status === 'CRITICAL') color = 0xef4444; // red
      
      this.tunnelView.updateSegmentColor(a.id, color);
    }

    if (maxRiskSegment) {
      this.uiManager.updateDashboard(this.analysis, maxRiskSegment);
      this.sensorView.updateFailurePrediction(maxRiskSegment.centerX, maxRiskSegment.centerZ, maxRiskSegment.riskScore);
    }
  }

  private loop = () => {
    requestAnimationFrame(this.loop);
    
    if (this.params.simulationActive) {
      // randomly jitter values slightly
      let changed = false;
      this.sensors.forEach(s => {
        if (Math.random() < 0.1) {
          s.stress += (Math.random() - 0.5) * 5;
          s.deformation += (Math.random() - 0.5) * 0.2;
          s.waterPressure += (Math.random() - 0.5) * 2;
          changed = true;
        }
      });
      if (changed) this.updateAnalysis();
    }

    this.sceneWrapper.render();
  }
}
