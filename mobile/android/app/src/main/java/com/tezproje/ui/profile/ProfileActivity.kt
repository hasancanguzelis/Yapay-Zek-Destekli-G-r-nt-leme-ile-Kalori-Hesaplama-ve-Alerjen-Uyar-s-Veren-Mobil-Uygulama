package com.tezproje.ui.profile

import android.os.Bundle
import android.view.MenuItem
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import com.google.android.material.chip.Chip
import com.tezproje.databinding.ActivityProfileBinding
import com.tezproje.ui.MainActivity
import com.tezproje.ui.settings.SettingsActivity
import com.tezproje.data.AuthRepository
import com.tezproje.network.ApiClient
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.Locale
import com.github.mikephil.charting.charts.PieChart
import com.github.mikephil.charting.data.PieData
import com.github.mikephil.charting.data.PieDataSet
import com.github.mikephil.charting.data.PieEntry
import android.view.View

class ProfileActivity : AppCompatActivity() {

    private lateinit var binding: ActivityProfileBinding
    private lateinit var viewModel: ProfileViewModel

    private data class Option(val key: String, val labelTr: String, val labelEn: String, val synonyms: List<String> = emptyList())

    // Canonical allergen keys align with backend (app/allergens.py).
    private val allergenOptions = listOf(
        Option("gluten", "Gluten", "Gluten", synonyms = listOf("buğday", "bugday", "wheat", "arpa", "çavdar", "yulaf")),
        Option("milk", "Süt", "Milk", synonyms = listOf("sut", "milk", "lactose", "laktoz", "peynir", "yoğurt")),
        Option("egg", "Yumurta", "Egg", synonyms = listOf("egg", "yumurta")),
        Option("peanut", "Yer fıstığı", "Peanut", synonyms = listOf("peanut", "groundnut", "fıstık", "fistik", "yer fistigi")),
        Option("tree_nuts", "Kuruyemiş", "Tree Nuts", synonyms = listOf("badem", "fındık", "ceviz", "kaju", "antep fıstığı", "nuts")),
        Option("soy", "Soya", "Soy", synonyms = listOf("soya", "soy", "soja", "soybeans")),
        Option("sesame", "Susam", "Sesame", synonyms = listOf("susam", "sesame", "sesame-seeds")),
        Option("mustard", "Hardal", "Mustard", synonyms = listOf("hardal", "mustard")),
        Option("fish", "Balık", "Fish", synonyms = listOf("balık", "balik", "fish")),
        Option("shellfish", "Kabuklu deniz ürünleri", "Shellfish", synonyms = listOf("kabuklu", "karides", "midye", "shellfish", "crustaceans", "molluscs")),
        Option("celery", "Kereviz", "Celery", synonyms = listOf("kereviz", "celery")),
        Option("lupin", "Acı bakla", "Lupin", synonyms = listOf("acı bakla", "aci bakla", "lupin")),
        Option("sulphites", "Sülfitler", "Sulphites", synonyms = listOf("sülfit", "sulfit", "sulfite", "sulphite", "kükürt dioksit", "sulfur dioxide")),
    )

    // Canonical condition keys (backend currently treats as informational).
    private val conditionOptions = listOf(
        Option("diabetes", "Diyabet", "Diabetes", synonyms = listOf("diyabet", "diabetes")),
        Option("celiac", "Çölyak", "Celiac", synonyms = listOf("çölyak", "colyak", "celiac", "coeliac")),
        Option("hypertension", "Hipertansiyon", "Hypertension", synonyms = listOf("hipertansiyon", "hypertension")),
        Option("hypercholesterolemia", "Hiperkolesterolemi", "High Cholesterol", synonyms = listOf("hiperkolesterolemi", "high cholesterol", "kolesterol")),
        Option("kidney_disease", "Böbrek hastalığı", "Kidney Disease", synonyms = listOf("böbrek", "bobrek", "kidney")),
        Option("liver_disease", "Karaciğer hastalığı", "Liver Disease", synonyms = listOf("karaciğer", "karaciger", "liver")),
        Option("heart_disease", "Kalp hastalığı", "Heart Disease", synonyms = listOf("kalp", "heart")),
        Option("obesity", "Obezite", "Obesity", synonyms = listOf("obezite", "obesity")),
        Option("reflux", "Reflü", "Reflux", synonyms = listOf("reflü", "reflu", "reflux", "gerd")),
        Option("ibs", "IBS", "IBS", synonyms = listOf("ibs", "irritable bowel")),
        Option("gout", "Gut", "Gout", synonyms = listOf("gut", "gout", "ürik asit", "urik asit")),
        Option("lactose_intolerance", "Laktoz intoleransı", "Lactose Intolerance", synonyms = listOf("laktoz", "lactose intolerance", "laktoz intoleransı")),
    )
    
