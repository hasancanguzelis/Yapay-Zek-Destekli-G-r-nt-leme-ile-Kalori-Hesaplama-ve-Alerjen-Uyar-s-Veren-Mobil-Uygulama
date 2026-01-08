package com.tezproje.data

data class NutritionFacts(
    val calories_kcal: Double? = null,
    val fat_g: Double? = null,
    val carbs_g: Double? = null,
    val protein_g: Double? = null,
    val sugar_g: Double? = null,
    val salt_g: Double? = null,
    val sodium_mg: Double? = null
)

data class AnalyzeResponse(
    val extracted_text: String,
    val ingredients: List<String> = emptyList(),
    val nutrition: NutritionFacts = NutritionFacts(),
    val detected_allergens: List<String> = emptyList(),
    val warnings: List<String> = emptyList(),
    val source: String = "ocr_only"
)

data class CalorieTargetResponse(
    val bmr: Double? = null,
    val tdee: Double? = null,
    val target: Double? = null,
    val min: Double? = null,
    val max: Double? = null
)

data class DailyConsumptionResponse(
    val date: String,
    val nutrition: NutritionFacts = NutritionFacts(),
    val bmr: Double? = null,
    val tdee: Double? = null,
    val target: Double? = null,
    val remaining: Double? = null,
    val is_over_target: Boolean = false,
    val is_over_limit: Boolean = false,
    val warnings: List<String> = emptyList()
)






