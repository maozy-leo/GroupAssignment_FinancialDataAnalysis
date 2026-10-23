"""Historical bond regressions, rolling duration, and yield-curve PCA."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from numpy.typing import NDArray

from config import (
    ANALYSIS_START_DATE,
    BOND_ASSETS,
    HAC_MAX_LAGS,
    ROLLING_REGRESSION_WINDOW,
    YIELD_TENORS,
    YieldPcaResults,
)
from repository import FixedIncomeRepository


FACTOR_NAMES = ("level", "slope", "curvature")
YIELD_CHANGE_COLUMNS = (
    "yield_change_2y",
    "yield_change_5y",
    "yield_change_10y",
    "yield_change_30y",
)


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


def run_yield_pca(repository: FixedIncomeRepository) -> YieldPcaResults:
    """Fit three yield-curve PCs and bond factor regressions.

    Args:
        repository: Read-only source for yields and bond returns.

    Returns:
        PCA factors, diagnostics, regressions, and key-rate sensitivities.
    """
    yield_panel = repository.load_yield_change_panel(ANALYSIS_START_DATE)
    yield_matrix = yield_panel[list(YIELD_CHANGE_COLUMNS)].to_numpy(dtype=float)
    centered_yields = yield_matrix - yield_matrix.mean(axis=0)
    _, singular_values, right_vectors = np.linalg.svd(
        centered_yields,
        full_matrices=False,
    )
    components = _orient_pca_components(right_vectors[:3].copy())
    scores = pd.DataFrame(
        centered_yields @ components.T,
        columns=[f"pc_{factor}" for factor in FACTOR_NAMES],
    )
    scores.insert(0, "trade_date", yield_panel["trade_date"].to_numpy())
    explained_ratios = np.square(singular_values) / np.square(
        singular_values
    ).sum()
    explained_variance = pd.DataFrame(
        {
            "component": [f"PC{index}" for index in range(1, 5)],
            "factor_name": [*FACTOR_NAMES, "residual"],
            "explained_variance_ratio": explained_ratios,
            "cumulative_explained_variance_ratio": np.cumsum(
                explained_ratios
            ),
        }
    )
    loadings = pd.DataFrame(
        {
            "tenor_years": YIELD_TENORS,
            **{
                f"pc_{factor}_loading": components[index]
                for index, factor in enumerate(FACTOR_NAMES)
            },
        }
    )
    regressions, key_rate_durations = _run_pca_regressions(
        repository,
        scores,
        components,
    )
    return YieldPcaResults(
        scores=scores,
        explained_variance=explained_variance,
        loadings=loadings,
        regressions=regressions,
        key_rate_durations=key_rate_durations,
    )


def _orient_pca_components(
    components: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Orient PCA loadings as level, slope, and curvature factors."""
    if components.shape != (3, 4):
        raise ValueError(
            "Expected 'components' to have shape [3, 4], but got "
            f"{components.shape}."
        )
    if components[0].sum() < 0:
        components[0] *= -1
    if components[1, -1] - components[1, 0] < 0:
        components[1] *= -1
    if components[2, 1:3].mean() - components[2, [0, 3]].mean() < 0:
        components[2] *= -1
    return components


def _run_pca_regressions(
    repository: FixedIncomeRepository,
    scores: pd.DataFrame,
    components: NDArray[np.float64],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Estimate PCA models and transform betas to key-rate exposures."""
    factor_columns = [f"pc_{factor}" for factor in FACTOR_NAMES]
    regression_rows: list[dict[str, object]] = []
    key_rate_rows: list[dict[str, object]] = []
    for asset_id, asset_name in BOND_ASSETS.items():
        returns = repository.load_bond_returns(asset_id, ANALYSIS_START_DATE)
        sample = returns.merge(scores, on="trade_date", how="inner")
        explanatory = sm.add_constant(sample[factor_columns], has_constant="add")
        model = sm.OLS(sample["bond_log_return"], explanatory).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": HAC_MAX_LAGS},
        )
        regression_rows.append(
            _pca_regression_record(asset_id, asset_name, sample, model)
        )
        factor_betas = model.params[factor_columns].to_numpy(dtype=float)
        factor_covariance = model.cov_params().loc[
            factor_columns,
            factor_columns,
        ].to_numpy(dtype=float)
        coefficients = components.T @ factor_betas
        standard_errors = np.sqrt(
            np.diag(components.T @ factor_covariance @ components)
        )
        for tenor, coefficient, standard_error in zip(
            YIELD_TENORS,
            coefficients,
            standard_errors,
            strict=True,
        ):
            key_rate_rows.append(
                {
                    "asset_id": asset_id,
                    "asset_name": asset_name,
                    "tenor_years": tenor,
                    "return_sensitivity": float(coefficient),
                    "hac_standard_error": float(standard_error),
                    "implied_key_rate_duration_years": -float(coefficient),
                }
            )
    return pd.DataFrame(regression_rows), pd.DataFrame(key_rate_rows)


def _pca_regression_record(
    asset_id: str,
    asset_name: str,
    sample: pd.DataFrame,
    model: object,
) -> dict[str, object]:
    """Build one PCA factor-regression output row."""
    record: dict[str, object] = {
        "asset_id": asset_id,
        "asset_name": asset_name,
        "sample_start": sample["trade_date"].min(),
        "sample_end": sample["trade_date"].max(),
        "alpha": float(model.params["const"]),
        "r_squared": float(model.rsquared),
        "n_observations": int(model.nobs),
        "hac_max_lags": HAC_MAX_LAGS,
    }
    for factor in FACTOR_NAMES:
        column = f"pc_{factor}"
        record[f"beta_{factor}"] = float(model.params[column])
        record[f"hac_se_{factor}"] = float(model.bse[column])
        record[f"p_value_{factor}"] = float(model.pvalues[column])
    return record
