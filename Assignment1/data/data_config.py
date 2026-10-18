"""Shared configuration for Assignment 1 data processing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parent
DATABASE_PATH = DATA_DIR / "data.duckdb"
CLEANING_SUMMARY_PATH = DATA_DIR / "cleaning_summary.json"
VALIDATION_RESULTS_PATH = DATA_DIR / "validation_results.json"

RAW_START_DATE = "2018-01-01"
ANALYSIS_START_DATE = "2019-01-01"

FetchMethod = Literal["index", "bond_index", "etf_price"]


@dataclass(frozen=True)
class AssetSpec:
    """Describe one market series and its download method.

    Args:
        asset_id: Stable identifier used in DuckDB.
        asset_name: Human-readable Chinese asset name.
        asset_class: Broad class, either ``equity`` or ``bond``.
        symbol: Symbol accepted by the selected ``findata_lib`` interface.
        source: Exact source interface used for retrieval.
        return_type: Stored index or adjusted-price convention.
        tenor_bucket: Remaining-maturity bucket when applicable.
        fetch_method: Dispatcher key for the download interface.
    """

    asset_id: str
    asset_name: str
    asset_class: str
    symbol: str
    source: str
    return_type: str
    tenor_bucket: str | None
    fetch_method: FetchMethod


ASSET_SPECS = (
    AssetSpec(
        asset_id="CSI300",
        asset_name="沪深300",
        asset_class="equity",
        symbol="sh000300",
        source="findata_lib.get_index_close",
        return_type="price_index",
        tenor_bucket=None,
        fetch_method="index",
    ),
    AssetSpec(
        asset_id="CSI500",
        asset_name="中证500",
        asset_class="equity",
        symbol="sh000905",
        source="findata_lib.get_index_close",
        return_type="price_index",
        tenor_bucket=None,
        fetch_method="index",
    ),
    AssetSpec(
        asset_id="STAR50",
        asset_name="科创50",
        asset_class="equity",
        symbol="sh000688",
        source="findata_lib.get_index_close",
        return_type="price_index",
        tenor_bucket=None,
        fetch_method="index",
    ),
    AssetSpec(
        asset_id="SSE_COMPOSITE",
        asset_name="上证综指",
        asset_class="equity",
        symbol="sh000001",
        source="findata_lib.get_index_close",
        return_type="price_index",
        tenor_bucket=None,
        fetch_method="index",
    ),
    AssetSpec(
        asset_id="SSE_TREASURY",
        asset_name="上证国债指数",
        asset_class="bond",
        symbol="sh000012",
        source="findata_lib.get_bond_index_close",
        return_type="price_index",
        tenor_bucket=None,
        fetch_method="bond_index",
    ),
    AssetSpec(
        asset_id="POLICY_BOND_7_10_PROXY",
        asset_name="政金债券ETF（政金债7—10年指数代理）",
        asset_class="bond",
        symbol="511520",
        source="findata_lib.get_etf_price",
        return_type="forward_adjusted_etf_price",
        tenor_bucket="7-10Y",
        fetch_method="etf_price",
    ),
    AssetSpec(
        asset_id="SSE_ENTERPRISE_BOND",
        asset_name="上证企债指数",
        asset_class="bond",
        symbol="sh000013",
        source="findata_lib.get_bond_index_close",
        return_type="price_index",
        tenor_bucket=None,
        fetch_method="bond_index",
    ),
)

GOVERNMENT_YIELD_COLUMNS = {
    2.0: "中国国债收益率2年",
    5.0: "中国国债收益率5年",
    10.0: "中国国债收益率10年",
    30.0: "中国国债收益率30年",
}

