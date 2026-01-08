from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Allow running from repo root or anywhere without manual PYTHONPATH on Windows.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.allergens import canonicalize_off_allergens, detect_allergens  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.external.open_food_facts import extract_basic_fields, search_products  # noqa: E402
from app.external.usda import search_foods  # noqa: E402


@dataclass(frozen=True)
class Record:
    source: str
    query: str | None
    barcode: str | None
    product_name: str | None
    ingredients_text: str | None
    ingredients_list: list[str]
    allergens_rule: list[str]
    allergens_off_raw: str | list[str] | None
    allergens_off_canon: list[str]
    label_allergens: list[str]
    nutriments: dict
    extra: dict

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "query": self.query,
            "barcode": self.barcode,
            "product_name": self.product_name,
            "ingredients_text": self.ingredients_text,
            "ingredients_list": self.ingredients_list,
            "allergens_rule": self.allergens_rule,
            "allergens_off_raw": self.allergens_off_raw,
            "allergens_off_canon": self.allergens_off_canon,
            "label_allergens": self.label_allergens,
            "nutriments": self.nutriments,
            "extra": self.extra,
        }


def _split_queries(raw: str) -> list[str]:
    # Supports "milk,chocolate" or "milk\nchocolate"
    raw = (raw or "").strip()
    if not raw:
        return []
    parts: list[str] = []
    for line in raw.splitlines():
        parts.extend([p.strip() for p in line.split(",") if p.strip()])
    # de-dup keep order
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _default_queries_tr() -> list[str]:
    # A small seed list; extend freely.
    return [
        "bisküvi",
        "çikolata",
        "kraker",
        "cips",
        "yoğurt",
        "peynir",
        "süt",
        "dondurma",
        "ekmek",
        "makarna",
        "sos",
        "ketçap",
        "mayonez",
        "ton balığı",
        "fıstık ezmesi",
        "tahin",
        "susam",
    ]


def _ingredients_to_list(ingredients_text: str | None) -> list[str]:
    if not ingredients_text:
        return []
    items = [x.strip() for x in ingredients_text.split(",") if x.strip()]
    # de-dup keep order
    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _safe_jsonl_append(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Flatten to a pragmatic training-friendly subset
    fieldnames = [
        "source",
        "query",
        "barcode",
        "product_name",
        "ingredients_text",
        "label_allergens",
        "allergens_rule",
        "allergens_off_canon",
        "allergens_off_raw",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "source": r.get("source"),
                    "query": r.get("query"),
                    "barcode": r.get("barcode"),
                    "product_name": r.get("product_name"),
                    "ingredients_text": r.get("ingredients_text"),
                    "label_allergens": json.dumps(r.get("label_allergens") or [], ensure_ascii=False),
                    "allergens_rule": json.dumps(r.get("allergens_rule") or [], ensure_ascii=False),
                    "allergens_off_canon": json.dumps(r.get("allergens_off_canon") or [], ensure_ascii=False),
                    "allergens_off_raw": json.dumps(r.get("allergens_off_raw"), ensure_ascii=False),
                }
            )


