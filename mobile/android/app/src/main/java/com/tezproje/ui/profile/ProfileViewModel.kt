package com.tezproje.ui.profile

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.tezproje.data.ProfileRepository
import com.tezproje.data.UserProfile
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ProfileViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = ProfileRepository(app.applicationContext)

    private val _state = MutableStateFlow(ProfileUiState(profile = repo.loadProfile()))
    val state: StateFlow<ProfileUiState> = _state.asStateFlow()

    fun save(
        allergensComma: String, 
        conditionsComma: String, 
        age: Int? = null,
        weightKg: Double? = null,
        heightCm: Double? = null,
        gender: String? = null,
        activityLevel: String? = null,
        showMessage: Boolean = true
    ) {
        viewModelScope.launch {
            try {
                val profile = UserProfile(
                    allergens = splitComma(allergensComma),
                    conditions = splitComma(conditionsComma),
                    age = age,
                    weightKg = weightKg,
                    heightCm = heightCm,
                    gender = gender,
                    activityLevel = activityLevel
                )
                val ok = repo.saveProfile(profile)
                _state.value = if (showMessage) {
                    ProfileUiState(
                        profile = profile,
                        savedMessage = if (ok) "Profil kaydedildi." else "Profil kaydedilemedi.",
                        errorMessage = if (ok) null else "commit=false"
                    )
                } else {
                    // Sessiz kaydetme (örn. ekran kapanırken)
                    _state.value.copy(profile = profile, savedMessage = null, errorMessage = null)
                }
            } catch (e: Exception) {
                _state.value = _state.value.copy(errorMessage = e.message ?: "Profil kaydedilemedi")
            }
        }
    }

    private fun splitComma(value: String): List<String> =
        value.split(",")
            .map { it.trim() }
            .filter { it.isNotEmpty() }
}





