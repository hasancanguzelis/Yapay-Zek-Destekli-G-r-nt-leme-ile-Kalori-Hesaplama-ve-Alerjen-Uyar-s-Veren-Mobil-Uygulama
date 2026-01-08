from __future__ import annotations

import re

from .utils import normalize_space
from .catalogs_loader import load_catalog_c
from .nlp import lemmatize_text, lemmatize_word

# Canonical allergen keys and their synonyms (TR + EN, extend as needed).
ALLERGEN_SYNONYMS: dict[str, set[str]] = {
    "gluten": {"gluten", "buğday", "bugday", "arpa", "çavdar", "cavdar", "yulaf", "wheat", "barley", "rye", "oats"},
    "milk": {"süt", "sut", "milk", "lactose", "laktoz", "peynir", "yoğurt", "yogurt"},
    "egg": {"yumurta", "egg"},
    "peanut": {"yer fıstığı", "yer fistigi", "fıstık", "fistik", "peanut", "groundnut"},
    "tree_nuts": {"badem", "fındık", "findik", "ceviz", "kaju", "antep fıstığı", "antep fistigi", "almond", "hazelnut", "walnut", "cashew", "pistachio"},
    "soy": {"soya", "soy", "soja"},
    "sesame": {"susam", "sesame"},
    "mustard": {"hardal", "mustard"},
    "fish": {"balık", "balik", "fish"},
    "shellfish": {"kabuklu", "karides", "yengeç", "midye", "shellfish", "shrimp", "crab", "mussel"},
    # EU-14 extras that often appear on labels
    "celery": {"kereviz", "celery"},
    "lupin": {"acı bakla", "aci bakla", "lupin"},
    "sulphites": {"sülfit", "sulfit", "sulfite", "sulphite", "kükürt dioksit", "kukurt dioksit", "sulfur dioxide"},
}

# Localized labels for canonical allergens.
ALLERGEN_LABEL_TR: dict[str, str] = {
    "gluten": "Gluten",
    "milk": "Süt",
    "egg": "Yumurta",
    "peanut": "Yer fıstığı",
    "tree_nuts": "Kuruyemiş",
    "soy": "Soya",
    "sesame": "Susam",
    "mustard": "Hardal",
    "fish": "Balık",
    "shellfish": "Kabuklu deniz ürünleri",
    "celery": "Kereviz",
    "lupin": "Acı bakla",
    "sulphites": "Sülfitler",
}

ALLERGEN_LABEL_EN: dict[str, str] = {
    "gluten": "Gluten",
    "milk": "Milk",
    "egg": "Egg",
    "peanut": "Peanut",
    "tree_nuts": "Tree nuts",
    "soy": "Soy",
    "sesame": "Sesame",
    "mustard": "Mustard",
    "fish": "Fish",
    "shellfish": "Shellfish",
    "celery": "Celery",
    "lupin": "Lupin",
    "sulphites": "Sulphites",
}


def normalize_ui_lang(ui_lang: str | None) -> str:
    s = (ui_lang or "").strip().lower()
    if s.startswith("en"):
        return "en"
    return "tr"


def allergen_label(key: str, ui_lang: str | None = None) -> str:
    lang = normalize_ui_lang(ui_lang)
    if lang == "en":
        return ALLERGEN_LABEL_EN.get(key, key)
    return ALLERGEN_LABEL_TR.get(key, key)

# Market-shelf category -> allergen hints.
# These mappings are intentionally conservative and represent "may contain" signals.
MARKET_CATEGORY_TO_ALLERGEN_HINTS: dict[str, set[str]] = {
    "Süt ve süt ürünleri": {"milk"},
    "Şarküteri": set(),
    "Atıştırmalık - bisküvi/kraker/gofret": {"gluten", "milk", "egg"},
    "Atıştırmalık - cips": set(),
    "Çikolata ve şekerleme": {"milk", "tree_nuts", "peanut"},
    "Kuruyemiş": {"tree_nuts", "peanut"},
    "Kahvaltılık - bal/reçel/pekmez": set(),
    "Soslar": {"soy", "mustard"},
    "Konserve": {"fish"},
    "Hazır çorba / hazır yemek": {"celery", "gluten"},
    "Bakliyat": set(),
    "Makarna / unlu gıdalar": {"gluten"},
    "Ekmek/hamur işleri (paketli)": {"gluten"},
    "Kahve": {"milk"},
    "Meyve suyu / nektar": {"sulphites"},
    "Turşu / zeytin": {"sulphites"},
}

