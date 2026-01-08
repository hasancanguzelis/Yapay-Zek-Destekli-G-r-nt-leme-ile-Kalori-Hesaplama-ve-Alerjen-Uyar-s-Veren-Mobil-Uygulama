from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    allergens: list[str] = Field(default_factory=list, description="Kullanıcının kaçındığı alerjenler.")
    conditions: list[str] = Field(
        default_factory=list,
        description="Opsiyonel: diyabet, çölyak vb. (ileride kural seti için).",
    )
    age: int | None = Field(None, ge=1, le=120, description="Kullanıcının yaşı (kalori hesaplama için).")
    weight_kg: float | None = Field(None, ge=1.0, le=500.0, description="Kullanıcının kilosu (kg) - kalori hesaplama için.")
    height_cm: float | None = Field(None, ge=50.0, le=300.0, description="Kullanıcının boyu (cm) - kalori hesaplama için.")
    gender: Literal["male", "female", "other"] | None = Field(None, description="Cinsiyet - kalori hesaplama için (male/female/other).")
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"] | None = Field(
        None, description="Fiziksel aktivite seviyesi - TDEE hesaplama için."
    )


class NutritionFacts(BaseModel):
    calories_kcal: float | None = None
    fat_g: float | None = None
    carbs_g: float | None = None
    protein_g: float | None = None
    sugar_g: float | None = None
    salt_g: float | None = None
    sodium_mg: float | None = None


class AnalyzeResponse(BaseModel):
    extracted_text: str
    ingredients: list[str] = Field(default_factory=list)
    nutrition: NutritionFacts = Field(default_factory=NutritionFacts)
    detected_allergens: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: Literal["ocr_only", "ocr_plus_external", "barcode_only", "meal_estimate", "meal_model", "image_calorie_model"] = "ocr_only"


class AllergenPredictRequest(BaseModel):
    text: str = Field(..., description="Serbest metin veya 'İçindekiler' satırı.")
    top_k: int = Field(10, ge=1, le=50, description="En yüksek olasılıklı ilk K label.")


class AllergenScore(BaseModel):
    label: str
    prob: float
    threshold: float


class AllergenPredictResponse(BaseModel):
    predicted: list[str] = Field(default_factory=list, description="Threshold sonrası seçilen label'lar.")
    scores: list[AllergenScore] = Field(default_factory=list, description="Top-K olasılık ve threshold bilgisi.")
    model_path: str


class AssistantRequest(BaseModel):
    message: str = Field(..., description="Kullanıcı mesajı")
    ui_lang: str | None = Field(None, description="UI dili (tr/en)")


class AssistantResponse(BaseModel):
    response: str = Field(..., description="Asistan yanıtı")
    detected_conditions: list[str] = Field(default_factory=list, description="Tespit edilen hastalıklar")
    detected_allergens: list[str] = Field(default_factory=list, description="Tespit edilen alerjenler")
    suggestions: list[str] = Field(default_factory=list, description="Öneriler")
    needs_medical_attention: bool = Field(False, description="Tıbbi yardım gerekli mi?")
    disclaimer: str = Field(..., description="Sağlık uyarısı")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, description="Kullanıcı adı (minimum 3 karakter)")
    password: str = Field(..., min_length=6, description="Şifre (minimum 6 karakter)")


class LoginRequest(BaseModel):
    username: str = Field(..., description="Kullanıcı adı")
    password: str = Field(..., description="Şifre")


class AuthResponse(BaseModel):
    access_token: str = Field(..., description="JWT token")
    token_type: str = Field(default="bearer", description="Token tipi")
    username: str = Field(..., description="Kullanıcı adı")


class DailyConsumptionResponse(BaseModel):
    date: str = Field(..., description="Tarih (YYYY-MM-DD)")
    nutrition: NutritionFacts = Field(..., description="Besin değerleri")
    bmr: float | None = Field(None, description="Bazal metabolik hız")
    tdee: float | None = Field(None, description="Toplam günlük enerji harcaması")
    target: float | None = Field(None, description="Hedef kalori")
    remaining: float | None = Field(None, description="Kalan kalori")
    is_over_target: bool = Field(False, description="Hedef aşıldı mı?")
    is_over_limit: bool = Field(False, description="Maksimum sınır aşıldı mı?")
    warnings: list[str] = Field(default_factory=list, description="Uyarılar")


class CalorieTargetResponse(BaseModel):
    bmr: float | None = Field(None, description="Bazal metabolik hız")
    tdee: float | None = Field(None, description="Toplam günlük enerji harcaması")
    target: float | None = Field(None, description="Hedef kalori")
    min: float | None = Field(None, description="Minimum güvenli kalori")
    max: float | None = Field(None, description="Maksimum önerilen kalori")


