package com.tezproje.ui.auth

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.tezproje.data.AuthRepository
import com.tezproje.data.SettingsRepository
import com.tezproje.databinding.ActivityRegisterBinding
import com.tezproje.ui.MainActivity

class RegisterActivity : AppCompatActivity() {
    private lateinit var binding: ActivityRegisterBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsRepository(applicationContext).applyToApp()

        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.registerButton.setOnClickListener {
            val username = binding.usernameEdit.text?.toString().orEmpty().trim()
            val password = binding.passwordEdit.text?.toString().orEmpty().trim()
            val confirm = binding.passwordConfirmEdit.text?.toString().orEmpty().trim()

            if (password != confirm) {
                binding.messageText.text = getString(com.tezproje.R.string.register_error_password_mismatch)
                return@setOnClickListener
            }

            binding.registerButton.isEnabled = false
            binding.messageText.text = "Kayıt yapılıyor..."
            
            val auth = AuthRepository(applicationContext)
            when (val result = auth.register(username, password)) {
                is AuthRepository.RegisterResult.Success -> {
                    binding.messageText.text = ""
                    // Auto-login already done in repository; go to main.
                    startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                }
                AuthRepository.RegisterResult.EmptyFields -> {
                    binding.messageText.text = getString(com.tezproje.R.string.register_error_empty)
                    binding.registerButton.isEnabled = true
                }
                AuthRepository.RegisterResult.UserExists -> {
                    binding.messageText.text = getString(com.tezproje.R.string.register_error_user_exists)
                    binding.registerButton.isEnabled = true
                }
                AuthRepository.RegisterResult.Error -> {
                    binding.messageText.text = "${getString(com.tezproje.R.string.register_error_generic)}\n(Backend bağlantısı kontrol edin)"
                    binding.registerButton.isEnabled = true
                }
            }
        }

        binding.loginLink.setOnClickListener {
            startActivity(Intent(this, LoginActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
            finish()
        }
    }
}



