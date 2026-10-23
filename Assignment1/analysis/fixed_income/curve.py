"""Yield-curve fitting, bond risk, stress, and liability calculations."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import OptimizeResult, minimize

from config import BOND_ASSETS, FACE_VALUE, NelsonSiegelFit, SCENARIOS


def nelson_siegel_yield(
    tenors: NDArray[np.float64],
    parameters: Sequence[float],
) -> NDArray[np.float64]:
    """Evaluate the Nelson–Siegel curve at positive maturities.

    Args:
        tenors: Maturities in years with shape ``[n_tenors]``.
        parameters: ``beta_0``, ``beta_1``, ``beta_2``, and positive ``tau``.

    Returns:
        Decimal annual yields with shape ``[n_tenors]``.

    Raises:
        ValueError: If tenors or parameters are invalid.
    """
    tenor_array = np.asarray(tenors, dtype=float)
    parameter_array = np.asarray(parameters, dtype=float)
    if tenor_array.ndim != 1 or np.any(tenor_array <= 0):
        raise ValueError(
            "Expected 'tenors' to be one-dimensional and positive, but got "
            f"shape {tenor_array.shape}."
        )
    if parameter_array.shape != (4,):
        raise ValueError(
            "Expected 'parameters' to have shape [4], but got "
            f"{parameter_array.shape}."
        )

    beta_0, beta_1, beta_2, tau = parameter_array
    if tau <= 0:
        raise ValueError(f"Expected positive 'tau', but got {tau}.")
    scaled_tenors = tenor_array / tau
    slope_loading = -np.expm1(-scaled_tenors) / scaled_tenors
    curvature_loading = slope_loading - np.exp(-scaled_tenors)
    return beta_0 + beta_1 * slope_loading + beta_2 * curvature_loading


def fit_nelson_siegel(curve: pd.DataFrame) -> NelsonSiegelFit:
    """Fit Nelson–Siegel parameters from five initial values.

    Args:
        curve: Eight-point curve with tenor and decimal yield columns.

    Returns:
        Best converged fit and diagnostics for every start.

    Raises:
        RuntimeError: If no optimization start converges.
    """
    tenors = curve["tenor_years"].to_numpy(dtype=float)
    observed_yields = curve["yield_decimal"].to_numpy(dtype=float)
    long_rate = float(observed_yields[-1])
    short_spread = float(observed_yields[0] - long_rate)
    initial_values = (
        (long_rate, short_spread, 0.010, 0.75),
        (long_rate, short_spread, 0.020, 1.50),
        (long_rate, short_spread, -0.010, 3.00),
        (0.025, -0.015, 0.015, 5.00),
        (0.020, -0.010, 0.000, 10.00),
    )

    def scaled_objective(parameters: NDArray[np.float64]) -> float:
        residuals = observed_yields - nelson_siegel_yield(tenors, parameters)
        return float(np.dot(residuals, residuals) * 1e8)

    bounds = ((-0.20, 0.20), (-0.20, 0.20), (-0.20, 0.20), (0.01, 100.0))
    converged_results: list[OptimizeResult] = []
    diagnostics: list[dict[str, object]] = []
    for start_id, initial_value in enumerate(initial_values, start=1):
        result = minimize(
            scaled_objective,
            x0=np.asarray(initial_value, dtype=float),
            method="L-BFGS-B",
            bounds=bounds,
            options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 20_000},
        )
        unscaled_sse = float(result.fun / 1e8)
        diagnostics.append(
            {
                "start_id": start_id,
                **{
                    f"initial_{name}": value
                    for name, value in zip(
                        ("beta_0", "beta_1", "beta_2", "tau"),
                        initial_value,
                        strict=True,
                    )
                },
                "success": bool(result.success),
                "sse": unscaled_sse,
                "beta_0": float(result.x[0]),
                "beta_1": float(result.x[1]),
                "beta_2": float(result.x[2]),
                "tau": float(result.x[3]),
                "message": str(result.message),
            }
        )
        if result.success and np.isfinite(unscaled_sse):
            converged_results.append(result)
    if not converged_results:
        raise RuntimeError("Nelson–Siegel optimization failed for every start.")

    best_result = min(converged_results, key=lambda result: float(result.fun))
    return NelsonSiegelFit(
        parameters=np.asarray(best_result.x, dtype=float),
        objective=float(best_result.fun / 1e8),
        diagnostics=pd.DataFrame(diagnostics),
    )


def build_curve_results(
    curve: pd.DataFrame,
    curve_fit: NelsonSiegelFit,
) -> pd.DataFrame:
    """Calculate fitted yields and observed-minus-fitted residuals.

    Args:
        curve: Observed curve points.
        curve_fit: Selected Nelson–Siegel fit.

    Returns:
        Curve table with fitted yields and residuals.
    """
    results = curve.copy()
    tenors = results["tenor_years"].to_numpy(dtype=float)
    results["fitted_yield_decimal"] = nelson_siegel_yield(
        tenors,
        curve_fit.parameters,
    )
    results["residual_decimal"] = (
        results["yield_decimal"] - results["fitted_yield_decimal"]
    )
    results["residual_bp"] = results["residual_decimal"] * 10_000.0
    return results


def zero_coupon_metrics(
    tenors: NDArray[np.float64],
    yields: NDArray[np.float64],
    face_value: float = FACE_VALUE,
) -> pd.DataFrame:
    """Calculate zero-coupon prices, durations, and convexities.

    Args:
        tenors: Maturities with shape ``[n_bonds]``.
        yields: Annual decimal yields with shape ``[n_bonds]``.
        face_value: Positive redemption value.

    Returns:
        One row per bond with price and risk metrics.

    Raises:
        ValueError: If shapes or numerical domains are invalid.
    """
    tenor_array = np.asarray(tenors, dtype=float)
    yield_array = np.asarray(yields, dtype=float)
    if tenor_array.ndim != 1 or yield_array.ndim != 1:
        raise ValueError("Expected one-dimensional 'tenors' and 'yields'.")
    if tenor_array.shape != yield_array.shape:
        raise ValueError(
            "Expected matching tenor and yield shapes, but got "
            f"{tenor_array.shape} and {yield_array.shape}."
        )
    if np.any(tenor_array <= 0) or np.any(1.0 + yield_array <= 0):
        raise ValueError("Expected positive tenors and yields greater than -1.")
    if face_value <= 0:
        raise ValueError(f"Expected positive 'face_value', but got {face_value}.")

    compounding_base = 1.0 + yield_array
    prices = face_value / np.power(compounding_base, tenor_array)
    modified_durations = tenor_array / compounding_base
    convexities = tenor_array * (tenor_array + 1.0) / np.square(compounding_base)
    return pd.DataFrame(
        {
            "tenor_years": tenor_array,
            "fitted_yield_decimal": yield_array,
            "price": prices,
            "macaulay_duration_years": tenor_array,
            "modified_duration_years": modified_durations,
            "convexity": convexities,
        }
    )


def build_duration_convexity(curve_fit: NelsonSiegelFit) -> pd.DataFrame:
    """Build 1-, 3-, 5-, and 10-year zero-coupon risk metrics.

    Args:
        curve_fit: Selected Nelson–Siegel fit.

    Returns:
        Price, duration, and convexity table.
    """
    tenors = np.asarray([1.0, 3.0, 5.0, 10.0])
    return zero_coupon_metrics(
        tenors,
        nelson_siegel_yield(tenors, curve_fit.parameters),
    )


def yield_shock(
    tenors: NDArray[np.float64],
    scenario_id: str,
) -> NDArray[np.float64]:
    """Return decimal yield shocks for one configured scenario.

    Args:
        tenors: Maturities with shape ``[n_bonds]``.
        scenario_id: Key in ``SCENARIOS``.

    Returns:
        Decimal yield changes with shape ``[n_bonds]``.

    Raises:
        ValueError: If the scenario or tenors are invalid.
    """
    tenor_array = np.asarray(tenors, dtype=float)
    if tenor_array.ndim != 1 or np.any(tenor_array <= 0):
        raise ValueError("Expected 'tenors' to be one-dimensional and positive.")
    parallel_shocks = {
        "parallel_down_100bp": -0.010,
        "parallel_down_50bp": -0.005,
        "parallel_50bp": 0.005,
        "parallel_100bp": 0.010,
    }
    if scenario_id in parallel_shocks:
        return np.full_like(tenor_array, parallel_shocks[scenario_id])
    if scenario_id == "steepening":
        return np.where(
            tenor_array <= 1.0,
            0.0,
            np.where(
                tenor_array >= 10.0,
                0.005,
                0.005 * (tenor_array - 1.0) / 9.0,
            ),
        )
    raise ValueError(
        f"Unknown 'scenario_id': {scenario_id!r}. Expected one of "
        f"{tuple(SCENARIOS)}."
    )


def build_stress_results(metrics: pd.DataFrame) -> pd.DataFrame:
    """Compare exact repricing with duration and convexity approximations.

    Args:
        metrics: Base zero-coupon bond metrics.

    Returns:
        Long-form results for every maturity and scenario.
    """
    records: list[dict[str, float | str]] = []
    tenors = metrics["tenor_years"].to_numpy(dtype=float)
    for scenario_id, scenario_name in SCENARIOS.items():
        for row, shock in zip(
            metrics.to_dict("records"),
            yield_shock(tenors, scenario_id),
            strict=True,
        ):
            shocked_yield = float(row["fitted_yield_decimal"] + shock)
            shocked_price = FACE_VALUE / (1.0 + shocked_yield) ** row["tenor_years"]
            exact_change = shocked_price / row["price"] - 1.0
            duration_change = -row["modified_duration_years"] * shock
            convexity_change = duration_change + 0.5 * row["convexity"] * shock**2
            records.append(
                _stress_record(
                    scenario_id,
                    scenario_name,
                    row,
                    shock,
                    shocked_yield,
                    shocked_price,
                    exact_change,
                    duration_change,
                    convexity_change,
                )
            )
    return pd.DataFrame(records)


def _stress_record(
    scenario_id: str,
    scenario_name: str,
    row: dict[str, float],
    shock: float,
    shocked_yield: float,
    shocked_price: float,
    exact_change: float,
    duration_change: float,
    convexity_change: float,
) -> dict[str, float | str]:
    """Build one stress-test output row from calculated values."""
    duration_error = abs(duration_change - exact_change)
    convexity_error = abs(convexity_change - exact_change)
    return {
        "scenario_id": scenario_id,
        "scenario": scenario_name,
        "tenor_years": row["tenor_years"],
        "base_yield_decimal": row["fitted_yield_decimal"],
        "yield_shock_decimal": shock,
        "shocked_yield_decimal": shocked_yield,
        "base_price": row["price"],
        "shocked_price": shocked_price,
        "exact_price_change_amount": shocked_price - row["price"],
        "exact_price_change": exact_change,
        "duration_price_change_amount": row["price"] * duration_change,
        "duration_price_change": duration_change,
        "duration_convexity_price_change_amount": (
            row["price"] * convexity_change
        ),
        "duration_convexity_price_change": convexity_change,
        "duration_absolute_error": duration_error,
        "duration_convexity_absolute_error": convexity_error,
        "duration_error_bp": duration_error * 10_000.0,
        "duration_convexity_error_bp": convexity_error * 10_000.0,
    }


def build_realized_2024_convexity_attribution(
    late_period: pd.DataFrame,
) -> pd.DataFrame:
    """Attribute the late-2024 ten-year constant-maturity rate return.

    Args:
        late_period: Common-date late-2024 yields and bond asset levels.

    Returns:
        Exact, duration, and duration-plus-convexity comparison.

    Notes:
        Remaining maturity stays fixed at ten years to isolate the rate effect.
    """
    tenor = 10.0
    start_yield = float(late_period["yield_10y_decimal"].iloc[0])
    end_yield = float(late_period["yield_10y_decimal"].iloc[-1])
    yield_change = end_yield - start_yield
    metrics = zero_coupon_metrics(
        np.asarray([tenor]),
        np.asarray([start_yield]),
    ).iloc[0]
    end_price = FACE_VALUE / (1.0 + end_yield) ** tenor
    exact_return = end_price / metrics["price"] - 1.0
    duration_return = -metrics["modified_duration_years"] * yield_change
    convexity_contribution = 0.5 * metrics["convexity"] * yield_change**2
    duration_convexity_return = duration_return + convexity_contribution
    record: dict[str, float | str] = {
        "period_start": str(late_period["trade_date"].iloc[0]),
        "period_end": str(late_period["trade_date"].iloc[-1]),
        "tenor_years": tenor,
        "start_yield_decimal": start_yield,
        "end_yield_decimal": end_yield,
        "yield_change_decimal": yield_change,
        "yield_change_bp": yield_change * 10_000.0,
        "start_price": metrics["price"],
        "end_price": end_price,
        "exact_rate_driven_return": exact_return,
        "duration_return": duration_return,
        "convexity_contribution": convexity_contribution,
        "duration_convexity_return": duration_convexity_return,
        "duration_absolute_error": abs(duration_return - exact_return),
        "duration_convexity_absolute_error": abs(
            duration_convexity_return - exact_return
        ),
    }
    for asset_id, asset_name in BOND_ASSETS.items():
        record[f"observed_return_{asset_id}"] = float(
            late_period[f"{asset_id}_cumulative_return"].iloc[-1]
        )
        record[f"observed_asset_name_{asset_id}"] = asset_name
    return pd.DataFrame([record])


def build_liability_matching_analysis(
    metrics: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare zero-coupon strategies against a five-year liability.

    Args:
        metrics: Current 1-, 3-, 5-, and 10-year zero-coupon metrics.

    Returns:
        Strategy metrics and ±100bp asset-minus-liability stress results.
    """
    indexed = metrics.set_index("tenor_years")
    liability = indexed.loc[5.0]
    target_duration = float(liability["modified_duration_years"])
    duration_3y = float(indexed.loc[3.0, "modified_duration_years"])
    duration_10y = float(indexed.loc[10.0, "modified_duration_years"])
    weight_3y = (duration_10y - target_duration) / (
        duration_10y - duration_3y
    )
    weight_10y = 1.0 - weight_3y
    if not 0.0 <= weight_3y <= 1.0:
        raise ValueError("Calculated 3Y/10Y barbell weights are infeasible.")

    strategies = [
        _single_bond_strategy(indexed, tenor)
        for tenor in (1.0, 3.0, 5.0, 10.0)
    ]
    strategies.append(
        {
            "strategy_id": "barbell_3y_10y",
            "strategy_name": "3年/10年零息债久期匹配组合",
            "weight_1y": 0.0,
            "weight_3y": weight_3y,
            "weight_5y": 0.0,
            "weight_10y": weight_10y,
            "modified_duration_years": target_duration,
            "duration_gap_years": 0.0,
            "convexity": float(
                weight_3y * indexed.loc[3.0, "convexity"]
                + weight_10y * indexed.loc[10.0, "convexity"]
            ),
        }
    )
    strategy_table = pd.DataFrame(strategies)
    return strategy_table, _liability_stress(strategy_table, indexed, liability)


