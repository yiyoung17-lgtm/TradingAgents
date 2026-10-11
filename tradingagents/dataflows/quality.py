"""Fail closed when the requested analysis lacks its required evidence."""
from datetime import datetime, timedelta
from pathlib import Path

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.router import route_to_vendor


class DataQualityError(RuntimeError):
    """Core data is unavailable; this is an incomplete run, never a Hold."""


def unavailable(value) -> bool:
    text = str(value or "").strip()
    return not text or (text.startswith("<") and " unavailable for " in text) or any(marker in text for marker in (
        "DATA_UNAVAILABLE", "NO_DATA_AVAILABLE", "COVERAGE_GAP",
    ))


def require_data(method, *args):
    try:
        result = route_to_vendor(method, *args)
    except Exception as exc:
        # Do not copy provider exceptions that may contain credential-bearing URLs.
        raise DataQualityError(f"{method}: 数据源请求失败 ({type(exc).__name__})") from None
    if unavailable(result):
        raise DataQualityError(f"{method}: 必需数据不可用或日期覆盖不足。请检查数据源和限流。")
    return result


def preflight(ticker, trade_date, analysts):
    """Validate core evidence before any analyst/debate model requests."""
    end = datetime.strptime(trade_date, "%Y-%m-%d")
    # Every workflow ends in a trading decision and therefore needs an actual price.
    prices = require_data("get_stock_data", ticker, (end - timedelta(days=365)).strftime("%Y-%m-%d"), trade_date)
    from io import StringIO
    import pandas as pd
    try:
        frame = pd.read_csv(StringIO(str(prices)), comment="#")
        columns = {str(col).lower(): col for col in frame.columns}
        close = pd.to_numeric(frame[columns["close"]], errors="coerce")
        dates = pd.to_datetime(frame.iloc[:, 0], errors="coerce", utc=True)
        if frame.empty or close.isna().all() or (close.dropna() <= 0).any():
            raise ValueError("missing valid close prices")
        latest = dates.max()
        if pd.isna(latest) or latest.date() > end.date() or (end.date() - latest.date()).days > 10:
            raise ValueError("stale or future data")
    except (KeyError, ValueError, TypeError, pd.errors.ParserError):
        raise DataQualityError("get_stock_data: 行情缺少有效价格或日期过期，无法分析。") from None
    if "news" in analysts:
        require_data("get_news", ticker, (end - timedelta(days=7)).strftime("%Y-%m-%d"), trade_date)
    if "fundamentals" in analysts:
        require_data("get_income_statement", ticker, "annual", trade_date)


def write_failure(ticker, trade_date, reason):
    from tradingagents.dataflows.symbols import safe_ticker_component
    folder = Path(get_config()["results_dir"]) / "failed" / (
        f"{safe_ticker_component(ticker)}_{datetime.now():%Y%m%d_%H%M%S_%f}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "data_quality_failure.md"
    path.write_text(
        f"# 分析未完成：{ticker}\n\n分析日期：{trade_date}\n\n"
        f"状态：DATA_UNAVAILABLE / 无法判断\n\n原因：{reason}\n\n"
        "本次未生成有效投资评级、目标价或交易数量。请修复数据源后重新分析。\n",
        encoding="utf-8",
    )
    return path