async def _collect_off_for_query(
    query: str,
    *,
    pages: int,
    page_size: int,
    polite_delay_s: float,
    timeout_s: float,
    retries: int,
    retry_backoff_s: float,
    label_source: str,
) -> list[Record]:
    fields = [
        "code",
        "product_name",
        "ingredients_text",
        "allergens",
        "allergens_tags",
        "nutriments",
        "brands",
        "categories_tags",
        "countries_tags",
        "lang",
    ]
    out: list[Record] = []
    for page in range(1, pages + 1):
        data = await search_products(
            search_terms=query,
            page=page,
            page_size=page_size,
            fields=fields,
            timeout_s=timeout_s,
            retries=retries,
            retry_backoff_s=retry_backoff_s,
        )
        products = data.get("products") or []
        for p in products:
            basic = extract_basic_fields(p)
            ingredients_text = (basic.get("ingredients_text") or "").strip() or None
            ingredients_list = _ingredients_to_list(ingredients_text)
            allergens_rule = detect_allergens(ingredients_text or "")
            allergens_off_raw = basic.get("allergens")
            allergens_off_canon = canonicalize_off_allergens(allergens_off_raw)
            if label_source == "off":
                label_allergens = allergens_off_canon
            elif label_source == "rule":
                label_allergens = allergens_rule
            elif label_source == "union":
                label_allergens = sorted(set(allergens_off_canon).union(allergens_rule))
            elif label_source == "intersection":
                label_allergens = sorted(set(allergens_off_canon).intersection(allergens_rule))
            else:  # pragma: no cover
                label_allergens = allergens_off_canon
            nutriments = basic.get("nutriments") or {}
            barcode = (p.get("code") or "").strip() or None
            extra = {
                "brands": p.get("brands"),
                "categories_tags": p.get("categories_tags"),
                "countries_tags": p.get("countries_tags"),
                "lang": p.get("lang"),
            }
            out.append(
                Record(
                    source="openfoodfacts",
                    query=query,
                    barcode=barcode,
                    product_name=basic.get("product_name"),
                    ingredients_text=ingredients_text,
                    ingredients_list=ingredients_list,
                    allergens_rule=allergens_rule,
                    allergens_off_raw=allergens_off_raw,
                    allergens_off_canon=allergens_off_canon,
                    label_allergens=label_allergens,
                    nutriments=nutriments,
                    extra=extra,
                )
            )
        if polite_delay_s > 0:
            await asyncio.sleep(polite_delay_s)
    return out


async def _collect_usda_for_queries(
    queries: list[str],
    *,
    api_key: str,
    timeout_s: float,
    retries: int,
    retry_backoff_s: float,
    polite_delay_s: float,
    label_source: str,
) -> list[Record]:
    out: list[Record] = []
    for q in queries:
        data = await search_foods(
            query=q,
            api_key=api_key,
            timeout_s=timeout_s,
            retries=retries,
            retry_backoff_s=retry_backoff_s,
        )
        foods = data.get("foods") or []
        for f in foods:
            desc = f.get("description") or f.get("lowercaseDescription")
            # USDA search results often don't contain full ingredients; keep what we can.
            ingredients_text = (f.get("ingredients") or "").strip() or None
            ingredients_list = _ingredients_to_list(ingredients_text)
            allergens_rule = detect_allergens(ingredients_text or (desc or ""))
            allergens_off_canon: list[str] = []
            if label_source == "rule":
                label_allergens = allergens_rule
            elif label_source in {"union", "intersection", "off"}:
                # USDA search results usually have no explicit allergen tags.
                label_allergens = allergens_rule if label_source != "intersection" else []
            else:  # pragma: no cover
                label_allergens = allergens_rule
            nutriments = {"foodNutrients": f.get("foodNutrients") or []}
            extra = {
                "fdcId": f.get("fdcId"),
                "dataType": f.get("dataType"),
                "publishedDate": f.get("publishedDate"),
            }
            out.append(
                Record(
                    source="usda",
                    query=q,
                    barcode=None,
                    product_name=desc,
                    ingredients_text=ingredients_text,
                    ingredients_list=ingredients_list,
                    allergens_rule=allergens_rule,
                    allergens_off_raw=None,
                    allergens_off_canon=allergens_off_canon,
                    label_allergens=label_allergens,
                    nutriments=nutriments,
                    extra=extra,
                )
            )
        if polite_delay_s > 0:
            await asyncio.sleep(polite_delay_s)
    return out


