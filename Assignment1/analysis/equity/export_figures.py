import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import duckdb

# 基础显示配置：中文字体与负号
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# 路径自动推导
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
DUCKDB_PATH = PROJECT_ROOT / "data" / "data.duckdb"
OUTPUT_DIR = PROJECT_ROOT / "output" / "equity"
FIGURES_DIR = PROJECT_ROOT / "figures" / "module2"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# 1. 第 1 问：图 1-1（收益分布与理论正态拟合）
# ==========================================
print("正在绘制 第1问：图 1-1（收益分布与厚尾检验）...")
con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
df_raw = con.execute("""
    SELECT d.trade_date AS date, a.symbol, d.close
    FROM index_daily d 
    JOIN assets a ON d.asset_id = a.asset_id
    WHERE a.asset_class = 'equity' AND d.trade_date >= '2019-01-01'
    ORDER BY d.trade_date ASC
""").fetchdf()
con.close()

price_df = df_raw.pivot(index='date', columns='symbol', values='close').sort_index()
ret_df = np.log(price_df / price_df.shift(1)).dropna()

name_map = {
    'sh000001': '上证综指',
    'sh000300': '沪深300',
    'sh000905': '中证500',
    'sh000688': '科创50'
}

fig, axes = plt.subplots(1, 4, figsize=(18, 4.5), dpi=300)
fig.suptitle('主要权益指数日对数收益率经验分布与理论正态拟合 (厚尾检验)', fontsize=14, fontweight='bold', y=1.03)

for ax, (sym, name) in zip(axes, name_map.items()):
    if sym not in ret_df.columns:
        continue
    r = ret_df[sym].dropna()
    mu, sigma = r.mean(), r.std()

    # 实际收益经验直方图
    ax.hist(r, bins=60, density=True, alpha=0.6, color='#1f77b4', edgecolor='white', label='实际经验分布')

    # 理论正态拟合曲线
    x_axis = np.linspace(r.min(), r.max(), 300)
    norm_pdf = (1.0 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_axis - mu) / sigma) ** 2)
    ax.plot(x_axis, norm_pdf, color='#d62728', linestyle='--', linewidth=1.8, label='理论正态分布')

    ax.set_title(name, fontsize=12, fontweight='bold')
    ax.set_xlabel('日对数收益率', fontsize=10)
    ax.grid(True, linestyle=':', alpha=0.6)
    if ax == axes[0]:
        ax.set_ylabel('概率密度', fontsize=10)
        ax.legend(frameon=True, fontsize=9)

plt.tight_layout()
fig.savefig(FIGURES_DIR / "图1-1_权益指数收益分布与厚尾检验.svg", format='svg', bbox_inches='tight')
fig.savefig(FIGURES_DIR / "图1-1_权益指数收益分布与厚尾检验.png", format='png', bbox_inches='tight')
plt.close(fig)
print("-> 成功生成: 图1-1_权益指数收益分布与厚尾检验.svg / .png")

# ==========================================
# 2. 第 2 问第一张图：图 2-1（60日滚动年化波动率）
# ==========================================
print("\n正在绘制 第2问：图 2-1（60日滚动年化波动率）...")
vol_csv = OUTPUT_DIR / "明细_权益指数60日滚动年化波动率.csv"
df_vol = pd.read_csv(vol_csv, index_col=0, parse_dates=True)

fig, ax = plt.subplots(figsize=(12, 5.5), dpi=300)
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd']
for col, c in zip(df_vol.columns, colors):
    ax.plot(df_vol.index, df_vol[col] * 100, label=col, color=c, linewidth=1.6)

ax.set_title('主要权益指数 60 日滚动年化波动率时变走势 (2019至今)', fontsize=13, fontweight='bold', pad=12)
ax.set_xlabel('交易日期', fontsize=11)
ax.set_ylabel('年化波动率 (%)', fontsize=11)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0f}%'))
ax.grid(True, linestyle='--', alpha=0.5)
ax.legend(frameon=True, loc='upper left')

plt.tight_layout()
fig.savefig(FIGURES_DIR / "图2-1_60日滚动年化波动率.svg", format='svg', bbox_inches='tight')
fig.savefig(FIGURES_DIR / "图2-1_60日滚动年化波动率.png", format='png', bbox_inches='tight')
plt.close(fig)
print("-> 成功生成: 图2-1_60日滚动年化波动率.svg / .png")

# ==========================================
# 3. 第 2 问第二张图：图 2-2（指数间120日滚动相关）
# ==========================================
print("\n正在绘制 第2问：图 2-2（指数间120日滚动相关）...")
corr_csv = OUTPUT_DIR / "明细_权益指数间120日滚动相关系数.csv"
df_corr = pd.read_csv(corr_csv, index_col=0, parse_dates=True)

fig, ax = plt.subplots(figsize=(12, 5.5), dpi=300)
corr_colors = ['#1f77b4', '#e377c2', '#2ca02c']
for col, c in zip(df_corr.columns, corr_colors):
    ax.plot(df_corr.index, df_corr[col], label=col, color=c, linewidth=1.6)

ax.axhline(0.0, color='gray', linestyle=':', linewidth=1)
ax.set_title('沪深300 与其他主要权益指数间 120 日滚动相关系数序列', fontsize=13, fontweight='bold', pad=12)
ax.set_xlabel('交易日期', fontsize=11)
ax.set_ylabel('Pearson 相关系数', fontsize=11)
ax.set_ylim(-0.2, 1.05)
ax.grid(True, linestyle='--', alpha=0.5)
ax.legend(frameon=True, loc='lower right')

plt.tight_layout()
fig.savefig(FIGURES_DIR / "图2-2_指数间120日滚动相关.svg", format='svg', bbox_inches='tight')
fig.savefig(FIGURES_DIR / "图2-2_指数间120日滚动相关.png", format='png', bbox_inches='tight')
plt.close(fig)
print("-> 成功生成: 图2-2_指数间120日滚动相关.svg / .png")

print("\n【处理完成】图片已全部按照规范重命名为：图1-1、图2-1、图2-2！")