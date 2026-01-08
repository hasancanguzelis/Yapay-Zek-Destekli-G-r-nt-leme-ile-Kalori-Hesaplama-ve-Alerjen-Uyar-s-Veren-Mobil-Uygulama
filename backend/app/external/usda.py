from __future__ import annotations

import httpx


class USDAError(RuntimeError):
    pass


async def search_foods(
    query: str,
    api_key: str,
    *,
    timeout_s: float = 20.0,
    retries: int = 2,
    retry_backoff_s: float = 0.4,
) -> dict:
    """
    USDA FoodData Central search endpoint.
    Docs: https://fdc.nal.usda.gov/api-guide.html
    """
    if not api_key:
        raise USDAError("USDA_API_KEY missing")
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    payload = {"query": query, "pageSize": 5}
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                r = await client.post(url, params={"api_key": api_key}, json=payload)
            if r.status_code >= 500 and attempt < retries:
                await _sleep_backoff(attempt, retry_backoff_s)
                continue
            break
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_err = e
            if attempt >= retries:
                raise USDAError(f"USDA network error: {e}") from e
            await _sleep_backoff(attempt, retry_backoff_s)
    else:  # pragma: no cover
        raise USDAError(f"USDA failed: {last_err}")
    if r.status_code >= 400:
        raise USDAError(f"USDA error: {r.status_code}")
    return r.json()


async def _sleep_backoff(attempt: int, base: float) -> None:
    import asyncio

    await asyncio.sleep(base * (2**attempt))


