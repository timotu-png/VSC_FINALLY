"""LLM client using LiteLLM + OpenRouter + Cerebras inference."""

# DEPENDENCIES REQUIRED: litellm>=1.0.0, pydantic>=2.0.0
# (Backend API Engineer adds these to pyproject.toml)

import asyncio
import json
import os

from litellm import completion

from .mock import mock_response
from .models import LLMResponse

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

SYSTEM_PROMPT_TEMPLATE = """You are FinAlly, an AI trading assistant. You help users analyze their portfolio and execute trades.

Current portfolio context:
- Cash balance: ${cash_balance:,.2f}
- Total portfolio value: ${total_value:,.2f}
- Positions: {position_count} holdings
- Positions detail: {positions_json}
- Watchlist: {watchlist_tickers}

Instructions:
- Analyze portfolio composition, risk, and P&L when relevant
- Suggest trades with clear reasoning
- Execute trades when the user asks or agrees
- Be concise and data-driven
- Always respond with valid JSON matching the required schema"""


def _build_system_message(portfolio_context: dict) -> str:
    """Construct the system message with injected portfolio context."""
    cash_balance = portfolio_context.get("cash_balance", 0.0)
    total_value = portfolio_context.get("total_value", cash_balance)
    positions = portfolio_context.get("positions", [])
    position_count = len(positions)
    positions_json = json.dumps(positions, indent=2)
    watchlist = portfolio_context.get("watchlist", [])
    watchlist_tickers = ", ".join(watchlist) if watchlist else "none"

    return SYSTEM_PROMPT_TEMPLATE.format(
        cash_balance=cash_balance,
        total_value=total_value,
        position_count=position_count,
        positions_json=positions_json,
        watchlist_tickers=watchlist_tickers,
    )


class LLMClient:
    """Main LLM client.

    Uses mock mode when LLM_MOCK=true, otherwise calls OpenRouter via LiteLLM
    with Cerebras as the inference provider.
    """

    def __init__(self) -> None:
        self._mock = os.environ.get("LLM_MOCK", "").lower() == "true"

    async def process_chat(
        self,
        message: str,
        portfolio_context: dict,
        history: list[dict],  # [{"role": "user"|"assistant", "content": str}]
    ) -> LLMResponse:
        """Process a chat message and return a structured LLM response."""
        if self._mock:
            return mock_response(message, portfolio_context)
        return await self._real_call(message, portfolio_context, history)

    async def _real_call(
        self,
        message: str,
        portfolio_context: dict,
        history: list[dict],
    ) -> LLMResponse:
        """Make a real LLM call via LiteLLM -> OpenRouter -> Cerebras."""
        system_content = _build_system_message(portfolio_context)

        # Build messages: system + last 20 history + new user message
        messages: list[dict] = [{"role": "system", "content": system_content}]
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": message})

        def _call() -> LLMResponse:
            response = completion(
                model=MODEL,
                messages=messages,
                response_format=LLMResponse,
                reasoning_effort="low",
                extra_body=EXTRA_BODY,
            )
            raw = response.choices[0].message.content
            return LLMResponse.model_validate_json(raw)

        return await asyncio.to_thread(_call)
