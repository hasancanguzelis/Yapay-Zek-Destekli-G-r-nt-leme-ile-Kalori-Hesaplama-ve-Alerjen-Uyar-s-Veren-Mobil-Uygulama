#!/usr/bin/env python3
"""
Görüntü kalori dataset'i hazırlama scripti.

Bu script, yemek görüntüleri ve etiketlerini toplayarak eğitim için dataset oluşturur.
USDA API'den besin bilgilerini çekerek görüntüler için etiket oluşturur.

Kullanım:
    py -m backend.scripts.prepare_image_calorie_dataset \
        --foods "pilav,kuru fasulye,mercimek çorbası,çorba,menemen,omlet,çılbır,balık,ton balığı,tavuk göğsü" \
        --images-per-food 5 \
        --output data/food_images/labels.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import random
import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_root))

from typing import Any

from PIL import Image as PILImage

try:
    from app.external.usda import search_foods
    from app.config import get_settings
    settings = get_settings()
except ImportError as e:
    print(f"ERROR: Backend import hatası: {e}")
    sys.exit(1)


async def fetch_nutrition_for_food(food_name: str) -> dict[str, float | None] | None:
    """USDA API'den yemek adı için besin bilgilerini çek."""
    try:
        data = await search_foods(
            query=food_name,
            api_key=settings.usda_api_key,
            timeout_s=10.0,
            retries=1,
            retry_backoff_s=1.0,
        )
        foods = data.get("foods") or []
        if not foods:
            return None
        
        # İlk sonucu al
        food = foods[0]
        nutrients = food.get("foodNutrients") or []
        
        nutrition = {
            "calories_kcal": None,
            "fat_g": None,
            "carbs_g": None,
            "protein_g": None,
            "sugar_g": None,
            "salt_g": None,
            "sodium_mg": None,
        }
        
        for n in nutrients:
            name = (n.get("nutrientName") or "").lower()
            val = n.get("value")
            unit = (n.get("unitName") or "").lower()
            
            if val is None:
                continue
            
            if "energy" in name and (unit == "kcal" or unit == ""):
                nutrition["calories_kcal"] = float(val)
            elif name.startswith("protein"):
                nutrition["protein_g"] = float(val)
            elif "carbohydrate" in name:
                nutrition["carbs_g"] = float(val)
            elif "total lipid" in name or name == "fat":
                nutrition["fat_g"] = float(val)
            elif "sugars" in name:
                nutrition["sugar_g"] = float(val)
            elif "sodium" in name and unit in {"mg", ""}:
                nutrition["sodium_mg"] = float(val)
            elif "salt" in name and unit in {"g", ""}:
                nutrition["salt_g"] = float(val)
        
        return nutrition
    except Exception as e:
        print(f"UYARI: {food_name} için besin bilgisi alınamadı: {e}")
        return None


