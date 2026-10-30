"""Build the self-contained HTML report for fixed-income analysis."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from config import AnalysisResults, BOND_ASSETS, HAC_MAX_LAGS, SCENARIOS


def write_html_report(
    figures: dict[str, go.Figure],
    results: AnalysisResults,
    output_path: Path,
) -> None:
    """Write methods, results, analysis, and figures to one offline HTML file.

    Args:
        figures: Ordered mapping of report figure identifiers to Plotly figures.
        results: Complete Module 3 calculation results.
        output_path: Destination path for the self-contained HTML report.

    Raises:
        KeyError: If a required report figure is missing.
    """
    required_figures = {
        "module3_nelson_siegel_curve",
        "module3_stress_test_errors",
        "module3_rate_sensitivity_regressions",
        "module3_late_2024_rate_stage",
        "module3_realized_2024_convexity",
        "module3_rolling_rate_duration",
    }
    missing_figures = required_figures.difference(figures)
    if missing_figures:
        raise KeyError(
            "Expected all report figures, but missing: "
            f"{sorted(missing_figures)}."
        )

    figure_fragments = _build_figure_fragments(figures)
    document = _build_document(results, figure_fragments)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def _build_figure_fragments(
    figures: dict[str, go.Figure],
) -> dict[str, str]:
    """Convert figures to responsive fragments with one embedded Plotly bundle."""
    fragments: dict[str, str] = {}
    for figure_index, (figure_id, figure) in enumerate(figures.items()):
        fragments[figure_id] = pio.to_html(
            figure,
            full_html=False,
            include_plotlyjs=figure_index == 0,
            config={
                "responsive": True,
                "displaylogo": False,
                "scrollZoom": True,
            },
        )
    return fragments


def _build_document(
    results: AnalysisResults,
    figures: dict[str, str],
) -> str:
    """Assemble the complete HTML document from calculated results."""
    beta_0, beta_1, beta_2, tau = results.curve_fit.parameters
    curve_date = pd.Timestamp(
        results.curve["curve_date"].iloc[0]
    ).date().isoformat()
    rmse_bp = (
        np.sqrt(results.curve_fit.objective / len(results.curve)) * 10_000.0
    )
    max_residual = results.curve_results.iloc[
        results.curve_results["residual_bp"].abs().argmax()
    ]
    stress = results.stress_results
    worst_duration = stress.iloc[stress["duration_error_bp"].argmax()]
    worst_convexity = stress.iloc[
        stress["duration_convexity_error_bp"].argmax()
    ]
    average_error_reduction = 1.0 - (
        stress["duration_convexity_absolute_error"].mean()
        / stress["duration_absolute_error"].mean()
    )
    regressions = results.regression_results
    treasury_regression = regressions.loc[
        regressions["asset_id"] == "SSE_TREASURY"
    ].iloc[0]
    enterprise_regression = regressions.loc[
        regressions["asset_id"] == "SSE_ENTERPRISE_BOND"
    ].iloc[0]
    policy_regression = regressions.loc[
        regressions["asset_id"] == "POLICY_BOND_7_10_PROXY"
    ].iloc[0]
    late_period = results.late_period
    start_yield = float(late_period["yield_10y_decimal"].iloc[0])
    end_yield = float(late_period["yield_10y_decimal"].iloc[-1])
    yield_change_bp = (end_yield - start_yield) * 10_000.0
    attribution = results.realized_convexity.iloc[0]
    duration_error_bp = attribution["duration_absolute_error"] * 10_000.0
    convexity_error_bp = (
        attribution["duration_convexity_absolute_error"] * 10_000.0
    )
    regression_start = pd.Timestamp(regressions["sample_start"].min())
    regression_end = pd.Timestamp(regressions["sample_end"].max())

    parameter_table = _parameter_table(
        beta_0,
        beta_1,
        beta_2,
        tau,
        rmse_bp,
    )
    source_table = _source_table(results)
    bond_asset_table = _bond_asset_table(results)
    yield_tenor_table = _yield_tenor_table(results)
    curve_source_table = _curve_source_table(results.curve)
    residual_table = _residual_table(results.curve_results)
    start_diagnostics_table = _start_diagnostics_table(
        results.curve_fit.diagnostics
    )
    duration_table = _duration_table(results.duration_convexity)
    scenario_shock_table = _scenario_shock_table(stress)
    stress_table = _stress_table(stress)
    regression_table = _regression_table(regressions)
    late_return_table = _late_return_table(late_period)
    attribution_table = _attribution_table(attribution)
    rolling_table = _rolling_table(results)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Assignment 1 模块3：固定收益分析报告</title>
  <style>{_report_css()}</style>
</head>
<body>
  <header class="hero">
    <div class="hero-inner">
      <p class="eyebrow">金融数据分析导论 · Assignment 1 · Module 3</p>
      <h1>固定收益分析报告</h1>
      <p class="hero-copy">
        本报告直接由 DuckDB 数据和分析代码生成，完整记录收益率曲线拟合、
        久期凸性、利率压力测试、债券指数利率敏感度及 2024 年末案例分析。
      </p>
      <div class="hero-metrics">
        <div><span>最新曲线日期</span><strong>{curve_date}</strong></div>
        <div><span>历史分析区间</span>
          <strong>{regression_start:%Y-%m-%d}—{regression_end:%Y-%m-%d}</strong>
        </div>
        <div><span>曲线期限点</span><strong>{len(results.curve)} 个</strong></div>
        <div><span>债券资产</span><strong>{len(BOND_ASSETS)} 类</strong></div>
      </div>
    </div>
  </header>

  <div class="page-shell">
    <aside class="toc">
      <div class="toc-title">报告目录</div>
      <a href="#scope">研究口径</a>
      <a href="#data">数据说明</a>
      <a href="#section-31">3.1 NS 曲线拟合</a>
      <a href="#section-32">3.2 久期和凸性</a>
      <a href="#section-33">3.3 利率压力测试</a>
      <a href="#section-34">3.4 利率敏感度</a>
      <a href="#section-35">3.5 2024 年末阶段</a>
      <a href="#section-36">3.6 实际凸性归因</a>
      <a href="#section-37">3.7 滚动隐含久期</a>
      <a href="#limitations">局限性</a>
      <a href="#appendix">可复现性附录</a>
    </aside>

    <main>
      <section id="scope" class="report-section">
        <div class="section-heading">
          <span>研究设计</span><h2>数据口径与执行流程</h2>
        </div>
        <div class="two-column">
          <div class="panel">
            <h3>统一口径</h3>
            <ul>
              <li>全部数据通过 SQL 从 <code>Assignment1/data/data.duckdb</code> 只读加载。</li>
              <li>收益率在计算中使用小数；图表按百分比或 bp 展示。</li>
              <li>零息债面值为 100，采用年复利；历史回归从 2019-01-01 开始。</li>
              <li>债券收益与国债收益率变动按共同交易日内连接。</li>
              <li>回归采用含截距 OLS，标准误使用 Newey–West HAC，最大滞后为 {HAC_MAX_LAGS}。</li>
            </ul>
          </div>
          <div class="panel">
            <h3>分析链路</h3>
            <ol>
              <li>拟合最新国债收益率曲线。</li>
              <li>由拟合收益率计算关键期限债券风险指标。</li>
              <li>在预设利率情景下比较精确重定价和近似方法。</li>
              <li>使用历史市场数据估计债券指数的实际利率敏感度。</li>
              <li>用 2024 年末利率下行阶段检验凸性修正价值。</li>
            </ol>
          </div>
        </div>
        <div class="note">
          图表为离线 Plotly 交互图，可悬停读取数据、框选缩放，并通过右上角工具栏导出。
        </div>
      </section>

      <section id="data" class="report-section">
        <div class="section-heading">
          <span>数据说明</span><h2>数据来源、字段与样本覆盖</h2>
        </div>
        <h3>1. 数据来源与落表关系</h3>
        <p>模块 3 不在分析阶段调用外部接口，而是读取模块 1 已清洗并通过质量检查的
          DuckDB 数据库。原始债券指数来自债券指数日线接口；政金债公开指数无法由现有
          接口返回，因此使用跟踪中债 7—10 年政策性金融债指数的 511520 ETF 前复权价格
          作为补充代理。历史国债收益率来自 <code>get_bond_rates</code>，最新曲线来自
          <code>get_china_yield_curve</code>。</p>
        <div class="lineage">
          <div><strong>外部数据接口</strong><span>指数、ETF、国债收益率</span></div>
          <b>→</b>
          <div><strong>模块 1 清洗</strong><span>类型、范围、去重、排序</span></div>
          <b>→</b>
          <div><strong>DuckDB</strong><span>统一的小数与日期口径</span></div>
          <b>→</b>
          <div><strong>模块 3</strong><span>SQL 只读查询与共同日对齐</span></div>
        </div>

        <h3>2. 输入表覆盖范围</h3>
        {source_table}
        <p class="caption">记录数和日期范围在每次生成报告时直接查询数据库，因此数据更新后会自动变化。</p>

        <h3>3. 与固定收益分析直接相关的字段</h3>
        <div class="schema-grid">
          <div class="panel">
            <h3><code>yield_curve_snapshot</code></h3>
            <dl>
              <dt>curve_date · DATE</dt><dd>曲线截面日期。</dd>
              <dt>tenor_years · DOUBLE</dt><dd>到期期限，单位为年。</dd>
              <dt>yield_decimal · DOUBLE</dt><dd>到期收益率，小数口径。</dd>
            </dl>
            <p>用于 3.1 的 NS 拟合，以及 3.2–3.3 的理论债券计算。</p>
          </div>
          <div class="panel">
            <h3><code>gov_yield_daily</code></h3>
            <dl>
              <dt>trade_date · DATE</dt><dd>收益率观测日期。</dd>
              <dt>tenor_years · DOUBLE</dt><dd>2、5、10、30 年期限。</dd>
              <dt>yield_decimal · DOUBLE</dt><dd>国债到期收益率，小数口径。</dd>
            </dl>
            <p>模块 3 使用其中 10 年期序列构造日变化和 2024 年末案例。</p>
          </div>
          <div class="panel">
            <h3><code>index_daily</code></h3>
            <dl>
              <dt>asset_id · VARCHAR</dt><dd>数据库内部资产标识。</dd>
              <dt>trade_date · DATE</dt><dd>交易日期。</dd>
              <dt>close · DOUBLE</dt><dd>指数收盘点位或 ETF 前复权收盘价。</dd>
            </dl>
            <p>用于债券指数日对数收益、累计收益和历史敏感度回归。</p>
          </div>
          <div class="panel">
            <h3><code>assets</code></h3>
            <dl>
              <dt>asset_id / asset_name</dt><dd>资产标识及展示名称。</dd>
              <dt>symbol / source</dt><dd>证券代码与原始数据接口。</dd>
              <dt>return_type / tenor_bucket</dt><dd>价格口径与适用期限段。</dd>
            </dl>
            <p>用于解释指数、ETF 代理和数据口径差异。</p>
          </div>
        </div>

        <h3>4. 三类债券资产</h3>
        {bond_asset_table}
        <div class="note">
          上证国债指数是主结果，上证企债指数用于展示信用债差异；政金债 ETF
          仅作为较短样本的长久期稳健性参照，不替代 2019 年起的主序列。
        </div>

        <h3>5. 收益率数据覆盖</h3>
        {yield_tenor_table}
        <p>历史表包含 2、5、10、30 年期限，但当前保留的分析只使用 10 年期历史收益率；
          最新截面则使用 0.25、0.5、1、3、5、7、10、30 年共 8 个期限点：</p>
        {curve_source_table}

        <h3>6. 清洗、单位与日期对齐</h3>
        <ul>
          <li>日期统一为 <code>DATE</code>，数值统一为 <code>DOUBLE</code>；事实表不存在空值和重复主键。</li>
          <li>收益率以小数保存，例如 2% 存为 0.02；1bp 等于 0.0001。</li>
          <li>指数和 ETF 保存点位或前复权价格，不进行跨日填充。</li>
          <li>日对数收益先在各资产完整序列上用 <code>LAG</code> 计算，再筛选分析起点，避免错误丢失首日收益。</li>
          <li>回归使用债券收益与 10 年期收益率变化的共同交易日；2024 年末案例要求三类资产与利率同时存在。</li>
        </ul>
        <div class="formula-grid">
          <div class="formula">
            债券日收益：r<sub>t</sub> = ln(P<sub>t</sub>/P<sub>t−1</sub>)
          </div>
          <div class="formula">
            利率日变化：Δy<sub>t</sub> = y<sub>t</sub> − y<sub>t−1</sub>
          </div>
          <div class="formula">
            区间累计收益：R<sub>t</sub> = P<sub>t</sub>/P<sub>0</sub> − 1
          </div>
        </div>
      </section>

      <section id="section-31" class="report-section">
        <div class="section-heading">
          <span>任务 3.1</span><h2>Nelson–Siegel 收益率曲线拟合</h2>
        </div>
        <h3>怎么做</h3>
        <p>读取 {curve_date} 的 8 个国债期限点，使用五组不同初值调用
          <code>scipy.optimize.minimize</code>，最小化实际收益率与模型收益率之间的残差平方和。
          所有初值均要求 τ &gt; 0，最终选择原始收益率口径 SSE 最小的收敛结果。</p>
        <div class="formula">
          y(T) = β₀ + β₁[(1 − e<sup>−T/τ</sup>)/(T/τ)]
          + β₂[(1 − e<sup>−T/τ</sup>)/(T/τ) − e<sup>−T/τ</sup>]
        </div>
        <div class="derivation">
          <h3>模型分解与估计目标</h3>
          <p>令 x=T/τ、L₁(x)=(1−e<sup>−x</sup>)/x、
            L₂(x)=L₁(x)−e<sup>−x</sup>，则 y(T)=β₀+β₁L₁+β₂L₂。
            当 T→0 时，L₁→1、L₂→0，所以短端极限约为 β₀+β₁；
            当 T→∞ 时两个载荷均趋近于 0，因此长期极限为 β₀。
            L₂ 在中间期限先升后降，对应曲率因子。</p>
          <div class="formula">
            SSE(θ) = Σ<sub>i=1</sub><sup>8</sup>
            [y<sub>i</sub> − y(T<sub>i</sub>;θ)]<sup>2</sup>，
            RMSE = √(SSE/8)
          </div>
          <p>代码将目标函数乘以常数后交给优化器，以改善极小数量级残差下的数值分辨率；
            报告中的 SSE、RMSE 和残差仍还原为原始小数收益率口径。</p>
        </div>
        <details>
          <summary>查看五组初值与收敛诊断</summary>
          {start_diagnostics_table}
        </details>
        <h3>结果</h3>
        {parameter_table}
        <p>8 个期限点的 RMSE 为 <strong>{rmse_bp:.3f} bp</strong>；最大绝对残差出现在
          <strong>{max_residual['tenor_years']:g} 年期</strong>，残差为
          <strong>{max_residual['residual_bp']:.3f} bp</strong>。</p>
        <div class="chart-card">{figures['module3_nelson_siegel_curve']}</div>
        <details><summary>查看各期限拟合残差</summary>{residual_table}</details>
        <div class="analysis-box">
          <h3>结果分析</h3>
          <p>β₀={beta_0:.6f} 表示长期利率水平；β₁={beta_1:.6f} 为负，说明短端低于长期水平；
            β₂={beta_2:.6f} 描述中端曲率；τ={tau:.4f} 控制曲率峰值位置和因子衰减速度。
            较低的拟合误差说明四参数模型能够紧凑概括当前曲线，但配置时仍应关注单一期限残差。</p>
          <p><strong>配置含义：</strong>期限拉长可能增加静态收益，同时也放大利率风险；不能只依据曲线水平决定久期。</p>
        </div>
      </section>

      <section id="section-32" class="report-section">
        <div class="section-heading"><span>任务 3.2</span><h2>关键期限久期和凸性</h2></div>
        <h3>怎么做</h3>
        <p>在 Nelson–Siegel 曲线上读取 1、3、5、10 年拟合收益率，并将每个期限构造成面值 100 的零息债。
          零息债的麦考利久期等于期限，修正久期和凸性按年复利口径计算。</p>
        <div class="formula-grid">
          <div class="formula">P(T) = 100/(1+y<sub>T</sub>)<sup>T</sup></div>
          <div class="formula">D<sub>mod</sub> = T/(1+y<sub>T</sub>)</div>
          <div class="formula">C = T(T+1)/(1+y<sub>T</sub>)<sup>2</sup></div>
        </div>
        <div class="derivation">
          <h3>从价格导数得到风险指标</h3>
          <p>零息债价格为 P(y)=100(1+y)<sup>−T</sup>。对收益率求一阶导数：</p>
          <div class="formula">
            ∂P/∂y = −100T(1+y)<sup>−T−1</sup>，
            −(1/P)(∂P/∂y) = T/(1+y) = D<sub>mod</sub>
          </div>
          <p>再求一次导数，可得单位价格凸性：</p>
          <div class="formula">
            (1/P)(∂²P/∂y²) = T(T+1)/(1+y)<sup>2</sup> = C
          </div>
          <p>因此修正久期是一阶相对价格敏感度，凸性是二阶曲率；二者均随期限上升而增加。</p>
        </div>
        <h3>结果</h3>
        {duration_table}
        <div class="analysis-box">
          <h3>结果分析</h3>
          <p>期限越长，修正久期和凸性越大。10 年零息债的修正久期为
            <strong>
              {results.duration_convexity.iloc[-1]['modified_duration_years']:.4f} 年
            </strong>，
            明显高于短期限债券，因此同样的收益率冲击会产生更大的价格变化。</p>
          <p><strong>配置含义：</strong>长久期债券在利率下行时具有更强资本利得潜力，但在利率上行时也承担更大的回撤。</p>
        </div>
      </section>

      <section id="section-33" class="report-section">
        <div class="section-heading"><span>任务 3.3</span><h2>利率压力测试</h2></div>
        <h3>怎么做</h3>
        <p>对四个期限分别施加平行 ±50bp、平行 ±100bp 和陡峭化冲击。陡峭化情景规定：
          1 年及以下不变，10 年及以上上移 50bp，1—10 年之间线性插值。
          每个情景同时计算精确重定价、仅久期近似和久期加凸性近似。</p>
        {scenario_shock_table}
        <div class="formula-grid">
          <div class="formula">精确：ΔP/P = P(y+Δy)/P(y) − 1</div>
          <div class="formula">久期：ΔP/P ≈ −D<sub>mod</sub>Δy</div>
          <div class="formula">
            久期+凸性：ΔP/P ≈ −D<sub>mod</sub>Δy + ½C(Δy)<sup>2</sup>
          </div>
        </div>
        <div class="derivation">
          <h3>近似公式的来源</h3>
          <p>将价格函数 P(y+Δy) 在当前收益率 y 附近作二阶 Taylor 展开：</p>
          <div class="formula">
            P(y+Δy) ≈ P(y) + P′(y)Δy + ½P″(y)(Δy)<sup>2</sup>
          </div>
          <p>两边除以 P(y)，并代入
            D<sub>mod</sub>=−P′/P、C=P″/P，即得到久期加凸性公式。
            仅久期方法相当于舍弃二阶项，所以收益率冲击越大、期限越长，线性化误差通常越明显。
            精确重定价则直接用冲击后的收益率计算新价格，不依赖局部近似。</p>
        </div>
        <h3>结果</h3>
        <div class="result-strip">
          <div><span>最大久期误差</span>
            <strong>{worst_duration['duration_error_bp']:.3f} bp</strong>
            <small>{worst_duration['scenario']} ·
              {worst_duration['tenor_years']:g} 年</small>
          </div>
          <div><span>最大凸性修正误差</span>
            <strong>{worst_convexity['duration_convexity_error_bp']:.3f} bp</strong>
            <small>{worst_convexity['scenario']} ·
              {worst_convexity['tenor_years']:g} 年</small>
          </div>
          <div><span>平均误差降幅</span>
            <strong>{average_error_reduction:.1%}</strong>
            <small>久期+凸性相对仅久期</small>
          </div>
        </div>
        <div class="chart-card">{figures['module3_stress_test_errors']}</div>
        <details><summary>查看全部期限与情景结果</summary>{stress_table}</details>
        <div class="analysis-box">
          <h3>结果分析</h3>
          <p>仅久期是价格—收益率曲线的一阶线性近似，误差会随期限和冲击幅度增大。
            凸性项捕捉二阶弯曲后，平均绝对误差下降 {average_error_reduction:.1%}。</p>
          <p><strong>配置含义：</strong>长久期组合或大幅利率情景至少应加入凸性；关键决策仍以精确重定价为准。</p>
        </div>
      </section>

      <section id="section-34" class="report-section">
        <div class="section-heading"><span>任务 3.4</span><h2>债券指数的利率敏感度</h2></div>
        <h3>怎么做</h3>
        <p>先计算债券资产日对数收益 r<sub>t</sub>=ln(P<sub>t</sub>/P<sub>t−1</sub>)，再计算
          10 年期国债收益率日变化 Δy<sub>t</sub>。两者按共同交易日内连接，分别对上证国债指数、
          上证企债指数和政金债 ETF 进行含截距 OLS 回归。</p>
        <div class="formula">
          r<sub>t</sub><sup>bond</sup> = α + βΔy<sub>t</sub><sup>10Y</sup>
          + ε<sub>t</sub>，隐含利率久期 ≈ −β
        </div>
        <p>系数仍由 OLS 估计；显著性检验使用 Newey–West HAC 稳健标准误，最大滞后为 {HAC_MAX_LAGS}。</p>
        <div class="derivation">
          <h3>为什么 −β 可以解释为隐含利率久期</h3>
          <p>小幅收益率变化下，债券的一阶近似为 r<sup>bond</sup>≈−DΔy。
            将它与回归式 r<sup>bond</sup>=α+βΔy+ε 对照，可得 D≈−β。
            单因子含截距 OLS 的斜率也可以写成：</p>
          <div class="formula">β̂ = Cov(Δy,r<sup>bond</sup>) / Var(Δy)</div>
          <p>OLS 系数本身不因 HAC 而改变。Newey–West 只修正协方差矩阵，使标准误、t 值和 p 值
            对异方差及至多 5 阶的残差自相关更稳健。由于横轴使用小数收益率变化，−β 的单位直接是年。</p>
        </div>
        <h3>结果</h3>
        {regression_table}
        <div class="chart-card">{figures['module3_rate_sensitivity_regressions']}</div>
        <div class="analysis-box">
          <h3>结果分析</h3>
          <p>上证国债指数 β={treasury_regression['beta']:.4f}，对应隐含久期
            <strong>
              {treasury_regression['implied_rate_duration_years']:.4f} 年
            </strong>，且系数显著。
            政金债 ETF 的隐含久期为 {policy_regression['implied_rate_duration_years']:.4f} 年，
            与其 7—10 年期限定位相符。上证企债指数 β={enterprise_regression['beta']:.4f}，
            p={enterprise_regression['beta_p_value']:.4f}，说明单一国债利率因子解释力很弱。</p>
          <p><strong>解释边界：</strong>回归久期是统计敏感度，不等同于根据现金流计算的法定久期；企债还受到信用利差和成分结构影响。</p>
        </div>
      </section>

      <section id="section-35" class="report-section">
        <div class="section-heading">
          <span>任务 3.5</span><h2>2024 年末利率快速下行阶段</h2>
        </div>
        <h3>怎么做</h3>
        <p>截取 2024-11-01 至 2024-12-31，将 10 年期国债收益率与三类债券资产按共同交易日对齐。
          债券资产以区间首个共同交易日为基准，计算买入并持有累计收益 P<sub>t</sub>/P<sub>0</sub>−1。</p>
        <div class="derivation">
          <h3>共同日期与累计收益</h3>
          <p>先将三类债券价格转为宽表，再与 10 年期收益率按日期内连接；任何一类资产缺失的日期都不进入案例。
            最终得到 {len(late_period)} 个共同观测。累计收益直接使用指数或 ETF 点位之比，
            不把日对数收益简单相加，以保持买入持有收益的直观含义。</p>
        </div>
        <h3>结果</h3>
        <p>10 年期国债收益率由 <strong>{start_yield:.4%}</strong> 降至
          <strong>{end_yield:.4%}</strong>，累计变化
          <strong>{yield_change_bp:.2f} bp</strong>。</p>
        {late_return_table}
        <div class="chart-card">{figures['module3_late_2024_rate_stage']}</div>
        <div class="analysis-box">
          <h3>结果分析</h3>
          <p>利率下降期间三类资产均取得正收益，但久期较长的政金债 ETF 反应最强；
            企债指数受到信用利差和指数期限结构影响，涨幅明显低于政金债 ETF。</p>
          <p><strong>配置含义：</strong>债券并非同质资产，判断降息受益程度时需要同时考虑久期、信用风险和指数构成。</p>
        </div>
      </section>

      <section id="section-36" class="report-section">
        <div class="section-heading"><span>深化分析</span><h2>2024 年末实际凸性归因</h2></div>
        <h3>怎么做</h3>
        <p>为隔离纯利率效应，构造固定剩余期限为 10 年的零息债，使用区间期初收益率计算初始价格，
          使用期末收益率精确重定价，并与久期、久期加凸性两种近似比较。该理论归因不把真实债券指数收益完全解释为利率效应。</p>
        <div class="derivation">
          <h3>归因分解</h3>
          <div class="formula-grid">
            <div class="formula">久期贡献：R<sub>D</sub> = −D<sub>mod</sub>Δy</div>
            <div class="formula">凸性贡献：R<sub>C</sub> = ½C(Δy)<sup>2</sup></div>
            <div class="formula">
              二阶估计：R<sub>D+C</sub> = R<sub>D</sub> + R<sub>C</sub>
            </div>
          </div>
          <p>剩余期限固定在 10 年，是为了把观察到的收益率变化映射为纯利率价格效应；
            若让期限自然缩短，还会混入持有期滚降效应。真实指数收益还可能包含票息、成分调整和信用利差变化。</p>
        </div>
        <h3>结果</h3>
        {attribution_table}
        <div class="chart-card">{figures['module3_realized_2024_convexity']}</div>
        <div class="analysis-box">
          <h3>结果分析</h3>
          <p>收益率下降 {abs(attribution['yield_change_bp']):.2f}bp 时，精确利率驱动收益为
            {attribution['exact_rate_driven_return']:.3%}。仅久期估计误差为
            <strong>{duration_error_bp:.3f}bp</strong>；加入凸性后误差降至
            <strong>{convexity_error_bp:.3f}bp</strong>。</p>
          <p><strong>结论：</strong>在接近 50bp 的实际利率变化中，凸性修正显著改善近似精度，验证了原作业要求讨论的凸性价值。</p>
        </div>
      </section>

      <section id="section-37" class="report-section">
        <div class="section-heading"><span>稳健性分析</span><h2>252 个共同观测窗口的滚动隐含久期</h2></div>
        <h3>怎么做</h3>
        <p>在每个包含 252 个共同观测的滚动窗口内，利用
          β=Cov(Δy,r)/Var(Δy) 重新估计单因子 OLS 斜率，并取 −β 作为时变隐含利率久期。
          窗口不足 252 个共同观测时不输出结果。</p>
        <div class="derivation">
          <h3>滚动计算细节</h3>
          <div class="formula">
            β̂<sub>t,252</sub> =
            Cov(Δy<sub>t−251:t</sub>,r<sub>t−251:t</sub>) /
            Var(Δy<sub>t−251:t</sub>)，D̂<sub>t</sub> = −β̂<sub>t,252</sub>
          </div>
          <p>“252 个共同观测”指对齐后的 252 个有效交易日，不是 252 个自然日。
            截距按窗口内均值计算为 α̂=r̄−β̂Δȳ，R² 等于窗口内相关系数的平方。
            因此首次滚动估计会晚于原始样本起点约一个交易年。</p>
        </div>
        <h3>结果</h3>
        {rolling_table}
        <div class="chart-card">{figures['module3_rolling_rate_duration']}</div>
        <div class="analysis-box">
          <h3>结果分析</h3>
          <p>隐含久期会随市场阶段和指数结构变化，并不是固定常数。企债指数出现负估计，
            表示该窗口内统计关系受到信用利差等因素主导，不应解释为现金流意义上的负久期。</p>
          <p><strong>使用建议：</strong>全样本回归适合概括平均敏感度；风险监控应同时参考滚动结果，并结合产品披露的实际久期。</p>
        </div>
      </section>

      <section id="limitations" class="report-section">
        <div class="section-heading"><span>研究边界</span><h2>局限性与结论</h2></div>
        <div class="two-column">
          <div class="panel">
            <h3>主要局限性</h3>
            <ul>
              <li>久期和压力测试采用零息债近似，未显式建模票息、应计利息和现金流再投资。</li>
              <li>平行移动和线性陡峭化是简化情景，不能覆盖所有非平行曲线变化。</li>
              <li>单因子回归不能完全解释信用债收益，结果不等同于基金或指数公布的组合久期。</li>
              <li>2024 年末归因固定剩余期限为 10 年，目的是隔离利率效应，而非复刻可交易债券全过程。</li>
            </ul>
          </div>
          <div class="panel conclusion">
            <h3>核心结论</h3>
            <p>当前收益率曲线可由 Nelson–Siegel 模型较好概括；期限越长，价格对利率变化越敏感。</p>
            <p>久期适合小幅变动下的一阶估计，凸性在长久期和大幅利率变化中具有实质价值。</p>
            <p>历史回归表明不同债券资产的利率暴露差异显著，资产配置应区分利率风险、信用风险和产品结构。</p>
          </div>
        </div>
      </section>

      <section id="appendix" class="report-section">
        <div class="section-heading">
          <span>附录</span><h2>可复现性目录</h2>
        </div>
        <p>本报告中的数字、表格和图形都由同一入口脚本生成，不需要手工复制结果。
          以下目录列出从数据库到最终 HTML 的完整依赖关系。</p>

        <h3>A.1 项目文件与职责</h3>
        <pre class="code-block">GroupAssignment_FinancialDataAnalysis/
├── Assignment1/
│   ├── data/
│   │   ├── data.duckdb                 # 唯一分析数据源
│   │   ├── 数据说明.md                 # 表结构、字段和来源
│   │   └── 数据质量报告.md             # 缺失、重复、范围与日期校验
│   ├── analysis/fixed_income/
│   │   ├── config.py                   # 常量、路径和结果数据类
│   │   ├── repository.py               # DuckDB 只读 SQL 与边界校验
│   │   ├── curve.py                    # NS、定价、久期、凸性和压力测试
│   │   ├── market.py                   # 单因子回归与滚动隐含久期
│   │   ├── charts.py                   # Plotly 图表和 SVG 导出
│   │   ├── outputs.py                  # CSV 结果表
│   │   ├── html_report.py              # 方法、结果、图表与附录整合
│   │   └── fixed_income_analysis.py    # 唯一命令行入口
│   ├── output/fixed_income/            # HTML 报告和 9 个 CSV
│   └── figures/module3/                # 6 张 Plotly SVG
├── requirements.txt
└── requirements_full.txt</pre>

        <h3>A.2 一键运行</h3>
        <pre class="code-block">cd GroupAssignment_FinancialDataAnalysis
source ../.venv/bin/activate
python Assignment1/analysis/fixed_income/fixed_income_analysis.py</pre>
        <p>脚本依次执行：读取并校验输入 → 计算全部结果 → 写出 CSV → 构建单文件 HTML →
          通过 Kaleido 批量导出 SVG。分析脚本不会下载数据，也不会修改 DuckDB。</p>

        <h3>A.3 固定参数</h3>
        <table class="dataframe data-table">
          <thead><tr><th>参数</th><th>值</th><th>作用</th></tr></thead>
          <tbody>
            <tr><td>ANALYSIS_START_DATE</td><td>2019-01-01</td><td>历史回归展示起点</td></tr>
            <tr><td>LATE_2024_START_DATE</td><td>2024-11-01</td><td>年末案例起点</td></tr>
            <tr><td>LATE_2024_END_DATE</td><td>2024-12-31</td><td>年末案例终点</td></tr>
            <tr><td>FACE_VALUE</td><td>100</td><td>零息债面值</td></tr>
            <tr><td>HAC_MAX_LAGS</td><td>{HAC_MAX_LAGS}</td>
              <td>Newey–West 最大滞后</td></tr>
            <tr><td>ROLLING_REGRESSION_WINDOW</td><td>252</td><td>滚动回归共同观测数</td></tr>
            <tr><td>复利口径</td><td>年复利</td><td>零息债定价、久期和凸性</td></tr>
          </tbody>
        </table>

        <h3>A.4 结果文件目录</h3>
        <div class="two-column">
          <div class="panel">
            <h3>表格与报告</h3>
            <ul class="artifact-list">
              <li><code>module3_fixed_income_dashboard.html</code>：本报告，
                内嵌 Plotly.js 和全部交互图。</li>
              <li><code>nelson_siegel_parameters.csv</code>：最终参数及 RMSE。</li>
              <li><code>nelson_siegel_start_diagnostics.csv</code>：五组初值和收敛结果。</li>
              <li><code>nelson_siegel_residuals.csv</code>：逐期限实际值、拟合值和残差。</li>
              <li><code>duration_convexity.csv</code>：关键期限价格和风险指标。</li>
              <li><code>stress_test_results.csv</code>：全部期限和情景的重定价结果。</li>
              <li><code>rate_sensitivity_regressions.csv</code>：三类资产 HAC 回归统计量。</li>
              <li><code>late_2024_period.csv</code>：年末共同日期面板。</li>
              <li><code>realized_2024_convexity_attribution.csv</code>：实际凸性归因。</li>
              <li><code>rolling_rate_duration.csv</code>：252 观测滚动久期。</li>
            </ul>
          </div>
          <div class="panel">
            <h3>静态图</h3>
            <ul class="artifact-list">
              <li><code>module3_nelson_siegel_curve.svg</code></li>
              <li><code>module3_stress_test_errors.svg</code></li>
              <li><code>module3_rate_sensitivity_regressions.svg</code></li>
              <li><code>module3_late_2024_rate_stage.svg</code></li>
              <li><code>module3_realized_2024_convexity.svg</code></li>
              <li><code>module3_rolling_rate_duration.svg</code></li>
            </ul>
          </div>
        </div>

        <h3>A.5 复核顺序</h3>
        <ol>
          <li>检查 <code>数据质量报告.md</code>，确认输入记录数、日期覆盖、缺失和重复校验。</li>
          <li>运行唯一入口脚本，并确认终端输出的结果目录和图表目录。</li>
          <li>将 HTML 中的参数、回归和压力测试数字与同名 CSV 交叉核对。</li>
          <li>确认 HTML 包含 6 个 Plotly 图容器，且断网后仍能缩放和悬停。</li>
          <li>运行
            <code>python -m compileall -q Assignment1/analysis/fixed_income</code>
            做语法检查。</li>
        </ol>
        <div class="note">
          可复现性边界：报告依赖已生成的 <code>data.duckdb</code>。若更新原始数据，应先按模块 1
          的下载、清洗、校验顺序重建数据库，再运行模块 3；不要直接修改 CSV 或 HTML 中的数字。
        </div>
      </section>
    </main>
  </div>
</body>
</html>
"""


