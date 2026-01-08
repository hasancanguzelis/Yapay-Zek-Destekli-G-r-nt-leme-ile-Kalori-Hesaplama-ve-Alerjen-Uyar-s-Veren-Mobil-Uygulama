package com.tezproje.data

data class AssistantResponse(
    val response: String,
    val detected_conditions: List<String> = emptyList(),
    val detected_allergens: List<String> = emptyList(),
    val suggestions: List<String> = emptyList(),
    val needs_medical_attention: Boolean = false,
    val disclaimer: String
)

