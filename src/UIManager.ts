import Chart from 'chart.js/auto';
import type { SegmentAnalysis } from './DataModel';
import { Calculations } from './Calculations';

export class UIManager {
  private statusBadge = document.getElementById('val-status')!;
  private maxStress = document.getElementById('val-max-stress')!;
  private maxDef = document.getElementById('val-max-def')!;
  private maxWp = document.getElementById('val-max-wp')!;
  private minSf = document.getElementById('val-min-sf')!;
  private riskSegment = document.getElementById('val-risk-segment')!;
  private riskScore = document.getElementById('val-risk-score')!;
  private predictedFailure = document.getElementById('val-predicted-failure')!;
  private geoLayer = document.getElementById('val-geo-layer')!;
  
  private surfX = document.getElementById('val-surf-x')!;
  private surfY = document.getElementById('val-surf-y')!;
  private surfZ = document.getElementById('val-surf-z')!;

  private selPanel = document.getElementById('selected-segment-panel')!;
  private selId = document.getElementById('sel-id')!;
  private selStress = document.getElementById('sel-stress')!;
  private selDef = document.getElementById('sel-def')!;
  private selWp = document.getElementById('sel-wp')!;

  private stressChart: Chart;
  private defChart: Chart;
  private riskChart: Chart;

  constructor() {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.scale.grid.color = 'rgba(255,255,255,0.1)';

    this.stressChart = new Chart(document.getElementById('chart-stress') as HTMLCanvasElement, {
      type: 'line',
      data: { labels: [], datasets: [{ label: 'Stress (kPa)', data: [], borderColor: '#3b82f6', tension: 0.3 }] },
      options: { responsive: true, maintainAspectRatio: false }
    });

    this.defChart = new Chart(document.getElementById('chart-def') as HTMLCanvasElement, {
      type: 'line',
      data: { labels: [], datasets: [{ label: 'Deformation (mm)', data: [], borderColor: '#f59e0b', tension: 0.3 }] },
      options: { responsive: true, maintainAspectRatio: false }
    });

    this.riskChart = new Chart(document.getElementById('chart-risk') as HTMLCanvasElement, {
      type: 'bar',
      data: { labels: [], datasets: [{ label: 'Risk Score (%)', data: [], backgroundColor: '#ef4444' }] },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  public updateDashboard(analysis: SegmentAnalysis[], maxRiskSegment: SegmentAnalysis) {
    let mStress = 0, mDef = 0, mWp = 0, mSf = 999;
    
    analysis.forEach(a => {
      if (a.sensor.stress > mStress) mStress = a.sensor.stress;
      if (a.sensor.deformation > mDef) mDef = a.sensor.deformation;
      if (a.sensor.waterPressure > mWp) mWp = a.sensor.waterPressure;
      if (a.safetyFactor < mSf) mSf = a.safetyFactor;
    });

    this.maxStress.textContent = `${mStress.toFixed(0)} kPa`;
    this.maxDef.textContent = `${mDef.toFixed(1)} mm`;
    this.maxWp.textContent = `${mWp.toFixed(0)} kPa`;
    this.minSf.textContent = mSf.toFixed(2);

    this.statusBadge.textContent = maxRiskSegment.status;
    if (maxRiskSegment.status === 'SAFE') this.statusBadge.style.backgroundColor = 'var(--safe)';
    else if (maxRiskSegment.status === 'NORMAL') this.statusBadge.style.backgroundColor = 'var(--normal)';
    else if (maxRiskSegment.status === 'WARNING') this.statusBadge.style.backgroundColor = 'var(--warning)';
    else this.statusBadge.style.backgroundColor = 'var(--critical)';

    this.riskSegment.textContent = maxRiskSegment.id;
    this.riskScore.textContent = `${maxRiskSegment.riskScore.toFixed(1)}%`;
    this.predictedFailure.textContent = `X=${maxRiskSegment.centerX.toFixed(1)}, Y=0, Z=${maxRiskSegment.centerZ.toFixed(1)}`;
    this.geoLayer.textContent = maxRiskSegment.geoLayer.name;

    const surfaceElevation = Calculations.getTerrainHeight(maxRiskSegment.centerX, 0);
    this.surfX.textContent = `${maxRiskSegment.centerX.toFixed(1)} m`;
    this.surfY.textContent = `${surfaceElevation.toFixed(1)} m (Elevation)`;
    this.surfZ.textContent = `${(surfaceElevation - maxRiskSegment.centerZ).toFixed(1)} m (Total Depth)`;

    // Charts
    const labels = analysis.map(a => a.id.replace('T-', ''));
    this.stressChart.data.labels = labels;
    this.stressChart.data.datasets[0].data = analysis.map(a => a.sensor.stress);
    this.stressChart.update();

    this.defChart.data.labels = labels;
    this.defChart.data.datasets[0].data = analysis.map(a => a.sensor.deformation);
    this.defChart.update();

    this.riskChart.data.labels = labels;
    this.riskChart.data.datasets[0].data = analysis.map(a => a.riskScore);
    // update colors
    this.riskChart.data.datasets[0].backgroundColor = analysis.map(a => {
        if(a.riskScore < 40) return '#10b981';
        if(a.riskScore < 60) return '#3b82f6';
        if(a.riskScore < 80) return '#f59e0b';
        return '#ef4444';
    });
    this.riskChart.update();
  }

  public showSelectedSegment(a: SegmentAnalysis | null) {
    if (!a) {
      this.selPanel.style.display = 'none';
      return;
    }
    this.selPanel.style.display = 'block';
    this.selId.textContent = a.id;
    this.selStress.textContent = `${a.sensor.stress.toFixed(0)} kPa`;
    this.selDef.textContent = `${a.sensor.deformation.toFixed(1)} mm`;
    this.selWp.textContent = `${a.sensor.waterPressure.toFixed(0)} kPa`;
  }
}
