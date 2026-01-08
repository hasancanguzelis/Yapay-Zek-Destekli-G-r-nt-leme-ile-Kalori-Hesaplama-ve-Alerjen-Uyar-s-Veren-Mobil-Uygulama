# Android (Kotlin) — MVVM + Retrofit + CameraX

Bu klasörde Android Studio ile açılabilecek bir **MVVM + Retrofit + CameraX** örnek uygulama vardır:
- Proje yolu: `mobile/android`
- Ana ekran: CameraX preview → “Fotoğraf Çek ve Analiz Et” → sonuç metni

## Çalıştırma
1. Backend’i çalıştırın: `http://localhost:8000`
2. Android Studio’da `mobile/android` klasörünü açın ve Sync edin.

## Gradle Hatası: "SDK location not found"
Eğer terminalde şunu görürseniz:
- `SDK location not found. Define a valid SDK location ... local.properties`

Çözüm:
1. Android Studio → **Tools → SDK Manager** bölümünden Android SDK’yı kurun ve **SDK Path** değerini kopyalayın.
2. `mobile/android/local.properties` dosyasını oluşturun (repo’ya commit etmeyin; zaten `.gitignore` içinde):

Örnek (Windows, PowerShell) — **sdk.dir değerini Android Studio → SDK Manager’daki "Android SDK Location" ile aynı yapın**:
```bash
cd mobile/android
@"
sdk.dir=C:/PATH/TO/Android/Sdk
"@ | Set-Content -Encoding ASCII .\\local.properties
```

Sonra tekrar deneyin:
```bash
cd mobile/android
.\gradlew.bat :app:assembleDebug
```

## Base URL (çok önemli)
Varsayılan olarak emulator için ayarlı:
- `mobile/android/app/build.gradle.kts` içinde:
  - `API_BASE_URL = "http://10.0.2.2:8000/"`

Fiziksel cihazda test edecekseniz PC’nizin IP’sini verin (aynı Wi‑Fi):
- Örn: `http://192.168.1.10:8000/`

## Backend Endpoint
- `POST /analyze` (multipart)
  - `image` (dosya)
  - `lang` (opsiyonel): `tur` / `eng`
  - `barcode` (opsiyonel): barkod numarası (Open Food Facts zenginleştirme için)
  - `user_profile_json` (opsiyonel): JSON string

- `POST /product/by_barcode` (form)
  - `barcode` (zorunlu)
  - `user_profile_json` (opsiyonel)

- `POST /meal/analyze` (multipart)
  - `image` (dosya)
  - `dish_name` (opsiyonel)
  - `ingredients_csv` (opsiyonel, virgülle)
  - `user_profile_json` (opsiyonel)

Örnek profil:
```json
{"allergens":["gluten","fıstık"],"conditions":["diyabet"]}
```

## Kodda Nerede?
- **UI + CameraX**: `mobile/android/app/src/main/java/com/tezproje/ui/MainActivity.kt`
- **MVVM**: `MainViewModel.kt` + `UiState.kt`
- **Profil (MVVM)**: `ui/profile/ProfileActivity.kt` + `ProfileViewModel.kt` + `ProfileRepository.kt`
- **Retrofit**: `network/TezApiService.kt` + `network/ApiClient.kt`
- **Repository**: `data/TezRepository.kt`

## Yeni Özellikler
- **Barkod desteği**: UI’dan barkod girilirse backend’e gönderilir, Open Food Facts ile zenginleştirme yapılabilir.
- **Canlı barkod tarama**: Paketli ürün modunda CameraX canlı akışında ML Kit ile barkod okunup otomatik doldurulur.
- **Barkod-only arama**: Etiket fotoğrafı çekmeden sadece barkod ile ürün bilgisi çekilebilir.
- **Cache**: Son analiz sonucu cihazda saklanır ve uygulama açıldığında otomatik yüklenir.
- **Paylaşım**: Sonuç **JSON** veya **PDF** olarak paylaşılabilir.
- **Profil ekranı**: Alerjenler ve rahatsızlıklar kaydedilir; analizde otomatik olarak `user_profile_json` içine eklenir.
- **Tabaklı yemek modu**: Fotoğraf çekilip ML Kit ile yemek adı için otomatik tahmin yapılır; istenirse manuel düzenlenir ve backend’de USDA üzerinden yaklaşık besin hesabı yapılır (USDA_API_KEY gerekir).

## Cleartext HTTP Notu
Dev aşamasında `http://` için izin açık:
- `AndroidManifest.xml`: `android:usesCleartextTraffic="true"`
- `res/xml/network_security_config.xml`

Prod’da mutlaka **HTTPS** kullanın.


