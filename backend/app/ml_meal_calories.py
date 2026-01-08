from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from .schemas import NutritionFacts


class MealCalorieModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedMealCalorieModel:
    path: Path
    mtime_ns: int
    loaded_at_s: float
    models: dict[str, object]  # field -> sklearn pipeline


_CACHE: LoadedMealCalorieModel | None = None


def _default_model_path() -> Path:
    # backend/app/ml_meal_calories.py -> backend/
    backend_root = Path(__file__).resolve().parents[1]
    return backend_root / "models" / "meal_calorie_model.joblib"


def get_meal_model_path(*, settings_model_path: str | None = None) -> Path:
    env = (os.getenv("MEAL_CALORIE_MODEL_PATH") or "").strip()
    if env:
        return Path(env)
    if settings_model_path:
        return Path(settings_model_path)
    return _default_model_path()


def load_meal_calorie_model(*, settings_model_path: str | None = None, force_reload: bool = False) -> LoadedMealCalorieModel:
    """
    Loads a trained meal calorie model from joblib and caches it.
    Expected joblib format:
      {"version": 1, "models": {"calories_kcal": <pipeline>, ...}}
    """
    global _CACHE
    path = get_meal_model_path(settings_model_path=settings_model_path)
    if not path.exists():
        raise MealCalorieModelError(f"Model dosyası bulunamadı: {path}")

    stat = path.stat()
    if not force_reload and _CACHE and _CACHE.path == path and _CACHE.mtime_ns == stat.st_mtime_ns:
        return _CACHE

    try:
        from joblib import load  # type: ignore
    except Exception as e:  # pragma: no cover
        raise MealCalorieModelError(
            "joblib yüklü değil. Meal model endpoint'i için 'pip install -r backend/requirements-ml.txt' gerekli."
        ) from e

    obj = load(path)
    models = obj.get("models") if isinstance(obj, dict) else None
    if not isinstance(models, dict) or not models:
        raise MealCalorieModelError("Model dosyası beklenen formatta değil (models eksik).")

    _CACHE = LoadedMealCalorieModel(
        path=path,
        mtime_ns=stat.st_mtime_ns,
        loaded_at_s=time.time(),
        models=models,
    )
    return _CACHE


def predict_nutrition(model: LoadedMealCalorieModel, dish_name: str) -> NutritionFacts:
    """
    Predicts per-portion (base portion=1.0) nutrition from dish_name.
    Each field is predicted only if its model exists.
    """
    text = (dish_name or "").strip()
    if not text:
        raise MealCalorieModelError("dish_name boş olamaz.")

    def pred(field: str) -> float | None:
        m = model.models.get(field)
        if not m:
            return None
        try:
            y = m.predict([text])[0]
            y = float(y)
            # clamp to sane minimum
            if y < 0:
                y = 0.0
            return y
        except Exception:
            return None

    return NutritionFacts(
        calories_kcal=pred("calories_kcal"),
        fat_g=pred("fat_g"),
        carbs_g=pred("carbs_g"),
        protein_g=pred("protein_g"),
        sugar_g=pred("sugar_g"),
        salt_g=pred("salt_g"),
        sodium_mg=pred("sodium_mg"),
    )



