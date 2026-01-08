# Tez-Proje — Paketli Gıda Etiketi Analizi (OCR + NLP + Alerjen Uyarı + Kalori Takibi)

Bu repo, paketli gıda ürünlerinin etiket fotoğrafından **besin değerleri** ve **içerik/alergen** bilgisini çıkarıp, kullanıcı sağlık profiline göre **kişiselleştirilmiş uyarılar** üreten ve **günlük kalori takibi** yapan bir sistemdir.

## Mimari
- **Mobil (Android/Kotlin)**: Kamera ile fotoğraf çekme → backend'e gönderme → uyarıları gösterme
  - Veri Depolama: **Room Database (SQLite wrapper)** - Kullanıcı profili ve analiz sonuçları için
  - Veri Depolama: SharedPreferences - Basit ayarlar ve authentication token'ları için
  - MVVM mimarisi ile geliştirilmiştir
  - **Görsel Uyarılar**: Alerjen tespit edildiğinde renk kodlaması (kırmızı uyarı kartı)
  - **Sesli Uyarılar**: Text-to-Speech (TTS) ile alerjen uyarıları
  - **Bildirimler**: Android Notification sistemini kullanarak alerjen uyarıları
- **Backend (Python/FastAPI)**: Görüntü ön işleme (OpenCV) → OCR (Tesseract) → NLP ayrıştırma (regex + SpaCy lemmatization) → alerjen eşleştirme → (opsiyonel) ürün veri tabanı doğrulama → günlük kalori takibi
  - Veritabanı: SQLite (SQLAlchemy ORM ile)
- **Harici Veri Kaynakları**: Open Food Facts API / USDA FoodData Central API

## Hızlı Başlangıç (Backend)
> Not: OCR için sistemde **Tesseract OCR** yüklü olmalı.

### Ön Koşullar (Windows)
- **Python 3.11+** kurulu olmalı ve PATH’e ekli olmalı.
  - Kontrol: `python --version`
- **Tesseract OCR** kurulu olmalı.
  - Windows’ta en yaygın hata: Tesseract kurulu değil / yolu bulunamıyor.
  - Gerekirse `TESSERACT_CMD` ile yolu belirtin.
  - Hızlı kurulum (PowerShell):

```bash
winget install --id UB-Mannheim.TesseractOCR -e
```

  - Kurulumdan sonra genelde yol şudur: `C:\Program Files\Tesseract-OCR\tesseract.exe`

### 1) Kurulum
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 1.1) SpaCy Modellerini İndir (NLP Lemmatization için)
Lemmatization özelliğini kullanmak için SpaCy modellerini indirmeniz gerekir:

```bash
# Türkçe model
python -m spacy download tr_core_news_sm

# İngilizce model (opsiyonel, ancak önerilir)
python -m spacy download en_core_web_sm
```

**Not**: Modeller indirilmezse sistem otomatik olarak regex tabanlı fallback kullanır (işlevsellik devam eder).

### 2) Çalıştırma
```bash
# Seçenek A (önerilen): backend klasörünün içinden
cd backend
py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Seçenek B: repo kökünden
# cd <repo-root>
# py -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3) API Dokümantasyonu
- Swagger UI: `http://localhost:8000/docs`

## Ortam Değişkenleri (Opsiyonel)
Örnek değerler için `backend/env.example` dosyasına bakın. Windows PowerShell örneği:

```bash
$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:TESSERACT_LANG="tur"   # Türkçe dil paketi kurulu olmalı
$env:USDA_API_KEY="YOUR_KEY"
```

## Prod Önerileri (Backend)
Prod’da hedef: **CORS allowlist**, **HTTPS**, daha sıkı timeout/retry.

Örnek (PowerShell):

```bash
$env:APP_ENV="prod"
$env:CORS_ALLOW_ORIGINS="https://tezproje.example.com"
$env:CORS_ALLOW_CREDENTIALS="false"
$env:HTTP_TIMEOUT_S="10"
$env:HTTP_RETRIES="1"
$env:HTTP_RETRY_BACKOFF_S="0.25"
```

Notlar:
- `CORS_ALLOW_ORIGINS="*"` + `CORS_ALLOW_CREDENTIALS=true` prod benzeri ortamda **engellenir** (güvenlik).
- `/product/by_barcode` (Open Food Facts) ve `/meal/analyze` (USDA) dış servis çağırdığı için timeout/retry değerleri prod’da daha konservatif tutulmalıdır.

## Android Entegrasyonu
Android örneği ve önerilen akış için: `mobile/README.md`

