import * as h3 from 'h3-js';
import { DEMLoader, type DEMTileData } from './DEMLoader';

export interface SpatialNode {
  node_id: number;
  lat: number;
  lon: number;
  risk_tier?: string;
  displacement_mm?: number;
  temperature_c?: number;
  tilt_deg?: number;
  moisture_pct?: number;
}

export class RegionalView {
  private viewer: any = null;
  private container: HTMLElement | null = null;
  private hexEntities: any[] = [];
  private nodeEntities: any[] = [];
  private isInitialized = false;
  private isVisible = false;
  private pollInterval: any = null;

  constructor(containerId: string = 'cesium-container') {
    this.container = document.getElementById(containerId);
  }

  public async init(): Promise<boolean> {
    if (this.isInitialized) return true;
    if (!this.container) return false;

    // Check if Cesium is available globally
    const Cesium = (window as any).Cesium;
    if (!Cesium) {
      console.warn('[RegionalView] Cesium global not found. Loading dynamically...');
      await this.loadCesiumScripts();
    }

    const CesiumObj = (window as any).Cesium;
    if (!CesiumObj) {
      console.error('[RegionalView] Failed to load Cesium library.');
      return false;
    }

    try {
      // Default to Cesium ION token or offline mode
      CesiumObj.Ion.defaultAccessToken = '';

      this.viewer = new CesiumObj.Viewer(this.container, {
        animation: false,
        baseLayerPicker: false,
        fullscreenButton: false,
        geocoder: false,
        homeButton: false,
        infoBox: false,
        sceneModePicker: false,
        selectionIndicator: false,
        timeline: false,
        navigationHelpButton: false,
        navigationInstructionsInitiallyVisible: false,
        terrainProvider: new CesiumObj.EllipsoidTerrainProvider(),
      });

      // Fly to Jharia / Dhanbad Coalfields region
      const centerLon = 84.1314;
      const centerLat = 23.6102;
      this.viewer.camera.flyTo({
        destination: CesiumObj.Cartesian3.fromDegrees(centerLon, centerLat, 3500),
        orientation: {
          heading: CesiumObj.Math.toRadians(0.0),
          pitch: CesiumObj.Math.toRadians(-45.0),
          roll: 0.0,
        },
        duration: 2.0,
      });

      this.isInitialized = true;

      // Fetch DEM metadata in background
      DEMLoader.fetchTile(centerLat, centerLon).then((demData: DEMTileData) => {
        console.log(`[RegionalView] DEM tile loaded: ${demData.width}x${demData.height}, elev range: ${demData.minElevation}-${demData.maxElevation}m`);
      });

      return true;
    } catch (err) {
      console.error('[RegionalView] Initialization error:', err);
      return false;
    }
  }

  public toggle(show?: boolean) {
    if (!this.container) return;
    this.isVisible = show !== undefined ? show : !this.isVisible;
    this.container.style.display = this.isVisible ? 'block' : 'none';

    if (this.isVisible) {
      if (!this.isInitialized) {
        this.init().then(() => {
          this.fetchAndRenderNodes();
          this.startLivePolling();
        });
      } else {
        this.fetchAndRenderNodes();
        this.startLivePolling();
      }
    } else {
      this.stopLivePolling();
    }
  }

  public getVisible(): boolean {
    return this.isVisible;
  }

