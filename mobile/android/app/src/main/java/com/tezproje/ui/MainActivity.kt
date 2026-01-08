package com.tezproje.ui

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.pdf.PdfDocument
import android.os.Build
import android.os.Bundle
import android.net.Uri
import android.speech.tts.TextToSpeech
import android.text.Editable
import android.text.TextWatcher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.core.view.isVisible
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import com.google.gson.Gson
import com.google.android.material.chip.Chip
import com.tezproje.data.ProfileRepository
import com.tezproje.data.SettingsRepository
import com.tezproje.data.UserProfile
import com.tezproje.data.AuthRepository
import com.tezproje.network.ApiClient
import com.tezproje.data.NutritionFacts
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.tezproje.databinding.ActivityMainBinding
import com.tezproje.ui.camera.BarcodeScanActivity
import com.tezproje.ui.camera.PhotoCaptureActivity
import com.tezproje.ui.profile.ProfileActivity
import com.tezproje.ui.settings.SettingsActivity
import coil.load
import com.github.mikephil.charting.charts.PieChart
import com.github.mikephil.charting.data.PieData
import com.github.mikephil.charting.data.PieDataSet
import com.github.mikephil.charting.data.PieEntry
import com.github.mikephil.charting.utils.ColorTemplate
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Locale

class MainActivity : AppCompatActivity() {
    private enum class Mode { PACKAGED, MEAL }

    private lateinit var binding: ActivityMainBinding
    private lateinit var viewModel: MainViewModel

    private var lastUiState: UiState = UiState.Idle
    private var ocrExpanded: Boolean = false
    private var ocrFullText: String = ""
    private var lastResponse: com.tezproje.data.AnalyzeResponse? = null
    private var currentProfile: UserProfile = UserProfile()
    private var mode: Mode = Mode.PACKAGED

    private val gson = Gson()
    private val cacheFileName = "last_result.json"
    
    // Text-to-Speech
    private var textToSpeech: TextToSpeech? = null
    private val CHANNEL_ID = "tezproje_allergen_alerts"
    private val NOTIFICATION_ID = 1001

    private fun currentUiLang(): String {
        val lang = try {
            resources.configuration.locales[0]?.language ?: Locale.getDefault().language
        } catch (_: Exception) {
            Locale.getDefault().language
        }
        return if (lang.lowercase().startsWith("en")) "en" else "tr"
    }

