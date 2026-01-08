from __future__ import annotations

import re

from .schemas import NutritionFacts
from .utils import normalize_space, parse_number

# SpaCy lemmatization için
_SPACY_MODELS: dict[str, any] = {}
_SPACY_AVAILABLE = False


def _load_spacy_model(lang: str = "tr") -> any | None:
    """
    SpaCy modelini lazy-load eder.
    Türkçe için 'tr_core_news_sm', İngilizce için 'en_core_web_sm' modeli gerekir.
    Kurulum: python -m spacy download tr_core_news_sm
    """
    global _SPACY_AVAILABLE
    
    model_name = "tr_core_news_sm" if lang == "tr" else "en_core_web_sm"
    
    if model_name in _SPACY_MODELS:
        return _SPACY_MODELS[model_name]
    
    try:
        import spacy  # type: ignore
        nlp = spacy.load(model_name)
        _SPACY_MODELS[model_name] = nlp
        _SPACY_AVAILABLE = True
        return nlp
    except (ImportError, OSError):
        # SpaCy yüklü değil veya model indirilmemiş
        _SPACY_AVAILABLE = False
        return None


def lemmatize_text(text: str, lang: str = "tr") -> str:
    """
    Metni lemmatize eder (kelimelerin kök haline getirir).
    SpaCy modeli varsa kullanır, yoksa regex tabanlı basit normalizasyon yapar.
    
    Args:
        text: İşlenecek metin
        lang: Dil kodu ("tr" veya "en")
    
    Returns:
        Lemmatize edilmiş metin
    """
    nlp = _load_spacy_model(lang)
    
    if nlp is None:
        # SpaCy yoksa basit normalizasyon (mevcut regex yaklaşımı)
        return normalize_space(text.lower())
    
    try:
        doc = nlp(text)
        # Lemmatize edilmiş token'ları birleştir
        lemmas = [token.lemma_.lower() if token.lemma_ else token.text.lower() for token in doc if not token.is_punct and not token.is_space]
        return " ".join(lemmas)
    except Exception:
        # Hata durumunda basit normalizasyon
        return normalize_space(text.lower())


def lemmatize_word(word: str, lang: str = "tr") -> str:
    """
    Tek bir kelimeyi lemmatize eder.
    """
    nlp = _load_spacy_model(lang)
    
    if nlp is None:
        return word.lower().strip()
    
    try:
        doc = nlp(word)
        if len(doc) > 0:
            return doc[0].lemma_.lower() if doc[0].lemma_ else word.lower()
        return word.lower()
    except Exception:
        return word.lower().strip()


def extract_ingredients(text: str, use_lemmatization: bool = True) -> list[str]:
    """
    Tries to extract an ingredient list from common label patterns.
    Supports TR/EN keywords (extend as needed).
    Lemmatization kullanarak daha iyi eşleştirme yapar (tekrarlı içerikleri tespit eder).
    """
    t = normalize_space(text)
    
    # Look for a line that starts with "İçindekiler" or "Ingredients"
    m = re.search(r"(?im)^(içindekiler|icindekiler|ingredients)\s*[:\-]\s*(.+)$", t)
    if not m:
        return []
    tail = m.group(2).strip()

    # Cut off if another section starts (e.g., nutrition table)
    tail = re.split(r"(?i)\b(besin değerleri|besin degerleri|nutrition)\b", tail)[0]

    items = [normalize_space(x) for x in re.split(r"[;,]", tail) if normalize_space(x)]
    
    # De-duplicate while preserving order
    # Lemmatization kullanarak daha iyi eşleştirme yap (örn: "süt", "süt tozu" -> farklı, ama "süt" ve "Süt" -> aynı)
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if use_lemmatization:
            # Lemmatize edilmiş haliyle karşılaştır
            key = lemmatize_word(it)
        else:
            key = it.lower().strip()
        
        if key not in seen:
            seen.add(key)
            out.append(it)  # Orijinal metni sakla, lemmatize edilmiş halini değil
    return out


