from __future__ import annotations

import re

from .allergens import (
    ALLERGEN_LABEL_EN,
    ALLERGEN_LABEL_TR,
    ALLERGEN_SYNONYMS,
    detect_allergens,
    infer_allergens_from_food_text,
)
from .conditions import (
    CONDITION_LABEL_EN,
    CONDITION_LABEL_TR,
    CONDITION_SYNONYMS,
    canonicalize_condition,
)


def _normalize_text(text: str) -> str:
    """Metni normalize et (küçük harf, Türkçe karakter düzeltme)."""
    text = text.lower()
    # Türkçe karakter düzeltme
    text = text.replace("ı", "i").replace("ğ", "g").replace("ş", "s")
    text = text.replace("ç", "c").replace("ö", "o").replace("ü", "u")
    return text


def _detect_conditions_from_text(text: str) -> list[str]:
    """Metinden olası hastalık/rahatsızlık durumlarını tespit et."""
    normalized = _normalize_text(text)
    detected = []
    
    # Belirti anahtar kelimeleri (normalize edilmiş formlar)
    symptom_keywords = {
        "hazimsizlik": ["lactose_intolerance", "ibs"],
        "karn agrisi": ["ibs", "lactose_intolerance"],
        "karnagrisi": ["ibs", "lactose_intolerance"],
        "ishal": ["ibs", "lactose_intolerance"],
        "kabizlik": ["ibs"],
        "siskinlik": ["ibs", "lactose_intolerance"],
        "gaz": ["ibs", "lactose_intolerance"],
        "mide yanmasi": ["reflux"],
        "mideyanmasi": ["reflux"],
        "reflu": ["reflux"],
        "mide bulantisi": ["reflux", "ibs"],
        "midebulantisi": ["reflux", "ibs"],
        "sut": ["lactose_intolerance"],
        "laktoz": ["lactose_intolerance"],
        "gluten": ["celiac"],
        "colyak": ["celiac"],
        "seker": ["diabetes"],
        "diyabet": ["diabetes"],
        "tansiyon": ["hypertension"],
        "hipertansiyon": ["hypertension"],
        "kolesterol": ["hypercholesterolemia"],
        "kalp": ["heart_disease"],
        "bobrek": ["kidney_disease"],
        "karaciger": ["liver_disease"],
    }
    
    for keyword, conditions in symptom_keywords.items():
        if keyword in normalized:
            detected.extend(conditions)
    
    # Condition synonyms ile eşleştirme
    words = re.findall(r'\b\w+\b', normalized)
    for word in words:
        canon = canonicalize_condition(word)
        if canon and canon not in detected:
            detected.append(canon)
    
    # Tekrarları kaldır ve sırala
    return sorted(list(set(detected)))


def _detect_allergens_from_text(text: str) -> list[str]:
    """Metinden alerjenleri tespit et."""
    detected = set(detect_allergens(text))
    detected |= set(infer_allergens_from_food_text(text))
    return sorted(list(detected))


def analyze_user_message(text: str, ui_lang: str | None = None) -> dict:
    """
    Kullanıcı mesajını analiz et ve olası durumları/alerjenleri tespit et.
    
    Returns:
        {
            "detected_conditions": list[str],
            "detected_allergens": list[str],
            "suggestions": list[str],
            "needs_medical_attention": bool
        }
    """
    is_tr = (ui_lang or "").strip().lower().startswith("tr")
    
    conditions = _detect_conditions_from_text(text)
    allergens = _detect_allergens_from_text(text)
    
    suggestions = []
    needs_medical_attention = False
    
    if conditions:
        needs_medical_attention = True
        condition_labels = [CONDITION_LABEL_TR.get(c, c) if is_tr else CONDITION_LABEL_EN.get(c, c) for c in conditions]
        if is_tr:
            suggestions.append(
                f"Mesajınızda '{', '.join(condition_labels)}' ile ilgili belirtiler tespit edildi. "
                f"Bu durum hakkında daha fazla bilgi için 'Hastalıklar' bölümüne bakabilirsiniz."
            )
        else:
            suggestions.append(
                f"Your message suggests possible concerns related to: {', '.join(condition_labels)}. "
                f"Please check the 'Diseases' section for more information."
            )
    
    if allergens:
        allergen_labels = [ALLERGEN_LABEL_TR.get(a, a) if is_tr else ALLERGEN_LABEL_EN.get(a, a) for a in allergens]
        if is_tr:
            suggestions.append(
                f"Mesajınızda '{', '.join(allergen_labels)}' alerjeni tespit edildi. "
                f"Bu alerjenlerden kaçınmanız önerilir."
            )
        else:
            suggestions.append(
                f"Your message mentions allergens: {', '.join(allergen_labels)}. "
                f"It is recommended to avoid these allergens."
            )
    
    # Özel durumlar için öneriler
    normalized = _normalize_text(text)
    
    if "sut" in normalized:
        if "hazimsizlik" in normalized or "karn" in normalized or "agri" in normalized or "agrisi" in normalized:
            if is_tr:
                suggestions.append(
                    "Süt tüketimi sonrası hazımsızlık yaşıyorsanız, bu laktoz intoleransı belirtisi olabilir. "
                    "Laktozsuz ürünleri deneyebilir veya süt ürünlerinden kaçınabilirsiniz."
                )
            else:
                suggestions.append(
                    "If you experience digestive issues after consuming milk, this may be a sign of lactose intolerance. "
                    "You can try lactose-free products or avoid dairy products."
                )
            needs_medical_attention = True
    
    if not suggestions:
        if is_tr:
            suggestions.append(
                "Mesajınız analiz edildi. Daha spesifik bilgi için lütfen belirtilerinizi veya sorularınızı detaylandırın."
            )
        else:
            suggestions.append(
                "Your message has been analyzed. Please provide more specific details about your symptoms or questions."
            )
    
    return {
        "detected_conditions": conditions,
        "detected_allergens": allergens,
        "suggestions": suggestions,
        "needs_medical_attention": needs_medical_attention,
    }


def get_disclaimer(ui_lang: str | None = None) -> str:
    """Sağlık uyarısı ve disclaimer metni."""
    is_tr = (ui_lang or "").strip().lower().startswith("tr")
    
    if is_tr:
        return (
            "⚠️ ÖNEMLİ UYARI:\n\n"
            "Bu uygulama tıbbi tavsiye, teşhis veya tedavi sağlamaz. "
            "Sağlık sorunlarınız için mutlaka bir sağlık kuruluşuna başvurun. "
            "Bu uygulama sadece farkındalık oluşturmak ve günlük yaşantınızı kolaylaştırmak için tasarlanmıştır. "
            "Ciddi belirtiler veya acil durumlar için derhal tıbbi yardım alın."
        )
    else:
        return (
            "⚠️ IMPORTANT WARNING:\n\n"
            "This application does not provide medical advice, diagnosis, or treatment. "
            "Please consult a healthcare provider for any health concerns. "
            "This application is designed only to raise awareness and facilitate your daily life. "
            "Seek immediate medical attention for serious symptoms or emergencies."
        )