def _source_table(results: AnalysisResults) -> str:
    """Build source-table row counts and date coverage."""
    descriptions = {
        "assets": "资产元数据",
        "index_daily": "指数与 ETF 日线",
        "gov_yield_daily": "国债到期收益率历史",
        "yield_curve_snapshot": "最新国债收益率曲线",
        "trading_calendar": "A 股交易日历",
    }
    table = results.data_audit.source_tables.copy()
    table["description"] = table["table_name"].map(descriptions)
    table = table[
        ["table_name", "description", "n_rows", "start_date", "end_date"]
    ]
    table.columns = ["DuckDB 表", "内容", "记录数", "起始日期", "结束日期"]
    table["记录数"] = table["记录数"].map(lambda value: f"{int(value):,}")
    for column in ("起始日期", "结束日期"):
        table[column] = table[column].map(_format_optional_date)
    return _table_html(table)


def _bond_asset_table(results: AnalysisResults) -> str:
    """Build metadata and coverage for bond assets used by Module 3."""
    table = results.data_audit.bond_assets.copy()
    table["tenor_bucket"] = table["tenor_bucket"].fillna("—")
    table = table[
        [
            "asset_id",
            "asset_name",
            "symbol",
            "source",
            "return_type",
            "tenor_bucket",
            "n_rows",
            "start_date",
            "end_date",
        ]
    ]
    table.columns = [
        "asset_id",
        "资产",
        "代码",
        "数据接口",
        "价格口径",
        "期限段",
        "记录数",
        "起始日期",
        "结束日期",
    ]
    table["记录数"] = table["记录数"].map(lambda value: f"{int(value):,}")
    for column in ("起始日期", "结束日期"):
        table[column] = table[column].map(_format_optional_date)
    return _table_html(table)


