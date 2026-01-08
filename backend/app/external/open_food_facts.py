from __future__ import annotations

import httpx


class OpenFoodFactsError(RuntimeError):
    pass


async def search_products(
    *,
    search_terms: str = "",
    page: int = 1,
    page_size: int = 50,
    fields: list[str] | None = None,
    timeout_s: float = 15.0,
    retries: int = 2,
    retry_backoff_s: float = 0.4,
    extra_params: dict[str, str] | None = None,
) -> dict:
    """
    Searches Open Food Facts via the public search endpoint (cgi/search.pl).

    Example (docs/community usage):
    - https://world.openfoodfacts.org/cgi/search.pl?search_terms=milk&search_simple=1&action=process&json=1

    Returns raw JSON dict that typically contains:
    - "products": list[dict]
    - "count": int
    - "page": int
    - "page_size": int
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 1000:
        raise ValueError("page_size must be between 1 and 1000")

    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params: dict[str, str] = {
        "search_terms": (search_terms or "").strip(),
        "search_simple": "1",
        "action": "process",
        "json": "1",
        "page": str(page),
        "page_size": str(page_size),
    }
    if fields:
        # Comma-separated list of fields to reduce payload.
        params["fields"] = ",".join([f.strip() for f in fields if f and f.strip()])
    if extra_params:
        for k, v in extra_params.items():
            if k and v is not None:
                params[str(k)] = str(v)

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                r = await client.get(url, params=params, headers={"User-Agent": "Tez-Proje/1.0 (academic)"})
            if r.status_code >= 500 and attempt < retries:
                await _sleep_backoff(attempt, retry_backoff_s)
                continue
            break
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_err = e
            if attempt >= retries:
                raise OpenFoodFactsError(f"OpenFoodFacts network error: {e}") from e
            await _sleep_backoff(attempt, retry_backoff_s)
    else:  # pragma: no cover
        raise OpenFoodFactsError(f"OpenFoodFacts failed: {last_err}")

    if r.status_code >= 400:
        raise OpenFoodFactsError(f"OpenFoodFacts error: {r.status_code}")
    return r.json()


async def fetch_product_by_barcode(
    barcode: str,
    *,
    timeout_s: float = 15.0,
    retries: int = 2,
    retry_backoff_s: float = 0.4,
) -> dict | None:
    """
    Uses Open Food Facts v2 endpoint:
    https://world.openfoodfacts.org/api/v2/product/{barcode}.json
    Returns product dict or None if not found.
    """
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                r = await client.get(url, headers={"User-Agent": "Tez-Proje/1.0 (academic)"})
            if r.status_code >= 500 and attempt < retries:
                # transient server error
                await _sleep_backoff(attempt, retry_backoff_s)
                continue
            break
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_err = e
            if attempt >= retries:
                raise OpenFoodFactsError(f"OpenFoodFacts network error: {e}") from e
            await _sleep_backoff(attempt, retry_backoff_s)
    else:  # pragma: no cover
        raise OpenFoodFactsError(f"OpenFoodFacts failed: {last_err}")
    if r.status_code == 404:
        return None
    if r.status_code >= 400:
        raise OpenFoodFactsError(f"OpenFoodFacts error: {r.status_code}")
    data = r.json()
    if not data.get("product"):
        return None
    return data["product"]


async def _sleep_backoff(attempt: int, base: float) -> None:
    # Simple exponential backoff: base * 2^attempt
    import asyncio

    await asyncio.sleep(base * (2**attempt))


def extract_basic_fields(product: dict) -> dict:
    """
    Normalizes a subset of OFF fields into a simple dict.
    """
    nutriments = product.get("nutriments") or {}
    return {
        "product_name": product.get("product_name"),
        "ingredients_text": product.get("ingredients_text"),
        "allergens": product.get("allergens") or product.get("allergens_tags") or [],
        "nutriments": {
            "energy-kcal_100g": nutriments.get("energy-kcal_100g"),
            "fat_100g": nutriments.get("fat_100g"),
            "carbohydrates_100g": nutriments.get("carbohydrates_100g"),
            "proteins_100g": nutriments.get("proteins_100g"),
            "sugars_100g": nutriments.get("sugars_100g"),
            "salt_100g": nutriments.get("salt_100g"),
            "sodium_100g": nutriments.get("sodium_100g"),
        },
    }


