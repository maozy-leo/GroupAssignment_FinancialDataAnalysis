/* Native Plotly charts: data are loaded by a local classic script for file:// support. */
(() => {
  const source = window.allocationRobustnessData;
  if (!source || !window.Plotly) return;

  const parameterChart = document.getElementById('parameter-sensitivity-chart');
  const assetChart = document.getElementById('asset-substitution-chart');
  const parameterSelect = document.getElementById('parameter-group');
  const cohortSelect = document.getElementById('asset-cohort');
  const metricSelect = document.getElementById('asset-metric');
  if (!parameterChart || !assetChart) return;

  const config = { responsive: false, displaylogo: false, scrollZoom: false };
  const font = { family: '-apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif', size: 13, color: '#1b3041' };
  for (const name of Object.keys(source.parameters)) {
    parameterSelect.add(new Option(name, name));
  }
  parameterSelect.value = '最小方差股票下限';

  function isChartVisible(chart) {
    return !chart.closest('details:not([open])') && chart.clientWidth > 0;
  }

  function drawParameters() {
    if (!isChartVisible(parameterChart)) return Promise.resolve();
    const group = source.parameters[parameterSelect.value];
    const measures = [
      { key: '年化收益率', color: '#398e88', axis: 'y', format: '.2%' },
      { key: '夏普比率', color: '#3d6d9c', axis: 'y2', format: '.3f' },
      { key: '最大回撤', color: '#c58446', axis: 'y3', format: '.2%' },
    ];
    const traces = measures.map((measure) => ({
      type: 'scatter', mode: 'lines+markers', name: measure.key,
      x: group.label, y: group[measure.key], yaxis: measure.axis,
      line: { color: measure.color, width: 3 }, marker: { size: 9 },
      hovertemplate: `%{x}<br>${measure.key}：%{y:${measure.format}}<extra></extra>`,
    }));
    const axis = { gridcolor: '#e8eef1', zeroline: false, automargin: true };
    return Plotly.react(parameterChart, traces, {
      width: parameterChart.clientWidth, height: 630, autosize: false, font, showlegend: false,
      margin: { l: 70, r: 20, t: 45, b: 70 },
      title: { text: parameterSelect.value, font: { size: 16 } },
      xaxis: {
        ...axis, type: 'category', anchor: 'free', position: 0,
        title: { text: '试验参数（其他参数固定）' },
      },
      yaxis: { ...axis, domain: [0.72, 1], title: { text: '年化收益' }, tickformat: '.1%' },
      yaxis2: { ...axis, domain: [0.37, 0.65], title: { text: 'Sharpe' }, tickformat: '.2f' },
      yaxis3: { ...axis, domain: [0, 0.28], title: { text: '最大回撤' }, tickformat: '.1%' },
      paper_bgcolor: '#fff', plot_bgcolor: '#fff',
    }, config);
  }

  function drawAssets() {
    if (!isChartVisible(assetChart)) return Promise.resolve();
    const cohort = cohortSelect.value;
    const metric = metricSelect.value;
    const rows = source.assets.filter((row) => row.cohort === cohort);
    const pairs = [...new Set(rows.map((row) => row.pair))];
    const strategies = Object.keys(source.strategyNames);
    const matrix = pairs.map((pair) => strategies.map((strategy) =>
      rows.find((row) => row.pair === pair && row.strategy === strategy)));
    const isSharpe = metric === '夏普比率';
    const z = matrix.map((row) => row.map((result) => result[metric] * (isSharpe ? 1 : 100)));
    const custom = matrix.map((row) => row.map((result) => [
      (100 * result['年化收益率']).toFixed(2), result['夏普比率'].toFixed(3),
      (100 * result['最大回撤']).toFixed(2), result.start_date, result.end_date,
    ]));
    const compact = assetChart.clientWidth < 650;
    return Plotly.react(assetChart, [{
      type: 'heatmap', x: strategies.map((key) => source.strategyNames[key]),
      y: pairs, z, customdata: custom,
      colorscale: [[0, '#edf5f3'], [0.5, '#7dc3b6'], [1, '#176b67']],
      autocolorscale: false, reversescale: metric === '最大回撤',
      colorbar: { title: { text: isSharpe ? 'Sharpe' : '%' }, thickness: 12 },
      hovertemplate: '%{y}<br>%{x}<br>年化收益：%{customdata[0]}%<br>Sharpe：%{customdata[1]}'
        + '<br>最大回撤：%{customdata[2]}%<br>%{customdata[3]}—%{customdata[4]}<extra></extra>',
    }], {
      width: assetChart.clientWidth,
      height: cohort === '短样本' ? 700 : 480, autosize: false, font,
      margin: { l: compact ? 120 : 175, r: 45, t: 55, b: compact ? 95 : 60 },
      title: { text: `${cohort} · ${metric}${metric === '最大回撤' ? '（越小越好）' : ''}`, font: { size: 16 } },
      xaxis: { tickangle: compact ? -55 : 0, automargin: true },
      yaxis: { autorange: 'reversed', automargin: true, tickfont: { size: compact ? 10 : 12 } },
      paper_bgcolor: '#fff', plot_bgcolor: '#fff',
    }, config);
  }

  parameterSelect.addEventListener('change', drawParameters);
  cohortSelect.addEventListener('change', drawAssets);
  metricSelect.addEventListener('change', drawAssets);
  for (const panel of new Set([parameterChart.closest('details'), assetChart.closest('details')])) {
    if (!panel) continue;
    panel.addEventListener('toggle', () => {
      if (!panel.open) return;
      requestAnimationFrame(() => {
        if (panel.contains(parameterChart)) drawParameters();
        if (panel.contains(assetChart)) drawAssets();
      });
    });
  }
  const previousWidths = new WeakMap();
  const observer = new ResizeObserver((entries) => {
    for (const { target } of entries) {
      const width = target.clientWidth;
      const previousWidth = previousWidths.get(target) ?? 0;
      previousWidths.set(target, width);
      if (!isChartVisible(target) || Math.abs(width - previousWidth) < 2) continue;
      if (target === parameterChart) drawParameters();
      else drawAssets();
    }
  });
  observer.observe(parameterChart);
  observer.observe(assetChart);
  window.allocationRobustnessReady = Promise.all([drawParameters(), drawAssets()]);
})();