def _yield_tenor_table(results: AnalysisResults) -> str:
    """Build historical government-yield coverage by tenor."""
    table = results.data_audit.yield_tenors.copy()
    table.columns = ["期限（年）", "记录数", "起始日期", "结束日期"]
    table["期限（年）"] = table["期限（年）"].map(lambda value: f"{value:g}")
    table["记录数"] = table["记录数"].map(lambda value: f"{int(value):,}")
    for column in ("起始日期", "结束日期"):
        table[column] = table[column].map(_format_optional_date)
    return _table_html(table)


def _curve_source_table(curve: pd.DataFrame) -> str:
    """Build the latest observed curve table used by Nelson–Siegel."""
    table = curve[["curve_date", "tenor_years", "yield_decimal"]].copy()
    table.columns = ["曲线日期", "期限（年）", "实际收益率"]
    table["曲线日期"] = table["曲线日期"].map(_format_optional_date)
    table["期限（年）"] = table["期限（年）"].map(lambda value: f"{value:g}")
    table["实际收益率"] = table["实际收益率"].map(
        lambda value: f"{value:.4%}"
    )
    return _table_html(table)


def _start_diagnostics_table(diagnostics: pd.DataFrame) -> str:
    """Build multi-start Nelson–Siegel convergence diagnostics."""
    table = diagnostics[
        [
            "start_id",
            "initial_beta_0",
            "initial_beta_1",
            "initial_beta_2",
            "initial_tau",
            "success",
            "sse",
            "beta_0",
            "beta_1",
            "beta_2",
            "tau",
        ]
    ].copy()
    table.columns = [
        "初值组",
        "初始 β₀",
        "初始 β₁",
        "初始 β₂",
        "初始 τ",
        "收敛",
        "SSE",
        "最终 β₀",
        "最终 β₁",
        "最终 β₂",
        "最终 τ",
    ]
    table["收敛"] = table["收敛"].map({True: "是", False: "否"})
    for column in (
        "初始 β₀",
        "初始 β₁",
        "初始 β₂",
        "最终 β₀",
        "最终 β₁",
        "最终 β₂",
    ):
        table[column] = table[column].map(lambda value: f"{value:.6f}")
    for column in ("初始 τ", "最终 τ"):
        table[column] = table[column].map(lambda value: f"{value:.4f}")
    table["SSE"] = table["SSE"].map(lambda value: f"{value:.3e}")
    return _table_html(table)


