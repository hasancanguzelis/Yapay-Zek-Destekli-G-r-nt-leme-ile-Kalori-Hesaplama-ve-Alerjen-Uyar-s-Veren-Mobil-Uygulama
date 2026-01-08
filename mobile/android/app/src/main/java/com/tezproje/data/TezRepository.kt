package com.tezproje.data

import com.tezproje.network.ApiClient
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

class TezRepository {
    suspend fun analyzeLabelImage(
        imageFile: File,
        lang: String?,
        barcode: String?,
        userProfileJson: String?,
        uiLang: String?
    ): AnalyzeResponse {
        val imageBody = imageFile.asRequestBody("image/jpeg".toMediaType())
        val imagePart = MultipartBody.Part.createFormData("image", imageFile.name, imageBody)

        val langBody: RequestBody? = lang?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("text/plain".toMediaType())

        val barcodeBody: RequestBody? = barcode?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("text/plain".toMediaType())

        val profileBody: RequestBody? = userProfileJson?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("application/json".toMediaType())

        val uiLangBody: RequestBody? = uiLang?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("text/plain".toMediaType())

        return ApiClient.api.analyze(
            image = imagePart,
            lang = langBody,
            barcode = barcodeBody,
            userProfileJson = profileBody,
            uiLang = uiLangBody
        )
    }

    suspend fun productByBarcode(barcode: String, userProfileJson: String?, uiLang: String?): AnalyzeResponse {
        return ApiClient.api.productByBarcode(
            barcode = barcode,
            userProfileJson = userProfileJson,
            uiLang = uiLang
        )
    }

    suspend fun analyzeMeal(
        imageFile: File,
        dishName: String?,
        ingredientsCsv: String?,
        userProfileJson: String?,
        uiLang: String?
    ): AnalyzeResponse {
        val imageBody = imageFile.asRequestBody("image/jpeg".toMediaType())
        val imagePart = MultipartBody.Part.createFormData("image", imageFile.name, imageBody)

        val dishBody: RequestBody? = dishName?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("text/plain".toMediaType())

        val ingBody: RequestBody? = ingredientsCsv?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("text/plain".toMediaType())

        val profileBody: RequestBody? = userProfileJson?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("application/json".toMediaType())

        val uiLangBody: RequestBody? = uiLang?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("text/plain".toMediaType())

        return ApiClient.api.analyzeMeal(
            image = imagePart,
            dishName = dishBody,
            ingredientsCsv = ingBody,
            userProfileJson = profileBody,
            uiLang = uiLangBody
        )
    }

    suspend fun estimateMeal(
        dishName: String,
        portion: String?,
        userProfileJson: String?,
        uiLang: String?
    ): AnalyzeResponse {
        return ApiClient.api.estimateMeal(
            dishName = dishName.trim(),
            portion = portion?.trim()?.takeIf { it.isNotEmpty() },
            userProfileJson = userProfileJson,
            uiLang = uiLang
        )
    }

    suspend fun predictMeal(
        dishName: String,
        portion: String?,
        userProfileJson: String?,
        uiLang: String?
    ): AnalyzeResponse {
        return ApiClient.api.predictMeal(
            dishName = dishName.trim(),
            portion = portion?.trim()?.takeIf { it.isNotEmpty() },
            userProfileJson = userProfileJson,
            uiLang = uiLang
        )
    }

    suspend fun assistantChat(
        message: String,
        uiLang: String?
    ): com.tezproje.data.AssistantResponse {
        return ApiClient.api.assistantChat(
            message = message.trim(),
            uiLang = uiLang
        )
    }

    suspend fun analyzeImageCalories(
        imageFile: File,
        userProfileJson: String?,
        uiLang: String?
    ): AnalyzeResponse {
        val imageBody = imageFile.asRequestBody("image/jpeg".toMediaType())
        val imagePart = MultipartBody.Part.createFormData("image", imageFile.name, imageBody)

        val profileBody: RequestBody? = userProfileJson?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("application/json".toMediaType())

        val uiLangBody: RequestBody? = uiLang?.trim()?.takeIf { it.isNotEmpty() }
            ?.toRequestBody("text/plain".toMediaType())

        return ApiClient.api.analyzeImageCalories(
            image = imagePart,
            userProfileJson = profileBody,
            uiLang = uiLangBody
        )
    }
}


