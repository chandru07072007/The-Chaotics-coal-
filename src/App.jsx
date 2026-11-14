import React, { useState, useEffect } from 'react';
import Dashboard from './Dashboard.jsx';
import './index.css';

const SOLUTION_STEPS = [
  {
    id: 1,
    stepTag: "STEP 01 OF 04",
    title: "Smart Surface & Subsurface Sensing Grid",
    thumb: "/image/sensor datails.webp",
    video: null,
    description: "Dense wireless array of MEMS 3-axis vibration sensors (MPU6050), high-precision geotechnical tilt transducers, displacement strain gauges, and capacitive pore-water soil pressure probes capturing microscopic rock strata shifts."
  },
  {
    id: 2,
    stepTag: "STEP 02 OF 04",
    title: "Self-Healing LoRa Mesh Telemetry",
    thumb: "/image/comucation.webp",
    video: "/video/unifited sloution/self healing.mp4",
    description: "Decentralized, fault-tolerant sub-GHz LoRa/Zigbee mesh routing network capable of dynamic multi-hop packet rerouting around severe rock mass fracturing, strata absorption, and open-cast highwall collapse."
  },
  {
    id: 3,
    stepTag: "STEP 03 OF 04",
    title: "Predictive 3D Digital Twin Simulation",
    thumb: "/image/digital-twin-main.webp",
    video: "/video/unifited sloution/digit twin.mp4",
    description: "High-fidelity WebGL 3D digital twin rendering real-time borehole arrays, tunnel alignment convergence, and dynamic upper-layer surface deformation heatmaps with Gaussian fault-line spatial interpolation."
  },
  {
    id: 4,
    stepTag: "STEP 04 OF 04",
    title: "Coal Mining Geological Section & Alerts",
    thumb: "/image/ALERT.png",
    video: "/video/unifited sloution/model.mp4",
    description: "Stratigraphic 3D geotechnical section mapping coal seam extraction, overburden stresses, and automated DGMS statutory threshold alerts with real-time Time-To-Critical (TTC) forecasting."
  }
];