## Model Eğitimi İçin Veri Toplama (Dataset)
Backend içinde, Open Food Facts (OFF) ve opsiyonel USDA’dan veri toplayıp **JSONL/CSV** olarak kaydeden bir script var:

- Script: `backend/scripts/collect_food_data.py`
- Varsayılan çıktı: `backend/data/food_dataset.jsonl`

### Alerjen Sınıflandırma İçin Önerilen Ayar
- **Input**: `ingredients_text`
- **Label (multi-label)**: `label_allergens` (OFF alerjen tag’lerinden kanonikleştirilmiş sınıflar)

```bash
py backend\scripts\collect_food_data.py --source off --label-source off --require-ingredients --overwrite --csv-out backend\data\allergen_dataset.csv
```

## Alerjen Sınıflandırma Modeli (Baseline Eğitim)
Basit ama etkili bir başlangıç için `TF-IDF (char ngram) + LogisticRegression (One-vs-Rest)` baseline eğitim scripti:

### 1) ML bağımlılıklarını kur
```bash
cd backend
pip install -r requirements-ml.txt
```

### 2) Eğit + değerlendir + modeli kaydet
```bash
# repo kökünden:
py backend\scripts\train_allergen_classifier.py --data backend\data\food_dataset.jsonl --require-text --require-labels --min-label-freq 5 --tune-thresholds --text-mode both --out-model backend\models\allergen_clf.joblib
```

### 3) Hızlı tahmin denemesi
```bash
py backend\scripts\train_allergen_classifier.py --out-model backend\models\allergen_clf.joblib --predict "İçindekiler: buğday unu, süt tozu, soya lesitini"
```

## API: Alerjen Tahmini Endpoint’i
Eğittiğin modeli backend’e koyduktan sonra mobil uygulama şu endpoint’i çağırabilir:

- Endpoint: `POST /predict/allergens`
- Body: `{ "text": "...", "top_k": 10 }`

### Örnek (PowerShell)
```bash
# Not: PowerShell'de "curl" komutu çoğu zaman Invoke-WebRequest alias'ıdır.
# Bu yüzden aşağıdaki iki seçenekten birini kullanın.

# Seçenek A (önerilen): Invoke-RestMethod
$body = @{ text = "İçindekiler: buğday unu, süt tozu, soya lesitini"; top_k = 10 } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/predict/allergens" -ContentType "application/json; charset=utf-8" -Body $body

# Seçenek B: Gerçek curl (curl.exe)
curl.exe -X POST "http://localhost:8000/predict/allergens" -H "Content-Type: application/json" -d "{\"text\":\"İçindekiler: buğday unu, süt tozu, soya lesitini\",\"top_k\":10}"
```

Notlar:
- Model dosyası varsayılan olarak `backend/models/allergen_clf.joblib` beklenir.
- Farklı konum için `backend/.env` içine `ALLERGEN_MODEL_PATH=...` yazabilirsin.

### Not: Nadir Alerjenler (egg/peanut) İçin
Eğer raporda bazı sınıflarda **support çok düşükse** (örn: `egg`, `peanut`), model o sınıfları öğrenemez.
- Daha stabil eğitim için `--min-label-freq 5` (veya 10) kullanıp nadir sınıfları şimdilik dışarıda bırakabilirsin.
- Ya da hedefli veri topla (sayfayı artır):

```bash
py backend\scripts\collect_food_data.py --source off --label-source off --queries "yumurta,egg,mayonez,peanut,yer fıstığı,fıstık ezmesi" --off-pages 10 --off-page-size 50 --require-ingredients --overwrite --csv-out backend\data\allergen_dataset_more.csv
```

### Hızlı Çalıştırma (Windows / PowerShell)
> Not: OFF için API key gerekmez. USDA için `USDA_API_KEY` gerekir.

```bash
# Repo kökünden (Windows'ta genelde "py" launcher daha sorunsuzdur):
py backend\scripts\collect_food_data.py --source off --overwrite --csv-out backend\data\food_dataset.csv --require-ingredients

# Alternatif (python PATH'te ise):
# python backend\scripts\collect_food_data.py --source off --overwrite --csv-out backend\data\food_dataset.csv --require-ingredients
```

### Özel Arama Terimleriyle Toplama
```bash
py backend\scripts\collect_food_data.py --source off --queries "süt,çikolata,bisküvi,ton balığı" --off-pages 5 --off-page-size 50 --polite-delay-s 0.25
```

