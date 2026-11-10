import numpy as np
import pandas as pd
import duckdb
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

# ==========================================
# 1. 路径自动定位配置
# ==========================================
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent  # 指向 Assignment1 根目录
DUCKDB_PATH = PROJECT_ROOT / "data" / "data.duckdb"
OUTPUT_DIR = PROJECT_ROOT / "output" / "equity"
FIGURES_DIR = PROJECT_ROOT / "figures" / "module2"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# 对应数据库中的 4 大实际权益资产
INDEX_MAP = {
    'sh000001': '上证综指',
    'sh000300': '沪深300',
    'sh000688': '科创50',
    'sh000905': '中证500'
}

# ==========================================
# 2. 从 DuckDB 读取数据 (关联 assets 与 index_daily)
# ==========================================
def load_equity_data(db_path: Path) -> pd.DataFrame:
    con = duckdb.connect(str(db_path), read_only=True)
    
    # 严格使用 SQL JOIN 获取权益资产收盘价
    query = """
        SELECT 
            d.trade_date AS date,
            a.symbol,
            d.close
        FROM index_daily d
        JOIN assets a ON d.asset_id = a.asset_id
        WHERE a.asset_class = 'equity'
          AND d.trade_date >= '2019-01-01'
        ORDER BY d.trade_date ASC, a.symbol ASC
    """
    df = con.execute(query).fetchdf()
    con.close()
    
    # 透视表转换：Index=date, Columns=symbol
    price_df = df.pivot(index='date', columns='symbol', values='close')
    price_df.index = pd.to_datetime(price_df.index)
    price_df = price_df.sort_index().dropna(how='all')
    return price_df

# ==========================================
# 3. 任务 1：收益分布刻画与 JB 正态性检验 (纯数学公式实现)
# ==========================================
def task1_distribution_analysis(log_returns: pd.DataFrame):
    stats_list = []
    valid_symbols = [s for s in INDEX_MAP.keys() if s in log_returns.columns]

    for sym in valid_symbols:
        name = INDEX_MAP[sym]
        r = log_returns[sym].dropna()
        n = len(r)
        mean_val = float(r.mean())
        std_val = float(r.std())
        skew_val = float(r.skew())
        kurt_val = float(r.kurtosis())  # pandas 计算的是 Fisher 超额峰度 (正态为 0)
        
        # Jarque-Bera 统计量计算: n/6 * (S^2 + K^2 / 4)
        jb_stat = (n / 6.0) * (skew_val**2 + (kurt_val**2) / 4.0)
        # 自由度为 2 的卡方分布检验 p 值解析解: p = exp(-JB / 2)
        p_val = np.exp(-jb_stat / 2.0)
        
        stats_list.append({
            '指数代码': sym,
            '指数名称': name,
            '样本数': n,
            '日均对数收益': mean_val,
            '年化收益率': mean_val * 252,
            '日收益波动率': std_val,
            '年化波动率': std_val * np.sqrt(252),
            '偏度(Skewness)': skew_val,
            '超额峰度(Kurtosis)': kurt_val,
            'JB检验统计量': jb_stat,
            'JB检验p值': p_val,
            '是否拒绝正态假设(α=0.01)': '是' if p_val < 0.01 else '否'
        })
    
    stats_df = pd.DataFrame(stats_list)
    stats_csv_path = OUTPUT_DIR / "表1-1_权益指数收益分布与正态性检验.csv"
    stats_df.to_csv(stats_csv_path, index=False, encoding='utf-8-sig')
    print(f"\n[OK] 任务1统计检验表已保存至: {stats_csv_path}")
    print(stats_df[['指数名称', '年化收益率', '年化波动率', '偏度(Skewness)', '超额峰度(Kurtosis)', 'JB检验p值']])

    # 使用 Plotly 绘制子图（自动根据实际资产数量排版）
    n_cols = len(valid_symbols)
    fig = make_subplots(
        rows=1, cols=n_cols, 
        subplot_titles=[f"{INDEX_MAP[s]} 收益分布与厚尾检验" for s in valid_symbols],
        horizontal_spacing=0.05
    )

    for i, sym in enumerate(valid_symbols, start=1):
        name = INDEX_MAP[sym]
        r = log_returns[sym].dropna()
        mu, sigma = r.mean(), r.std()
        
        # 实际收益率直方图（概率密度）
        fig.add_trace(
            go.Histogram(
                x=r, histnorm='probability density', name=f'{name} 实际经验分布',
                marker=dict(color='rgba(31, 119, 180, 0.6)', line=dict(color='rgba(31, 119, 180, 1.0)', width=1)),
                opacity=0.75, nbinsx=60, showlegend=(i == 1)
            ),
            row=1, col=i
        )
        
        # 理论正态分布密度曲线 (闭式正态分布公式)
        x_axis = np.linspace(r.min(), r.max(), 300)
        norm_pdf = (1.0 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_axis - mu) / sigma)**2)
        fig.add_trace(
            go.Scatter(
                x=x_axis, y=norm_pdf, mode='lines', name='理论正态分布',
                line=dict(color='red', width=2, dash='dash'),
                showlegend=(i == 1)
            ),
            row=1, col=i
        )

    fig.update_layout(
        title_text="<b>主要权益指数日对数收益率分布与厚尾检验 (2019至今)</b>",
        title_x=0.5,
        template="plotly_white",
        height=480, width=320 * n_cols,
        margin=dict(l=40, r=40, t=80, b=40)
    )
    
    html_path = OUTPUT_DIR / "图1-1_权益指数对数收益分布直方图.html"
    fig.write_html(str(html_path))
    print(f"[OK] 任务1交互式直方图已生成: {html_path}")

