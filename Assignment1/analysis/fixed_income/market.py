"""Historical bond regressions and rolling duration estimates."""

from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from config import (
    ANALYSIS_START_DATE,
    BOND_ASSETS,
    HAC_MAX_LAGS,
    ROLLING_REGRESSION_WINDOW,
)
from repository import FixedIncomeRepository


def run_rate_sensitivity_regressions(
    repository: FixedIncomeRepository,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Estimate one-factor OLS models with Newey–West errors.

    Args:
        repository: Read-only source for aligned observations.

    Returns:
        Per-asset samples and one-row-per-asset statistics.
    """
    regression_data: dict[str, pd.DataFrame] = {}
    result_rows: list[dict[str, object]] = []
    for asset_id, asset_name in BOND_ASSETS.items():
        sample = repository.load_regression_sample(
            asset_id,
            ANALYSIS_START_DATE,
        )
        if len(sample) <= HAC_MAX_LAGS + 2:
            raise ValueError(
                f"Regression sample for '{asset_id}' is too short: "
                f"{len(sample)} observations."
            )
        explanatory = sm.add_constant(
            sample["yield_change_10y"].astype(float),
            has_constant="add",
        )
        model = sm.OLS(
            sample["bond_log_return"].astype(float),
            explanatory,
        ).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_MAX_LAGS})
        sample["fitted_return"] = model.predict(explanatory)
        regression_data[asset_id] = sample
        result_rows.append(
            {
                "asset_id": asset_id,
                "asset_name": asset_name,
                "sample_start": sample["trade_date"].min(),
                "sample_end": sample["trade_date"].max(),
                "alpha": float(model.params["const"]),
                "alpha_hac_se": float(model.bse["const"]),
                "alpha_t_value": float(model.tvalues["const"]),
                "alpha_p_value": float(model.pvalues["const"]),
                "beta": float(model.params["yield_change_10y"]),
                "beta_hac_se": float(model.bse["yield_change_10y"]),
                "beta_t_value": float(model.tvalues["yield_change_10y"]),
                "beta_p_value": float(model.pvalues["yield_change_10y"]),
                "r_squared": float(model.rsquared),
                "n_observations": int(model.nobs),
                "implied_rate_duration_years": -float(
                    model.params["yield_change_10y"]
                ),
                "hac_max_lags": HAC_MAX_LAGS,
            }
        )
    return regression_data, pd.DataFrame(result_rows)


def calculate_rolling_rate_duration(
    regression_data: dict[str, pd.DataFrame],
    window: int = ROLLING_REGRESSION_WINDOW,
) -> pd.DataFrame:
    """Estimate rolling OLS rate duration from covariance and variance.

    Args:
        regression_data: Per-asset one-factor regression samples.
        window: Required observations in each rolling estimate.

    Returns:
        Long-form rolling alpha, beta, duration, and $R^2$ series.
    """
    if window < 3:
        raise ValueError(f"Expected 'window' >= 3, but got {window}.")
    rolling_frames: list[pd.DataFrame] = []
    for asset_id, sample in regression_data.items():
        yield_changes = sample["yield_change_10y"].astype(float)
        bond_returns = sample["bond_log_return"].astype(float)
        rolling_yield = yield_changes.rolling(window=window)
        rolling_return = bond_returns.rolling(window=window)
        beta = rolling_yield.cov(bond_returns) / rolling_yield.var()
        rolling_frames.append(
            pd.DataFrame(
                {
                    "trade_date": sample["trade_date"],
                    "asset_id": asset_id,
                    "asset_name": BOND_ASSETS[asset_id],
                    "window_observations": window,
                    "alpha": (
                        rolling_return.mean() - beta * rolling_yield.mean()
                    ),
                    "beta": beta,
                    "implied_rate_duration_years": -beta,
                    "r_squared": rolling_yield.corr(bond_returns).pow(2),
                }
            ).dropna()
        )
    return pd.concat(rolling_frames, ignore_index=True)
