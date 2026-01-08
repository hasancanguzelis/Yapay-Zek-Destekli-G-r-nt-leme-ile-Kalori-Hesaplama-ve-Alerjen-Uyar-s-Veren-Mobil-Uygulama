from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
import io

from .schemas import NutritionFacts


class ImageCalorieModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedImageCalorieModel:
    path: Path
    mtime_ns: int
    loaded_at_s: float
    model: Any  # TensorFlow/Keras model
    img_size: tuple[int, int]  # (width, height)
    mean_calories: float  # for fallback/denormalization


_CACHE: LoadedImageCalorieModel | None = None


def _default_model_path() -> Path:
    # backend/app/ml_image_calories.py -> backend/
    backend_root = Path(__file__).resolve().parents[1]
    return backend_root / "models" / "image_calorie_model.h5"


def get_image_model_path(*, settings_model_path: str | None = None) -> Path:
    env = (os.getenv("IMAGE_CALORIE_MODEL_PATH") or "").strip()
    if env:
        return Path(env)
    if settings_model_path:
        return Path(settings_model_path)
    return _default_model_path()


def _create_model_architecture(img_size: tuple[int, int] = (224, 224)) -> Any:
    """
    ResNet50 tabanlı transfer learning modeli oluşturur.
    ImageNet ön eğitimli ResNet50 kullanarak kalori tahmini yapar.
    """
    try:
        from tensorflow import keras
        from tensorflow.keras.applications import ResNet50
        from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
        from tensorflow.keras.models import Model
    except ImportError as e:
        raise ImageCalorieModelError(
            "TensorFlow yüklü değil. Image calorie model için 'pip install tensorflow' gerekli."
        ) from e

    # ResNet50 base model (ImageNet ön eğitimli, ağırlıklar frozen)
    base_model = ResNet50(
        weights='imagenet',
        include_top=False,
        input_shape=(img_size[0], img_size[1], 3)
    )
    base_model.trainable = False  # Transfer learning: ön eğitimli katmanları dondur

    # Custom head for calorie prediction
    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(512, activation='relu')(x)
    x = Dropout(0.3)(x)
    x = Dense(256, activation='relu')(x)
    x = Dropout(0.2)(x)
    
    # Multi-output regression: kalori ve diğer besin değerleri
    calories_out = Dense(1, activation='relu', name='calories')(x)  # Kalori tahmini (sadece pozitif)
    fat_out = Dense(1, activation='relu', name='fat')(x)
    carbs_out = Dense(1, activation='relu', name='carbs')(x)
    protein_out = Dense(1, activation='relu', name='protein')(x)
    sugar_out = Dense(1, activation='relu', name='sugar')(x)
    salt_out = Dense(1, activation='relu', name='salt')(x)
    sodium_out = Dense(1, activation='relu', name='sodium')(x)

    model = Model(
        inputs=base_model.input,
        outputs=[calories_out, fat_out, carbs_out, protein_out, sugar_out, salt_out, sodium_out],
        name='food_image_calorie_predictor'
    )

    return model


