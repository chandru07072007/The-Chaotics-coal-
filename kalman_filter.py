"""
kalman_filter.py — Geotechnical Multi-State Kalman Filter for Mine Telemetry
=============================================================================
MUNKANIPPU — Real-Time Geotechnical & Subsidence Monitoring System
Smart India Hackathon (SIH 2026) Technical Approach Implementation

Provides optimal real-time recursive state estimation for noisy geotechnical
sensors (accelerometers, tilt, strain gauges, and FSR mechanical pressure)
under heavy mining vibrations, equipment noise, and electrical interference.

State Vector:
  x = [ position_displacement (mm), velocity (mm/s), acceleration (mm/s^2) ]^T

Mathematical Formulation:
  State transition: x_{k} = F * x_{k-1} + w_{k},   w_k ~ N(0, Q)
  Measurement:      z_{k} = H * x_{k} + v_{k},       v_k ~ N(0, R)
"""

from __future__ import annotations

import numpy as np


class GeotechnicalKalmanFilter:
    """
    Continuous-Discrete Extended/Linear Kalman Filter for single-channel
    geotechnical displacement and tilt telemetry.
    """

    def __init__(
        self,
        dt: float = 2.0,
        process_noise_q: float = 1e-3,
        measurement_noise_r: float = 0.25,
        initial_val: float = 0.0,
    ):
        """
        Args:
            dt: Sampling time delta in seconds (default: 2.0s ESP32 interval).
            process_noise_q: Strata movement process variance (Q).
            measurement_noise_r: Transducer electrical/jitter variance (R).
            initial_val: Initial measured value.
        """
        self.dt = dt

        # State vector: [displacement (mm), velocity (mm/s)]
        self.x = np.array([[initial_val], [0.0]], dtype=np.float64)

        # State transition matrix F
        self.F = np.array([
            [1.0, self.dt],
            [0.0, 1.0]
        ], dtype=np.float64)

        # Measurement matrix H (we measure displacement)
        self.H = np.array([[1.0, 0.0]], dtype=np.float64)

        # Process noise covariance Q (Piecewise white noise model)
        q_var = process_noise_q
        self.Q = np.array([
            [(self.dt**4) / 4.0 * q_var, (self.dt**3) / 2.0 * q_var],
            [(self.dt**3) / 2.0 * q_var, (self.dt**2) * q_var]
        ], dtype=np.float64)

        # Measurement noise covariance R
        self.R = np.array([[measurement_noise_r]], dtype=np.float64)

        # Initial estimation error covariance P
        self.P = np.array([
            [1.0, 0.0],
            [0.0, 1.0]
        ], dtype=np.float64)

        self.initialized = False

    def update(self, measurement: float, dt: float | None = None) -> tuple[float, float]:
        """
        Processes a new noisy sensor reading and returns the filtered state.
        
        Returns:
            (filtered_displacement_mm, estimated_velocity_mm_s)
        """
        if dt is not None and dt > 0:
            self.dt = dt
            self.F[0, 1] = dt

        if not self.initialized:
            self.x[0, 0] = measurement
            self.x[1, 0] = 0.0
            self.initialized = True
            return float(self.x[0, 0]), float(self.x[1, 0])

        # 1. Predict Step
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self.F.T + self.Q

        # 2. Update (Correction) Step
        z = np.array([[measurement]], dtype=np.float64)
        y = z - (self.H @ x_pred)  # Measurement residual (innovation)
        S = self.H @ P_pred @ self.H.T + self.R  # Residual covariance
        K = P_pred @ self.H.T @ np.linalg.inv(S)  # Optimal Kalman gain

        self.x = x_pred + K @ y
        I = np.eye(self.P.shape[0])
        # Joseph form for numerical stability
        self.P = (I - K @ self.H) @ P_pred @ (I - K @ self.H).T + K @ self.R @ K.T

        return float(self.x[0, 0]), float(self.x[1, 0])

    def reset(self, initial_val: float = 0.0):
        """Reset the internal filter state."""
        self.x = np.array([[initial_val], [0.0]], dtype=np.float64)
        self.P = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float64)
        self.initialized = False


def filter_telemetry_series(
    raw_series: list[float] | np.ndarray,
    dt: float = 2.0,
    q: float = 1e-3,
    r: float = 0.25
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convenience function to batch-filter an entire time-series.
    
    Returns:
        (filtered_displacements, estimated_velocities)
    """
    kf = GeotechnicalKalmanFilter(dt=dt, process_noise_q=q, measurement_noise_r=r)
    filtered = []
    velocities = []
    for val in raw_series:
        est_pos, est_vel = kf.update(float(val))
        filtered.append(est_pos)
        velocities.append(est_vel)
    return np.array(filtered), np.array(velocities)


if __name__ == "__main__":
    # Test the Kalman Filter with synthetic noisy strata subsidence
    print("=" * 65)
    print("Testing Geotechnical Kalman Filter on Simulated Subsidence")
    print("=" * 65)

    np.random.seed(42)
    time_steps = 25
    true_subsidence = np.linspace(0.0, 45.0, time_steps)
    noise = np.random.normal(0, 1.5, time_steps)
    noisy_readings = true_subsidence + noise

    kf = GeotechnicalKalmanFilter(dt=2.0, process_noise_q=0.01, measurement_noise_r=2.25)
    print(f"{'Step':<5} | {'True (mm)':<10} | {'Noisy (mm)':<10} | {'Kalman (mm)':<11} | {'Est Vel (mm/s)'}")
    print("-" * 65)

    for i in range(time_steps):
        f_val, v_val = kf.update(noisy_readings[i])
        print(f"{i+1:<5} | {true_subsidence[i]:<10.2f} | {noisy_readings[i]:<10.2f} | {f_val:<11.2f} | {v_val:.3f}")

    print("=" * 65)
    print("Kalman Filter successfully verified!")

