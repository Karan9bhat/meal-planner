# Regional plan evaluation

2/2 profiles planned. Each plan is 7 days; ✓ counts are days within limits (calories ±10%, protein ≥85% of target, cost ≤110% of budget). Currency is checked against the mledoze/countries dataset; diet violations are a keyword scan of every meal.

| Profile | Model | Time | Currency | kcal ✓ | Protein ✓ (avg/target) | Budget ✓ (avg/budget) | Distinct dishes | Repetitive days | Diet violations | Regional share |
|---|---|---|---|---|---|---|---|---|---|---|
| Moscow · pescatarian | gpt-oss-120b | 12.6s | RUB ✓ | 7/7 | 7/7 (89/87 g) | 7/7 (286.29/700.0) | 25 | 0 | 0 | 96% |
| Chennai · eggetarian, no onion/garlic | Gemma 4 26B-A4B | 244.8s | INR ✓ | 7/7 | 7/7 (79/87 g) | 7/7 (180.71/250.0) | 20 | 0 | 0 | 69% |

## Totals

- Calories on target: 14/14 days
- Protein on target: 14/14 days
- Within budget: 14/14 days
- Currency correct: 2/2
- Diet violations: 0 meals
- Average distinct dishes per week: 22.5
- Average regional share: 82%

## Diet violations found


## Sample day (Wednesday) per profile

**Moscow · pescatarian**: Breakfast: Open rye sandwich with tvorog, cucumber & dill · Lunch: Leftover salmon & buckwheat bowl with beet‑carrot salad · Snack: Kefir with a drizzle of jam · Dinner: Fish fillet baked in pressure cooker with potatoes and dill sauce

**Chennai · eggetarian, no onion/garlic**: Early Morning: Filter coffee · Breakfast: Ragi Upma with vegetables · Lunch: Rice with Rasam and Moong Dal Poriyal · Snack: Boiled egg · Dinner: Egg Dosa with chutney
