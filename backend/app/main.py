from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import date

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.requests import Request

from .allergens import allergen_label, detect_allergens, infer_allergens_from_food_text, match_profile_allergens, matched_allergen_terms
from .assistant import analyze_user_message, get_disclaimer
from .auth import authenticate_user, create_access_token, create_user, decode_access_token
from .profile_service import get_user_profile, update_user_profile
from .consumption_service import (
    get_today_consumption,
    add_consumption,
    get_consumption_by_date,
    get_consumption_range,
    delete_consumption,
)
from .calorie_calculator import (
    calculate_daily_calorie_target,
    check_calorie_limit,
)
from .conditions import condition_warnings
from .config import get_settings
from .database import User, init_db, get_db
from .external.open_food_facts import extract_basic_fields, fetch_product_by_barcode
from .external.usda import search_foods
from .ml_allergens import AllergenModelError, load_allergen_model
from .ml_meal_calories import MealCalorieModelError, load_meal_calorie_model, predict_nutrition
from .ml_image_calories import ImageCalorieModelError, load_image_calorie_model, predict_nutrition_from_image
from .nlp import extract_ingredients, parse_nutrition_facts
from .ocr import OcrUnavailableError, ocr_image_bytes
from .schemas import (
    AllergenPredictRequest,
    AllergenPredictResponse,
    AllergenScore,
    AnalyzeResponse,
    AssistantRequest,
    AssistantResponse,
    AuthResponse,
    CalorieTargetResponse,
    DailyConsumptionResponse,
    LoginRequest,
    NutritionFacts,
    RegisterRequest,
    UserProfile,
)
from .utils import normalize_space


settings = get_settings()

# Veritabanını başlat
init_db()

app = FastAPI(title="Tez-Proje API", version="0.1.0")

logger = logging.getLogger("tezproje")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

allow_origins = settings.cors_allow_origins or ([] if settings.app_env != "dev" else ["*"])
if allow_origins == ["*"] and settings.cors_allow_credentials and settings.app_env != "dev":
    # Hard safety: don't allow wildcard origins with credentials in prod-like env.
    raise RuntimeError("Prod ortamında CORS_ALLOW_ORIGINS='*' ve CORS_ALLOW_CREDENTIALS=true kullanılamaz.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins if allow_origins else [],
    allow_credentials=settings.cors_allow_credentials if allow_origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BARCODE_RE = re.compile(r"^\d{8}(\d{4}|\d{5}|\d{6})?$")  # 8,12,13,14 digits


@app.middleware("http")
async def request_id_and_access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
    finally:
        dur_ms = (time.perf_counter() - start) * 1000.0
        # response may not exist on hard failures; log what we can
        status = getattr(response, "status_code", "ERR")
        logger.info(
            "%s %s status=%s dur_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            status,
            dur_ms,
            request_id,
        )


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/predict/allergens", response_model=AllergenPredictResponse)
async def predict_allergens(request: Request) -> AllergenPredictResponse:
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Body boş olamaz.")

    # Be tolerant to Windows PowerShell which may send UTF-16 JSON without charset.
    content_type = (request.headers.get("content-type") or "").lower()
    charset: str | None = None
    if "charset=" in content_type:
        charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip() or None

    def _decode_body(b: bytes) -> str:
        if charset:
            return b.decode(charset)
        # BOM-based UTF-16 detection
        if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
            return b.decode("utf-16")
        # Heuristic: lots of null bytes => likely UTF-16
        if b"\x00" in b[:64]:
            try:
                return b.decode("utf-16")
            except Exception:
                pass
        return b.decode("utf-8")

    try:
        body_text = _decode_body(raw)
        obj = json.loads(body_text)
        req = AllergenPredictRequest.model_validate(obj)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Body JSON parse hatası: {type(e).__name__}: {e}") from e

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text boş olamaz.")
    try:
        model = load_allergen_model()
    except AllergenModelError as e:
        # Optional feature; treat as "not available" rather than 500.
        raise HTTPException(status_code=501, detail=str(e)) from e

    pipeline = model.pipeline
    try:
        probs = pipeline.predict_proba([text])[0]
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Model predict_proba başarısız: {type(e).__name__}: {e}") from e

    classes = model.classes
    thresholds = model.thresholds
    triples = list(zip(classes, [float(p) for p in probs], [float(t) for t in thresholds]))
    triples_sorted = sorted(triples, key=lambda x: x[1], reverse=True)

    predicted = sorted([lab for lab, p, th in triples if p >= th])
    scores = [AllergenScore(label=lab, prob=p, threshold=th) for lab, p, th in triples_sorted[: req.top_k]]
    return AllergenPredictResponse(predicted=predicted, scores=scores, model_path=str(model.path))


def _parse_profile(user_profile_json: str | None) -> UserProfile:
    profile = UserProfile()
    if user_profile_json:
        try:
            profile = UserProfile.model_validate(json.loads(user_profile_json))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"user_profile_json geçersiz: {e}") from e
    return profile


