package com.tezproje.assistant

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException

object WebSearchHelper {
    private val client = OkHttpClient()

    /**
     * DuckDuckGo Instant Answer API kullanarak web araması yapar
     */
    suspend fun searchWeb(query: String, uiLang: String? = null): String? = withContext(Dispatchers.IO) {
        try {
            val isTr = (uiLang ?: "").trim().lowercase().startsWith("tr")
            
            // DuckDuckGo Instant Answer API
            val url = "https://api.duckduckgo.com/?q=${java.net.URLEncoder.encode(query, "UTF-8")}&format=json&no_html=1&skip_disambig=1"
            
            val request = Request.Builder()
                .url(url)
                .get()
                .build()

            val response = client.newCall(request).execute()
            
            if (response.isSuccessful) {
                val jsonString = response.body?.string()
                if (!jsonString.isNullOrBlank()) {
                    // JSON'dan AbstractText veya Answer al
                    val json = org.json.JSONObject(jsonString)
                    val abstractText = json.optString("AbstractText", "")
                    val answer = json.optString("Answer", "")
                    val answerType = json.optString("AnswerType", "")
                    
                    if (abstractText.isNotBlank()) {
                        return@withContext abstractText
                    } else if (answer.isNotBlank() && answerType == "calc") {
                        return@withContext answer
                    }
                }
            }
            
            // DuckDuckGo'dan sonuç alınamazsa, genel bir mesaj döndür
            if (isTr) {
                "Web'de '$query' hakkında bilgi bulundu. Daha detaylı bilgi için bir sağlık kuruluşuna başvurmanızı öneririm."
            } else {
                "Found information about '$query' on the web. For more detailed information, I recommend consulting a healthcare provider."
            }
        } catch (e: IOException) {
            null
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Kullanıcı mesajından arama sorgusu oluşturur
     */
    fun createSearchQuery(message: String, detectedConditions: List<String>, detectedAllergens: List<String>, uiLang: String? = null): String {
        val isTr = (uiLang ?: "").trim().lowercase().startsWith("tr")
        
        val queryParts = mutableListOf<String>()
        
        if (detectedConditions.isNotEmpty()) {
            val conditionLabels = detectedConditions.map { c ->
                if (isTr) LocalAssistant.CONDITION_LABEL_TR[c] ?: c else LocalAssistant.CONDITION_LABEL_EN[c] ?: c
            }
            queryParts.add(conditionLabels.joinToString(" "))
        }
        
        if (detectedAllergens.isNotEmpty()) {
            val allergenLabels = detectedAllergens.map { a ->
                if (isTr) LocalAssistant.ALLERGEN_LABEL_TR[a] ?: a else LocalAssistant.ALLERGEN_LABEL_EN[a] ?: a
            }
            queryParts.add(allergenLabels.joinToString(" "))
        }
        
        if (queryParts.isEmpty()) {
            // Eğer tespit edilen bir şey yoksa, mesajın kendisini kullan
            return message
        }
        
        return queryParts.joinToString(" ")
    }
}