# Open Food Facts often provides allergens as tags like "en:milk", "en:soybeans", etc.
# Map common OFF tag tokens (after language prefix removal) to our canonical keys.
OFF_TAG_TO_CANONICAL: dict[str, str] = {
    "gluten": "gluten",
    "wheat": "gluten",
    "milk": "milk",
    "lactose": "milk",
    "eggs": "egg",
    "egg": "egg",
    "peanuts": "peanut",
    "peanut": "peanut",
    "nuts": "tree_nuts",
    "tree-nuts": "tree_nuts",
    "soybeans": "soy",
    "soya": "soy",
    "soy": "soy",
    "sesame-seeds": "sesame",
    "sesame": "sesame",
    "mustard": "mustard",
    "fish": "fish",
    "crustaceans": "shellfish",
    "molluscs": "shellfish",
    "shellfish": "shellfish",
    "celery": "celery",
    "lupin": "lupin",
    "sulphur-dioxide-and-sulphites": "sulphites",
    "sulfur-dioxide-and-sulfites": "sulphites",
}

# Food-name heuristics: if the dish/product name strongly implies certain allergens,
# add them as "possible" detections. This helps cases like "makarna" -> gluten
# even when ingredients are missing.
# NOTE: Heuristics; not medical advice.
FOOD_KEYWORDS_TO_ALLERGEN_HINTS: dict[str, set[str]] = {
    # Gluten / wheat-based staples
    "makarna": {"gluten"},
    "pasta": {"gluten"},  # EN: pasta
    "spaghetti": {"gluten"},
    "penne": {"gluten"},
    "noodle": {"gluten"},
    "noodles": {"gluten"},
    "kuskus": {"gluten"},
    "couscous": {"gluten"},
    "bulgur": {"gluten"},
    "irmik": {"gluten"},
    "un": {"gluten"},
    "wheat flour": {"gluten"},
    "ekmek": {"gluten"},
    "sandwich": {"gluten"},
    "tost": {"gluten"},
    "borek": {"gluten"},
    "börek": {"gluten"},
    "lahmacun": {"gluten"},
    "pide": {"gluten"},
    "pizza": {"gluten", "milk"},
    "hamburger": {"gluten"},
    "burger": {"gluten"},
    "cheeseburger": {"gluten", "milk"},
    "ramen": {"gluten"},
    "udon": {"gluten"},
    "simit": {"gluten", "sesame"},
    "galeta": {"gluten"},
    "kraker": {"gluten"},
    "cracker": {"gluten"},
    "bisküvi": {"gluten"},
    "biskuvi": {"gluten"},
    "cookie": {"gluten"},
    "kek": {"gluten", "egg", "milk"},
    "cake": {"gluten", "egg", "milk"},
    "pankek": {"gluten", "egg", "milk"},
    "pancake": {"gluten", "egg", "milk"},
    "waffle": {"gluten", "egg", "milk"},
    "gofret": {"gluten", "milk"},
    "baklava": {"tree_nuts", "gluten", "milk"},
    "kruvasan": {"gluten", "milk"},
    "croissant": {"gluten", "milk"},
    # Turkish desserts
    "trileçe": {"milk", "gluten"},
    "trilece": {"milk", "gluten"},
    "tres leches": {"milk", "gluten"},
    "sütlaç": {"milk"},
    "sutlac": {"milk"},
    "kazandibi": {"milk"},
    "muhallebi": {"milk"},
    "puding": {"milk"},
    "künefe": {"milk", "gluten"},
    "kunefe": {"milk", "gluten"},
    "kadayıf": {"gluten"},
    "kadayif": {"gluten"},
    # Dairy-heavy / drinks
    "peynir": {"milk"},
    "yoğurt": {"milk"},
    "yogurt": {"milk"},
    "dondurma": {"milk"},
    "ice cream": {"milk"},
    "süt": {"milk"},
    "milk": {"milk"},
    "butter": {"milk"},
    "tereyağı": {"milk"},
    "tereyagi": {"milk"},
    "krema": {"milk"},
    "cream": {"milk"},
    "latte": {"milk"},
    "cappuccino": {"milk"},
    "mocha": {"milk"},
    "milkshake": {"milk"},
    "ayran": {"milk"},
    # Egg-based
    "yumurta": {"egg"},
    "mayonez": {"egg"},
    "mayonnaise": {"egg"},
    "aioli": {"egg"},
    "omlet": {"egg"},
    "omelette": {"egg"},
    "carbonara": {"egg", "milk", "gluten"},
    # Peanut / nuts / seeds
    "peanut": {"peanut"},
    "peanut butter": {"peanut"},
    "yer fıstığı": {"peanut"},
    "yer fistigi": {"peanut"},
    "satay": {"peanut"},
    "fıstık ezmesi": {"peanut"},
    "fistik ezmesi": {"peanut"},
    "fındık": {"tree_nuts"},
    "findik": {"tree_nuts"},
    "badem": {"tree_nuts"},
    "ceviz": {"tree_nuts"},
    "kaju": {"tree_nuts"},
    "antep fıstığı": {"tree_nuts"},
    "antep fistigi": {"tree_nuts"},
    "pistachio": {"tree_nuts"},
    "pesto": {"tree_nuts"},
    "nutella": {"tree_nuts"},
    "fındık kreması": {"tree_nuts"},
    "findik kremasi": {"tree_nuts"},
    "almond milk": {"tree_nuts"},
    "badem sütü": {"tree_nuts"},
    "badem susu": {"tree_nuts"},
    "tahin": {"sesame"},
    "tahini": {"sesame"},
    "humus": {"sesame"},
    "hummus": {"sesame"},
    "susam": {"sesame"},
    "sesame": {"sesame"},
    # Soy
    "tofu": {"soy"},
    "soya": {"soy"},
    "soy": {"soy"},
    "soya sosu": {"soy", "gluten"},  # often contains wheat
    "soy sauce": {"soy", "gluten"},
    "edamame": {"soy"},
    "miso": {"soy"},
    "tempeh": {"soy"},
    "teriyaki": {"soy", "gluten"},
    # Mustard
    "hardal": {"mustard"},
    "mustard": {"mustard"},
    "dijon": {"mustard"},

    # Fish / shellfish
    "sushi": {"fish"},
    "somon": {"fish"},
    "ton": {"fish"},
    "tuna": {"fish"},
    "balık": {"fish"},
    "balik": {"fish"},
    "fish sauce": {"fish"},
    "anchovy": {"fish"},
    "hamsi": {"fish"},
    "sardalya": {"fish"},
    "karides": {"shellfish"},
    "midye": {"shellfish"},
    "yengeç": {"shellfish"},
    "crab": {"shellfish"},
    "shrimp": {"shellfish"},
    "lobster": {"shellfish"},
    "istakoz": {"shellfish"},
    "oyster": {"shellfish"},
    "istiridye": {"shellfish"},

    # Celery
    "kereviz": {"celery"},
    "celery": {"celery"},
    "sebze suyu": {"celery"},
    "broth": {"celery"},
    "bouillon": {"celery"},
    "stock": {"celery"},

    # Lupin
    "acı bakla": {"lupin"},
    "aci bakla": {"lupin"},
    "lupin": {"lupin"},
    "lupin flour": {"lupin"},
    "bakla unu": {"lupin"},

    # Sulphites / preservative heavy
    "şarap": {"sulphites"},
    "sarap": {"sulphites"},
    "wine": {"sulphites"},
    "kuru meyve": {"sulphites"},
    "dried fruit": {"sulphites"},
    "kuru üzüm": {"sulphites"},
    "kuru uzum": {"sulphites"},
    "sirke": {"sulphites"},
    "vinegar": {"sulphites"},
    "turşu": {"sulphites"},
    "pickle": {"sulphites"},
    # Sulphites / alcohol-ish
    "bira": {"gluten"},
    "beer": {"gluten"},
    "şarap": {"sulphites"},
    "wine": {"sulphites"},
}


