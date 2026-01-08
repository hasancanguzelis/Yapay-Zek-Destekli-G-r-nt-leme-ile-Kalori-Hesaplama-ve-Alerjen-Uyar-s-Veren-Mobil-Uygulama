from __future__ import annotations

import re

from .schemas import NutritionFacts, UserProfile
from .utils import normalize_space
from .catalogs_loader import load_catalog_c


# Canonical condition keys and their synonyms (TR + EN).
# NOTE: These are *not* medical advice. They are lightweight rules to surface
# "dikkat" uyarıları based on nutrition/ingredients.
CONDITION_SYNONYMS: dict[str, set[str]] = {
    "diabetes": {"diyabet", "diabetes", "type 2 diabetes", "type-2 diabetes", "şeker", "seker"},
    "celiac": {"çölyak", "colyak", "çölyak hastalığı", "celiac", "coeliac", "gluten intoleransı", "gluten intolerance"},
    "hypertension": {"hipertansiyon", "tansiyon", "yüksek tansiyon", "hypertension", "high blood pressure"},
    "hypercholesterolemia": {"hiperkolesterolemi", "kolesterol", "yüksek kolesterol", "hypercholesterolemia", "high cholesterol"},
    "kidney_disease": {"böbrek", "bobrek", "böbrek hastalığı", "kidney", "kidney disease", "ckd", "renal"},
    "liver_disease": {"karaciğer", "karaciger", "karaciğer hastalığı", "liver", "liver disease", "fatty liver", "hepatit", "hepatitis"},
    "heart_disease": {"kalp", "kalp hastalığı", "heart", "heart disease", "coronary"},
    "obesity": {"obezite", "obesity", "kilo", "weight"},
    "reflux": {"reflü", "reflu", "reflux", "gerd"},
    "ibs": {"ibs", "irritable bowel", "irritable bowel syndrome", "huzursuz bagirsak"},
    "gout": {"gut", "gout", "ürik asit", "urik asit"},
    "lactose_intolerance": {"laktoz intoleransı", "laktoz", "lactose intolerance"},
}

CONDITION_LABEL_TR: dict[str, str] = {
    "diabetes": "Diyabet",
    "celiac": "Çölyak",
    "hypertension": "Hipertansiyon",
    "hypercholesterolemia": "Kolesterol",
    "kidney_disease": "Böbrek",
    "liver_disease": "Karaciğer",
    "heart_disease": "Kalp",
    "obesity": "Kilo",
    "reflux": "Reflü",
    "ibs": "IBS",
    "gout": "Gut",
    "lactose_intolerance": "Laktoz",
}

CONDITION_LABEL_EN: dict[str, str] = {
    "diabetes": "Diabetes",
    "celiac": "Celiac",
    "hypertension": "Hypertension",
    "hypercholesterolemia": "Cholesterol",
    "kidney_disease": "Kidney",
    "liver_disease": "Liver",
    "heart_disease": "Heart",
    "obesity": "Obesity",
    "reflux": "Reflux",
    "ibs": "IBS",
    "gout": "Gout",
    "lactose_intolerance": "Lactose",
}


def _ui_lang(ui_lang: str | None) -> str:
    s = (ui_lang or "").strip().lower()
    return "en" if s.startswith("en") else "tr"


def _label_cond(cond: str, ui_lang: str | None) -> str:
    if _ui_lang(ui_lang) == "en":
        return CONDITION_LABEL_EN.get(cond, cond)
    return CONDITION_LABEL_TR.get(cond, cond)

# Market shelf category -> condition triggers.
# These are "may be risky" heuristics, designed to work even when nutrition fields are missing.
MARKET_CATEGORY_TO_CONDITIONS: dict[str, set[str]] = {
    "Gazlı içecekler": {"diabetes", "obesity", "reflux"},
    "Meyve suyu / nektar": {"diabetes", "obesity"},
    "Soğuk çay": {"diabetes", "obesity"},
    "Enerji içeceği": {"diabetes", "obesity", "heart_disease", "hypertension"},
    "Atıştırmalık - cips": {"hypertension", "obesity", "heart_disease", "kidney_disease"},
    "Atıştırmalık - bisküvi/kraker/gofret": {"diabetes", "obesity"},
    "Çikolata ve şekerleme": {"diabetes", "obesity", "reflux"},
    "Şarküteri": {"hypertension", "heart_disease", "kidney_disease"},
    "Soslar": {"hypertension", "kidney_disease", "reflux"},
    "Hazır çorba / hazır yemek": {"hypertension", "kidney_disease"},
    "Dondurulmuş gıdalar": {"hypertension", "obesity", "heart_disease"},
    "Diyet/şekersiz ürünler": set(),
    "Kahve": {"reflux", "heart_disease"},
    "Çay": set(),
    "Süt ve süt ürünleri": {"lactose_intolerance"},
    "Makarna / unlu gıdalar": {"celiac"},
    "Ekmek/hamur işleri (paketli)": {"celiac"},
    "Kuruyemiş": set(),
    "Turşu / zeytin": {"hypertension", "kidney_disease"},
}


