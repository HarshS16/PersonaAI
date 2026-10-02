from __future__ import annotations

from httpx import AsyncClient


async def test_security_headers_present(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "referrer-policy" in resp.headers


async def test_metrics_endpoint(client: AsyncClient) -> None:
    # Generate a request so a counter exists.
    await client.get("/health")
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