### OFF + USDA (USDA_API_KEY gerekli)
```bash
$env:USDA_API_KEY="YOUR_KEY"
py backend\scripts\collect_food_data.py --source both --queries "pizza,burger,kebap" --overwrite
```

### Çıktı Formatı
- **JSONL**: Her satır 1 JSON obje olacak şekilde; model eğitimi için pratik (stream/append edilebilir).
- Alanlar (özet): `product_name`, `ingredients_text`, `label_allergens`, `allergens_off_canon`, `allergens_rule`, `nutriments`, `source`, `query`, `barcode`


## Tabaklı Yemek Kalori Modeli (İsim + Porsiyon)

- **Fotoğraf → yemek adı**: Android tarafında **ML Kit** ile önerilir (model eğitimi gerektirmez).
- **Kalori/besin tahmini**: Backend’de **`POST /meal/predict`** ile yapılır.
  - Model yoksa backend otomatik olarak **`/meal/estimate` (USDA ortalaması)** fallback yapar.

### Dataset toplama (USDA)

```bash
py backend\\scripts\\collect_meal_calorie_data.py --queries "kuru fasulye,pilav,köfte,mercimek çorbası" --out backend\\data\\meal_calorie.jsonl --overwrite
```

### Model eğitimi (scikit-learn)

```bash
py -m pip install -r backend\\requirements-ml.txt
py backend\\scripts\\train_meal_calorie_model.py --data backend\\data\\meal_calorie.jsonl --out-model backend\\models\\meal_calorie_model.joblib
```

### Opsiyonel: Model yolu

`backend/.env` içine:

```bash
MEAL_CALORIE_MODEL_PATH=backend/models/meal_calorie_model.joblib
```

## Günlük Kalori Takibi

Proje, kullanıcının yaş, kilo, boy, cinsiyet ve aktivite seviyesine göre **BMR (Basal Metabolic Rate)** ve **TDEE (Total Daily Energy Expenditure)** hesaplayarak günlük kalori takibi yapar.

### Mobil Uygulamada Günlük Kalori Takibi

Mobil uygulamada günlük kalori takibi şu özelliklere sahiptir:

1. **Profil Ekranı - Kalori Takibi Bölümü**:
   - Yaş, kilo, boy, cinsiyet ve aktivite seviyesi girişi
   - Hedef kalori gösterimi (BMR ve TDEE bilgileri ile)
   - Bugünkü tüketim bilgisi
   - Progress bar ile hedef/kalan kalori gösterimi
   - **Pasta grafiği (PieChart)** ile günlük makro besin dağılımı (yağ, karbonhidrat, protein)
   - Uyarılar (hedef aşıldığında)

2. **Analiz Sonuçlarından Ekleme**:
   - Analiz sonucunda besin değerleri gösterildiğinde "Günlük Takibe Ekle" butonu görünür
   - Butona tıklandığında analiz sonucundaki kalori ve makro besinler günlük takibe eklenir
   - Başarı mesajı ve uyarılar (hedef aşıldıysa) gösterilir

3. **Görselleştirme**:
   - Günlük tüketilen makro besinler pasta grafiği ile gösterilir
   - Renk kodlaması:
     - Kırmızı: Yağ
     - Turkuaz: Karbonhidrat
     - Açık Yeşil: Protein
   - Grafik animasyonlu olarak gösterilir

### Kullanıcı Profili Güncelleme

Kullanıcı profiline fiziksel özellikler eklemek için `PUT /profile` endpoint'i kullanılabilir:

```json
{
  "allergens": ["gluten", "milk"],
  "conditions": ["diabetes"],
  "age": 30,
  "weight_kg": 75.0,
  "height_cm": 175.0,
  "gender": "male",
  "activity_level": "moderate"
}
```

**Aktivite Seviyeleri:**
- `sedentary`: Hareketsiz (az hareket, masa başı iş)
- `light`: Hafif aktif (hafif egzersiz, 1-3 gün/hafta)
- `moderate`: Orta aktif (orta egzersiz, 3-5 gün/hafta)
- `active`: Çok aktif (ağır egzersiz, 6-7 gün/hafta)
- `very_active`: Ekstra aktif (çok ağır egzersiz, fiziksel iş)

### Kalori Hedefi Hesaplama

```bash
# GET /calorie/target?goal=maintain
# goal: "lose" (kilo verme), "maintain" (koruma), "gain" (kilo alma)
```

### Günlük Tüketim Takibi

- `POST /consumption/add`: Günlük tüketime besin değerleri ekle (toplar)
- `GET /consumption/today`: Bugünkü toplam tüketimi getir
- `GET /consumption/{YYYY-MM-DD}`: Belirli bir tarihteki tüketimi getir
- `DELETE /consumption/{YYYY-MM-DD}`: Belirli bir tarihteki tüketimi sil

