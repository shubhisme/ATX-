"""Gate runner — orchestrator that runs all deterministic gates.

Provides :func:`run_static_gates`, the single entry-point that the API layer
calls.  It fans out to the secret scanner and syntax checker, collects their
results, and returns a unified :class:`GateResult`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from .secret_scanner import SecretFinding, scan_secrets
from .syntax_checker import SyntaxResult, check_syntax

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GateCheckResult:
    """Result of a single gate check (e.g. secret scan or syntax check)."""

    check_type: str  # "secret_scan" | "syntax_check"
    passed: bool
    details: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass(slots=True)
class GateResult:
    """Aggregated result of all deterministic gates."""

    passed: bool
    checks: list[GateCheckResult] = field(default_factory=list)
    duration_ms: float = 0.0
    failed_checks: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding_to_dict(f: SecretFinding) -> dict:
    """Serialise a :class:`SecretFinding` to a plain dict."""
    return {
        "pattern_name": f.pattern_name,
        "matched_text": f.matched_text,
        "line_number": f.line_number,
        "file_path": f.file_path,
    }


def _syntax_result_to_dict(r: SyntaxResult) -> dict:
    """Serialise a :class:`SyntaxResult` to a plain dict."""
    return {
        "file_path": r.file_path,
        "valid": r.valid,
        "error_message": r.error_message,
        "line_number": r.line_number,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_static_gates(
    diff_text: str,
    changed_files: list[dict],
) -> GateResult:
    """Run all deterministic gates against a PR diff.

    Args:
        diff_text: The full unified diff text of the PR.
        changed_files: A list of dicts with keys ``"path"`` (``str``) and
            ``"content"`` (``str``) for every changed file.

    Returns:
        A :class:`GateResult` summarising pass/fail and individual check
        results.
    """
    overall_start = time.perf_counter()
    checks: list[GateCheckResult] = []
    failed_checks: list[str] = []

    # ---- 1. Secret scan --------------------------------------------------
    secret_start = time.perf_counter()
    findings: list[SecretFinding] = scan_secrets(diff_text)
    secret_duration = (time.perf_counter() - secret_start) * 1000

    secret_passed = len(findings) == 0
    secret_check = GateCheckResult(
        check_type="secret_scan",
        passed=secret_passed,
        details=[_finding_to_dict(f) for f in findings],
        duration_ms=round(secret_duration, 3),
    )
    checks.append(secret_check)
    if not secret_passed:
        failed_checks.append("secret_scan")
        logger.warning("Secret scan FAILED — %d secret(s) found", len(findings))
    else:
        logger.info("Secret scan passed")

    # ---- 2. Syntax check -------------------------------------------------
    syntax_start = time.perf_counter()
    syntax_details: list[dict] = []
    syntax_passed = True

    for file_info in changed_files:
        path: str = file_info.get("path", "")
        content: str = file_info.get("content", "")

        # Only check Python files
        if not path.endswith(".py"):
            continue

        result: SyntaxResult = check_syntax(path, content)
        syntax_details.append(_syntax_result_to_dict(result))
        if not result.valid:
            syntax_passed = False

    syntax_duration = (time.perf_counter() - syntax_start) * 1000

    syntax_check = GateCheckResult(
        check_type="syntax_check",
        passed=syntax_passed,
        details=syntax_details,
        duration_ms=round(syntax_duration, 3),
    )
    checks.append(syntax_check)
    if not syntax_passed:
        failed_checks.append("syntax_check")
        logger.warning("Syntax check FAILED")
    else:
        logger.info("Syntax check passed")

    # ---- Aggregate -------------------------------------------------------
    overall_duration = (time.perf_counter() - overall_start) * 1000
    passed = len(failed_checks) == 0

    gate_result = GateResult(
        passed=passed,
        checks=checks,
        duration_ms=round(overall_duration, 3),
        failed_checks=failed_checks,
    )

    logger.info(
        "Static gates %s in %.1f ms (%d check(s), %d failed)",
        "PASSED" if passed else "FAILED",
        overall_duration,
        len(checks),
        len(failed_checks),
    )
    return gate_result