def _profile_warnings(
    detected: set[str],
    profile: UserProfile,
    nutrition: NutritionFacts,
    context_text: str,
    ui_lang: str | None = None,
) -> list[str]:
    matched, unknown_profile = match_profile_allergens(sorted(detected), profile.allergens)
    warnings: list[str] = []
    if matched:
        details: list[str] = []
        for a in matched:
            terms = matched_allergen_terms(context_text, a)
            label = allergen_label(a, ui_lang=ui_lang)
            if terms:
                details.append(f"{label} ({', '.join(terms)})")
            else:
                details.append(label)
        joined = ", ".join(details)
        if (ui_lang or "").lower().startswith("en"):
            warnings.append(f"Warning (Allergen): Selected allergen(s) detected: {joined}")
        else:
            warnings.append(f"Uyarı (Alerjen): profilde seçili alerjen(ler) tespit edildi: {joined}")
    # Conditions-based warnings (nutrition/ingredient heuristics)
    warnings.extend(
        condition_warnings(
            profile=profile,
            nutrition=nutrition,
            context_text=context_text,
            detected_allergens=detected,
            ui_lang=ui_lang,
        )
    )
    return warnings


def _try_ml_detect_allergens(text: str) -> set[str]:
    """
    Optional: if allergen ML model is available, use it to augment detection.
    Never fails the request; falls back silently.
    """
    try:
        model = load_allergen_model()
    except AllergenModelError:
        return set()
    try:
        probs = model.pipeline.predict_proba([text])[0]
        out: set[str] = set()
        for lab, p, th in zip(model.classes, probs, model.thresholds):
            if float(p) >= float(th):
                out.add(lab)
        return out
    except Exception:
        return set()


def _extract_usda_nutrition(food: dict) -> NutritionFacts:
    """
    Heuristic mapping from USDA FoodData Central search result.
    Uses per-100g values when available.
    """
    nf = NutritionFacts()
    nutrients = food.get("foodNutrients") or []
    for n in nutrients:
        name = (n.get("nutrientName") or "").lower()
        val = n.get("value")
        unit = (n.get("unitName") or "").lower()
        if val is None:
            continue

        if "energy" in name and (unit == "kcal" or unit == ""):
            nf.calories_kcal = float(val)
        elif name.startswith("protein"):
            nf.protein_g = float(val)
        elif "carbohydrate" in name:
            nf.carbs_g = float(val)
        elif "total lipid" in name or name == "fat":
            nf.fat_g = float(val)
        elif "sugars" in name:
            nf.sugar_g = float(val)
        elif "sodium" in name and unit in {"mg", ""}:
            nf.sodium_mg = float(val)
        elif "salt" in name and unit in {"g", ""}:
            nf.salt_g = float(val)
    return nf


def _validate_barcode(barcode: str) -> str:
    b = (barcode or "").strip()
    if not b:
        raise HTTPException(status_code=400, detail="barcode boş olamaz.")
    if not BARCODE_RE.match(b):
        raise HTTPException(status_code=400, detail="barcode formatı geçersiz. (8/12/13/14 haneli sayısal olmalı)")
    return b


def _pick_best_usda_food(foods: list[dict]) -> dict:
    # Prefer explicit score if present, otherwise fallback to first.
    def score(f: dict) -> float:
        s = f.get("score")
        if isinstance(s, (int, float)):
            return float(s)
        s2 = f.get("searchScore")
        if isinstance(s2, (int, float)):
            return float(s2)
        return 0.0

    return max(foods, key=score)


def _tr_to_ascii(s: str) -> str:
    return s.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))


def _usda_query_candidates(dish: str) -> list[str]:
    """
    USDA araması İngilizce ağırlıklı olduğu için, Türkçe yemek adları için birkaç makul alternatif deneriz.
    Bu bir çeviri modeli değildir; sadece küçük bir alias + transliterasyon fallback'idir.
    """
    base = normalize_space((dish or "").strip())
    low = base.lower()

    aliases: dict[str, list[str]] = {
        "pilav": ["pilaf", "rice"],
        "kuru fasulye": ["white beans", "beans", "bean stew"],
        "mercimek çorbası": ["lentil soup"],
        "mercimek corbasi": ["lentil soup"],
        "köfte": ["kofte", "meatballs"],
        "kofte": ["meatballs"],
        "tavuk döner": ["chicken doner", "doner kebab chicken"],
        "döner": ["doner kebab"],
        "doner": ["doner kebab"],
        "menemen": ["menemen", "scrambled eggs"],
        "lahmacun": ["lahmacun", "turkish pizza"],
        "baklava": ["baklava"],
        "trileçe": ["tres leches", "cake", "milk cake"],
        "trilece": ["tres leches", "cake", "milk cake"],
        "çorba": ["soup"],
        "corba": ["soup"],
        "salata": ["salad"],
    }

    cands: list[str] = [base]
    # transliteration
    ascii_q = _tr_to_ascii(base)
    if ascii_q and ascii_q.lower() != low:
        cands.append(ascii_q)

    # exact alias
    if low in aliases:
        cands.extend(aliases[low])
    # also try removing common suffixes
    if low.endswith(" çorbası") or low.endswith(" corbasi"):
        cands.append("soup")

    # de-dup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for q in cands:
        qn = normalize_space(q)
        if not qn:
            continue
        k = qn.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(qn)
    return out[:6]


async def _search_usda_first_match(query: str) -> tuple[str, list[dict]]:
    """
    Tries multiple query variants; returns (used_query, foods).
    """
    last_err: Exception | None = None
    for q in _usda_query_candidates(query):
        try:
            data = await search_foods(
                query=q,
                api_key=settings.usda_api_key,
                timeout_s=settings.http_timeout_s,
                retries=settings.http_retries,
                retry_backoff_s=settings.http_retry_backoff_s,
            )
        except Exception as e:
            last_err = e
            continue
        foods = data.get("foods") or []
        if foods:
            return q, foods
    if last_err is not None:
        raise last_err
    return query, []


