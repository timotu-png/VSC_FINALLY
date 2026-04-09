# DEPENDENCIES REQUIRED: litellm>=1.0.0, pydantic>=2.0.0
# (Backend API Engineer adds these to pyproject.toml)

from .client import LLMClient
from .models import LLMResponse, TradeRequest, WatchlistChange

_llm_client: LLMClient | None = None


def set_llm_client(client: LLMClient) -> None:
    global _llm_client
    _llm_client = client


def get_llm_client() -> LLMClient:
    if _llm_client is None:
        raise RuntimeError("LLM client not initialized")
    return _llm_client


__all__ = [
    "LLMClient",
    "LLMResponse",
    "TradeRequest",
    "WatchlistChange",
    "set_llm_client",
    "get_llm_client",
]