def _scenario_shock_table(stress_results: pd.DataFrame) -> str:
    """Build yield shocks in basis points for each scenario and tenor."""
    scenario_order = list(SCENARIOS)
    table = stress_results.pivot(
        index=["scenario_id", "scenario"],
        columns="tenor_years",
        values="yield_shock_decimal",
    ).reset_index()
    table["scenario_id"] = pd.Categorical(
        table["scenario_id"],
        categories=scenario_order,
        ordered=True,
    )
    table = table.sort_values("scenario_id").drop(columns="scenario_id")
    table.columns = ["情景", "1 年", "3 年", "5 年", "10 年"]
    for column in ("1 年", "3 年", "5 年", "10 年"):
        table[column] = table[column].map(lambda value: f"{value * 10_000:+.2f}")
    return _table_html(table)


def _format_optional_date(value: object) -> str:
    """Format a nullable date value for report tables."""
    if pd.isna(value):
        return "—"
    return pd.Timestamp(value).date().isoformat()


def _parameter_table(
    beta_0: float,
    beta_1: float,
    beta_2: float,
    tau: float,
    rmse_bp: float,
) -> str:
    """Build the Nelson–Siegel parameter table."""
    table = pd.DataFrame(
        [
            ("β₀", beta_0, "长期利率水平"),
            ("β₁", beta_1, "短端斜率"),
            ("β₂", beta_2, "中端曲率"),
            ("τ", tau, "曲率位置与衰减速度"),
            ("RMSE", rmse_bp, "拟合误差（bp）"),
        ],
        columns=["参数", "估计值", "含义"],
    )
    table["估计值"] = table["估计值"].map(lambda value: f"{value:.6f}")
    return _table_html(table)


