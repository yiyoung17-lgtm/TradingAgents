from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from tradingagents.dataflows import quality
from tradingagents.dataflows.config import run_config


PRICES = "Date,Open,High,Low,Close,Volume\n2026-10-09,100,102,99,101,1000\n"


def test_market_failure_stops_before_news_or_models(monkeypatch):
    router = Mock(return_value="DATA_UNAVAILABLE: rate limited")
    monkeypatch.setattr(quality, "route_to_vendor", router)
    with pytest.raises(quality.DataQualityError):
        quality.preflight("AAPL", "2026-10-09", ["market", "news"])
    assert router.call_count == 1


@pytest.mark.parametrize("answer", ["<Yahoo Finance news unavailable for 2026-10-02..2026-10-09: recent only>", "", "NO_DATA_AVAILABLE"])
def test_news_gap_is_not_an_investment_rating(monkeypatch, answer):
    monkeypatch.setattr(quality, "route_to_vendor", Mock(side_effect=[PRICES, answer]))
    with pytest.raises(quality.DataQualityError):
        quality.preflight("AAPL", "2026-10-09", ["market", "news"])


@pytest.mark.parametrize("prices", [PRICES.replace("2026-10-09", "2025-10-09"), PRICES.replace(",101,", ",0,"), "An error occurred"])
def test_invalid_prices_are_rejected(monkeypatch, prices):
    monkeypatch.setattr(quality, "route_to_vendor", Mock(return_value=prices))
    with pytest.raises(quality.DataQualityError):
        quality.preflight("AAPL", "2026-10-09", ["market"])


def test_valid_evidence_passes(monkeypatch):
    monkeypatch.setattr(quality, "route_to_vendor", Mock(side_effect=[PRICES, "Dated news with source"]))
    quality.preflight("AAPL", "2026-10-09", ["market", "news"])


def test_failed_run_has_no_hold_rating_or_order(tmp_path):
    with run_config({"results_dir": str(tmp_path)}):
        path = quality.write_failure("AAPL", "2026-10-09", "get_news unavailable")
    text = path.read_text()
    assert "DATA_UNAVAILABLE / 无法判断" in text
    assert "Rating: Hold" not in text
    assert "Quantity:" not in text


def test_mid_run_tool_failure_prevents_next_model_request(monkeypatch):
    from tradingagents.graph.setup import _analyst_graph
    from tradingagents.graph.analyst_execution import ANALYST_NODE_SPECS
    from tradingagents.agents.tools import get_stock_data
    monkeypatch.setattr(get_stock_data, "func", lambda **kwargs: "DATA_UNAVAILABLE")
    agent = Mock(return_value={"messages": [AIMessage(content="", tool_calls=[{
        "name": "get_stock_data", "args": {"symbol": "AAPL", "start_date": "2026-10-01", "end_date": "2026-10-09"}, "id": "call-1",
    }])]})
    graph = _analyst_graph(ANALYST_NODE_SPECS["market"], agent, 3)
    with pytest.raises(quality.DataQualityError):
        graph.invoke({"messages": [], "company_of_interest": "AAPL", "trade_date": "2026-10-09"})
    assert agent.call_count == 1


def test_explicit_vendor_env_overrides(monkeypatch):
    from tradingagents.default_config import build_default_config
    monkeypatch.setenv("TRADINGAGENTS_VENDOR_CORE_STOCK_APIS", "yfinance,alpha_vantage")
    assert build_default_config()["data_vendors"]["core_stock_apis"] == "yfinance,alpha_vantage"


def test_news_window_gap_tries_explicit_backup(monkeypatch):
    from tradingagents.dataflows import router
    first = Mock(return_value="<Yahoo Finance news unavailable for 2026-10-02..2026-10-09: recent only>")
    backup = Mock(return_value="Dated news from backup")
    monkeypatch.setitem(router.VENDOR_METHODS, "get_news", {"yfinance": first, "alpha_vantage": backup})
    with run_config({"data_vendors": {"news_data": "yfinance,alpha_vantage"}}):
        assert router.route_to_vendor("get_news", "AAPL", "2026-10-02", "2026-10-09") == "Dated news from backup"
    assert first.call_count == backup.call_count == 1
