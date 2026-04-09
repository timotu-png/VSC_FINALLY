"""Tests for the LLM client and mock responder."""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.llm.mock import mock_response
from app.llm.models import LLMResponse, TradeRequest, WatchlistChange


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EMPTY_PORTFOLIO: dict = {
    "cash_balance": 10000.0,
    "total_value": 10000.0,
    "positions": [],
    "watchlist": ["AAPL", "TSLA"],
}

PORTFOLIO_WITH_POSITIONS: dict = {
    "cash_balance": 5000.0,
    "total_value": 15000.0,
    "positions": [
        {"ticker": "AAPL", "quantity": 10, "avg_cost": 190.0, "current_price": 200.0},
        {"ticker": "TSLA", "quantity": 5, "avg_cost": 250.0, "current_price": 260.0},
    ],
    "watchlist": ["AAPL", "TSLA", "NVDA"],
}


# ---------------------------------------------------------------------------
# mock_response — trigger patterns
# ---------------------------------------------------------------------------


class TestMockResponse:
    def test_buy_integer_quantity(self) -> None:
        result = mock_response("buy 10 AAPL", EMPTY_PORTFOLIO)
        assert isinstance(result, LLMResponse)
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.ticker == "AAPL"
        assert trade.side == "buy"
        assert trade.quantity == 10.0
        assert len(result.watchlist_changes) == 0

    def test_buy_fractional_quantity(self) -> None:
        result = mock_response("buy 5.5 TSLA", EMPTY_PORTFOLIO)
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.ticker == "TSLA"
        assert trade.side == "buy"
        assert trade.quantity == 5.5

    def test_sell(self) -> None:
        result = mock_response("sell 3 MSFT", EMPTY_PORTFOLIO)
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.ticker == "MSFT"
        assert trade.side == "sell"
        assert trade.quantity == 3.0
        assert len(result.watchlist_changes) == 0

    def test_watchlist_add(self) -> None:
        result = mock_response("add NVDA", EMPTY_PORTFOLIO)
        assert len(result.trades) == 0
        assert len(result.watchlist_changes) == 1
        change = result.watchlist_changes[0]
        assert change.ticker == "NVDA"
        assert change.action == "add"

    def test_watchlist_remove(self) -> None:
        result = mock_response("remove GOOGL", EMPTY_PORTFOLIO)
        assert len(result.trades) == 0
        assert len(result.watchlist_changes) == 1
        change = result.watchlist_changes[0]
        assert change.ticker == "GOOGL"
        assert change.action == "remove"

    def test_portfolio_summary(self) -> None:
        result = mock_response("portfolio", PORTFOLIO_WITH_POSITIONS)
        assert len(result.trades) == 0
        assert len(result.watchlist_changes) == 0
        # Message should mention cash and position count
        assert "5,000.00" in result.message or "5000" in result.message
        assert "2" in result.message

    def test_portfolio_summary_empty(self) -> None:
        result = mock_response("show me my portfolio", EMPTY_PORTFOLIO)
        assert len(result.trades) == 0
        assert "10,000.00" in result.message or "10000" in result.message
        assert "0" in result.message

    def test_unknown_message_echoes(self) -> None:
        user_msg = "hello there"
        result = mock_response(user_msg, EMPTY_PORTFOLIO)
        assert len(result.trades) == 0
        assert len(result.watchlist_changes) == 0
        assert result.message == f"Mock response: {user_msg}"

    def test_case_insensitive_buy(self) -> None:
        result = mock_response("BUY 10 AAPL", EMPTY_PORTFOLIO)
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.ticker == "AAPL"
        assert trade.side == "buy"
        assert trade.quantity == 10.0

    def test_case_insensitive_sell(self) -> None:
        result = mock_response("SELL 3 MSFT", EMPTY_PORTFOLIO)
        assert len(result.trades) == 1
        assert result.trades[0].side == "sell"

    def test_case_insensitive_add(self) -> None:
        result = mock_response("ADD NVDA to my watchlist", EMPTY_PORTFOLIO)
        assert len(result.watchlist_changes) == 1
        assert result.watchlist_changes[0].action == "add"
        assert result.watchlist_changes[0].ticker == "NVDA"

    def test_buy_before_sell_priority(self) -> None:
        # "buy" appears first, so buy pattern wins even if "sell" also present
        result = mock_response("buy 1 AAPL then sell 2 MSFT", EMPTY_PORTFOLIO)
        assert result.trades[0].side == "buy"

    def test_add_before_remove_priority(self) -> None:
        # "add" appears before "remove" in the message
        result = mock_response("add AAPL and remove TSLA", EMPTY_PORTFOLIO)
        # add pattern should win
        assert result.watchlist_changes[0].action == "add"

    def test_ticker_uppercased(self) -> None:
        result = mock_response("buy 1 aapl", EMPTY_PORTFOLIO)
        assert result.trades[0].ticker == "AAPL"


