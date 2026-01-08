from app.nlp import extract_ingredients, parse_nutrition_facts


def test_parse_nutrition_tr_basic():
    text = """
    Besin Değerleri
    Enerji: 250 kcal
    Yağ: 12,5 g
    Karbonhidrat: 30 g
    Protein: 6 g
    Şeker: 10 g
    Tuz: 0,8 g
    Sodyum: 120 mg
    """
    nf = parse_nutrition_facts(text)
    assert nf.calories_kcal == 250
    assert nf.fat_g == 12.5
    assert nf.carbs_g == 30
    assert nf.protein_g == 6
    assert nf.sugar_g == 10
    assert nf.salt_g == 0.8
    assert nf.sodium_mg == 120


def test_extract_ingredients_tr():
    text = "İçindekiler: Su, Buğday unu, Süt tozu; Tuz"
    items = extract_ingredients(text)
    assert "Su" in items
    assert any("Buğday" in x for x in items)
    assert any("Süt" in x for x in items)






