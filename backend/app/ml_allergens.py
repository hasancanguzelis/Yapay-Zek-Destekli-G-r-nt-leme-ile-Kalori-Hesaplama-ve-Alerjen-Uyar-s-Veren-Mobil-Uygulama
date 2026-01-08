from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path


class AllergenModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedAllergenModel:
    path: Path
    mtime_ns: int
    loaded_at_s: float
    pipeline: object
    classes: list[str]
    thresholds: list[float]


_CACHE: LoadedAllergenModel | None = None


def _default_model_path() -> Path:
    # backend/app/ml_allergens.py -> backend/
    backend_root = Path(__file__).resolve().parents[1]
    return backend_root / "models" / "allergen_clf.joblib"


def get_model_path() -> Path:
    env = (os.getenv("ALLERGEN_MODEL_PATH") or "").strip()
    if env:
        return Path(env)
    return _default_model_path()


def load_allergen_model(*, force_reload: bool = False) -> LoadedAllergenModel:
    """
    Loads the trained allergen classifier from joblib and caches it.
    If the file changes on disk (mtime), it is reloaded automatically.
    """
    global _CACHE
    path = get_model_path()
    if not path.exists():
        raise AllergenModelError(f"Model dosyası bulunamadı: {path}")

    stat = path.stat()
    if not force_reload and _CACHE and _CACHE.path == path and _CACHE.mtime_ns == stat.st_mtime_ns:
        return _CACHE

    try:
        from joblib import load  # type: ignore
    except Exception as e:  # pragma: no cover
        raise AllergenModelError(
            "joblib yüklü değil. Model endpoint'i için 'pip install -r backend/requirements-ml.txt' gerekli."
        ) from e

    obj = load(path)
    pipeline = obj.get("pipeline")

    classes_raw = obj.get("classes")
    if classes_raw is None:
        classes: list[str] = []
    else:
        # classes might be a numpy array; avoid boolean evaluation with "or".
        classes = [str(x) for x in list(classes_raw)]

    thresholds_raw = obj.get("thresholds")
    if thresholds_raw is None:
        thresholds = [0.5] * len(classes)
    else:
        thresholds = [float(x) for x in list(thresholds_raw)]
    if not pipeline or not classes:
        raise AllergenModelError("Model dosyası beklenen formatta değil (pipeline/classes eksik).")
    if len(thresholds) != len(classes):
        thresholds = [0.5] * len(classes)

    _CACHE = LoadedAllergenModel(
        path=path,
        mtime_ns=stat.st_mtime_ns,
        loaded_at_s=time.time(),
        pipeline=pipeline,
        classes=classes,
        thresholds=thresholds,
    )
    return _CACHE