export default function App() {
  const [user, setUser] = useState(null);
  const [activeModalStep, setActiveModalStep] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Keyboard navigation for modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        if (showLoginModal) setShowLoginModal(false);
        if (activeModalStep !== null) setActiveModalStep(null);
        return;
      }
      if (activeModalStep !== null) {
        if (e.key === "ArrowRight") {
          setActiveModalStep((prev) => (prev + 1) % SOLUTION_STEPS.length);
        } else if (e.key === "ArrowLeft") {
          setActiveModalStep((prev) => (prev - 1 + SOLUTION_STEPS.length) % SOLUTION_STEPS.length);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeModalStep, showLoginModal]);

  const handleLoginSubmit = (e) => {
    e.preventDefault();
    setUser({ email: loginEmail || 'operator@chaotics.mine' });
    setShowLoginModal(false);
  };

  const handleLogout = () => {
    setUser(null);
  };

  // If user is authenticated, render the full Dashboard Command Center
  if (user) {
    return <Dashboard user={user} onLogout={handleLogout} />;
  }

  const currentStep = activeModalStep !== null ? SOLUTION_STEPS[activeModalStep] : null;

  return (
    <div className="app">

      {/* Top Navigation Bar with Luxury Login Button */}
      <header className="top-nav">
        <a href="#welcome" className="nav-brand">THE CHAOTICS</a>
        <button
          className="login-btn"
          onClick={() => setShowLoginModal(true)}
          id="login-button"
        >
          OPERATOR LOGIN
        </button>
      </header>

      {/* Section 1: Hero / Welcome Screen */}
      <section id="welcome" className="section hero-section">
        <h2 className="hero-subtitle">Welcome To</h2>
        <h1 className="hero-title">THE CHAOTICS</h1>
        <div className="hero-badge">
          Intelligent IoT & AI Coal Mine Subsidence Platform
        </div>
      </section>

      {/* Section 2: Problem Statement */}
      <section id="problem-statement" className="section" style={{ background: '#f5f5f5' }}>
        <h2 className="section-title">PROBLEM STATEMENT</h2>
        <p className="section-subtitle">Catastrophic Ground Subsidence in Unmonitored Coal Seams</p>
        <div className="frame-box-16-9">
          <video
            src="/video/problem/When Abandoned Mines Collapse(720P_HD).mp4"
            autoPlay
            loop
            muted
            controls
            playsInline
            preload="auto"
            poster="/image/sensor datails.webp"
          >
            Your browser does not support HTML5 video.
          </video>
        </div>
      </section>

      {/* Section 3: Our Solution – 4-Box Descending Diagonal Staircase */}
      <section id="our-solution" className="section" style={{ background: '#ffffff', minHeight: '115vh' }}>
        <h2 className="section-title">OUR SOLUTION</h2>
        <p className="section-subtitle">YOU ARE SEE SAME SOLUTION MANY PPT</p>

        <div className="staircase-grid">
          {SOLUTION_STEPS.map((step, idx) => (
            <div key={step.id} className={`card-wrapper-${idx + 1}`}>
              <div className="staircase-card" onClick={() => setActiveModalStep(idx)}>
                <div className="card-image-wrap">
                  <img src={step.thumb} alt={step.title} loading="lazy" />
                </div>
                <div className="card-content">
                  <div className="card-step-badge">STEP 0{step.id}</div>
                  <div className="card-title">{step.title}</div>
                  <div className="card-view-badge">Click to view</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Section 4: Unified Solution – Alternating Zig-Zag Grid */}
      <section id="unified-solution" className="section" style={{ background: '#f7f5f4', minHeight: 'auto', paddingBottom: '7rem' }}>
        <h2 className="section-title">UNIFIED SOLUTION</h2>
        <p className="section-subtitle">Deep Hardware & Geotechnical AI Integration</p>

        <div className="zigzag-container">
          {/* Row 1: Left Media, Right Text */}
          <div className="zigzag-row">
            <div className="zigzag-media">
              <img src="/image/sensor datails.webp" alt="Smart Surface Sensing Grid" loading="lazy" />
            </div>
            <div className="zigzag-info">
              <div className="zigzag-tag">GEOTECHNICAL TRANSDUCERS</div>
              <h3 className="zigzag-title">SMART SURFACE SENSING GRID</h3>
              <p className="zigzag-desc">
                Comprehensive multi-modal array deploying MEMS 3-axis inclinometers, micro-strain crack gauges, capacitive moisture sensors, and piezoelectric ground vibration probes engineered for real-time edge telemetry.
              </p>
            </div>
          </div>

          {/* Row 2: Right Media, Left Text */}
          <div className="zigzag-row reverse">
            <div className="zigzag-media">
              <video
                src="/video/unifited sloution/self healing.mp4"
                autoPlay
                loop
                muted
                playsInline
              />
            </div>
            <div className="zigzag-info">
              <div className="zigzag-tag">WIRELESS TELEMETRY</div>
              <h3 className="zigzag-title">SELF-HEALING LORA MESH</h3>
              <p className="zigzag-desc">
                Autonomous multi-hop mesh routing across an N×N surface benchmark grid. Dynamic packet rerouting prevents data blackouts even during severe strata rupture, bench collapse, or excavator line-of-sight obstruction.
              </p>
            </div>
          </div>

          {/* Row 3: Left Media, Right Text */}
          <div className="zigzag-row">
            <div className="zigzag-media">
              <video
                src="/video/unifited sloution/digit twin.mp4"
                autoPlay
                loop
                muted
                playsInline
              />
            </div>
            <div className="zigzag-info">
              <div className="zigzag-tag">REAL-TIME TWIN SYNCHRONIZATION</div>
              <h3 className="zigzag-title">PREDICTIVE 3D DIGITAL TWIN</h3>
              <p className="zigzag-desc">
                Synchronized Three.js WebGL simulation featuring dynamic vertex color displacement, spatial fault-line Gaussian decay shading, and structural safety index calculations across 100 tunnel sections.
              </p>
            </div>
          </div>

          {/* Row 4: Right Media, Left Text */}
          <div className="zigzag-row reverse">
            <div className="zigzag-media">
              <video
                src="/video/unifited sloution/model.mp4"
                autoPlay
                loop
                muted
                playsInline
              />
            </div>
            <div className="zigzag-info">
              <div className="zigzag-tag">DGMS SAFETY ENGINE</div>
              <h3 className="zigzag-title">COAL MINING GEOLOGICAL MODEL</h3>
              <p className="zigzag-desc">
                Stratigraphic geotechnical mapping correlating coal seam extraction voids with surface subsidence rates, calculating statutory risk tiers (Safe, Advisory, Warning, Critical) and Time-To-Critical (TTC) windows.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 5: YouTube Video Showcase */}
      <section id="youtube-video" className="section" style={{ background: '#f5f5f5' }}>
        <h2 className="section-title">YOU TUBE VIDEO</h2>
        <p className="section-subtitle">Coal Mine Subsidence Mechanism & Geotechnical Analysis</p>
        <div className="frame-box-16-9">
          <iframe
            src="https://www.youtube.com/embed/R2IBYPBCXAk?rel=0&modestbranding=1"
            title="YouTube Video"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        </div>
      </section>

      {/* Section 6: Live System Demo */}
      <section id="demo" className="section" style={{ background: '#ffffff' }}>
        <h2 className="section-title">DEMO</h2>
        <p className="section-subtitle">MUNKANIPPU Hardware & AI Subterranean Platform in Action</p>
        <div className="frame-box-16-9">
          <iframe
            src="https://www.youtube.com/embed/vGwQXER6Wq8?rel=0&modestbranding=1"
            title="Coal Mine Monitoring System Demo"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        </div>
      </section>

      {/* Split Two-Pane Modal for Solution Steps */}
      {currentStep && (
        <div className="modal-backdrop" onClick={() => setActiveModalStep(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <button
              className="modal-close-btn"
              onClick={() => setActiveModalStep(null)}
              title="Close (Esc)"
            >
              X
            </button>

            <button
              className="modal-nav-btn modal-prev-btn"
              onClick={() => setActiveModalStep((prev) => (prev - 1 + SOLUTION_STEPS.length) % SOLUTION_STEPS.length)}
              title="Previous (Left Arrow)"
            >
              ‹
            </button>

            <button
              className="modal-nav-btn modal-next-btn"
              onClick={() => setActiveModalStep((prev) => (prev + 1) % SOLUTION_STEPS.length)}
              title="Next (Right Arrow)"
            >
              ›
            </button>

            {/* Left Column: Media Player */}
            <div className="modal-media-col">
              {currentStep.video ? (
                <video
                  src={currentStep.video}
                  autoPlay
                  loop
                  muted
                  playsInline
                  controls
                />
              ) : (
                <img src={currentStep.thumb} alt={currentStep.title} />
              )}
            </div>

            {/* Right Column: Technical Details */}
            <div className="modal-info-col">
              <div className="modal-step-tag">{currentStep.stepTag}</div>
              <h3 className="modal-step-title">{currentStep.title}</h3>
              <p className="modal-step-desc">{currentStep.description}</p>
              <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid #000000', fontSize: '0.85rem', color: '#666666' }}>
                Tip: Use Left/Right arrow keys to cycle through steps, or ESC to dismiss.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Login Modal */}
      {showLoginModal && (
        <div className="modal-backdrop" onClick={() => setShowLoginModal(false)}>
          <div className="login-modal-card" onClick={(e) => e.stopPropagation()}>
            <button
              className="modal-close-btn"
              onClick={() => setShowLoginModal(false)}
              title="Close (Esc)"
            >
              X
            </button>
            <div className="login-modal-header">
              <h2 className="login-modal-title">OPERATOR PORTAL</h2>
              <p className="login-modal-subtitle">Subterranean Telemetry & AI Access</p>
            </div>
            <form className="login-form" onSubmit={handleLoginSubmit}>
              <div className="form-group">
                <label>Mining Engineer ID / Email</label>
                <input
                  type="text"
                  placeholder="operator@chaotics.mine"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Security Clearance Key</label>
                <input
                  type="password"
                  placeholder="••••••••••••"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className="login-submit-btn">
                AUTHENTICATE & ENTER
              </button>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
