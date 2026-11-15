"""
microclimate_model.py — 2D Microclimate & Soil Saturation Model
Correlates surface temperature, moisture, and historical subsidence to
estimate accelerated displacement risk in saturated or thermally stressed zones.
"""
import numpy as np
from typing import Dict, Any, List

class MicroclimateModel:
    def __init__(self, grid_size: int = 10):
        self.grid_size = grid_size
        self.temp_grid = np.ones((grid_size, grid_size)) * 25.0
        self.moisture_grid = np.ones((grid_size, grid_size)) * 55.0
        self.heat_index = np.zeros((grid_size, grid_size))

    def update(self, temperature: float = 25.0, moisture_pct: float = 55.0, center: tuple = (4, 5)):
        """Gaussian diffusion of heat and moisture across the 10x10 geotechnical grid."""
        cx, cy = center
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                dist = np.sqrt((r - cx) ** 2 + (c - cy) ** 2)
                decay = np.exp(-dist ** 2 / (2 * (2.8 ** 2)))
                self.temp_grid[r, c] = 24.0 + (temperature - 24.0) * decay
                self.moisture_grid[r, c] = 50.0 + (moisture_pct - 50.0) * decay

        # Heat index: correlation between temperature excess and moisture saturation
        self.heat_index = (
            (self.temp_grid - 24.0) * 0.4 +
            (self.moisture_grid - 50.0) * 0.6
        )
        self.heat_index = np.clip(self.heat_index, 0, 100)

    def get_risk_grid(self) -> np.ndarray:
        """Returns a 10x10 acceleration multiplier for the geotechnical whatif engine."""
        return 1.0 + (self.heat_index / 100.0) * 0.35

    def get_summary(self) -> Dict[str, Any]:
        return {
            "mean_temp_c": round(float(np.mean(self.temp_grid)), 2),
            "max_temp_c": round(float(np.max(self.temp_grid)), 2),
            "mean_moisture_pct": round(float(np.mean(self.moisture_grid)), 2),
            "max_moisture_pct": round(float(np.max(self.moisture_grid)), 2),
            "heat_island_intensity": round(float(np.max(self.heat_index)), 2),
            "grid_size": self.grid_size
        }

microclimate_model = MicroclimateModel()
