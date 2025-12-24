"""
Pre-Paper Package

Enables live strategy execution using Backtest-Atom promotion contract.

CRITICAL INVARIANTS:
- Data segregation (no backtest parquet writes)
- Manifest SSOT (promotion contract)
- NO-SIGNALS when history insufficient
- Auditability (pre_paper artifacts)
"""

__version__ = "0.1.0"
