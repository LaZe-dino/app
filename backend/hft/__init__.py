"""
High-Frequency Trading Engine
═════════════════════════════
Sub-microsecond trading pipeline with:
  • Network Infrastructure — kernel-bypass NIC simulation, multicast feeds
  • In-Memory Order Book — lock-free, replicated across cores
  • Event-Driven Pipeline — lock-free queues with nanosecond timestamps
  • FPGA Acceleration — hardware-simulated decision engine
  • Market-Making Strategy — spread management, quote generation
  • Latency Arbitrage — cross-venue price discrepancy detection
  • Smart Order Router — optimal venue selection
  • Order Management System — full order lifecycle
  • Risk Engine — pre-trade checks in microseconds
  • Position Tracker — real-time P&L and exposure
  • Monitoring — tick-to-trade latency, 99th percentile tracking
"""

from .orchestrator import HFTOrchestrator

__all__ = ["HFTOrchestrator"]
