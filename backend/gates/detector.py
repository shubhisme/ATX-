"""
Deterministic checks: secret detection and Python syntax validation.
Runs before LLM review to reject PRs with obvious issues.
"""
import re
import ast
from dataclasses import dataclass
from typing import Optional


@dataclass
class GateResult:
    """Result from running deterministic gate checks."""
    passed: bool
    errors: list[str]
    warnings: list[str]
    

# Secret patterns - 11 types as per requirements
SECRET_PATTERNS = {
    "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "AWS Secret Key": re.compile(r"(?i)aws(.{0,20})?['\"][0-9a-zA-Z/+]{40}['\"]"),
    "GitHub Token": re.compile(r"ghp_[0-9a-zA-Z]{36}"),
    "Generic API Key": re.compile(r"(?i)(api[_-]?key|apikey)[\s]*[=:]['\"]\s*[0-9a-zA-Z]{20,}"),
    "Private Key": re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    "Google API Key": re.compile(r"AIza[0-9A-Za-z\\-_]{35}"),
    "Slack Token": re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
    "Stripe Key": re.compile(r"(?i)(sk|pk)_(test|live)_[0-9a-zA-Z]{24,}"),
    "Database Password": re.compile(r"(?i)(password|passwd|pwd)[\s]*[=:]['\"]\s*[^\s'\";]{6,}"),
    "JWT Token": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "Twilio Auth": re.compile(r"SK[0-9a-fA-F]{32}"),
}


def run_gate(diff: str, files: list[str]) -> GateResult:
    """
    Run all deterministic checks on the PR.
    
    Args:
        diff: Unified diff content
        files: List of changed file paths
        
    Returns:
        GateResult with pass/fail status and detected issues
    """
    errors = []
    warnings = []
    
    # 1. Secret detection
    secret_errors = detect_secrets(diff)
    errors.extend(secret_errors)
    
    # 2. Python syntax validation for .py files
    python_files = [f for f in files if f.endswith('.py')]
    for filepath in python_files:
        syntax_error = check_python_syntax(diff, filepath)
        if syntax_error:
            errors.append(syntax_error)
    
    # 3. Additional checks can be added here
    # - Large file detection
    # - Binary file warning
    # - etc.
    
    passed = len(errors) == 0
    
    return GateResult(
        passed=passed,
        errors=errors,
        warnings=warnings
    )


def detect_secrets(content: str) -> list[str]:
    """
    Scan content for secret patterns.
    
    Returns list of error messages for detected secrets.
    """
    detected = []
    
    for secret_type, pattern in SECRET_PATTERNS.items():
        matches = pattern.findall(content)
        if matches:
            detected.append(
                f"Potential {secret_type} detected in diff. "
                f"Remove secrets before submitting."
            )
    
    return detected


def check_python_syntax(diff: str, filepath: str) -> Optional[str]:
    """
    Extract added Python code from diff and validate syntax.
    
    Returns error message if syntax is invalid, None otherwise.
    """
    # Extract added lines (lines starting with '+')
    added_lines = []
    for line in diff.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            # Remove the '+' prefix
            added_lines.append(line[1:])
    
    if not added_lines:
        return None
    
    # Try to parse the added code
    code = '\n'.join(added_lines)
    
    # Skip if it's just empty lines or comments
    code_stripped = '\n'.join(
        line for line in added_lines 
        if line.strip() and not line.strip().startswith('#')
    )
    
    if not code_stripped:
        return None
    
    try:
        ast.parse(code_stripped)
        return None
    except SyntaxError as e:
        return (
            f"Python syntax error in {filepath}: "
            f"{e.msg} at line {e.lineno}"
        )
    except Exception:
        # If we can't parse partial code, that's okay
        # (might be incomplete context)
        return None
