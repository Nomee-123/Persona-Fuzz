import pytest

from engine.config import get_settings
from engine.llm.client import TokenFactoryClient


@pytest.mark.live
@pytest.mark.skipif(not get_settings().has_key, reason="NEBIUS_API_KEY is not set; live smoke skipped")
async def test_live_model_discovery_and_tool_mode():
    client = TokenFactoryClient(get_settings(), cache_path=None)
    try:
        chosen, nemotrons = await client.discover()
        assert chosen
        assert nemotrons
        mode = await client.probe_tool_mode(chosen)
        assert mode in {"native", "react"}
    finally:
        await client.close()
