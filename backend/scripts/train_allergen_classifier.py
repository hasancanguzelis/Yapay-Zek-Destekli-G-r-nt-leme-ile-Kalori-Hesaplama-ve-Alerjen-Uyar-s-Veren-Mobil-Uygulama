from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow running from repo root or anywhere without manual PYTHONPATH on Windows.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@dataclass(frozen=True)
class Example:
    ingredients_text: str
    product_name: str
    labels: list[str]


def _load_jsonl(path: Path) -> list[Example]:
    out: list[Example] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            ingredients_text = (obj.get("ingredients_text") or "").strip()
            product_name = (obj.get("product_name") or "").strip()
            labels = obj.get("label_allergens") or []
            if not isinstance(labels, list):
                labels = []
            labels = [str(x) for x in labels if str(x).strip()]
            out.append(Example(ingredients_text=ingredients_text, product_name=product_name, labels=labels))
    return out


def _load_csv(path: Path) -> list[Example]:
    out: list[Example] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            ingredients_text = (row.get("ingredients_text") or "").strip()
            product_name = (row.get("product_name") or "").strip()
            labels_raw = (row.get("label_allergens") or "").strip()
            try:
                labels = json.loads(labels_raw) if labels_raw else []
            except Exception:
                labels = []
            if not isinstance(labels, list):
                labels = []
            labels = [str(x) for x in labels if str(x).strip()]
            out.append(Example(ingredients_text=ingredients_text, product_name=product_name, labels=labels))
    return out


def _load_dataset(path: Path) -> list[Example]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl(path)
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    raise ValueError("Unsupported dataset format. Use .jsonl or .csv")


def _filter_examples(examples: list[Example], *, require_text: bool, require_labels: bool) -> list[Example]:
    out: list[Example] = []
    for ex in examples:
        if require_text and not (ex.ingredients_text.strip() or ex.product_name.strip()):
            continue
        if require_labels and not ex.labels:
            continue
        out.append(ex)
    return out


