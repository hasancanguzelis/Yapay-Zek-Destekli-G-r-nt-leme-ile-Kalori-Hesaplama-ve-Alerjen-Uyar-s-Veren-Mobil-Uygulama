package com.tezproje.ui.auth

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.tezproje.data.AuthRepository
import com.tezproje.data.SettingsRepository
import com.tezproje.databinding.ActivityLoginBinding
import com.tezproje.ui.MainActivity

class LoginActivity : AppCompatActivity() {
    private lateinit var binding: ActivityLoginBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsRepository(applicationContext).applyToApp()

        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.loginButton.setOnClickListener {
            val username = binding.usernameEdit.text?.toString().orEmpty().trim()
            val password = binding.passwordEdit.text?.toString().orEmpty().trim()
            val auth = AuthRepository(applicationContext)
            val result = auth.login(username, password)
            when (result) {
                is AuthRepository.LoginResult.Success -> {
                    binding.messageText.text = ""
                    startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                }
                AuthRepository.LoginResult.EmptyFields -> {
                    binding.messageText.text = getString(com.tezproje.R.string.login_error_empty)
                }
                AuthRepository.LoginResult.UserNotFound -> {
                    // Kullanıcı bulunamadı - muhtemelen veriler temizlenmiş veya kayıt yapılmamış
                    binding.messageText.text = "${getString(com.tezproje.R.string.login_error_invalid_credentials)}\n(Lütfen 'Üye ol' butonuna tıklayarak yeniden kayıt olun)"
                }
                AuthRepository.LoginResult.WrongPassword -> {
                    binding.messageText.text = getString(com.tezproje.R.string.login_error_invalid_credentials)
                }
                AuthRepository.LoginResult.Error -> {
                    binding.messageText.text = getString(com.tezproje.R.string.login_error_generic)
                }
            }
        }

        binding.signupLink.setOnClickListener {
            startActivity(Intent(this, RegisterActivity::class.java))
        }
    }
}