    private val photoCaptureLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode != RESULT_OK) return@registerForActivityResult
        val path = result.data?.getStringExtra(PhotoCaptureActivity.EXTRA_PHOTO_PATH) ?: return@registerForActivityResult
        val file = File(path)
        if (mode != Mode.PACKAGED) return@registerForActivityResult
        analyzePackagedFromSelectedImage(file)
    }

    private val barcodeScanLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode != RESULT_OK) return@registerForActivityResult
        val barcode = result.data?.getStringExtra(BarcodeScanActivity.EXTRA_BARCODE) ?: return@registerForActivityResult
        binding.barcodeEdit.setText(barcode)
        binding.statusText.text = "Barkod bulundu: $barcode"
        // Barkod tarandıktan sonra otomatik analiz (paketli ürün akışı)
        if (mode == Mode.PACKAGED && lastUiState != UiState.Loading) {
            analyzeByBarcodeOnly()
        } else {
            applyEnabledState(isLoading = lastUiState == UiState.Loading, canShare = lastResponse != null)
        }
    }

    private val pickMealImageLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri ->
        if (uri == null || mode != Mode.MEAL) return@registerForActivityResult
        try {
            // URI'den File'a kopyala
            val inputStream = contentResolver.openInputStream(uri) ?: return@registerForActivityResult
            val tempFile = createTempImage("meal_image_", "jpg")
            val outputStream = java.io.FileOutputStream(tempFile)
            inputStream.copyTo(outputStream)
            inputStream.close()
            outputStream.close()
            analyzeImageCalories(tempFile)
        } catch (e: Exception) {
            binding.statusText.text = "Görüntü seçilemedi: ${e.message}"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsRepository(applicationContext).applyToApp()
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        viewModel = ViewModelProvider(this)[MainViewModel::class.java]

        // Mode switching
        binding.modeToggleGroup.check(binding.modePackagedButton.id)
        binding.modeToggleGroup.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            mode = if (checkedId == binding.modeMealButton.id) Mode.MEAL else Mode.PACKAGED
            renderMode()
        }

        binding.captureButton.setOnClickListener { onCaptureAnalyzeClicked() }
        binding.scanBarcodeButton.setOnClickListener { openBarcodeScanner() }
        binding.barcodeOnlyButton.setOnClickListener { analyzeByBarcodeOnly() }
        binding.mealAnalyzeButton.setOnClickListener { analyzeMealNow() }
        binding.mealImageCalorieButton.setOnClickListener { onMealImageCalorieClicked() }

        // Barkod alanı değişince buton aktifliğini güncelle
        binding.barcodeEdit.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) {
                applyEnabledState(isLoading = lastUiState == UiState.Loading, canShare = lastResponse != null)
            }
        })

        binding.shareJsonButton.setOnClickListener { shareAsJson() }
        binding.sharePdfButton.setOnClickListener { shareAsPdf() }
        binding.editProfileButton.setOnClickListener {
            startActivity(Intent(this, ProfileActivity::class.java))
        }
        binding.addToDailyConsumptionButton.setOnClickListener {
            addToDailyConsumption()
        }

        binding.ocrToggleButton.setOnClickListener {
            toggleOcr()
        }

        lifecycleScope.launch {
            viewModel.state.collect { state ->
                render(state)
            }
        }

        // Önceki sonucu (varsa) göster
        loadCachedResultIfAny()

        // Profil özetini yükle
        loadProfileAndRender()

        renderMode()
        
        // Arka plan görselini yükle (Unsplash'tan ücretsiz sağlıklı yiyecek görseli)
        loadBackgroundImage()
        
        // Text-to-Speech başlat
        initializeTextToSpeech()
        
        // Notification channel oluştur
        createNotificationChannel()

        // Bottom nav
        binding.bottomNav.selectedItemId = com.tezproje.R.id.nav_analyze
        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                com.tezproje.R.id.nav_analyze -> true
                com.tezproje.R.id.nav_health -> {
                    startActivity(Intent(this, com.tezproje.ui.health.DiseasesActivity::class.java))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_assistant -> {
                    startActivity(Intent(this, com.tezproje.ui.assistant.AssistantActivity::class.java))
                    finish()
                    true
                }
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

    override fun onResume() {
        super.onResume()
        // Profil ekranından dönünce güncelle
        loadProfileAndRender()
    }

    private fun loadProfileAndRender() {
        val repo = ProfileRepository(applicationContext)
        currentProfile = repo.loadProfile()
        fun displayAllergen(a: String, isTurkish: Boolean): String {
            return when (a.trim().lowercase()) {
                "gluten" -> if (isTurkish) "Gluten" else "Gluten"
                "milk" -> if (isTurkish) "Süt" else "Milk"
                "egg" -> if (isTurkish) "Yumurta" else "Egg"
                "peanut" -> if (isTurkish) "Yer fıstığı" else "Peanut"
                "tree_nuts" -> if (isTurkish) "Kuruyemiş" else "Tree Nuts"
                "soy" -> if (isTurkish) "Soya" else "Soy"
                "sesame" -> if (isTurkish) "Susam" else "Sesame"
                "mustard" -> if (isTurkish) "Hardal" else "Mustard"
                "fish" -> if (isTurkish) "Balık" else "Fish"
                "shellfish" -> if (isTurkish) "Kabuklu deniz ürünleri" else "Shellfish"
                else -> a
            }
        }
        fun displayCondition(c: String, isTurkish: Boolean): String {
            return when (c.trim().lowercase()) {
                "diabetes" -> if (isTurkish) "Diyabet" else "Diabetes"
                "celiac" -> if (isTurkish) "Çölyak" else "Celiac"
                "hypertension" -> if (isTurkish) "Hipertansiyon" else "Hypertension"
                "hypercholesterolemia" -> if (isTurkish) "Hiperkolesterolemi" else "High Cholesterol"
                "kidney_disease" -> if (isTurkish) "Böbrek hastalığı" else "Kidney Disease"
                "liver_disease" -> if (isTurkish) "Karaciğer hastalığı" else "Liver Disease"
                "heart_disease" -> if (isTurkish) "Kalp hastalığı" else "Heart Disease"
                "obesity" -> if (isTurkish) "Obezite" else "Obesity"
                "reflux" -> if (isTurkish) "Reflü" else "Reflux"
                "ibs" -> "IBS"
                else -> c
            }
        }
        val isTurkish = resources.configuration.locales[0]?.language?.startsWith("tr", ignoreCase = true) ?: true
        binding.profileSummaryText.text = buildString {
            append(getString(com.tezproje.R.string.profile_allergen_label))
            append(" ")
            append(
                if (currentProfile.allergens.isEmpty()) "-" else currentProfile.allergens.joinToString { displayAllergen(it, isTurkish) }
            )
            append("\n")
            append(getString(com.tezproje.R.string.profile_condition_label))
            append(" ")
            append(
                if (currentProfile.conditions.isEmpty()) "-" else currentProfile.conditions.joinToString { displayCondition(it, isTurkish) }
            )
        }
    }

    private fun render(state: UiState) {
        lastUiState = state
        when (state) {
            UiState.Idle -> {
                binding.progress.isVisible = false
                applyEnabledState(isLoading = false, canShare = lastResponse != null)
                binding.statusText.text = getString(com.tezproje.R.string.ready)
            }
            UiState.Loading -> {
                binding.progress.isVisible = true
                applyEnabledState(isLoading = true, canShare = false)
                binding.statusText.text = getString(com.tezproje.R.string.analyzing)
                hideResultCards()
            }
            is UiState.Success -> {
                binding.progress.isVisible = false
                applyEnabledState(isLoading = false, canShare = true)
                binding.statusText.text = getString(com.tezproje.R.string.analysis_complete)
                showResult(state.data)
            }
            is UiState.Error -> {
                binding.progress.isVisible = false
                applyEnabledState(isLoading = false, canShare = false)
                binding.statusText.text = getString(com.tezproje.R.string.error)
                hideResultCards()
                binding.warningsCard.isVisible = true
                binding.warningsText.text = state.message
            }
        }
    }

    private fun applyEnabledState(isLoading: Boolean, canShare: Boolean) {
        val packaged = mode == Mode.PACKAGED
        val meal = mode == Mode.MEAL

        binding.captureButton.isEnabled = !isLoading && packaged
        binding.scanBarcodeButton.isEnabled = !isLoading && packaged
        // Barkod ile ara, kamera gerektirmez.
        val barcode = binding.barcodeEdit.text?.toString()?.trim().orEmpty()
        binding.barcodeOnlyButton.isEnabled = !isLoading && packaged && isValidBarcode(barcode)

        binding.mealAnalyzeButton.isEnabled = !isLoading && meal
        binding.mealImageCalorieButton.isEnabled = !isLoading && meal

        binding.shareJsonButton.isEnabled = !isLoading && canShare
        binding.sharePdfButton.isEnabled = !isLoading && canShare
    }

    private fun renderMode() {
        val packaged = mode == Mode.PACKAGED
        binding.packagedSection.isVisible = packaged
        binding.mealSection.isVisible = !packaged
        binding.captureButton.isVisible = packaged
        if (packaged) {
            binding.titleText.text = getString(com.tezproje.R.string.mode_packaged)
        } else {
            binding.titleText.text = getString(com.tezproje.R.string.mode_meal)
        }

        // Mod değişince butonların enable/disable durumunu da güncelle (aksi halde eski moddan disabled kalabiliyor).
        applyEnabledState(isLoading = lastUiState == UiState.Loading, canShare = lastResponse != null)
    }

    private fun hideResultCards() {
        binding.detectedAllergensLabel.isVisible = false
        binding.allergenChipGroup.isVisible = false
        binding.allergenChipGroup.removeAllViews()
        binding.warningsCard.isVisible = false
        binding.nutritionCard.isVisible = false
        binding.ingredientsCard.isVisible = false
        binding.ocrCard.isVisible = false
        binding.ocrText.isVisible = false
        binding.ocrToggleButton.text = getString(com.tezproje.R.string.show)
        ocrExpanded = false
        ocrFullText = ""
        lastResponse = null
    }

    private fun onCaptureAnalyzeClicked() {
        if (mode != Mode.PACKAGED) return
        photoCaptureLauncher.launch(Intent(this, PhotoCaptureActivity::class.java))
    }

    /**
     * Kullanıcıya "OCR dili" seçtirmiyoruz.
     * OCR/hesaplama dili, Ayarlar'da seçilen uygulama diliyle aynı olacak şekilde otomatik seçilir.
     *
     * Backend tarafında Tesseract dil kodları kullanıldığı için (tur/eng) map ediyoruz.
     */
    private fun resolveOcrLangForApp(): String {
        val lang = try {
            resources.configuration.locales[0]?.language
        } catch (_: Exception) {
            null
        } ?: Locale.getDefault().language

        return if (lang.equals("tr", ignoreCase = true)) "tur" else "eng"
    }

    private fun analyzeByBarcodeOnly() {
        if (mode != Mode.PACKAGED) return
        val barcode = binding.barcodeEdit.text?.toString()?.trim().orEmpty()
        if (!isValidBarcode(barcode)) {
            binding.statusText.text = "Barkod formatı geçersiz. (8/12/13/14 haneli sayısal olmalı)"
            return
        }
        // Kullanıcıya anlık geri bildirim
        binding.statusText.text = "Barkod ile ürün aranıyor..."
        binding.progress.isVisible = true
        viewModel.analyzePackagedByBarcode(barcode, currentProfile, uiLang = currentUiLang())
    }

    private fun isValidBarcode(value: String): Boolean {
        val b = value.trim()
        if (b.isEmpty()) return false
        if (!b.all { it.isDigit() }) return false
        return b.length == 8 || b.length == 12 || b.length == 13 || b.length == 14
    }

    private fun openBarcodeScanner() {
        if (mode != Mode.PACKAGED) return
        barcodeScanLauncher.launch(Intent(this, BarcodeScanActivity::class.java))
    }

    private fun analyzeMealNow() {
        if (mode != Mode.MEAL) return
        val dishName = binding.mealNameEdit.text?.toString().orEmpty().trim()
        if (dishName.isBlank()) {
            binding.statusText.text = "Yemek adı boş."
            return
        }
        val portionRaw = binding.portionEdit.text?.toString().orEmpty().trim()
        val portionNormalized = portionRaw
            .ifBlank { "1" }
            .replace(",", ".")
        // Kullanıcıya anlık geri bildirim (state akışı gelmezse bile tıklamanın çalıştığını görsün)
        binding.statusText.text = "Gönderiliyor..."
        binding.progress.isVisible = true
        viewModel.estimateMeal(dishName, portionNormalized, currentProfile, uiLang = currentUiLang())
    }

    private fun onMealImageCalorieClicked() {
        if (mode != Mode.MEAL) return
        // Galeriden görüntü seç
        pickMealImageLauncher.launch("image/*")
    }

    private fun analyzeImageCalories(imageFile: File) {
        if (mode != Mode.MEAL) return
        binding.statusText.text = "Görüntüden kalori tahmin ediliyor (AI)..."
        binding.progress.isVisible = true
        viewModel.analyzeImageCalories(imageFile, currentProfile, uiLang = currentUiLang())
    }

    private fun fileToContentUri(file: File): Uri {
        return FileProvider.getUriForFile(
            this,
            "${applicationContext.packageName}.fileprovider",
            file
        )
    }

    private fun createTempImage(prefix: String, ext: String): File {
        val time = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(System.currentTimeMillis())
        val safeExt = ext.trim().ifBlank { "jpg" }.lowercase()
        return File(cacheDir, "${prefix}${time}.$safeExt")
    }

    private fun analyzePackagedFromSelectedImage(file: File) {
        val lang = resolveOcrLangForApp()
        val uiLang = currentUiLang()
        val barcodeFromField = binding.barcodeEdit.text?.toString()?.trim().orEmpty().takeIf { it.isNotBlank() }

        fun startAnalyze(barcode: String?) {
            viewModel.analyzePackagedByPhoto(file, lang, barcode, currentProfile, uiLang = uiLang)
        }

        // Barkod girilmediyse görselden barkod okumayı dene (OCR zayıfsa OFF zenginleştirme yardımcı olur).
        if (barcodeFromField.isNullOrBlank()) {
            binding.statusText.text = "Barkod aranıyor..."
            try {
                val uri = fileToContentUri(file)
                val img = InputImage.fromFilePath(this, uri)
                val scanner = BarcodeScanning.getClient()
                scanner.process(img)
                    .addOnSuccessListener { barcodes ->
                        val raw = barcodes.firstOrNull { !it.rawValue.isNullOrBlank() }?.rawValue?.trim().orEmpty()
                        val digits = raw.filter { it.isDigit() }
                        val normalized = digits.takeIf { it.length == 8 || it.length == 12 || it.length == 13 || it.length == 14 }
                        if (!normalized.isNullOrBlank()) {
                            binding.barcodeEdit.setText(normalized)
                            binding.statusText.text = "Barkod bulundu: $normalized"
                        } else {
                            binding.statusText.text = "Barkod bulunamadı. OCR ile devam ediliyor..."
                        }
                        startAnalyze(normalized)
                    }
                    .addOnFailureListener {
                        binding.statusText.text = "Barkod okunamadı. OCR ile devam ediliyor..."
                        startAnalyze(null)
                    }
            } catch (_: Exception) {
                startAnalyze(null)
            }
        } else {
            startAnalyze(barcodeFromField)
        }
    }

    private fun showResult(resp: com.tezproje.data.AnalyzeResponse) {
        lastResponse = resp
        cacheResult(resp)

        val isMeal = resp.source == "meal_estimate" || resp.source == "meal_model" || resp.source == "image_calorie_model"
        val isOcr = resp.source == "ocr_only" || resp.source == "ocr_plus_external"
        val n = resp.nutrition
        val hasAnyNutrition =
            n.calories_kcal != null || n.fat_g != null || n.carbs_g != null || n.protein_g != null ||
                n.sugar_g != null || n.salt_g != null || n.sodium_mg != null
        if (isOcr && resp.extracted_text.isBlank() && resp.ingredients.isEmpty() && !hasAnyNutrition) {
            binding.statusText.text = getString(com.tezproje.R.string.text_not_readable)
        }

        // Alerjen chipleri
        val hasAllergens = !isMeal && resp.detected_allergens.isNotEmpty()
        if (hasAllergens) {
            binding.detectedAllergensLabel.isVisible = true
            binding.allergenChipGroup.isVisible = true
            binding.allergenChipGroup.removeAllViews()
            resp.detected_allergens.forEach { a ->
                val chip = Chip(this).apply {
                    text = a
                    isClickable = false
                    isCheckable = false
                }
                binding.allergenChipGroup.addView(chip)
            }
        } else {
            binding.detectedAllergensLabel.isVisible = false
            binding.allergenChipGroup.isVisible = false
        }

        // Uyarılar
        // Tabaklı yemekte sadece gerçek "Uyarı" satırlarını göster (debug/bilgi satırlarını gizle).
        val onlyWarnings = resp.warnings.filter {
            val s = it.trim()
            s.startsWith("Uyarı") || s.startsWith("Warning")
        }
        val showWarnings = if (isMeal) onlyWarnings.isNotEmpty() else resp.warnings.isNotEmpty()
        val hasWarnings = showWarnings
        if (showWarnings) {
            binding.warningsCard.isVisible = true
            val items = if (isMeal) onlyWarnings else resp.warnings
            binding.warningsText.text = items.joinToString(separator = "\n") { "• $it" }
        } else {
            binding.warningsCard.isVisible = false
        }
        
        // Görsel uyarı (renk kodlaması)
        applyAllergenVisualWarning(hasAllergens, hasWarnings)
        
        // Profil alerjenleriyle eşleşen alerjenler var mı kontrol et
        val profileAllergens = currentProfile.allergens
        val matchedAllergens = if (hasAllergens) {
            resp.detected_allergens.filter { it in profileAllergens }
        } else {
            emptyList()
        }
        
        // Eğer profil alerjenleriyle eşleşen alerjen varsa veya uyarı varsa bildirim ve sesli uyarı göster
        if (matchedAllergens.isNotEmpty() || hasWarnings) {
            showAllergenNotification(
                allergens = if (matchedAllergens.isNotEmpty()) matchedAllergens else resp.detected_allergens,
                warnings = if (isMeal) onlyWarnings else resp.warnings
            )
            speakAllergenWarning(
                allergens = if (matchedAllergens.isNotEmpty()) matchedAllergens else resp.detected_allergens,
                warnings = if (isMeal) onlyWarnings else resp.warnings
            )
        }

        // Besin değerleri
        binding.nutritionCard.isVisible = true
        fun fmt2(x: Double?): String {
            return if (x == null) "-" else String.format(Locale.getDefault(), "%.2f", x)
        }
        
        // Pasta grafiğini oluştur (makro besinler: yağ, karbonhidrat, protein)
        setupNutritionPieChart(n)
        
        val isTurkish = resources.configuration.locales[0]?.language?.startsWith("tr", ignoreCase = true) ?: true
        binding.nutritionText.text = buildString {
            appendLine("${getString(com.tezproje.R.string.calories)} ${getString(com.tezproje.R.string.kcal_unit)}: ${fmt2(n.calories_kcal)}")
            appendLine("${getString(com.tezproje.R.string.fat)} ${getString(com.tezproje.R.string.g_unit)}: ${fmt2(n.fat_g)}")
            appendLine("${getString(com.tezproje.R.string.carbohydrate)} ${getString(com.tezproje.R.string.g_unit)}: ${fmt2(n.carbs_g)}")
            appendLine("${getString(com.tezproje.R.string.protein)} ${getString(com.tezproje.R.string.g_unit)}: ${fmt2(n.protein_g)}")
            appendLine("${getString(com.tezproje.R.string.sugar)} ${getString(com.tezproje.R.string.g_unit)}: ${fmt2(n.sugar_g)}")
            appendLine("${getString(com.tezproje.R.string.salt)} ${getString(com.tezproje.R.string.g_unit)}: ${fmt2(n.salt_g)}")
            appendLine("${getString(com.tezproje.R.string.sodium)} ${getString(com.tezproje.R.string.mg_unit)}: ${fmt2(n.sodium_mg)}")
        }
        
        // Günlük takibe ekle butonu - sadece kalori bilgisi varsa göster
        if (n.calories_kcal != null && n.calories_kcal!! > 0) {
            binding.addToDailyConsumptionButton.isVisible = true
        } else {
            binding.addToDailyConsumptionButton.isVisible = false
        }

        // İçindekiler
        if (!isMeal && resp.ingredients.isNotEmpty()) {
            binding.ingredientsCard.isVisible = true
            binding.ingredientsText.text = resp.ingredients.joinToString(separator = "\n") { "• $it" }
        } else {
            binding.ingredientsCard.isVisible = false
        }

        // OCR metni (toggle) — sadece OCR kaynaklı analizlerde göster.
        val showOcr = resp.source == "ocr_only" || resp.source == "ocr_plus_external"
        ocrFullText = resp.extracted_text
        if (showOcr && ocrFullText.isNotBlank()) {
            binding.ocrCard.isVisible = true
            binding.ocrToggleButton.text = getString(com.tezproje.R.string.show)
            binding.ocrText.isVisible = false
            ocrExpanded = false
            binding.ocrText.text = ocrFullText.take(1200) + if (ocrFullText.length > 1200) "\n\n${getString(com.tezproje.R.string.truncated)}" else ""
        } else {
            binding.ocrCard.isVisible = false
        }
    }

    private fun toggleOcr() {
        if (!binding.ocrCard.isVisible) return
        ocrExpanded = !ocrExpanded
        binding.ocrText.isVisible = ocrExpanded
        binding.ocrToggleButton.text = if (ocrExpanded) getString(com.tezproje.R.string.hide) else getString(com.tezproje.R.string.show)
        if (ocrExpanded) {
            binding.ocrText.text = ocrFullText
        } else {
            binding.ocrText.text = ocrFullText.take(1200) + if (ocrFullText.length > 1200) "\n\n${getString(com.tezproje.R.string.truncated)}" else ""
        }
    }

    private fun shareAsJson() {
        val resp = lastResponse ?: return
        val json = gson.toJson(resp)

        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "application/json"
            putExtra(Intent.EXTRA_SUBJECT, "TezProje Analiz Sonucu (JSON)")
            putExtra(Intent.EXTRA_TEXT, json)
        }
        startActivity(Intent.createChooser(intent, "JSON paylaş"))
    }

    private fun shareAsPdf() {
        val resp = lastResponse ?: return
        val pdfFile = createPdf(resp)
        val uri = FileProvider.getUriForFile(this, "${applicationContext.packageName}.fileprovider", pdfFile)

        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "application/pdf"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, "TezProje Analiz Sonucu (PDF)")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(intent, "PDF paylaş"))
    }

    private fun createPdf(resp: com.tezproje.data.AnalyzeResponse): File {
        val doc = PdfDocument()
        val pageInfo = PdfDocument.PageInfo.Builder(595, 842, 1).create() // A4 ~ 72dpi
        val page = doc.startPage(pageInfo)
        val canvas: Canvas = page.canvas

        val paint = Paint().apply { textSize = 12f }
        var y = 40f
        fun line(s: String) {
            canvas.drawText(s, 40f, y, paint)
            y += 18f
        }

        line("TezProje - Analiz Sonucu")
        line("Kaynak: ${resp.source}")
        line("")
        line("Tespit edilen alerjenler: ${resp.detected_allergens.joinToString()}")
        if (resp.warnings.isNotEmpty()) {
            line("Uyarılar:")
            resp.warnings.forEach { line("- $it") }
        }
        line("")
        line("Besin Değerleri:")
        val n = resp.nutrition
        fun fmt2(x: Double?): String {
            return if (x == null) "-" else String.format(Locale.getDefault(), "%.2f", x)
        }
        line("Kalori (kcal): ${fmt2(n.calories_kcal)}")
        line("Yağ (g): ${fmt2(n.fat_g)}")
        line("Karbonhidrat (g): ${fmt2(n.carbs_g)}")
        line("Protein (g): ${fmt2(n.protein_g)}")
        line("Şeker (g): ${fmt2(n.sugar_g)}")
        line("Tuz (g): ${fmt2(n.salt_g)}")
        line("Sodyum (mg): ${fmt2(n.sodium_mg)}")

        doc.finishPage(page)

        val outFile = File(cacheDir, "tezproje_result.pdf")
        FileOutputStream(outFile).use { doc.writeTo(it) }
        doc.close()
        return outFile
    }

    private fun cacheResult(resp: com.tezproje.data.AnalyzeResponse) {
        try {
            val json = gson.toJson(resp)
            openFileOutput(cacheFileName, MODE_PRIVATE).use { it.write(json.toByteArray()) }
        } catch (_: Exception) {
            // ignore cache failures
        }
    }

    private fun loadCachedResultIfAny() {
        try {
            val file = File(filesDir, cacheFileName)
            if (!file.exists()) return
            val json = file.readText()
            val resp = gson.fromJson(json, com.tezproje.data.AnalyzeResponse::class.java)
            // Direkt UI'ya bas (state üzerinden de yapılabilir ama basit tutuyoruz)
            binding.statusText.text = getString(com.tezproje.R.string.previous_result_loaded)
            binding.shareJsonButton.isEnabled = true
            binding.sharePdfButton.isEnabled = true
            showResult(resp)
        } catch (_: Exception) {
            // ignore
        }
    }
    
    private fun loadBackgroundImage() {
        // Unsplash'tan ücretsiz sağlıklı yiyecek ve içecek görselleri
        // Farklı görseller arasından rastgele seçim yapılabilir
        val imageUrls = listOf(
            "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=800&q=80", // Sağlıklı meyveler
            "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=800&q=80", // Taze sebzeler
            "https://images.unsplash.com/photo-1495521821757-a1efb6729352?w=800&q=80", // Renkli meyveler
            "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800&q=80", // Sağlıklı besinler
            "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&q=80", // Taze meyve tabağı
        )
        
        // Rastgele bir görsel seç
        val randomImageUrl = imageUrls.random()
        
        // ImageView'in alpha'sı zaten layout'ta 0.35 olarak ayarlı
        binding.healthyFoodsBackground.load(randomImageUrl) {
            crossfade(true)
        }
    }
    
    private fun setupNutritionPieChart(n: com.tezproje.data.NutritionFacts) {
        val fat = n.fat_g ?: 0.0
        val carbs = n.carbs_g ?: 0.0
        val protein = n.protein_g ?: 0.0
        
        // Toplam makro besin
        val total = fat + carbs + protein
        
        if (total <= 0) {
            binding.nutritionPieChart.visibility = android.view.View.GONE
            return
        }
        
        binding.nutritionPieChart.visibility = android.view.View.VISIBLE
        
        val isTurkish = resources.configuration.locales[0]?.language?.startsWith("tr", ignoreCase = true) ?: true
        val entries = mutableListOf<PieEntry>()
        if (fat > 0) entries.add(PieEntry(fat.toFloat(), getString(com.tezproje.R.string.fat)))
        if (carbs > 0) entries.add(PieEntry(carbs.toFloat(), getString(com.tezproje.R.string.carbohydrate)))
        if (protein > 0) entries.add(PieEntry(protein.toFloat(), getString(com.tezproje.R.string.protein)))
        
        if (entries.isEmpty()) {
            binding.nutritionPieChart.visibility = android.view.View.GONE
            return
        }
        
        val dataSet = PieDataSet(entries, "${getString(com.tezproje.R.string.macronutrients)} ${getString(com.tezproje.R.string.g_unit)}")
        dataSet.colors = listOf(
            android.graphics.Color.parseColor("#FF6B6B"), // Kırmızı - Yağ
            android.graphics.Color.parseColor("#4ECDC4"), // Turkuaz - Karbonhidrat
            android.graphics.Color.parseColor("#95E1D3")  // Açık yeşil - Protein
        )
        dataSet.valueTextSize = 12f
        dataSet.valueTextColor = android.graphics.Color.WHITE
        
        val pieData = PieData(dataSet)
        binding.nutritionPieChart.data = pieData
        
        // Grafik ayarları
        binding.nutritionPieChart.description.isEnabled = false
        binding.nutritionPieChart.legend.isEnabled = true
        binding.nutritionPieChart.legend.textSize = 12f
        binding.nutritionPieChart.setEntryLabelTextSize(12f)
        binding.nutritionPieChart.setEntryLabelColor(android.graphics.Color.BLACK)
        binding.nutritionPieChart.setUsePercentValues(false)
        binding.nutritionPieChart.setDrawEntryLabels(true)
        binding.nutritionPieChart.animateY(1000)
        binding.nutritionPieChart.invalidate()
    }
    
    // ========== Görsel ve Sesli Uyarı Fonksiyonları ==========
    
    private fun initializeTextToSpeech() {
        textToSpeech = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val isTurkish = resources.configuration.locales[0]?.language?.startsWith("tr", ignoreCase = true) ?: true
                val locale = if (isTurkish) Locale("tr", "TR") else Locale.US
                val result = textToSpeech?.setLanguage(locale)
                if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    // Dil desteği yoksa varsayılan dili kullan
                    textToSpeech?.setLanguage(Locale.getDefault())
                }
            }
        }
    }
    
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val name = "Alerjen Uyarıları"
            val descriptionText = "Alerjen tespit edildiğinde bildirim gösterir"
            val importance = NotificationManager.IMPORTANCE_HIGH
            val channel = NotificationChannel(CHANNEL_ID, name, importance).apply {
                description = descriptionText
                enableLights(true)
                lightColor = Color.RED
                enableVibration(true)
            }
            val notificationManager: NotificationManager =
                getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }
    
    private fun showAllergenNotification(allergens: List<String>, warnings: List<String>) {
        val isTurkish = resources.configuration.locales[0]?.language?.startsWith("tr", ignoreCase = true) ?: true
        
        val title = if (isTurkish) "⚠️ Alerjen Tespit Edildi!" else "⚠️ Allergen Detected!"
        val contentText = if (allergens.isNotEmpty()) {
            if (isTurkish) {
                "Tespit edilen alerjenler: ${allergens.joinToString(", ")}"
            } else {
                "Detected allergens: ${allergens.joinToString(", ")}"
            }
        } else if (warnings.isNotEmpty()) {
            warnings.firstOrNull() ?: (if (isTurkish) "Uyarı!" else "Warning!")
        } else {
            if (isTurkish) "Dikkat: Ürün analizi tamamlandı" else "Attention: Product analysis completed"
        }
        
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        val pendingIntent: PendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(contentText)
            .setStyle(NotificationCompat.BigTextStyle().bigText(contentText))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setColor(ContextCompat.getColor(this, android.R.color.holo_red_dark))
            .build()
        
        val notificationManager = ContextCompat.getSystemService(this, NotificationManager::class.java)
        notificationManager?.notify(NOTIFICATION_ID, notification)
    }
    
    private fun speakAllergenWarning(allergens: List<String>, warnings: List<String>) {
        val isTurkish = resources.configuration.locales[0]?.language?.startsWith("tr", ignoreCase = true) ?: true
        
        val message = if (allergens.isNotEmpty()) {
            if (isTurkish) {
                "Dikkat! Tespit edilen alerjenler: ${allergens.joinToString(", ")}"
            } else {
                "Warning! Detected allergens: ${allergens.joinToString(", ")}"
            }
        } else if (warnings.isNotEmpty()) {
            warnings.firstOrNull() ?: (if (isTurkish) "Uyarı!" else "Warning!")
        } else {
            return // Konuşacak bir şey yok
        }
        
        textToSpeech?.speak(message, TextToSpeech.QUEUE_FLUSH, null, null)
    }
    
    private fun applyAllergenVisualWarning(hasAllergens: Boolean, hasWarnings: Boolean) {
        // Uyarı kartına renk kodlaması ekle
        if (hasAllergens || hasWarnings) {
            // Uyarı rengi (colors.xml'den)
            val warningColor = ContextCompat.getColor(this, com.tezproje.R.color.warning_bg)
            binding.warningsCard.setCardBackgroundColor(warningColor)
            // Alerjen chip'lerine kırmızı renk ekle
            for (i in 0 until binding.allergenChipGroup.childCount) {
                val chip = binding.allergenChipGroup.getChildAt(i) as? Chip
                chip?.setChipBackgroundColorResource(android.R.color.holo_red_light)
                chip?.setTextColor(Color.WHITE)
            }
        } else {
            // Normal renk (beyaz veya varsayılan tema rengi)
            val surfaceColor = ContextCompat.getColor(this, com.tezproje.R.color.app_surface)
            binding.warningsCard.setCardBackgroundColor(surfaceColor)
        }
    }
    
    private fun addToDailyConsumption() {
        val response = lastResponse ?: return
        val nutrition = response.nutrition
        
        if (nutrition.calories_kcal == null || nutrition.calories_kcal!! <= 0) {
            binding.statusText.text = "Kalori bilgisi bulunamadı."
            return
        }
        
        val authRepo = AuthRepository(this)
        val token = authRepo.getAccessToken()
        
        if (token.isNullOrBlank()) {
            binding.statusText.text = "Giriş yapmanız gerekiyor."
            return
        }
        
        binding.statusText.text = "Günlük takibe ekleniyor..."
        binding.addToDailyConsumptionButton.isEnabled = false
        
        lifecycleScope.launch {
            try {
                val authorization = "Bearer $token"
                val nutritionFacts = NutritionFacts(
                    calories_kcal = nutrition.calories_kcal,
                    fat_g = nutrition.fat_g,
                    carbs_g = nutrition.carbs_g,
                    protein_g = nutrition.protein_g,
                    sugar_g = nutrition.sugar_g,
                    salt_g = nutrition.salt_g,
                    sodium_mg = nutrition.sodium_mg
                )
                
                val result = withContext(Dispatchers.IO) {
                    ApiClient.api.addConsumption(
                        authorization = authorization,
                        nutrition = nutritionFacts,
                        consumptionDate = null // Bugün için
                    )
                }
                
                val isTurkish = resources.configuration.locales[0]?.language?.startsWith("tr", ignoreCase = true) ?: true
                val message = if (isTurkish) {
                    "Günlük takibe eklendi! Toplam: ${String.format(Locale.getDefault(), "%.1f", result.nutrition.calories_kcal ?: 0.0)} kcal"
                } else {
                    "Added to daily tracking! Total: ${String.format(Locale.getDefault(), "%.1f", result.nutrition.calories_kcal ?: 0.0)} kcal"
                }
                
                if (result.warnings.isNotEmpty()) {
                    binding.statusText.text = "$message\n⚠️ ${result.warnings.joinToString("\n")}"
                } else {
                    binding.statusText.text = message
                }
                
                binding.addToDailyConsumptionButton.isEnabled = true
            } catch (e: Exception) {
                val isTurkish = resources.configuration.locales[0]?.language?.startsWith("tr", ignoreCase = true) ?: true
                binding.statusText.text = if (isTurkish) {
                    "Günlük takibe eklenirken hata oluştu: ${e.message}"
                } else {
                    "Error adding to daily tracking: ${e.message}"
                }
                binding.addToDailyConsumptionButton.isEnabled = true
            }
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        textToSpeech?.stop()
        textToSpeech?.shutdown()
    }
}