def load_image_calorie_model(*, settings_model_path: str | None = None, force_reload: bool = False) -> LoadedImageCalorieModel:
    """
    Eğitilmiş görüntü kalori modelini yükler ve cache'ler.
    Model .h5 formatında (Keras/TensorFlow) beklenir.
    """
    global _CACHE
    path = get_image_model_path(settings_model_path=settings_model_path)
    
    if not path.exists():
        raise ImageCalorieModelError(f"Model dosyası bulunamadı: {path}")

    stat = path.stat()
    if not force_reload and _CACHE and _CACHE.path == path and _CACHE.mtime_ns == stat.st_mtime_ns:
        return _CACHE

    try:
        from tensorflow import keras
    except ImportError as e:
        raise ImageCalorieModelError(
            "TensorFlow yüklü değil. Image calorie model için 'pip install tensorflow' gerekli."
        ) from e

    try:
        # Keras model yükleme
        model = keras.models.load_model(str(path))
        
        # Model yapılandırmasını kontrol et
        # Eğer model yoksa, default bir model oluştur (fallback için)
        if model is None:
            # Default img_size (ResNet için 224x224 standart)
            img_size = (224, 224)
            model = _create_model_architecture(img_size)
        else:
            # Model'den input shape'i al
            input_shape = model.input_shape
            if input_shape and len(input_shape) >= 3:
                # (batch, height, width, channels)
                img_size = (int(input_shape[1]), int(input_shape[2]))
            else:
                img_size = (224, 224)
        
        # Mean calories için bir fallback değer (normalizasyon için)
        # Gerçek model eğitiminde bu değer kaydedilmelidir
        mean_calories = 300.0  # Ortalama bir yemek porsiyonu kalori
        
        _CACHE = LoadedImageCalorieModel(
            path=path,
            mtime_ns=stat.st_mtime_ns,
            loaded_at_s=time.time(),
            model=model,
            img_size=img_size,
            mean_calories=mean_calories,
        )
        return _CACHE
    except Exception as e:
        raise ImageCalorieModelError(f"Model yüklenemedi: {type(e).__name__}: {e}") from e


def preprocess_image(image_bytes: bytes, target_size: tuple[int, int] = (224, 224)) -> np.ndarray:
    """
    Görüntüyü model için hazırlar:
    - PIL Image'e dönüştür
    - Resize et
    - RGB'ye çevir
    - Normalize et (0-1 arası)
    - Batch dimension ekle
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # RGBA veya L modundan RGB'ye çevir
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize
        img = img.resize(target_size, Image.Resampling.LANCZOS)
        
        # NumPy array'e çevir
        img_array = np.array(img, dtype=np.float32)
        
        # Normalize (0-255 -> 0-1)
        img_array = img_array / 255.0
        
        # ImageNet preprocessing (ResNet için)
        # ImageNet mean subtraction
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_array = (img_array - mean) / std
        
        # Batch dimension ekle: (1, height, width, channels)
        img_array = np.expand_dims(img_array, axis=0)
        
        return img_array
    except Exception as e:
        raise ImageCalorieModelError(f"Görüntü işlenemedi: {type(e).__name__}: {e}") from e


def predict_nutrition_from_image(model: LoadedImageCalorieModel, image_bytes: bytes) -> NutritionFacts:
    """
    Görüntüden besin değerlerini tahmin eder.
    Model multi-output regression yapıyor: [calories, fat, carbs, protein, sugar, salt, sodium]
    """
    # Görüntüyü hazırla
    img_array = preprocess_image(image_bytes, target_size=model.img_size)
    
    try:
        # Tahmin yap
        predictions = model.model.predict(img_array, verbose=0)
        
        # Multi-output için predictions bir liste olabilir
        if isinstance(predictions, (list, tuple)):
            calories = float(np.maximum(predictions[0][0][0], 0.0))
            fat = float(np.maximum(predictions[1][0][0], 0.0))
            carbs = float(np.maximum(predictions[2][0][0], 0.0))
            protein = float(np.maximum(predictions[3][0][0], 0.0))
            sugar = float(np.maximum(predictions[4][0][0], 0.0))
            salt = float(np.maximum(predictions[5][0][0], 0.0))
            sodium = float(np.maximum(predictions[6][0][0], 0.0))
        else:
            # Tek output ise (sadece kalori)
            calories = float(np.maximum(predictions[0][0], 0.0))
            fat = None
            carbs = None
            protein = None
            sugar = None
            salt = None
            sodium = None
        
        return NutritionFacts(
            calories_kcal=calories if calories > 0 else None,
            fat_g=fat if fat and fat > 0 else None,
            carbs_g=carbs if carbs and carbs > 0 else None,
            protein_g=protein if protein and protein > 0 else None,
            sugar_g=sugar if sugar and sugar > 0 else None,
            salt_g=salt if salt and salt > 0 else None,
            sodium_mg=sodium if sodium and sodium > 0 else None,
        )
    except Exception as e:
        raise ImageCalorieModelError(f"Tahmin yapılamadı: {type(e).__name__}: {e}") from e

