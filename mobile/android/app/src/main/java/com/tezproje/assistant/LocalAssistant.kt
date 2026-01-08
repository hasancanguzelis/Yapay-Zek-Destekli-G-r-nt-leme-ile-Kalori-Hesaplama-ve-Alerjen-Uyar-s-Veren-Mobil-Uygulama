package com.tezproje.assistant

import java.util.regex.Pattern

object LocalAssistant {
    // Condition labels
    val CONDITION_LABEL_TR = mapOf(
        "diabetes" to "Diyabet",
        "celiac" to "Çölyak",
        "hypertension" to "Hipertansiyon",
        "hypercholesterolemia" to "Kolesterol",
        "kidney_disease" to "Böbrek",
        "liver_disease" to "Karaciğer",
        "heart_disease" to "Kalp",
        "obesity" to "Obezite",
        "reflux" to "Reflü",
        "ibs" to "IBS",
        "gout" to "Gut",
        "lactose_intolerance" to "Laktoz"
    )

    val CONDITION_LABEL_EN = mapOf(
        "diabetes" to "Diabetes",
        "celiac" to "Celiac",
        "hypertension" to "Hypertension",
        "hypercholesterolemia" to "Cholesterol",
        "kidney_disease" to "Kidney",
        "liver_disease" to "Liver",
        "heart_disease" to "Heart",
        "obesity" to "Obesity",
        "reflux" to "Reflux",
        "ibs" to "IBS",
        "gout" to "Gout",
        "lactose_intolerance" to "Lactose"
    )

    // Allergen labels
    val ALLERGEN_LABEL_TR = mapOf(
        "gluten" to "Gluten",
        "milk" to "Süt",
        "egg" to "Yumurta",
        "peanut" to "Yer fıstığı",
        "tree_nuts" to "Kuruyemiş",
        "soy" to "Soya",
        "sesame" to "Susam",
        "mustard" to "Hardal",
        "fish" to "Balık",
        "shellfish" to "Kabuklu deniz ürünleri",
        "celery" to "Kereviz",
        "lupin" to "Acı bakla",
        "sulphites" to "Sülfitler"
    )

    val ALLERGEN_LABEL_EN = mapOf(
        "gluten" to "Gluten",
        "milk" to "Milk",
        "egg" to "Egg",
        "peanut" to "Peanut",
        "tree_nuts" to "Tree nuts",
        "soy" to "Soy",
        "sesame" to "Sesame",
        "mustard" to "Mustard",
        "fish" to "Fish",
        "shellfish" to "Shellfish",
        "celery" to "Celery",
        "lupin" to "Lupin",
        "sulphites" to "Sulphites"
    )

    // Condition synonyms
    private val CONDITION_SYNONYMS = mapOf(
        "diabetes" to setOf("diyabet", "diabetes", "type 2 diabetes", "type-2 diabetes", "şeker", "seker"),
        "celiac" to setOf("çölyak", "colyak", "çölyak hastalığı", "celiac", "coeliac", "gluten intoleransı", "gluten intolerance"),
        "hypertension" to setOf("hipertansiyon", "tansiyon", "yüksek tansiyon", "hypertension", "high blood pressure"),
        "hypercholesterolemia" to setOf("hiperkolesterolemi", "kolesterol", "yüksek kolesterol", "hypercholesterolemia", "high cholesterol"),
        "kidney_disease" to setOf("böbrek", "bobrek", "böbrek hastalığı", "kidney", "kidney disease", "ckd", "renal"),
        "liver_disease" to setOf("karaciğer", "karaciger", "karaciğer hastalığı", "liver", "liver disease", "fatty liver", "hepatit", "hepatitis"),
        "heart_disease" to setOf("kalp", "kalp hastalığı", "heart", "heart disease", "coronary"),
        "obesity" to setOf("obezite", "obesity", "kilo", "weight"),
        "reflux" to setOf("reflü", "reflu", "reflux", "gerd"),
        "ibs" to setOf("ibs", "irritable bowel", "irritable bowel syndrome", "huzursuz bagirsak"),
        "gout" to setOf("gut", "gout", "ürik asit", "urik asit"),
        "lactose_intolerance" to setOf("laktoz intoleransı", "laktoz", "lactose intolerance")
    )