  public updateHexLayer(nodes: SpatialNode[]) {
    if (!this.viewer || !(window as any).Cesium) return;
    const Cesium = (window as any).Cesium;

    // Clear existing hex entities
    for (const ent of this.hexEntities) {
      this.viewer.entities.remove(ent);
    }
    this.hexEntities = [];

    // Clear existing node markers
    for (const ent of this.nodeEntities) {
      this.viewer.entities.remove(ent);
    }
    this.nodeEntities = [];

    // Group nodes by H3 cell at resolution 8 (~460m hex diameter)
    const h3Resolution = 8;
    const cellGroups = new Map<string, SpatialNode[]>();

    for (const node of nodes) {
      const cell = h3.latLngToCell(node.lat, node.lon, h3Resolution);
      if (!cellGroups.has(cell)) {
        cellGroups.set(cell, []);
      }
      cellGroups.get(cell)!.push(node);

      // Add pin/marker for each physical/simulated sensor node
      const marker = this.viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(node.lon, node.lat, 25),
        point: {
          pixelSize: 10,
          color: Cesium.Color.fromCssColorString(this.getTierColor(node.risk_tier || 'SAFE')),
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2,
        },
        label: {
          text: `Node #${node.node_id}\n${node.displacement_mm?.toFixed(1) || '0.0'} mm`,
          font: '11px sans-serif',
          fillColor: Cesium.Color.WHITE,
          showBackground: true,
          backgroundColor: new Cesium.Color(0.06, 0.09, 0.16, 0.8),
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(0, -12),
        },
      });
      this.nodeEntities.push(marker);
    }

    // Render each H3 hexagon
    cellGroups.forEach((cellNodes, cellIndex) => {
      try {
        const boundary = h3.cellToBoundary(cellIndex); // [[lat, lng], ...]
        const degreesArray: number[] = [];
        for (const [bLat, bLon] of boundary) {
          degreesArray.push(bLon, bLat);
        }

        // Aggregate statistics for this cell
        let maxDisp = 0;
        let worstTier = 'SAFE';
        for (const n of cellNodes) {
          const d = n.displacement_mm || 0;
          if (d > maxDisp) maxDisp = d;
          if (n.risk_tier === 'CRITICAL') worstTier = 'CRITICAL';
          else if (n.risk_tier === 'WARNING' && worstTier !== 'CRITICAL') worstTier = 'WARNING';
          else if (n.risk_tier === 'ADVISORY' && worstTier === 'SAFE') worstTier = 'ADVISORY';
        }

        const colorStr = this.getTierColor(worstTier);
        const hexEntity = this.viewer.entities.add({
          name: `H3 Hex Cell: ${cellIndex}`,
          polygon: {
            hierarchy: Cesium.Cartesian3.fromDegreesArray(degreesArray),
            material: Cesium.Color.fromCssColorString(colorStr).withAlpha(0.45),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString(colorStr),
            outlineWidth: 2,
            height: 5,
          },
          description: `
            <div style="padding: 8px; font-family: sans-serif; color: #fff;">
              <h3 style="margin: 0 0 6px 0; color: ${colorStr};">H3 Cell: ${cellIndex}</h3>
              <p><strong>Nodes Count:</strong> ${cellNodes.length}</p>
              <p><strong>Peak Subsidence:</strong> ${maxDisp.toFixed(2)} mm</p>
              <p><strong>DGMS Risk Status:</strong> ${worstTier}</p>
            </div>
          `,
        });
        this.hexEntities.push(hexEntity);
      } catch (e) {
        console.warn('[RegionalView] Failed to render hex cell:', cellIndex, e);
      }
    });
  }

  private getTierColor(tier: string): string {
    switch (tier.toUpperCase()) {
      case 'CRITICAL':
        return '#ef4444';
      case 'WARNING':
        return '#f97316';
      case 'ADVISORY':
        return '#facc15';
      case 'SAFE':
      default:
        return '#10b981';
    }
  }

  public async fetchAndRenderNodes() {
    try {
      const res = await fetch('http://localhost:8080/api/spatial/nodes');
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.ok && Array.isArray(data.nodes)) {
        this.updateHexLayer(data.nodes);
      }
    } catch (err) {
      console.warn('[RegionalView] Failed to fetch spatial nodes:', err);
    }
  }

  private startLivePolling() {
    this.stopLivePolling();
    this.pollInterval = setInterval(() => {
      if (this.isVisible) {
        this.fetchAndRenderNodes();
      }
    }, 4000);
  }

  private stopLivePolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  private loadCesiumScripts(): Promise<void> {
    return new Promise((resolve, reject) => {
      if ((window as any).Cesium) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Cesium.js';
      script.onload = () => resolve();
      script.onerror = (e) => reject(e);
      document.head.appendChild(script);

      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Widgets/widgets.css';
      document.head.appendChild(link);
    });
  }
}
