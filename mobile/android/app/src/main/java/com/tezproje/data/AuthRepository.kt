package com.tezproje.data

import android.content.Context
import com.tezproje.AppSession
import com.tezproje.network.ApiClient
import kotlinx.coroutines.runBlocking
import retrofit2.HttpException
import java.io.IOException

class AuthRepository(context: Context) {
    private val prefs = context.getSharedPreferences("tezproje_prefs", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_LOGGED_IN = "auth_logged_in"
        private const val KEY_USERNAME = "auth_username"
        private const val KEY_ACCESS_TOKEN = "auth_access_token"
        private const val KEY_SESSION_ID = "auth_session_id"
    }

    sealed class LoginResult {
        data class Success(val username: String) : LoginResult()
        data object EmptyFields : LoginResult()
        data object UserNotFound : LoginResult()
        data object WrongPassword : LoginResult()
        data object Error : LoginResult()
    }

    sealed class RegisterResult {
        data class Success(val username: String) : RegisterResult()
        data object EmptyFields : RegisterResult()
        data object UserExists : RegisterResult()
        data object Error : RegisterResult()
    }

    /**
     * Giriş yapılmış mı kontrol et (JWT token ile).
     */
    fun isLoggedIn(): Boolean {
        val loggedIn = prefs.getBoolean(KEY_LOGGED_IN, false)
        if (!loggedIn) return false

        val sessionId = prefs.getString(KEY_SESSION_ID, null)
        if (sessionId.isNullOrBlank() || sessionId != AppSession.id) {
            logout()
            return false
        }

        val token = prefs.getString(KEY_ACCESS_TOKEN, null)
        val username = prefs.getString(KEY_USERNAME, null)
        
        if (token.isNullOrBlank() || username.isNullOrBlank()) {
            logout()
            return false
        }
        
        return true
    }

    fun getUsername(): String? = prefs.getString(KEY_USERNAME, null)
    
    fun getAccessToken(): String? = prefs.getString(KEY_ACCESS_TOKEN, null)

    /**
     * Backend'e login isteği gönder.
     */
    fun login(username: String, password: String): LoginResult {
        val u = username.trim()
        val p = password.trim()
        if (u.isBlank() || p.isBlank()) return LoginResult.EmptyFields

        return try {
            val response = runBlocking {
                ApiClient.api.login(u, p)
            }
            
            // Başarılı: token ve username'i kaydet
            if (
                !prefs.edit()
                    .putBoolean(KEY_LOGGED_IN, true)
                    .putString(KEY_USERNAME, response.username)
                    .putString(KEY_ACCESS_TOKEN, response.access_token)
                    .putString(KEY_SESSION_ID, AppSession.id)
                    .commit()
            ) {
                return LoginResult.Error
            }
            LoginResult.Success(response.username)
        } catch (e: HttpException) {
            when (e.code()) {
                401 -> LoginResult.WrongPassword
                404 -> LoginResult.UserNotFound
                else -> LoginResult.Error
            }
        } catch (e: IOException) {
            LoginResult.Error
        } catch (e: Exception) {
            LoginResult.Error
        }
    }

    /**
     * Backend'e kayıt isteği gönder.
     */
    fun register(username: String, password: String): RegisterResult {
        val u = username.trim()
        val p = password.trim()
        if (u.isBlank() || p.isBlank()) return RegisterResult.EmptyFields
        if (u.length < 3) return RegisterResult.Error
        if (p.length < 6) return RegisterResult.Error

        return try {
            val response = runBlocking {
                ApiClient.api.register(u, p)
            }
            
            // Başarılı: token ve username'i kaydet
            if (
                !prefs.edit()
                    .putBoolean(KEY_LOGGED_IN, true)
                    .putString(KEY_USERNAME, response.username)
                    .putString(KEY_ACCESS_TOKEN, response.access_token)
                    .putString(KEY_SESSION_ID, AppSession.id)
                    .commit()
            ) {
                return RegisterResult.Error
            }
            RegisterResult.Success(response.username)
        } catch (e: HttpException) {
            when (e.code()) {
                400 -> {
                    // Kullanıcı zaten var veya geçersiz bilgi
                    val errorBody = try {
                        e.response()?.errorBody()?.string()
                    } catch (_: Exception) { null }
                    if (errorBody?.contains("zaten kullanılıyor", ignoreCase = true) == true) {
                        RegisterResult.UserExists
                    } else {
                        RegisterResult.Error
                    }
                }
                401 -> RegisterResult.Error
                404 -> RegisterResult.Error  // Backend endpoint bulunamadı
                500 -> RegisterResult.Error
                else -> RegisterResult.Error
            }
        } catch (e: IOException) {
            // Ağ hatası - backend'e ulaşılamıyor
            android.util.Log.e("AuthRepository", "Network error during register", e)
            RegisterResult.Error
        } catch (e: Exception) {
            android.util.Log.e("AuthRepository", "Unexpected error during register", e)
            RegisterResult.Error
        }
    }

    fun logout() {
        prefs.edit()
            .putBoolean(KEY_LOGGED_IN, false)
            .remove(KEY_USERNAME)
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_SESSION_ID)
            .commit()
    }
}