def normalize_allergen_name(name: str) -> str:
    name = normalize_space(name).lower()
    name = name.replace("ı", "i").replace("ğ", "g").replace("ş", "s").replace("ç", "c").replace("ö", "o").replace("ü", "u")
    return name


def canonicalize_allergen(name: str) -> str | None:
    n = normalize_allergen_name(name)
    for canonical, syns in ALLERGEN_SYNONYMS.items():
        if n == canonical:
            return canonical
        if n in {normalize_allergen_name(s) for s in syns}:
            return canonical
    return None


def canonicalize_off_allergens(allergens_raw: str | list[str] | None) -> list[str]:
    """
    Converts Open Food Facts allergen fields (string or tags) into canonical allergen keys.

    Examples:
    - "en:milk,en:soybeans" -> ["milk","soy"]
    - ["en:milk","en:peanuts"] -> ["milk","peanut"]
    """
    tokens: list[str] = []
    if allergens_raw is None:
        tokens = []
    elif isinstance(allergens_raw, str):
        # OFF sometimes returns a comma-separated tag string.
        tokens = [x.strip() for x in re.split(r"[;,]", allergens_raw) if x.strip()]
    elif isinstance(allergens_raw, list):
        for it in allergens_raw:
            if not isinstance(it, str):
                continue
            s = it.strip()
            if not s:
                continue
            # Some tag lists may still contain "a,b" style tokens.
            tokens.extend([x.strip() for x in re.split(r"[;,]", s) if x.strip()])
    else:  # pragma: no cover
        tokens = []

    out: set[str] = set()
    for tok in tokens:
        t = tok.strip().lower()
        if not t:
            continue
        # Remove language prefix (en:, tr:, fr:, etc.)
        if ":" in t:
            t = t.split(":", 1)[1]
        t = t.strip()
        if not t:
            continue

        # Normalize separators for mapping attempts.
        t_norm = t.replace("_", "-")
        mapped = OFF_TAG_TO_CANONICAL.get(t_norm)
        if mapped:
            out.add(mapped)
            continue

        # Fall back to our synonym-based canonicalizer.
        # Try with hyphens replaced by spaces as well.
        c = canonicalize_allergen(t_norm) or canonicalize_allergen(t_norm.replace("-", " "))
        if c:
            out.add(c)
            continue

    return sorted(out)


