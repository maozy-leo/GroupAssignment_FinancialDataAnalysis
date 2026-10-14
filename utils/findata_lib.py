"""Unified online financial-data access for the group assignment.

The module only returns observations obtained from real online data sources.
It deliberately does not read a local fallback database and never generates
simulated market data. When every source for a dataset fails, the public
function raises :class:`DataSourceError` with the underlying failure details.

Source priority:

* indices and A-shares: Baostock, then AkShare;
* ETF prices: Tencent K-line, then AkShare;
* ETF NAV, rates and yield curves: AkShare;
* bond indices: Tencent K-line;
* convertible-bond reference data: AkShare;
* option quotes: Sina Finance.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

import numpy as np
import pandas as pd
import requests
from dateutil.relativedelta import relativedelta


DEFAULT_TIMEOUT_SECONDS = 10
MIN_YIELD_CURVE_POINTS = 5
TENCENT_MAX_BARS_PER_REQUEST = 2_000
TENCENT_CHUNK_YEARS = 4

TENCENT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    ),
}
SINA_OPTION_HEADERS = {
    "Referer": "https://stock.finance.sina.com.cn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    ),
}


class DataSourceError(RuntimeError):
    """Indicate that no real online source returned usable observations."""


def _normalize_date(value: str | date | pd.Timestamp, with_dash: bool = True) -> str:
    """Normalize a date to the format required by an upstream API.

    Args:
        value: Date-like value accepted by ``pandas.Timestamp``.
        with_dash: Whether to return ``YYYY-MM-DD`` instead of ``YYYYMMDD``.

    Returns:
        Normalized date string.

    Raises:
        ValueError: If ``value`` cannot be parsed as a date.
    """
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid date value: {value!r}.") from exc

    date_format = "%Y-%m-%d" if with_dash else "%Y%m%d"
    return timestamp.strftime(date_format)


def _validate_date_range(
    start: str | date | pd.Timestamp,
    end: str | date | pd.Timestamp | None,
) -> tuple[str, str]:
    """Validate and normalize a closed date interval.

    Args:
        start: Inclusive interval start.
        end: Inclusive interval end. ``None`` means today.

    Returns:
        Pair of dates in ``YYYY-MM-DD`` format.

    Raises:
        ValueError: If the start is later than the end.
    """
    normalized_start = _normalize_date(start)
    normalized_end = _normalize_date(end or pd.Timestamp.today())
    if normalized_start > normalized_end:
        raise ValueError(
            f"Expected 'start' <= 'end', but got {normalized_start} > "
            f"{normalized_end}."
        )
    return normalized_start, normalized_end


def _to_baostock_code(symbol: str) -> str:
    """Convert a security symbol to Baostock notation.

    Args:
        symbol: Symbol such as ``sh000300``, ``600519`` or ``sz.399006``.

    Returns:
        Symbol in ``sh.000300`` or ``sz.399006`` notation.

    Raises:
        ValueError: If ``symbol`` is empty.
    """
    normalized_symbol = str(symbol).strip().lower()
    if not normalized_symbol:
        raise ValueError("Expected non-empty 'symbol'.")
    if "." in normalized_symbol:
        return normalized_symbol
    if normalized_symbol.startswith(("sh", "sz")):
        return f"{normalized_symbol[:2]}.{normalized_symbol[2:]}"
    exchange = "sh" if normalized_symbol.startswith("6") else "sz"
    return f"{exchange}.{normalized_symbol}"


def _to_tencent_code(code: str) -> str:
    """Convert a security code to Tencent notation.

    Args:
        code: Code such as ``510300``, ``sh510300`` or ``sz.159915``.

    Returns:
        Code in ``sh510300`` or ``sz159915`` notation.

    Raises:
        ValueError: If ``code`` is empty.
    """
    normalized_code = str(code).replace(".", "").strip().lower()
    if not normalized_code:
        raise ValueError("Expected non-empty 'code'.")
    if normalized_code.startswith(("sh", "sz")):
        return normalized_code
    exchange = "sh" if normalized_code.startswith(("5", "6", "9")) else "sz"
    return f"{exchange}{normalized_code}"


def _read_baostock_result(result: Any) -> pd.DataFrame:
    """Convert a Baostock cursor to a DataFrame without deprecated APIs.

    Args:
        result: Cursor returned by ``query_history_k_data_plus``.

    Returns:
        Query rows with the cursor's declared fields.

    Raises:
        DataSourceError: If the cursor is missing or reports an error.
    """
    if result is None:
        raise DataSourceError("Baostock returned no query cursor.")
    if result.error_code != "0":
        raise DataSourceError(
            f"Baostock query failed: {result.error_code} {result.error_msg}."
        )

    rows: list[list[str]] = []
    while result.next():
        rows.append(result.get_row_data())
    return pd.DataFrame(rows, columns=result.fields)


def _format_source_failures(dataset: str, failures: Sequence[str]) -> DataSourceError:
    """Build a consistent exception for exhausted online data sources.

    Args:
        dataset: Human-readable dataset name.
        failures: Per-source failure summaries.

    Returns:
        Exception containing every attempted source and failure reason.
    """
    details = "; ".join(failures) if failures else "no source returned data"
    return DataSourceError(f"Unable to fetch real {dataset} data. {details}")


def _tencent_kline(
    code: str,
    start: str | date | pd.Timestamp,
    end: str | date | pd.Timestamp | None = None,
    bar_count: int = TENCENT_MAX_BARS_PER_REQUEST,
    adjustment: str = "qfq",
) -> pd.DataFrame:
    """Download Tencent daily K-line observations.

    Args:
        code: Security code in Tencent notation.
        start: Inclusive start date.
        end: Inclusive end date. ``None`` means today.
        bar_count: Maximum daily observations requested in each date chunk.
        adjustment: Tencent adjustment flag, normally ``qfq``.

    Returns:
        Daily OHLCV data indexed by date.

    Raises:
        ValueError: If ``bar_count`` is not positive.
        DataSourceError: If Tencent returns no usable observations.
    """
    if not 0 < bar_count <= TENCENT_MAX_BARS_PER_REQUEST:
        raise ValueError(
            f"Expected 'bar_count' to be in [1, "
            f"{TENCENT_MAX_BARS_PER_REQUEST}], but got {bar_count}."
        )

    start_date, end_date = _validate_date_range(start, end)
    normalized_code = _to_tencent_code(code)
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    columns = ["date", "open", "close", "high", "low", "volume"]
    chunk_start = pd.Timestamp(start_date)
    final_date = pd.Timestamp(end_date)
    chunks: list[pd.DataFrame] = []

    # Tencent rejects very large bar counts. Four-year chunks stay safely below
    # 2,000 trading days while preserving long histories without truncation.
    while chunk_start <= final_date:
        chunk_end = min(
            chunk_start + pd.DateOffset(years=TENCENT_CHUNK_YEARS)
            - pd.Timedelta(days=1),
            final_date,
        )
        params = {
            "param": (
                f"{normalized_code},day,{chunk_start:%Y-%m-%d},"
                f"{chunk_end:%Y-%m-%d},{bar_count},{adjustment}"
            ),
        }
        response = requests.get(
            url,
            params=params,
            headers=TENCENT_HEADERS,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        response_data = response.json().get("data")
        if not isinstance(response_data, dict):
            raise DataSourceError(
                f"Tencent returned an invalid payload for {normalized_code}."
            )
        payload = response_data.get(normalized_code, {})
        raw_rows = payload.get(f"{adjustment}day") or payload.get("day")
        if raw_rows:
            chunks.append(pd.DataFrame(raw_rows, columns=columns))
        chunk_start = chunk_end + pd.Timedelta(days=1)

    if not chunks:
        raise DataSourceError(f"Tencent returned no K-line rows for {normalized_code}.")

    frame = pd.concat(chunks, ignore_index=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in columns[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["date", "close"])
    frame = frame.drop_duplicates(subset=["date"], keep="last")
    frame = frame.set_index("date").sort_index()
    frame = frame.loc[start_date:end_date]
    if frame.empty:
        raise DataSourceError(
            f"Tencent returned no usable K-line rows for {normalized_code}."
        )
    return frame


def _sina_option_months(underlying: str) -> list[str]:
    """Return listed option expiry months for an ETF underlying.

    Args:
        underlying: ETF code, for example ``510050``.

    Returns:
        Unique expiry months in ``YYYYMM`` format.

    Raises:
        DataSourceError: If Sina returns no expiry month.
    """
    url = (
        "https://stock.finance.sina.com.cn/futures/api/openapi.php/"
        "StockOptionService.getStockName"
    )
    response = requests.get(
        url,
        params={"underlying": underlying},
        headers=SINA_OPTION_HEADERS,
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    raw_months = response.json()["result"]["data"]["contractMonth"]
    months = list(dict.fromkeys(str(value).replace("-", "") for value in raw_months))
    if not months:
        raise DataSourceError(f"Sina returned no option months for {underlying}.")
    return months


def _sina_option_codes(underlying: str, month: str) -> list[str]:
    """Return call and put contract codes for one expiry month.

    Args:
        underlying: ETF code, for example ``510050``.
        month: Expiry month in ``YYYYMM`` format.

    Returns:
        Unique Sina option contract codes.

    Raises:
        DataSourceError: If Sina returns no contract code.
    """
    contract_codes: list[str] = []
    for direction in ("UP", "DOWN"):
        url = (
            "https://hq.sinajs.cn/list="
            f"OP_{direction}_{underlying}{str(month)[-4:]}"
        )
        response = requests.get(
            url,
            headers=SINA_OPTION_HEADERS,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response.encoding = "gbk"
        for token in response.text.replace('"', ",").split(","):
            if token.startswith("CON_OP_"):
                contract_codes.append(token[7:])

    unique_codes = list(dict.fromkeys(contract_codes))
    if not unique_codes:
        raise DataSourceError(
            f"Sina returned no option contracts for {underlying} {month}."
        )
    return unique_codes


def _sina_option_batch(contract_codes: Sequence[str]) -> pd.DataFrame:
    """Download real-time quotes for Sina option contracts.

    Args:
        contract_codes: Sina option contract codes.

    Returns:
        Quote table containing code, name, type, strike, price, volume,
        open interest, return and expiry date.

    Raises:
        DataSourceError: If no quote can be parsed.
    """
    rows: list[dict[str, str | float]] = []
    for offset in range(0, len(contract_codes), 30):
        batch_codes = contract_codes[offset:offset + 30]
        query_codes = ",".join(f"CON_OP_{code}" for code in batch_codes)
        response = requests.get(
            f"https://hq.sinajs.cn/list={query_codes}",
            headers=SINA_OPTION_HEADERS,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response.encoding = "gbk"

        for line in response.text.strip().splitlines():
            try:
                contract_code = line.split("=")[0].split("CON_OP_")[-1]
                values = line[line.find('"') + 1:line.rfind('"')].split(",")
                if len(values) < 47:
                    continue
                contract_name = values[37]
                rows.append(
                    {
                        "期权代码": contract_code,
                        "合约名称": contract_name,
                        "类型": "购" if "购" in contract_name else "沽",
                        "行权价": float(values[7]),
                        "最新价": float(values[2]),
                        "成交量": float(values[41]),
                        "持仓量": float(values[5]),
                        "涨幅": float(values[6]),
                        "到期日": values[46],
                    }
                )
            except (IndexError, ValueError):
                continue

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise DataSourceError("Sina returned no parseable option quotes.")
    return frame


def get_index_close(
    symbol: str = "sh000001",
    start: str = "2015-01-01",
    end: str | None = None,
) -> pd.Series:
    """Download daily index closing values from real online sources.

    Args:
        symbol: Index code, such as ``sh000300`` or ``sz399006``.
        start: Inclusive start date.
        end: Inclusive end date. ``None`` means today.

    Returns:
        Float64 closing-value series indexed by trading date.

    Raises:
        DataSourceError: If Baostock and AkShare both fail.
        ValueError: If the date interval is invalid.
    """
    start_date, end_date = _validate_date_range(start, end)
    baostock_code = _to_baostock_code(symbol)
    failures: list[str] = []

    try:
        import baostock as bs

        login_result = bs.login()
        if login_result.error_code != "0":
            raise DataSourceError(
                f"login failed: {login_result.error_code} "
                f"{login_result.error_msg}"
            )
        try:
            result = bs.query_history_k_data_plus(
                baostock_code,
                "date,close",
                start_date=start_date,
                end_date=min(end_date, date.today().isoformat()),
                frequency="d",
            )
            frame = _read_baostock_result(result)
        finally:
            bs.logout()

        series = pd.Series(
            pd.to_numeric(frame["close"], errors="coerce").to_numpy(),
            index=pd.to_datetime(frame["date"], errors="coerce"),
            name="close",
            dtype="float64",
        ).dropna()
        if not series.empty:
            return series.sort_index()
        raise DataSourceError("Baostock returned no usable closing values.")
    except Exception as exc:
        failures.append(f"Baostock: {type(exc).__name__}: {exc}")

    try:
        import akshare as ak

        frame = ak.stock_zh_index_daily(symbol=symbol)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        series = frame.dropna(subset=["date", "close"]).set_index("date")["close"]
        series = series.sort_index().loc[start_date:end_date].rename("close")
        if not series.empty:
            return series.astype("float64")
        raise DataSourceError("AkShare returned no usable closing values.")
    except Exception as exc:
        failures.append(f"AkShare: {type(exc).__name__}: {exc}")

    raise _format_source_failures(f"index {symbol}", failures)


def get_stock_close(
    code: str = "600036",
    start: str = "2016-01-01",
    end: str | None = None,
) -> pd.Series:
    """Download daily forward-adjusted A-share closing prices.

    Args:
        code: Six-digit A-share code.
        start: Inclusive start date.
        end: Inclusive end date. ``None`` means today.

    Returns:
        Float64 forward-adjusted closing-price series indexed by trading date.

    Raises:
        DataSourceError: If Baostock and AkShare both fail.
        ValueError: If the date interval is invalid.
    """
    start_date, end_date = _validate_date_range(start, end)
    baostock_code = _to_baostock_code(code)
    failures: list[str] = []

    try:
        import baostock as bs

        login_result = bs.login()
        if login_result.error_code != "0":
            raise DataSourceError(
                f"login failed: {login_result.error_code} "
                f"{login_result.error_msg}"
            )
        try:
            result = bs.query_history_k_data_plus(
                baostock_code,
                "date,close",
                start_date=start_date,
                end_date=min(end_date, date.today().isoformat()),
                frequency="d",
                adjustflag="2",
            )
            frame = _read_baostock_result(result)
        finally:
            bs.logout()

        series = pd.Series(
            pd.to_numeric(frame["close"], errors="coerce").to_numpy(),
            index=pd.to_datetime(frame["date"], errors="coerce"),
            name="close",
            dtype="float64",
        ).dropna()
        if not series.empty:
            return series.sort_index()
        raise DataSourceError("Baostock returned no usable adjusted prices.")
    except Exception as exc:
        failures.append(f"Baostock: {type(exc).__name__}: {exc}")

    try:
        import akshare as ak

        frame = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=_normalize_date(start_date, with_dash=False),
            end_date=_normalize_date(end_date, with_dash=False),
            adjust="qfq",
        )
        series = pd.Series(
            pd.to_numeric(frame["收盘"], errors="coerce").to_numpy(),
            index=pd.to_datetime(frame["日期"], errors="coerce"),
            name="close",
            dtype="float64",
        ).dropna()
        if not series.empty:
            return series.sort_index()
        raise DataSourceError("AkShare returned no usable adjusted prices.")
    except Exception as exc:
        failures.append(f"AkShare: {type(exc).__name__}: {exc}")

    raise _format_source_failures(f"A-share {code}", failures)


def get_stock_panel(
    codes: Sequence[str],
    start: str = "2018-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Download an aligned panel of forward-adjusted A-share prices.

    Args:
        codes: Non-empty sequence of six-digit A-share codes.
        start: Inclusive start date.
        end: Inclusive end date. ``None`` means today.

    Returns:
        Price panel with shape ``[trading_dates, stocks]``. Missing observations
        remain missing and are not silently forward-filled.

    Raises:
        ValueError: If ``codes`` is empty or contains duplicates.
        DataSourceError: If any requested stock cannot be downloaded.
    """
    normalized_codes = [str(code).strip() for code in codes]
    if not normalized_codes or any(not code for code in normalized_codes):
        raise ValueError("Expected 'codes' to contain at least one non-empty code.")
    if len(set(normalized_codes)) != len(normalized_codes):
        raise ValueError("Expected 'codes' to contain no duplicates.")

    prices = {
        code: get_stock_close(code=code, start=start, end=end)
        for code in normalized_codes
    }
    panel = pd.concat(prices, axis="columns").sort_index()
    panel.columns = normalized_codes
    return panel.astype("float64")


