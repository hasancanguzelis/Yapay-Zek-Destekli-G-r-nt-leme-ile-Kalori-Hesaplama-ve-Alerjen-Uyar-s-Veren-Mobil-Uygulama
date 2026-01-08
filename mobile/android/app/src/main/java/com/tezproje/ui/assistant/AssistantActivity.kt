package com.tezproje.ui.assistant

import android.content.Intent
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.tezproje.data.SettingsRepository
import com.tezproje.databinding.ActivityAssistantBinding
import com.tezproje.ui.MainActivity
import com.tezproje.ui.health.DiseasesActivity
import com.tezproje.ui.profile.ProfileActivity
import com.tezproje.ui.settings.SettingsActivity
import kotlinx.coroutines.launch

data class ChatMessage(
    val text: String,
    val isUser: Boolean,
    val needsMedicalAttention: Boolean = false
)

class AssistantActivity : AppCompatActivity() {
    private lateinit var binding: ActivityAssistantBinding
    private lateinit var adapter: ChatAdapter
    private val messages = mutableListOf<ChatMessage>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsRepository(applicationContext).applyToApp()
        binding = ActivityAssistantBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // İlk hoş geldin mesajı
        messages.add(
            ChatMessage(
                text = getString(com.tezproje.R.string.assistant_welcome),
                isUser = false
            )
        )

        adapter = ChatAdapter(messages)
        binding.chatRecyclerView.layoutManager = LinearLayoutManager(this).apply {
            stackFromEnd = true
        }
        binding.chatRecyclerView.adapter = adapter

        // Disclaimer metni
        binding.disclaimerText.text = getString(com.tezproje.R.string.assistant_disclaimer)

        // Mesaj input kontrolü
        binding.messageEdit.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) {
                binding.sendButton.isEnabled = !s.isNullOrBlank()
            }
        })

        binding.sendButton.setOnClickListener {
            val message = binding.messageEdit.text.toString().trim()
            if (message.isNotEmpty()) {
                sendMessage(message)
                binding.messageEdit.setText("")
            }
        }

        // Bottom Navigation
        binding.bottomNav.selectedItemId = com.tezproje.R.id.nav_assistant
        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                com.tezproje.R.id.nav_analyze -> {
                    startActivity(Intent(this, MainActivity::class.java))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_health -> {
                    startActivity(Intent(this, DiseasesActivity::class.java))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_assistant -> true
                com.tezproje.R.id.nav_profile -> {
                    startActivity(Intent(this, ProfileActivity::class.java))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_settings -> {
                    startActivity(Intent(this, SettingsActivity::class.java))
                    finish()
                    true
                }
                else -> false
            }
        }
    }

    private fun sendMessage(message: String) {
        // Kullanıcı mesajını ekle
        messages.add(ChatMessage(text = message, isUser = true))
        adapter.notifyItemInserted(messages.size - 1)
        binding.chatRecyclerView.smoothScrollToPosition(messages.size - 1)

        // Loading mesajı
        val loadingIndex = messages.size
        messages.add(ChatMessage(text = getString(com.tezproje.R.string.thinking), isUser = false))
        adapter.notifyItemInserted(loadingIndex)
        binding.chatRecyclerView.smoothScrollToPosition(loadingIndex)

        // Lokal analiz + web arama
        lifecycleScope.launch {
            try {
                val uiLang = SettingsRepository(applicationContext).getLanguage() ?: "tr"
                
                // Lokal analiz
                val analysis = com.tezproje.assistant.LocalAssistant.analyzeMessage(message, uiLang)
                
                // Loading mesajını kaldır
                messages.removeAt(loadingIndex)
                adapter.notifyItemRemoved(loadingIndex)

                // Analiz sonuçlarını göster
                val responseText = if (analysis.suggestions.isNotEmpty()) {
                    analysis.suggestions.joinToString("\n\n")
                } else {
                    if ((uiLang ?: "").trim().lowercase().startsWith("tr")) {
                        "Mesajınız analiz edildi. Daha spesifik bilgi için lütfen belirtilerinizi veya sorularınızı detaylandırın."
                    } else {
                        "Your message has been analyzed. Please provide more specific details about your symptoms or questions."
                    }
                }

                messages.add(
                    ChatMessage(
                        text = responseText,
                        isUser = false,
                        needsMedicalAttention = analysis.needsMedicalAttention
                    )
                )
                adapter.notifyItemInserted(messages.size - 1)

                // Web araması yap (eğer tespit edilen bir şey varsa)
                if (analysis.detectedConditions.isNotEmpty() || analysis.detectedAllergens.isNotEmpty()) {
                    val searchQuery = com.tezproje.assistant.WebSearchHelper.createSearchQuery(
                        message,
                        analysis.detectedConditions,
                        analysis.detectedAllergens,
                        uiLang
                    )
                    
                    val webResult = com.tezproje.assistant.WebSearchHelper.searchWeb(searchQuery, uiLang)
                    if (!webResult.isNullOrBlank()) {
                        messages.add(
                            ChatMessage(
                                text = webResult,
                                isUser = false
                            )
                        )
                        adapter.notifyItemInserted(messages.size - 1)
                    }
                }

                // Tıbbi yardım gerekliyse uyarı ekle
                if (analysis.needsMedicalAttention) {
                    messages.add(
                        ChatMessage(
                            text = com.tezproje.assistant.LocalAssistant.getDisclaimer(uiLang),
                            isUser = false,
                            needsMedicalAttention = true
                        )
                    )
                    adapter.notifyItemInserted(messages.size - 1)
                }

                binding.chatRecyclerView.smoothScrollToPosition(messages.size - 1)
            } catch (e: Exception) {
                // Loading mesajını kaldır
                messages.removeAt(loadingIndex)
                adapter.notifyItemRemoved(loadingIndex)

                // Genel hata
                val uiLang = SettingsRepository(applicationContext).getLanguage() ?: "tr"
                val isTr = (uiLang ?: "").trim().lowercase().startsWith("tr")
                val errorMessage = if (isTr) {
                    "Üzgünüm, bir hata oluştu: ${e.message ?: e.javaClass.simpleName}\n\nLütfen tekrar deneyin. Eğer sorun devam ederse, bir sağlık kuruluşuna başvurmanızı öneririm."
                } else {
                    "Sorry, an error occurred: ${e.message ?: e.javaClass.simpleName}\n\nPlease try again. If the problem persists, I recommend consulting a healthcare provider."
                }
                
                messages.add(
                    ChatMessage(
                        text = errorMessage,
                        isUser = false
                    )
                )
                adapter.notifyItemInserted(messages.size - 1)
                binding.chatRecyclerView.smoothScrollToPosition(messages.size - 1)
            }
        }
    }
}

class ChatAdapter(private val messages: List<ChatMessage>) : RecyclerView.Adapter<ChatAdapter.ViewHolder>() {
    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val messageText: TextView = view.findViewById(com.tezproje.R.id.messageText)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val layoutId = if (viewType == 0) {
            com.tezproje.R.layout.item_chat_message_user
        } else {
            com.tezproje.R.layout.item_chat_message
        }
        val view = LayoutInflater.from(parent.context).inflate(layoutId, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val message = messages[position]
        holder.messageText.text = message.text
        
        // Tıbbi yardım gerekliyse kırmızı renk
        if (message.needsMedicalAttention) {
            holder.messageText.setTextColor(0xFFFF0000.toInt())
        } else {
            holder.messageText.setTextColor(0xFF333333.toInt())
        }
    }

    override fun getItemCount(): Int = messages.size

    override fun getItemViewType(position: Int): Int {
        return if (messages[position].isUser) 0 else 1
    }
}

