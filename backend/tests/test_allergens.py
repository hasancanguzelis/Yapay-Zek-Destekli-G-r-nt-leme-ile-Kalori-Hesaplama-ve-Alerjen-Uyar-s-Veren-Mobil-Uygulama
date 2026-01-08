from app.allergens import canonicalize_off_allergens, detect_allergens, match_profile_allergens


def test_detect_allergens_tr():
    text = "İçindekiler: Buğday unu, süt tozu. Alerjen uyarısı: Yer fıstığı içerebilir."
    found = detect_allergens(text)
    assert "gluten" in found
    assert "milk" in found
    assert "peanut" in found


def test_match_profile_allergens():
    detected = ["gluten", "milk", "peanut"]
    matched, unknown = match_profile_allergens(detected, ["gluten", "fıstık", "bilinmeyenalerjen"])
    assert "gluten" in matched
    assert "peanut" in matched
    assert unknown == ["bilinmeyenalerjen"]


def test_canonicalize_off_allergens_tags():
    raw = [
        "en:milk",
        "en:soybeans",
        "en:eggs",
        "en:peanuts",
        "en:sesame-seeds",
        "en:nuts",
        "en:gluten",
        "en:fish",
        "en:crustaceans",
    ]
    out = canonicalize_off_allergens(raw)
    assert "milk" in out
    assert "soy" in out
    assert "egg" in out
    assert "peanut" in out
    assert "sesame" in out
    assert "tree_nuts" in out
    assert "gluten" in out
    assert "fish" in out
    assert "shellfish" in out




