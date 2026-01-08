package com.tezproje.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tezproje.data.TezRepository
import com.tezproje.data.UserProfile
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import retrofit2.HttpException

class MainViewModel(
    private val repository: TezRepository = TezRepository()
) : ViewModel() {

    private val _state = MutableStateFlow<UiState>(UiState.Idle)
    val state: StateFlow<UiState> = _state.asStateFlow()

    fun analyzePackagedByPhoto(imageFile: File, lang: String?, barcode: String?, profile: UserProfile, uiLang: String?) {
        val profileJson = JSONObject().apply {
            // Explicit JSONArray to avoid Kotlin List being serialized as "[a,b]" string on some devices.
            put("allergens", JSONArray(profile.allergens))
            put("conditions", JSONArray(profile.conditions))
        }.toString()

        _state.value = UiState.Loading
        viewModelScope.launch {
            try {
                val resp = repository.analyzeLabelImage(
                    imageFile = imageFile,
                    lang = lang,
                    barcode = barcode,
                    userProfileJson = profileJson,
                    uiLang = uiLang
                )
                _state.value = UiState.Success(resp)
            } catch (e: Exception) {
                _state.value = UiState.Error(toUserMessage(e))
            }
        }
    }

    fun analyzePackagedByBarcode(barcode: String, profile: UserProfile, uiLang: String?) {
        val profileJson = JSONObject().apply {
            put("allergens", JSONArray(profile.allergens))
            put("conditions", JSONArray(profile.conditions))
        }.toString()

        _state.value = UiState.Loading
        viewModelScope.launch {
            try {
                val resp = repository.productByBarcode(
                    barcode = barcode,
                    userProfileJson = profileJson,
                    uiLang = uiLang
                )
                _state.value = UiState.Success(resp)
            } catch (e: Exception) {
                _state.value = UiState.Error(toUserMessage(e))
            }
        }
    }

    fun estimateMeal(dishName: String, portion: String?, profile: UserProfile, uiLang: String?) {
        val profileJson = JSONObject().apply {
            put("allergens", JSONArray(profile.allergens))
            put("conditions", JSONArray(profile.conditions))
        }.toString()

        _state.value = UiState.Loading
        viewModelScope.launch {
            try {
                val resp = try {
                    // Önce ML model endpoint'ini dene (model yoksa backend otomatik USDA fallback yapar).
                    repository.predictMeal(dishName = dishName, portion = portion, userProfileJson = profileJson, uiLang = uiLang)
                } catch (e: HttpException) {
                    // Sadece endpoint yoksa (404) eski estimate endpoint'ine düş.
                    // 4xx/5xx hatalarda kullanıcı gerçek sebebi görsün (USDA_API_KEY yok, model yok, vb.).
                    if (e.code() == 404) {
                        repository.estimateMeal(dishName = dishName, portion = portion, userProfileJson = profileJson, uiLang = uiLang)
                    } else {
                        throw e
                    }
                }
                _state.value = UiState.Success(resp)
            } catch (e: Exception) {
                _state.value = UiState.Error(toUserMessage(e))
            }
        }
    }

    fun analyzeImageCalories(imageFile: File, profile: UserProfile, uiLang: String?) {
        val profileJson = JSONObject().apply {
            put("allergens", JSONArray(profile.allergens))
            put("conditions", JSONArray(profile.conditions))
        }.toString()

        _state.value = UiState.Loading
        viewModelScope.launch {
            try {
                val resp = repository.analyzeImageCalories(
                    imageFile = imageFile,
                    userProfileJson = profileJson,
                    uiLang = uiLang
                )
                _state.value = UiState.Success(resp)
            } catch (e: Exception) {
                _state.value = UiState.Error(toUserMessage(e))
            }
        }
    }

    private fun toUserMessage(e: Exception): String {
        return when (e) {
            is HttpException -> {
                val code = e.code()
                val raw = try { e.response()?.errorBody()?.string() } catch (_: Exception) { null }
                val detail = raw?.let { extractFastApiDetail(it) } ?: raw
                // OCR/Tesseract kurulum hatası gibi durumlarda kullanıcıyı uzun teknik metne boğmayalım.
                val d = detail.orEmpty()
                if (code == 503 && (d.contains("OCR", ignoreCase = true) || d.contains("Tesseract", ignoreCase = true))) {
                    "OCR kullanılamıyor: Tesseract kurulumu gerekli. Bilgisayarınıza Tesseract OCR kurup backend'i yeniden başlatın."
                } else {
                    if (!detail.isNullOrBlank()) "Sunucu hatası ($code): $detail" else "Sunucu hatası ($code)"
                }
            }
            is IOException -> "Ağ hatası: Backend'e ulaşılamadı. API_BASE_URL doğru mu? (emulator: 10.0.2.2)"
            else -> e.message ?: "Bilinmeyen hata"
        }
    }

    private fun extractFastApiDetail(body: String): String? {
        return try {
            val obj = JSONObject(body)
            obj.optString("detail").takeIf { it.isNotBlank() }
        } catch (_: Exception) {
            null
        }
    }
}


