# 模块3：固定收益分析结果

数据全部从 `Assignment1/data/data.duckdb` 通过 SQL 读取。收益率使用小数口径，债券定价采用面值 100、年复利的零息债近似；回归标准误为 Newey–West HAC（最大滞后 {{ hac_max_lags }}）。

## 3.1 Nelson–Siegel 曲线拟合

曲线日期为 **{{ curve_date }}**。最优参数为：$\beta_0={{ "%.6f"|format(beta_0) }}$，$\beta_1={{ "%.6f"|format(beta_1) }}$，$\beta_2={{ "%.6f"|format(beta_2) }}$，$\tau={{ "%.4f"|format(tau) }}$；8 个期限点的 RMSE 为 **{{ "%.3f"|format(rmse_bp) }} bp**。绝对残差最大的是 {{ "%g"|format(max_residual.tenor_years) }} 年期，残差为 {{ "%.3f"|format(max_residual.residual_bp) }} bp。

**结果说明什么：** $\beta_0$ 对应长期利率水平；$\beta_1$ 为负，说明短端低于长期水平；$\beta_2$ 描述中端弯曲；$\tau$ 控制曲率峰值位置及因子衰减速度。较低 RMSE 表明四参数曲线能简洁概括该截面。

**对资产配置有何影响：** 延长期限可能提高静态收益率，但也会显著增加利率敏感度；配置决策应同时看收益率曲线形状与久期风险。

## 3.2 久期和凸性

10 年期零息债的拟合收益率为 {{ "%.4f%%"|format(long_bond.fitted_yield_decimal * 100) }}，理论价格为 {{ "%.4f"|format(long_bond.price) }}，修正久期为 {{ "%.4f"|format(long_bond.modified_duration_years) }} 年，凸性为 {{ "%.4f"|format(long_bond.convexity) }}。

**结果说明什么：** 在零息债假设下，麦考利久期等于期限；期限越长，修正久期和凸性越高，价格对收益率变化越敏感。

**对资产配置有何影响：** 长久期债券在利率下行时提供更高资本利得，但在利率上行时承担更大回撤。

## 3.3 利率压力测试

仅久期近似的最大绝对误差出现在 **{{ worst_duration.scenario }}、{{ "%g"|format(worst_duration.tenor_years) }} 年期**，为 {{ "%.3f"|format(worst_duration.duration_error_bp) }} bp；加入凸性后的最大绝对误差为 {{ "%.3f"|format(worst_convexity.duration_convexity_error_bp) }} bp。跨全部期限和情景，凸性使平均绝对误差降低 **{{ "%.1f%%"|format(average_error_reduction * 100) }}**。

**对资产配置有何影响：** 对含长久期债券的组合做压力测试时，应至少使用久期加凸性，重要决策则应采用精确重定价。

## 3.4 债券指数利率敏感度

| 资产 | $\alpha$ | $\beta$ | $SE_{HAC}(\beta)$ | $t$ | $p$ | $R^2$ | $N$ | 隐含利率久期 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{% for row in regressions -%}
| {{ row.asset_name }} | {{ "%.8f"|format(row.alpha) }} | {{ "%.4f"|format(row.beta) }} | {{ "%.4f"|format(row.beta_hac_se) }} | {{ "%.2f"|format(row.beta_t_value) }} | {{ "%.4g"|format(row.beta_p_value) }} | {{ "%.4f"|format(row.r_squared) }} | {{ row.n_observations }} | {{ "%.4f"|format(row.implied_rate_duration_years) }} |
{% endfor %}

主结果中，上证国债指数的 $\beta={{ "%.4f"|format(treasury_regression.beta) }}$，对应隐含利率久期约 **{{ "%.4f"|format(treasury_regression.implied_rate_duration_years) }} 年**。企债指数还受信用利差影响，政金债 ETF 是较短样本的稳健性参照。

## 3.5 2024 年末利率阶段

10 年期国债收益率从 {{ "%.4f%%"|format(start_yield * 100) }} 变为 {{ "%.4f%%"|format(end_yield * 100) }}，累计变化 **{{ "%.2f"|format(yield_change_bp) }} bp**；同期累计收益为：{% for row in late_returns %}{{ row.asset_name }} {{ "%.2f%%"|format(row.value * 100) }}{% if not loop.last %}；{% endif %}{% endfor %}。

## 3.6 利率下行情景与实际凸性归因

平行下移 100bp 时，10 年零息债精确价格变化为 {{ "%.3f%%"|format(down_100bp.exact_price_change * 100) }}，仅久期近似为 {{ "%.3f%%"|format(down_100bp.duration_price_change * 100) }}，久期加凸性为 {{ "%.3f%%"|format(down_100bp.duration_convexity_price_change * 100) }}。

2024 年末 10 年期收益率实际下降 {{ "%.2f"|format(attribution.yield_change_bp|abs) }}bp。固定剩余期限的 10 年零息债精确重定价为 {{ "%.3f%%"|format(attribution.exact_rate_driven_return * 100) }}，仅久期估计为 {{ "%.3f%%"|format(attribution.duration_return * 100) }}，凸性贡献为 {{ "%.3f%%"|format(attribution.convexity_contribution * 100) }}，久期加凸性估计为 {{ "%.3f%%"|format(attribution.duration_convexity_return * 100) }}。

## 3.7 252 个共同观测滚动隐含久期

| 资产 | 首个估计日 | 期末估计日 | 最低久期 | 最高久期 | 期末久期 |
|---|---:|---:|---:|---:|---:|
{% for row in rolling_summaries -%}
| {{ row.asset_name }} | {{ row.first_date }} | {{ row.last_date }} | {{ "%.4f"|format(row.minimum) }} | {{ "%.4f"|format(row.maximum) }} | {{ "%.4f"|format(row.latest) }} |
{% endfor %}

**配置含义：** 隐含久期并非常数。企债指数出现的负估计是统计敏感度，而不是现金流意义上的负久期。

## 3.8 多期限收益率 PCA 与关键期限暴露

2、5、10、30 年期国债收益率日变动的前三个主成分累计解释 **{{ "%.2f%%"|format(first_three_variance * 100) }}** 的波动。

| 资产 | 关键期限 | PCA隐含关键利率久期 | HAC标准误 |
|---|---:|---:|---:|
{% for row in key_rate_rows -%}
| {{ row.asset_name }} | {{ "%g"|format(row.tenor_years) }}年 | {{ "%.4f"|format(row.implied_key_rate_duration_years) }} | {{ "%.4f"|format(row.hac_standard_error) }} |
{% endfor %}

**配置含义：** PCA 可区分曲线整体移动、斜率和曲率变化。表中数值是前三个主成分重构的统计暴露，负值表示期限间的抵消关系。

## 3.9 五年到期资金的久期匹配

以五年零息负债的修正久期为目标，3年/10年零息债杠铃组合的市值权重为 3年 **{{ "%.2f%%"|format(barbell.weight_3y * 100) }}**、10年 **{{ "%.2f%%"|format(barbell.weight_10y * 100) }}**，其一阶久期缺口为零。

该组合相对五年负债的精确盈余变化为：{% for row in barbell_stress %}{{ "%+.0f"|format(row.yield_shock_bp) }}bp 时 {{ "%.3f%%"|format(row.surplus_return_gap * 100) }}{% if not loop.last %}；{% endif %}{% endfor %}。即使久期完全匹配，凸性差异仍会造成二阶盈余变化。

**配置含义：** 对五年后确定用途的资金，债券配置应以资产—负债久期缺口为核心，而不是只看债券权重。