    private fun isTurkish(): Boolean {
        val lang = try {
            resources.configuration.locales[0]?.language
        } catch (_: Exception) {
            null
        } ?: java.util.Locale.getDefault().language
        return lang.lowercase().startsWith("tr")
    }

    private var didAutoMigrate = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityProfileBinding.inflate(layoutInflater)
        setContentView(binding.root)

        viewModel = ViewModelProvider(this)[ProfileViewModel::class.java]

        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        renderBaseChips()

        binding.addAllergenButton.setOnClickListener {
            addCustomChip(
                group = binding.allergensChipGroup,
                value = binding.customAllergenEdit.text?.toString().orEmpty(),
            )
            binding.customAllergenEdit.setText("")
        }

        binding.addConditionButton.setOnClickListener {
            addCustomChip(
                group = binding.conditionsChipGroup,
                value = binding.customConditionEdit.text?.toString().orEmpty(),
            )
            binding.customConditionEdit.setText("")
        }
        
        binding.refreshCalorieButton.setOnClickListener {
            loadDailyCalorieInfo()
        }
        
        // İlk yüklemede kalori bilgilerini yükle
        loadDailyCalorieInfo()

        // Gender dropdown
        binding.genderEdit.setOnClickListener {
            val genders = arrayOf("Erkek (male)", "Kadın (female)", "Diğer (other)")
            val currentGender = binding.genderEdit.text?.toString()?.trim().orEmpty()
            val currentIndex = genders.indexOfFirst { it.contains(currentGender, ignoreCase = true) }
            
            android.app.AlertDialog.Builder(this)
                .setTitle("Cinsiyet Seçin")
                .setSingleChoiceItems(genders, if (currentIndex >= 0) currentIndex else 0) { dialog, which ->
                    val selected = genders[which]
                    binding.genderEdit.setText(selected.substringBefore(" (").trim())
                    dialog.dismiss()
                }
                .show()
        }
        
        // Activity level dropdown
        binding.activityLevelEdit.setOnClickListener {
            val activityLevels = arrayOf(
                "Hareketsiz (sedentary)",
                "Hafif (light)",
                "Orta (moderate)",
                "Aktif (active)",
                "Çok Aktif (very_active)"
            )
            val currentLevel = binding.activityLevelEdit.text?.toString()?.trim().orEmpty()
            val currentIndex = activityLevels.indexOfFirst { it.contains(currentLevel, ignoreCase = true) }
            
            android.app.AlertDialog.Builder(this)
                .setTitle("Aktivite Seviyesi Seçin")
                .setSingleChoiceItems(activityLevels, if (currentIndex >= 0) currentIndex else 0) { dialog, which ->
                    val selected = activityLevels[which]
                    binding.activityLevelEdit.setText(selected.substringBefore(" (").trim())
                    dialog.dismiss()
                }
                .show()
        }
        
