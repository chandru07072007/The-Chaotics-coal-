import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

export class ThreeScene {
  public scene: THREE.Scene;
  public camera: THREE.PerspectiveCamera;
  public renderer: THREE.WebGLRenderer;
  public controls: OrbitControls;
  public raycaster: THREE.Raycaster;
  public mouse: THREE.Vector2;

  constructor(containerId: string) {
    const container = document.getElementById(containerId)!;
    
    this.scene = new THREE.Scene();
    
    // CesiumJS / Bentley iTwin Dark Geotechnical Subterranean Atmosphere (No harsh glare)
    this.scene.background = new THREE.Color(0x0a0f1d);
    this.scene.fog = new THREE.FogExp2(0x0a0f1d, 0.0022);

    this.camera = new THREE.PerspectiveCamera(54, container.clientWidth / container.clientHeight, 0.1, 2000);
    // Initial camera position: Inside the coal mine tunnel looking down the illuminated drift
    this.camera.position.set(-135, -20.2, 0);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    // Look straight down the tunnel gallery along the rails
    this.controls.target.set(-70, -20.2, 0);
    this.controls.maxDistance = 600;
    this.controls.maxPolarAngle = Math.PI / 2 + 0.15;

    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.setupLighting();
    
    window.addEventListener('resize', this.onResize.bind(this));
  }

  private setupLighting() {
    // 1. Soft subterranean ambient light (toned down, no blinding white glare)
    const ambient = new THREE.AmbientLight(0x94a3b8, 0.35);
    this.scene.add(ambient);

    // 2. Dual-hemisphere geotechnical sky & ground bounce
    const hemiLight = new THREE.HemisphereLight(0x38bdf8, 0x0f172a, 0.4);
    hemiLight.position.set(0, 150, 0);
    this.scene.add(hemiLight);

    // 3. Directional sun for surface terrain topography (soft daylight)
    const dirLight = new THREE.DirectionalLight(0xfff7ed, 0.55);
    dirLight.position.set(120, 180, 80);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.camera.left = -220;
    dirLight.shadow.camera.right = 220;
    dirLight.shadow.camera.top = 220;
    dirLight.shadow.camera.bottom = -220;
    dirLight.shadow.bias = -0.0002;
    this.scene.add(dirLight);

    // 4. Industrial Mining Portal Floodlights (authentic coal mine workface illumination)
    const portalSpotWest = new THREE.SpotLight(0xfef08a, 1.2, 140, Math.PI / 5, 0.5);
    portalSpotWest.position.set(-165, 8, 25);
    portalSpotWest.target.position.set(-145, -20, 0);
    this.scene.add(portalSpotWest);
    this.scene.add(portalSpotWest.target);

    const portalSpotEast = new THREE.SpotLight(0xfef08a, 1.2, 140, Math.PI / 5, 0.5);
    portalSpotEast.position.set(165, 8, 25);
    portalSpotEast.target.position.set(145, -20, 0);
    this.scene.add(portalSpotEast);
    this.scene.add(portalSpotEast.target);

    // 5. Engineering baseline grid (iTwin dark mode grid)
    const grid = new THREE.GridHelper(450, 45, 0x1e293b, 0x0f172a);
    grid.position.y = -50.1;
    this.scene.add(grid);
  }

  private onResize() {
    const container = this.renderer.domElement.parentElement;
    if (!container) return;
    this.camera.aspect = container.clientWidth / container.clientHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(container.clientWidth, container.clientHeight);
  }

  public render() {
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}
