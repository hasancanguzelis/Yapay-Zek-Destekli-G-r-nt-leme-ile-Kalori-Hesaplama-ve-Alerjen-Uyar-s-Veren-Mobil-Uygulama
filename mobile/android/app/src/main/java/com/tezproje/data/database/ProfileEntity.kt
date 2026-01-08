package com.tezproje.data.database

import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.TypeConverters

/**
 * Kullanıcı profil verileri için Room Entity.
 */
@Entity(tableName = "user_profiles")
@TypeConverters(Converters::class)
data class ProfileEntity(
    @PrimaryKey
    val username: String,
    val allergens: List<String>,
    val conditions: List<String>,
    val age: Int? = null,
    val weightKg: Double? = null,
    val heightCm: Double? = null,
    val gender: String? = null, // "male", "female", "other"
    val activityLevel: String? = null, // "sedentary", "light", "moderate", "active", "very_active"
    val lastUpdated: Long = System.currentTimeMillis()
)