def _norm(s: str) -> str:
    s = normalize_space(s).lower()
    s = s.replace("ı", "i").replace("ğ", "g").replace("ş", "s").replace("ç", "c").replace("ö", "o").replace("ü", "u")
    return s


def canonicalize_condition(name: str) -> str | None:
    n = _norm(name)
    for canonical, syns in CONDITION_SYNONYMS.items():
        if n == canonical:
            return canonical
        if n in {_norm(x) for x in syns}:
            return canonical
    return None


def canonicalize_profile_conditions(conditions: list[str]) -> tuple[list[str], list[str]]:
    canon: list[str] = []
    unknown: list[str] = []
    for c in conditions:
        cc = canonicalize_condition(c)
        if cc:
            canon.append(cc)
        elif (c or "").strip():
            unknown.append(c)
    # de-dup keep order
    seen: set[str] = set()
    canon2: list[str] = []
    for c in canon:
        if c not in seen:
            seen.add(c)
            canon2.append(c)
    return canon2, unknown


def _fmt2(x: float | None, unit: str) -> str:
    if x is None:
        return "?"
    return f"{x:.2f}{unit}"


def _contains_any(text: str, keywords: set[str]) -> bool:
    t = _norm(text)
    for kw in keywords:
        # word-ish match, allow multi-word
        pattern = r"\b" + re.escape(_norm(kw)) + r"\b"
        if re.search(pattern, t, flags=re.IGNORECASE):
            return True
    return False


def _matched_keywords(text: str, keywords: set[str]) -> list[str]:
    """
    Returns keywords that appear in text (normalized).
    Used to produce more explicit "hangi madde" uyarıları.
    """
    t = _norm(text)
    found: list[str] = []
    for kw in sorted(keywords):
        pattern = r"\b" + re.escape(_norm(kw)) + r"\b"
        if re.search(pattern, t, flags=re.IGNORECASE):
            found.append(kw)
    return found


