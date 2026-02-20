"""
HFT Orchestrator
════════════════
The master conductor of the entire tick-to-trade pipeline.

Pipeline flow (matching the architecture diagram):
  ┌──────────────────────────────────────────────────────────────────┐
  │                     CO-LOCATION (NY5)                            │
  │                                                                  │
  │  Exchange Feeds                                                  │
  │      ↓                                                           │
  │  [Ultra-Low-Latency NIC] → [Kernel Bypass / DPDK]              │
  │      ↓                                                           │
  │  [Market Data Feed Handler] → nanosecond timestamps             │
  │      ↓                                                           │
  │  [Lock-Free Event Queue]                                         │
  │      ↓                                                           │
  │  [In-Memory Order Book] (replicated)                            │
  │      ↓                    ↓                                      │
  │  [FPGA Engine]     [Strategy Engine]                            │
  │   • Timestamping    • Market Making                             │
  │   • Arb Detection   • Latency Arb                               │
  │   • Decision Logic  • Quote Management                          │
  │      ↓                    ↓                                      │
  │  [Risk Engine] — pre-trade checks in <5µs                      │
  │      ↓                                                           │
  │  [Smart Order Router] — venue selection + order splitting       │
  │      ↓                                                           │
  │  [Exchange Gateway] → NASDAQ / NYSE / BATS / ARCA              │
  │      ↓                                                           │
  │  [OMS] — full lifecycle tracking                                │
  │      ↓                                                           │
  │  [Position Tracker] — real-time P&L                             │
  │      ↓                                                           │
  │  [Monitoring] — latency metrics, dashboards, alerts             │
  └──────────────────────────────────────────────────────────────────┘
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .clock import NanosecondClock
from .config import HFTConfig
from .pipeline import LockFreeEventQueue
from .pipeline.event_types import (
    MarketDataEvent, StrategySignal, OrderEvent, FillEvent,
    HFTEventType, Side, OrderType, OrderStatus,
)
from .network import MarketDataFeedHandler, MulticastDistributor
from .orderbook import OrderBookManager
from .fpga import FPGAEngine
from .strategy import MarketMakingEngine, LatencyArbitrageEngine
from .execution import ExchangeGateway, OrderManagementSystem, SmartOrderRouter
from .risk import HFTRiskEngine, PositionTracker
from .monitoring import LatencyMetrics, HFTMetricsCollector, HFTDashboardProvider

logger = logging.getLogger(__name__)


class HFTOrchestrator:
    """
    Main HFT system orchestrator. Initializes all components and
    runs the tick-to-trade pipeline in a continuous async loop.
    """

    def __init__(
        self,
        config: HFTConfig,
        symbols: List[str],
        base_prices: Dict[str, float],
    ):
        self.config = config
        self.symbols = symbols
        self.base_prices = base_prices

        self.clock = NanosecondClock()

        self.event_queue = LockFreeEventQueue(
            capacity=65536, name="market_data"
        )
        self.signal_queue = LockFreeEventQueue(
            capacity=8192, name="signals"
        )

        self.feed_handler = MarketDataFeedHandler(
            config=config.network,
            output_queue=self.event_queue,
            symbols=symbols,
            base_prices=base_prices,
            clock=self.clock,
        )

        self.multicast = MulticastDistributor(self.clock)
        half = len(symbols) // 2
        self.multicast.create_group("239.1.1.1", symbols[:half])
        self.multicast.create_group("239.1.1.2", symbols[half:])

        self.order_books = OrderBookManager(
            clock=self.clock,
            replica_count=config.orderbook.replica_count,
        )
        for sym in symbols:
            self.order_books.register_symbol(sym)

        self.fpga = FPGAEngine(config=config.fpga, clock=self.clock)

        self.market_maker = MarketMakingEngine(
            config=config.strategy, clock=self.clock
        )
        self.arbitrage = LatencyArbitrageEngine(
            config=config.strategy, clock=self.clock
        )

        self.position_tracker = PositionTracker()
        self.risk_engine = HFTRiskEngine(
            config=config.risk,
            clock=self.clock,
            position_tracker=self.position_tracker,
        )

        self.oms = OrderManagementSystem(clock=self.clock)
        self.gateway = ExchangeGateway(clock=self.clock)
        self.router = SmartOrderRouter(
            config=config.execution,
            clock=self.clock,
            oms=self.oms,
            gateway=self.gateway,
        )

        self.metrics = HFTMetricsCollector(config=config.monitoring)
        self.dashboard_provider = HFTDashboardProvider()

        self._running = False
        self._pipeline_task: Optional[asyncio.Task] = None
        self._mm_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._ws_broadcast_fn: Optional[Callable] = None

        self._pipeline_cycles = 0
        self._total_signals_processed = 0
        self._total_orders_executed = 0

    def set_ws_broadcast(self, fn: Callable):
        self._ws_broadcast_fn = fn

    async def start(self):
        if self._running:
            return

        self._running = True
        logger.info(f"[HFT] Starting orchestrator — {len(self.symbols)} symbols, co-location: {self.config.co_location}")

        await self.feed_handler.start()

        self._pipeline_task = asyncio.create_task(self._pipeline_loop())
        self._mm_task = asyncio.create_task(self._market_making_loop())
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info("[HFT] All pipeline components running — tick-to-trade active")

    async def stop(self):
        self._running = False
        await self.feed_handler.stop()

        for task in [self._pipeline_task, self._mm_task, self._monitoring_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info(f"[HFT] Orchestrator stopped — {self._pipeline_cycles} pipeline cycles, {self._total_orders_executed} orders executed")

    async def _pipeline_loop(self):
        """
        Main tick-to-trade pipeline. Processes market data events,
        evaluates strategies, checks risk, routes orders, handles fills.
        """
        while self._running:
            try:
                events = self.event_queue.consume_batch(max_items=16)
                if not events:
                    await asyncio.sleep(0.05)
                    continue

                for event in events:
                    tick_start = time.perf_counter_ns()

                    self.order_books.apply_event(event)
                    book_update_ns = time.perf_counter_ns() - tick_start
                    self.metrics.book_update.record(book_update_ns)

                    fpga_start = time.perf_counter_ns()
                    fpga_signal = self.fpga.process_tick(event)
                    fpga_ns = time.perf_counter_ns() - fpga_start
                    self.metrics.fpga_pipeline.record(fpga_ns)

                    arb_signal = self.arbitrage.evaluate(event)

                    signals = []
                    if fpga_signal:
                        signals.append(fpga_signal)
                    if arb_signal:
                        signals.append(arb_signal)

                    for signal in signals:
                        await self._execute_signal(signal, tick_start)

                    tick_total = time.perf_counter_ns() - tick_start
                    if signals:
                        self.metrics.tick_to_trade.record(tick_total)

                    self.metrics.record_event("tick")

                self._pipeline_cycles += 1
                await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HFT] Pipeline error: {e}")
                await asyncio.sleep(0.1)

    async def _market_making_loop(self):
        """
        Periodic market-making quote refresh loop.
        Generates two-sided quotes for all active symbols.
        """
        while self._running:
            try:
                for symbol in self.symbols:
                    book = self.order_books.get_book(symbol)
                    if not book or not book.mid_price:
                        continue

                    signals = self.market_maker.generate_quotes(symbol, book)
                    for signal in signals:
                        await self._execute_signal(signal, time.perf_counter_ns())

                interval_s = self.config.strategy.quote_refresh_interval_ms / 1_000
                await asyncio.sleep(interval_s)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HFT] Market-making error: {e}")
                await asyncio.sleep(0.1)

    async def _execute_signal(self, signal: StrategySignal, tick_start_ns: int):
        """
        Full execution path: signal → risk check → route → submit → fill.
        """
        self._total_signals_processed += 1

        route_start = time.perf_counter_ns()
        orders = await self.router.route_signal(signal)
        route_ns = time.perf_counter_ns() - route_start
        self.metrics.order_routing.record(route_ns)

        for order in orders:
            risk_decision = self.risk_engine.check_order(order)
            self.metrics.risk_check.record(risk_decision.latency_ns)

            if not risk_decision.approved:
                self.oms.update_status(order.order_id, OrderStatus.REJECTED)
                continue

            exchange_start = time.perf_counter_ns()
            acked_order = await self.gateway.submit_order(order)
            self.oms.update_status(acked_order.order_id, acked_order.status)

            if acked_order.status == OrderStatus.ACKED:
                fills = await self.gateway.get_fills(acked_order)
                for fill in fills:
                    self.oms.apply_fill(fill)
                    self.position_tracker.apply_fill(fill)
                    self.market_maker.on_fill(fill)
                    self.risk_engine.update_daily_pnl(
                        fill.fill_price * fill.fill_qty * (1 if fill.side == Side.SELL else -1) * 0.001
                    )
                    self.metrics.record_event("fill")
                    self._total_orders_executed += 1

                self.router.update_venue_score(acked_order.venue, True)
            else:
                self.router.update_venue_score(acked_order.venue, False)

            exchange_ns = time.perf_counter_ns() - exchange_start
            self.metrics.exchange_round_trip.record(exchange_ns)
            self.metrics.record_event("order")

    async def _monitoring_loop(self):
        """Periodic dashboard snapshot and alert checking."""
        while self._running:
            try:
                self.metrics.check_alerts()

                if self._ws_broadcast_fn:
                    dashboard = self.get_dashboard()
                    try:
                        await self._ws_broadcast_fn(dashboard)
                    except Exception:
                        pass

                interval = self.config.monitoring.metrics_publish_interval_ms / 1_000
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HFT] Monitoring error: {e}")
                await asyncio.sleep(1.0)

    def get_dashboard(self) -> Dict[str, Any]:
        """Build complete dashboard snapshot."""
        return self.dashboard_provider.build_dashboard(
            feed_stats=self.feed_handler.get_stats(),
            book_stats=self.order_books.get_stats(),
            book_snapshots=self.order_books.get_all_snapshots(),
            fpga_stats=self.fpga.get_pipeline_stats(),
            mm_stats=self.market_maker.get_stats(),
            mm_positions=self.market_maker.get_positions(),
            arb_stats=self.arbitrage.get_stats(),
            risk_stats=self.risk_engine.get_stats(),
            position_summary=self.position_tracker.get_portfolio_summary(),
            all_positions=self.position_tracker.get_all_positions(),
            oms_stats=self.oms.get_stats(),
            recent_fills=self.oms.get_recent_fills(50),
            router_stats=self.router.get_stats(),
            venue_stats=self.gateway.get_venue_stats(),
            metrics_summary=self.metrics.get_summary(),
            queue_stats=self.event_queue.get_stats(),
        )

    def get_order_book_snapshot(self, symbol: str) -> Optional[Dict]:
        book = self.order_books.get_book(symbol)
        return book.get_snapshot() if book else None

    def get_all_order_books(self) -> Dict[str, Dict]:
        return self.order_books.get_all_snapshots()

    def inject_price_shock(self, symbol: str, magnitude_pct: float):
        self.feed_handler.inject_price_shock(symbol, magnitude_pct)

    def get_system_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "co_location": self.config.co_location,
            "system_id": self.config.system_id,
            "simulation_mode": self.config.simulation_mode,
            "symbols": self.symbols,
            "pipeline_cycles": self._pipeline_cycles,
            "signals_processed": self._total_signals_processed,
            "orders_executed": self._total_orders_executed,
            "components": {
                "feed_handler": "active" if self._running else "stopped",
                "order_books": f"{len(self.symbols)} symbols",
                "fpga_engine": "enabled" if self.config.fpga.enabled else "disabled",
                "market_maker": "enabled" if self.config.strategy.market_making_enabled else "disabled",
                "arbitrage": "enabled" if self.config.strategy.arbitrage_enabled else "disabled",
                "risk_engine": "active" if not self.risk_engine._circuit_breaker_active else "HALTED",
                "smart_router": f"{len(self.config.execution.venues)} venues",
            },
        }
