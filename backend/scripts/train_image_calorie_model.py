#!/usr/bin/env python3
"""
CNN/ResNet tabanlı görüntüden kalori tahmin modeli eğitim scripti.

Kullanım:
    py -m backend.scripts.train_image_calorie_model \
        --dataset data/food_images/ \
        --labels data/food_labels.jsonl \
        --output models/image_calorie_model.h5 \
        --epochs 50 \
        --batch-size 32

Dataset formatı:
    - images/: Gıda görüntüleri (JPG/PNG)
    - labels.jsonl: Her satır bir JSON obje:
        {"image_path": "images/dish1.jpg", "calories_kcal": 350.0, "fat_g": 15.0, ...}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_root))

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.applications import ResNet50
    from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
    from tensorflow.keras.models import Model
    from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
    from tensorflow.keras.optimizers import Adam
except ImportError:
    print("ERROR: TensorFlow yüklü değil. 'pip install tensorflow' gerekli.")
    sys.exit(1)


@dataclass
class ImageLabel:
    image_path: str
    calories_kcal: float | None = None
    fat_g: float | None = None
    carbs_g: float | None = None
    protein_g: float | None = None
    sugar_g: float | None = None
    salt_g: float | None = None
    sodium_mg: float | None = None


def load_labels(jsonl_path: Path) -> list[ImageLabel]:
    """JSONL dosyasından etiketleri yükle."""
    labels = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        labels.append(ImageLabel(
            image_path=str(obj.get("image_path") or ""),
            calories_kcal=obj.get("calories_kcal"),
            fat_g=obj.get("fat_g"),
            carbs_g=obj.get("carbs_g"),
            protein_g=obj.get("protein_g"),
            sugar_g=obj.get("sugar_g"),
            salt_g=obj.get("salt_g"),
            sodium_mg=obj.get("sodium_mg"),
        ))
    return labels


def load_and_preprocess_image(image_path: Path, target_size: tuple[int, int] = (224, 224)) -> np.ndarray:
    """Görüntüyü yükle ve ön işleme yap."""
    img = Image.open(image_path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img = img.resize(target_size, Image.Resampling.LANCZOS)
    img_array = np.array(img, dtype=np.float32) / 255.0
    
    # ImageNet preprocessing
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img_array = (img_array - mean) / std
    
    return img_array


def create_model(img_size: tuple[int, int] = (224, 224)) -> Model:
    """ResNet50 tabanlı model oluştur."""
    base_model = ResNet50(
        weights='imagenet',
        include_top=False,
        input_shape=(img_size[0], img_size[1], 3)
    )
    base_model.trainable = False  # Transfer learning: önce frozen
    
    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(512, activation='relu')(x)
    x = Dropout(0.3)(x)
    x = Dense(256, activation='relu')(x)
    x = Dropout(0.2)(x)
    
    # Multi-output regression
    outputs = [
        Dense(1, activation='relu', name='calories')(x),
        Dense(1, activation='relu', name='fat')(x),
        Dense(1, activation='relu', name='carbs')(x),
        Dense(1, activation='relu', name='protein')(x),
        Dense(1, activation='relu', name='sugar')(x),
        Dense(1, activation='relu', name='salt')(x),
        Dense(1, activation='relu', name='sodium')(x),
    ]
    
    model = Model(inputs=base_model.input, outputs=outputs, name='food_image_calorie_predictor')
    return model


def main():
    parser = argparse.ArgumentParser(description="CNN/ResNet tabanlı görüntü kalori modeli eğitimi")
    parser.add_argument("--dataset", type=str, required=True, help="Görüntü klasörü yolu")
    parser.add_argument("--labels", type=str, required=True, help="Etiket JSONL dosyası yolu")
    parser.add_argument("--output", type=str, default="models/image_calorie_model.h5", help="Çıktı model dosyası")
    parser.add_argument("--epochs", type=int, default=50, help="Eğitim epoch sayısı")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--img-size", type=int, default=224, help="Görüntü boyutu (224x224)")
    parser.add_argument("--validation-split", type=float, default=0.2, help="Validation split oranı")
    parser.add_argument("--learning-rate", type=float, default=0.001, help="Learning rate")
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    labels_path = Path(args.labels)
    output_path = Path(args.output)
    
    if not dataset_dir.exists():
        print(f"ERROR: Dataset klasörü bulunamadı: {dataset_dir}")
        sys.exit(1)
    
    if not labels_path.exists():
        print(f"ERROR: Etiket dosyası bulunamadı: {labels_path}")
        sys.exit(1)
    
    print("Etiketler yükleniyor...")
    labels = load_labels(labels_path)
    print(f"{len(labels)} etiket yüklendi.")
    
    # Görüntüleri ve etiketleri yükle
    print("Görüntüler yükleniyor...")
    images = []
    targets = {
        'calories': [],
        'fat': [],
        'carbs': [],
        'protein': [],
        'sugar': [],
        'salt': [],
        'sodium': [],
    }
    
    valid_count = 0
    for label in labels:
        img_path = dataset_dir / label.image_path
        if not img_path.exists():
            print(f"UYARI: Görüntü bulunamadı: {img_path}")
            continue
        
        try:
            img = load_and_preprocess_image(img_path, target_size=(args.img_size, args.img_size))
            images.append(img)
            
            # Targets (NaN değerler 0 olarak kabul edilir)
            targets['calories'].append(label.calories_kcal if label.calories_kcal is not None else 0.0)
            targets['fat'].append(label.fat_g if label.fat_g is not None else 0.0)
            targets['carbs'].append(label.carbs_g if label.carbs_g is not None else 0.0)
            targets['protein'].append(label.protein_g if label.protein_g is not None else 0.0)
            targets['sugar'].append(label.sugar_g if label.sugar_g is not None else 0.0)
            targets['salt'].append(label.salt_g if label.salt_g is not None else 0.0)
            targets['sodium'].append(label.sodium_mg if label.sodium_mg is not None else 0.0)
            
            valid_count += 1
        except Exception as e:
            print(f"UYARI: Görüntü işlenemedi {img_path}: {e}")
            continue
    
    if valid_count == 0:
        print("ERROR: Geçerli görüntü bulunamadı!")
        sys.exit(1)
    
    print(f"{valid_count} görüntü yüklendi.")
    
    # NumPy array'e çevir
    X = np.array(images)
    y = [np.array(targets[key]) for key in ['calories', 'fat', 'carbs', 'protein', 'sugar', 'salt', 'sodium']]
    
    # Train/validation split
    split_idx = int(len(X) * (1 - args.validation_split))
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train = [yt[:split_idx] for yt in y]
    y_val = [yt[split_idx:] for yt in y]
    
    print(f"Train: {len(X_train)} örnek, Validation: {len(X_val)} örnek")
    
    # Model oluştur
    print("Model oluşturuluyor...")
    model = create_model(img_size=(args.img_size, args.img_size))
    
    # Compile
    model.compile(
        optimizer=Adam(learning_rate=args.learning_rate),
        loss='mse',  # Mean Squared Error for regression
        metrics=['mae'],  # Mean Absolute Error
        loss_weights=[1.0, 0.5, 0.5, 0.5, 0.3, 0.3, 0.3]  # Kaloriye daha fazla ağırlık
    )
    
    print("Model yapısı:")
    model.summary()
    
    # Callbacks
    output_path.parent.mkdir(parents=True, exist_ok=True)
    callbacks = [
        ModelCheckpoint(
            str(output_path),
            monitor='val_loss',
            save_best_only=True,
            verbose=1
        ),
        EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True,
            verbose=1
        ),
        ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=1e-7,
            verbose=1
        )
    ]
    
    # Eğitim
    print("Eğitim başlatılıyor...")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=callbacks,
        verbose=1
    )
    
    print(f"\nEğitim tamamlandı! Model kaydedildi: {output_path}")
    print(f"Final validation loss: {min(history.history['val_loss']):.4f}")


if __name__ == "__main__":
    main()

