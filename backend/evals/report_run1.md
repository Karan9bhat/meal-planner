# Regional plan evaluation

7/10 profiles planned. Each plan is 7 days; ✓ counts are days within limits (calories ±10%, protein ≥85% of target, cost ≤110% of budget). Currency is checked against the mledoze/countries dataset; diet violations are a keyword scan of every meal.

| Profile | Model | Time | Currency | kcal ✓ | Protein ✓ (avg/target) | Budget ✓ (avg/budget) | Distinct dishes | Repetitive days | Diet violations | Regional share |
|---|---|---|---|---|---|---|---|---|---|---|
| Pune · vegetarian | — | — | INR | error: The model returned a plan in an unexpected format. Please try again. | | | | | | |
| Baramulla · halal | gpt-oss-120b | 21.5s | INR ✓ | 7/7 | 5/7 (76/87 g) | 7/7 (240.89/280.0) | 21 | 0 | 0 | 57% |
| London · tight budget | — | — | GBP | error: Gemma 4 31B is overloaded right now. Try again shortly. | | | | | | |
| Lyon · vegetarian, peanut allergy | gpt-oss-120b | 12.8s | EUR ✓ | 7/7 | 0/7 (67/87 g) | 7/7 (6.3/10.0) | 27 | 0 | 2 | 100% |
| Moscow · pescatarian | Qwen 3.8 27B | 72.7s | RUB ✓ | 7/7 | 7/7 (85/87 g) | 7/7 (425.0/700.0) | 9 | 3 | 0 | 100% |
| Mexico City · gluten-free | gpt-oss-120b | 13.9s | MXN ✓ | 7/7 | 7/7 (85/87 g) | 7/7 (53.93/150.0) | 27 | 0 | 0 | 89% |
| Tokyo · high protein | gpt-oss-120b | 30.0s | JPY ✓ | 7/7 | 7/7 (112/106 g) | 7/7 (634.29/1500.0) | 5 | 5 | 0 | 100% |
| New York · vegan | gpt-oss-120b | 49.7s | USD ✓ | 7/7 | 0/7 (63/87 g) | 7/7 (6.56/14.0) | 8 | 5 | 0 | 89% |
| Kraków · keto | gpt-oss-120b | 13.8s | PLN ✓ | 7/7 | 7/7 (98/87 g) | 7/7 (11.49/50.0) | 24 | 0 | 0 | 61% |
| Chennai · eggetarian, no onion/garlic | — | — | INR | error: The model returned a plan in an unexpected format. Please try again. | | | | | | |

## Totals

- Calories on target: 49/49 days
- Protein on target: 33/49 days
- Within budget: 49/49 days
- Currency correct: 7/7
- Diet violations: 2 meals
- Average distinct dishes per week: 17.3
- Average regional share: 85%

## Diet violations found

- Lyon · vegetarian, peanut allergy: Wednesday Lunch: 'Quinoa‑lentil bowl with roasted veg and goat cheese' (lamb_mutton)
- Lyon · vegetarian, peanut allergy: Friday Lunch: 'Puy lentil salad with roasted beetroot and goat cheese' (lamb_mutton)

## Sample day (Wednesday) per profile

**Baramulla · halal**: Breakfast: Vegetable Omelette with whole wheat toast · Lunch: Tofu-Spinach Stir-Fry · Snack: Fruit Salad (Apple and Banana) · Dinner: Soy Chunk Curry

**Lyon · vegetarian, peanut allergy**: Breakfast: Tartine with cheese and cucumber · Lunch: Quinoa‑lentil bowl with roasted veg and goat cheese · Snack: Fruit salad (apple, pear, orange) · Dinner: Vegetable gratin with béchamel (no meat) and a side salad

**Moscow · pescatarian**: Breakfast: Buckwheat Kasha with Milk · Lunch: Fish Borscht & Buckwheat · Snack: Kefir & Rye Bread · Dinner: Baked Hake with Cabbage

**Mexico City · gluten-free**: Breakfast: Scrambled eggs with nopales and salsa · Lunch: Lentil soup with rice · Snack: Cucumber sticks with lime and chili · Dinner: Chicken pozole (light)

**Tokyo · high protein**: Breakfast: Grilled salmon with rice, natto & miso soup · Lunch: Chicken teriyaki bowl (leftovers) · Snack: Onigiri (salmon) · Dinner: Grilled mackerel, half‑portion zaru soba, hiyayakko & miso soup (leftovers)

**New York · vegan**: Breakfast: Peanut butter‑banana oat bowl · Lunch: Tofu‑vegetable stir‑fry with brown rice · Snack: Apple with almond butter · Dinner: Chickpea‑spinach salad wrap

**Kraków · keto**: Breakfast: Keto scrambled eggs with bacon · Lunch: Zurek keto style (sour rye broth) with boiled egg · Snack: Cheese cubes & olives · Dinner: Pan‑fried pork cutlet with sauerkraut
