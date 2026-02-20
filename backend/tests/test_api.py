import pytest
import requests
import os
import time

# Test: Backend API endpoints for AI-Native Hedge Fund
# Covers: dashboard, market-data, trade-signals, research/analyze, research/reports, portfolio, risk, agents/status

BASE_URL = "https://alpha-agents.preview.emergentagent.com"

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

class TestDashboard:
    """Dashboard endpoint tests"""

    def test_dashboard_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/dashboard")
        assert response.status_code == 200, f"Dashboard failed with {response.status_code}: {response.text}"

    def test_dashboard_has_portfolio_data(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/dashboard")
        data = response.json()
        assert "portfolio" in data, "Missing portfolio key"
        assert "total_value" in data["portfolio"], "Missing portfolio.total_value"
        assert "total_pnl" in data["portfolio"], "Missing portfolio.total_pnl"
        assert "holdings_count" in data["portfolio"], "Missing portfolio.holdings_count"
        assert isinstance(data["portfolio"]["total_value"], (int, float)), "total_value should be numeric"

    def test_dashboard_has_signals(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/dashboard")
        data = response.json()
        assert "top_signals" in data, "Missing top_signals key"
        assert isinstance(data["top_signals"], list), "top_signals should be a list"

    def test_dashboard_has_market_indices(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/dashboard")
        data = response.json()
        assert "market_indices" in data, "Missing market_indices key"
        assert len(data["market_indices"]) >= 2, "Should have at least 2 indices (SPY, QQQ)"
        for idx in data["market_indices"]:
            assert "name" in idx and "symbol" in idx and "price" in idx, f"Index missing required fields: {idx}"

    def test_dashboard_has_agent_stats(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/dashboard")
        data = response.json()
        assert "agents" in data, "Missing agents key"
        assert "total" in data["agents"], "Missing agents.total"
        assert "active" in data["agents"], "Missing agents.active"
        assert data["agents"]["total"] >= 0, "agents.total should be >= 0"

class TestMarketData:
    """Market data endpoint tests"""

    def test_market_data_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/market-data")
        assert response.status_code == 200, f"Market data failed with {response.status_code}"

    def test_market_data_has_12_stocks(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/market-data")
        data = response.json()
        assert "stocks" in data, "Missing stocks key"
        assert len(data["stocks"]) == 12, f"Expected 12 stocks, got {len(data['stocks'])}"

    def test_market_data_stock_structure(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/market-data")
        data = response.json()
        required_fields = ["symbol", "name", "sector", "price", "change", "change_pct", "market_cap", "pe", "volume"]
        for stock in data["stocks"]:
            for field in required_fields:
                assert field in stock, f"Stock {stock.get('symbol', 'unknown')} missing field: {field}"

    def test_market_data_symbols_correct(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/market-data")
        data = response.json()
        expected_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V", "UNH", "SPY", "QQQ"]
        actual_symbols = [s["symbol"] for s in data["stocks"]]
        for sym in expected_symbols:
            assert sym in actual_symbols, f"Expected symbol {sym} not found in market data"

class TestTradeSignals:
    """Trade signals endpoint tests"""

    def test_trade_signals_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trade-signals")
        assert response.status_code == 200, f"Trade signals failed with {response.status_code}"

    def test_trade_signals_structure(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trade-signals")
        data = response.json()
        assert "signals" in data, "Missing signals key"
        assert "count" in data, "Missing count key"
        assert isinstance(data["signals"], list), "signals should be a list"

    def test_seeded_signals_exist(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trade-signals")
        data = response.json()
        # Seed data creates 5 initial signals
        assert len(data["signals"]) >= 5, f"Expected at least 5 seeded signals, got {len(data['signals'])}"

    def test_signal_has_required_fields(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trade-signals")
        data = response.json()
        if len(data["signals"]) > 0:
            signal = data["signals"][0]
            required = ["id", "symbol", "action", "confidence", "price_target", "current_price", "reasoning", "agent_type", "timestamp"]
            for field in required:
                assert field in signal, f"Signal missing field: {field}"
            assert signal["action"] in ["BUY", "SELL", "HOLD"], f"Invalid action: {signal['action']}"

class TestResearchAnalyze:
    """Research analyze endpoint tests (GPT-5.2 AI integration)"""

    def test_analyze_aapl_success(self, api_client):
        response = api_client.post(
            f"{BASE_URL}/api/research/analyze",
            json={"symbol": "AAPL", "analysis_type": "comprehensive"}
        )
        assert response.status_code == 200, f"Analyze failed with {response.status_code}: {response.text}"

    def test_analyze_returns_report_and_signal(self, api_client):
        # Test with a quick analysis
        response = api_client.post(
            f"{BASE_URL}/api/research/analyze",
            json={"symbol": "MSFT", "analysis_type": "comprehensive"}
        )
        data = response.json()
        assert "report" in data, "Missing report key"
        assert "signal" in data, "Missing signal key"

    def test_analyze_report_structure(self, api_client):
        response = api_client.post(
            f"{BASE_URL}/api/research/analyze",
            json={"symbol": "GOOGL", "analysis_type": "comprehensive"}
        )
        data = response.json()
        report = data["report"]
        required = ["id", "symbol", "analysis_type", "summary", "sentiment", "sentiment_score", "key_findings", "risks", "recommendation", "confidence", "agent_name", "timestamp"]
        for field in required:
            assert field in report, f"Report missing field: {field}"
        assert report["sentiment"] in ["bullish", "bearish", "neutral"], f"Invalid sentiment: {report['sentiment']}"
        assert isinstance(report["key_findings"], list), "key_findings should be a list"
        assert isinstance(report["risks"], list), "risks should be a list"

    def test_analyze_signal_structure(self, api_client):
        response = api_client.post(
            f"{BASE_URL}/api/research/analyze",
            json={"symbol": "NVDA", "analysis_type": "comprehensive"}
        )
        data = response.json()
        signal = data["signal"]
        required = ["id", "symbol", "action", "confidence", "price_target", "current_price", "reasoning", "agent_type", "timestamp"]
        for field in required:
            assert field in signal, f"Signal missing field: {field}"
        assert signal["action"] in ["BUY", "SELL", "HOLD"], f"Invalid action: {signal['action']}"

    def test_analyze_invalid_symbol_returns_400(self, api_client):
        response = api_client.post(
            f"{BASE_URL}/api/research/analyze",
            json={"symbol": "INVALID", "analysis_type": "comprehensive"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid symbol, got {response.status_code}"

    def test_analyze_creates_persistent_data(self, api_client):
        # Analyze a symbol
        symbol = "TSLA"
        response = api_client.post(
            f"{BASE_URL}/api/research/analyze",
            json={"symbol": symbol, "analysis_type": "comprehensive"}
        )
        assert response.status_code == 200, "Analysis failed"
        
        # Wait a moment for data to persist
        time.sleep(1)
        
        # Verify report was saved
        reports_response = api_client.get(f"{BASE_URL}/api/research/reports")
        reports_data = reports_response.json()
        symbols_in_reports = [r["symbol"] for r in reports_data["reports"]]
        assert symbol in symbols_in_reports, f"Report for {symbol} not found in /research/reports"
        
        # Verify signal was saved
        signals_response = api_client.get(f"{BASE_URL}/api/trade-signals")
        signals_data = signals_response.json()
        symbols_in_signals = [s["symbol"] for s in signals_data["signals"]]
        assert symbol in symbols_in_signals, f"Signal for {symbol} not found in /trade-signals"

class TestResearchReports:
    """Research reports endpoint tests"""

    def test_reports_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/research/reports")
        assert response.status_code == 200, f"Reports failed with {response.status_code}"

    def test_reports_structure(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/research/reports")
        data = response.json()
        assert "reports" in data, "Missing reports key"
        assert "count" in data, "Missing count key"
        assert isinstance(data["reports"], list), "reports should be a list"

class TestPortfolio:
    """Portfolio endpoint tests"""

    def test_portfolio_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/portfolio")
        assert response.status_code == 200, f"Portfolio failed with {response.status_code}"

    def test_portfolio_has_holdings(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/portfolio")
        data = response.json()
        assert "holdings" in data, "Missing holdings key"
        assert len(data["holdings"]) >= 6, f"Expected at least 6 seeded holdings, got {len(data['holdings'])}"

    def test_portfolio_holdings_structure(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/portfolio")
        data = response.json()
        if len(data["holdings"]) > 0:
            holding = data["holdings"][0]
            required = ["symbol", "name", "shares", "avg_cost", "current_price", "pnl", "pnl_pct", "market_value"]
            for field in required:
                assert field in holding, f"Holding missing field: {field}"

    def test_portfolio_has_totals(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/portfolio")
        data = response.json()
        assert "total_value" in data, "Missing total_value"
        assert "total_cost" in data, "Missing total_cost"
        assert "total_pnl" in data, "Missing total_pnl"
        assert "total_pnl_pct" in data, "Missing total_pnl_pct"

    def test_portfolio_has_history(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/portfolio")
        data = response.json()
        assert "history" in data, "Missing history key"
        assert len(data["history"]) > 0, "Portfolio history should not be empty"

class TestRisk:
    """Risk metrics endpoint tests"""

    def test_risk_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/risk")
        assert response.status_code == 200, f"Risk failed with {response.status_code}"

    def test_risk_metrics_present(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/risk")
        data = response.json()
        required = ["var_95", "sharpe_ratio", "beta", "max_drawdown", "volatility", "sector_allocation", "total_value"]
        for field in required:
            assert field in data, f"Risk data missing field: {field}"

    def test_risk_sector_allocation(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/risk")
        data = response.json()
        assert isinstance(data["sector_allocation"], list), "sector_allocation should be a list"
        if len(data["sector_allocation"]) > 0:
            sector = data["sector_allocation"][0]
            assert "sector" in sector and "value" in sector and "pct" in sector, "Sector missing required fields"

    def test_risk_alerts_structure(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/risk")
        data = response.json()
        assert "alerts" in data, "Missing alerts key"
        assert isinstance(data["alerts"], list), "alerts should be a list"

class TestAgentsStatus:
    """Agents status endpoint tests"""

    def test_agents_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/agents/status")
        assert response.status_code == 200, f"Agents status failed with {response.status_code}"

    def test_agents_has_summary(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/agents/status")
        data = response.json()
        assert "summary" in data, "Missing summary key"
        assert "total" in data["summary"], "Missing summary.total"
        assert "active" in data["summary"], "Missing summary.active"

    def test_agents_list_structure(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/agents/status")
        data = response.json()
        assert "agents" in data, "Missing agents key"
        assert len(data["agents"]) >= 6, f"Expected at least 6 seeded agents, got {len(data['agents'])}"
        
        if len(data["agents"]) > 0:
            agent = data["agents"][0]
            required = ["name", "type", "status", "tasks_completed", "last_active"]
            for field in required:
                assert field in agent, f"Agent missing field: {field}"
            assert agent["type"] in ["research", "synthesis", "execution", "risk"], f"Invalid agent type: {agent['type']}"
            assert agent["status"] in ["active", "idle", "processing"], f"Invalid agent status: {agent['status']}"