def _residual_table(curve_results: pd.DataFrame) -> str:
    """Build the observed-versus-fitted curve table."""
    table = curve_results[
        ["tenor_years", "yield_decimal", "fitted_yield_decimal", "residual_bp"]
    ].copy()
    table.columns = ["期限（年）", "实际收益率", "拟合收益率", "残差（bp）"]
    table["期限（年）"] = table["期限（年）"].map(lambda value: f"{value:g}")
    for column in ("实际收益率", "拟合收益率"):
        table[column] = table[column].map(lambda value: f"{value:.4%}")
    table["残差（bp）"] = table["残差（bp）"].map(
        lambda value: f"{value:.3f}"
    )
    return _table_html(table)


def _duration_table(duration_convexity: pd.DataFrame) -> str:
    """Build the zero-coupon duration and convexity table."""
    table = duration_convexity.copy()
    table.columns = [
        "期限（年）",
        "拟合收益率",
        "理论价格",
        "麦考利久期",
        "修正久期",
        "凸性",
    ]
    table["期限（年）"] = table["期限（年）"].map(lambda value: f"{value:g}")
    table["拟合收益率"] = table["拟合收益率"].map(
        lambda value: f"{value:.4%}"
    )
    for column in ("理论价格", "麦考利久期", "修正久期", "凸性"):
        table[column] = table[column].map(lambda value: f"{value:.4f}")
    return _table_html(table)


