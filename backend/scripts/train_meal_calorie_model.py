from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Example:
    dish_name: str
    calories_kcal: float | None = None
    fat_g: float | None = None
    carbs_g: float | None = None
    protein_g: float | None = None
    sugar_g: float | None = None
    salt_g: float | None = None
    sodium_mg: float | None = None


FIELDS = ["calories_kcal", "fat_g", "carbs_g", "protein_g", "sugar_g", "salt_g", "sodium_mg"]


def _load_jsonl(path: str) -> list[Example]:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Dataset bulunamadı: {p}")
    out: list[Example] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out.append(
            Example(
                dish_name=str(obj.get("dish_name") or "").strip(),
                calories_kcal=obj.get("calories_kcal"),
                fat_g=obj.get("fat_g"),
                carbs_g=obj.get("carbs_g"),
                protein_g=obj.get("protein_g"),
                sugar_g=obj.get("sugar_g"),
                salt_g=obj.get("salt_g"),
                sodium_mg=obj.get("sodium_mg"),
            )
        )
    return [e for e in out if e.dish_name]


def _train_one(X: list[str], y: list[float], *, seed: int):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline

    # Char n-gram works well for noisy / multilingual dish names.
    vec = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=1)
    reg = Ridge(alpha=2.0, random_state=seed)
    pipe = Pipeline([("tfidf", vec), ("ridge", reg)])
    pipe.fit(X, y)
    return pipe


def main() -> int:
    ap = argparse.ArgumentParser(description="Yemek adı -> besin değerleri (regresyon) modeli eğitir.")
    ap.add_argument("--data", default="backend/data/meal_calorie.jsonl")
    ap.add_argument("--out-model", default="backend/models/meal_calorie_model.joblib")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-samples", type=int, default=15, help="Bir alan için model eğitmek üzere min örnek sayısı")
    args = ap.parse_args()

    examples = _load_jsonl(args.data)
    if not examples:
        raise SystemExit("Dataset boş.")

    # build per-field models (handles missing values)
    models: dict[str, object] = {}
    for field in FIELDS:
        X: list[str] = []
        y: list[float] = []
        for e in examples:
            val = getattr(e, field)
            if val is None:
                continue
            try:
                fv = float(val)
            except Exception:
                continue
            X.append(e.dish_name)
            y.append(fv)

        if len(X) < args.min_samples:
            print(f"[SKIP] {field}: örnek az (n={len(X)} < {args.min_samples})")
            continue

        models[field] = _train_one(X, y, seed=args.seed)
        print(f"[OK] {field}: trained (n={len(X)})")

    if "calories_kcal" not in models:
        raise SystemExit("calories_kcal için yeterli örnek yok. Daha fazla veri toplayın.")

    out_path = Path(args.out_model)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from joblib import dump  # type: ignore
    except Exception as e:
        raise SystemExit("joblib yok. 'pip install -r backend/requirements-ml.txt' kurun.") from e

    payload = {"version": 1, "models": models}
    dump(payload, out_path)
    print(f"Model yazıldı: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



