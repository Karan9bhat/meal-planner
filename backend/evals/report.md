# Regional plan evaluation

5/6 profiles planned. Each plan is 7 days; ✓ counts are days within limits (calories ±10%, protein ≥85% of target, cost ≤110% of budget). Currency is checked against the mledoze/countries dataset; diet violations are a keyword scan of every meal.

| Profile | Model | Time | Currency | kcal ✓ | Protein ✓ (avg/target) | Budget ✓ (avg/budget) | Distinct dishes | Repetitive days | Diet violations | Regional share |
|---|---|---|---|---|---|---|---|---|---|---|
| Pune · vegetarian | gpt-oss-120b | 24.1s | INR ✓ | 7/7 | 5/7 (78/87 g) | 7/7 (174.86/250.0) | 23 | 0 | 0 | 74% |
| London · tight budget | gpt-oss-120b | 12.5s | GBP ✓ | 7/7 | 7/7 (84/87 g) | 6/7 (5.28/6.3) | 24 | 0 | 0 | 89% |
| Moscow · pescatarian | Qwen 3.8 27B | 46.0s | RUB ✓ | 7/7 | 7/7 (88/87 g) | 7/7 (564.57/700.0) | 10 | 3 | 0 | 91% |
| Tokyo · high protein | Gemma 4 26B-A4B | 82.8s | JPY ✓ | 7/7 | 7/7 (99/106 g) | 7/7 (1101.43/1500.0) | 17 | 2 | 0 | 71% |
| New York · vegan | Qwen 3.8 27B | 16.2s | USD ✓ | 7/7 | 5/7 (77/87 g) | 7/7 (7.33/14.0) | 20 | 0 | 1 | 68% |
| Chennai · eggetarian, no onion/garlic | — | — | INR | error: Gemma 4 31B is overloaded right now. Try again shortly. | | | | | | |

## Totals

- Calories on target: 35/35 days
- Protein on target: 31/35 days
- Within budget: 34/35 days
- Currency correct: 5/5
- Diet violations: 1 meals
- Average distinct dishes per week: 18.8
- Average regional share: 79%

## Diet violations found

- New York · vegan: Friday Snack: 'Greek-style Tofu Yogurt' (dairy)

## Sample day (Wednesday) per profile

**Pune · vegetarian**: Early Morning: Tea plain · Breakfast: Vegetable Upma (semolina) · Lunch: Rice, Masoor Dal & Lauki (bottle gourd) Sabzi with Jowar Bhakri · Snack: Buttermilk (Chaas) with a pinch of roasted cumin · Dinner: Methi Thepla with Tomato Chutney

**London · tight budget**: Breakfast: Whole‑grain toast with baked beans and a poached egg · Lunch: Cheese and pickle sandwich · Snack: Tea with 2 digestive biscuits · Dinner: Shepherd’s pie (made with lean mince)

**Moscow · pescatarian**: Breakfast: Oatmeal with Berries · Lunch: Borscht with Fish & Rye Bread · Snack: Kefir · Dinner: Baked Salmon with Potatoes · Drink: Black Tea

**Tokyo · high protein**: Breakfast: Rice, Miso soup, and Natto · Lunch: Oyakodon (Leftover) · Snack: Boiled Egg · Dinner: Zaru Soba with Hiyayakko

**New York · vegan**: Breakfast: Lentil Veggie Muffins · Lunch: Leftover Chili Salad Bowl · Snack: Carrot Sticks with Hummus · Dinner: Tofu & Broccoli Stir-fry
