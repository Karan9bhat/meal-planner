"""Build the reference fixtures the tests compare against, from public internet datasets.

Usage (download the two files first, into a folder of their own):
    curl -L -o fndds.zip https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_survey_food_json_2024-10-31.zip
    curl -L -o countries.json https://raw.githubusercontent.com/mledoze/countries/master/countries.json
    python -I tests/tools/build_reference_data.py fndds.zip countries.json tests/fixtures

Only the handful of values the tests need are written to the fixtures (with their source), so the repo
stays small and the tests run offline.
"""

import json
import sys
import zipfile
from datetime import date
from pathlib import Path

# KB dish -> USDA FNDDS food, and the grams that match the KB portion.
# Grams come from USDA's own portion weights where one matches; otherwise from a stated household measure.
NUTRITION_MAP = [
    # cuisine, KB dish name, FNDDS description, grams, how the grams were chosen
    ("north_indian", "Steamed rice", "Rice, white, cooked, NS as to fat", 163, "USDA '1 cup, cooked'"),
    ("north_indian", "Dal tadka", "Dal", 150, "1 katori ≈ 150 g"),
    ("north_indian", "Palak paneer", "Palak Paneer", 150, "1 katori ≈ 150 g"),
    ("north_indian", "Samosa", "Samosa", 100, "USDA '1 regular/large'"),
    ("north_indian", "Chicken curry", "Chicken curry", 200, "1 katori with 3 pieces ≈ 200 g"),
    ("south_indian", "Idli", "Idli", 76, "USDA '1 item' 38 g × 2"),
    ("south_indian", "Plain dosa", "Dosa, plain", 80, "USDA '1 medium'"),
    ("south_indian", "Masala dosa", "Dosa, with filling", 267, "USDA '1 medium'"),
    ("french", "Ratatouille", "Ratatouille", 215, "USDA '1 cup'"),
    ("french", "Plain yogurt (yaourt nature)", "Yogurt, whole milk, plain", 125, "French pot = 125 g"),
    ("french", "Quiche lorraine", "Quiche with meat, poultry or fish", 140, "home slice ≈ 140 g"),
    ("russian", "Kefir", "Kefir", 244, "USDA '1 cup'"),
    ("italian", "Minestrone", "Soup, minestrone", 300, "1 bowl ≈ 300 g"),
    ("italian", "Cappuccino", "Coffee, Cappuccino", 180, "Italian cup ≈ 180 ml"),
    ("american", "Mac and cheese", "Macaroni or noodles with cheese", 230, "USDA '1 cup'"),
    ("american", "Cheeseburger", "Cheeseburger, NFS", 165, "USDA '1 cheeseburger'"),
    ("mexican", "Quesadilla", "Quesadilla, cheese only", 120, "USDA '1 full circle'"),
    ("mexican", "Frijoles de olla", "Pinto beans, from dried, no added fat", 180, "USDA '1 cup'"),
    ("mexican", "Huevos rancheros", "Huevos rancheros", 236, "USDA 'quantity not specified'"),
    ("mexican", "Arroz rojo", "Spanish rice, fat added", 243, "USDA '1 cup'"),
    ("mexican", "Enchiladas verdes", "Enchilada, chicken", 450, "USDA '1 enchilada' 150 g × 3"),
    ("chinese", "Kung pao chicken", "Kung pao chicken", 243, "1 plate ≈ 1.5 USDA cups"),
    ("chinese", "Egg fried rice", "Rice, fried, NFS", 297, "1 plate ≈ 1.5 USDA cups"),
    ("japanese", "Miso soup", "Soup, miso or tofu", 245, "USDA '1 cup'"),
    ("german", "Sauerkraut", "Sauerkraut", 140, "USDA '1 cup'"),
    ("british", "Shepherd's pie", "Shepherd's pie", 250, "USDA '1 individual pie'"),
    ("global", "Lentil soup", "Soup, lentil", 300, "1 bowl ≈ 300 g"),
]

# Country (as in countries.json common name) per curated cuisine, plus extra places the live tests resolve.
CUISINE_COUNTRY = {
    "north_indian": "India", "kashmiri": "India", "south_indian": "India", "east_indian": "India", "west_indian": "India",
    "british": "United Kingdom", "french": "France", "russian": "Russia", "italian": "Italy", "german": "Germany",
    "american": "United States", "mexican": "Mexico", "chinese": "China", "japanese": "Japan",
}
EXTRA_COUNTRIES = ["Brazil", "Canada", "United Arab Emirates", "Chile", "Poland", "Australia", "Nigeria",
                   "South Korea", "Türkiye", "Spain", "Kenya", "Vietnam"]


def _fndds(zip_path: str) -> dict[str, dict]:
    """Stream-decode the 66 MB survey file one food at a time (keeps memory low)."""
    text = zipfile.ZipFile(zip_path).read("surveyDownload.json").decode("utf-8")
    wanted = {m[2] for m in NUTRITION_MAP}
    dec, i, found = json.JSONDecoder(), text.index("[") + 1, {}
    while True:
        while i < len(text) and text[i] in " \r\n\t,":
            i += 1
        if i >= len(text) or text[i] == "]":
            break
        obj, i = dec.raw_decode(text, i)
        if obj["description"] in wanted:
            nut = {n["nutrient"]["number"]: n.get("amount") for n in obj.get("foodNutrients", []) if "nutrient" in n}
            found[obj["description"]] = {"fdcId": obj["fdcId"], "kcal_100g": nut.get("208"), "protein_100g": nut.get("203")}
    return found


def main(zip_path: str, countries_path: str, out_dir: str) -> None:
    out = Path(out_dir)
    foods = _fndds(zip_path)
    missing = [m[2] for m in NUTRITION_MAP if m[2] not in foods]
    if missing:
        raise SystemExit(f"FNDDS foods not found: {missing}")
    nutrition = [
        {
            "cuisine": c, "dish": dish, "usda_food": food, "usda_fdc_id": foods[food]["fdcId"], "grams": g, "grams_basis": basis,
            "usda_kcal": round(foods[food]["kcal_100g"] * g / 100), "usda_protein_g": round(foods[food]["protein_100g"] * g / 100, 1),
        }
        for c, dish, food, g, basis in NUTRITION_MAP
    ]
    (out / "reference_nutrition.json").write_text(json.dumps({
        "source": "USDA FoodData Central, Survey (FNDDS) 2024-10-31 — https://fdc.nal.usda.gov/download-datasets",
        "built": date.today().isoformat(), "items": nutrition}, indent=2, ensure_ascii=False), encoding="utf-8")

    countries = {c["name"]["common"]: c for c in json.loads(Path(countries_path).read_text(encoding="utf-8"))}
    wanted = sorted(set(CUISINE_COUNTRY.values()) | set(EXTRA_COUNTRIES))
    currency = {}
    for name in wanted:
        if name not in countries:
            raise SystemExit(f"country not found in dataset: {name}")
        cur = countries[name].get("currencies", {})
        currency[name] = sorted(cur.keys())
    (out / "reference_currency.json").write_text(json.dumps({
        "source": "mledoze/countries — https://github.com/mledoze/countries",
        "built": date.today().isoformat(), "cuisine_country": CUISINE_COUNTRY, "currencies": currency}, indent=2), encoding="utf-8")
    print(f"wrote {len(nutrition)} nutrition references and {len(currency)} country currencies to {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