def condition_warnings(
    profile: UserProfile,
    nutrition: NutritionFacts,
    context_text: str,
    detected_allergens: set[str] | None = None,
    ui_lang: str | None = None,
) -> list[str]:
    """
    Returns warnings based on profile.conditions and available nutrition/context.
    Keeps output intentionally short and actionable.
    """
    conds, unknown = canonicalize_profile_conditions(profile.conditions)
    warnings: list[str] = []

    # İçerik/ürün/yemek adına dayalı (eşiksiz) uyarı kuralları:
    # Amaç: net değerleri göz ardı ederek, tipik içerik ve kategoriler üzerinden
    # "dikkat" uyarıları üretmek (örn. çölyak + makarna -> buğday/gluten).
    # Bu kurallar tıbbi tavsiye değildir.
    def warn_if_any(cond: str, keywords: set[str], message_tr: str, message_en: str) -> None:
        if cond in conds and _contains_any(context_text, keywords):
            if _ui_lang(ui_lang) == "en":
                warnings.append(f"Warning ({_label_cond(cond, ui_lang)}): {message_en}")
            else:
                warnings.append(f"Uyarı ({_label_cond(cond, ui_lang)}): {message_tr}")

    # 0) Catalog-driven triggers (market shelf categories)
    # If the text contains a market category example, emit a short condition-specific warning.
    try:
        c = load_catalog_c()
        for cat in c.categories:
            cat_conds = MARKET_CATEGORY_TO_CONDITIONS.get(cat.category_tr)
            if not cat_conds:
                continue
            if not (set(conds) & set(cat_conds)):
                continue
            # any example keyword present?
            if any(_contains_any(context_text, {ex}) for ex in cat.examples):
                for cc in (set(conds) & set(cat_conds)):
                    warnings.append(
                        (f"Warning ({_label_cond(cc, ui_lang)}): '{cat.category_tr}' category may be risky based on ingredients."
                         if _ui_lang(ui_lang) == "en"
                         else f"Uyarı ({_label_cond(cc, ui_lang)}): '{cat.category_tr}' kategorisi içerik açısından riskli olabilir.")
                    )
    except Exception:
        pass

    # Çölyak: gluten içerebilecek unlu ürünler
    if "celiac" in conds:
        gluten_keywords = {
            "gluten",
            "un",
            "bugday",
            "buğday",
            "arpa",
            "cavdar",
            "çavdar",
            "yulaf",
            "ekmek",
            "makarna",
            "pizza",
            "borek",
            "börek",
            "lahmacun",
            "pide",
            "bulgur",
            "irmik",
            "kuskus",
            "couscous",
            "bira",
            "beer",
            "malt",
            "soya sosu",
            "soy sauce",
        }
        matched_terms = _matched_keywords(context_text, gluten_keywords)
        if (detected_allergens and "gluten" in detected_allergens) or matched_terms:
            detail = "gluten (buğday unu vb.)"
            if matched_terms:
                # Keep short
                detail = ", ".join(matched_terms[:4]) + (", ..." if len(matched_terms) > 4 else "")
            if _ui_lang(ui_lang) == "en":
                warnings.append(f"Warning ({_label_cond('celiac', ui_lang)}): Found {detail} in name/ingredients. Avoid recommended.")
            else:
                warnings.append(f"Uyarı ({_label_cond('celiac', ui_lang)}): İçerikte/isimde {detail} görüldü. Kaçınılması önerilir.")

    # Laktoz intoleransı: süt ürünleri
    if "lactose_intolerance" in conds:
        dairy_keywords = {"sut", "süt", "milk", "lactose", "laktoz", "peynir", "yoğurt", "yogurt", "dondurma", "ice cream", "krema", "cream", "tereyağı", "tereyagi"}
        matched_terms = _matched_keywords(context_text, dairy_keywords)
        if (detected_allergens and "milk" in detected_allergens) or matched_terms:
            detail = "süt/krema/peynir/yoğurt (laktoz içerebilir)"
            if matched_terms:
                detail = ", ".join(matched_terms[:4]) + (", ..." if len(matched_terms) > 4 else "")
            if _ui_lang(ui_lang) == "en":
                warnings.append(f"Warning ({_label_cond('lactose_intolerance', ui_lang)}): Found {detail} in name/ingredients. May contain lactose.")
            else:
                warnings.append(f"Uyarı ({_label_cond('lactose_intolerance', ui_lang)}): İçerikte/isimde {detail} görüldü. Laktoz içerebilir.")

    # Diyabet: şekerli gıdalar/içecekler + rafine karbonhidratlar (eşiksiz)
    warn_if_any(
        "diabetes",
        {
            "seker",
            "şeker",
            "tatli",
            "tatlı",
            "pasta",
            "kek",
            "kurabiye",
            "bisküvi",
            "cikolata",
            "çikolata",
            "dondurma",
            "recel",
            "reçel",
            "bal",
            "gazoz",
            "kola",
            "cola",
            "meyve suyu",
            "juice",
            "enerji icecegi",
            "enerji içeceği",
        },
        "Şekerli/rafine karbonhidrat içeriği nedeniyle dikkat gerektirebilir.",
        "May be risky due to sugary/refined carbohydrate content.",
    )
    warn_if_any(
        "diabetes",
        {"beyaz ekmek", "ekmek", "pilav", "rice", "pilaf", "makarna", "noodle", "patates", "fries"},
        "Rafine karbonhidrat ağırlıklı olabilir; porsiyona dikkat ediniz.",
        "May be high in refined carbohydrates; watch portion size.",
    )

    # Hipertansiyon: tuzlu/işlenmiş/fast food
    warn_if_any(
        "hypertension",
        {
            "cips",
            "turşu",
            "salam",
            "sosis",
            "sucuk",
            "pastirma",
            "pastırma",
            "hazir corba",
            "hazır çorba",
            "sos",
            "soya sosu",
            "soy sauce",
            "fast food",
            "pizza",
            "hamburger",
            "burger",
            "doner",
            "döner",
        },
        "Tuz/sodyum yüksek olabileceği için dikkat gerektirebilir.",
        "May be high in salt/sodium; caution advised.",
    )

    # Kalp/Kolesterol: kızartma/işlenmiş et/krema-tereyağı
    if "hypercholesterolemia" in conds or "heart_disease" in conds:
        if _contains_any(
            context_text,
            {
                "kizartma",
                "kızartma",
                "fast food",
                "pizza",
                "hamburger",
                "burger",
                "doner",
                "döner",
                "sucuk",
                "sosis",
                "salam",
                "kavurma",
                "tereyagi",
                "tereyağı",
                "krema",
                "cream",
                "mayonez",
                "mayonnaise",
                "margarin",
                "margarine",
            },
        ):
            warnings.append(
                "Warning (Heart/Cholesterol): May be risky due to fatty/processed content."
                if _ui_lang(ui_lang) == "en"
                else "Uyarı (Kalp/Kolesterol): Yağlı/işlenmiş içerik nedeniyle dikkat gerektirebilir."
            )

    # Böbrek: yüksek tuz/işlenmiş + bazı potasyum/fosfor kaynakları
    warn_if_any(
        "kidney_disease",
        {"cips", "hazir corba", "hazır çorba", "salam", "sosis", "sucuk", "turşu", "sos", "soya sosu", "soy sauce"},
        "Tuz/sodyum ve katkılar nedeniyle dikkat gerektirebilir.",
        "May be risky due to salt/sodium and additives.",
    )
    warn_if_any(
        "kidney_disease",
        {"muz", "banana", "patates", "domates", "portakal", "orange", "kuru meyve", "kuruyemis", "kuruyemiş", "cikolata", "çikolata", "cola"},
        "Potasyum/fosfor açısından yoğun olabileceği için dikkat gerektirebilir.",
        "May be high in potassium/phosphorus; caution advised.",
    )

    # Karaciğer: alkol + kızartma/şekerli
    warn_if_any(
        "liver_disease",
        {"alkol", "alcohol", "bira", "beer", "şarap", "sarap", "wine"},
        "Alkol içerdiği/alkolle ilişkili olabileceği için kaçınılmalıdır.",
        "Avoid due to alcohol content/association.",
    )
    warn_if_any(
        "liver_disease",
        {"kizartma", "kızartma", "fast food", "hamburger", "burger", "pizza", "tatli", "tatlı", "kek", "pasta", "cikolata", "çikolata"},
        "Yağlı/şekerli içerik nedeniyle dikkat gerektirebilir.",
        "May be risky due to fatty/sugary content.",
    )

    # Obezite/Kilo: fast food + kızartma + tatlı/içecek
    warn_if_any(
        "obesity",
        {"fast food", "hamburger", "burger", "pizza", "doner", "döner", "kizartma", "kızartma", "patates", "fries"},
        "Yüksek kalorili/yağlı olabileceği için dikkat gerektirebilir.",
        "May be high-calorie/fatty; caution advised.",
    )
    warn_if_any(
        "obesity",
        {"tatli", "tatlı", "pasta", "kek", "kurabiye", "bisküvi", "dondurma", "kola", "cola", "gazoz", "enerji icecegi", "enerji içeceği"},
        "Şekerli içeriği nedeniyle dikkat gerektirebilir.",
        "May be risky due to sugary content.",
    )
    warn_if_any(
        "obesity",
        {"milkshake", "smoothie", "frappe", "cappuccino", "latte"},
        "Kalorisi yüksek içecekler arasında olabilir; dikkat gerektirebilir.",
        "May be a high-calorie drink; caution advised.",
    )

    # Reflü: tetikleyiciler
    warn_if_any(
        "reflux",
        {"kahve", "coffee", "cikolata", "çikolata", "domates", "narenciye", "limon", "portakal", "acı", "baharat", "cola", "gazli", "gazlı"},
        "Bazı içerikler reflüyü tetikleyebilir.",
        "Some ingredients may trigger reflux.",
    )

    # IBS: FODMAP-ish tetikleyiciler
    warn_if_any(
        "ibs",
        {"sogan", "soğan", "sarimsak", "sarımsak", "fasulye", "nohut", "mercimek", "lahana", "sut", "süt", "milk"},
        "Bazı içerikler hassasiyeti tetikleyebilir.",
        "Some ingredients may trigger sensitivity.",
    )

    # Gut: ürik asidi artırabilecek tipik içerikler
    warn_if_any(
        "gout",
        {"sakatat", "ciger", "ciğer", "hamsi", "sardalya", "midye", "karides", "bira", "beer"},
        "Bazı içerikler ürik asidi artırabilir.",
        "Some ingredients may increase uric acid.",
    )

    return warnings