def _build_text(ex: Example, mode: str) -> str:
    if mode == "ingredients":
        return ex.ingredients_text.strip()
    if mode == "name":
        return ex.product_name.strip()
    if mode == "both":
        a = ex.product_name.strip()
        b = ex.ingredients_text.strip()
        if a and b:
            return f"{a} | {b}"
        return a or b
    return ex.ingredients_text.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Train a baseline multi-label allergen classifier from dataset JSONL/CSV.")
    p.add_argument(
        "--data",
        default="backend/data/food_dataset.jsonl",
        help="Dataset path (.jsonl or .csv). Must include ingredients_text + label_allergens.",
    )
    p.add_argument(
        "--out-model",
        default="backend/models/allergen_clf.joblib",
        help="Output model path (joblib).",
    )
    p.add_argument("--test-size", type=float, default=0.2, help="Test split ratio (default 0.2).")
    p.add_argument("--val-size", type=float, default=0.2, help="Validation split ratio from train (default 0.2).")
    p.add_argument("--seed", type=int, default=42, help="Random seed for split.")
    p.add_argument(
        "--min-label-freq",
        type=int,
        default=5,
        help="Drop labels that appear fewer than this (default 5) to reduce noise.",
    )
    p.add_argument("--require-text", action="store_true", help="Drop empty ingredients_text rows.")
    p.add_argument("--require-labels", action="store_true", help="Drop rows with no labels.")
    p.add_argument(
        "--text-mode",
        default="ingredients",
        choices=["ingredients", "name", "both"],
        help="Model input text: ingredients | name | both (default ingredients).",
    )
    p.add_argument(
        "--tune-thresholds",
        action="store_true",
        help="Tune per-label probability thresholds on validation split (recommended for multi-label).",
    )
    p.add_argument(
        "--predict",
        default="",
        help="If set, loads --out-model and predicts labels for given text instead of training.",
    )
    args = p.parse_args(argv)

    if args.predict:
        from joblib import load  # type: ignore

        model_obj = load(args.out_model)
        pipeline = model_obj["pipeline"]
        classes = list(model_obj["classes"])
        thresholds = list(model_obj.get("thresholds") or [0.5] * len(classes))

        probs = pipeline.predict_proba([args.predict])[0]
        ranked = sorted(zip(classes, probs), key=lambda x: float(x[1]), reverse=True)
        top = [(c, float(p)) for c, p in ranked[:10]]
        print("Top predictions:")
        for c, pr in top:
            print(f"- {c}: {pr:.3f}")
        predicted = [c for c, pr, th in zip(classes, probs, thresholds) if float(pr) >= float(th)]
        if predicted:
            print("Predicted labels (thresholded): " + ", ".join(predicted))
        return 0

    data_path = Path(args.data)
    examples = _load_dataset(data_path)
    examples = _filter_examples(examples, require_text=args.require_text, require_labels=args.require_labels)
    if not examples:
        print("No examples after filtering.", file=sys.stderr)
        return 2

    # Compute label frequencies and drop rare labels.
    freq: dict[str, int] = {}
    for ex in examples:
        for lab in set(ex.labels):
            freq[lab] = freq.get(lab, 0) + 1
    kept_labels = sorted([lab for lab, n in freq.items() if n >= args.min_label_freq])
    if not kept_labels:
        print("No labels left after min-label-freq filtering.", file=sys.stderr)
        return 2
    dropped = sorted([lab for lab, n in freq.items() if n < args.min_label_freq])
    if dropped:
        print(f"Dropped labels (<{args.min_label_freq}): {dropped}")

    filtered: list[Example] = []
    for ex in examples:
        labs = [l for l in ex.labels if l in kept_labels]
        filtered.append(Example(ingredients_text=ex.ingredients_text, product_name=ex.product_name, labels=labs))
    # Optionally drop rows that became unlabeled after filtering.
    if args.require_labels:
        filtered = [ex for ex in filtered if ex.labels]

    X = [_build_text(ex, args.text_mode) for ex in filtered]
    Y = [ex.labels for ex in filtered]

    # Lazy import so backend runtime doesn't require sklearn.
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.linear_model import LogisticRegression  # type: ignore
    from sklearn.metrics import classification_report, f1_score  # type: ignore
    from sklearn.model_selection import train_test_split  # type: ignore
    from sklearn.multiclass import OneVsRestClassifier  # type: ignore
    from sklearn.pipeline import Pipeline  # type: ignore
    from sklearn.preprocessing import MultiLabelBinarizer  # type: ignore

    X_train_all, X_test, Y_train_all, Y_test = train_test_split(
        X,
        Y,
        test_size=args.test_size,
        random_state=args.seed,
        shuffle=True,
    )
    X_train, X_val, Y_train, Y_val = train_test_split(
        X_train_all,
        Y_train_all,
        test_size=args.val_size,
        random_state=args.seed,
        shuffle=True,
    )

    mlb = MultiLabelBinarizer(classes=kept_labels)
    y_train = mlb.fit_transform(Y_train)
    y_val = mlb.transform(Y_val)
    y_test = mlb.transform(Y_test)

    # Character ngrams are robust to Turkish diacritics/typos and ingredient tokenization.
    pipeline = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2)),
            (
                "clf",
                OneVsRestClassifier(
                    LogisticRegression(max_iter=2000, class_weight="balanced", solver="liblinear")
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)

    import numpy as np  # type: ignore

    thresholds = np.array([0.5] * len(mlb.classes_), dtype=float)
    if args.tune_thresholds:
        val_probs = pipeline.predict_proba(X_val)
        tuned = []
        for j in range(val_probs.shape[1]):
            best_th = 0.5
            best_f1 = -1.0
            y_true_j = y_val[:, j]
            for th in [x / 100 for x in range(10, 91, 5)]:
                y_pred_j = (val_probs[:, j] >= th).astype(int)
                f1 = f1_score(y_true_j, y_pred_j, average="binary", zero_division=0)
                if float(f1) > best_f1:
                    best_f1 = float(f1)
                    best_th = float(th)
            tuned.append(best_th)
        thresholds = np.array(tuned, dtype=float)

    test_probs = pipeline.predict_proba(X_test)
    y_pred = (test_probs >= thresholds).astype(int)
    micro = f1_score(y_test, y_pred, average="micro", zero_division=0)
    macro = f1_score(y_test, y_pred, average="macro", zero_division=0)
    print(
        f"Examples: {len(filtered)} | labels: {len(kept_labels)} | text_mode={args.text_mode} | "
        f"test_size={args.test_size} val_size={args.val_size} tune_thresholds={bool(args.tune_thresholds)}"
    )
    print(f"F1 micro={micro:.3f} macro={macro:.3f}")
    print(classification_report(y_test, y_pred, target_names=mlb.classes_, zero_division=0))

    out_path = Path(args.out_model)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    from joblib import dump  # type: ignore

    dump({"pipeline": pipeline, "classes": mlb.classes_, "thresholds": thresholds.tolist()}, out_path)
    print(f"Saved model: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