def _parse_portion(portion: str | None) -> float:
    raw = (portion or "").strip()
    if not raw:
        return 1.0
    raw = raw.replace(",", ".")
    try:
        v = float(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="portion geçersiz. Örn: 1 veya 1.5") from e
    if v <= 0:
        raise HTTPException(status_code=400, detail="portion 0'dan büyük olmalı.")
    if v > 20:
        raise HTTPException(status_code=400, detail="portion çok büyük (max 20).")
    return v


def _scale_nutrition(nf: NutritionFacts, factor: float) -> NutritionFacts:
    def s(x: float | None) -> float | None:
        return None if x is None else float(x) * factor

    return NutritionFacts(
        calories_kcal=s(nf.calories_kcal),
        fat_g=s(nf.fat_g),
        carbs_g=s(nf.carbs_g),
        protein_g=s(nf.protein_g),
        sugar_g=s(nf.sugar_g),
        salt_g=s(nf.salt_g),
        sodium_mg=s(nf.sodium_mg),
    )


def _average_usda_nutrition(foods: list[dict]) -> NutritionFacts:
    """
    USDA arama sonuçlarından (top-N) NutritionFacts değerlerini ortalama alır.
    Her alan için sadece mevcut (None olmayan) değerler ortalamaya katılır.
    """

    def avg(vals: list[float]) -> float | None:
        return (sum(vals) / len(vals)) if vals else None

    cals: list[float] = []
    fat: list[float] = []
    carbs: list[float] = []
    protein: list[float] = []
    sugar: list[float] = []
    salt: list[float] = []
    sodium: list[float] = []

    for f in foods:
        nf = _extract_usda_nutrition(f)
        if nf.calories_kcal is not None:
            cals.append(float(nf.calories_kcal))
        if nf.fat_g is not None:
            fat.append(float(nf.fat_g))
        if nf.carbs_g is not None:
            carbs.append(float(nf.carbs_g))
        if nf.protein_g is not None:
            protein.append(float(nf.protein_g))
        if nf.sugar_g is not None:
            sugar.append(float(nf.sugar_g))
        if nf.salt_g is not None:
            salt.append(float(nf.salt_g))
        if nf.sodium_mg is not None:
            sodium.append(float(nf.sodium_mg))

    return NutritionFacts(
        calories_kcal=avg(cals),
        fat_g=avg(fat),
        carbs_g=avg(carbs),
        protein_g=avg(protein),
        sugar_g=avg(sugar),
        salt_g=avg(salt),
        sodium_mg=avg(sodium),
    )


@app.post("/meal/estimate", response_model=AnalyzeResponse)
async def estimate_meal(
    dish_name: str | None = Form(None),
    portion: str | None = Form(None),
    user_profile_json: str | None = Form(None),
    ui_lang: str | None = Form(None),
) -> AnalyzeResponse:
    """
    Tabaklı yemek tahmini (v2):
    - dish_name + portion ile USDA araması yapılır ve top sonuçların ortalaması alınır.
    - portion: "porsiyon sayısı" olarak çarpan (örn: 1, 1.5, 2)
    """
    if not settings.usda_api_key:
        raise HTTPException(status_code=501, detail="USDA_API_KEY ayarlı değil. Meal analizi devre dışı.")

    profile = _parse_profile(user_profile_json)

    dish = (dish_name or "").strip()
    if not dish:
        raise HTTPException(status_code=400, detail="dish_name gerekli.")
    if len(dish) > 80:
        raise HTTPException(status_code=400, detail="dish_name çok uzun (max 80).")

    portion_factor = _parse_portion(portion)

    try:
        used_query, foods = await _search_usda_first_match(dish)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"USDA çağrısı başarısız: {e}") from e
    if not foods:
        # USDA bulunamazsa bile, isim/kurallardan alerjen+profil uyarılarını üretip boş besin değeriyle dön.
        detected = set(detect_allergens(dish))
        detected |= set(infer_allergens_from_food_text(dish))
        detected |= _try_ml_detect_allergens(dish)
        warnings = _profile_warnings(detected, profile, nutrition=NutritionFacts(), context_text=dish, ui_lang=ui_lang)
        return AnalyzeResponse(
            extracted_text=f"meal_estimate:{dish}",
            ingredients=[],
            nutrition=NutritionFacts(),
            detected_allergens=sorted(detected),
            warnings=warnings,
            source="meal_estimate",
        )

    avg_nf = _average_usda_nutrition(foods)
    scaled_nf = _scale_nutrition(avg_nf, portion_factor)

    # Alerjen tespiti: sadece yemek adı (ortalama tahmin olduğundan)
    detected = set(detect_allergens(dish))
    detected |= set(infer_allergens_from_food_text(dish))
    detected |= _try_ml_detect_allergens(dish)
    warnings = _profile_warnings(detected, profile, nutrition=scaled_nf, context_text=dish, ui_lang=ui_lang)

    return AnalyzeResponse(
        extracted_text=f"meal_estimate:{dish}",
        ingredients=[],
        nutrition=scaled_nf,
        detected_allergens=sorted(detected),
        warnings=warnings,
        source="meal_estimate",
    )


