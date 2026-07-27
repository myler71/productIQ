/* ProductIQ — Chart.js helpers (teal/navy palette) */
const Charts = {
  palette: {
    teal: '#00A6A6',
    navy: '#0B1F3A',
    gold: '#D4A537',
    tealSoft: 'rgba(0,166,166,0.15)',
    goldSoft: 'rgba(212,165,55,0.15)',
    series: ['#00A6A6', '#0B1F3A', '#D4A537', '#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EF4444']
  },

  defaults() {
    if (!window.Chart) return;
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = '#64748B';
    Chart.defaults.borderColor = '#E2E8F0';
    Chart.defaults.plugins.legend.rtl = document.body.getAttribute('dir') === 'rtl';
  },

  bar(canvasId, labels, values, opts = {}) {
    this.defaults();
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: this.palette.series.slice(0, labels.length),
          borderRadius: 6,
          maxBarThickness: 42
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: opts.horizontal ? 'y' : 'x',
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: '#F1F5F9' } },
          x: { grid: { display: false } }
        }
      }
    });
  },

  line(canvasId, labels, values, opts = {}) {
    this.defaults();
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: this.palette.teal,
          backgroundColor: this.palette.tealSoft,
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointBackgroundColor: this.palette.teal
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: false, grid: { color: '#F1F5F9' } },
          x: { grid: { display: false } }
        }
      }
    });
  },

  doughnut(canvasId, labels, values) {
    this.defaults();
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: this.palette.series.slice(0, labels.length),
          borderWidth: 2,
          borderColor: '#fff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '62%',
        plugins: { legend: { position: 'bottom' } }
      }
    });
  },

  radar(canvasId, labels, datasetsCfg) {
    this.defaults();
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const datasets = datasetsCfg.map((d, i) => ({
      label: d.label,
      data: d.data,
      borderColor: i === 0 ? this.palette.teal : this.palette.gold,
      backgroundColor: i === 0 ? this.palette.tealSoft : this.palette.goldSoft,
      pointBackgroundColor: i === 0 ? this.palette.teal : this.palette.gold,
      borderWidth: 2
    }));
    return new Chart(ctx, {
      type: 'radar',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            min: 0, max: 100,
            ticks: { stepSize: 25, display: false },
            grid: { color: '#E2E8F0' },
            angleLines: { color: '#E2E8F0' },
            pointLabels: { font: { size: 11 } }
          }
        },
        plugins: { legend: { position: 'bottom' } }
      }
    });
  }
};
