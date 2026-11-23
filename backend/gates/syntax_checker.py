"""Syntax checker gate — validates Python syntax of changed files.

Uses the built-in :mod:`ast` module to parse Python source and report any
syntax errors, including the offending line number and error message.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SyntaxResult:
    """Result of a syntax check on a single file."""

    file_path: str
    valid: bool
    error_message: str | None = None
    line_number: int | None = None


# ---------------------------------------------------------------------------
# Diff parsing helpers
# ---------------------------------------------------------------------------

# Matches the +++ header in a unified diff to extract the file path
_DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def _extract_python_files_from_diff(
    diff_text: str,
) -> list[tuple[str, str]]:
    """Extract full added content of ``.py`` files from a unified diff.

    Returns a list of ``(file_path, reconstructed_content)`` tuples.  The
    content is built from added lines only (``+`` prefix stripped), which is
    a reasonable approximation for newly-added files.  For modified files
    the caller should prefer :func:`check_syntax` with the actual file
    content when available.
    """
    files: list[tuple[str, str]] = []
    current_path: str | None = None
    current_lines: list[str] = []

    for line in diff_text.splitlines():
        header_match = _DIFF_FILE_RE.match(line)
        if header_match:
            # Flush previous file
            if current_path and current_path.endswith(".py") and current_lines:
                files.append((current_path, "\n".join(current_lines)))
            current_path = header_match.group(1)
            current_lines = []
            continue

        if current_path and current_path.endswith(".py"):
            if line.startswith("+") and not line.startswith("+++"):
                current_lines.append(line[1:])  # strip leading '+'

    # Flush last file
    if current_path and current_path.endswith(".py") and current_lines:
        files.append((current_path, "\n".join(current_lines)))

    return files


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_syntax(file_path: str, content: str) -> SyntaxResult:
    """Check whether *content* is valid Python syntax.

    Args:
        file_path: Path of the file (used for reporting only).
        content: The full Python source text to validate.

    Returns:
        A :class:`SyntaxResult` indicating validity and any error details.
    """
    try:
        ast.parse(content, filename=file_path)
    except SyntaxError as exc:
        logger.info("Syntax error in %s line %s: %s", file_path, exc.lineno, exc.msg)
        return SyntaxResult(
            file_path=file_path,
            valid=False,
            error_message=exc.msg,
            line_number=exc.lineno,
        )

    logger.debug("Syntax OK: %s", file_path)
    return SyntaxResult(file_path=file_path, valid=True)


def check_syntax_from_diff(diff_text: str) -> list[SyntaxResult]:
    """Extract added Python files from a unified diff and check each.

    This is a convenience wrapper that combines diff parsing with
    :func:`check_syntax`.  It returns one :class:`SyntaxResult` per
    ``.py`` file found in the diff.
    """
    extracted = _extract_python_files_from_diff(diff_text)
    results: list[SyntaxResult] = []
    for path, content in extracted:
        results.append(check_syntax(path, content))

    logger.info(
        "Syntax check from diff complete — %d file(s) checked, %d error(s)",
        len(results),
        sum(1 for r in results if not r.valid),
    )
    return results