@app.post("/meal/predict", response_model=AnalyzeResponse)
async def predict_meal(
    dish_name: str | None = Form(None),
    portion: str | None = Form(None),
    user_profile_json: str | None = Form(None),
    ui_lang: str | None = Form(None),
) -> AnalyzeResponse:
    """
    Tabaklı yemek kalorisi (model):
    - dish_name + portion -> eğitimli metin regresyon modeli ile tahmin.
    - Model yoksa otomatik olarak /meal/estimate (USDA ortalaması) fallback yapar.
    """
    dish = (dish_name or "").strip()
    if not dish:
        raise HTTPException(status_code=400, detail="dish_name gerekli.")
    if len(dish) > 80:
        raise HTTPException(status_code=400, detail="dish_name çok uzun (max 80).")

    portion_factor = _parse_portion(portion)
    profile = _parse_profile(user_profile_json)

    try:
        model = load_meal_calorie_model(settings_model_path=settings.meal_calorie_model_path)
        base_nf = predict_nutrition(model, dish)
        scaled_nf = _scale_nutrition(base_nf, portion_factor)
        detected = set(detect_allergens(dish))
        detected |= set(infer_allergens_from_food_text(dish))
        detected |= _try_ml_detect_allergens(dish)
        warnings = _profile_warnings(detected, profile, nutrition=scaled_nf, context_text=dish, ui_lang=ui_lang)
        return AnalyzeResponse(
            extracted_text=f"meal_model:{dish}",
            ingredients=[],
            nutrition=scaled_nf,
            detected_allergens=sorted(detected),
            warnings=warnings,
            source="meal_model",
        )
    except MealCalorieModelError as e:
        # Fallback to USDA estimate (keeps app usable without training)
        if not settings.usda_api_key:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Meal modeli bulunamadı ve USDA_API_KEY ayarlı değil. "
                    "Model eğitin (backend/scripts/train_meal_calorie_model.py) veya USDA_API_KEY ayarlayın. "
                    f"(Detay: {e})"
                ),
            )
        return await estimate_meal(dish_name=dish_name, portion=portion, user_profile_json=user_profile_json, ui_lang=ui_lang)


