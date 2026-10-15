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
    this.scene.background = new THREE.Color(0x8899aa); // Overcast sky
    this.scene.fog = new THREE.FogExp2(0x8899aa, 0.003); // Atmospheric distance fog

    this.camera = new THREE.PerspectiveCamera(55, container.clientWidth / container.clientHeight, 0.1, 2000);
    // Position camera just inside the left portal, looking down the tunnel
    this.camera.position.set(-140, -18, 0);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    // Target the center of the tunnel
    this.controls.target.set(0, -20, 0);
    this.controls.maxDistance = 500;
    this.controls.maxPolarAngle = Math.PI / 2 + 0.2; // Allow looking slightly below the horizon

    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.setupLighting();
    
    window.addEventListener('resize', this.onResize.bind(this));
  }

  private setupLighting() {
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambient);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.6);
    hemiLight.position.set(0, 200, 0);
    this.scene.add(hemiLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(100, 200, 50);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 4096;
    dirLight.shadow.mapSize.height = 4096;
    dirLight.shadow.camera.left = -200;
    dirLight.shadow.camera.right = 200;
    dirLight.shadow.camera.top = 200;
    dirLight.shadow.camera.bottom = -200;
    dirLight.shadow.bias = -0.0001;
    this.scene.add(dirLight);
    
    // Grid and Axes for engineering look
    const grid = new THREE.GridHelper(400, 40, 0x444444, 0x222222);
    this.scene.add(grid);

    const axes = new THREE.AxesHelper(50);
    this.scene.add(axes);
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
