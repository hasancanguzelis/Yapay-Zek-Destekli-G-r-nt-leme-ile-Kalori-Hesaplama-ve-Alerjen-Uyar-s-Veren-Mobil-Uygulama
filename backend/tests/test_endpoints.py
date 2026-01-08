import io

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import NutritionFacts
from app.ml_meal_calories import MealCalorieModelError


client = TestClient(app)


def test_product_by_barcode_validates_barcode(monkeypatch):
    # invalid
    r = client.post("/product/by_barcode", data={"barcode": "abc"})
    assert r.status_code == 400

    async def fake_fetch(barcode: str, **_kwargs):
        assert barcode == "12345678"
        return {
            "product_name": "Test Ürün",
            "ingredients_text": "Buğday unu, süt tozu",
            "nutriments": {"energy-kcal_100g": 100, "fat_100g": 1.0},
        }

    monkeypatch.setattr("app.main.fetch_product_by_barcode", fake_fetch)
    r = client.post("/product/by_barcode", data={"barcode": "12345678"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "barcode_only"
    assert "OFF eşleşmesi" in "\n".join(body["warnings"])


def test_meal_analyze_requires_params_and_usda_key(monkeypatch):
    # No USDA key => 501
    monkeypatch.setattr(
        "app.main.settings",
        type("S", (), {"usda_api_key": None, "http_timeout_s": 1.0, "http_retries": 0, "http_retry_backoff_s": 0.0})(),
    )
    r = client.post(
        "/meal/analyze",
        files={"image": ("x.jpg", b"123", "image/jpeg")},
        data={"dish_name": "pilav"},
    )
    assert r.status_code == 501


def test_meal_analyze_uses_usda_and_includes_match(monkeypatch):
    # Provide USDA key
    monkeypatch.setattr(
        "app.main.settings",
        type("S", (), {"usda_api_key": "k", "http_timeout_s": 1.0, "http_retries": 0, "http_retry_backoff_s": 0.0})(),
    )

    async def fake_search(query: str, api_key: str, **_kwargs):
        assert api_key == "k"
        return {
            "foods": [
                {"description": "Low score", "fdcId": 1, "score": 1.0, "foodNutrients": []},
                {
                    "description": "Best match",
                    "fdcId": 2,
                    "score": 99.0,
                    "foodNutrients": [
                        {"nutrientName": "Energy", "unitName": "KCAL", "value": 250},
                        {"nutrientName": "Protein", "unitName": "G", "value": 5},
                    ],
                },
            ]
        }

    monkeypatch.setattr("app.main.search_foods", fake_search)

    r = client.post(
        "/meal/analyze",
        files={"image": ("x.jpg", io.BytesIO(b"123"), "image/jpeg")},
        data={"dish_name": "pilav"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "meal_estimate"
    assert body["nutrition"]["calories_kcal"] == 250
    assert "USDA eşleşmesi" in "\n".join(body["warnings"])


def test_meal_estimate_averages_and_scales_by_portion(monkeypatch):
    monkeypatch.setattr(
        "app.main.settings",
        type("S", (), {"usda_api_key": "k", "http_timeout_s": 1.0, "http_retries": 0, "http_retry_backoff_s": 0.0})(),
    )

    async def fake_search(query: str, api_key: str, **_kwargs):
        assert query == "kuru fasulye"
        assert api_key == "k"
        return {
            "foods": [
                {
                    "description": "A",
                    "fdcId": 1,
                    "score": 10.0,
                    "foodNutrients": [{"nutrientName": "Energy", "unitName": "KCAL", "value": 100}],
                },
                {
                    "description": "B",
                    "fdcId": 2,
                    "score": 9.0,
                    "foodNutrients": [{"nutrientName": "Energy", "unitName": "KCAL", "value": 200}],
                },
            ]
        }

    monkeypatch.setattr("app.main.search_foods", fake_search)

    r = client.post("/meal/estimate", data={"dish_name": "kuru fasulye", "portion": "2"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "meal_estimate"
    # average(100,200)=150; portion 2 => 300
    assert body["nutrition"]["calories_kcal"] == 300.0
    assert "Porsiyon=2.0" in "\n".join(body["warnings"])


def test_meal_predict_uses_model_when_available(monkeypatch):
    # If model loader works, /meal/predict should return source=meal_model.
    monkeypatch.setattr(
        "app.main.settings",
        type(
            "S",
            (),
            {
                "usda_api_key": "k",
                "http_timeout_s": 1.0,
                "http_retries": 0,
                "http_retry_backoff_s": 0.0,
                "meal_calorie_model_path": None,
            },
        )(),
    )

    class FakePipeline:
        def predict(self, X):
            # constant kcal per portion
            return [123.0]

    class FakeModel:
        path = "backend/models/meal_calorie_model.joblib"
        models = {"calories_kcal": FakePipeline()}

    monkeypatch.setattr("app.main.load_meal_calorie_model", lambda **_kwargs: FakeModel())
    monkeypatch.setattr("app.main.predict_nutrition", lambda _m, _dish: NutritionFacts(calories_kcal=123.0))

    r = client.post("/meal/predict", data={"dish_name": "kuru fasulye", "portion": "2"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "meal_model"
    assert body["nutrition"]["calories_kcal"] == 246.0


def test_meal_predict_falls_back_to_estimate_when_model_missing(monkeypatch):
    # If model is missing, endpoint should still work via USDA fallback.
    monkeypatch.setattr(
        "app.main.settings",
        type(
            "S",
            (),
            {
                "usda_api_key": "k",
                "http_timeout_s": 1.0,
                "http_retries": 0,
                "http_retry_backoff_s": 0.0,
                "meal_calorie_model_path": None,
            },
        )(),
    )

    monkeypatch.setattr(
        "app.main.load_meal_calorie_model",
        lambda **_kwargs: (_ for _ in ()).throw(MealCalorieModelError("no model")),
    )

    async def fake_search(query: str, api_key: str, **_kwargs):
        return {
            "foods": [
                {"description": "A", "fdcId": 1, "score": 1.0, "foodNutrients": [{"nutrientName": "Energy", "unitName": "KCAL", "value": 100}]},
            ]
        }

    monkeypatch.setattr("app.main.search_foods", fake_search)

    r = client.post("/meal/predict", data={"dish_name": "kuru fasulye", "portion": "2"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "meal_estimate"
    assert body["nutrition"]["calories_kcal"] == 200.0


def test_predict_allergens_endpoint(monkeypatch):
    # Avoid requiring sklearn/joblib in tests: monkeypatch loader to return a fake model.
    class FakePipeline:
        def predict_proba(self, X):
            # labels: ["milk","gluten","soy"] -> probs
            return [[0.9, 0.2, 0.6]]

    class FakeModel:
        path = "backend/models/allergen_clf.joblib"
        pipeline = FakePipeline()
        classes = ["milk", "gluten", "soy"]
        thresholds = [0.5, 0.5, 0.7]

    monkeypatch.setattr("app.main.load_allergen_model", lambda: FakeModel())

    r = client.post("/predict/allergens", json={"text": "İçindekiler: süt tozu, buğday unu, soya lesitini", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["model_path"]
    assert "milk" in body["predicted"]
    assert "soy" not in body["predicted"]  # 0.6 < 0.7 threshold
    assert len(body["scores"]) == 3