def detect_allergens(text: str, use_lemmatization: bool = True) -> list[str]:
    """
    Rule-based detection: searches for any synonym token/phrase.
    Lemmatization kullanarak daha iyi eşleştirme yapar.
    Returns canonical allergen keys.
    """
    # Normalize for better TR/EN coverage (e.g., süt/sut).
    t = normalize_allergen_name(text)
    
    # Lemmatize edilmiş metni de hazırla
    if use_lemmatization:
        t_lemmatized = lemmatize_text(text)
        t_combined = t + " " + t_lemmatized
    else:
        t_combined = t
    
    found: set[str] = set()
    for canonical, syns in ALLERGEN_SYNONYMS.items():
        for s in syns:
            sn = normalize_allergen_name(s)
            # Orijinal metinde ara
            pattern = r"\b" + re.escape(sn) + r"\b"
            if re.search(pattern, t, flags=re.IGNORECASE):
                found.add(canonical)
                break
            
            # Lemmatize edilmiş metinde de ara
            if use_lemmatization:
                s_lemmatized = lemmatize_word(s)
                if s_lemmatized and s_lemmatized != sn:
                    pattern_lem = r"\b" + re.escape(s_lemmatized) + r"\b"
                    if re.search(pattern_lem, t_lemmatized, flags=re.IGNORECASE):
                        found.add(canonical)
                        break
    return sorted(found)