        binding.saveButton.setOnClickListener {
            viewModel.save(
                allergensComma = selectedKeys(binding.allergensChipGroup).joinToString(","),
                conditionsComma = selectedKeys(binding.conditionsChipGroup).joinToString(","),
                age = binding.ageEdit.text?.toString()?.trim()?.toIntOrNull(),
                weightKg = binding.weightEdit.text?.toString()?.trim()?.toDoubleOrNull(),
                heightCm = binding.heightEdit.text?.toString()?.trim()?.toDoubleOrNull(),
                gender = when (binding.genderEdit.text?.toString()?.trim()?.lowercase()) {
                    "erkek" -> "male"
                    "kadın", "kadin" -> "female"
                    "diğer", "diger" -> "other"
                    else -> null
                },
                activityLevel = when (binding.activityLevelEdit.text?.toString()?.trim()?.lowercase()) {
                    "hareketsiz" -> "sedentary"
                    "hafif" -> "light"
                    "orta" -> "moderate"
                    "aktif" -> "active"
                    "çok aktif", "cok aktif" -> "very_active"
                    else -> null
                }
            )
        }

        lifecycleScope.launch {
            viewModel.state.collect { state ->
                val p = state.profile

                // Load chips from saved profile (predefined + custom)
                applySelections(
                    group = binding.allergensChipGroup,
                    baseOptions = allergenOptions,
                    savedValues = p.allergens,
                )
                applySelections(
                    group = binding.conditionsChipGroup,
                    baseOptions = conditionOptions,
                    savedValues = p.conditions,
                )
                
                // Kalori takibi alanlarını yükle
                binding.ageEdit.setText(p.age?.toString() ?: "")
                binding.weightEdit.setText(p.weightKg?.toString() ?: "")
                binding.heightEdit.setText(p.heightCm?.toString() ?: "")
                
                // Cinsiyet
                val genderText = when (p.gender?.lowercase()) {
                    "male" -> if (isTurkish()) "Erkek" else "Male"
                    "female" -> if (isTurkish()) "Kadın" else "Female"
                    "other" -> if (isTurkish()) "Diğer" else "Other"
                    else -> ""
                }
                binding.genderEdit.setText(genderText)
                
                // Aktivite seviyesi
                val activityText = when (p.activityLevel?.lowercase()) {
                    "sedentary" -> if (isTurkish()) "Hareketsiz" else "Sedentary"
                    "light" -> if (isTurkish()) "Hafif" else "Light"
                    "moderate" -> if (isTurkish()) "Orta" else "Moderate"
                    "active" -> if (isTurkish()) "Aktif" else "Active"
                    "very_active" -> if (isTurkish()) "Çok Aktif" else "Very Active"
                    else -> ""
                }
                binding.activityLevelEdit.setText(activityText)

                binding.messageText.text = state.savedMessage ?: state.errorMessage.orEmpty()
                
                // Profil kaydedildiğinde kalori bilgilerini yenile
                if (state.savedMessage != null && state.savedMessage!!.contains("kaydedildi", ignoreCase = true)) {
                    loadDailyCalorieInfo()
                }

                // One-time migration: if older saved strings exist, rewrite as canonical keys.
                if (!didAutoMigrate) {
                    didAutoMigrate = true
                    val migratedAllergens = p.allergens.map { canonicalizeAllergen(it) }
                    val migratedConditions = p.conditions.map { canonicalizeCondition(it) }
                    if (migratedAllergens != p.allergens || migratedConditions != p.conditions) {
                        viewModel.save(
                            allergensComma = migratedAllergens.joinToString(","),
                            conditionsComma = migratedConditions.joinToString(","),
                            age = state.profile.age,
                            weightKg = state.profile.weightKg,
                            heightCm = state.profile.heightCm,
                            gender = state.profile.gender,
                            activityLevel = state.profile.activityLevel,
                            showMessage = false
                        )
                    }
                }
            }
        }