@app.post("/product/by_barcode", response_model=AnalyzeResponse)
async def product_by_barcode(
    barcode: str = Form(...),
    user_profile_json: str | None = Form(None),
    ui_lang: str | None = Form(None),
) -> AnalyzeResponse:
    barcode = _validate_barcode(barcode)
    profile = _parse_profile(user_profile_json)

    try:
        product = await fetch_product_by_barcode(
            barcode,
            timeout_s=settings.http_timeout_s,
            retries=settings.http_retries,
            retry_backoff_s=settings.http_retry_backoff_s,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Open Food Facts çağrısı başarısız: {e}") from e

    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı (barcode).")

    basic = extract_basic_fields(product)
    product_name = (basic.get("product_name") or "").strip()
    nutr = basic.get("nutriments") or {}
    off_ing = (basic.get("ingredients_text") or "").strip()
    ingredients = [x.strip() for x in off_ing.split(",") if x.strip()] if off_ing else []

    nutrition = NutritionFacts(
        calories_kcal=nutr.get("energy-kcal_100g"),
        fat_g=nutr.get("fat_100g"),
        carbs_g=nutr.get("carbohydrates_100g"),
        protein_g=nutr.get("proteins_100g"),
        sugar_g=nutr.get("sugars_100g"),
        salt_g=nutr.get("salt_100g"),
        sodium_mg=(nutr.get("sodium_100g") * 1000.0 if nutr.get("sodium_100g") else None),
    )

    detected = set(detect_allergens(" ".join([x for x in [product_name, off_ing] if x])))
    detected |= set(infer_allergens_from_food_text(product_name))
    warnings = _profile_warnings(
        detected,
        profile,
        nutrition=nutrition,
        context_text=" ".join([x for x in [product_name, off_ing] if x]),
        ui_lang=ui_lang,
    )

    return AnalyzeResponse(
        extracted_text=f"barcode:{barcode}",
        ingredients=ingredients,
        nutrition=nutrition,
        detected_allergens=sorted(detected),
        warnings=warnings,
        source="barcode_only",
    )


@app.post("/meal/analyze", response_model=AnalyzeResponse)
async def analyze_meal(
    image: UploadFile = File(...),
    dish_name: str | None = Form(None),
    ingredients_csv: str | None = Form(None),
    user_profile_json: str | None = Form(None),
    ui_lang: str | None = Form(None),
) -> AnalyzeResponse:
    """
    Tabaklı yemek modu (v1):
    - Fotoğraf: şimdilik sadece istemci tarafı tahmini için (log/gelecek için saklanabilir).
    - dish_name/ingredients_csv: USDA araması için kullanılır (yaklaşık).
    """
    if not settings.usda_api_key:
        raise HTTPException(status_code=501, detail="USDA_API_KEY ayarlı değil. Meal analizi devre dışı.")

    # foto okunuyor (şimdilik kullanılmıyor ama upload doğrulaması için)
    try:
        await image.read()
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=400, detail=f"Görüntü okunamadı: {e}") from e

    profile = _parse_profile(user_profile_json)

    dish = (dish_name or "").strip()
    ingredients_list = [x.strip() for x in (ingredients_csv or "").split(",") if x.strip()]

    if not dish and not ingredients_list:
        raise HTTPException(status_code=400, detail="dish_name veya ingredients_csv gerekli.")
    if dish and len(dish) > 80:
        raise HTTPException(status_code=400, detail="dish_name çok uzun (max 80).")
    if len(ingredients_list) > 30:
        raise HTTPException(status_code=400, detail="ingredients_csv çok fazla (max 30).")

    # USDA araması: önce dish_name, yoksa ilk ingredient
    query = dish or ingredients_list[0]
    try:
        data = await search_foods(
            query=query,
            api_key=settings.usda_api_key,
            timeout_s=settings.http_timeout_s,
            retries=settings.http_retries,
            retry_backoff_s=settings.http_retry_backoff_s,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"USDA çağrısı başarısız: {e}") from e

    foods = data.get("foods") or []
    if not foods:
        raise HTTPException(status_code=404, detail="USDA'da uygun sonuç bulunamadı.")

    chosen = _pick_best_usda_food(foods)
    nf = _extract_usda_nutrition(chosen)
    chosen_desc = chosen.get("description") or chosen.get("lowercaseDescription") or ""
    chosen_fdc = chosen.get("fdcId")

    detected = set(detect_allergens(" ".join([dish] + ingredients_list)))
    detected |= set(infer_allergens_from_food_text(dish))
    warnings = _profile_warnings(
        detected,
        profile,
        nutrition=nf,
        context_text=" ".join([dish, " ".join(ingredients_list), chosen_desc]).strip(),
        ui_lang=ui_lang,
    )

    return AnalyzeResponse(
        extracted_text=f"meal:{dish or query}",
        ingredients=ingredients_list,
        nutrition=nf,
        detected_allergens=sorted(detected),
        warnings=warnings,
        source="meal_estimate",
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    image: UploadFile = File(...),
    lang: str | None = Form(None),
    barcode: str | None = Form(None),
    user_profile_json: str | None = Form(
        None,
        description='JSON string. Örn: {"allergens":["gluten","fıstık"],"conditions":["diyabet"]}',
    ),
    ui_lang: str | None = Form(None),
) -> AnalyzeResponse:
    try:
        img_bytes = await image.read()
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=400, detail=f"Görüntü okunamadı: {e}") from e

    # 1) OCR
    try:
        raw_text = ocr_image_bytes(img_bytes, settings=settings, lang=lang)
    except OcrUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR şu anda kullanılamıyor. Sebep: Tesseract OCR kurulu değil veya erişilemiyor. "
                "Windows için önerilen kurulum: winget ile 'UB-Mannheim.TesseractOCR' yükleyin. "
                "Ardından backend/.env içine TESSERACT_CMD yolunu yazıp backend'i yeniden başlatın. "
                f"Hata: {type(e).__name__}: {e}"
            ),
        ) from e
    except Exception as e:
        # Most common failure on Windows: Tesseract not installed / path missing
        raise HTTPException(
            status_code=500,
            detail=(
                "OCR çalıştırılamadı. Tesseract kurulu mu? "
                "Gerekirse backend/.env içinde TESSERACT_CMD ayarlayın. "
                f"Hata: {type(e).__name__}: {e}"
            ),
        ) from e

    text = normalize_space(raw_text)

    # 2) NLP (heuristic)
    nutrition = parse_nutrition_facts(text)
    ingredients = extract_ingredients(text)

    # 3) Alerjen tespiti (OCR metni + içerik)
    detected = set(detect_allergens(text))
    detected |= set(infer_allergens_from_food_text(text))
    if ingredients:
        detected |= set(detect_allergens(" ".join(ingredients)))

    # 4) User profile parse (warnings will be computed after optional enrich)
    profile = _parse_profile(user_profile_json)

    source = "ocr_only"

    # 5) Opsiyonel: Open Food Facts ile zenginleştirme (barcode varsa)
    if barcode:
        barcode = _validate_barcode(barcode)
        try:
            product = await fetch_product_by_barcode(
                barcode,
                timeout_s=settings.http_timeout_s,
                retries=settings.http_retries,
                retry_backoff_s=settings.http_retry_backoff_s,
            )
        except Exception:
            product = None
        if product:
            source = "ocr_plus_external"
            basic = extract_basic_fields(product)
            product_name = (basic.get("product_name") or "").strip()
            # OFF ingredients prefer (if OCR couldn't read)
            off_ing = basic.get("ingredients_text")
            if off_ing and not ingredients:
                ingredients = [x.strip() for x in off_ing.split(",") if x.strip()]

            # Merge nutriments (prefer external if OCR missing)
            nutr = basic.get("nutriments") or {}
            merged = NutritionFacts(
                calories_kcal=nutrition.calories_kcal or nutr.get("energy-kcal_100g"),
                fat_g=nutrition.fat_g or nutr.get("fat_100g"),
                carbs_g=nutrition.carbs_g or nutr.get("carbohydrates_100g"),
                protein_g=nutrition.protein_g or nutr.get("proteins_100g"),
                sugar_g=nutrition.sugar_g or nutr.get("sugars_100g"),
                salt_g=nutrition.salt_g or nutr.get("salt_100g"),
                sodium_mg=nutrition.sodium_mg
                or (nutr.get("sodium_100g") * 1000.0 if nutr.get("sodium_100g") else None),
            )
            nutrition = merged

            # Detect allergens from OFF as well
            detected |= set(detect_allergens(off_ing or ""))
            detected |= set(infer_allergens_from_food_text(product_name or ""))
            # warnings will be recomputed below using final detected + nutrition

    # 6) Final warnings: profile allergens + conditions
    context_text = " ".join([text] + ingredients)
    warnings = _profile_warnings(detected, profile, nutrition=nutrition, context_text=context_text, ui_lang=ui_lang)

    return AnalyzeResponse(
        extracted_text=text,
        ingredients=ingredients,
        nutrition=nutrition,
        detected_allergens=sorted(detected),
        warnings=warnings,
        source=source,  # type: ignore[arg-type]
    )


