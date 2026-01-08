from __future__ import annotations

"""
Kalori hesaplama modülü.
BMR (Basal Metabolic Rate) ve TDEE (Total Daily Energy Expenditure) hesaplamaları.
"""


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """
    BMR (Basal Metabolic Rate) hesaplar.
    Mifflin-St Jeor Equation kullanılır (daha doğru).
    
    Args:
        weight_kg: Kilo (kg)
        height_cm: Boy (cm)
        age: Yaş
        gender: "male", "female", veya "other"
    
    Returns:
        Günlük bazal metabolik hız (kcal/gün)
    """
    # Mifflin-St Jeor Equation
    # Erkek: BMR = 10 * weight(kg) + 6.25 * height(cm) - 5 * age(years) + 5
    # Kadın: BMR = 10 * weight(kg) + 6.25 * height(cm) - 5 * age(years) - 161
    
    base_bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
    
    if gender == "male":
        bmr = base_bmr + 5
    elif gender == "female":
        bmr = base_bmr - 161
    else:
        # "other" için ortalama alınır
        bmr_male = base_bmr + 5
        bmr_female = base_bmr - 161
        bmr = (bmr_male + bmr_female) / 2
    
    return max(bmr, 800.0)  # Minimum 800 kcal (güvenlik)


def get_activity_multiplier(activity_level: str) -> float:
    """
    Aktivite seviyesine göre çarpan döndürür (TDEE hesaplama için).
    
    Args:
        activity_level: "sedentary", "light", "moderate", "active", "very_active"
    
    Returns:
        Aktivite çarpanı
    """
    multipliers = {
        "sedentary": 1.2,  # Hareketsiz (az hareket, masa başı iş)
        "light": 1.375,  # Hafif aktif (hafif egzersiz, 1-3 gün/hafta)
        "moderate": 1.55,  # Orta aktif (orta egzersiz, 3-5 gün/hafta)
        "active": 1.725,  # Çok aktif (ağır egzersiz, 6-7 gün/hafta)
        "very_active": 1.9,  # Ekstra aktif (çok ağır egzersiz, fiziksel iş)
    }
    return multipliers.get(activity_level.lower(), 1.2)  # Default: sedentary


def calculate_tdee(weight_kg: float, height_cm: float, age: int, gender: str, activity_level: str) -> float:
    """
    TDEE (Total Daily Energy Expenditure) hesaplar.
    
    TDEE = BMR * Activity Multiplier
    
    Args:
        weight_kg: Kilo (kg)
        height_cm: Boy (cm)
        age: Yaş
        gender: "male", "female", veya "other"
        activity_level: "sedentary", "light", "moderate", "active", "very_active"
    
    Returns:
        Günlük toplam enerji harcaması (kcal/gün)
    """
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    multiplier = get_activity_multiplier(activity_level)
    tdee = bmr * multiplier
    return round(tdee, 1)


def calculate_daily_calorie_target(
    weight_kg: float | None,
    height_cm: float | None,
    age: int | None,
    gender: str | None,
    activity_level: str | None,
    goal: str = "maintain",
) -> dict[str, float | None]:
    """
    Kullanıcının günlük kalori hedefini hesaplar.
    
    Args:
        weight_kg: Kilo (kg)
        height_cm: Boy (cm)
        age: Yaş
        gender: "male", "female", veya "other"
        activity_level: "sedentary", "light", "moderate", "active", "very_active"
        goal: "lose" (kilo verme), "maintain" (koruma), "gain" (kilo alma)
    
    Returns:
        {
            "bmr": float | None,  # Bazal metabolik hız
            "tdee": float | None,  # Toplam günlük enerji harcaması
            "target": float | None,  # Hedef kalori (goal'a göre)
            "min": float | None,  # Minimum güvenli kalori
            "max": float | None,  # Maksimum önerilen kalori
        }
    """
    # Gerekli bilgiler eksikse None döndür
    if not all([weight_kg, height_cm, age, gender, activity_level]):
        return {
            "bmr": None,
            "tdee": None,
            "target": None,
            "min": None,
            "max": None,
        }
    
    # Validasyon
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        return {
            "bmr": None,
            "tdee": None,
            "target": None,
            "min": None,
            "max": None,
        }
    
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    tdee = calculate_tdee(weight_kg, height_cm, age, gender, activity_level)
    
    # Goal'a göre hedef kalori
    goal_multipliers = {
        "lose": 0.85,  # %15 açık (kilo verme)
        "maintain": 1.0,  # TDEE (koruma)
        "gain": 1.15,  # %15 fazla (kilo alma)
    }
    multiplier = goal_multipliers.get(goal.lower(), 1.0)
    target = tdee * multiplier
    
    # Güvenli sınırlar
    min_cal = max(bmr * 0.8, 1200.0)  # Minimum: BMR'in %80'i veya 1200 kcal (kadınlar için)
    max_cal = tdee * 1.5  # Maksimum: TDEE'in %150'si
    
    return {
        "bmr": round(bmr, 1),
        "tdee": round(tdee, 1),
        "target": round(target, 1),
        "min": round(min_cal, 1),
        "max": round(max_cal, 1),
    }


def check_calorie_limit(
    consumed: float,
    target: float | None,
    min_limit: float | None = None,
    max_limit: float | None = None,
) -> dict[str, bool | float | None]:
    """
    Tüketilen kaloriyi hedef ve sınırlarla karşılaştırır.
    
    Args:
        consumed: Tüketilen kalori (kcal)
        target: Hedef kalori (kcal/gün)
        min_limit: Minimum güvenli kalori (kcal/gün)
        max_limit: Maksimum önerilen kalori (kcal/gün)
    
    Returns:
        {
            "is_over": bool,  # Maksimum sınırı aştı mı?
            "is_under": bool,  # Minimum sınırın altında mı?
            "is_over_target": bool,  # Hedefin üzerinde mi?
            "remaining": float | None,  # Kalan kalori (hedef - tüketilen)
            "excess": float | None,  # Aşım miktarı (tüketilen - maksimum)
        }
    """
    is_over = False
    is_under = False
    is_over_target = False
    remaining = None
    excess = None
    
    if target is not None:
        remaining = max(0, target - consumed)
        is_over_target = consumed > target
    
    if max_limit is not None:
        is_over = consumed > max_limit
        if is_over:
            excess = consumed - max_limit
    
    if min_limit is not None:
        is_under = consumed < min_limit
    
    return {
        "is_over": is_over,
        "is_under": is_under,
        "is_over_target": is_over_target,
        "remaining": round(remaining, 1) if remaining is not None else None,
        "excess": round(excess, 1) if excess is not None else None,
    }