**Örnek (PowerShell):**
```bash
$token = "YOUR_JWT_TOKEN"
$headers = @{ Authorization = "Bearer $token" }
$body = @{
    calories_kcal = 500.0
    fat_g = 20.0
    carbs_g = 60.0
    protein_g = 25.0
} | ConvertTo-Json

Invoke-RestMethod -Method POST -Uri "http://localhost:8000/consumption/add" -Headers $headers -ContentType "application/json" -Body $body
```

Sistem otomatik olarak:
- Kullanıcının hedef kalorisini kontrol eder
- Maksimum sınırı aşıp aşmadığını kontrol eder
- Gerekirse uyarılar döner

## Teknoloji Notları

### NLP İmplementasyonu
- **Mevcut Durum**: Regex tabanlı keyword matching ve pattern matching + **Lemmatization** kullanılıyor
- **Lemmatization**: ✅ SpaCy ile uygulanmıştır
  - Türkçe model: `tr_core_news_sm` (kurulum: `python -m spacy download tr_core_news_sm`)
  - İngilizce model: `en_core_web_sm` (kurulum: `python -m spacy download en_core_web_sm`)
  - Model yoksa otomatik olarak regex tabanlı fallback kullanılır
  - `extract_ingredients()`, `parse_nutrition_facts()`, `detect_allergens()` fonksiyonları lemmatization kullanıyor
- NLP modülü (`backend/app/nlp.py`): Besin değerleri çıkarma ve içerik ayrıştırma için regex + lemmatization kullanır

### Model Eğitimi
- **Mevcut Durum**: Python scriptler ile yapılıyor (`backend/scripts/train_*.py`)
- **Jupyter Notebook**: Kullanılmıyor (Python scriptler tercih edilmiştir)

### Mobil Veri Depolama
- **Mevcut Durum**: ✅ **Room Database (SQLite wrapper)** kullanılıyor
  - Kullanıcı profil verileri için `ProfileEntity` (alerjenler, rahatsızlıklar, yaş, kilo, boy, cinsiyet, aktivite seviyesi)
  - Analiz sonuçları için `AnalysisResultEntity` (offline cache)
  - Room Database: `TezDatabase` sınıfı
  - Room DAO'lar: `ProfileDao`, `AnalysisResultDao`
- **SharedPreferences**: Sadece basit ayarlar için kullanılıyor (SettingsRepository, AuthRepository'de token'lar için)

### Mobil Uygulama Özellikleri

#### Profil Yönetimi
- Kullanıcı profilinde alerjen ve rahatsızlık seçimi (chip-based UI)
- **Kalori takibi için fiziksel özellikler**:
  - Yaş (number input)
  - Kilo (kg) - decimal input
  - Boy (cm) - decimal input
  - Cinsiyet (dropdown: Erkek, Kadın, Diğer)
  - Aktivite seviyesi (dropdown: Hareketsiz, Hafif, Orta, Aktif, Çok Aktif)
- Profil kaydetme ve otomatik güncelleme
- Günlük kalori takibi kartı (scroll edilebilir)

#### Analiz ve Uyarılar
- Paketli ürün analizi (OCR + barkod)
- Tabaklı yemek analizi (metin veya görüntü)
- **Görsel uyarılar**: Alerjen tespit edildiğinde uyarı kartı kırmızı renkle vurgulanır
- **Sesli uyarılar**: Text-to-Speech (TTS) ile alerjen uyarıları
- **Bildirimler**: Android Notification sistemi ile alerjen uyarıları (Android 8.0+ için notification channel)
- Analiz sonucunda "Günlük Takibe Ekle" butonu (kalori bilgisi varsa)

#### Günlük Kalori Takibi (Mobil)
- Hedef kalori gösterimi (BMR, TDEE bilgileri ile)
- Bugünkü tüketim gösterimi
- Progress bar ile hedef/kalan kalori
- **Pasta grafiği ile makro besin dağılımı** (yağ, karbonhidrat, protein)
- Uyarı mesajları (hedef aşıldığında)
- "Yenile" butonu ile manuel veri güncelleme

#### Diğer Özellikler
- Scroll edilebilir profil ekranı (NestedScrollView)
- Analiz sonuçlarında kaynak bilgisi gösterilmez (sadece "Analiz tamamlandı" mesajı)
- Offline cache (Room Database ile analiz sonuçları)


