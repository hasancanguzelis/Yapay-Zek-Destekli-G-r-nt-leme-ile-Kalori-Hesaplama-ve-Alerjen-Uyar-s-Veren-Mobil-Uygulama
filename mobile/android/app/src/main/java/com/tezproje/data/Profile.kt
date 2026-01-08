package com.tezproje.data

import com.google.gson.annotations.SerializedName

data class UserProfile(
    @SerializedName("allergens")
    val allergens: List<String> = emptyList(),
    @SerializedName("conditions")
    val conditions: List<String> = emptyList(),
    @SerializedName("age")
    val age: Int? = null,
    @SerializedName("weight_kg")
    val weightKg: Double? = null,
    @SerializedName("height_cm")
    val heightCm: Double? = null,
    @SerializedName("gender")
    val gender: String? = null, // "male", "female", "other"
    @SerializedName("activity_level")
    val activityLevel: String? = null // "sedentary", "light", "moderate", "active", "very_active"
)