@app.post("/assistant/chat", response_model=AssistantResponse)
async def assistant_chat(
    message: str = Form(...),
    ui_lang: str | None = Form(None),
) -> AssistantResponse:
    """
    Yardımcı asistan endpoint'i.
    Kullanıcı mesajını analiz eder ve öneriler sunar.
    """
    message = (message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")
    if len(message) > 1000:
        raise HTTPException(status_code=400, detail="Mesaj çok uzun (max 1000 karakter).")
    
    try:
        analysis = analyze_user_message(message, ui_lang=ui_lang)
        disclaimer = get_disclaimer(ui_lang=ui_lang)
        
        # Yanıt oluştur
        is_tr = (ui_lang or "").strip().lower().startswith("tr")
        
        response_parts = []
        if analysis["suggestions"]:
            response_parts.extend(analysis["suggestions"])
        else:
            if is_tr:
                response_parts.append("Mesajınız alındı. Size nasıl yardımcı olabilirim?")
            else:
                response_parts.append("Your message has been received. How can I help you?")
        
        response_text = "\n\n".join(response_parts)
        
        return AssistantResponse(
            response=response_text,
            detected_conditions=analysis["detected_conditions"],
            detected_allergens=analysis["detected_allergens"],
            suggestions=analysis["suggestions"],
            needs_medical_attention=analysis["needs_medical_attention"],
            disclaimer=disclaimer,
        )
    except Exception as e:
        logger.exception("Assistant chat hatası: %s", e)
        raise HTTPException(status_code=500, detail=f"Assistant hatası: {type(e).__name__}: {e}") from e


@app.post("/analyze/image_calories", response_model=AnalyzeResponse)
async def analyze_image_calories(
    image: UploadFile = File(...),
    user_profile_json: str | None = Form(None),
    ui_lang: str | None = Form(None),
) -> AnalyzeResponse:
    """
    Görüntüden doğrudan kalori ve besin değerleri tahmini (CNN/ResNet tabanlı).
    - Görüntü: Gıda/tabaklı yemek fotoğrafı
    - Model: ResNet50 transfer learning ile eğitilmiş model
    - Çıktı: Kalori ve diğer besin değerleri (yağ, karbonhidrat, protein, şeker, tuz, sodyum)
    """
    try:
        img_bytes = await image.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Görüntü okunamadı: {e}") from e

    if len(img_bytes) == 0:
        raise HTTPException(status_code=400, detail="Görüntü boş olamaz.")

    # Model yükleme
    try:
        model = load_image_calorie_model()
    except ImageCalorieModelError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "Görüntü kalori modeli bulunamadı veya yüklenemedi. "
                "Model eğitimi için 'py -m backend.scripts.train_image_calorie_model' çalıştırın. "
                f"(Detay: {e})"
            ),
        ) from e

    # Görüntüden besin değerleri tahmini
    try:
        nutrition = predict_nutrition_from_image(model, img_bytes)
    except ImageCalorieModelError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Görüntü işlenemedi veya tahmin yapılamadı: {type(e).__name__}: {e}",
        ) from e
    except Exception as e:
        logger.exception("Image calorie prediction hatası: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Tahmin hatası: {type(e).__name__}: {e}",
        ) from e

    # Alerjen tespiti: görüntüden direkt tespit yapamıyoruz, sadece nutrition bazlı uyarılar
    # (Gelecekte görüntüden alerjen tespiti de eklenebilir)
    detected = set()
    
    # User profile parse
    profile = _parse_profile(user_profile_json)
    
    # Warnings (nutrition ve profile bazlı)
    warnings = _profile_warnings(
        detected,
        profile,
        nutrition=nutrition,
        context_text="image_based_prediction",
        ui_lang=ui_lang,
    )

    return AnalyzeResponse(
        extracted_text="image_calorie_model",
        ingredients=[],
        nutrition=nutrition,
        detected_allergens=sorted(detected),
        warnings=warnings,
        source="image_calorie_model",
    )


@app.post("/auth/register", response_model=AuthResponse)
async def register_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> AuthResponse:
    """
    Yeni kullanıcı kaydı.
    - Kullanıcı adı: minimum 3 karakter, küçük harfe çevrilir
    - Şifre: minimum 6 karakter, bcrypt ile hash'lenir
    """
    user = create_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Kullanıcı adı zaten kullanılıyor veya geçersiz. (Kullanıcı adı: min 3, şifre: min 6 karakter)"
        )
    
    access_token = create_access_token(user.username)
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        username=user.username
    )


@app.post("/auth/login", response_model=AuthResponse)
async def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> AuthResponse:
    """
    Kullanıcı girişi.
    - Kullanıcı adı ve şifre ile giriş yapılır
    - Başarılı olursa JWT token döner
    """
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Kullanıcı adı veya şifre hatalı"
        )
    
    access_token = create_access_token(user.username)
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        username=user.username
    )



def get_current_user(authorization: str | None, db: Session) -> str | None:
    """JWT token'dan kullanıcı adını al."""
    if not authorization:
        return None
    # "Bearer " prefix'i varsa kaldır
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    else:
        token = authorization.strip()
    username = decode_access_token(token)
    if not username:
        return None
    # Kullanıcı veritabanında var mı kontrol et
    user = db.query(User).filter(User.username == username).first()
    return username if user else None