def _find_metric_value(text: str, labels: list[str], use_lemmatization: bool = True) -> tuple[float | None, str | None]:
    """
    Returns (value, unit) for first matched label in text.
    Lemmatization kullanarak daha iyi eşleştirme yapar.
    """
    t = normalize_space(text)
    
    # Önce orijinal metinde ara
    for lab in labels:
        pattern = rf"(?i)\b{re.escape(lab)}\b\s*[:\-]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(kcal|kj|mg|g)?"
        m = re.search(pattern, t)
        if m:
            val = parse_number(m.group(1))
            unit = (m.group(2) or "").lower() or None
            return val, unit
    
    # Orijinal metinde bulunamadıysa ve lemmatization aktifse, lemmatize edilmiş metinde ara
    if use_lemmatization:
        t_lemmatized = lemmatize_text(t)
        # Her label için lemmatize edilmiş versiyonları oluştur ve ara
        for lab in labels:
            lab_lemmatized = lemmatize_word(lab)
            if lab_lemmatized and lab_lemmatized != lab.lower():
                pattern = rf"(?i)\b{re.escape(lab_lemmatized)}\b\s*[:\-]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(kcal|kj|mg|g)?"
                m = re.search(pattern, t_lemmatized)
                if m:
                    val = parse_number(m.group(1))
                    unit = (m.group(2) or "").lower() or None
                    return val, unit
    
    return None, None


def parse_nutrition_facts(text: str, use_lemmatization: bool = True) -> NutritionFacts:
    """
    Heuristic parser for common nutrition label fields.
    Lemmatization kullanarak daha iyi eşleştirme yapar.
    If your thesis needs higher accuracy, replace with a model or table-structure parser.
    """
    t = normalize_space(text)
    nf = NutritionFacts()

    kcal, kcal_unit = _find_metric_value(
        t,
        labels=["energy", "enerji", "kalori", "calories", "kcal"],
        use_lemmatization=use_lemmatization,
    )
    if kcal is not None:
        # If captured as kJ, do quick conversion (1 kcal ≈ 4.184 kJ)
        if kcal_unit == "kj":
            nf.calories_kcal = round(kcal / 4.184, 2)
        else:
            nf.calories_kcal = kcal

    fat, fat_unit = _find_metric_value(t, labels=["fat", "yağ", "yag", "total fat"], use_lemmatization=use_lemmatization)
    if fat is not None:
        nf.fat_g = fat if fat_unit != "mg" else round(fat / 1000.0, 4)

    carbs, carbs_unit = _find_metric_value(t, labels=["carbohydrate", "carbohydrates", "karbonhidrat", "carbs"], use_lemmatization=use_lemmatization)
    if carbs is not None:
        nf.carbs_g = carbs if carbs_unit != "mg" else round(carbs / 1000.0, 4)

    protein, protein_unit = _find_metric_value(t, labels=["protein", "proteinler"], use_lemmatization=use_lemmatization)
    if protein is not None:
        nf.protein_g = protein if protein_unit != "mg" else round(protein / 1000.0, 4)

    sugar, sugar_unit = _find_metric_value(t, labels=["sugars", "sugar", "şeker", "seker"], use_lemmatization=use_lemmatization)
    if sugar is not None:
        nf.sugar_g = sugar if sugar_unit != "mg" else round(sugar / 1000.0, 4)

    salt, salt_unit = _find_metric_value(t, labels=["salt", "tuz"], use_lemmatization=use_lemmatization)
    if salt is not None:
        nf.salt_g = salt if salt_unit != "mg" else round(salt / 1000.0, 4)

    sodium, sodium_unit = _find_metric_value(t, labels=["sodium", "sodyum"], use_lemmatization=use_lemmatization)
    if sodium is not None:
        if sodium_unit == "g":
            nf.sodium_mg = round(sodium * 1000.0, 2)
        else:
            nf.sodium_mg = sodium

    return nf




