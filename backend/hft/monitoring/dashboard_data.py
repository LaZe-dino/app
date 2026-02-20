"""
HFT Dashboard Data Provider
────────────────────────────
Aggregates data from all HFT subsystems into a unified dashboard payload
for the frontend. Includes the market-making P&L table from the architecture.
"""

import time
from typing import Any, Dict, List, Optional


class HFTDashboardProvider:
    """
    Collects snapshots from all HFT components and produces
    the complete dashboard state for WebSocket broadcasting.
    """

    def __init__(self):
        self._snapshot_count = 0

    def build_dashboard(
        self,
        feed_stats: Dict,
        book_stats: Dict,
        book_snapshots: Dict,
        fpga_stats: Dict,
        mm_stats: Dict,
        mm_positions: Dict,
        arb_stats: Dict,
        risk_stats: Dict,
        position_summary: Dict,
        all_positions: Dict,
        oms_stats: Dict,
        recent_fills: List,
        router_stats: Dict,
        venue_stats: Dict,
        metrics_summary: Dict,
        queue_stats: Dict,
    ) -> Dict[str, Any]:
        self._snapshot_count += 1

        mm_table = self._build_mm_table(book_snapshots, mm_positions)

        return {
            "type": "hft_dashboard",
            "snapshot_id": self._snapshot_count,
            "timestamp": time.time(),

            "system_health": {
                "status": "ACTIVE" if not risk_stats.get("circuit_breaker_active") else "HALTED",
                "uptime_seconds": metrics_summary.get("uptime_seconds", 0),
                "events_per_second": metrics_summary.get("events_per_second", 0),
                "orders_per_second": metrics_summary.get("orders_per_second", 0),
            },

            "tick_to_trade": {
                "avg_us": metrics_summary.get("latencies", {}).get("tick_to_trade", {}).get("avg_us", 0),
                "p50_us": metrics_summary.get("latencies", {}).get("tick_to_trade", {}).get("p50_us", 0),
                "p95_us": metrics_summary.get("latencies", {}).get("tick_to_trade", {}).get("p95_us", 0),
                "p99_us": metrics_summary.get("latencies", {}).get("tick_to_trade", {}).get("p99_us", 0),
                "p999_us": metrics_summary.get("latencies", {}).get("tick_to_trade", {}).get("p999_us", 0),
            },

            "network": {
                "messages_per_second": feed_stats.get("messages_per_second", 0),
                "total_messages": feed_stats.get("messages_received", 0),
                "gaps_detected": feed_stats.get("gaps_detected", 0),
                "kernel_bypass": feed_stats.get("kernel_bypass", False),
                "queue_depth": queue_stats.get("depth", 0),
            },

            "order_books": {
                "symbols_tracked": book_stats.get("symbols_tracked", 0),
                "total_updates": book_stats.get("total_updates", 0),
                "books": book_stats.get("books", {}),
            },

            "fpga": {
                "enabled": fpga_stats.get("enabled", False),
                "ticks_processed": fpga_stats.get("ticks_processed", 0),
                "signals_generated": fpga_stats.get("signals_generated", 0),
                "avg_pipeline_ns": fpga_stats.get("avg_pipeline_ns", 0),
                "pipeline_stages": fpga_stats.get("stages", []),
                "arbitrage_opportunities": fpga_stats.get("arbitrage_opportunities", 0),
                "recent_arbs": fpga_stats.get("recent_arbs", []),
            },

            "strategies": {
                "market_making": {
                    "total_pnl": mm_stats.get("total_pnl", 0),
                    "total_trades": mm_stats.get("total_trades", 0),
                    "total_volume": mm_stats.get("total_volume", 0),
                    "active_quotes": mm_stats.get("active_quotes", 0),
                    "spread_earned": mm_stats.get("spread_earned", 0),
                },
                "arbitrage": {
                    "opportunities": arb_stats.get("opportunities_detected", 0),
                    "theoretical_profit": arb_stats.get("total_theoretical_profit", 0),
                    "hit_rate": arb_stats.get("hit_rate", 0),
                    "recent_signals": arb_stats.get("recent_signals", [])[:5],
                },
            },

            "market_making_table": mm_table,

            "risk": {
                "checks_run": risk_stats.get("checks_run", 0),
                "pass_rate": risk_stats.get("pass_rate", 0),
                "circuit_breaker": risk_stats.get("circuit_breaker_active", False),
                "daily_pnl": risk_stats.get("daily_pnl", 0),
                "avg_check_latency_us": risk_stats.get("avg_check_latency_us", 0),
                "rejection_reasons": risk_stats.get("rejection_reasons", {}),
            },

            "positions": {
                "summary": position_summary,
                "by_symbol": all_positions,
            },

            "execution": {
                "oms": oms_stats,
                "routing": router_stats,
                "venues": venue_stats,
                "recent_fills": recent_fills[-20:],
            },

            "latency_breakdown": {
                stage: metrics_summary.get("latencies", {}).get(stage, {})
                for stage in [
                    "feed_handler", "book_update", "fpga_pipeline",
                    "risk_check", "order_routing", "exchange_round_trip",
                ]
            },
        }

    def _build_mm_table(
        self, book_snapshots: Dict, mm_positions: Dict
    ) -> List[Dict[str, Any]]:
        """
        Build the market-making P&L table shown in the architecture diagram:
        Stock | Buy Price | Sell Price | Spread | Trades Executed | Profit
        """
        table = []
        for symbol, snap in book_snapshots.items():
            pos = mm_positions.get(symbol, {})
            bid = snap.get("best_bid", 0)
            ask = snap.get("best_ask", 0)
            spread = round(ask - bid, 2) if (bid and ask) else 0

            table.append({
                "stock": symbol,
                "buy_price": bid,
                "sell_price": ask,
                "spread": spread,
                "spread_bps": snap.get("spread_bps", 0),
                "trades_executed": pos.get("trades", 0),
                "volume": pos.get("volume", 0),
                "profit": pos.get("total_pnl", 0),
                "net_position": pos.get("net_position", 0),
            })

        table.sort(key=lambda x: x.get("profit", 0), reverse=True)
        return table