def get_pair(
    code_y: str = "601318",
    code_x: str = "600036",
    start: str = "2018-01-01",
    end: str | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Download two aligned forward-adjusted A-share price series.

    Args:
        code_y: First A-share code.
        code_x: Second A-share code.
        start: Inclusive start date.
        end: Inclusive end date. ``None`` means today.

    Returns:
        Pair of price series sharing the panel's date index.
    """
    panel = get_stock_panel([code_y, code_x], start=start, end=end)
    return panel[code_y], panel[code_x]


def get_etf_price(
    code_etf: str = "510300",
    start: str = "20240101",
    end: str | None = None,
) -> pd.Series:
    """Download daily forward-adjusted ETF closing prices.

    Args:
        code_etf: Six-digit ETF code.
        start: Inclusive start date.
        end: Inclusive end date. ``None`` means today.

    Returns:
        Float64 closing-price series indexed by trading date.

    Raises:
        DataSourceError: If Tencent and AkShare both fail.
    """
    start_date, end_date = _validate_date_range(start, end)
    failures: list[str] = []

    try:
        frame = _tencent_kline(code_etf, start_date, end_date)
        return frame["close"].astype("float64").rename("close")
    except Exception as exc:
        failures.append(f"Tencent: {type(exc).__name__}: {exc}")

    try:
        import akshare as ak

        frame = ak.fund_etf_hist_em(
            symbol=code_etf,
            period="daily",
            start_date=_normalize_date(start_date, with_dash=False),
            end_date=_normalize_date(end_date, with_dash=False),
            adjust="qfq",
        )
        series = pd.Series(
            pd.to_numeric(frame["收盘"], errors="coerce").to_numpy(),
            index=pd.to_datetime(frame["日期"], errors="coerce"),
            name="close",
            dtype="float64",
        ).dropna()
        if not series.empty:
            return series.sort_index()
        raise DataSourceError("AkShare returned no usable ETF prices.")
    except Exception as exc:
        failures.append(f"AkShare: {type(exc).__name__}: {exc}")

    raise _format_source_failures(f"ETF {code_etf}", failures)


def get_etf_nav(
    code_etf: str = "510300",
    start: str = "20240101",
    end: str | None = None,
) -> pd.Series:
    """Download daily ETF unit NAV observations from AkShare.

    Args:
        code_etf: Six-digit ETF code.
        start: Inclusive start date.
        end: Inclusive end date. ``None`` means today.

    Returns:
        Float64 NAV series indexed by valuation date.

    Raises:
        DataSourceError: If AkShare returns no usable NAV observations.
    """
    start_date, end_date = _validate_date_range(start, end)
    try:
        import akshare as ak

        frame = ak.fund_etf_fund_info_em(
            fund=code_etf,
            start_date=_normalize_date(start_date, with_dash=False),
            end_date=_normalize_date(end_date, with_dash=False),
        )
        series = pd.Series(
            pd.to_numeric(frame["单位净值"], errors="coerce").to_numpy(),
            index=pd.to_datetime(frame["净值日期"], errors="coerce"),
            name="nav",
            dtype="float64",
        ).dropna()
        if not series.empty:
            return series.sort_index()
    except Exception as exc:
        raise _format_source_failures(
            f"ETF NAV {code_etf}",
            [f"AkShare: {type(exc).__name__}: {exc}"],
        ) from exc

    raise _format_source_failures(
        f"ETF NAV {code_etf}",
        ["AkShare returned no usable NAV observations"],
    )


def get_bond_rates(start: str = "20240101") -> pd.DataFrame:
    """Download Chinese and US government-bond yield history.

    Args:
        start: Inclusive start date.

    Returns:
        Chronological yield table returned by AkShare. Yields retain the
        upstream percentage unit.

    Raises:
        DataSourceError: If AkShare returns no usable observations.
    """
    normalized_start = _normalize_date(start, with_dash=False)
    try:
        import akshare as ak

        frame = ak.bond_zh_us_rate(start_date=normalized_start).copy()
        frame["日期"] = pd.to_datetime(frame["日期"], errors="coerce")
        frame = (
            frame.dropna(subset=["日期"])
            .sort_values("日期")
            .reset_index(drop=True)
        )
        if not frame.empty:
            return frame
    except Exception as exc:
        raise _format_source_failures(
            "government-bond yields",
            [f"AkShare: {type(exc).__name__}: {exc}"],
        ) from exc

    raise _format_source_failures(
        "government-bond yields",
        ["AkShare returned no usable observations"],
    )


def get_bond_index_close(
    symbol: str = "sh000012",
    start: str = "20240101",
    end: str | None = None,
) -> pd.Series:
    """Download daily exchange bond-index closing values from Tencent.

    Args:
        symbol: Bond-index code, for example ``sh000012`` or ``sh000139``.
        start: Inclusive start date.
        end: Inclusive end date. ``None`` means today.

    Returns:
        Float64 closing-value series indexed by trading date.

    Raises:
        DataSourceError: If Tencent returns no usable observations.
    """
    try:
        frame = _tencent_kline(symbol, start, end)
        return frame["close"].astype("float64").rename("close")
    except Exception as exc:
        raise _format_source_failures(
            f"bond index {symbol}",
            [f"Tencent: {type(exc).__name__}: {exc}"],
        ) from exc


def get_china_yield_curve() -> tuple[np.ndarray, np.ndarray]:
    """Download the latest ChinaBond government yield-curve cross-section.

    Returns:
        Pair ``(maturities, yields)``. ``maturities`` has shape ``[T]`` and is
        measured in years. ``yields`` has shape ``[T]`` and is expressed as a
        decimal rather than a percentage.

    Raises:
        DataSourceError: If AkShare returns fewer than five valid tenors.
    """
    tenor_map = {
        "3月": 0.25,
        "0.25年": 0.25,
        "6月": 0.5,
        "0.5年": 0.5,
        "1年": 1.0,
        "2年": 2.0,
        "3年": 3.0,
        "5年": 5.0,
        "7年": 7.0,
        "10年": 10.0,
        "15年": 15.0,
        "20年": 20.0,
        "30年": 30.0,
    }
    end_date = date.today()
    start_date = end_date - relativedelta(days=10)

    try:
        import akshare as ak

        frame = ak.bond_china_yield(
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
        government_curve = frame.loc[
            frame["曲线名称"] == "中债国债收益率曲线"
        ].sort_values("日期")
        if government_curve.empty:
            raise DataSourceError("No government yield-curve row was returned.")

        latest = government_curve.iloc[-1]
        points = [
            (tenor_years, float(latest[column]) / 100)
            for column, tenor_years in tenor_map.items()
            if column in latest.index and pd.notna(latest[column])
        ]
        points = sorted(set(points))
        if len(points) < MIN_YIELD_CURVE_POINTS:
            raise DataSourceError(
                f"Expected at least {MIN_YIELD_CURVE_POINTS} valid tenors, "
                f"but got {len(points)}."
            )
        maturities, yields = zip(*points, strict=True)
        return np.asarray(maturities, dtype=float), np.asarray(yields, dtype=float)
    except Exception as exc:
        raise _format_source_failures(
            "China government yield curve",
            [f"AkShare: {type(exc).__name__}: {exc}"],
        ) from exc


def get_convertible_bonds() -> pd.DataFrame:
    """Download the current convertible-bond reference table from AkShare.

    Returns:
        Non-empty convertible-bond reference table using upstream columns.

    Raises:
        DataSourceError: If AkShare returns no usable records.
    """
    try:
        import akshare as ak

        frame = ak.bond_zh_cov_info().copy()
        if not frame.empty:
            return frame
    except Exception as exc:
        raise _format_source_failures(
            "convertible-bond reference",
            [f"AkShare: {type(exc).__name__}: {exc}"],
        ) from exc

    raise _format_source_failures(
        "convertible-bond reference",
        ["AkShare returned no usable records"],
    )


def get_option_board(
    underlying: str = "510050",
    month: str | None = None,
) -> pd.DataFrame:
    """Download a real-time Sina option quote board.

    Args:
        underlying: ETF underlying code.
        month: Expiry month in ``YYYYMM`` format. ``None`` selects the nearest
            listed month.

    Returns:
        Quote table sorted by strike and option type.

    Raises:
        ValueError: If the requested month is not listed.
        DataSourceError: If Sina returns no usable quotes.
    """
    try:
        listed_months = _sina_option_months(underlying)
        selected_month = month or listed_months[0]
        if selected_month not in listed_months:
            raise ValueError(
                f"Expected 'month' to be one of {listed_months}, "
                f"but got {selected_month!r}."
            )
        contract_codes = _sina_option_codes(underlying, selected_month)
        frame = _sina_option_batch(contract_codes)
        return frame.sort_values(["行权价", "类型"]).reset_index(drop=True)
    except ValueError:
        raise
    except Exception as exc:
        raise _format_source_failures(
            f"option board {underlying}",
            [f"Sina: {type(exc).__name__}: {exc}"],
        ) from exc


def get_option_daily(code: str = "10011255") -> pd.DataFrame:
    """Aggregate Sina five-day option minute data into daily OHLCV bars.

    Args:
        code: Sina option contract code.

    Returns:
        Daily table with date, open, high, low, close and volume columns.

    Raises:
        DataSourceError: If Sina returns no usable minute observations.
    """
    url = (
        "https://stock.finance.sina.com.cn/futures/api/openapi.php/"
        "StockOptionDaylineService.getFiveDayLine"
    )
    try:
        response = requests.get(
            url,
            params={"symbol": f"CON_OP_{code}"},
            headers=SINA_OPTION_HEADERS,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        day_groups = response.json()["result"]["data"]

        rows: list[dict[str, str | float]] = []
        for day_bars in day_groups:
            if not day_bars:
                continue
            prices = [float(bar["p"]) for bar in day_bars if bar.get("p")]
            volumes = [float(bar.get("v") or 0) for bar in day_bars]
            if not prices:
                continue
            rows.append(
                {
                    "日期": day_bars[0].get("d", ""),
                    "开盘": prices[0],
                    "最高": max(prices),
                    "最低": min(prices),
                    "收盘": prices[-1],
                    "成交量": sum(volumes),
                }
            )

        frame = pd.DataFrame(rows)
        if frame.empty:
            raise DataSourceError("Sina returned no parseable option bars.")
        frame["日期"] = pd.to_datetime(frame["日期"], errors="coerce")
        frame = frame.dropna(subset=["日期"])
        return frame.sort_values("日期").reset_index(drop=True)
    except Exception as exc:
        raise _format_source_failures(
            f"option daily bars {code}",
            [f"Sina: {type(exc).__name__}: {exc}"],
        ) from exc


__all__ = [
    "DataSourceError",
    "get_bond_index_close",
    "get_bond_rates",
    "get_china_yield_curve",
    "get_convertible_bonds",
    "get_etf_nav",
    "get_etf_price",
    "get_index_close",
    "get_option_board",
    "get_option_daily",
    "get_pair",
    "get_stock_close",
    "get_stock_panel",
]