def _stress_table(stress_results: pd.DataFrame) -> str:
    """Build the detailed stress-repricing comparison table."""
    scenario_order = {scenario: index for index, scenario in enumerate(SCENARIOS)}
    table = stress_results[
        [
            "scenario_id",
            "scenario",
            "tenor_years",
            "exact_price_change",
            "duration_price_change",
            "duration_convexity_price_change",
            "duration_error_bp",
            "duration_convexity_error_bp",
        ]
    ].copy()
    table["scenario_order"] = table["scenario_id"].map(scenario_order)
    table = table.sort_values(["scenario_order", "tenor_years"])
    table = table.drop(columns=["scenario_id", "scenario_order"])
    table.columns = [
        "情景",
        "期限（年）",
        "精确变化",
        "久期近似",
        "久期+凸性",
        "久期误差（bp）",
        "凸性修正误差（bp）",
    ]
    table["期限（年）"] = table["期限（年）"].map(lambda value: f"{value:g}")
    for column in ("精确变化", "久期近似", "久期+凸性"):
        table[column] = table[column].map(lambda value: f"{value:.3%}")
    for column in ("久期误差（bp）", "凸性修正误差（bp）"):
        table[column] = table[column].map(lambda value: f"{value:.3f}")
    return _table_html(table)


def _regression_table(regressions: pd.DataFrame) -> str:
    """Build the HAC rate-sensitivity regression table."""
    table = regressions[
        [
            "asset_name",
            "beta",
            "beta_hac_se",
            "beta_t_value",
            "beta_p_value",
            "r_squared",
            "n_observations",
            "implied_rate_duration_years",
        ]
    ].copy()
    table.columns = ["资产", "β", "HAC SE", "t 值", "p 值", "R²", "N", "隐含久期（年）"]
    for column in ("β", "HAC SE", "R²", "隐含久期（年）"):
        table[column] = table[column].map(lambda value: f"{value:.4f}")
    table["t 值"] = table["t 值"].map(lambda value: f"{value:.2f}")
    table["p 值"] = table["p 值"].map(lambda value: f"{value:.4g}")
    table["N"] = table["N"].astype(int).astype(str)
    return _table_html(table)


