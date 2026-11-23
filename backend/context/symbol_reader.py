"""
Symbol Reader — AST-based extraction of functions, classes, and symbols from Python files.

Provides targeted source code extraction for symbols referenced in a PR diff,
and builds an assembled, token-budgeted context string for LLM review.
"""

from __future__ import annotations

import ast
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .dependency_resolver import resolve_dependencies

logger = logging.getLogger(__name__)


@dataclass
class SymbolContext:
    """Represents an extracted code symbol (function, class, or assignment)."""

    symbol_name: str
    symbol_type: str  # "function" | "class" | "variable"
    source_code: str
    start_line: int
    end_line: int
    file_path: str
    docstring: Optional[str] = None


def _get_docstring(node: ast.AST) -> Optional[str]:
    """Extract docstring from an AST node if present."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return ast.get_docstring(node)
    return None


def _slice_source_lines(lines: list[str], start_line: int, end_line: int) -> str:
    """Slice lines from 1-based start_line to end_line inclusive."""
    # lines list is 0-indexed, line numbers are 1-indexed
    s_idx = max(0, start_line - 1)
    e_idx = min(len(lines), end_line)
    return "".join(lines[s_idx:e_idx])


def read_symbol_context(file_path: str, symbol_name: str) -> Optional[SymbolContext]:
    """Extract a specific function, async function, or class from a file.

    Args:
        file_path: Path to the Python file.
        symbol_name: Name of the function or class to find.

    Returns:
        SymbolContext if found, or None.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        logger.warning("File not found: %s", abs_path)
        return None

    try:
        source = Path(abs_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=abs_path)
    except Exception as exc:
        logger.warning("Could not parse %s: %s", abs_path, exc)
        return None

    lines = source.splitlines(keepends=True)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol_name:
                sym_type = "class" if isinstance(node, ast.ClassDef) else "function"
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                code = _slice_source_lines(lines, start, end)
                return SymbolContext(
                    symbol_name=node.name,
                    symbol_type=sym_type,
                    source_code=code,
                    start_line=start,
                    end_line=end,
                    file_path=abs_path,
                    docstring=_get_docstring(node),
                )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol_name:
                    start = node.lineno
                    end = getattr(node, "end_lineno", start)
                    code = _slice_source_lines(lines, start, end)
                    return SymbolContext(
                        symbol_name=symbol_name,
                        symbol_type="variable",
                        source_code=code,
                        start_line=start,
                        end_line=end,
                        file_path=abs_path,
                        docstring=None,
                    )

    return None


def extract_all_symbols(file_path: str) -> list[SymbolContext]:
    """Extract all top-level functions and classes from a Python file.

    Args:
        file_path: Path to the Python file.

    Returns:
        List of SymbolContext for each top-level definition.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        source = Path(abs_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=abs_path)
    except Exception as exc:
        logger.warning("Could not parse %s: %s", abs_path, exc)
        return []

    lines = source.splitlines(keepends=True)
    symbols: list[SymbolContext] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            sym_type = "class" if isinstance(node, ast.ClassDef) else "function"
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            code = _slice_source_lines(lines, start, end)
            symbols.append(
                SymbolContext(
                    symbol_name=node.name,
                    symbol_type=sym_type,
                    source_code=code,
                    start_line=start,
                    end_line=end,
                    file_path=abs_path,
                    docstring=_get_docstring(node),
                )
            )

    return symbols


def build_context_for_diff(
    diff_files: list[str],
    repo_root: str,
    token_budget: int = 4000,
) -> str:
    """Assemble a surgical context string for the files modified in a diff.

    1. Resolves direct module dependencies of the changed files.
    2. Reads top-level symbol signatures and docstrings/definitions from direct dependencies.
    3. Keeps total context within token_budget (1 token ≈ 4 characters).

    Args:
        diff_files: List of paths (relative or absolute) of files in the diff.
        repo_root: Absolute path to the repository root.
        token_budget: Maximum tokens allocated for dependency context.

    Returns:
        Formatted context string ready for LLM prompt insertion.
    """
    char_budget = token_budget * 4
    repo_root = os.path.abspath(repo_root)

    # 1. Resolve direct dependencies
    dep_paths = resolve_dependencies(diff_files, repo_root)

    sections: list[str] = []
    current_chars = 0

    sections.append("### DIRECT DEPENDENCY CONTEXT (Surgically Bound):")

    if not dep_paths:
        sections.append("No local repository dependencies detected for changed files.")
        return "\n".join(sections)

    for dep in dep_paths:
        rel_path = os.path.relpath(dep, repo_root)
        symbols = extract_all_symbols(dep)

        dep_header = f"\n#### File: `{rel_path}` (Direct Dependency)\n"
        sections.append(dep_header)
        current_chars += len(dep_header)

        if not symbols:
            # If no top-level classes/functions, include brief snippet
            try:
                snippet = Path(dep).read_text(encoding="utf-8")[:500]
                sections.append(f"```python\n{snippet}\n```\n")
                current_chars += len(snippet) + 20
            except Exception:
                pass
            continue

        for sym in symbols:
            sym_block = (
                f"# [{sym.symbol_type}] {sym.symbol_name} (lines {sym.start_line}-{sym.end_line})\n"
                f"```python\n{sym.source_code.strip()}\n```\n"
            )
            if current_chars + len(sym_block) > char_budget:
                sections.append("\n[Context truncated to remain within token budget]\n")
                return "\n".join(sections)

            sections.append(sym_block)
            current_chars += len(sym_block)

    return "\n".join(sections)
