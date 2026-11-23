"""
Context Engine — Dependency and symbol extraction for surgical context bounding.
"""

from .dependency_resolver import (
    ImportedSymbol,
    extract_files_from_diff,
    get_imported_symbols,
    resolve_dependencies,
)
from .symbol_reader import (
    SymbolContext,
    build_context_for_diff,
    extract_all_symbols,
    read_symbol_context,
)

__all__ = [
    "ImportedSymbol",
    "extract_files_from_diff",
    "get_imported_symbols",
    "resolve_dependencies",
    "SymbolContext",
    "read_symbol_context",
    "extract_all_symbols",
    "build_context_for_diff",
]
