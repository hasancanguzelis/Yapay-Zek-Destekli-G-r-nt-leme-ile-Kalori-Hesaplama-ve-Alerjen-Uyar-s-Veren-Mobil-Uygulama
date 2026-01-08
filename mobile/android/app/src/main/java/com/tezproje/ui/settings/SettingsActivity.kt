package com.tezproje.ui.settings

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.tezproje.data.AuthRepository
import com.tezproje.data.SettingsRepository
import com.tezproje.databinding.ActivitySettingsBinding
import com.tezproje.ui.MainActivity
import com.tezproje.ui.auth.LoginActivity
import com.tezproje.ui.profile.ProfileActivity

class SettingsActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val settings = SettingsRepository(applicationContext)

        // Init selections
        when (settings.getThemeMode()) {
            "dark" -> binding.themeToggle.check(binding.themeDark.id)
            "light" -> binding.themeToggle.check(binding.themeLight.id)
            else -> binding.themeToggle.check(binding.themeSystem.id)
        }
        when (settings.getLanguage()) {
            "tr" -> binding.langToggle.check(binding.langTr.id)
            "en" -> binding.langToggle.check(binding.langEn.id)
            else -> binding.langToggle.check(binding.langSystem.id)
        }

        binding.themeToggle.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            val mode = when (checkedId) {
                binding.themeDark.id -> "dark"
                binding.themeLight.id -> "light"
                else -> "system"
            }
            settings.setThemeMode(mode)
            settings.applyToApp()
        }

        binding.langToggle.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            val lang = when (checkedId) {
                binding.langTr.id -> "tr"
                binding.langEn.id -> "en"
                else -> "system"
            }
            settings.setLanguage(lang)
            settings.applyToApp()
        }

        binding.logoutButton.setOnClickListener {
            AuthRepository(applicationContext).logout()
            startActivity(Intent(this, LoginActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
            finish()
        }

        // Bottom nav
        binding.bottomNav.selectedItemId = com.tezproje.R.id.nav_settings
        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                com.tezproje.R.id.nav_analyze -> {
                    startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_health -> {
                    startActivity(Intent(this, com.tezproje.ui.health.DiseasesActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_assistant -> {
                    startActivity(Intent(this, com.tezproje.ui.assistant.AssistantActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_profile -> {
                    startActivity(Intent(this, ProfileActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_settings -> true
                else -> false
            }
        }
    }
}