def infer_allergens_from_food_text(text: str, use_lemmatization: bool = True) -> list[str]:
    """
    Food-name heuristic detection to complement ingredient/synonym matching.
    Lemmatization kullanarak daha iyi eşleştirme yapar.
    Returns canonical allergen keys.
    """
    # Use the same normalization as detect_allergens for consistent matching.
    t = normalize_allergen_name(text)
    
    # Lemmatize edilmiş metni hazırla
    if use_lemmatization:
        t_lemmatized = lemmatize_text(text)
    else:
        t_lemmatized = t
    
    found: set[str] = set()

    # 1) Explicit keyword->allergen hints
    for kw, alls in FOOD_KEYWORDS_TO_ALLERGEN_HINTS.items():
        # word-ish match, allow multi-word
        kwn = normalize_allergen_name(kw)
        pattern = r"\b" + re.escape(kwn) + r"\b"
        # Orijinal metinde ara
        if re.search(pattern, t, flags=re.IGNORECASE):
            found |= set(alls)
            continue
        
        # Lemmatize edilmiş metinde de ara
        if use_lemmatization:
            kw_lemmatized = lemmatize_word(kw)
            if kw_lemmatized and kw_lemmatized != kwn:
                pattern_lem = r"\b" + re.escape(kw_lemmatized) + r"\b"
                if re.search(pattern_lem, t_lemmatized, flags=re.IGNORECASE):
                    found |= set(alls)

    # 2) Catalog-driven hints (market shelf categories)
    try:
        c = load_catalog_c()
        for cat in c.categories:
            alls = MARKET_CATEGORY_TO_ALLERGEN_HINTS.get(cat.category_tr)
            if not alls:
                continue
            for ex in cat.examples:
                exn = normalize_allergen_name(ex)
                pattern = r"\b" + re.escape(exn) + r"\b"
                # Orijinal metinde ara
                if re.search(pattern, t, flags=re.IGNORECASE):
                    found |= set(alls)
                    break
                
                # Lemmatize edilmiş metinde de ara
                if use_lemmatization:
                    ex_lemmatized = lemmatize_word(ex)
                    if ex_lemmatized and ex_lemmatized != exn:
                        pattern_lem = r"\b" + re.escape(ex_lemmatized) + r"\b"
                        if re.search(pattern_lem, t_lemmatized, flags=re.IGNORECASE):
                            found |= set(alls)
                            break
    except Exception:
        # Catalogs are optional; never fail inference.
        pass
    return sorted(found)


def matched_allergen_terms(text: str, canonical: str, limit: int = 4) -> list[str]:
    """
    Returns a few matched synonym terms for a canonical allergen in the given text.
    Useful for more explicit warnings ("süt/yoğurt görüldü" etc).
    """
    syns = ALLERGEN_SYNONYMS.get(canonical)
    if not syns:
        return []
    t = normalize_allergen_name(text)
    hits: list[str] = []
    for s in sorted(syns):
        sn = normalize_allergen_name(s)
        pattern = r"\b" + re.escape(sn) + r"\b"
        if re.search(pattern, t, flags=re.IGNORECASE):
            hits.append(s)
            if len(hits) >= limit:
                break
    return hits


def match_profile_allergens(detected: list[str], profile_allergens: list[str]) -> tuple[list[str], list[str]]:
    """
    Returns (matched_canonical, unknown_profile_items)
    """
    prof_canon: set[str] = set()
    unknown: list[str] = []
    for a in profile_allergens:
        c = canonicalize_allergen(a)
        if c:
            prof_canon.add(c)
        else:
            unknown.append(a)
    matched = sorted(set(detected).intersection(prof_canon))
    return matched, unknown




