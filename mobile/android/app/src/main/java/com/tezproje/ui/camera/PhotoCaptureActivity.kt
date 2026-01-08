package com.tezproje.ui.camera

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Size
import android.view.Surface
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.AspectRatio
import androidx.camera.core.CameraSelector
import androidx.camera.core.CameraState
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.tezproje.data.SettingsRepository
import com.tezproje.databinding.ActivityPhotoCaptureBinding
import java.io.FileOutputStream
import java.io.File
import java.text.SimpleDateFormat
import java.util.Locale

class PhotoCaptureActivity : AppCompatActivity() {
    companion object {
        const val EXTRA_PHOTO_PATH = "extra_photo_path"
    }

    private lateinit var binding: ActivityPhotoCaptureBinding
    private var imageCapture: ImageCapture? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var cameraReady: Boolean = false
    private var showedEmulatorHint: Boolean = false
    private var activeSelector: CameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

    private val requestCameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera() else {
            binding.statusText.text = "Kamera izni verilmedi."
            binding.captureButton.isEnabled = false
        }
    }

    private val pickFromGallery = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri ->
        if (uri == null) return@registerForActivityResult
        try {
            contentResolver.openInputStream(uri)?.use { input ->
                val outFile = createTempJpeg(prefix = "gallery_")
                FileOutputStream(outFile).use { output ->
                    input.copyTo(output)
                }
                val data = Intent().putExtra(EXTRA_PHOTO_PATH, outFile.absolutePath)
                setResult(RESULT_OK, data)
                finish()
            } ?: run {
                binding.statusText.text = "Görsel okunamadı."
            }
        } catch (e: Exception) {
            binding.statusText.text = "Görsel seçilemedi: ${e.message}"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsRepository(applicationContext).applyToApp()

        binding = ActivityPhotoCaptureBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.captureButton.isEnabled = false
        binding.cancelButton.setOnClickListener {
            setResult(RESULT_CANCELED)
            finish()
        }
        binding.captureButton.setOnClickListener { takePhoto() }
        binding.switchCameraButton.setOnClickListener { toggleCamera() }
        binding.galleryButton.setOnClickListener { pickFromGallery.launch("image/*") }

        ensureCameraPermissionAndStart()
    }

    override fun onStop() {
        super.onStop()
        stopCamera()
    }

    private fun ensureCameraPermissionAndStart() {
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED

        if (granted) startCamera() else requestCameraPermission.launch(Manifest.permission.CAMERA)
    }

    private fun startCamera() {
        binding.statusText.text = if (!showedEmulatorHint && isProbablyEmulator()) {
            showedEmulatorHint = true
            "Kamera hazırlanıyor...\nEmülatörde: (…) > Camera > Back/Front Camera = Webcam0 seç.\nWindows: Kamera izinlerini kontrol et."
        } else {
            "Kamera hazırlanıyor..."
        }
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            try {
                val provider = cameraProviderFuture.get()
                cameraProvider = provider
                cameraReady = false

                // Emülatörde PreviewView uyumluluk modu daha stabil.
                if (isProbablyEmulator()) {
                    binding.previewView.implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                }

                val rotation = binding.previewView.display?.rotation ?: Surface.ROTATION_0

                val preview = Preview.Builder()
                    .setTargetRotation(rotation)
                    // Daha yüksek preview çözünürlüğü: emülatör/webcam'de daha okunabilir görüntü.
                    .setTargetResolution(Size(1920, 1080))
                    .build().also {
                    it.setSurfaceProvider(binding.previewView.surfaceProvider)
                }

                imageCapture = ImageCapture.Builder()
                    .setTargetRotation(rotation)
                    // OCR için kalite önemli; gecikme pahasına maksimum kalite.
                    .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                    // Daha yüksek hedef çözünürlük: tesseract için daha fazla detay.
                    .setTargetResolution(Size(1920, 1080))
                    // JPEG sıkıştırmasını düşür (daha net metin).
                    .setJpegQuality(95)
                    .build()

                val selectors = listOf(
                    activeSelector,
                    if (activeSelector == CameraSelector.DEFAULT_BACK_CAMERA) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
                )

                var bound = false
                var lastError: Exception? = null
                for (selector in selectors) {
                    try {
                        val hasCamera = try { provider.hasCamera(selector) } catch (_: Exception) { true }
                        if (!hasCamera) continue
                        provider.unbindAll()
                        val cam = provider.bindToLifecycle(this, selector, preview, imageCapture)
                        val camLabel = if (selector == CameraSelector.DEFAULT_FRONT_CAMERA) "Ön" else "Arka"
                        cam.cameraInfo.cameraState.observe(this) { st ->
                            if (st.type == CameraState.Type.OPEN) {
                                binding.statusText.text = "Hazır ($camLabel)"
                            } else if (st.type == CameraState.Type.CLOSED && st.error != null) {
                                binding.statusText.text =
                                    "Kamera hatası: ${st.error?.code}\nEmülatör Camera ayarını kontrol edin (Webcam0)."
                            }
                        }
                        bound = true
                        break
                    } catch (e: Exception) {
                        lastError = e
                    }
                }

                if (bound) {
                    cameraReady = true
                    binding.captureButton.isEnabled = true
                } else {
                    cameraReady = false
                    binding.captureButton.isEnabled = false
                    binding.statusText.text =
                        "Kamera başlatılamadı. Emülatörde Camera ayarını kontrol edin (Back/Front Camera). " +
                            (lastError?.message?.let { "Detay: $it" } ?: "")
                }
            } catch (e: Exception) {
                cameraReady = false
                binding.captureButton.isEnabled = false
                binding.statusText.text = "Kamera başlatılamadı: ${e.message}"
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun toggleCamera() {
        activeSelector = if (activeSelector == CameraSelector.DEFAULT_BACK_CAMERA) {
            CameraSelector.DEFAULT_FRONT_CAMERA
        } else {
            CameraSelector.DEFAULT_BACK_CAMERA
        }
        // Rebind
        startCamera()
    }

    private fun isProbablyEmulator(): Boolean {
        return (Build.FINGERPRINT.startsWith("generic")
            || Build.FINGERPRINT.lowercase().contains("emulator")
            || Build.MODEL.contains("Emulator")
            || Build.MODEL.contains("Android SDK built for")
            || Build.MANUFACTURER.lowercase().contains("genymotion")
            || (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic"))
            || Build.PRODUCT.lowercase().contains("sdk_gphone"))
    }

    private fun stopCamera() {
        try {
            cameraProvider?.unbindAll()
        } catch (_: Exception) {
        }
        imageCapture = null
        cameraReady = false
    }

    private fun takePhoto() {
        val capture = imageCapture
        if (!cameraReady || capture == null) {
            binding.statusText.text = "Kamera hazır değil."
            return
        }

        binding.progress.visibility = android.view.View.VISIBLE
        binding.captureButton.isEnabled = false

        val file = createTempJpeg()
        val output = ImageCapture.OutputFileOptions.Builder(file).build()
        capture.takePicture(
            output,
            ContextCompat.getMainExecutor(this),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                    val data = Intent().putExtra(EXTRA_PHOTO_PATH, file.absolutePath)
                    setResult(RESULT_OK, data)
                    finish()
                }

                override fun onError(exception: ImageCaptureException) {
                    binding.progress.visibility = android.view.View.GONE
                    binding.captureButton.isEnabled = true
                    binding.statusText.text = "Fotoğraf çekilemedi: ${exception.message}"
                }
            }
        )
    }

    private fun createTempJpeg(prefix: String = "capture_"): File {
        val time = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(System.currentTimeMillis())
        return File(cacheDir, "${prefix}${time}.jpg")
    }
}


