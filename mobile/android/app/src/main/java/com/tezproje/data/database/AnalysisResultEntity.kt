package com.tezproje.data.database

import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.TypeConverters

/**
 * Analiz sonuçları için Room Entity (offline cache).
 */
@Entity(tableName = "analysis_results")
@TypeConverters(Converters::class)
data class AnalysisResultEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val username: String? = null, // Hangi kullanıcı için (opsiyonel)
    val extractedText: String,
    val ingredients: List<String>,
    val detectedAllergens: List<String>,
    val warnings: List<String>,
    val source: String, // "ocr_only", "barcode_only", "meal_estimate", etc.
    
    // Besin değerleri
    val caloriesKcal: Double? = null,
    val fatG: Double? = null,
    val carbsG: Double? = null,
    val proteinG: Double? = null,
    val sugarG: Double? = null,
    val saltG: Double? = null,
    val sodiumMg: Double? = null,
    
    // Metadata
    val createdAt: Long = System.currentTimeMillis(),
    val barcode: String? = null // Eğer barkod ile analiz edildiyse
)
