import httpx
import pytest

from blurt.cleanup_client import CleanupClient


@pytest.mark.asyncio
async def test_cleanup_returns_stripped_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        body = request.read().decode()
        assert "qwen2.5:1.5b" in body
        return httpx.Response(200, json={"response": "  Open GitHub.com\n"})

    transport = httpx.MockTransport(handler)
    client = CleanupClient(
        base_url="http://ollama-host:11434",
        model="qwen2.5:1.5b",
        timeout_ms=500,
        transport=transport,
    )
    result = await client.cleanup("open github dot com")
    assert result == "Open GitHub.com"


@pytest.mark.asyncio
async def test_cleanup_returns_original_on_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated", request=request)

    transport = httpx.MockTransport(handler)
    client = CleanupClient(
        base_url="http://ollama-host:11434",
        model="qwen2.5:1.5b",
        timeout_ms=50,
        transport=transport,
    )
    result = await client.cleanup("anything")
    assert result == "anything"


@pytest.mark.asyncio
async def test_cleanup_returns_original_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    transport = httpx.MockTransport(handler)
    client = CleanupClient(
        base_url="http://ollama-host:11434",
        model="qwen2.5:1.5b",
        timeout_ms=500,
        transport=transport,
    )
    result = await client.cleanup("anything")
    assert result == "anything"


@pytest.mark.asyncio
async def test_cleanup_empty_input_short_circuits() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"response": "unexpected"})

    transport = httpx.MockTransport(handler)
    client = CleanupClient(
        base_url="http://ollama-host:11434",
        model="qwen2.5:1.5b",
        timeout_ms=500,
        transport=transport,
    )
    result = await client.cleanup("")
    assert result == ""
    assert called is False
