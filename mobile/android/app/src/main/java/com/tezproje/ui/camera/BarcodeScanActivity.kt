package com.tezproje.ui.camera

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.Surface
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.AspectRatio
import androidx.camera.core.CameraSelector
import androidx.camera.core.CameraState
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import com.tezproje.data.SettingsRepository
import com.tezproje.databinding.ActivityBarcodeScanBinding

class BarcodeScanActivity : AppCompatActivity() {
    companion object {
        const val EXTRA_BARCODE = "extra_barcode"
    }

    private lateinit var binding: ActivityBarcodeScanBinding
    private var cameraProvider: ProcessCameraProvider? = null
    private var imageAnalysis: ImageAnalysis? = null
    private var processingFrame: Boolean = false
    private var showedEmulatorHint: Boolean = false
    private var activeSelector: CameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

    private val barcodeScanner = BarcodeScanning.getClient()

    private val requestCameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera() else {
            binding.statusText.text = "Kamera izni verilmedi."
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsRepository(applicationContext).applyToApp()

        binding = ActivityBarcodeScanBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.cancelButton.setOnClickListener {
            setResult(RESULT_CANCELED)
            finish()
        }
        binding.switchCameraButton.setOnClickListener { toggleCamera() }

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

                if (isProbablyEmulator()) {
                    binding.previewView.implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                }

                val rotation = binding.previewView.display?.rotation ?: Surface.ROTATION_0

                val preview = Preview.Builder()
                    .setTargetAspectRatio(AspectRatio.RATIO_16_9)
                    .setTargetRotation(rotation)
                    .build().also {
                    it.setSurfaceProvider(binding.previewView.surfaceProvider)
                }

                imageAnalysis = ImageAnalysis.Builder()
                    .setTargetAspectRatio(AspectRatio.RATIO_16_9)
                    .setTargetRotation(rotation)
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also { analysis ->
                        analysis.setAnalyzer(ContextCompat.getMainExecutor(this)) { imageProxy ->
                            analyzeFrame(imageProxy)
                        }
                    }

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
                        val cam = provider.bindToLifecycle(this, selector, preview, imageAnalysis)
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
                    // statusText, cameraState ile güncellenir
                } else {
                    binding.statusText.text =
                        "Kamera başlatılamadı. Emülatörde Camera ayarını kontrol edin (Back/Front Camera). " +
                            (lastError?.message?.let { "Detay: $it" } ?: "")
                }
            } catch (e: Exception) {
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
            imageAnalysis?.clearAnalyzer()
        } catch (_: Exception) {
        }
        try {
            cameraProvider?.unbindAll()
        } catch (_: Exception) {
        }
        imageAnalysis = null
        processingFrame = false
    }

    private fun analyzeFrame(imageProxy: ImageProxy) {
        if (processingFrame) {
            imageProxy.close()
            return
        }
        val mediaImage = imageProxy.image
        if (mediaImage == null) {
            imageProxy.close()
            return
        }

        processingFrame = true
        val inputImage = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
        barcodeScanner.process(inputImage)
            .addOnSuccessListener { barcodes ->
                val first = barcodes.firstOrNull { !it.rawValue.isNullOrBlank() }?.rawValue
                if (!first.isNullOrBlank()) {
                    val data = Intent().putExtra(EXTRA_BARCODE, first)
                    setResult(RESULT_OK, data)
                    finish()
                }
            }
            .addOnFailureListener { e ->
                binding.statusText.text = "Barkod tarama hatası: ${e.message}"
            }
            .addOnCompleteListener {
                processingFrame = false
                imageProxy.close()
            }
    }
}