def _single_bond_strategy(
    indexed: pd.DataFrame,
    tenor: float,
) -> dict[str, float | str]:
    """Build one single-tenor liability-matching strategy row."""
    row = indexed.loc[tenor]
    target_duration = indexed.loc[5.0, "modified_duration_years"]
    return {
        "strategy_id": f"single_{tenor:g}y",
        "strategy_name": f"{tenor:g}年零息债",
        **{
            f"weight_{candidate:g}y": float(tenor == candidate)
            for candidate in (1.0, 3.0, 5.0, 10.0)
        },
        "modified_duration_years": float(row["modified_duration_years"]),
        "duration_gap_years": float(
            row["modified_duration_years"] - target_duration
        ),
        "convexity": float(row["convexity"]),
    }


def _liability_stress(
    strategies: pd.DataFrame,
    indexed: pd.DataFrame,
    liability: pd.Series,
) -> pd.DataFrame:
    """Calculate exact asset-minus-liability returns under ±100bp shocks."""
    records: list[dict[str, float | str]] = []
    for shock in (-0.010, 0.010):
        liability_return = _exact_zero_coupon_return(liability, shock)
        for strategy in strategies.to_dict("records"):
            asset_return = sum(
                strategy[f"weight_{tenor:g}y"]
                * _exact_zero_coupon_return(indexed.loc[tenor], shock)
                for tenor in (1.0, 3.0, 5.0, 10.0)
            )
            records.append(
                {
                    "strategy_id": strategy["strategy_id"],
                    "strategy_name": strategy["strategy_name"],
                    "yield_shock_decimal": shock,
                    "yield_shock_bp": shock * 10_000.0,
                    "asset_return": asset_return,
                    "liability_return": liability_return,
                    "surplus_return_gap": asset_return - liability_return,
                }
            )
    return pd.DataFrame(records)


def _exact_zero_coupon_return(metrics: pd.Series, shock: float) -> float:
    """Return exact zero-coupon price change after a yield shock."""
    shocked_price = FACE_VALUE / (
        1.0 + metrics["fitted_yield_decimal"] + shock
    ) ** metrics.name
    return float(shocked_price / metrics["price"] - 1.0)
