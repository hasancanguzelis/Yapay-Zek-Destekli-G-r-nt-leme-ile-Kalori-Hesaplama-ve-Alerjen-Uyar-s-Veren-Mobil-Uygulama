from __future__ import annotations

from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from .database import DailyConsumption, User
from .schemas import NutritionFacts


def get_today_consumption(db: Session, username: str) -> DailyConsumption | None:
    """Kullanıcının bugünkü tüketimini getir."""
    today = date.today()
    return db.query(DailyConsumption).filter(
        and_(
            DailyConsumption.username == username,
            DailyConsumption.consumption_date == today,
        )
    ).first()


def add_consumption(
    db: Session,
    username: str,
    nutrition: NutritionFacts,
    consumption_date: date | None = None,
) -> DailyConsumption:
    """
    Günlük tüketime besin değerleri ekler (toplar).
    Eğer o gün için kayıt yoksa yeni oluşturur.
    """
    if consumption_date is None:
        consumption_date = date.today()
    
    # Mevcut kaydı bul veya yeni oluştur
    record = db.query(DailyConsumption).filter(
        and_(
            DailyConsumption.username == username,
            DailyConsumption.consumption_date == consumption_date,
        )
    ).first()
    
    if record:
        # Mevcut değerlere ekle
        record.calories_kcal = (record.calories_kcal or 0.0) + (nutrition.calories_kcal or 0.0)
        record.fat_g = (record.fat_g or 0.0) + (nutrition.fat_g or 0.0)
        record.carbs_g = (record.carbs_g or 0.0) + (nutrition.carbs_g or 0.0)
        record.protein_g = (record.protein_g or 0.0) + (nutrition.protein_g or 0.0)
        record.sugar_g = (record.sugar_g or 0.0) + (nutrition.sugar_g or 0.0)
        record.salt_g = (record.salt_g or 0.0) + (nutrition.salt_g or 0.0)
        record.sodium_mg = (record.sodium_mg or 0.0) + (nutrition.sodium_mg or 0.0)
        record.updated_at = datetime.utcnow()
    else:
        # Yeni kayıt oluştur
        record = DailyConsumption(
            username=username,
            consumption_date=consumption_date,
            calories_kcal=nutrition.calories_kcal or 0.0,
            fat_g=nutrition.fat_g or 0.0,
            carbs_g=nutrition.carbs_g or 0.0,
            protein_g=nutrition.protein_g or 0.0,
            sugar_g=nutrition.sugar_g or 0.0,
            salt_g=nutrition.salt_g or 0.0,
            sodium_mg=nutrition.sodium_mg or 0.0,
        )
        db.add(record)
    
    db.commit()
    db.refresh(record)
    return record


def get_consumption_by_date(
    db: Session,
    username: str,
    consumption_date: date,
) -> DailyConsumption | None:
    """Belirli bir tarihteki tüketimi getir."""
    return db.query(DailyConsumption).filter(
        and_(
            DailyConsumption.username == username,
            DailyConsumption.consumption_date == consumption_date,
        )
    ).first()


def get_consumption_range(
    db: Session,
    username: str,
    start_date: date,
    end_date: date,
) -> list[DailyConsumption]:
    """Tarih aralığındaki tüketimleri getir."""
    return db.query(DailyConsumption).filter(
        and_(
            DailyConsumption.username == username,
            DailyConsumption.consumption_date >= start_date,
            DailyConsumption.consumption_date <= end_date,
        )
    ).order_by(DailyConsumption.consumption_date.desc()).all()


def update_consumption(
    db: Session,
    username: str,
    consumption_date: date,
    nutrition: NutritionFacts,
) -> DailyConsumption | None:
    """Belirli bir tarihteki tüketimi güncelle (toplama değil, değiştirme)."""
    record = get_consumption_by_date(db, username, consumption_date)
    if not record:
        return None
    
    record.calories_kcal = nutrition.calories_kcal or 0.0
    record.fat_g = nutrition.fat_g or 0.0
    record.carbs_g = nutrition.carbs_g or 0.0
    record.protein_g = nutrition.protein_g or 0.0
    record.sugar_g = nutrition.sugar_g or 0.0
    record.salt_g = nutrition.salt_g or 0.0
    record.sodium_mg = nutrition.sodium_mg or 0.0
    record.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(record)
    return record


def delete_consumption(
    db: Session,
    username: str,
    consumption_date: date,
) -> bool:
    """Belirli bir tarihteki tüketimi sil."""
    record = get_consumption_by_date(db, username, consumption_date)
    if not record:
        return False
    
    db.delete(record)
    db.commit()
    return True
