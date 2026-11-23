"""Secret scanner gate — detects hardcoded secrets in diff text.

Scans unified diff output for common secret patterns (AWS keys, JWT tokens,
GitHub tokens, generic API keys, private keys, Slack tokens) and returns
findings with redacted matched text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """A single secret detected in the diff."""

    pattern_name: str
    matched_text: str  # redacted
    line_number: int
    file_path: str


# ---------------------------------------------------------------------------
# Secret patterns
# ---------------------------------------------------------------------------

# Each entry: (pattern_name, compiled regex)
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "AWS Access Key",
        re.compile(r"AKIA[0-9A-Z]{16}"),
    ),
    (
        "JWT Token",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}"),
    ),
    (
        "GitHub Token (ghp)",
        re.compile(r"ghp_[A-Za-z0-9]{36}"),
    ),
    (
        "GitHub Token (gho)",
        re.compile(r"gho_[A-Za-z0-9]{36}"),
    ),
    (
        "GitHub Token (ghu)",
        re.compile(r"ghu_[A-Za-z0-9]{36}"),
    ),
    (
        "GitHub Token (ghs)",
        re.compile(r"ghs_[A-Za-z0-9]{36}"),
    ),
    (
        "GitHub Token (ghr)",
        re.compile(r"ghr_[A-Za-z0-9]{36}"),
    ),
    (
        "OpenAI / Anthropic API Key",
        re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    ),
    (
        "Generic API Key/Secret",
        re.compile(
            r"(?i)(api[_-]?key|api[_-]?secret|access[_-]?token)"
            r"""\s*[=:]\s*['"][A-Za-z0-9_\-]{16,}['"]"""
        ),
    ),
    (
        "Private Key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    ),
    (
        "Slack Token",
        re.compile(r"xox[bpors]-[A-Za-z0-9\-]{10,}"),
    ),
]

# Regex to extract the current file path from a unified diff header
_DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redact(text: str, *, visible_chars: int = 4) -> str:
    """Return a redacted version of *text*, keeping only the first few chars."""
    if len(text) <= visible_chars:
        return "*" * len(text)
    return text[:visible_chars] + "*" * (len(text) - visible_chars)


def _current_file_for_line(diff_lines: list[str], line_idx: int) -> str:
    """Walk backwards from *line_idx* to find the most recent +++ header."""
    for i in range(line_idx, -1, -1):
        m = _DIFF_FILE_RE.match(diff_lines[i])
        if m:
            return m.group(1)
    return "<unknown>"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_secrets(diff_text: str) -> list[SecretFinding]:
    """Scan *diff_text* (unified diff) for hardcoded secrets.

    Only added lines (starting with ``+``, excluding the ``+++`` header)
    are inspected so that removed secrets are not flagged.

    Returns a list of :class:`SecretFinding` with redacted matched text.
    """
    findings: list[SecretFinding] = []
    lines = diff_text.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        # Only inspect added lines (skip the +++ file header)
        if not line.startswith("+") or line.startswith("+++"):
            continue

        for pattern_name, regex in _SECRET_PATTERNS:
            for match in regex.finditer(line):
                file_path = _current_file_for_line(lines, line_idx - 1)
                finding = SecretFinding(
                    pattern_name=pattern_name,
                    matched_text=_redact(match.group()),
                    line_number=line_idx,
                    file_path=file_path,
                )
                findings.append(finding)
                logger.warning(
                    "Secret detected: %s in %s at line %d",
                    pattern_name,
                    file_path,
                    line_idx,
                )

    logger.info("Secret scan complete — %d finding(s)", len(findings))
    return findings
