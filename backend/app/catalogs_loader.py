from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MarketCategory:
    category_tr: str
    examples: list[str]
    common_brands: list[str]


@dataclass(frozen=True)
class CatalogAItem:
    type: str  # meal|packaged|beverage
    name_tr: str
    aliases: list[str]


@dataclass(frozen=True)
class CatalogA:
    items: list[CatalogAItem]


@dataclass(frozen=True)
class CatalogB:
    meals: list[str]
    packaged_products: list[str]
    beverages: list[str]


@dataclass(frozen=True)
class CatalogC:
    categories: list[MarketCategory]


def _catalogs_dir() -> Path:
    return Path(__file__).resolve().parent / "catalogs"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_catalog_a() -> CatalogA:
    data = _read_json(_catalogs_dir() / "tr_catalog_A_100.json")
    items: list[CatalogAItem] = []
    for it in (data.get("items") or []):
        if not isinstance(it, dict):
            continue
        items.append(
            CatalogAItem(
                type=str(it.get("type") or "").strip(),
                name_tr=str(it.get("name_tr") or "").strip(),
                aliases=[str(x).strip() for x in (it.get("aliases") or []) if str(x).strip()],
            )
        )
    return CatalogA(items=items)


@lru_cache(maxsize=1)
def load_catalog_b() -> CatalogB:
    data = _read_json(_catalogs_dir() / "tr_catalog_B_300plus.json")
    meals = [str(x).strip() for x in (data.get("meals") or []) if str(x).strip()]
    packaged = [str(x).strip() for x in (data.get("packaged_products") or []) if str(x).strip()]
    beverages = [str(x).strip() for x in (data.get("beverages") or []) if str(x).strip()]
    return CatalogB(meals=meals, packaged_products=packaged, beverages=beverages)


@lru_cache(maxsize=1)
def load_catalog_c() -> CatalogC:
    data = _read_json(_catalogs_dir() / "tr_catalog_C_market_shelf.json")
    cats: list[MarketCategory] = []
    for c in (data.get("categories") or []):
        if not isinstance(c, dict):
            continue
        cats.append(
            MarketCategory(
                category_tr=str(c.get("category_tr") or "").strip(),
                examples=[str(x).strip() for x in (c.get("examples") or []) if str(x).strip()],
                common_brands=[str(x).strip() for x in (c.get("common_brands") or []) if str(x).strip()],
            )
        )
    return CatalogC(categories=cats)


@lru_cache(maxsize=1)
def all_catalog_terms_tr() -> set[str]:
    """
    Union of all catalog items (names, aliases, category examples).
    Useful for autocomplete or keyword scanning.
    """
    out: set[str] = set()
    try:
        a = load_catalog_a()
        for it in a.items:
            if it.name_tr:
                out.add(it.name_tr)
            out |= set(it.aliases)
    except Exception:
        pass
    try:
        b = load_catalog_b()
        out |= set(b.meals)
        out |= set(b.packaged_products)
        out |= set(b.beverages)
    except Exception:
        pass
    try:
        c = load_catalog_c()
        for cat in c.categories:
            if cat.category_tr:
                out.add(cat.category_tr)
            out |= set(cat.examples)
    except Exception:
        pass
    return {x for x in out if x}



