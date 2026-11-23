"""Deterministic gate layer for the PR verification engine.

This package exposes :func:`run_static_gates` as the single entry-point
for running all deterministic checks (secret scanning, syntax validation)
against a pull-request diff.
"""

from .gate_runner import GateResult, GateCheckResult, run_static_gates

__all__ = ["run_static_gates", "GateResult", "GateCheckResult"]
