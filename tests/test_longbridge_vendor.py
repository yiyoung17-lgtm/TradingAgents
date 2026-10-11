import json
from types import SimpleNamespace

import pytest
import pandas as pd

from tradingagents.dataflows.errors import NoMarketDataError, VendorUnavailableError
from tradingagents.dataflows.vendors import longbridge as lb


def test_symbol_mapping_rejects_unsupported_instruments():
    assert lb.symbol_for("AAPL") == "AAPL.US"
    assert lb.symbol_for("0700.HK") == "700.HK"
    assert lb.symbol_for("600519.SS") == "600519.SH"
    with pytest.raises(ValueError):
        lb.symbol_for("EURUSD=X")


def test_exchange_local_dates_and_cutoff(monkeypatch):
    rows = [{"time": time, "open": "10", "high": "12", "low": "9", "close": "11", "volume": "4"}
            for time in ["2026-10-08T16:00:00Z", "2026-10-09T16:00:00Z", "2026-10-10T16:00:00Z"]]
    monkeypatch.setattr(lb, "_bars", lambda *a: rows)
    frame = lb.load_prices("700.HK", "2026-10-09", "2026-10-10")
    assert list(frame.Date.dt.strftime("%Y-%m-%d")) == ["2026-10-09", "2026-10-10"]


@pytest.mark.parametrize("change", [{"close": "0"}, {"volume": "-1"}, {"high": "1"}, {"close": "bad"}])
def test_invalid_prices_fail_closed(monkeypatch, change):
    row = {"time": "2026-10-09T04:00:00Z", "open": "10", "high": "12", "low": "9", "close": "11", "volume": "4"}
    row.update(change)
    monkeypatch.setattr(lb, "_bars", lambda *a: [row])
    with pytest.raises(NoMarketDataError):
        lb.load_prices("AAPL", "2026-10-01", "2026-10-09")


def test_statement_uses_publication_date_not_period_end(monkeypatch):
    rows = [{"rpt_date": date, "fp_end": "2025-09-30", "fields": [{"value": "123"}]}
            for date in ["2026-10-01", "2026-10-11", None]]
    monkeypatch.setattr(lb, "cli", lambda *a: {"currency": "USD", "list": rows})
    result = lb.get_income_statement("AAPL", "annual", "2026-10-09")
    assert '"rpt_date": "2026-10-01"' in result
    assert '"rpt_date": "2026-10-11"' not in result
    assert '"rpt_date": null' not in result


def test_news_excludes_future_and_undated_details(monkeypatch):
    items = [{"id": str(i), "published_at": date, "title": "headline"} for i, date in
             enumerate(["2026-10-09T12:00:00Z", "2026-10-10T12:00:00Z", None])]
    def cli(*args):
        if args[1] == "detail":
            assert args[2] == "0"
            return {**items[0], "description": "dated evidence"}
        return items
    monkeypatch.setattr(lb, "cli", cli)
    result = lb.get_news("AAPL", "2026-10-02", "2026-10-09")
    assert "dated evidence" in result
    assert "Coverage is partial" in result
    assert "2026-10-10" not in result


def test_missing_news_window_is_not_no_news(monkeypatch):
    monkeypatch.setattr(lb, "cli", lambda *a: [])
    with pytest.raises(VendorUnavailableError):
        lb.get_news("AAPL", "2025-01-01", "2025-01-07")


def test_search_news_uses_time_field(monkeypatch):
    item = {"id": "1", "time": "2026-10-09T12:00:00Z", "title": "macro"}
    monkeypatch.setattr(lb, "cli", lambda *a: {"published_at": item["time"], "description": "macro evidence"} if a[1] == "detail" else [item])
    assert "macro evidence" in lb.get_global_news("2026-10-09", 7, 1)


def test_cli_errors_never_echo_provider_secrets(monkeypatch):
    monkeypatch.setattr(lb.shutil, "which", lambda a: "/bin/longbridge")
    monkeypatch.setattr(lb.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stderr="secret_token", stdout=""))
    with pytest.raises(VendorUnavailableError) as exc:
        lb.cli("quote", "AAPL.US")
    assert "secret_token" not in str(exc.value)


def test_selected_snapshot_and_settlement_never_call_yahoo(monkeypatch):
    from tradingagents.agents.tools import get_verified_market_snapshot
    from tradingagents.dataflows.config import run_config
    from tradingagents.dataflows.vendors.yahoo import market, snapshot
    data = pd.DataFrame({"Date": pd.to_datetime(["2026-10-08", "2026-10-09"]),
                         "Open": [10., 11.], "High": [12., 13.], "Low": [9., 10.],
                         "Close": [11., 12.], "Volume": [100, 200]})
    monkeypatch.setattr(lb, "load_prices", lambda *a: data)
    def forbidden(*a, **k):
        raise AssertionError("Yahoo must not be called")
    monkeypatch.setattr(snapshot, "load_ohlcv", forbidden)
    monkeypatch.setattr(market.yf, "Ticker", forbidden)
    with run_config({"data_vendors": {"core_stock_apis": "longbridge"}}):
        result = get_verified_market_snapshot.func("AAPL", "2026-10-09", 2, trade_date="2026-10-09")
        assert "Source: Longbridge" in result
        assert list(market.get_closes("AAPL", "2026-10-08", "2026-10-10")) == [11., 12.]
