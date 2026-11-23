"""
Surgical context gathering - extracts only relevant code context.
Uses Python AST for import parsing and function extraction.
Respects the 4,000 token budget.
"""
import ast
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ContextResult:
    """Result from context gathering."""
    snippets: list[str]
    total_tokens: int
    files_included: list[str]


def gather_context(
    diff: str,
    files: list[str],
    repo_path: str = "sample_repo",
    token_budget: int = 4000
) -> ContextResult:
    """
    Gather surgical context for the PR review.
    
    Args:
        diff: Unified diff content
        files: List of changed file paths
        repo_path: Path to repository root
        token_budget: Maximum tokens to include
        
    Returns:
        ContextResult with selected code snippets
    """
    snippets = []
    files_included = []
    estimated_tokens = 0
    
    # Reserve tokens for the diff itself
    diff_tokens = estimate_tokens(diff)
    remaining_budget = token_budget - diff_tokens
    
    if remaining_budget <= 0:
        # Diff alone exceeds budget
        return ContextResult(
            snippets=[],
            total_tokens=min(diff_tokens, token_budget),
            files_included=[]
        )
    
    # Process each changed Python file
    for filepath in files:
        if not filepath.endswith('.py'):
            continue
            
        # Try multiple candidate paths for robustness
        candidates = [
            os.path.join(repo_path, filepath),
            os.path.join(repo_path, os.path.basename(filepath)),
            filepath,
            os.path.join(os.path.dirname(__file__), "..", repo_path, os.path.basename(filepath)),
            os.path.join(os.path.dirname(__file__), "..", "..", repo_path, os.path.basename(filepath)),
        ]
        full_path = next((c for c in candidates if os.path.exists(c)), None)
        if not full_path:
            continue
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract imports and related functions
            context_snippets = extract_relevant_context(content, filepath)
            
            for snippet in context_snippets:
                snippet_tokens = estimate_tokens(snippet)
                
                if estimated_tokens + snippet_tokens > remaining_budget:
                    # Budget exhausted
                    break
                
                snippets.append(snippet)
                estimated_tokens += snippet_tokens
                
                if filepath not in files_included:
                    files_included.append(filepath)
            
            if estimated_tokens >= remaining_budget:
                break
                
        except Exception as e:
            # Skip files that can't be read
            continue
    
    return ContextResult(
        snippets=snippets,
        total_tokens=diff_tokens + estimated_tokens,
        files_included=files_included
    )


def extract_relevant_context(content: str, filepath: str) -> list[str]:
    """
    Parse Python file and extract imports and function definitions.
    
    Returns list of code snippets (imports, function defs).
    """
    snippets = []
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Can't parse - return empty
        return []
    
    # Extract imports
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            names = ', '.join(alias.name for alias in node.names)
            imports.append(f"from {module} import {names}")
    
    if imports:
        snippets.append(f"# Imports from {filepath}\n" + "\n".join(imports))
    
    # Extract function and class definitions (signatures only)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_sig = extract_function_signature(node, content)
            if func_sig:
                snippets.append(func_sig)
        elif isinstance(node, ast.ClassDef):
            class_sig = extract_class_signature(node, content)
            if class_sig:
                snippets.append(class_sig)
    
    return snippets


def extract_function_signature(node: ast.FunctionDef, content: str) -> Optional[str]:
    """Extract function signature and docstring."""
    try:
        lines = content.split('\n')
        start_line = node.lineno - 1
        
        # Get function definition line(s)
        sig_lines = []
        for i in range(start_line, min(start_line + 5, len(lines))):
            sig_lines.append(lines[i])
            if ':' in lines[i]:
                break
        
        # Get docstring if present
        docstring = ast.get_docstring(node)
        if docstring:
            # Include first line of docstring
            first_doc_line = docstring.split('\n')[0]
            sig_lines.append(f'    """{first_doc_line}"""')
        
        return '\n'.join(sig_lines)
    except Exception:
        return None


def extract_class_signature(node: ast.ClassDef, content: str) -> Optional[str]:
    """Extract class signature and docstring."""
    try:
        lines = content.split('\n')
        start_line = node.lineno - 1
        
        # Get class definition line
        sig_lines = [lines[start_line]]
        
        # Get docstring if present
        docstring = ast.get_docstring(node)
        if docstring:
            first_doc_line = docstring.split('\n')[0]
            sig_lines.append(f'    """{first_doc_line}"""')
        
        return '\n'.join(sig_lines)
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation: ~4 characters per token for English code.
    This is a conservative estimate.
    """
    return len(text) // 4
