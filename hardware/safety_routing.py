"""
safety_routing.py — Mine Worker Evacuation & Safety Routing Engine
Calculates optimal minimum-risk escape routes away from CRITICAL geotechnical zones.
Input: 10x10 risk matrix
Output: Per-step safe path coordinates, nearest portal exit, and evacuation window.
"""
import heapq
from typing import List, Tuple, Dict, Any

DEFAULT_EXITS = [(0, 0), (0, 9), (9, 0), (9, 9)]

def dijkstra_safety(
    risk_grid: List[List[float]],
    start: Tuple[int, int] = (4, 5),
    exits: List[Tuple[int, int]] = DEFAULT_EXITS,
    cell_distance_m: float = 10.0,
    evac_speed_mps: float = 1.2
) -> Dict[str, Any]:
    """
    Finds the minimum-risk evacuation path from start location to the safest reachable mine exit.
    Edge cost = base traversal distance penalty + geotechnical risk score of target cell.
    """
    n_rows = len(risk_grid)
    n_cols = len(risk_grid[0]) if n_rows > 0 else 0

    sr, sc = start
    # Bounds check
    sr = max(0, min(n_rows - 1, sr))
    sc = max(0, min(n_cols - 1, sc))

    dist = [[float('inf')] * n_cols for _ in range(n_rows)]
    dist[sr][sc] = 0.0

    # Priority queue stores: (accumulated_cost, (r, c), path_coords)
    pq = [(0.0, (sr, sc), [(sr, sc)])]
    visited = set()

    best_result = None

    while pq:
        cost, (r, c), path = heapq.heappop(pq)

        if (r, c) in visited:
            continue
        visited.add((r, c))

        # Check if an exit is reached
        if (r, c) in exits:
            total_dist_m = len(path) * cell_distance_m
            evac_time_sec = total_dist_m / max(0.5, evac_speed_mps)
            evac_time_min = round(evac_time_sec / 60.0, 1)

            detailed_path = []
            for pr, pc in path:
                cell_risk = risk_grid[pr][pc] if 0 <= pr < n_rows and 0 <= pc < n_cols else 0.0
                detailed_path.append({
                    "r": pr,
                    "c": pc,
                    "node_id": pr * 10 + pc,
                    "x": pc * cell_distance_m,
                    "y": pr * cell_distance_m,
                    "risk": round(cell_risk, 2)
                })

            exit_names = {
                (0, 0): "Portal A (North-West Adit)",
                (0, 9): "Portal B (North-East Incline)",
                (9, 0): "Shaft C (South-West Shaft)",
                (9, 9): "Shaft D (South-East Ventilation)"
            }

            best_result = {
                "success": True,
                "start": {"r": sr, "c": sc, "node_id": sr * 10 + sc},
                "exit": {"r": r, "c": c, "name": exit_names.get((r, c), f"Exit ({r},{c})")},
                "total_risk_score": round(cost, 2),
                "steps": len(path),
                "distance_meters": round(total_dist_m, 1),
                "estimated_evac_time_min": evac_time_min,
                "path": detailed_path
            }
            break

        # 4-directional moves (North, South, West, East)
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n_rows and 0 <= nc < n_cols:
                # Hazard cost: cell risk + base movement cost
                cell_hazard = max(0.1, float(risk_grid[nr][nc]))
                step_cost = 1.0 + (cell_hazard ** 1.5)
                new_cost = cost + step_cost

                if new_cost < dist[nr][nc]:
                    dist[nr][nc] = new_cost
                    heapq.heappush(pq, (new_cost, (nr, nc), path + [(nr, nc)]))

    if not best_result:
        return {
            "success": False,
            "start": {"r": sr, "c": sc},
            "total_risk_score": 999.0,
            "steps": 0,
            "path": [],
            "message": "No reachable path to designated mine exits"
        }

    return best_result