        // Bottom nav
        binding.bottomNav.selectedItemId = com.tezproje.R.id.nav_profile
        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                com.tezproje.R.id.nav_analyze -> {
                    startActivity(android.content.Intent(this, MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_health -> {
                    startActivity(android.content.Intent(this, com.tezproje.ui.health.DiseasesActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_assistant -> {
                    startActivity(android.content.Intent(this, com.tezproje.ui.assistant.AssistantActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_profile -> true
                com.tezproje.R.id.nav_settings -> {
                    startActivity(android.content.Intent(this, SettingsActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP))
                    finish()
                    true
                }
                else -> false
            }
        }
    }

    override fun onPause() {
        super.onPause()
        // Kullanıcı Kaydet'e basmasa bile, ekrandan çıkarken sessizce kalıcılaştır.
        // Böylece uygulama kapanıp açıldığında profil kaybolmaz.
            viewModel.save(
                allergensComma = selectedKeys(binding.allergensChipGroup).joinToString(","),
                conditionsComma = selectedKeys(binding.conditionsChipGroup).joinToString(","),
                age = binding.ageEdit.text?.toString()?.trim()?.toIntOrNull(),
                weightKg = binding.weightEdit.text?.toString()?.trim()?.toDoubleOrNull(),
                heightCm = binding.heightEdit.text?.toString()?.trim()?.toDoubleOrNull(),
                gender = when (binding.genderEdit.text?.toString()?.trim()?.lowercase()) {
                    "erkek" -> "male"
                    "kadın", "kadin" -> "female"
                    "diğer", "diger" -> "other"
                    else -> null
                },
                activityLevel = when (binding.activityLevelEdit.text?.toString()?.trim()?.lowercase()) {
                    "hareketsiz" -> "sedentary"
                    "hafif" -> "light"
                    "orta" -> "moderate"
                    "aktif" -> "active"
                    "çok aktif", "cok aktif" -> "very_active"
                    else -> null
                },
                showMessage = false
            )
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) {
            finish()
            return true
        }
        return super.onOptionsItemSelected(item)
    }

    private fun renderBaseChips() {
        binding.allergensChipGroup.removeAllViews()
        val isTr = isTurkish()
        allergenOptions.forEach { 
            addChoiceChip(binding.allergensChipGroup, key = it.key, label = if (isTr) it.labelTr else it.labelEn, isChecked = false) 
        }

        binding.conditionsChipGroup.removeAllViews()
        conditionOptions.forEach { 
            addChoiceChip(binding.conditionsChipGroup, key = it.key, label = if (isTr) it.labelTr else it.labelEn, isChecked = false) 
        }
    }

    private fun addChoiceChip(
        group: com.google.android.material.chip.ChipGroup,
        key: String,
        label: String,
        isChecked: Boolean
    ) {
        val chip = Chip(this).apply {
            text = label
            tag = key // store canonical key
            isCheckable = true
            this.isChecked = isChecked
            isClickable = true
            isFocusable = true
            // Custom items can be removed with long press
            setOnLongClickListener {
                group.removeView(this)
                true
            }
        }
        group.addView(chip)
    }

    private fun addCustomChip(group: com.google.android.material.chip.ChipGroup, value: String) {
        val raw = value.trim()
        if (raw.isBlank()) return

        val isTr = isTurkish()
        val (key, label) = if (group.id == binding.allergensChipGroup.id) {
            val k = canonicalizeAllergen(raw)
            val opt = allergenOptions.find { it.key == k }
            Pair(k, if (isTr) (opt?.labelTr ?: raw) else (opt?.labelEn ?: raw))
        } else {
            val k = canonicalizeCondition(raw)
            val opt = conditionOptions.find { it.key == k }
            Pair(k, if (isTr) (opt?.labelTr ?: raw) else (opt?.labelEn ?: raw))
        }

        val existingKeys = selectedKeys(group, includeUnchecked = true).map { it.lowercase() }.toSet()
        if (existingKeys.contains(key.lowercase())) {
            // if already exists, just check it
            for (i in 0 until group.childCount) {
                val c = group.getChildAt(i)
                if (c is Chip && (c.tag?.toString() ?: "").equals(key, ignoreCase = true)) {
                    c.isChecked = true
                    break
                }
            }
            return
        }

        addChoiceChip(group, key = key, label = label, isChecked = true)
    }

    private fun selectedKeys(
        group: com.google.android.material.chip.ChipGroup,
        includeUnchecked: Boolean = false
    ): List<String> {
        val out = mutableListOf<String>()
        for (i in 0 until group.childCount) {
            val v = group.getChildAt(i)
            if (v is Chip) {
                if (includeUnchecked || v.isChecked) {
                    val t = v.tag?.toString()?.trim().orEmpty()
                    if (t.isNotBlank()) out.add(t)
                }
            }
        }
        // de-dup keep order (case-insensitive)
        val seen = mutableSetOf<String>()
        return out.filter {
            val k = it.lowercase()
            if (seen.contains(k)) false else { seen.add(k); true }
        }
    }

    private fun applySelections(
        group: com.google.android.material.chip.ChipGroup,
        baseOptions: List<Option>,
        savedValues: List<String>,
    ) {
        val savedCanon = if (group.id == binding.allergensChipGroup.id) {
            savedValues.map { canonicalizeAllergen(it) }
        } else {
            savedValues.map { canonicalizeCondition(it) }
        }
        val savedSet = savedCanon.map { it.trim() }.filter { it.isNotBlank() }.toSet()

        // Ensure all base chips exist and update checked state
        for (i in 0 until group.childCount) {
            val v = group.getChildAt(i)
            if (v is Chip) {
                val key = v.tag?.toString().orEmpty()
                v.isChecked = savedSet.any { it.equals(key, ignoreCase = true) }
            }
        }

        // Add missing saved values as custom chips
        val isTr = isTurkish()
        val currentAll = selectedKeys(group, includeUnchecked = true).map { it.lowercase() }.toSet()
        savedSet.forEach { s ->
            if (!currentAll.contains(s.lowercase())) {
                val label = labelForKey(baseOptions, s, isTr) ?: s
                addChoiceChip(group, key = s, label = label, isChecked = true)
            }
        }

        // If someone removed base chip by long press, restore it on next load.
        val nowAll = selectedKeys(group, includeUnchecked = true).map { it.lowercase() }.toSet()
        baseOptions.forEach { opt ->
            if (!nowAll.contains(opt.key.lowercase())) {
                val label = if (isTr) opt.labelTr else opt.labelEn
                addChoiceChip(group, key = opt.key, label = label, isChecked = savedSet.any { it.equals(opt.key, ignoreCase = true) })
            }
        }
    }

    private fun labelForKey(options: List<Option>, key: String, isTurkish: Boolean): String? {
        val opt = options.firstOrNull { it.key.equals(key, ignoreCase = true) }
        return if (isTurkish) opt?.labelTr else opt?.labelEn
    }

    private fun normalizeTr(s: String): String {
        return s.trim()
            .lowercase()
            .replace("ı", "i")
            .replace("ğ", "g")
            .replace("ş", "s")
            .replace("ç", "c")
            .replace("ö", "o")
            .replace("ü", "u")
    }

    private fun canonicalizeAllergen(input: String): String {
        val n = normalizeTr(input)
        allergenOptions.forEach { opt ->
            if (n == normalizeTr(opt.key)) return opt.key
            if (n == normalizeTr(opt.labelTr)) return opt.key
            if (opt.synonyms.any { normalizeTr(it) == n }) return opt.key
        }
        return input.trim()
    }

    private fun canonicalizeCondition(input: String): String {
        val n = normalizeTr(input)
        conditionOptions.forEach { opt ->
            if (n == normalizeTr(opt.key)) return opt.key
            if (n == normalizeTr(opt.labelTr)) return opt.key
            if (opt.synonyms.any { normalizeTr(it) == n }) return opt.key
        }
        return input.trim()
    }
    
    private fun loadDailyCalorieInfo() {
        val authRepo = AuthRepository(this)
        val token = authRepo.getAccessToken()
        
        if (token.isNullOrBlank()) {
            binding.calorieTargetText.text = "Günlük kalori takibi için giriş yapmanız gerekiyor."
            binding.todayConsumptionText.text = ""
            return
        }
        
        binding.calorieTargetText.text = "Yükleniyor..."
        binding.todayConsumptionText.text = ""
        binding.calorieProgressBar.isVisible = true
        
        lifecycleScope.launch {
            try {
                val authorization = "Bearer $token"
                val isTurkish = isTurkish()
                
                // Kalori hedefi al
                val target = withContext(Dispatchers.IO) {
                    ApiClient.api.getCalorieTarget(authorization, "maintain")
                }
                
                // Bugünkü tüketim al
                val consumption = try {
                    withContext(Dispatchers.IO) {
                        ApiClient.api.getTodayConsumption(authorization)
                    }
                } catch (e: Exception) {
                    null // Bugünkü tüketim yoksa null
                }
                
                // Hedef kalori metni
                val targetText = if (isTurkish) {
                    buildString {
                        append("Hedef Kalori: ")
                        if (target.target != null) {
                            append(String.format(Locale.getDefault(), "%.1f", target.target))
                            append(" kcal")
                            if (target.bmr != null) {
                                append(" (BMR: ${String.format(Locale.getDefault(), "%.1f", target.bmr)})")
                            }
                            if (target.tdee != null) {
                                append(" | TDEE: ${String.format(Locale.getDefault(), "%.1f", target.tdee)})")
                            }
                        } else {
                            append("Profil bilgilerinizi tamamlayın (yaş, kilo, boy, cinsiyet, aktivite)")
                        }
                    }
                } else {
                    buildString {
                        append("Target Calories: ")
                        if (target.target != null) {
                            append(String.format(Locale.getDefault(), "%.1f", target.target))
                            append(" kcal")
                            if (target.bmr != null) {
                                append(" (BMR: ${String.format(Locale.getDefault(), "%.1f", target.bmr)})")
                            }
                            if (target.tdee != null) {
                                append(" | TDEE: ${String.format(Locale.getDefault(), "%.1f", target.tdee)})")
                            }
                        } else {
                            append("Complete your profile (age, weight, height, gender, activity)")
                        }
                    }
                }
                
                binding.calorieTargetText.text = targetText
                
                // Bugünkü tüketim metni ve pasta grafiği
                val consumptionText = if (consumption != null) {
                    val consumed = consumption.nutrition.calories_kcal ?: 0.0
                    val targetCal = target.target ?: 0.0
                    val remaining = consumption.remaining ?: targetCal
                    val progress = if (targetCal > 0) {
                        ((consumed / targetCal) * 100).coerceIn(0.0, 100.0).toInt()
                    } else {
                        0
                    }
                    
                    binding.calorieProgressBar.progress = progress
                    binding.calorieProgressBar.isVisible = true
                    
                    // Günlük makro besin pasta grafiğini oluştur
                    setupDailyNutritionPieChart(consumption.nutrition, isTurkish)
                    
                    if (isTurkish) {
                        buildString {
                            append("Bugünkü Tüketim: ")
                            append(String.format(Locale.getDefault(), "%.1f", consumed))
                            append(" kcal")
                            if (remaining >= 0) {
                                append(" | Kalan: ${String.format(Locale.getDefault(), "%.1f", remaining)} kcal")
                            } else {
                                append(" | Aşıldı: ${String.format(Locale.getDefault(), "%.1f", -remaining)} kcal")
                            }
                            if (consumption.is_over_target) {
                                append(" ⚠️")
                            }
                            if (consumption.is_over_limit) {
                                append(" 🚨")
                            }
                            if (consumption.warnings.isNotEmpty()) {
                                append("\n${consumption.warnings.joinToString("\n")}")
                            }
                        }
                    } else {
                        buildString {
                            append("Today's Consumption: ")
                            append(String.format(Locale.getDefault(), "%.1f", consumed))
                            append(" kcal")
                            if (remaining >= 0) {
                                append(" | Remaining: ${String.format(Locale.getDefault(), "%.1f", remaining)} kcal")
                            } else {
                                append(" | Exceeded: ${String.format(Locale.getDefault(), "%.1f", -remaining)} kcal")
                            }
                            if (consumption.is_over_target) {
                                append(" ⚠️")
                            }
                            if (consumption.is_over_limit) {
                                append(" 🚨")
                            }
                            if (consumption.warnings.isNotEmpty()) {
                                append("\n${consumption.warnings.joinToString("\n")}")
                            }
                        }
                    }
                } else {
                    // Tüketim yoksa pasta grafiğini gizle
                    binding.dailyNutritionPieChart.visibility = View.GONE
                    if (isTurkish) {
                        "Bugün henüz tüketim kaydı yok. Analiz sonucundan 'Günlük Takibe Ekle' butonuna tıklayarak ekleyebilirsiniz."
                    } else {
                        "No consumption record for today. You can add from analysis results using 'Add to Daily Tracking' button."
                    }
                }
                
                binding.todayConsumptionText.text = consumptionText
                binding.calorieProgressBar.isVisible = false
                
            } catch (e: Exception) {
                val isTurkish = isTurkish()
                binding.calorieTargetText.text = if (isTurkish) {
                    "Kalori bilgileri yüklenirken hata: ${e.message}"
                } else {
                    "Error loading calorie info: ${e.message}"
                }
                binding.todayConsumptionText.text = ""
                binding.calorieProgressBar.isVisible = false
                binding.dailyNutritionPieChart.visibility = View.GONE
            }
        }
    }
    
    private fun setupDailyNutritionPieChart(nutrition: com.tezproje.data.NutritionFacts, isTurkish: Boolean) {
        val fat = nutrition.fat_g ?: 0.0
        val carbs = nutrition.carbs_g ?: 0.0
        val protein = nutrition.protein_g ?: 0.0
        
        // Toplam makro besin
        val total = fat + carbs + protein
        
        if (total <= 0) {
            binding.dailyNutritionPieChart.visibility = View.GONE
            return
        }
        
        binding.dailyNutritionPieChart.visibility = View.VISIBLE
        
        val entries = mutableListOf<PieEntry>()
        if (fat > 0) {
            val fatLabel = if (isTurkish) "Yağ" else "Fat"
            entries.add(PieEntry(fat.toFloat(), fatLabel))
        }
        if (carbs > 0) {
            val carbsLabel = if (isTurkish) "Karbonhidrat" else "Carbs"
            entries.add(PieEntry(carbs.toFloat(), carbsLabel))
        }
        if (protein > 0) {
            val proteinLabel = if (isTurkish) "Protein" else "Protein"
            entries.add(PieEntry(protein.toFloat(), proteinLabel))
        }
        
        if (entries.isEmpty()) {
            binding.dailyNutritionPieChart.visibility = View.GONE
            return
        }
        
        val dataSet = PieDataSet(entries, if (isTurkish) "Günlük Makro Besinler (g)" else "Daily Macronutrients (g)")
        dataSet.colors = listOf(
            android.graphics.Color.parseColor("#FF6B6B"), // Kırmızı - Yağ
            android.graphics.Color.parseColor("#4ECDC4"), // Turkuaz - Karbonhidrat
            android.graphics.Color.parseColor("#95E1D3")  // Açık yeşil - Protein
        )
        dataSet.valueTextSize = 12f
        dataSet.valueTextColor = android.graphics.Color.WHITE
        
        val pieData = PieData(dataSet)
        binding.dailyNutritionPieChart.data = pieData
        
        // Grafik ayarları
        binding.dailyNutritionPieChart.description.isEnabled = false
        binding.dailyNutritionPieChart.legend.isEnabled = true
        binding.dailyNutritionPieChart.legend.textSize = 12f
        binding.dailyNutritionPieChart.setEntryLabelTextSize(12f)
        binding.dailyNutritionPieChart.setEntryLabelColor(android.graphics.Color.BLACK)
        binding.dailyNutritionPieChart.setUsePercentValues(false)
        binding.dailyNutritionPieChart.setDrawEntryLabels(true)
        binding.dailyNutritionPieChart.animateY(1000)
        binding.dailyNutritionPieChart.invalidate()
    }
}





