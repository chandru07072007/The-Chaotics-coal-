import React, { useState, useEffect, useRef } from 'react';
import './Prediction.css';

export default function PredictionView() {
  const [activeSubTab, setActiveSubTab] = useState('what_if'); // 'what_if', 'current', 'prediction', 'risk', 'node_twin'
  const [selectedNodeId, setSelectedNodeId] = useState(45);
  const [twinData, setTwinData] = useState(null);
  const [selectedNodeDetails, setSelectedNodeDetails] = useState(null);

  // What-If Simulation State
  const [stressMult, setStressMult] = useState(1.4);
  const [waterPct, setWaterPct] = useState(75);
  const [vibG, setVibG] = useState(0.45);
  const [hours, setHours] = useState(24);
  const [epicenterNode, setEpicenterNode] = useState(45);
  const [whatIfData, setWhatIfData] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [rotAngle, setRotAngle] = useState(35); // 3D rotation angle
  const canvasRef = useRef(null);

  // Poll Python Digital Twin Analytics Endpoint
  const fetchAnalytics = () => {
    fetch('http://localhost:8080/api/twin/analytics')
      .then(res => res.json())
      .then(data => {
        if (data && data.ok) {
          setTwinData(data);
        }
      })
      .catch(() => {});
  };

  // Fetch individual node twin state
  const fetchNodeTwin = (id) => {
    setSelectedNodeId(id);
    fetch(`http://localhost:8080/api/twin/node?id=${id}`)
      .then(res => res.json())
      .then(data => {
        if (data && data.ok) {
          setSelectedNodeDetails(data.node);
        }
      })
      .catch(() => {});
  };

  // Compute or Fetch What-If Simulation
  const computeWhatIf = () => {
    fetch(`http://localhost:8080/api/twin/whatif?stress=${stressMult}&water=${waterPct}&vib=${vibG}&hours=${hours}&center=${epicenterNode}`)
      .then(res => res.json())
      .then(data => {
        if (data && data.ok) {
          setWhatIfData(data);
        } else {
          fallbackClientWhatIf();
        }
      })
      .catch(() => {
        fallbackClientWhatIf();
      });
  };

  // Immediate Client-Side Calculation Fallback (ensures 60fps instant response)
  const fallbackClientWhatIf = () => {
    const center_r = Math.floor(epicenterNode / 10);
    const center_c = epicenterNode % 10;
    const sim_nodes = [];
    let max_disp = 0.0;
    let crit_count = 0;
    let warn_count = 0;

    for (let r = 0; r < 10; r++) {
      for (let c = 0; c < 10; c++) {
        const nid = r * 10 + c;
        const dist = Math.sqrt(Math.pow(c - center_c, 2) + Math.pow(r - center_r, 2));
        const trough_i = 3.2;
        const influence = Math.exp(-Math.pow(dist, 2) / (2 * Math.pow(trough_i, 2)));

        const base_disp = 12.0 + (32.0 * influence);
        const stress_factor = stressMult;
        const water_factor = 1.0 + (waterPct / 100.0) * 0.45;
        const vib_factor = 1.0 + (vibG * 0.35);
        const time_factor = 1.0 + (hours / 24.0) * 0.28;

        const sim_disp = Number((base_disp * stress_factor * water_factor * vib_factor * time_factor).toFixed(2));
        const delta = Number((sim_disp - base_disp).toFixed(2));

        let tier = 'SAFE';
        let color = '#10b981';
        if (sim_disp >= 50.0) {
          tier = 'CRITICAL';
          color = '#ef4444';
          crit_count++;
        } else if (sim_disp >= 25.0) {
          tier = 'WARNING';
          color = '#f97316';
          warn_count++;
        } else if (sim_disp >= 10.0) {
          tier = 'ADVISORY';
          color = '#facc15';
        }

        if (sim_disp > max_disp) max_disp = sim_disp;

        sim_nodes.push({
          node_id: nid,
          r,
          c,
          x: c * 10.0,
          y: r * 10.0,
          base_disp,
          sim_disp,
          delta,
          risk_tier: tier,
          color
        });
      }
    }

    const ttc = Number(Math.max(0.4, 24.0 / (1.0 + max_disp * 0.08 + vibG * 4.0)).toFixed(2));
    const dgms_overall = max_disp >= 50.0 ? 'CRITICAL' : (max_disp >= 25.0 ? 'WARNING' : 'ADVISORY');

    setWhatIfData({
      ok: true,
      max_disp_mm: max_disp,
      delta_max_mm: Number((max_disp - 44.0).toFixed(2)),
      affected_area_m2: (crit_count + warn_count) * 100,
      crit_count,
      warn_count,
      ttc_hours: ttc,
      dgms_tier: dgms_overall,
      nodes: sim_nodes
    });
  };

  useEffect(() => {
    fetchAnalytics();
    fetchNodeTwin(45);
    computeWhatIf();

    const interval = setInterval(() => {
      fetchAnalytics();
      fetchNodeTwin(selectedNodeId);
    }, 3000);
    return () => clearInterval(interval);
  }, [selectedNodeId]);

  useEffect(() => {
    computeWhatIf();
  }, [stressMult, waterPct, vibG, hours, epicenterNode]);

  // Render 3D Surface Mesh Graph on Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !whatIfData?.nodes) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Coordinate settings
    const originX = width / 2;
    const originY = height * 0.42;
    const scale = 22;
    const zScale = 1.35;
    const rad = (rotAngle * Math.PI) / 180;
    const cosA = Math.cos(rad);
    const sinA = Math.sin(rad);

    // 3D projection function
    const project = (r, c, z) => {
      const x = (c - 4.5) * scale;
      const y = (r - 4.5) * scale;
      // Rotate around Z axis
      const rx = x * cosA - y * sinA;
      const ry = x * sinA + y * cosA;
      // Isometric tilt
      const px = originX + rx * 1.1;
      const py = originY + ry * 0.55 - z * zScale;
      return { px, py };
    };

    // Draw grid quads from back to front
    const nodes = whatIfData.nodes;
    for (let r = 0; r < 9; r++) {
      for (let c = 0; c < 9; c++) {
        const n00 = nodes[r * 10 + c];
        const n01 = nodes[r * 10 + (c + 1)];
        const n11 = nodes[(r + 1) * 10 + (c + 1)];
        const n10 = nodes[(r + 1) * 10 + c];

        if (!n00 || !n01 || !n11 || !n10) continue;

        const p00 = project(r, c, -n00.sim_disp);
        const p01 = project(r, c + 1, -n01.sim_disp);
        const p11 = project(r + 1, c + 1, -n11.sim_disp);
        const p10 = project(r + 1, c, -n10.sim_disp);

        // Calculate average displacement for quad color
        const avgDisp = (n00.sim_disp + n01.sim_disp + n11.sim_disp + n10.sim_disp) / 4;
        let fillColor = 'rgba(16, 185, 129, 0.55)'; // Safe green
        if (avgDisp >= 50) fillColor = 'rgba(239, 68, 68, 0.75)'; // Critical red
        else if (avgDisp >= 25) fillColor = 'rgba(249, 115, 22, 0.65)'; // Warning orange
        else if (avgDisp >= 10) fillColor = 'rgba(250, 204, 21, 0.55)'; // Advisory yellow

        ctx.beginPath();
        ctx.moveTo(p00.px, p00.py);
        ctx.lineTo(p01.px, p01.py);
        ctx.lineTo(p11.px, p11.py);
        ctx.lineTo(p10.px, p10.py);
        ctx.closePath();

        ctx.fillStyle = fillColor;
        ctx.fill();

        ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    // Draw Borehole Probe at Epicenter Node
    const epiR = Math.floor(epicenterNode / 10);
    const epiC = epicenterNode % 10;
    const epiNode = nodes[epicenterNode];
    if (epiNode) {
      const topP = project(epiR, epiC, 0); // Ground surface baseline
      const defP = project(epiR, epiC, -epiNode.sim_disp); // Deformed bottom

      // Vertical Borehole Axis
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      ctx.moveTo(topP.px, topP.py);
      ctx.lineTo(defP.px, defP.py);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.setLineDash([]);

      // Baseline reference ring
      ctx.beginPath();
      ctx.ellipse(topP.px, topP.py, 12, 6, 0, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
      ctx.stroke();

      // Deformed trough point
      ctx.beginPath();
      ctx.arc(defP.px, defP.py, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#ef4444';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 12px monospace';
      ctx.fillText(`Epicenter #${epicenterNode} (-${epiNode.sim_disp}mm)`, defP.px + 10, defP.py + 4);
    }
  }, [whatIfData, rotAngle, epicenterNode]);

  // Scenario Presets
  const applyPreset = (preset) => {
    switch (preset) {
      case 'monsoon':
        setStressMult(1.1);
        setWaterPct(95);
        setVibG(0.12);
        setHours(24);
        break;
      case 'mining':
        setStressMult(1.85);
        setWaterPct(40);
        setVibG(0.35);
        setHours(48);
        break;
      case 'rupture':
        setStressMult(2.3);
        setWaterPct(80);
        setVibG(1.5);
        setHours(12);
        break;
      case 'mitigation':
        setStressMult(0.65);
        setWaterPct(20);
        setVibG(0.02);
        setHours(72);
        break;
      case 'baseline':
      default:
        setStressMult(1.0);
        setWaterPct(50);
        setVibG(0.05);
        setHours(24);
        break;
    }
  };

  const getTierColor = (tier) => {
    switch (tier) {
      case 'CRITICAL': return '#ef4444';
      case 'WARNING': return '#f97316';
      case 'ADVISORY': return '#facc15';
      case 'SAFE':
      default: return '#10b981';
    }
  };

  const sim3D = selectedNodeDetails?.sim_3d;

  return (
    <div className="prediction-container">
      {/* Sub-navigation bar separating the analytics sections */}
      <div className="pred-subnav">
        <button
          className={`pred-nav-btn ${activeSubTab === 'what_if' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('what_if')}
        >
          WHAT-IF SIMULATION (HEATMAP & 3D GRAPH)
        </button>
        <button
          className={`pred-nav-btn ${activeSubTab === 'current' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('current')}
        >
          CURRENT DEFORMATION FIELD
        </button>
        <button
          className={`pred-nav-btn ${activeSubTab === 'prediction' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('prediction')}
        >
          24H SUBSIDENCE FORECAST
        </button>
        <button
          className={`pred-nav-btn ${activeSubTab === 'risk' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('risk')}
        >
          DGMS RISK ZONES
        </button>
        <button
          className={`pred-nav-btn ${activeSubTab === 'node_twin' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('node_twin')}
        >
          3D STRUCTURAL DIGITAL TWIN (PER-NODE)
        </button>
      </div>

      {/* Main Content Area */}
      <div className="pred-content">
        
        {/* ========================================================
            SECTION: WHAT-IF SIMULATION IN HEATMAP & 3D GRAPH
            ======================================================== */}
        {activeSubTab === 'what_if' && (
          <div className="whatif-panel">
            
            {/* Header with Title & Scenario Presets */}
            <div className="whatif-header">
              <div>
                <h2>WHAT-IF SUBSIDENCE PROPAGATION SIMULATOR</h2>
                <p>Simulate overburden stress surges, pore-water infiltration, and seismic shocks across the 100-node geotechnical field</p>
              </div>
              <div className="whatif-presets">
                <span className="preset-lbl">SCENARIOS:</span>
                <button className="preset-btn" onClick={() => applyPreset('monsoon')}>Monsoon Saturation</button>
                <button className="preset-btn" onClick={() => applyPreset('mining')}>High-Speed Mining</button>
                <button className="preset-btn" onClick={() => applyPreset('rupture')}>Seismic Rupture</button>
                <button className="preset-btn" onClick={() => applyPreset('mitigation')}>Pillar Grouting</button>
                <button className="preset-btn reset" onClick={() => applyPreset('baseline')}>Reset</button>
              </div>
            </div>

            {/* Interactive Sliders Control Bar */}
            <div className="whatif-controls-grid">
              <div className="control-slider-box">
                <div className="slider-header">
                  <span>OVERBURDEN STRESS MULTIPLIER</span>
                  <strong>{stressMult.toFixed(2)}×</strong>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="2.5"
                  step="0.05"
                  value={stressMult}
                  onChange={(e) => setStressMult(parseFloat(e.target.value))}
                />
                <span className="slider-sub">Simulates mining advance void pressure</span>
              </div>

              <div className="control-slider-box">
                <div className="slider-header">
                  <span>PORE-WATER SATURATION</span>
                  <strong>{waterPct}%</strong>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={waterPct}
                  onChange={(e) => setWaterPct(parseInt(e.target.value))}
                />
                <span className="slider-sub">Hydrostatic groundwater infiltration</span>
              </div>

              <div className="control-slider-box">
                <div className="slider-header">
                  <span>MICRO-SEISMIC SHOCK (RMS)</span>
                  <strong>{vibG.toFixed(2)} g</strong>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="2.0"
                  step="0.05"
                  value={vibG}
                  onChange={(e) => setVibG(parseFloat(e.target.value))}
                />
                <span className="slider-sub">Dynamic strata rupture amplitude</span>
              </div>

              <div className="control-slider-box">
                <div className="slider-header">
                  <span>TIME HORIZON FORECAST</span>
                  <strong>+{hours} hrs</strong>
                </div>
                <input
                  type="range"
                  min="0"
                  max="72"
                  step="6"
                  value={hours}
                  onChange={(e) => setHours(parseInt(e.target.value))}
                />
                <span className="slider-sub">Subsidence trough development window</span>
              </div>
            </div>

            {/* 4 Real-time Impact KPI Summary Cards */}
            <div className="whatif-kpi-row">
              <div className="kpi-mini-card">
                <span className="kpi-mini-lbl">SIMULATED PEAK SUBSIDENCE</span>
                <div className="kpi-mini-val" style={{ color: getTierColor(whatIfData?.dgms_tier || 'SAFE') }}>
                  {whatIfData?.max_disp_mm || 42.5} mm
                </div>
                <span className="kpi-mini-sub">
                  Δ vs Baseline: <strong>{whatIfData?.delta_max_mm >= 0 ? '+' : ''}{whatIfData?.delta_max_mm || 0} mm</strong>
                </span>
              </div>

              <div className="kpi-mini-card">
                <span className="kpi-mini-lbl">HIGH-RISK SURFACE AREA</span>
                <div className="kpi-mini-val" style={{ color: '#ea580c' }}>
                  {whatIfData?.affected_area_m2 || 3200} m²
                </div>
                <span className="kpi-mini-sub">
                  Critical Nodes: <strong>{whatIfData?.crit_count || 0}</strong> &bull; Warning: <strong>{whatIfData?.warn_count || 0}</strong>
                </span>
              </div>

              <div className="kpi-mini-card">
                <span className="kpi-mini-lbl">SIMULATED TIME-TO-CRITICAL</span>
                <div className="kpi-mini-val" style={{ color: '#dc2626' }}>
                  {whatIfData?.ttc_hours || 4.33} hrs
                </div>
                <span className="kpi-mini-sub">Estimated time before strata failure</span>
              </div>

              <div className="kpi-mini-card">
                <span className="kpi-mini-lbl">STATUTORY DGMS RISK TIER</span>
                <div className="kpi-mini-val" style={{ color: getTierColor(whatIfData?.dgms_tier || 'SAFE') }}>
                  {whatIfData?.dgms_tier || 'SAFE'}
                </div>
                <span className="kpi-mini-sub">Indian Coal Mines Regulations threshold</span>
              </div>
            </div>

            {/* Dual Visualizations: Heatmap on Left, 3D Graph on Right */}
            <div className="whatif-vis-grid">
              
              {/* Left Column: What-If 10x10 Dynamic Subsidence Heatmap */}
              <div className="vis-card">
                <div className="vis-card-header">
                  <div>
                    <span>WHAT-IF SURFACE SUBSIDENCE HEATMAP (10×10 NODES)</span>
                    <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block' }}>
                      Click any cell to set excavation epicenter &bull; Currently: Node #{epicenterNode}
                    </span>
                  </div>
                  <div className="legend-mini">
                    <span style={{ color: '#10b981' }}>■ &lt;10mm</span>
                    <span style={{ color: '#facc15' }}>■ 10-25mm</span>
                    <span style={{ color: '#f97316' }}>■ 25-50mm</span>
                    <span style={{ color: '#ef4444' }}>■ &ge;50mm</span>
                  </div>
                </div>

                <div className="whatif-grid-container">
                  <div className="whatif-grid-100">
                    {whatIfData?.nodes?.map((node) => {
                      const isEpicenter = node.node_id === epicenterNode;
                      return (
                        <div
                          key={node.node_id}
                          className={`whatif-node-cell ${isEpicenter ? 'epicenter' : ''}`}
                          style={{
                            backgroundColor: node.color,
                            boxShadow: isEpicenter ? '0 0 12px #ffffff, inset 0 0 8px #000' : 'none'
                          }}
                          onClick={() => setEpicenterNode(node.node_id)}
                          onMouseEnter={() => setHoveredNode(node)}
                          onMouseLeave={() => setHoveredNode(null)}
                        >
                          <span className="cell-num">{node.node_id}</span>
                          <span className="cell-disp">{Math.round(node.sim_disp)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Hover Details Bar */}
                <div className="node-hover-bar">
                  {hoveredNode ? (
                    <span>
                      Node <strong>#{hoveredNode.node_id}</strong> &bull; Coord: ({hoveredNode.x}m, {hoveredNode.y}m) &bull; 
                      Simulated: <strong style={{ color: hoveredNode.color }}>{hoveredNode.sim_disp} mm</strong> (Δ: {hoveredNode.delta >= 0 ? '+' : ''}{hoveredNode.delta}mm) &bull; 
                      Risk: <strong style={{ color: hoveredNode.color }}>{hoveredNode.risk_tier}</strong>
                    </span>
                  ) : (
                    <span>Hover over any grid node to view localized simulated deformation and risk</span>
                  )}
                </div>
              </div>

              {/* Right Column: What-If 3D Surface & Strata Mesh Graph */}
              <div className="vis-card">
                <div className="vis-card-header">
                  <div>
                    <span>WHAT-IF 3D SURFACE & STRATA DEFORMATION MESH GRAPH</span>
                    <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block' }}>
                      Real-time isometric subsidence trough &bull; Rotate angle: {rotAngle}°
                    </span>
                  </div>
                  <div className="rot-controls">
                    <button className="rot-btn" onClick={() => setRotAngle((a) => (a - 15 + 360) % 360)}>Rotate Left</button>
                    <button className="rot-btn" onClick={() => setRotAngle((a) => (a + 15) % 360)}>Rotate Right</button>
                  </div>
                </div>

                <div className="canvas-3d-wrap">
                  <canvas
                    ref={canvasRef}
                    width={560}
                    height={380}
                    className="whatif-3d-canvas"
                  />
                  <div className="canvas-3d-legend">
                    <span>Elevation Depth: 0mm (Green) → 50mm+ (Red Trough)</span>
                  </div>
                </div>

                <div className="whatif-physics-footer">
                  <span>Geotechnical Law: <strong>Peck-Gaussian Subsidence Trough Equation</strong></span>
                  <code>S(x,y) = S_max × exp(-r² / 2i²)</code>
                </div>
              </div>

            </div>

          </div>
        )}

        {/* Section 1: Current Deformation Field */}
        {activeSubTab === 'current' && (
          <div className="pred-panel">
            <div className="pred-panel-header">
              <div>
                <h2>CURRENT SURFACE DEFORMATION FIELD (MEASURED)</h2>
                <p>NumPy/SciPy RBF multiquadric spatial interpolation based on 100 wireless surface nodes</p>
              </div>
              <div className="kpi-tag">
                Peak: <strong style={{ color: '#ef4444' }}>{twinData?.current_deformation?.max || 42.5} mm</strong>
              </div>
            </div>

            <div className="map-view-box">
              <iframe
                src="http://localhost:8080/gis"
                title="Current Deformation GIS"
                className="pred-iframe"
                scrolling="no"
              />
            </div>
          </div>
        )}

        {/* Section 2: 24h Subsidence Forecast */}
        {activeSubTab === 'prediction' && (
          <div className="pred-panel">
            <div className="pred-panel-header">
              <div>
                <h2>24-HOUR FUTURE SUBSIDENCE PREDICTION (t+24h)</h2>
                <p>Incremental temporal delta regression forecasting underground void convergence</p>
              </div>
              <div className="kpi-tag">
                Predicted Max: <strong style={{ color: '#f97316' }}>{twinData?.subsidence_prediction?.max || 48.2} mm</strong>
              </div>
            </div>

            <div className="map-view-box">
              <iframe
                src="http://localhost:8080/gis"
                title="Subsidence Prediction GIS"
                className="pred-iframe"
                scrolling="no"
              />
            </div>
          </div>
        )}

        {/* Section 3: DGMS Risk Zones */}
        {activeSubTab === 'risk' && (
          <div className="pred-panel">
            <div className="pred-panel-header">
              <div>
                <h2>DGMS STATUTORY SUBSIDENCE RISK ZONES</h2>
                <p>Directorate General of Mines Safety compliance thresholds with spatial boundaries</p>
              </div>
              <div className="risk-legend-pills">
                <span className="pill safe">SAFE (&lt;10mm)</span>
                <span className="pill advisory">ADVISORY (10-25mm)</span>
                <span className="pill warning">WARNING (25-50mm)</span>
                <span className="pill critical">CRITICAL (&ge;50mm)</span>
              </div>
            </div>

            <div className="map-view-box">
              <iframe
                src="http://localhost:8080/gis"
                title="DGMS Risk Zones GIS"
                className="pred-iframe"
                scrolling="no"
              />
            </div>
          </div>
        )}

        {/* Section 4: Per-Node 3D Structural Simulation Digital Twin */}
        {activeSubTab === 'node_twin' && (
          <div className="node-twin-layout">
            {/* Left: 100-Node Interactive Surface Grid Map */}
            <div className="grid-selector-panel">
              <div className="panel-title-bar">
                <span>10×10 SURFACE BENCHMARK GRID (SELECT NODE)</span>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Auto-Synced with ML Heatmap</span>
              </div>
              <div className="node-grid-100">
                {twinData?.nodes?.map((node) => {
                  const nodeColor = node.heatmap_color || getTierColor(node.risk_tier);
                  const isSelected = selectedNodeId === node.node_id;
                  return (
                    <button
                      key={node.node_id}
                      className={`node-pill ${isSelected ? 'selected' : ''}`}
                      style={{
                        borderColor: nodeColor,
                        backgroundColor: isSelected ? nodeColor : '#ffffff',
                        color: isSelected ? (node.risk_tier === 'ADVISORY' ? '#000' : '#fff') : '#000',
                        boxShadow: isSelected ? `0 0 10px ${nodeColor}` : 'none'
                      }}
                      onClick={() => fetchNodeTwin(node.node_id)}
                      title={`Node #${node.node_id} | Disp: ${node.displacement_mm}mm | Tier: ${node.risk_tier}`}
                    >
                      #{node.node_id}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Right: Individual Node 3D Structural Digital Twin Simulation */}
            <div className="node-twin-card">
              <div className="twin-card-header">
                <div>
                  <h3 style={{ fontSize: '1.4rem', fontFamily: 'monospace' }}>
                    3D DIGITAL TWIN ASSET: NODE #{selectedNodeDetails?.node_id ?? selectedNodeId}
                  </h3>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                    Surface Benchmark: ({selectedNodeDetails?.x ?? 50}m, {selectedNodeDetails?.y ?? 40}m) &bull; Depth: {selectedNodeDetails?.depth_z ?? -20}m &bull; Last Synced: {selectedNodeDetails?.last_sync || 'Live'}
                  </span>
                </div>
                <div
                  className="tier-badge"
                  style={{ backgroundColor: selectedNodeDetails?.heatmap_color || getTierColor(selectedNodeDetails?.risk_tier || 'SAFE') }}
                >
                  {selectedNodeDetails?.risk_tier || 'SAFE'}
                </div>
              </div>

              {/* 3D Structural Simulation Canvas (SVG Isometric Visualization) */}
              <div className="twin-3d-sim-container">
                <div className="sim-badge-overlay">
                  <span>3D STRUCTURAL BOREHOLE & STRATA DEFORMATION</span>
                  <span style={{ color: selectedNodeDetails?.heatmap_color || '#10b981' }}>
                    Convergence Offset: {sim3D?.convergence_factor ?? 0.21}m
                  </span>
                </div>
                <svg className="twin-3d-svg" viewBox="0 0 500 240">
                  <defs>
                    <linearGradient id="boreholeGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={selectedNodeDetails?.heatmap_color || '#10b981'} stopOpacity="0.8" />
                      <stop offset="50%" stopColor="#334155" stopOpacity="0.6" />
                      <stop offset="100%" stopColor="#0f172a" stopOpacity="0.9" />
                    </linearGradient>
                    <linearGradient id="surfaceGrad" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#e2e8f0" />
                      <stop offset="50%" stopColor={selectedNodeDetails?.heatmap_color || '#10b981'} stopOpacity="0.4" />
                      <stop offset="100%" stopColor="#e2e8f0" />
                    </linearGradient>
                  </defs>

                  {/* Surface Ground Plane */}
                  <polygon points="50,60 250,20 450,60 250,100" fill="url(#surfaceGrad)" stroke="#94a3b8" strokeWidth="1.5" />

                  {/* Underground Strata Depth Projection Lines */}
                  <line x1="50" y1="60" x2="50" y2="180" stroke="#64748b" strokeDasharray="3 3" />
                  <line x1="450" y1="60" x2="450" y2="180" stroke="#64748b" strokeDasharray="3 3" />
                  <line x1="250" y1="100" x2="250" y2="220" stroke="#334155" strokeWidth="1.5" />

                  {/* Bottom Underground Mining Floor */}
                  <polygon points="50,180 250,140 450,180 250,220" fill="#1e293b" stroke="#475569" strokeWidth="1.5" />

                  {/* 3D Vertical Borehole Sensor Casing Cylinder */}
                  <path d="M 235,60 L 235,180 A 15,6 0 0,0 265,180 L 265,60 Z" fill="url(#boreholeGrad)" stroke={selectedNodeDetails?.heatmap_color || '#10b981'} strokeWidth="2" />
                  
                  {/* Top Casing Cap (Deformed by subsidence) */}
                  <ellipse cx="250" cy="60" rx="15" ry="6" fill={selectedNodeDetails?.heatmap_color || '#10b981'} stroke="#ffffff" strokeWidth="1.5" />

                  {/* Bottom Anchor Cap */}
                  <ellipse cx="250" cy="180" rx="15" ry="6" fill="#0f172a" stroke={selectedNodeDetails?.heatmap_color || '#10b981'} strokeWidth="1.5" />

                  {/* Visual Displacement Delta Vector Arrow */}
                  <line x1="280" y1="45" x2="280" y2="75" stroke="#ef4444" strokeWidth="2.5" markerEnd="url(#arrow)" />
                  <text x="290" y="65" fill="#ef4444" fontSize="12" fontWeight="bold">
                    Δ: {selectedNodeDetails?.displacement_mm ?? 42.5} mm
                  </text>

                  {/* Micro-seismic vibration ripples */}
                  <ellipse cx="250" cy="120" rx="35" ry="12" fill="none" stroke={selectedNodeDetails?.heatmap_color || '#10b981'} strokeWidth="1" strokeDasharray="2 2" opacity="0.7">
                    <animate attributeName="rx" values="25;45;25" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.8;0.2;0.8" dur="2s" repeatCount="indefinite" />
                  </ellipse>
                </svg>
              </div>

              {/* State Vector Metrics */}
              <div className="twin-metrics-grid">
                <div className="metric-box">
                  <span className="metric-lbl">CURRENT DISPLACEMENT</span>
                  <span className="metric-val">{selectedNodeDetails?.displacement_mm ?? 42.5} mm</span>
                  <span className="metric-sub">Thermal drift compensated</span>
                </div>

                <div className="metric-box">
                  <span className="metric-lbl">24H SUBSIDENCE FORECAST</span>
                  <span className="metric-val" style={{ color: selectedNodeDetails?.heatmap_color || getTierColor(selectedNodeDetails?.risk_tier || 'SAFE') }}>
                    {selectedNodeDetails?.pred_24h_mm ?? 48.2} mm
                  </span>
                  <span className="metric-sub">Incremental delta estimation</span>
                </div>

                <div className="metric-box">
                  <span className="metric-lbl">CONVERGENCE VELOCITY</span>
                  <span className="metric-val">{selectedNodeDetails?.velocity_mm_h ?? 0.85} mm/h</span>
                  <span className="metric-sub">Rate of ground subsidence</span>
                </div>

                <div className="metric-box">
                  <span className="metric-lbl">TIME-TO-CRITICAL (TTC)</span>
                  <span className="metric-val" style={{ color: '#ef4444' }}>
                    {selectedNodeDetails?.ttc_hours ?? 4.33} hrs
                  </span>
                  <span className="metric-sub">Window before rupture</span>
                </div>

                <div className="metric-box">
                  <span className="metric-lbl">GROUND TILT (INCLINOMETER)</span>
                  <span className="metric-val">{selectedNodeDetails?.tilt_deg ?? 4.2}°</span>
                  <span className="metric-sub">Pitch/Roll resultant vector</span>
                </div>

                <div className="metric-box">
                  <span className="metric-lbl">GROUND VIBRATION (RMS)</span>
                  <span className="metric-val">{selectedNodeDetails?.vibration_rms ?? 9.85} m/s²</span>
                  <span className="metric-sub">Micro-seismic dynamics</span>
                </div>
              </div>

              {/* Downstream AI CLI Command Display */}
              <div className="cli-command-box">
                <span className="cli-title">DOWNSTREAM AI CLI EXECUTION HOOK:</span>
                <code>
                  python main.py --node-id {selectedNodeDetails?.node_id ?? selectedNodeId} --disp {selectedNodeDetails?.displacement_mm ?? 42.5} --tilt {selectedNodeDetails?.tilt_deg ?? 4.2} --vib {selectedNodeDetails?.vibration_rms ?? 9.85} --temp 25.0 --vel {selectedNodeDetails?.velocity_mm_h ?? 0.85}
                </code>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
