from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from backend.app.external.usda import search_foods
from backend.app.main import _average_usda_nutrition  # reuse mapping logic
from backend.app.config import get_settings


@dataclass(frozen=True)
class Record:
    dish_name: str
    calories_kcal: float | None
    fat_g: float | None
    carbs_g: float | None
    protein_g: float | None
    sugar_g: float | None
    salt_g: float | None
    sodium_mg: float | None
    source: str = "usda_avg"


def _load_queries(path: str | None, inline: str | None) -> list[str]:
    out: list[str] = []
    if inline:
        out.extend([x.strip() for x in inline.split(",") if x.strip()])
    if path:
        p = Path(path)
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                out.append(s)
    # de-dup preserving order
    seen: set[str] = set()
    dedup: list[str] = []
    for q in out:
        k = q.lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(q)
    return dedup


async def _collect_one(query: str, api_key: str, settings) -> Record | None:
    data = await search_foods(
        query=query,
        api_key=api_key,
        timeout_s=settings.http_timeout_s,
        retries=settings.http_retries,
        retry_backoff_s=settings.http_retry_backoff_s,
    )
    foods = data.get("foods") or []
    if not foods:
        return None
    nf = _average_usda_nutrition(foods)
    return Record(
        dish_name=query,
        calories_kcal=nf.calories_kcal,
        fat_g=nf.fat_g,
        carbs_g=nf.carbs_g,
        protein_g=nf.protein_g,
        sugar_g=nf.sugar_g,
        salt_g=nf.salt_g,
        sodium_mg=nf.sodium_mg,
        source="usda_avg",
    )


def _write_jsonl(path: str, rows: Iterable[Record], *, overwrite: bool) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not overwrite:
        raise SystemExit(f"Çıkış dosyası zaten var: {out_path} (üstüne yazmak için --overwrite)")
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


async def main_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    api_key = os.getenv("USDA_API_KEY") or settings.usda_api_key
    if not api_key:
        raise SystemExit("USDA_API_KEY ayarlı değil. backend/.env veya ortam değişkeni olarak ayarlayın.")

    queries = _load_queries(args.queries_file, args.queries)
    if not queries:
        raise SystemExit("Sorgu yok. --queries veya --queries-file verin.")

    records: list[Record] = []
    for q in queries:
        try:
            rec = await _collect_one(q, api_key, settings)
        except Exception as e:
            print(f"[WARN] {q}: {e}")
            continue
        if rec is None:
            print(f"[WARN] {q}: sonuç yok")
            continue
        records.append(rec)
        print(f"[OK] {q}: kcal={rec.calories_kcal}")

    _write_jsonl(args.out, records, overwrite=args.overwrite)
    print(f"Yazıldı: {args.out} ({len(records)} kayıt)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="USDA üzerinden yemek adı -> besin değerleri dataset'i (JSONL) oluşturur.")
    p.add_argument("--out", default="backend/data/meal_calorie.jsonl")
    p.add_argument("--queries", default=None, help="Virgülle ayrılmış yemek adları (örn: pilav,kuru fasulye)")
    p.add_argument("--queries-file", default=None, help="Satır satır yemek adları dosyası (utf-8)")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())



