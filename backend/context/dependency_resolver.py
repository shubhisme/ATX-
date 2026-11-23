"""
Dependency Resolver — Parses Python files to find import dependencies.

Extracts import statements from changed files using the AST module and
resolves them to file paths within the repository. Used by the context
engine to determine which related files need to be included for LLM
analysis.
"""

from __future__ import annotations

import ast
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ImportedSymbol:
    """Represents a single import statement parsed from a Python file."""

    module: str
    names: list[str] = field(default_factory=list)
    is_relative: bool = False
    resolved_path: Optional[str] = None


def _module_to_possible_paths(module: str, repo_root: str) -> list[str]:
    """Convert a dotted module name to candidate file paths within the repo.

    Args:
        module: Dotted module path, e.g. ``'sample_repo.utils'``.
        repo_root: Absolute path to the repository root.

    Returns:
        List of candidate absolute file paths (``module.py`` and
        ``module/__init__.py``).
    """
    parts = module.split(".")
    base = os.path.join(repo_root, *parts)
    return [
        base + ".py",
        os.path.join(base, "__init__.py"),
    ]


def _resolve_relative_import(
    importing_file: str,
    module: str | None,
    level: int,
    repo_root: str,
) -> list[str]:
    """Resolve a relative import to candidate absolute file paths.

    Args:
        importing_file: The file that contains the import statement.
        module: The module portion after the dots (may be ``None`` for
            bare ``from . import X``).
        level: Number of leading dots (1 for ``.``, 2 for ``..``, etc.).
        repo_root: Absolute path to the repository root.

    Returns:
        List of candidate absolute file paths.
    """
    importing_dir = os.path.dirname(os.path.abspath(importing_file))
    # Walk up `level - 1` directories (level 1 = same package)
    base_dir = importing_dir
    for _ in range(level - 1):
        base_dir = os.path.dirname(base_dir)

    if module:
        parts = module.split(".")
        base = os.path.join(base_dir, *parts)
    else:
        base = base_dir

    return [
        base + ".py",
        os.path.join(base, "__init__.py"),
    ]


def get_imported_symbols(file_path: str) -> list[ImportedSymbol]:
    """Parse a Python file and return all import statements.

    Args:
        file_path: Absolute path to a ``.py`` file.

    Returns:
        List of :class:`ImportedSymbol` dataclass instances.  Returns an
        empty list if the file cannot be read or parsed.
    """
    abs_path = os.path.abspath(file_path)

    if not os.path.isfile(abs_path):
        logger.warning("File not found, skipping: %s", abs_path)
        return []

    try:
        source = Path(abs_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read %s: %s", abs_path, exc)
        return []

    try:
        tree = ast.parse(source, filename=abs_path)
    except SyntaxError as exc:
        logger.warning("Syntax error in %s: %s", abs_path, exc)
        return []

    symbols: list[ImportedSymbol] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                symbols.append(
                    ImportedSymbol(
                        module=alias.name,
                        names=[alias.asname or alias.name],
                        is_relative=False,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            is_relative = (node.level or 0) > 0
            names = [alias.name for alias in node.names]
            symbols.append(
                ImportedSymbol(
                    module=module_name,
                    names=names,
                    is_relative=is_relative,
                )
            )

    return symbols


def _resolve_symbol_path(
    symbol: ImportedSymbol,
    importing_file: str,
    repo_root: str,
) -> str | None:
    """Try to resolve an :class:`ImportedSymbol` to an on-disk file path.

    Returns the resolved path or ``None`` if the import does not point to
    a file inside the repository (e.g. stdlib or third-party package).
    """
    if symbol.is_relative:
        # ast.ImportFrom stores level; we recover it from the dataclass
        # via a re-parse shortcut: we already know it's relative, so we
        # attempt level-1 resolution (same package) first.
        candidates = _resolve_relative_import(
            importing_file, symbol.module or None, level=1, repo_root=repo_root
        )
    else:
        candidates = _module_to_possible_paths(symbol.module, repo_root)

    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.normpath(candidate)
    return None


def resolve_dependencies(
    changed_files: list[str],
    repo_root: str,
) -> list[str]:
    """Return deduplicated list of files that *changed_files* import from.

    Only direct dependencies are returned — i.e. the files that the
    changed files import, **not** the entire transitive closure.

    Args:
        changed_files: Paths (absolute or relative to *repo_root*) of
            files that changed in the PR.
        repo_root: Absolute path to the repository root.

    Returns:
        Sorted, deduplicated list of absolute file paths that the
        changed files depend on.  The changed files themselves are
        excluded from the result.
    """
    repo_root = os.path.abspath(repo_root)
    seen: set[str] = set()
    dependencies: set[str] = set()

    # Normalise changed file paths
    normalised_changed: set[str] = set()
    for f in changed_files:
        abs_f = os.path.normpath(
            f if os.path.isabs(f) else os.path.join(repo_root, f)
        )
        normalised_changed.add(abs_f)

    for file_path in normalised_changed:
        if file_path in seen:
            continue
        seen.add(file_path)

        if not file_path.endswith(".py"):
            logger.debug("Skipping non-Python file: %s", file_path)
            continue

        logger.debug("Resolving imports for: %s", file_path)
        symbols = get_imported_symbols(file_path)

        for sym in symbols:
            resolved = _resolve_symbol_path(sym, file_path, repo_root)
            if resolved:
                sym.resolved_path = resolved
                # Exclude files that are themselves changed — they're
                # already part of the diff.
                if resolved not in normalised_changed:
                    dependencies.add(resolved)
                logger.debug(
                    "  %s -> %s", sym.module or "(relative)", resolved
                )
            else:
                logger.debug(
                    "  %s -> (external / not found)", sym.module or "(relative)"
                )

    result = sorted(dependencies)
    logger.info(
        "Resolved %d dependencies for %d changed files",
        len(result),
        len(changed_files),
    )
    return result