async def create_dataset_structure(
    food_names: list[str],
    images_per_food: int,
    output_dir: Path,
    labels_file: Path,
) -> None:
    """
    Dataset yapısını oluştur.
    
    Yapı:
    data/food_images/
        ├── labels.jsonl  (her satır: {"image_path": "...", "calories_kcal": 350.0, ...})
        └── images/
            ├── food1/
            │   ├── image1.jpg
            │   ├── image2.jpg
            │   └── ...
            ├── food2/
            └── ...
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    labels = []
    
    print(f"{len(food_names)} yiyecek için dataset hazırlanıyor...")
    print(f"Her yiyecek için {images_per_food} görüntü etiketi oluşturulacak.\n")
    
    for food_name in food_names:
        print(f"İşleniyor: {food_name}")
        
        # USDA'dan besin bilgilerini çek
        nutrition = await fetch_nutrition_for_food(food_name)
        if not nutrition:
            print(f"  UYARI: Besin bilgisi bulunamadi, atlaniyor.")
            continue
        
        if nutrition["calories_kcal"] is None:
            print(f"  ⚠️  Kalori bilgisi yok, atlanıyor.")
            continue
        
        print(f"  OK: Kalori: {nutrition['calories_kcal']:.1f} kcal")
        
        # Her yiyecek için görüntü etiketleri oluştur
        food_dir = images_dir / food_name.replace(" ", "_").replace("/", "_")
        food_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(images_per_food):
            image_filename = f"{food_name.replace(' ', '_').replace('/', '_')}_{i+1:03d}.jpg"
            image_path = f"images/{food_name.replace(' ', '_').replace('/', '_')}/{image_filename}"
            
            label_entry = {
                "image_path": image_path,
                "dish_name": food_name,
                **{k: v for k, v in nutrition.items() if v is not None}
            }
            labels.append(label_entry)
        
        print(f"  OK: {images_per_food} goruntu etiketi olusturuldu\n")
    
    # Labels.jsonl dosyasına yaz
    print(f"\nEtiketler kaydediliyor: {labels_file}")
    with open(labels_file, "w", encoding="utf-8") as f:
        for label in labels:
            f.write(json.dumps(label, ensure_ascii=False) + "\n")
    
    print(f"OK: Toplam {len(labels)} etiket olusturuldu.")
    
    # Test için placeholder görüntüler oluştur (basit renkli dikdörtgenler)
    print("\nTest için placeholder görüntüler oluşturuluyor...")
    
    created_count = 0
    for food_name in food_names:
        food_dir = images_dir / food_name.replace(" ", "_").replace("/", "_")
        if not food_dir.exists():
            continue
        
        nutrition = await fetch_nutrition_for_food(food_name)
        if not nutrition:
            continue
        
        # Her yiyecek için basit placeholder görüntüler oluştur
        for i in range(images_per_food):
            image_filename = f"{food_name.replace(' ', '_').replace('/', '_')}_{i+1:03d}.jpg"
            image_path = food_dir / image_filename
            
            if image_path.exists():
                continue
            
            # Basit placeholder görüntü (renkli dikdörtgen)
            # Kaloriye göre renk tonu (düşük kalori = açık, yüksek kalori = koyu)
            calories = nutrition.get("calories_kcal") or 300.0
            # Normalize: 0-1000 kcal arası -> 0-255 arası
            intensity = int(min(255, max(50, calories / 1000.0 * 255)))
            
            # Her yiyecek için farklı bir renk tonu
            color_variation = random.randint(-30, 30)
            r = min(255, max(0, intensity + color_variation))
            g = min(255, max(0, intensity - color_variation // 2))
            b = min(255, max(0, intensity + color_variation // 3))
            
            img = PILImage.new('RGB', (224, 224), (r, g, b))
            img.save(image_path, 'JPEG', quality=85)
            created_count += 1
    
    print(f"OK: {created_count} placeholder goruntu olusturuldu.")
    print(f"\nNOT: Bu görüntüler sadece test amaçlıdır. Gerçek eğitim için gerçek gıda görüntüleri gereklidir.")
    print(f"Her yiyecek için ayrı klasörler oluşturuldu:")
    for food_name in food_names:
        food_dir = images_dir / food_name.replace(" ", "_").replace("/", "_")
        if food_dir.exists():
            image_count = len(list(food_dir.glob("*.jpg")))
            print(f"  - {food_dir} ({image_count} görüntü)")


async def main_async():
    parser = argparse.ArgumentParser(
        description="Görüntü kalori dataset'i hazırlama"
    )
    parser.add_argument(
        "--foods",
        type=str,
        required=True,
        help="Virgülle ayrılmış yemek adları (örn: 'pilav,kuru fasulye,menemen')"
    )
    parser.add_argument(
        "--images-per-food",
        type=int,
        default=5,
        help="Her yiyecek için kaç görüntü etiketi oluşturulacak (default: 5)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/food_images/labels.jsonl",
        help="Çıktı labels.jsonl dosyası yolu"
    )
    
    args = parser.parse_args()
    
    if not settings.usda_api_key:
        print("ERROR: USDA_API_KEY ayarlı değil. backend/.env dosyasına ekleyin.")
        sys.exit(1)
    
    food_names = [f.strip() for f in args.foods.split(",") if f.strip()]
    if not food_names:
        print("ERROR: En az bir yemek adı gerekli.")
        sys.exit(1)
    
    output_path = Path(args.output)
    output_dir = output_path.parent
    
    print("=" * 60)
    print("Görüntü Kalori Dataset Hazırlama")
    print("=" * 60)
    print(f"Yiyecekler: {', '.join(food_names)}")
    print(f"Yiyecek başına görüntü: {args.images_per_food}")
    print(f"Çıktı: {output_path}")
    print("=" * 60)
    print()
    
    await create_dataset_structure(
        food_names=food_names,
        images_per_food=args.images_per_food,
        output_dir=output_dir,
        labels_file=output_path,
    )
    
    print("\n" + "=" * 60)
    print("Dataset yapısı hazır!")
    print("=" * 60)
    print("\nSonraki adımlar:")
    print("1. Gerçek görüntüleri 'images/<food_name>/' klasörlerine yerleştirin")
    print("2. Model eğitimi için: py -m backend.scripts.train_image_calorie_model")
    print()


def main():
    import asyncio
    import sys
    import io
    # Windows console encoding sorununu çöz
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