@app.get("/profile", response_model=UserProfile)
async def get_profile_endpoint(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> UserProfile:
    """
    Kullanıcının profilini getir.
    Authorization header'da Bearer token gereklidir.
    """
    username = get_current_user(authorization, db)
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik token")
    
    profile_data = get_user_profile(db, username)
    return UserProfile(
        allergens=profile_data.get("allergens", []),
        conditions=profile_data.get("conditions", []),
        age=profile_data.get("age"),
        weight_kg=profile_data.get("weight_kg"),
        height_cm=profile_data.get("height_cm"),
        gender=profile_data.get("gender"),
        activity_level=profile_data.get("activity_level"),
    )


@app.put("/profile", response_model=UserProfile)
async def update_profile_endpoint(
    profile: UserProfile,
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> UserProfile:
    """
    Kullanıcının profilini güncelle.
    Authorization header'da Bearer token gereklidir.
    """
    username = get_current_user(authorization, db)
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik token")
    
    success = update_user_profile(
        db,
        username,
        allergens=profile.allergens,
        conditions=profile.conditions,
        age=profile.age,
        weight_kg=profile.weight_kg,
        height_cm=profile.height_cm,
        gender=profile.gender,
        activity_level=profile.activity_level,
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Profil güncellenemedi")
    
    return profile


@app.get("/calorie/target", response_model=CalorieTargetResponse)
async def get_calorie_target(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
    goal: str = "maintain",
) -> CalorieTargetResponse:
    """
    Kullanıcının günlük kalori hedefini hesapla.
    Authorization header'da Bearer token gereklidir.
    
    Args:
        goal: "lose" (kilo verme), "maintain" (koruma), "gain" (kilo alma)
    """
    username = get_current_user(authorization, db)
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik token")
    
    profile_data = get_user_profile(db, username)
    target_data = calculate_daily_calorie_target(
        weight_kg=profile_data.get("weight_kg"),
        height_cm=profile_data.get("height_cm"),
        age=profile_data.get("age"),
        gender=profile_data.get("gender"),
        activity_level=profile_data.get("activity_level"),
        goal=goal,
    )
    
    return CalorieTargetResponse(
        bmr=target_data.get("bmr"),
        tdee=target_data.get("tdee"),
        target=target_data.get("target"),
        min=target_data.get("min"),
        max=target_data.get("max"),
    )


@app.post("/consumption/add", response_model=DailyConsumptionResponse)
async def add_consumption_endpoint(
    nutrition: NutritionFacts,
    authorization: str | None = Header(None, alias="Authorization"),
    consumption_date: str | None = None,
    db: Session = Depends(get_db),
) -> DailyConsumptionResponse:
    """
    Günlük tüketime besin değerleri ekle (toplar).
    Authorization header'da Bearer token gereklidir.
    
    Args:
        nutrition: Besin değerleri
        consumption_date: Tarih (YYYY-MM-DD), boşsa bugün kullanılır
    """
    username = get_current_user(authorization, db)
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik token")
    
    target_date = date.today()
    if consumption_date:
        try:
            target_date = date.fromisoformat(consumption_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD formatında olmalı.")
    
    record = add_consumption(db, username, nutrition, target_date)
    
    # Kalori hedefi hesapla
    profile_data = get_user_profile(db, username)
    target_data = calculate_daily_calorie_target(
        weight_kg=profile_data.get("weight_kg"),
        height_cm=profile_data.get("height_cm"),
        age=profile_data.get("age"),
        gender=profile_data.get("gender"),
        activity_level=profile_data.get("activity_level"),
    )
    
    # Limit kontrolü
    limit_check = check_calorie_limit(
        consumed=record.calories_kcal,
        target=target_data.get("target"),
        max_limit=target_data.get("max"),
    )
    
    # Uyarılar
    warnings = []
    if limit_check.get("is_over_target"):
        warnings.append("Günlük kalori hedefi aşıldı.")
    if limit_check.get("is_over"):
        warnings.append(f"Maksimum kalori sınırı aşıldı! {limit_check.get('excess'):.1f} kcal fazla.")
    
    return DailyConsumptionResponse(
        date=record.consumption_date.isoformat(),
        nutrition=NutritionFacts(
            calories_kcal=record.calories_kcal,
            fat_g=record.fat_g,
            carbs_g=record.carbs_g,
            protein_g=record.protein_g,
            sugar_g=record.sugar_g,
            salt_g=record.salt_g,
            sodium_mg=record.sodium_mg,
        ),
        bmr=target_data.get("bmr"),
        tdee=target_data.get("tdee"),
        target=target_data.get("target"),
        remaining=limit_check.get("remaining"),
        is_over_target=limit_check.get("is_over_target", False),
        is_over_limit=limit_check.get("is_over", False),
        warnings=warnings,
    )


@app.get("/consumption/today", response_model=DailyConsumptionResponse)
async def get_today_consumption_endpoint(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> DailyConsumptionResponse:
    """
    Bugünkü tüketimi getir.
    Authorization header'da Bearer token gereklidir.
    """
    username = get_current_user(authorization, db)
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik token")
    
    record = get_today_consumption(db, username)
    
    # Eğer kayıt yoksa boş döndür
    if not record:
        # Kalori hedefi hesapla
        profile_data = get_user_profile(db, username)
        target_data = calculate_daily_calorie_target(
            weight_kg=profile_data.get("weight_kg"),
            height_cm=profile_data.get("height_cm"),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            activity_level=profile_data.get("activity_level"),
        )
        
        return DailyConsumptionResponse(
            date=date.today().isoformat(),
            nutrition=NutritionFacts(),
            bmr=target_data.get("bmr"),
            tdee=target_data.get("tdee"),
            target=target_data.get("target"),
            remaining=target_data.get("target"),
            is_over_target=False,
            is_over_limit=False,
            warnings=[],
        )
    
    # Kalori hedefi hesapla
    profile_data = get_user_profile(db, username)
    target_data = calculate_daily_calorie_target(
        weight_kg=profile_data.get("weight_kg"),
        height_cm=profile_data.get("height_cm"),
        age=profile_data.get("age"),
        gender=profile_data.get("gender"),
        activity_level=profile_data.get("activity_level"),
    )
    
    # Limit kontrolü
    limit_check = check_calorie_limit(
        consumed=record.calories_kcal,
        target=target_data.get("target"),
        max_limit=target_data.get("max"),
    )
    
    # Uyarılar
    warnings = []
    if limit_check.get("is_over_target"):
        warnings.append("Günlük kalori hedefi aşıldı.")
    if limit_check.get("is_over"):
        warnings.append(f"Maksimum kalori sınırı aşıldı! {limit_check.get('excess'):.1f} kcal fazla.")
    
    return DailyConsumptionResponse(
        date=record.consumption_date.isoformat(),
        nutrition=NutritionFacts(
            calories_kcal=record.calories_kcal,
            fat_g=record.fat_g,
            carbs_g=record.carbs_g,
            protein_g=record.protein_g,
            sugar_g=record.sugar_g,
            salt_g=record.salt_g,
            sodium_mg=record.sodium_mg,
        ),
        bmr=target_data.get("bmr"),
        tdee=target_data.get("tdee"),
        target=target_data.get("target"),
        remaining=limit_check.get("remaining"),
        is_over_target=limit_check.get("is_over_target", False),
        is_over_limit=limit_check.get("is_over", False),
        warnings=warnings,
    )


@app.get("/consumption/{consumption_date}", response_model=DailyConsumptionResponse)
async def get_consumption_by_date_endpoint(
    consumption_date: str,
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> DailyConsumptionResponse:
    """
    Belirli bir tarihteki tüketimi getir.
    Authorization header'da Bearer token gereklidir.
    
    Args:
        consumption_date: Tarih (YYYY-MM-DD)
    """
    username = get_current_user(authorization, db)
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik token")
    
    try:
        target_date = date.fromisoformat(consumption_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD formatında olmalı.")
    
    record = get_consumption_by_date(db, username, target_date)
    
    # Eğer kayıt yoksa boş döndür
    if not record:
        profile_data = get_user_profile(db, username)
        target_data = calculate_daily_calorie_target(
            weight_kg=profile_data.get("weight_kg"),
            height_cm=profile_data.get("height_cm"),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            activity_level=profile_data.get("activity_level"),
        )
        
        return DailyConsumptionResponse(
            date=target_date.isoformat(),
            nutrition=NutritionFacts(),
            bmr=target_data.get("bmr"),
            tdee=target_data.get("tdee"),
            target=target_data.get("target"),
            remaining=target_data.get("target"),
            is_over_target=False,
            is_over_limit=False,
            warnings=[],
        )
    
    # Kalori hedefi hesapla
    profile_data = get_user_profile(db, username)
    target_data = calculate_daily_calorie_target(
        weight_kg=profile_data.get("weight_kg"),
        height_cm=profile_data.get("height_cm"),
        age=profile_data.get("age"),
        gender=profile_data.get("gender"),
        activity_level=profile_data.get("activity_level"),
    )
    
    # Limit kontrolü
    limit_check = check_calorie_limit(
        consumed=record.calories_kcal,
        target=target_data.get("target"),
        max_limit=target_data.get("max"),
    )
    
    warnings = []
    if limit_check.get("is_over_target"):
        warnings.append("Günlük kalori hedefi aşıldı.")
    if limit_check.get("is_over"):
        warnings.append(f"Maksimum kalori sınırı aşıldı! {limit_check.get('excess'):.1f} kcal fazla.")
    
    return DailyConsumptionResponse(
        date=record.consumption_date.isoformat(),
        nutrition=NutritionFacts(
            calories_kcal=record.calories_kcal,
            fat_g=record.fat_g,
            carbs_g=record.carbs_g,
            protein_g=record.protein_g,
            sugar_g=record.sugar_g,
            salt_g=record.salt_g,
            sodium_mg=record.sodium_mg,
        ),
        bmr=target_data.get("bmr"),
        tdee=target_data.get("tdee"),
        target=target_data.get("target"),
        remaining=limit_check.get("remaining"),
        is_over_target=limit_check.get("is_over_target", False),
        is_over_limit=limit_check.get("is_over", False),
        warnings=warnings,
    )


@app.delete("/consumption/{consumption_date}")
async def delete_consumption_endpoint(
    consumption_date: str,
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Belirli bir tarihteki tüketimi sil.
    Authorization header'da Bearer token gereklidir.
    
    Args:
        consumption_date: Tarih (YYYY-MM-DD)
    """
    username = get_current_user(authorization, db)
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik token")
    
    try:
        target_date = date.fromisoformat(consumption_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD formatında olmalı.")
    
    success = delete_consumption(db, username, target_date)
    if not success:
        raise HTTPException(status_code=404, detail="Bu tarihte tüketim kaydı bulunamadı.")
    
    return {"success": True, "message": "Tüketim kaydı silindi."}
