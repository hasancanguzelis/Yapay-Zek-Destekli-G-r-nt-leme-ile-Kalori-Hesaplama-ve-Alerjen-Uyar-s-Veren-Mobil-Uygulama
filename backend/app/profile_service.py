from __future__ import annotations

import json
from sqlalchemy.orm import Session

from .database import User


def get_user_profile(db: Session, username: str) -> dict:
    """Kullanıcının profilini getir."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {"allergens": [], "conditions": [], "age": None, "weight_kg": None, "height_cm": None, "gender": None, "activity_level": None}
    
    allergens = []
    conditions = []
    
    if user.profile_allergens:
        try:
            allergens = json.loads(user.profile_allergens)
        except (json.JSONDecodeError, TypeError):
            allergens = []
    
    if user.profile_conditions:
        try:
            conditions = json.loads(user.profile_conditions)
        except (json.JSONDecodeError, TypeError):
            conditions = []
    
    # Fiziksel özellikler
    age = None
    if user.profile_age:
        try:
            age = int(user.profile_age)
        except (ValueError, TypeError):
            age = None
    
    weight_kg = None
    if user.profile_weight_kg:
        try:
            weight_kg = float(user.profile_weight_kg)
        except (ValueError, TypeError):
            weight_kg = None
    
    height_cm = None
    if user.profile_height_cm:
        try:
            height_cm = float(user.profile_height_cm)
        except (ValueError, TypeError):
            height_cm = None
    
    return {
        "allergens": allergens if isinstance(allergens, list) else [],
        "conditions": conditions if isinstance(conditions, list) else [],
        "age": age,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "gender": user.profile_gender if user.profile_gender else None,
        "activity_level": user.profile_activity_level if user.profile_activity_level else None,
    }


def update_user_profile(
    db: Session,
    username: str,
    allergens: list[str] | None = None,
    conditions: list[str] | None = None,
    age: int | None = None,
    weight_kg: float | None = None,
    height_cm: float | None = None,
    gender: str | None = None,
    activity_level: str | None = None,
) -> bool:
    """Kullanıcının profilini güncelle."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    
    if allergens is not None:
        user.profile_allergens = json.dumps(allergens, ensure_ascii=False)
    
    if conditions is not None:
        user.profile_conditions = json.dumps(conditions, ensure_ascii=False)
    
    if age is not None:
        user.profile_age = str(age) if age else None
    elif age is not None and age == 0:  # Explicit None
        user.profile_age = None
    
    if weight_kg is not None:
        user.profile_weight_kg = str(weight_kg) if weight_kg else None
    elif weight_kg is not None and weight_kg == 0:  # Explicit None
        user.profile_weight_kg = None
    
    if height_cm is not None:
        user.profile_height_cm = str(height_cm) if height_cm else None
    elif height_cm is not None and height_cm == 0:  # Explicit None
        user.profile_height_cm = None
    
    if gender is not None:
        user.profile_gender = gender if gender else None
    
    if activity_level is not None:
        user.profile_activity_level = activity_level if activity_level else None
    
    db.commit()
    db.refresh(user)
    return True

