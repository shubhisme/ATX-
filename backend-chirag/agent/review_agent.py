"""
Core LLM review agent that calls Groq's API to review PR diffs.

Uses the ``groq`` Python SDK with an async client to send the diff and
repository context to the model and parse structured review findings.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from groq import AsyncGroq, RateLimitError, APIError, APITimeoutError

from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .token_tracker import TokenTracker, TokenUsage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

VALID_SEVERITIES = frozenset({"critical", "warning", "info", "suggestion"})
VALID_CATEGORIES = frozenset({"bug", "security", "performance", "style", "logic"})


@dataclass
class ReviewFinding:
    """A single issue found during the code review."""

    file_path: str
    line_number: Optional[int]
    severity: str  # "critical" | "warning" | "info" | "suggestion"
    category: str  # "bug" | "security" | "performance" | "style" | "logic"
    message: str
    suggestion: Optional[str] = None


@dataclass
class ReviewResult:
    """Aggregated result of a PR review."""

    findings: list[ReviewFinding]
    summary: str
    token_usage: TokenUsage
    latency_ms: float
    model: str
    cached: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_severity(value: str) -> str:
    """Normalise severity to an allowed value, defaulting to 'info'."""
    v = value.strip().lower()
    return v if v in VALID_SEVERITIES else "info"


def _sanitize_category(value: str) -> str:
    """Normalise category to an allowed value, defaulting to 'style'."""
    v = value.strip().lower()
    return v if v in VALID_CATEGORIES else "style"


def _parse_findings(raw_findings: list[dict]) -> list[ReviewFinding]:
    """Convert a list of dicts from the LLM response into ReviewFinding objects."""
    findings: list[ReviewFinding] = []
    for item in raw_findings:
        try:
            findings.append(
                ReviewFinding(
                    file_path=str(item.get("file_path", "unknown")),
                    line_number=item.get("line_number"),
                    severity=_sanitize_severity(
                        str(item.get("severity", "info"))
                    ),
                    category=_sanitize_category(
                        str(item.get("category", "style"))
                    ),
                    message=str(item.get("message", "")),
                    suggestion=item.get("suggestion"),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping malformed finding %r: %s", item, exc)
    return findings


def _extract_json(text: str) -> dict:
    """Try to parse JSON from *text*, stripping markdown fences if present."""
    cleaned = text.strip()
    # Strip ```json ... ``` wrappers
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n") if "\n" in cleaned else 3
        cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def review_pr(
    diff_text: str,
    context: str,
    changed_files: list[str],
) -> ReviewResult:
    """Send a PR diff to the Groq LLM for review and return structured findings.

    Args:
        diff_text: Unified diff of the pull request.
        context: Relevant repository context assembled by the context engine.
        changed_files: List of file paths that were changed.

    Returns:
        A :class:`ReviewResult` with findings, summary, token usage, and timing.

    Raises:
        RateLimitError: Re-raised so the upstream worker can implement retry/backoff.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        logger.error("GROQ_API_KEY is not set in the environment")
        return _error_result("GROQ_API_KEY environment variable is not set.")

    model = os.environ.get("GROQ_MODEL", "compound-beta")
    tracker = TokenTracker(model_name=model)

    user_message = USER_PROMPT_TEMPLATE.format(
        diff=diff_text,
        context=context,
        changed_files="\n".join(f"- {f}" for f in changed_files),
    )

    client = AsyncGroq(api_key=api_key)
    start = time.perf_counter()

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
    except RateLimitError:
        logger.warning("Groq rate limit hit — raising for retry by worker")
        raise
    except APITimeoutError as exc:
        logger.error("Groq API timeout: %s", exc)
        return _error_result(f"Groq API timeout: {exc}", model=model)
    except APIError as exc:
        logger.error("Groq API error: %s", exc)
        return _error_result(f"Groq API error: {exc}", model=model)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error calling Groq API")
        return _error_result(f"Unexpected error: {exc}", model=model)

    elapsed_ms = (time.perf_counter() - start) * 1000
    raw_content = response.choices[0].message.content or ""

    # Use API-reported token counts when available
    api_in = getattr(response.usage, "prompt_tokens", None) if response.usage else None
    api_out = (
        getattr(response.usage, "completion_tokens", None)
        if response.usage
        else None
    )

    input_text = SYSTEM_PROMPT + user_message
    token_usage = tracker.track_request(
        input_text,
        raw_content,
        api_input_tokens=api_in,
        api_output_tokens=api_out,
    )

    # Parse the LLM JSON response
    try:
        data = _extract_json(raw_content)
        findings = _parse_findings(data.get("findings", []))
        summary = str(data.get("summary", "No summary provided."))
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning(
            "Failed to parse LLM response as JSON (%s); wrapping as info finding",
            exc,
        )
        findings = [
            ReviewFinding(
                file_path="N/A",
                line_number=None,
                severity="info",
                category="style",
                message=raw_content[:2000],
                suggestion=None,
            )
        ]
        summary = "LLM response could not be parsed as structured JSON."

    return ReviewResult(
        findings=findings,
        summary=summary,
        token_usage=token_usage,
        latency_ms=round(elapsed_ms, 2),
        model=model,
        cached=False,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _error_result(
    message: str, *, model: str = "unknown"
) -> ReviewResult:
    """Build a ReviewResult representing an error state."""
    dummy_usage = TokenUsage(
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        estimated_cost_usd=0.0,
        model=model,
    )
    return ReviewResult(
        findings=[
            ReviewFinding(
                file_path="N/A",
                line_number=None,
                severity="critical",
                category="bug",
                message=message,
                suggestion=None,
            )
        ],
        summary=f"Review failed: {message}",
        token_usage=dummy_usage,
        latency_ms=0.0,
        model=model,
        cached=False,
    )
