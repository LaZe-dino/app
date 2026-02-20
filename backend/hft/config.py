"""
HFT System Configuration
─────────────────────────
Centralizes all tunable parameters for the tick-to-trade pipeline.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class NetworkConfig:
    kernel_bypass_enabled: bool = True
    nic_rx_ring_size: int = 4096
    multicast_groups: List[str] = field(default_factory=lambda: [
        "239.1.1.1",  # NASDAQ ITCH
        "239.1.1.2",  # NYSE Arca
    ])
    dpdk_enabled: bool = True
    onload_enabled: bool = True
    tcp_nodelay: bool = True
    so_busy_poll_us: int = 50


@dataclass
class OrderBookConfig:
    max_price_levels: int = 10000
    replica_count: int = 2
    snapshot_interval_ms: float = 100.0
    max_symbols: int = 5000
    pre_allocated_levels: int = 2000


@dataclass
class FPGAConfig:
    enabled: bool = True
    clock_frequency_mhz: int = 250
    pipeline_stages: int = 8
    max_tick_to_trade_ns: int = 800
    arbitrage_threshold_bps: float = 0.5
    decision_lookup_table_size: int = 65536


@dataclass
class StrategyConfig:
    market_making_enabled: bool = True
    arbitrage_enabled: bool = True

    default_spread_bps: float = 2.0
    min_spread_bps: float = 0.5
    max_spread_bps: float = 10.0
    quote_size_shares: int = 100
    max_position_shares: int = 10000
    inventory_skew_factor: float = 0.3
    quote_refresh_interval_ms: float = 50.0

    arb_min_profit_bps: float = 0.3
    arb_max_notional: float = 1_000_000.0
    arb_staleness_threshold_us: int = 500


@dataclass
class RiskConfig:
    max_order_value: float = 500_000.0
    max_position_value: float = 5_000_000.0
    max_daily_loss: float = 100_000.0
    max_orders_per_second: int = 5000
    max_notional_per_second: float = 10_000_000.0
    fat_finger_threshold_pct: float = 5.0
    circuit_breaker_loss_pct: float = 2.0
    position_limit_per_symbol: int = 50000
    correlation_exposure_limit: float = 0.8


@dataclass
class ExecutionConfig:
    venues: List[str] = field(default_factory=lambda: ["NASDAQ", "NYSE", "BATS", "IEX", "ARCA"])
    default_order_type: str = "LIMIT"
    max_slice_size: int = 500
    venue_latencies_us: Dict[str, int] = field(default_factory=lambda: {
        "NASDAQ": 45,
        "NYSE": 52,
        "BATS": 38,
        "IEX": 350,
        "ARCA": 48,
    })
    smart_routing_enabled: bool = True
    dark_pool_enabled: bool = False


@dataclass
class MonitoringConfig:
    latency_histogram_buckets_us: List[int] = field(default_factory=lambda: [
        1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000, 10000,
    ])
    metrics_publish_interval_ms: float = 1000.0
    alert_tick_to_trade_us: int = 100
    alert_99th_percentile_us: int = 500
    max_latency_samples: int = 100_000


@dataclass
class HFTConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    orderbook: OrderBookConfig = field(default_factory=OrderBookConfig)
    fpga: FPGAConfig = field(default_factory=FPGAConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    co_location: str = "NY5"
    system_id: str = "HFT-CORE-001"
    simulation_mode: bool = True
    tick_rate_hz: int = 10000