def _late_return_table(late_period: pd.DataFrame) -> str:
    """Build the late-2024 observed cumulative-return table."""
    rows = [
        {
            "资产": asset_name,
            "区间累计收益": (
                f"{late_period[f'{asset_id}_cumulative_return'].iloc[-1]:.2%}"
            ),
        }
        for asset_id, asset_name in BOND_ASSETS.items()
    ]
    return _table_html(pd.DataFrame(rows))


def _attribution_table(attribution: pd.Series) -> str:
    """Build the realized convexity attribution table."""
    table = pd.DataFrame(
        [
            ("精确重定价", attribution["exact_rate_driven_return"]),
            ("仅久期估计", attribution["duration_return"]),
            ("凸性贡献", attribution["convexity_contribution"]),
            ("久期+凸性估计", attribution["duration_convexity_return"]),
        ],
        columns=["项目", "收益或贡献"],
    )
    table["收益或贡献"] = table["收益或贡献"].map(
        lambda value: f"{value:.4%}"
    )
    return _table_html(table)


def _rolling_table(results: AnalysisResults) -> str:
    """Build rolling implied-duration summary statistics."""
    rows: list[dict[str, str]] = []
    for asset_id, asset_name in BOND_ASSETS.items():
        sample = results.rolling_duration.loc[
            results.rolling_duration["asset_id"] == asset_id
        ]
        duration = sample["implied_rate_duration_years"]
        rows.append(
            {
                "资产": asset_name,
                "首个估计日": pd.Timestamp(
                    sample["trade_date"].iloc[0]
                ).date().isoformat(),
                "期末估计日": pd.Timestamp(
                    sample["trade_date"].iloc[-1]
                ).date().isoformat(),
                "最低久期": f"{duration.min():.4f}",
                "最高久期": f"{duration.max():.4f}",
                "期末久期": f"{duration.iloc[-1]:.4f}",
            }
        )
    return _table_html(pd.DataFrame(rows))


def _table_html(table: pd.DataFrame) -> str:
    """Render a DataFrame as a consistently styled HTML table."""
    return table.to_html(
        index=False,
        classes="data-table",
        border=0,
        justify="left",
        escape=True,
    )


