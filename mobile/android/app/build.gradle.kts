plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("kotlin-kapt")
}

android {
    namespace = "com.tezproje"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.tezproje"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        // Backend (dev) URL — emulator için varsayılan.
        // Fiziksel cihazda PC IP'nize göre değiştirin: "http://192.168.1.10:8000/"
        buildConfigField("String", "API_BASE_URL", "\"http://10.0.2.2:8000/\"")
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")

    // MVVM
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Retrofit + OkHttp
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.google.code.gson:gson:2.10.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // CameraX
    implementation("androidx.camera:camera-core:1.3.2")
    implementation("androidx.camera:camera-camera2:1.3.2")
    implementation("androidx.camera:camera-lifecycle:1.3.2")
    implementation("androidx.camera:camera-view:1.3.2")

    // ML Kit (on-device)
    implementation("com.google.mlkit:barcode-scanning:17.2.0")
    implementation("com.google.mlkit:image-labeling:17.0.8")
    
    // Image loading (Coil)
    implementation("io.coil-kt:coil:2.5.0")
    
    // Chart library (MPAndroidChart)
    implementation("com.github.PhilJay:MPAndroidChart:v3.1.0")
    
    // Notification support
    implementation("androidx.core:core-ktx:1.12.0")
    
    // WorkManager for notifications (optional, for scheduled notifications)
    implementation("androidx.work:work-runtime-ktx:2.9.0")
    
    // Room Database
    val roomVersion = "2.6.1"
    implementation("androidx.room:room-runtime:$roomVersion")
    implementation("androidx.room:room-ktx:$roomVersion")
    kapt("androidx.room:room-compiler:$roomVersion")
}


