package com.tezproje.ui.auth

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.tezproje.data.AuthRepository
import com.tezproje.data.SettingsRepository
import com.tezproje.ui.MainActivity

/**
 * Minimal launcher that applies settings and routes to Login or Main.
 */
class LauncherActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Apply persisted settings (theme/language) before showing UI.
        SettingsRepository(applicationContext).applyToApp()

        val auth = AuthRepository(applicationContext)
        val next = if (auth.isLoggedIn()) {
            Intent(this, MainActivity::class.java)
        } else {
            Intent(this, LoginActivity::class.java)
        }
        next.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(next)
        finish()
    }
}



