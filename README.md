# meal-planner 🍲

Weekly meal plans built around **where you live, the food you grew up with, what's in your kitchen and what you can spend**,
on open-weight models only, routed automatically per task.

## How it works

1. **Your body:** sliders; calorie and macro targets come from standard formulas (Mifflin-St Jeor, WHO BMI), with safety limits.
2. **Your food:** type any place ("Lyon", "Baramulla", "Москва"). It's matched against a **knowledge base** of cuisine profiles
   (staples, reference dishes with nutrition, meal times, currency, local budgets). Unknown places are mapped by a fast model,
   and a new cuisine profile is written by **Gemma 4** in the background and saved, so the next lookup is instant.
3. **Your day:** describe a normal day in plain words. A **Mastra intake agent** grounds it in the knowledge base, estimates
   calories, flags diet conflicts and asks follow-up questions.
4. **Your kitchen:** equipment, plus a free-text pantry read by a **Mastra pantry agent**; budget in your local currency.
5. **Plan:** the model drafts the week; **code re-totals every day** and makes diet-safe top-ups/swaps (`backend/app/balance.py`).
6. **Chat:** a **Mastra chat agent** (tools: knowledge-base search, day details, meal-swap proposals with an Apply button),
   behind a topic guardrail (`gpt-oss-safeguard-20b`) that only allows food, diet and meal-plan questions.

### Knowledge graph (MongoDB Atlas)

Reference knowledge (never user data: answers and plans stay in the browser) is a graph in two collections,
`kg_nodes` and `kg_edges`:

```
place ─IN→ country ─USES→ currency        place ─EATS→ cuisine ─HAS_DISH→ dish ─CONTAINS→ tag
diet / restriction ─EXCLUDES→ tag         allergy ─IS→ tag      tag ─INCLUDES→ tag (animal_product → meat → red_meat → beef)
```

- `$graphLookup` expands preferences into banned ingredient tags (vegan → animal_product → meat → … → beef) and
  walks cuisine → dish → tag to find the dishes a person can eat (`backend/app/graph.py`).
- Curated knowledge is seeded on startup (idempotent; skipped when unchanged). Gemma-written cuisine profiles and
  resolved places are saved to Atlas, so they survive redeploys.
- `GET /api/graph/stats` and `POST /api/graph/explain` show the graph and why a dish is allowed or blocked.
- Without `MONGODB_URI` (or if Atlas is down) everything falls back to the JSON knowledge base, with identical rules.

### Model routing (no model picker)

| Task | Chain (first available wins; later ones are fallbacks) |
|---|---|
| Full week plan | gpt-oss-120b → Qwen 3.8 27B → Gemma 4 (split into parallel chunks on slow hosts) |
| Location / intake / pantry extraction | Qwen 3.8 27B → gpt-oss-120b → Gemma 4; **non-Latin text → Gemma 4 first**; very long text → gpt-oss-120b first |
| New cuisine profile for the knowledge base | Gemma 4 26B-A4B → Gemma 4 31B → gpt-oss-120b |
| Chat | gpt-oss-120b → Qwen → Gemma 4 |
| Topic guardrail | gpt-oss-safeguard-20b → Qwen |

## Run locally

```bash
# 1. secrets: copy .env.example to .env (repo root) and add your keys

# 2. backend (port 8000)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# 3. frontend + agents (port 3000)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The frontend reads the same root `.env` for the agent routes.

### Fully offline mode
Install [Ollama](https://ollama.com), run `ollama pull gemma3:1b`, and set `LOCAL_ONLY=true` in `.env`. Planning then
runs on your machine (slow on CPU-only laptops). The agents still use the hosted models for now.

## Tests and evaluation

```bash
cd backend
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest tests            # offline: maths, knowledge base, rules, balancer, variety, reference data
.venv/Scripts/python -m pytest tests --live     # + places outside the KB resolve to the right currency (calls models)
.venv/Scripts/python -m evals.region_plans      # full plans for 10 region/diet profiles -> evals/report.md
```

- **Reference data from the internet** (`tests/fixtures/`, rebuilt by `tests/tools/build_reference_data.py`):
  USDA FoodData Central survey foods (FNDDS 2024) for per-portion calories/protein of 27 matched dishes, and the
  mledoze/countries dataset for each country's currency.
- The nutrition comparison prints a KB-vs-USDA table and fails on outliers (>60% off) or a median error above 25%.
- If the MongoDB graph is configured, tests also check that graph traversals give exactly the same rules and dishes
  as the in-memory fallback.

## Layout

- `backend/app/`: FastAPI. `kb.py` + `kb/cuisines.json` (knowledge base), `region.py` (location → cuisine, background
  generation), `config.py` (routing), `planner.py`, `balance.py`, `nutrition.py`.
- `frontend/src/mastra/`: Mastra agents (`intake`, `pantry`, `chat`), the topic guard, the model router.
- `frontend/src/app/`: routes: `/` home, `/plan/[step]`, `/plan/result`, `/api/agent/*`.

## Deploy
- **Render:** `render.yaml` is a Blueprint for both services on free `*.onrender.com` URLs (custom domain steps are in its header).
- **Backend (Render web service):** `uvicorn app.main:app --host 0.0.0.0 --port $PORT` from `backend/`;
  env: model keys, `CORS_ORIGINS=https://<frontend domain>`, `ENABLE_LOCAL_MODELS=false`.
- **Frontend (Render or Vercel):** root `frontend/`; env: model keys (for the agents), `NEXT_PUBLIC_API_URL` and
  `BACKEND_URL` = the backend URL.

General guidance, not medical advice.
