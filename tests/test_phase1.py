"""Tests for Phase 1 implementation: Real API calls + structured output"""

import pytest
from app.gateway import ModelGateway
from app.config import settings


def test_gateway_not_in_mock_mode():
    """Test that we're not accidentally running in mock mode for Phase 1 testing"""
    # This test will pass if we're properly configured for real API calls
    # In a real CI environment, you might want to skip this if no API key is available
    if not settings.anthropic_api_key:
        pytest.skip("No API key available for testing")

    assert settings.mock_mode == False, "Should be using real API calls, not mock mode"


def test_gateway_has_api_key():
    """Test that API key is configured"""
    if not settings.anthropic_api_key:
        pytest.skip("No API key available for testing")

    assert settings.anthropic_api_key is not None
    assert len(settings.anthropic_api_key) > 0
    assert settings.anthropic_api_key != "your-anthropic-api-key-here"


# Optional: Integration test that actually calls the API (commented out to avoid accidental costs)
# Uncomment and run manually when you want to test the real API
#
# @pytest.mark.asyncio
# async def test_real_api_call():
#     """Test making a real API call to Anthropic"""
#     if not settings.anthropic_api_key:
#         pytest.skip("No API key available for testing")
#
#     gateway = ModelGateway()
#
#     # Test a simple call
#     result = await gateway.call(
#         task="draft",
#         system="You are a helpful assistant.",
#         user="Give me a brief one-sentence description of a coffee shop morning scene."
#     )
#
#     assert result.model is not None
#     assert result.text is not None and len(result.text) > 0
#     assert result.prompt_tokens >= 0
#     assert result.completion_tokens >= 0
#     assert result.latency_ms > 0
#     assert result.cost_usd >= 0