# ---------------------------------------------------------------------------
# LLMClient — mock mode via env var
# ---------------------------------------------------------------------------


class TestLLMClientMockMode:
    def test_client_uses_mock_when_env_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_MOCK", "true")
        from app.llm.client import LLMClient

        client = LLMClient()
        assert client._mock is True

    def test_client_does_not_mock_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLM_MOCK", raising=False)
        from app.llm.client import LLMClient

        client = LLMClient()
        assert client._mock is False

    def test_client_does_not_mock_when_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_MOCK", "false")
        from app.llm.client import LLMClient

        client = LLMClient()
        assert client._mock is False

    @pytest.mark.asyncio
    async def test_process_chat_mock_returns_llm_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_MOCK", "true")
        from app.llm.client import LLMClient

        client = LLMClient()
        result = await client.process_chat("buy 5 AAPL", EMPTY_PORTFOLIO, [])
        assert isinstance(result, LLMResponse)
        assert len(result.trades) == 1
        assert result.trades[0].ticker == "AAPL"


# ---------------------------------------------------------------------------
# LLMClient — real call with mocked litellm
# ---------------------------------------------------------------------------


class TestLLMClientRealCall:
    @pytest.mark.asyncio
    async def test_real_call_parses_llm_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        fake_response_json = (
            '{"message": "Buying 10 shares of AAPL.", '
            '"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}], '
            '"watchlist_changes": []}'
        )

        mock_choice = MagicMock()
        mock_choice.message.content = fake_response_json
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [mock_choice]

        with patch("app.llm.client.completion", return_value=mock_completion_response):
            from app.llm.client import LLMClient

            client = LLMClient()
            result = await client.process_chat(
                "buy 10 AAPL", PORTFOLIO_WITH_POSITIONS, []
            )

        assert isinstance(result, LLMResponse)
        assert result.message == "Buying 10 shares of AAPL."
        assert len(result.trades) == 1
        assert result.trades[0].ticker == "AAPL"
        assert result.trades[0].side == "buy"
        assert result.trades[0].quantity == 10.0

    @pytest.mark.asyncio
    async def test_real_call_with_history(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        fake_response_json = (
            '{"message": "Done.", "trades": [], "watchlist_changes": []}'
        )
        mock_choice = MagicMock()
        mock_choice.message.content = fake_response_json
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [mock_choice]

        history = [
            {"role": "user", "content": "What is my balance?"},
            {"role": "assistant", "content": "You have $5,000 cash."},
        ]

        with patch("app.llm.client.completion", return_value=mock_completion_response) as mock_comp:
            from app.llm.client import LLMClient

            client = LLMClient()
            result = await client.process_chat("Thanks!", EMPTY_PORTFOLIO, history)

        assert isinstance(result, LLMResponse)
        # Verify history was included in messages sent to litellm
        call_args = mock_comp.call_args
        messages_sent = call_args.kwargs.get("messages") or call_args.args[1]
        roles = [m["role"] for m in messages_sent]
        assert "system" in roles
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_real_call_history_capped_at_20(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        fake_response_json = (
            '{"message": "OK.", "trades": [], "watchlist_changes": []}'
        )
        mock_choice = MagicMock()
        mock_choice.message.content = fake_response_json
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [mock_choice]

        # 30 history messages — only last 20 should be included
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(30)
        ]

        with patch("app.llm.client.completion", return_value=mock_completion_response) as mock_comp:
            from app.llm.client import LLMClient

            client = LLMClient()
            await client.process_chat("new message", EMPTY_PORTFOLIO, history)

        call_args = mock_comp.call_args
        messages_sent = call_args.kwargs.get("messages") or call_args.args[1]
        # system(1) + last 20 history + new user message(1) = 22 total
        assert len(messages_sent) == 22


# ---------------------------------------------------------------------------
# Module-level client registry
# ---------------------------------------------------------------------------


class TestLLMRegistry:
    def test_get_llm_client_raises_before_init(self) -> None:
        import app.llm as llm_module

        # Reset registry state for isolation
        original = llm_module._llm_client
        llm_module._llm_client = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                llm_module.get_llm_client()
        finally:
            llm_module._llm_client = original

    def test_set_and_get_llm_client(self) -> None:
        import app.llm as llm_module

        original = llm_module._llm_client
        try:
            from app.llm.client import LLMClient

            client = LLMClient()
            llm_module.set_llm_client(client)
            assert llm_module.get_llm_client() is client
        finally:
            llm_module._llm_client = original