def _report_css() -> str:
    """Return the standalone report stylesheet."""
    return """
    :root { --ink:#162033; --muted:#5f6b7a; --line:#dbe2ea; --paper:#ffffff;
            --wash:#f3f6f9; --navy:#173b57; --blue:#1f77b4; --teal:#14807c;
            --amber:#c27a13; --shadow:0 8px 28px rgba(24,45,70,.08); }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { margin:0; color:var(--ink); background:var(--wash);
           font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
           "Microsoft YaHei",sans-serif; line-height:1.72; }
    .hero { color:white;
            background:linear-gradient(128deg,#102f47 0%,#1e5970 58%,#14807c 100%); }
    .hero-inner { max-width:1240px; margin:auto; padding:58px 28px 48px; }
    .eyebrow { margin:0 0 8px; color:#b9e6e1; font-size:13px; font-weight:700;
               letter-spacing:.08em; text-transform:uppercase; }
    h1 { margin:0; font-size:clamp(34px,5vw,58px); line-height:1.15; }
    .hero-copy { max-width:850px; margin:18px 0 28px; color:#e4f0f3; font-size:18px; }
    .hero-metrics { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
    .hero-metrics div { padding:14px 16px; border:1px solid rgba(255,255,255,.18);
                        border-radius:10px; background:rgba(255,255,255,.08); }
    .hero-metrics span,.hero-metrics strong { display:block; }
    .hero-metrics span { color:#c9e3e7; font-size:12px; }
    .hero-metrics strong { margin-top:3px; font-size:15px; }
    .page-shell { display:grid; grid-template-columns:220px minmax(0,1000px); gap:28px;
                  max-width:1260px; margin:0 auto; padding:32px 20px 70px; }
    .toc { position:sticky; top:18px; align-self:start; padding:18px;
           background:var(--paper); border:1px solid var(--line); border-radius:12px; }
    .toc-title { margin-bottom:9px; font-weight:800; }
    .toc a { display:block; padding:6px 0; color:var(--muted); font-size:13px;
             text-decoration:none; border-bottom:1px solid #edf1f5; }
    .toc a:hover { color:var(--teal); }
    main { min-width:0; }
    .report-section { margin-bottom:26px; padding:34px; background:var(--paper);
                      border:1px solid var(--line); border-radius:14px;
                      box-shadow:var(--shadow); }
    .section-heading { margin-bottom:22px; padding-bottom:14px;
                       border-bottom:1px solid var(--line); }
    .section-heading span { color:var(--teal); font-size:12px; font-weight:800;
                            letter-spacing:.08em; text-transform:uppercase; }
    h2 { margin:3px 0 0; color:var(--navy); font-size:28px; line-height:1.3; }
    h3 { margin:24px 0 8px; color:var(--navy); font-size:17px; }
    p { margin:8px 0 16px; color:#354255; }
    ul,ol { margin:8px 0; padding-left:22px; }
    code { padding:2px 6px; color:#0d5d67; background:#eaf5f4; border-radius:4px; }
    .two-column { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    .schema-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
    .panel { padding:20px; background:#f8fafc; border:1px solid var(--line);
             border-radius:10px; }
    .panel h3 { margin-top:0; }
    .panel dl { margin:0; }
    .panel dt { margin-top:10px; color:var(--navy); font-weight:750; }
    .panel dd { margin:2px 0 0; color:var(--muted); }
    .conclusion { border-top:4px solid var(--teal); }
    .note { margin-top:16px; padding:12px 15px; color:#32546b; background:#edf6fa;
            border-left:4px solid var(--blue); border-radius:6px; }
    .formula-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
    .formula { margin:14px 0; padding:14px 16px; overflow-x:auto; color:#173b57;
               background:#f1f6f8; border:1px solid #d8e7ec; border-radius:8px;
               font-family:"Times New Roman",serif; font-size:16px; text-align:center; }
    .derivation { margin:18px 0; padding:18px 20px; background:#f7f6fb;
                  border:1px solid #e2dff0; border-left:4px solid #7567a8;
                  border-radius:8px; }
    .derivation h3 { margin-top:0; color:#554783; }
    .lineage { display:grid; grid-template-columns:1fr auto 1fr auto 1fr auto 1fr;
               gap:10px; align-items:center; margin:18px 0; }
    .lineage div { min-height:90px; padding:14px; text-align:center; background:#f7fafb;
                   border:1px solid var(--line); border-radius:8px; }
    .lineage strong,.lineage span { display:block; }
    .lineage span { margin-top:5px; color:var(--muted); font-size:12px; }
    .lineage b { color:var(--teal); font-size:22px; }
    .chart-card { margin:20px 0; padding:6px; overflow:hidden;
                  border:1px solid var(--line);
                  border-radius:10px; background:white; }
    .result-strip { display:grid; grid-template-columns:repeat(3,1fr);
                    gap:12px; margin:16px 0; }
    .result-strip div { padding:16px; background:#f7fafb; border:1px solid var(--line);
                        border-top:4px solid var(--teal); border-radius:8px; }
    .result-strip span,.result-strip strong,.result-strip small { display:block; }
    .result-strip span { color:var(--muted); font-size:12px; }
    .result-strip strong { margin:4px 0; color:var(--navy); font-size:23px; }
    .result-strip small { color:#657386; }
    .analysis-box { margin-top:20px; padding:18px 20px; background:#fff9ed;
                    border-left:4px solid var(--amber); border-radius:8px; }
    .analysis-box h3 { margin-top:0; color:#85530c; }
    details { margin:16px 0; border:1px solid var(--line);
              border-radius:8px; overflow:hidden; }
    summary { padding:12px 15px; cursor:pointer; color:var(--navy); background:#f7f9fb;
              font-weight:700; }
    .dataframe { width:100%; border-collapse:collapse; font-size:13px; }
    .dataframe th { position:sticky; top:0; padding:10px; color:white;
                    background:var(--navy);
                    text-align:left; white-space:nowrap; }
    .dataframe td { padding:9px 10px; border-bottom:1px solid #e6ebf0;
                    white-space:nowrap; }
    .dataframe tbody tr:nth-child(even) { background:#f7f9fb; }
    details .dataframe { display:block; max-height:430px; overflow:auto; }
    .caption { margin-top:4px; color:var(--muted); font-size:12px; }
    .code-block { padding:18px; overflow:auto; color:#d9edf2; background:#102f47;
                  border-radius:9px;
                  font:13px/1.65 "SFMono-Regular",Consolas,monospace; }
    .artifact-list { padding-left:19px; }
    .artifact-list li { margin:7px 0; }
    @media (max-width:900px) {
      .page-shell { display:block; padding:18px 12px 48px; }
      .toc { position:relative; top:0; margin-bottom:18px; }
      .hero-metrics,.two-column,.schema-grid,.result-strip,.formula-grid {
        grid-template-columns:1fr;
      }
      .lineage { grid-template-columns:1fr; }
      .lineage b { transform:rotate(90deg); text-align:center; }
      .report-section { padding:22px 16px; }
      .hero-inner { padding:42px 20px 36px; }
    }
    @media print {
      .toc { display:none; }
      .page-shell { display:block; max-width:none; }
      .report-section { break-inside:avoid; box-shadow:none; }
    }
    """