    // Allergen synonyms
    private val ALLERGEN_SYNONYMS = mapOf(
        "gluten" to setOf("gluten", "buğday", "bugday", "arpa", "çavdar", "cavdar", "yulaf", "wheat", "barley", "rye", "oats"),
        "milk" to setOf("süt", "sut", "milk", "lactose", "laktoz", "peynir", "yoğurt", "yogurt"),
        "egg" to setOf("yumurta", "egg"),
        "peanut" to setOf("yer fıstığı", "yer fistigi", "fıstık", "fistik", "peanut", "groundnut"),
        "tree_nuts" to setOf("badem", "fındık", "findik", "ceviz", "kaju", "antep fıstığı", "antep fistigi", "almond", "hazelnut", "walnut", "cashew", "pistachio"),
        "soy" to setOf("soya", "soy", "soja"),
        "sesame" to setOf("susam", "sesame"),
        "mustard" to setOf("hardal", "mustard"),
        "fish" to setOf("balık", "balik", "fish"),
        "shellfish" to setOf("kabuklu", "karides", "yengeç", "midye", "shellfish", "shrimp", "crab", "mussel"),
        "celery" to setOf("kereviz", "celery"),
        "lupin" to setOf("acı bakla", "aci bakla", "lupin"),
        "sulphites" to setOf("sülfit", "sulfit", "sulfite", "sulphite", "kükürt dioksit", "kukurt dioksit", "sulfur dioxide")
    )

    data class AnalysisResult(
        val detectedConditions: List<String>,
        val detectedAllergens: List<String>,
        val suggestions: List<String>,
        val needsMedicalAttention: Boolean
    )

    private fun normalizeText(text: String): String {
        var normalized = text.lowercase()
        // Türkçe karakter düzeltme
        normalized = normalized.replace("ı", "i").replace("ğ", "g").replace("ş", "s")
        normalized = normalized.replace("ç", "c").replace("ö", "o").replace("ü", "u")
        return normalized
    }

    private fun detectConditions(text: String): List<String> {
        val normalized = normalizeText(text)
        val detected = mutableSetOf<String>()

        // Belirti anahtar kelimeleri
        val symptomKeywords = mapOf(
            "hazimsizlik" to listOf("lactose_intolerance", "ibs"),
            "karn agrisi" to listOf("ibs", "lactose_intolerance"),
            "karnagrisi" to listOf("ibs", "lactose_intolerance"),
            "ishal" to listOf("ibs", "lactose_intolerance"),
            "kabizlik" to listOf("ibs"),
            "siskinlik" to listOf("ibs", "lactose_intolerance"),
            "gaz" to listOf("ibs", "lactose_intolerance"),
            "mide yanmasi" to listOf("reflux"),
            "mideyanmasi" to listOf("reflux"),
            "reflu" to listOf("reflux"),
            "mide bulantisi" to listOf("reflux", "ibs"),
            "midebulantisi" to listOf("reflux", "ibs"),
            "sut" to listOf("lactose_intolerance"),
            "laktoz" to listOf("lactose_intolerance"),
            "gluten" to listOf("celiac"),
            "colyak" to listOf("celiac"),
            "seker" to listOf("diabetes"),
            "diyabet" to listOf("diabetes"),
            "tansiyon" to listOf("hypertension"),
            "hipertansiyon" to listOf("hypertension"),
            "kolesterol" to listOf("hypercholesterolemia"),
            "kalp" to listOf("heart_disease"),
            "bobrek" to listOf("kidney_disease"),
            "karaciger" to listOf("liver_disease")
        )

        for ((keyword, conditions) in symptomKeywords) {
            if (normalized.contains(keyword)) {
                detected.addAll(conditions)
            }
        }

        // Condition synonyms ile eşleştirme
        val words = normalized.split(Regex("\\s+"))
        for (word in words) {
            for ((canonical, synonyms) in CONDITION_SYNONYMS) {
                if (synonyms.contains(word) && canonical !in detected) {
                    detected.add(canonical)
                }
            }
        }

        return detected.sorted()
    }

    private fun detectAllergens(text: String): List<String> {
        val normalized = normalizeText(text)
        val detected = mutableSetOf<String>()

        for ((canonical, synonyms) in ALLERGEN_SYNONYMS) {
            for (synonym in synonyms) {
                val pattern = Pattern.compile("\\b${Pattern.quote(normalizeText(synonym))}\\b", Pattern.CASE_INSENSITIVE)
                if (pattern.matcher(normalized).find()) {
                    detected.add(canonical)
                    break
                }
            }
        }

        return detected.sorted()
    }

