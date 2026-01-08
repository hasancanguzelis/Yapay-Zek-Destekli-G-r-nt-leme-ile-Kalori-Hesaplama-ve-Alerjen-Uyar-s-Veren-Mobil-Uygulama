package com.tezproje.data

import android.content.Context
import com.tezproje.data.database.ProfileEntity
import com.tezproje.data.database.TezDatabase
import com.tezproje.network.ApiClient
import kotlinx.coroutines.runBlocking
import retrofit2.HttpException
import java.io.IOException

class ProfileRepository(context: Context) {
    private val authRepo = AuthRepository(context)
    private val database = TezDatabase.getDatabase(context)
    private val profileDao = database.profileDao()

    /**
     * Backend'den kullanıcı profilini yükle.
     */
    fun loadProfile(): UserProfile {
        val token = authRepo.getAccessToken()
        val username = authRepo.getUsername()
        
        if (token.isNullOrBlank() || username.isNullOrBlank()) {
            // Token yoksa SQLite'dan yükle veya boş döndür
            return loadProfileFromDatabase(username ?: "")
        }

        return try {
            val authorization = "Bearer $token"
            val profile = runBlocking {
                ApiClient.api.getProfile(authorization)
            }
            // Backend'den başarıyla yüklendi, SQLite'a kaydet
            saveProfileToDatabase(username, profile)
            profile
        } catch (e: HttpException) {
            when (e.code()) {
                401 -> {
                    // Token geçersiz, logout yap
                    authRepo.logout()
                    UserProfile()
                }
                else -> {
                    // Hata durumunda SQLite'dan yükle (fallback)
                    loadProfileFromDatabase(username ?: "")
                }
            }
        } catch (e: IOException) {
            // Ağ hatası, SQLite'dan yükle
            loadProfileFromDatabase(username ?: "")
        } catch (e: Exception) {
            loadProfileFromDatabase(username ?: "")
        }
    }

    /**
     * Backend'e kullanıcı profilini kaydet.
     */
    fun saveProfile(profile: UserProfile): Boolean {
        val token = authRepo.getAccessToken()
        val username = authRepo.getUsername()
        
        if (username.isNullOrBlank()) {
            return false
        }
        
        // Önce SQLite'a kaydet (offline mode için)
        saveProfileToDatabase(username, profile)
        
        if (token.isNullOrBlank()) {
            // Token yoksa sadece SQLite'a kaydet
            return true
        }

        return try {
            val authorization = "Bearer $token"
            runBlocking {
                ApiClient.api.updateProfile(authorization, profile)
            }
            // Başarılı ise SQLite'a da kaydet (zaten kaydettik ama güncellenmiş olur)
            saveProfileToDatabase(username, profile)
            true
        } catch (e: HttpException) {
            when (e.code()) {
                401 -> {
                    // Token geçersiz, logout yap
                    authRepo.logout()
                    false
                }
                else -> {
                    // Backend hatası, yine de SQLite'a kaydedildi
                    false
                }
            }
        } catch (e: IOException) {
            // Ağ hatası, SQLite'a kaydedildi (offline mode)
            false
        } catch (e: Exception) {
            false
        }
    }

    /**
     * SQLite'dan profil yükle (fallback).
     */
    private fun loadProfileFromDatabase(username: String): UserProfile {
        if (username.isBlank()) {
            return UserProfile()
        }
        
        return try {
            val entity = runBlocking {
                profileDao.getProfile(username)
            }
            entity?.toUserProfile() ?: UserProfile()
        } catch (e: Exception) {
            UserProfile()
        }
    }

    /**
     * SQLite'a profil kaydet (offline/fallback).
     */
    private fun saveProfileToDatabase(username: String, profile: UserProfile) {
        if (username.isBlank()) {
            return
        }
        
        try {
            val entity = ProfileEntity(
                username = username,
                allergens = profile.allergens,
                conditions = profile.conditions,
                age = profile.age,
                weightKg = profile.weightKg,
                heightCm = profile.heightCm,
                gender = profile.gender,
                activityLevel = profile.activityLevel,
                lastUpdated = System.currentTimeMillis()
            )
            runBlocking {
                profileDao.insertProfile(entity)
            }
        } catch (e: Exception) {
            // Log error if needed
        }
    }
    
    private fun ProfileEntity.toUserProfile(): UserProfile {
        return UserProfile(
            allergens = allergens,
            conditions = conditions,
            age = age,
            weightKg = weightKg,
            heightCm = heightCm,
            gender = gender,
            activityLevel = activityLevel
        )
    }
}





