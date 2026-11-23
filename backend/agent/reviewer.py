"""
Groq-powered AI code review agent.
Sends diff + surgical context to Groq and returns structured findings.
"""
import json
from dataclasses import dataclass
from typing import Optional
from groq import Groq
from config import GROQ_API_KEY


@dataclass
class Finding:
    """Single review finding."""
    severity: str  # "critical", "warning", "info"
    file: str
    line: Optional[int]
    message: str
    suggestion: Optional[str]


@dataclass
class ReviewResult:
    """Result from AI review."""
    findings: list[Finding]
    summary: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


# Groq pricing (as of latest known rates)
# llama-3.3-70b-versatile: $0.59/1M input, $0.79/1M output
MODEL_NAME = "llama-3.3-70b-versatile"
COST_PER_MILLION_INPUT = 0.59
COST_PER_MILLION_OUTPUT = 0.79


def review_pr(diff: str, context_snippets: list[str], title: str) -> ReviewResult:
    """
    Send PR diff and context to Groq for AI review.
    
    Args:
        diff: Unified diff content
        context_snippets: Surgical context from context engine
        title: PR title for context
        
    Returns:
        ReviewResult with findings and telemetry
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not configured")
    
    client = Groq(api_key=GROQ_API_KEY)
    
    # Build the review prompt
    prompt = build_review_prompt(diff, context_snippets, title)
    
    # Call Groq API
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert code reviewer. Analyze the provided PR diff and context. "
                    "Identify bugs, security issues, performance problems, and code quality concerns. "
                    "Return your findings in JSON format with this structure:\n"
                    "{\n"
                    '  "findings": [\n'
                    "    {\n"
                    '      "severity": "critical|warning|info",\n'
                    '      "file": "path/to/file.py",\n'
                    '      "line": 42,\n'
                    '      "message": "Description of the issue",\n'
                    '      "suggestion": "How to fix it"\n'
                    "    }\n"
                    "  ],\n"
                    '  "summary": "Overall assessment of the PR"\n'
                    "}\n"
                    "Be concise but thorough. Focus on real issues, not nitpicks."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    
    # Extract token usage
    usage = response.usage
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    
    # Calculate cost
    cost_usd = calculate_cost(prompt_tokens, completion_tokens)
    
    # Parse the response
    content = response.choices[0].message.content
    
    try:
        # Try to extract JSON from response
        review_data = extract_json(content)
        findings_list = review_data.get("findings", [])
        summary = review_data.get("summary", "Review completed")
        
        findings = [
            Finding(
                severity=f.get("severity", "info"),
                file=f.get("file", "unknown"),
                line=f.get("line"),
                message=f.get("message", ""),
                suggestion=f.get("suggestion")
            )
            for f in findings_list
        ]
    except Exception as e:
        # Fallback if JSON parsing fails
        findings = [
            Finding(
                severity="info",
                file="general",
                line=None,
                message=content[:500],  # First 500 chars
                suggestion=None
            )
        ]
        summary = "Review completed (parsing issue)"
    
    return ReviewResult(
        findings=findings,
        summary=summary,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd
    )


def build_review_prompt(diff: str, context_snippets: list[str], title: str) -> str:
    """Build the review prompt from diff and context."""
    prompt_parts = [
        f"# PR Title: {title}",
        "",
        "## Changed Code (Diff):",
        "```diff",
        diff,
        "```",
        "",
    ]
    
    if context_snippets:
        prompt_parts.extend([
            "## Relevant Context:",
            "```python",
            "\n\n".join(context_snippets),
            "```",
            "",
        ])
    
    prompt_parts.append("Please review this PR and provide structured findings.")
    
    return "\n".join(prompt_parts)


def extract_json(content: str) -> dict:
    """Extract JSON from LLM response (handles markdown code blocks)."""
    # Remove markdown code blocks if present
    content = content.strip()
    
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    
    if content.endswith("```"):
        content = content[:-3]
    
    content = content.strip()
    
    return json.loads(content)


def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost based on Groq pricing."""
    input_cost = (prompt_tokens / 1_000_000) * COST_PER_MILLION_INPUT
    output_cost = (completion_tokens / 1_000_000) * COST_PER_MILLION_OUTPUT
    return round(input_cost + output_cost, 6)