# ==========================================
# 4. 任务 2：滚动年化波动率与指数间滚动相关性
# ==========================================
def task2_rolling_metrics(log_returns: pd.DataFrame):
    # 60日滚动年化波动率
    rolling_vol = log_returns.rolling(window=60).std() * np.sqrt(252)
    vol_export = rolling_vol.rename(columns=INDEX_MAP)
    vol_csv_path = OUTPUT_DIR / "明细_权益指数60日滚动年化波动率.csv"
    vol_export.dropna().to_csv(vol_csv_path, encoding='utf-8-sig')

    # 绘制波动率走势图
    fig_vol = go.Figure()
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd']
    for idx, col in enumerate(rolling_vol.columns):
        fig_vol.add_trace(go.Scatter(
            x=rolling_vol.index, y=rolling_vol[col],
            mode='lines', name=INDEX_MAP.get(col, col),
            line=dict(color=colors[idx % len(colors)], width=1.8)
        ))
    fig_vol.update_layout(
        title="<b>主要权益指数 60 日滚动年化波动率时变走势 (2019至今)</b>",
        title_x=0.5,
        xaxis_title="日期", yaxis_title="年化波动率",
        yaxis_tickformat='.1%',
        template="plotly_white",
        height=500, width=1100,
        hovermode="x unified"
    )
    fig_vol.write_html(str(OUTPUT_DIR / "图2-1_60日滚动年化波动率.html"))

    # 120日指数间滚动相关系数序列
    fig_corr = go.Figure()
    pairs = [
        ('sh000300', 'sh000001', '沪深300 vs 上证综指', '#1f77b4'),
        ('sh000300', 'sh000688', '沪深300 vs 科创50', '#ff7f0e'),
        ('sh000300', 'sh000905', '沪深300 vs 中证500', '#2ca02c')
    ]
    
    corr_df = pd.DataFrame(index=log_returns.index)
    for sym1, sym2, label, col_color in pairs:
        if sym1 in log_returns.columns and sym2 in log_returns.columns:
            s_corr = log_returns[sym1].rolling(120).corr(log_returns[sym2])
            corr_df[label] = s_corr
            fig_corr.add_trace(go.Scatter(
                x=s_corr.index, y=s_corr,
                mode='lines', name=label,
                line=dict(color=col_color, width=1.8)
            ))
            
    corr_csv_path = OUTPUT_DIR / "明细_权益指数间120日滚动相关系数.csv"
    corr_df.dropna().to_csv(corr_csv_path, encoding='utf-8-sig')

    fig_corr.update_layout(
        title="<b>权益指数间 120 日滚动相关系数序列 (大盘价值 vs 中小盘/成长)</b>",
        title_x=0.5,
        xaxis_title="日期", yaxis_title="相关系数",
        yaxis=dict(range=[-0.2, 1.05]),
        template="plotly_white",
        height=500, width=1100,
        hovermode="x unified"
    )
    fig_corr.write_html(str(OUTPUT_DIR / "图2-2_指数间120日滚动相关系数.html"))

    print(f"[OK] 任务2图表与数据明细已生成完毕！")

# ==========================================
# 主入口
# ==========================================
if __name__ == "__main__":
    print(f"正在从 DuckDB 读取数据: {DUCKDB_PATH}")
    prices = load_equity_data(DUCKDB_PATH)
    log_returns = np.log(prices / prices.shift(1)).dropna()
    
    print("\n--- 正在执行任务 1：收益分布刻画与 JB 正态性检验 ---")
    task1_distribution_analysis(log_returns)
    
    print("\n--- 正在执行任务 2：滚动年化波动率与指数相关系数 ---")
    task2_rolling_metrics(log_returns)