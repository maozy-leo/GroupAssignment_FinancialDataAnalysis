"""Rolling stock-bond correlation and 2024 pulse calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    ANALYSIS_START_DATE,
    BOND_PORTFOLIO_WEIGHT,
    EQUITY_PORTFOLIO_WEIGHT,
    EVENT_END_DATE,
    EVENT_START_DATE,
    MAIN_STOCK_BOND_PAIR,
    PORTFOLIO_ASSET_ID,
    PORTFOLIO_NAME,
    ROLLING_CORR_WINDOW,
    STABILITY_END_DATE,
    STABILITY_START_DATE,
    STOCK_BOND_PAIRS,
    TRADING_DAYS_PER_YEAR,
    pair_id,
    pair_label,
)

ANALYSIS_START = pd.Timestamp(ANALYSIS_START_DATE)
EVENT_COLUMNS: dict[str, str] = {
    "CSI300": "csi300_nav",
    "SSE_TREASURY": "treasury_nav",
    PORTFOLIO_ASSET_ID: "portfolio_nav",
}
EVENT_NAMES: dict[str, str] = {
    "CSI300": "沪深300",
    "SSE_TREASURY": "上证国债指数",
    PORTFOLIO_ASSET_ID: PORTFOLIO_NAME,
}


def compute_log_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """Convert close prices into daily log returns.

    Args:
        panel: Wide close-price panel.

    Returns:
        Wide log-return panel with the first observation missing per asset.
    """
    return np.log(panel).diff()


def slice_analysis_window(
    frame: pd.DataFrame,
    start: str = ANALYSIS_START_DATE,
) -> pd.DataFrame:
    """Restrict a frame to the 2019-onward analysis window.

    Args:
        frame: Date-indexed frame, possibly containing 2018 warm-up rows.
        start: Inclusive first date of the reported window.

    Returns:
        The sliced frame.
    """
    return frame.loc[frame.index >= pd.Timestamp(start)]


def rolling_correlation(
    returns: pd.DataFrame,
    asset_a: str,
    asset_b: str,
    window: int = ROLLING_CORR_WINDOW,
) -> pd.Series:
    """Compute the rolling correlation of two assets on common dates.

    Args:
        returns: Wide log-return panel.
        asset_a: Left-hand asset identifier.
        asset_b: Right-hand asset identifier.
        window: Rolling window length in trading days.

    Returns:
        Rolling correlation series indexed by trade date.
    """
    pair_returns = returns[[asset_a, asset_b]].dropna()
    correlation = pair_returns[asset_a].rolling(
        window, min_periods=window
    ).corr(pair_returns[asset_b])
    return correlation.dropna()


def compute_stock_bond_correlations(returns: pd.DataFrame) -> pd.DataFrame:
    """Compute 120-day rolling stock-bond correlations.

    Args:
        returns: Wide log-return panel.

    Returns:
        Long table of rolling correlations for the main and supplementary
        stock-bond pairs.
    """
    frames: list[pd.DataFrame] = []
    for asset_a, asset_b in STOCK_BOND_PAIRS:
        correlation = rolling_correlation(returns, asset_a, asset_b)
        correlation = correlation[correlation.index >= ANALYSIS_START]
        frames.append(
            pd.DataFrame(
                {
                    "trade_date": correlation.index,
                    "pair_id": pair_id(asset_a, asset_b),
                    "pair_label": pair_label(asset_a, asset_b),
                    "asset_a": asset_a,
                    "asset_b": asset_b,
                    "correlation": correlation.to_numpy(),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _pair_role(asset_a: str, asset_b: str) -> str:
    """Classify a pair for display: main result or supplementary."""
    return "主结果" if (asset_a, asset_b) == MAIN_STOCK_BOND_PAIR else "补充结果"


def build_correlation_summary(
    returns: pd.DataFrame,
    rolling_correlations: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize headline statistics for both stock-bond pairs.

    Args:
        returns: Wide log-return panel.
        rolling_correlations: Long rolling-correlation table.

    Returns:
        One row per pair with full-sample, end-of-sample, extreme and
        negative-share statistics.

    Raises:
        ValueError: If a configured pair has no rolling observations.
    """
    sample = slice_analysis_window(returns)
    rows: list[dict[str, object]] = []
    for asset_a, asset_b in STOCK_BOND_PAIRS:
        identifier = pair_id(asset_a, asset_b)
        subset = rolling_correlations.loc[
            rolling_correlations["pair_id"] == identifier
        ]
        if subset.empty:
            raise ValueError(f"No rolling correlation for pair '{identifier}'.")
        pair_sample = sample[[asset_a, asset_b]].dropna()
        static_correlation = float(pair_sample.corr().iloc[0, 1])
        minimum_position = subset["correlation"].idxmin()
        maximum_position = subset["correlation"].idxmax()
        rows.append(
            {
                "pair_id": identifier,
                "pair_label": pair_label(asset_a, asset_b),
                "role": _pair_role(asset_a, asset_b),
                "full_sample_correlation": static_correlation,
                "full_sample_observations": int(pair_sample.shape[0]),
                "first_rolling_date": subset["trade_date"].min(),
                "last_rolling_date": subset["trade_date"].max(),
                "latest_rolling_correlation": float(
                    subset["correlation"].iloc[-1]
                ),
                "minimum_rolling_correlation": float(
                    subset["correlation"].min()
                ),
                "minimum_date": subset.loc[minimum_position, "trade_date"],
                "maximum_rolling_correlation": float(
                    subset["correlation"].max()
                ),
                "maximum_date": subset.loc[maximum_position, "trade_date"],
                "negative_share": float((subset["correlation"] < 0).mean()),
                "rolling_observations": int(subset.shape[0]),
            }
        )
    return pd.DataFrame(rows)


