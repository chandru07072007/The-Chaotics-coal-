import React, { useState, useEffect } from 'react';
import PredictionView from './PredictionView.jsx';

export default function Dashboard({ user, onLogout }) {
  const [activeNav, setActiveNav] = useState('Dashbored');
  const [availablePorts, setAvailablePorts] = useState([]);

  // Port 1: HX711 + ADXL345 + MPU6500 Impact Load Node
  const [port1, setPort1] = useState('No Port Selected');
  const [conn1, setConn1] = useState(false);

  // Port 2: Mountain Trekker Safety Watch (MPU6050 + Dallas + Soil)
  const [port2, setPort2] = useState('No Port Selected');
  const [conn2, setConn2] = useState(false);

  // Consolidated Telemetry Metrics
  const [dualData, setDualData] = useState(null);
  const [moisture, setMoisture] = useState(56.5);
  const [force, setForce] = useState(78);
  const [ttc, setTtc] = useState('4.33');
  const [disp, setDisp] = useState('42.50');
  const [dgmsTier, setDgmsTier] = useState('WARNING');

  // Fetch status and telemetry
  const fetchStatus = () => {
    fetch('http://localhost:8080/api/status')
      .then(r => r.json())
      .then(d => {
        if (d.ports && d.ports.length > 0) {
          const portList = d.ports.map(p => (typeof p === 'object' && p !== null ? p.device || p.description : String(p)));
          setAvailablePorts(portList);
          if (port1 === 'No Port Selected' && portList.length > 0) setPort1(portList[0]);
          if (port2 === 'No Port Selected' && portList.length > 1) setPort2(portList[1]);
        }
      })
      .catch(() => {});

    // Fetch unified dual-hardware stream
    fetch('http://localhost:8080/api/dual/status')
      .then(r => r.json())
      .then(d => {
        if (d && d.ok) {
          setDualData(d);
          if (d.node1_hx711_impact?.connected) setConn1(true);
          if (d.node2_trekker?.connected) setConn2(true);
          
          if (d.fused_telemetry) {
            setMoisture(d.fused_telemetry.moisture_pct);
            setForce(d.fused_telemetry.force_level);
            setDisp(d.fused_telemetry.displacement_mm);
            if (d.fused_telemetry.ttc_hours) setTtc(d.fused_telemetry.ttc_hours);
            if (d.fused_telemetry.dgms_tier) setDgmsTier(d.fused_telemetry.dgms_tier);
          }
        }
      })
      .catch(() => {});

    fetch('http://localhost:8080/api/ai_prediction')
      .then(r => r.json())
      .then(d => {
        if (d && d.ok) {
          if (d.ttc_hours !== undefined) setTtc(d.ttc_hours);
          if (d.dgms_risk_tier) setDgmsTier(d.dgms_risk_tier);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 1500);
    return () => clearInterval(interval);
  }, []);

  const handleConnectPort = (nodeIndex, selectedPort) => {
    fetch(`http://localhost:8080/api/dual/connect?node=${nodeIndex}&port=${encodeURIComponent(selectedPort)}&baud=115200`)
      .then(r => r.json())
      .then(d => {
        if (nodeIndex === 1) setConn1(d.connected);
        if (nodeIndex === 2) setConn2(d.connected);
      })
      .catch(() => {
        if (nodeIndex === 1) setConn1(!conn1);
        if (nodeIndex === 2) setConn2(!conn2);
      });
  };

  const n1 = dualData?.node1_hx711_impact || {};
  const n2 = dualData?.node2_trekker || {};
  const fused = dualData?.fused_telemetry || {};

  return (
    <div className="munkanippu-dashboard">
      {/* Top Header */}
      <header className="mk-header">
        <div className="mk-brand">MUNKANIPPU</div>

        <nav className="mk-nav">
          <button
            className={`mk-nav-item ${activeNav === 'Dashbored' ? 'active' : ''}`}
            onClick={() => setActiveNav('Dashbored')}
          >
            Dashbored
          </button>
          <button
            className={`mk-nav-item ${activeNav === '3d Twin' ? 'active' : ''}`}
            onClick={() => setActiveNav('3d Twin')}
          >
            3d Twin
          </button>
          <button
            className={`mk-nav-item ${activeNav === 'Prediction' ? 'active' : ''}`}
            onClick={() => setActiveNav('Prediction')}
          >
            Prediction
          </button>
          <button className="mk-logout-btn" onClick={onLogout}>
            logout
          </button>
        </nav>
      </header>

      {/* Main Tab Content */}
      <main className="mk-content" style={{ display: activeNav === 'Dashbored' ? 'flex' : 'none' }}>
        
        {/* DUAL HARDWARE PORTS CONNECTION BAR */}
        <div className="dual-port-bar-container">
          {/* Hardware Port 1 Bar */}
          <div className="mk-conn-bar dual-card">
            <div className={`mk-conn-status ${conn1 ? 'connected' : 'disconnected'}`}>
              <span className="status-dot"></span>
              {conn1 ? 'PORT 1: ONLINE (HARDWARE)' : 'PORT 1: STREAMING (SIM)'}
            </div>

            <div className="mk-cable-info">
              <span className="cable-label">NODE 1: HX711 + ADXL345 SPI + MPU6500</span>
              <span className="cable-val">{conn1 ? port1 : 'Auto-Emulated Dual Transducers'}</span>
            </div>

            <select
              className="mk-select port-select"
              value={port1}
              onChange={(e) => setPort1(e.target.value)}
            >
              {availablePorts.length > 0 ? (
                availablePorts.map((p, idx) => <option key={'p1_' + idx} value={p}>{p}</option>)
              ) : (
                <option value="No COM ports found">No COM ports found</option>
              )}
            </select>

            <button className={`mk-btn ${conn1 ? 'mk-btn-disconnect' : 'mk-btn-primary'}`} onClick={() => handleConnectPort(1, port1)}>
              {conn1 ? 'Disconnect' : 'Connect Port 1'}
            </button>
          </div>

          {/* Hardware Port 2 Bar */}
          <div className="mk-conn-bar dual-card">
            <div className={`mk-conn-status ${conn2 ? 'connected' : 'disconnected'}`}>
              <span className="status-dot"></span>
              {conn2 ? 'PORT 2: ONLINE (HARDWARE)' : 'PORT 2: STREAMING (SIM)'}
            </div>

            <div className="mk-cable-info">
              <span className="cable-label">NODE 2: MPU6050 + DALLAS DS18B20 + SOIL</span>
              <span className="cable-val">{conn2 ? port2 : 'Auto-Emulated Safety Watch'}</span>
            </div>

            <select
              className="mk-select port-select"
              value={port2}
              onChange={(e) => setPort2(e.target.value)}
            >
              {availablePorts.length > 0 ? (
                availablePorts.map((p, idx) => <option key={'p2_' + idx} value={p}>{p}</option>)
              ) : (
                <option value="No COM ports found">No COM ports found</option>
              )}
            </select>

            <button className={`mk-btn ${conn2 ? 'mk-btn-disconnect' : 'mk-btn-primary'}`} onClick={() => handleConnectPort(2, port2)}>
              {conn2 ? 'Disconnect' : 'Connect Port 2'}
            </button>
          </div>
        </div>

        {/* 3 Main Colored Rectangles */}
        <div className="mk-cards-grid">
          {/* Box 1: Reddish / Coral / Moisture Sensor (From Node 2 Soil Moisture + Dallas) */}
          <div className="mk-sensor-box box-moisture">
            <span className="box-title">Moisture Sensor</span>
            <div className="box-value">{moisture} <span className="box-unit">%</span></div>
            <div className="box-sub">Soil Raw: {n2.soil_raw || 1780} &bull; Dallas Temp: {n2.temperature_c || 24.62}°C</div>
          </div>

          {/* Box 2: Warm Yellow / Force-Sensing (From Node 1 HX711 Load Cell) */}
          <div className="mk-sensor-box box-force">
            <span className="box-title">Force-Sensing</span>
            <div className="box-value">{force} <span className="box-unit">%</span></div>
            <div className="box-sub">HX711 Δ: {n1.load_change >= 0 ? '+' : ''}{n1.load_change || '+1420'} &bull; Raw: {n1.raw_load || 8345420}</div>
          </div>

          {/* Box 3: Light Grey / TTC (From Combined Impact / Convergence) */}
          <div className="mk-sensor-box box-ttc">
            <span className="box-title">TTC</span>
            <div className="box-value">{ttc} <span className="box-unit">hrs</span></div>
            <div className="box-sub">ADXL Peak: {n1.adxl_peak || 0.045}g &bull; DGMS: {dgmsTier}</div>
          </div>
        </div>

        {/* DUAL HARDWARE REAL-TIME TELEMETRY MATRIX */}
        <div className="dual-hardware-matrix-grid">
          {/* Sub-Card 1: Node 1 Live Impact & Load Stream */}
          <div className="hardware-node-detail-card">
            <div className="card-top-tag">
              <span>HARDWARE PORT 1 STREAM &bull; IMPACT & LOAD TRANSDUCERS</span>
              <span className="status-badge" style={{ background: conn1 ? '#10b981' : '#facc15', color: conn1 ? '#fff' : '#000' }}>
                {conn1 ? 'ACTIVE (HARDWARE)' : 'STREAMING (SIM)'}
              </span>
            </div>
            <div className="sensor-readout-rows">
              <div className="readout-row">
                <span>HX711 Zero Offset / Raw:</span>
                <strong>{n1.zero_offset || 8344000} / {n1.raw_load || 8345420}</strong>
              </div>
              <div className="readout-row">
                <span>Load Cell Change (Δ):</span>
                <strong style={{ color: '#ef4444' }}>
                  {n1.load_change >= 0 ? '+' : ''}{n1.load_change || '+1420'}
                </strong>
              </div>
              <div className="readout-row">
                <span>ADXL345 SPI (Resultant / Peak):</span>
                <strong>{n1.adxl_mag || 1.002} g (Peak: {n1.adxl_peak || 0.045} g)</strong>
              </div>
              <div className="readout-row">
                <span>MPU6500 I2C (Resultant / Peak):</span>
                <strong>{n1.mpu_mag || 0.998} g (Peak: {n1.mpu_peak || 0.038} g)</strong>
              </div>
              <div className="readout-row">
                <span>Micro-Seismic Shock Trigger:</span>
                <span style={{ fontSize: '0.82rem', color: n1.last_impact ? '#ef4444' : '#64748b', fontWeight: 600 }}>
                  {n1.last_impact || 'Listening for high-g shockwaves (>0.5g)...'}
                </span>
              </div>
              {n1.last_impact_parsed && (
                <div className="readout-row" style={{ background: 'rgba(239, 68, 68, 0.08)', padding: '4px 8px', borderRadius: '4px' }}>
                  <span>Wavefront Propagation Gap:</span>
                  <strong style={{ color: '#ef4444' }}>
                    {n1.last_impact_parsed.gap_us} μs (First: {n1.last_impact_parsed.first})
                  </strong>
                </div>
              )}
            </div>
          </div>

          {/* Sub-Card 2: Node 2 Live Mountain Trekker Safety Watch */}
          <div className="hardware-node-detail-card">
            <div className="card-top-tag">
              <span>HARDWARE PORT 2 STREAM &bull; MOUNTAIN TREKKER SAFETY WATCH</span>
              <span className="status-badge" style={{ background: conn2 ? '#10b981' : '#facc15', color: conn2 ? '#fff' : '#000' }}>
                {conn2 ? 'ACTIVE (HARDWARE)' : 'STREAMING (SIM)'}
              </span>
            </div>
            <div className="sensor-readout-rows">
              <div className="readout-row">
                <span>MPU6050 Accelerometer (X, Y, Z):</span>
                <strong>
                  {n2.accel ? `${n2.accel[0]}g, ${n2.accel[1]}g, ${n2.accel[2]}g` : '0.020g, -0.010g, 0.980g'}
                </strong>
              </div>
              <div className="readout-row">
                <span>MPU6050 Gyroscope (X, Y, Z):</span>
                <strong>
                  {n2.gyro ? `${n2.gyro[0]}, ${n2.gyro[1]}, ${n2.gyro[2]} °/s` : '0.12, -0.08, 0.05 °/s'}
                </strong>
              </div>
              <div className="readout-row">
                <span>Dallas DS18B20 Strata Temp:</span>
                <strong style={{ color: '#0284c7' }}>{n2.temperature_c || 24.62} °C</strong>
              </div>
              <div className="readout-row">
                <span>Capacitive Soil Moisture Probe:</span>
                <strong style={{ color: '#059669' }}>
                  {n2.moisture_pct || 56.5}% (Raw: {n2.soil_raw || 1780})
                </strong>
              </div>
              <div className="readout-row">
                <span>Calculated Strata Tilt Angle:</span>
                <strong>{fused.tilt_deg !== undefined ? fused.tilt_deg : '0.22'}°</strong>
              </div>
              <div className="readout-row" style={{ background: 'rgba(56, 189, 248, 0.08)', padding: '4px 8px', borderRadius: '4px' }}>
                <span>Fused Estimated Subsidence:</span>
                <strong style={{ color: '#0284c7' }}>{disp} mm</strong>
              </div>
            </div>
          </div>
        </div>

        {/* Complete Hardware Embedded Dashboard underneath */}
        <div className="mk-embedded-hardware-section">
          <div className="mk-embedded-header">
            <span>FULL DUAL-PORT HARDWARE TELEMETRY CONSOLE & OSCILLOSCOPE</span>
            <a href="http://localhost:8080/" target="_blank" rel="noreferrer" className="mk-link">
              Open Full Hardware Hub in New Tab
            </a>
          </div>
          <iframe
            src="http://localhost:8080/"
            title="Complete Dual ESP32 Node Reading"
            className="mk-hardware-iframe"
            scrolling="yes"
          />
        </div>
      </main>

      {/* 3d Twin Tab */}
      <div className="mk-iframe-wrap" style={{ display: activeNav === '3d Twin' ? 'flex' : 'none' }}>
        <iframe
          src="http://localhost:5174/"
          title="3D Digital Twin"
          className="mk-iframe"
          style={{ border: 'none' }}
        />
      </div>

      {/* Prediction Tab */}
      <div className="mk-iframe-wrap" style={{ display: activeNav === 'Prediction' ? 'flex' : 'none' }}>
        <PredictionView />
      </div>
    </div>
  );
}
