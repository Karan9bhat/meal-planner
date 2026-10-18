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

## Layout

- `backend/app/`: FastAPI. `kb.py` + `kb/cuisines.json` (knowledge base), `region.py` (location → cuisine, background
  generation), `config.py` (routing), `planner.py`, `balance.py`, `nutrition.py`.
- `frontend/src/mastra/`: Mastra agents (`intake`, `pantry`, `chat`), the topic guard, the model router.
- `frontend/src/app/`: routes: `/` home, `/plan/[step]`, `/plan/result`, `/api/agent/*`.

## Deploy
- **Backend (Render web service):** `uvicorn app.main:app --host 0.0.0.0 --port $PORT` from `backend/`;
  env: model keys, `CORS_ORIGINS=https://<frontend domain>`, `ENABLE_LOCAL_MODELS=false`.
- **Frontend (Render or Vercel):** root `frontend/`; env: model keys (for the agents), `NEXT_PUBLIC_API_URL` and
  `BACKEND_URL` = the backend URL.

General guidance, not medical advice.