def build_annual_correlations(returns: pd.DataFrame) -> pd.DataFrame:
    """Compute calendar-year stock-bond correlations.

    Args:
        returns: Wide log-return panel.

    Returns:
        One row per calendar year with the correlation of each stock-bond
        pair and the number of common observations.
    """
    sample = slice_analysis_window(returns)
    rows: list[dict[str, object]] = []
    for year in range(sample.index.min().year, sample.index.max().year + 1):
        year_sample = sample.loc[sample.index.year == year]
        row: dict[str, object] = {"year": year}
        for asset_a, asset_b in STOCK_BOND_PAIRS:
            pair_sample = year_sample[[asset_a, asset_b]].dropna()
            row[pair_id(asset_a, asset_b) + "_observations"] = int(
                pair_sample.shape[0]
            )
            row[pair_id(asset_a, asset_b) + "_correlation"] = (
                float(pair_sample.corr().iloc[0, 1])
                if pair_sample.shape[0] >= 2
                else np.nan
            )
        row["common_observations"] = int(
            year_sample[["CSI300", "SSE_TREASURY"]].dropna().shape[0]
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_stock_bond_period_summary(
    stock_bond_correlations: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize rolling stock-bond correlations inside 2022–2024.

    The window is the regime the assignment asks to test: a stable "see-saw"
    would show persistently negative rolling correlations, not merely a
    negative average.

    Args:
        stock_bond_correlations: Long 120-day stock-bond correlation table.

    Returns:
        One row per stock-bond pair with the period mean, extremes and the
        share of rolling observations that are negative.

    Raises:
        ValueError: If a pair has no rolling observation in the window.
    """
    period = stock_bond_correlations.loc[
        (
            stock_bond_correlations["trade_date"]
            >= pd.Timestamp(STABILITY_START_DATE)
        )
        & (
            stock_bond_correlations["trade_date"]
            <= pd.Timestamp(STABILITY_END_DATE)
        )
    ]
    rows: list[dict[str, object]] = []
    for asset_a, asset_b in STOCK_BOND_PAIRS:
        identifier = pair_id(asset_a, asset_b)
        subset = period.loc[period["pair_id"] == identifier]
        if subset.empty:
            raise ValueError(
                f"No rolling correlation for pair '{identifier}' in 2022–2024."
            )
        minimum_position = subset["correlation"].idxmin()
        maximum_position = subset["correlation"].idxmax()
        rows.append(
            {
                "pair_id": identifier,
                "pair_label": pair_label(asset_a, asset_b),
                "role": _pair_role(asset_a, asset_b),
                "period_start": STABILITY_START_DATE,
                "period_end": STABILITY_END_DATE,
                "rolling_observations": int(subset.shape[0]),
                "first_rolling_date": subset["trade_date"].min(),
                "last_rolling_date": subset["trade_date"].max(),
                "mean_correlation": float(subset["correlation"].mean()),
                "minimum_correlation": float(subset["correlation"].min()),
                "minimum_date": subset.loc[minimum_position, "trade_date"],
                "maximum_correlation": float(subset["correlation"].max()),
                "maximum_date": subset.loc[maximum_position, "trade_date"],
                "negative_share": float((subset["correlation"] < 0).mean()),
                "weakly_negative_share": float(
                    (
                        (subset["correlation"] < 0)
                        & (subset["correlation"] >= -0.10)
                    ).mean()
                ),
                "strongly_negative_share": float(
                    (subset["correlation"] < -0.10).mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def build_event_analysis(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Analyze the September–October 2024 equity pulse.

    The 60/40 portfolio is rebalanced into its target weights on the first
    trading day of the window and then left untouched, so its net value is
    ``0.6 * equity_nav + 0.4 * bond_nav`` with both legs rebased to one.

    Args:
        panel: Wide close-price panel.

    Returns:
        A tuple of the event statistics table, the rebased net-value path and
        the long daily-return table for the sessions inside the window.

    Raises:
        ValueError: If the event window is missing trading days.
    """
    window = panel.loc[
        (panel.index >= pd.Timestamp(EVENT_START_DATE))
        & (panel.index <= pd.Timestamp(EVENT_END_DATE)),
        ["CSI300", "SSE_TREASURY"],
    ]
    if len(window) < 2:
        raise ValueError(
            "The 2024 event window contains fewer than two trading days."
        )

    equity_nav = window["CSI300"] / window["CSI300"].iloc[0]
    bond_nav = window["SSE_TREASURY"] / window["SSE_TREASURY"].iloc[0]
    portfolio_nav = (
        EQUITY_PORTFOLIO_WEIGHT * equity_nav
        + BOND_PORTFOLIO_WEIGHT * bond_nav
    )
    paths = pd.DataFrame(
        {
            "trade_date": window.index,
            "csi300_nav": equity_nav.to_numpy(),
            "treasury_nav": bond_nav.to_numpy(),
            "portfolio_nav": portfolio_nav.to_numpy(),
        }
    )
    for column in ("csi300_nav", "treasury_nav", "portfolio_nav"):
        paths[column.replace("_nav", "_daily_return")] = paths[column].pct_change(
            fill_method=None
        )

    rows: list[dict[str, object]] = []
    for asset_id, nav_column in EVENT_COLUMNS.items():
        nav = paths[nav_column]
        daily_returns = nav.pct_change(fill_method=None).dropna()
        worst_position = daily_returns.idxmin()
        best_position = daily_returns.idxmax()
        rows.append(
            {
                "object_id": asset_id,
                "object_name": EVENT_NAMES[asset_id],
                "window_start": paths["trade_date"].iloc[0],
                "window_end": paths["trade_date"].iloc[-1],
                "trading_days": int(paths.shape[0]),
                "daily_return_count": int(daily_returns.size),
                "cumulative_return": float(nav.iloc[-1] - 1.0),
                "max_daily_gain": float(daily_returns.max()),
                "max_daily_gain_date": paths.loc[best_position, "trade_date"],
                "max_daily_loss": float(daily_returns.min()),
                "max_daily_loss_date": paths.loc[worst_position, "trade_date"],
                "daily_volatility": float(daily_returns.std(ddof=1)),
                "annualized_volatility": float(
                    daily_returns.std(ddof=1)
                    * np.sqrt(TRADING_DAYS_PER_YEAR)
                ),
                "max_drawdown": float((nav / nav.cummax() - 1.0).min()),
            }
        )

    daily_returns = paths.melt(
        id_vars=["trade_date"],
        value_vars=[
            column
            for column in paths.columns
            if column.endswith("_daily_return")
        ],
        var_name="nav_column",
        value_name="daily_return",
    ).dropna(subset=["daily_return"])
    daily_column_to_asset = {
        nav_column.replace("_nav", "_daily_return"): asset_id
        for asset_id, nav_column in EVENT_COLUMNS.items()
    }
    daily_returns["object_id"] = daily_returns["nav_column"].map(
        daily_column_to_asset
    )
    daily_returns["object_name"] = daily_returns["object_id"].map(EVENT_NAMES)
    daily_returns = (
        daily_returns[["trade_date", "object_id", "object_name", "daily_return"]]
        .sort_values(["trade_date", "object_id"])
        .reset_index(drop=True)
    )
    return pd.DataFrame(rows), paths, daily_returns
