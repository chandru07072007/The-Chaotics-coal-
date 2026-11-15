export interface DEMTileData {
  width: number;
  height: number;
  minElevation: number;
  maxElevation: number;
  elevationGrid: Float32Array;
  bounds: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
}

export class DEMLoader {
  static async fetchTile(lat: number = 23.6102, lon: number = 84.1314): Promise<DEMTileData> {
    try {
      const url = `http://localhost:8080/api/dem?lat=${lat}&lon=${lon}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('DEM API error');
      const data = await res.json();
      return {
        width: data.width || 32,
        height: data.height || 32,
        minElevation: data.min_elev || 180,
        maxElevation: data.max_elev || 320,
        elevationGrid: new Float32Array(data.elevations || []),
        bounds: data.bounds || {
          north: lat + 0.05,
          south: lat - 0.05,
          east: lon + 0.05,
          west: lon - 0.05
        }
      };
    } catch {
      // Fallback synthetic 32x32 terrain grid for regional mine topography
      const width = 32;
      const height = 32;
      const grid = new Float32Array(width * height);
      for (let r = 0; r < height; r++) {
        for (let c = 0; c < width; c++) {
          const dist = Math.sqrt((r - 16) ** 2 + (c - 16) ** 2);
          grid[r * width + c] = 220 + Math.sin(r * 0.3) * 15 + Math.cos(c * 0.3) * 15 - dist * 1.5;
        }
      }
      return {
        width,
        height,
        minElevation: 190,
        maxElevation: 250,
        elevationGrid: grid,
        bounds: {
          north: lat + 0.05,
          south: lat - 0.05,
          east: lon + 0.05,
          west: lon - 0.05
        }
      };
    }
  }
}
