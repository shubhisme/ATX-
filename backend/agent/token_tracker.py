"""
Token counting and cost calculation for LLM API requests.

Provides approximate token counting and cost estimation for Groq API calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Pricing per token (USD).  Groq free-tier models currently charge $0.00;
# keep the constants so we can update them when pricing changes.
PRICING: dict[str, dict[str, float]] = {
    "compound-beta": {"input": 0.0, "output": 0.0},
    "gpt-oss-120b": {"input": 0.0, "output": 0.0},
    # Fallback for unknown models
    "_default": {"input": 0.0, "output": 0.0},
}


@dataclass
class TokenUsage:
    """Token usage statistics for a single API request."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model: str


class TokenTracker:
    """Tracks token usage and estimates costs for LLM API calls.

    Args:
        model_name: The model identifier used for pricing lookup.
    """

    def __init__(self, model_name: str = "gpt-oss-120b") -> None:
        self.model_name = model_name
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._total_cost: float = 0.0
        self._request_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        """Return an approximate token count for *text*.

        Uses the common heuristic of 1 token ≈ 4 characters.
        """
        return max(1, len(text) // 4)

    def calculate_cost(
        self, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate the estimated cost in USD for the given token counts."""
        rates = PRICING.get(self.model_name, PRICING["_default"])
        cost = (input_tokens * rates["input"]) + (
            output_tokens * rates["output"]
        )
        return round(cost, 8)

    def track_request(
        self,
        input_text: str,
        output_text: str,
        *,
        api_input_tokens: Optional[int] = None,
        api_output_tokens: Optional[int] = None,
    ) -> TokenUsage:
        """Record a completed request and return its :class:`TokenUsage`.

        If the Groq API returned actual token counts (via
        ``response.usage``), pass them as *api_input_tokens* /
        *api_output_tokens* to get precise numbers.  Otherwise the
        counts are estimated from text length.
        """
        in_tokens = (
            api_input_tokens
            if api_input_tokens is not None
            else self.count_tokens(input_text)
        )
        out_tokens = (
            api_output_tokens
            if api_output_tokens is not None
            else self.count_tokens(output_text)
        )
        cost = self.calculate_cost(in_tokens, out_tokens)

        # Accumulate session totals
        self._total_input_tokens += in_tokens
        self._total_output_tokens += out_tokens
        self._total_cost += cost
        self._request_count += 1

        usage = TokenUsage(
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=in_tokens + out_tokens,
            estimated_cost_usd=cost,
            model=self.model_name,
        )

        logger.debug(
            "Token usage — in: %d, out: %d, cost: $%.6f, model: %s",
            in_tokens,
            out_tokens,
            cost,
            self.model_name,
        )
        return usage

    # ------------------------------------------------------------------
    # Session statistics
    # ------------------------------------------------------------------

    @property
    def total_input_tokens(self) -> int:
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._total_output_tokens

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def request_count(self) -> int:
        return self._request_count

    def __repr__(self) -> str:
        return (
            f"TokenTracker(model={self.model_name!r}, "
            f"requests={self._request_count}, "
            f"tokens={self._total_input_tokens + self._total_output_tokens}, "
            f"cost=${self._total_cost:.6f})"
        )