    fun analyzeMessage(text: String, uiLang: String? = null): AnalysisResult {
        val isTr = (uiLang ?: "").trim().lowercase().startsWith("tr")
        val conditions = detectConditions(text)
        val allergens = detectAllergens(text)
        val suggestions = mutableListOf<String>()
        var needsMedicalAttention = false

        if (conditions.isNotEmpty()) {
            needsMedicalAttention = true
            val conditionLabels = conditions.map { c ->
                if (isTr) CONDITION_LABEL_TR[c] ?: c else CONDITION_LABEL_EN[c] ?: c
            }
            if (isTr) {
                suggestions.add(
                    "Mesajınızda '${conditionLabels.joinToString(", ")}' ile ilgili belirtiler tespit edildi. " +
                    "Bu durum hakkında daha fazla bilgi için 'Hastalıklar' bölümüne bakabilirsiniz."
                )
            } else {
                suggestions.add(
                    "Your message suggests possible concerns related to: ${conditionLabels.joinToString(", ")}. " +
                    "Please check the 'Diseases' section for more information."
                )
            }
        }

        if (allergens.isNotEmpty()) {
            val allergenLabels = allergens.map { a ->
                if (isTr) ALLERGEN_LABEL_TR[a] ?: a else ALLERGEN_LABEL_EN[a] ?: a
            }
            if (isTr) {
                suggestions.add(
                    "Mesajınızda '${allergenLabels.joinToString(", ")}' alerjeni tespit edildi. " +
                    "Bu alerjenlerden kaçınmanız önerilir."
                )
            } else {
                suggestions.add(
                    "Your message mentions allergens: ${allergenLabels.joinToString(", ")}. " +
                    "It is recommended to avoid these allergens."
                )
            }
        }

        // Özel durumlar için öneriler
        val normalized = normalizeText(text)
        if ("sut" in normalized && ("hazimsizlik" in normalized || "karn" in normalized || "agri" in normalized || "agrisi" in normalized)) {
            if (isTr) {
                suggestions.add(
                    "Süt tüketimi sonrası hazımsızlık yaşıyorsanız, bu laktoz intoleransı belirtisi olabilir. " +
                    "Laktozsuz ürünleri deneyebilir veya süt ürünlerinden kaçınabilirsiniz."
                )
            } else {
                suggestions.add(
                    "If you experience digestive issues after consuming milk, this may be a sign of lactose intolerance. " +
                    "You can try lactose-free products or avoid dairy products."
                )
            }
            needsMedicalAttention = true
        }

        if (suggestions.isEmpty()) {
            if (isTr) {
                suggestions.add(
                    "Mesajınız analiz edildi. Daha spesifik bilgi için lütfen belirtilerinizi veya sorularınızı detaylandırın."
                )
            } else {
                suggestions.add(
                    "Your message has been analyzed. Please provide more specific details about your symptoms or questions."
                )
            }
        }

        return AnalysisResult(
            detectedConditions = conditions,
            detectedAllergens = allergens,
            suggestions = suggestions,
            needsMedicalAttention = needsMedicalAttention
        )
    }

    fun getDisclaimer(uiLang: String? = null): String {
        val isTr = (uiLang ?: "").trim().lowercase().startsWith("tr")
        return if (isTr) {
            "⚠️ ÖNEMLİ UYARI:\n\n" +
            "Bu uygulama tıbbi tavsiye, teşhis veya tedavi sağlamaz. " +
            "Sağlık sorunlarınız için mutlaka bir sağlık kuruluşuna başvurun. " +
            "Bu uygulama sadece farkındalık oluşturmak ve günlük yaşantınızı kolaylaştırmak için tasarlanmıştır. " +
            "Ciddi belirtiler veya acil durumlar için derhal tıbbi yardım alın."
        } else {
            "⚠️ IMPORTANT WARNING:\n\n" +
            "This application does not provide medical advice, diagnosis, or treatment. " +
            "Please consult a healthcare provider for any health concerns. " +
            "This application is designed only to raise awareness and facilitate your daily life. " +
            "Seek immediate medical attention for serious symptoms or emergencies."
        }
    }
}

