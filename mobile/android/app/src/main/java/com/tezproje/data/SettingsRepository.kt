package com.tezproje.data

import android.content.Context
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat

class SettingsRepository(context: Context) {
    private val prefs = context.getSharedPreferences("tezproje_prefs", Context.MODE_PRIVATE)

    fun getThemeMode(): String = prefs.getString("settings_theme", "system") ?: "system"

    fun setThemeMode(mode: String) {
        prefs.edit().putString("settings_theme", mode).commit()
    }

    fun getLanguage(): String = prefs.getString("settings_lang", "system") ?: "system"

    fun setLanguage(lang: String) {
        prefs.edit().putString("settings_lang", lang).commit()
    }

    fun applyToApp() {
        when (getThemeMode()) {
            "dark" -> AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES)
            "light" -> AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO)
            else -> AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM)
        }

        val lang = getLanguage()
        val locales = when (lang) {
            "tr" -> LocaleListCompat.forLanguageTags("tr")
            "en" -> LocaleListCompat.forLanguageTags("en")
            else -> LocaleListCompat.getEmptyLocaleList()
        }
        AppCompatDelegate.setApplicationLocales(locales)
    }
}



