/* Render local LaTeX and the embedded Module 3 Plotly figures. */
(() => {
  const section = document.getElementById('bond');
  if (!section) return;

  renderMathInElement(section, {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '$', right: '$', display: false },
    ],
    throwOnError: false,
    strict: 'warn',
    trust: false,
  });

  const chartHeights = {
    nelson_siegel_curve: [570, 540],
    stress_test_errors: [530, 740],
    rate_sensitivity_regressions: [490, 990],
    late_2024_rate_stage: [620, 660],
  };
  const shortNames = new Map([
    ['上证国债指数', '上证国债'],
    ['上证企债指数', '上证企债'],
    ['政金债券ETF（政金债7—10年指数代理）', '政金债 ETF'],
  ]);

  function createLayout(specification, host, name) {
    const layout = structuredClone(specification.layout);
    const isNarrow = host.clientWidth < 640;
    layout.width = host.clientWidth;
    layout.height = chartHeights[name][Number(isNarrow)];
    layout.title = { text: '' };
    layout.autosize = false;
    layout.uirevision = name;
    layout.font = {
      family: '-apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif',
      size: isNarrow ? 11 : 14,
      color: '#1b3041',
    };
    layout.margin = { l: isNarrow ? 62 : 80, r: 28, t: 72, b: 65 };
    layout.legend = {
      ...layout.legend,
      orientation: 'h',
      x: 0,
      y: 1.13,
      font: { size: isNarrow ? 10 : 13 },
    };
    for (const [key, axis] of Object.entries(layout)) {
      if (!/^[xy]axis\d*$/.test(key)) continue;
      axis.automargin = true;
      if (axis.title) axis.title.font = { size: isNarrow ? 11 : 14 };
      axis.nticks = isNarrow ? 5 : 8;
    }
    if (layout.annotations) {
      layout.annotations.forEach(annotation => {
        annotation.font = { ...annotation.font, size: isNarrow ? 12 : 15 };
        annotation.text = shortNames.get(annotation.text) || annotation.text;
      });
    }
    if (name === 'rate_sensitivity_regressions' && isNarrow) {
      const domains = [[0.74, 0.98], [0.39, 0.63], [0.04, 0.28]];
      for (let index = 0; index < 3; index++) {
        const suffix = index === 0 ? '' : index + 1;
        layout[`xaxis${suffix}`].domain = [0, 1];
        layout[`yaxis${suffix}`].domain = domains[index];
        const annotation = layout.annotations[index];
        annotation.x = 0.5;
        annotation.y = domains[index][1] + 0.025;
      }
      layout.margin.t = 32;
      layout.margin.b = 70;
    }
    if (name === 'stress_test_errors') {
      layout.margin.l = isNarrow ? 94 : 115;
      layout.margin.r = 68;
      if (isNarrow) {
        layout.xaxis.domain = [0, 1];
        layout.xaxis2.domain = [0, 1];
        layout.yaxis.domain = [0.57, 1];
        layout.yaxis2.domain = [0, 0.43];
        layout.annotations[0].x = 0.5;
        layout.annotations[0].y = 1.04;
        layout.annotations[1].x = 0.5;
        layout.annotations[1].y = 0.47;
      }
      layout.coloraxis.colorbar = {
        ...layout.coloraxis.colorbar,
        thickness: 12,
        len: 0.9,
        tickfont: { size: isNarrow ? 10 : 12 },
      };
    }
    return layout;
  }

  async function initializeChart(host) {
    const name = host.dataset.fixedIncomeChart;
    const specification = window.fixedIncomeFigures[name];
    const data = structuredClone(specification.data);
    data.forEach(trace => {
      // These samples are small enough for SVG, which also works without WebGL.
      if (trace.type === 'scattergl') trace.type = 'scatter';
      trace.name = shortNames.get(trace.name) || trace.name;
      if (name === 'nelson_siegel_curve' && trace.type === 'bar') trace.showlegend = false;
      if (name === 'stress_test_errors') trace.textfont = { size: 11 };
    });
    const config = {
      ...specification.config,
      responsive: true,
      displaylogo: false,
      scrollZoom: false,
    };
    const layout = createLayout(specification, host, name);
    host.style.height = `${layout.height}px`;
    await Plotly.newPlot(host, data, layout, config);
    host.dataset.chartReady = 'true';

    let previousWidth = host.clientWidth;
    let resizeFrame;
    const observer = new ResizeObserver(() => {
      if (host.clientWidth === previousWidth) return;
      previousWidth = host.clientWidth;
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        const resizedLayout = createLayout(specification, host, name);
        host.style.height = `${resizedLayout.height}px`;
        Plotly.react(host, data, resizedLayout, config);
      });
    });
    observer.observe(host);
  }

  window.fixedIncomeReportReady = Promise.all(
    [...section.querySelectorAll('[data-fixed-income-chart]')].map(initializeChart),
  );
})();