def _dedupe_records(records: list[Record]) -> list[Record]:
    seen: set[str] = set()
    out: list[Record] = []
    for r in records:
        key = (r.source, r.barcode or "", (r.product_name or "").lower(), (r.ingredients_text or "").lower())
        k = json.dumps(key, ensure_ascii=False)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Model eğitimi için Open Food Facts / USDA üzerinden yemek/ürün verisi toplar ve JSONL/CSV olarak kaydeder."
    )
    p.add_argument(
        "--out",
        default="backend/data/food_dataset.jsonl",
        help="JSONL çıktı yolu (varsayılan: backend/data/food_dataset.jsonl)",
    )
    p.add_argument(
        "--csv-out",
        default="",
        help="Opsiyonel CSV çıktı yolu (örn: backend/data/food_dataset.csv). Boş ise yazılmaz.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Çıktı dosyalarını sıfırdan yazar (mevcut JSONL/CSV varsa siler). Varsayılan: append.",
    )
    p.add_argument(
        "--source",
        default="off",
        choices=["off", "usda", "both"],
        help="Veri kaynağı: off | usda | both",
    )
    p.add_argument(
        "--label-source",
        default="off",
        choices=["off", "rule", "union", "intersection"],
        help="Alerjen label üretimi: off (OFF tags) | rule (kural tabanlı) | union | intersection",
    )
    p.add_argument(
        "--queries",
        default="",
        help="Virgül veya satır ile ayrılmış arama terimleri. Boş ise TR seed list kullanılır.",
    )
    p.add_argument("--off-pages", type=int, default=3, help="OFF için sayfa sayısı (varsayılan 3)")
    p.add_argument("--off-page-size", type=int, default=50, help="OFF için page_size (varsayılan 50)")
    p.add_argument(
        "--require-ingredients",
        action="store_true",
        help="Sadece ingredients_text dolu kayıtları yazar (model eğitimi için genelde daha temiz).",
    )
    p.add_argument(
        "--require-labels",
        action="store_true",
        help="Sadece label_allergens boş olmayan kayıtları yazar (pozitif örnekleri garanti eder).",
    )
    p.add_argument(
        "--polite-delay-s",
        type=float,
        default=0.2,
        help="İstekler arası gecikme (rate-limit için). OFF/USDA arasında uygulanır.",
    )
    args = p.parse_args(argv)

    settings = get_settings()
    queries = _split_queries(args.queries) or _default_queries_tr()

    async def runner() -> tuple[list[Record], float]:
        started = time.perf_counter()
        all_records: list[Record] = []

        if args.source in {"off", "both"}:
            for q in queries:
                all_records.extend(
                    await _collect_off_for_query(
                        q,
                        pages=args.off_pages,
                        page_size=args.off_page_size,
                        polite_delay_s=args.polite_delay_s,
                        timeout_s=settings.http_timeout_s,
                        retries=settings.http_retries,
                        retry_backoff_s=settings.http_retry_backoff_s,
                        label_source=args.label_source,
                    )
                )

        if args.source in {"usda", "both"}:
            if not settings.usda_api_key:
                raise RuntimeError("USDA_API_KEY ayarlı değil (backend/.env veya environment).")
            all_records.extend(
                await _collect_usda_for_queries(
                    queries,
                    api_key=settings.usda_api_key,
                    timeout_s=settings.http_timeout_s,
                    retries=settings.http_retries,
                    retry_backoff_s=settings.http_retry_backoff_s,
                    polite_delay_s=args.polite_delay_s,
                    label_source=args.label_source,
                )
            )

        dur_s = time.perf_counter() - started
        return all_records, dur_s

    try:
        records, dur_s = asyncio.run(runner())
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    records = _dedupe_records(records)
    if args.require_ingredients:
        records = [r for r in records if (r.ingredients_text or "").strip()]
    if args.require_labels:
        records = [r for r in records if (r.label_allergens or [])]

    rows = [r.to_dict() for r in records]

    out_path = Path(args.out)
    if args.overwrite:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            out_path.unlink()
    _safe_jsonl_append(out_path, rows)

    if args.csv_out:
        csv_path = Path(args.csv_out)
        if args.overwrite and csv_path.exists():
            csv_path.unlink()
        _write_csv(csv_path, rows)

    print(f"Wrote {len(rows)} records to: {out_path}")
    if args.csv_out:
        print(f"Wrote CSV to: {args.csv_out}")
    print(f"Queries: {len(queries)} | source={args.source} | duration_s={dur_s:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


