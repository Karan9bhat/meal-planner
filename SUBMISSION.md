*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

## What I Built

**meal-planner** builds a week of meals around *your* life: where you live, the food you grew up with, what's in your cupboard, the pans you own and the money you can spend. Then it gets you to a target weight with food you'd actually cook.

Most diet apps hand everyone the same chicken-and-broccoli plan. It doesn't care that you live in Pune and eat poha for breakfast, that your hostel kitchen is one induction plate, or that your food budget is ₹200 a day. meal-planner starts from the opposite end:

- **You type where you live, in any language.** "Lyon", "Baramulla", "Москва", "Kraków". It loads what households there actually cook and buy, priced in the local currency (₹, £, €, R$, CLP…).
- **You describe a normal day in plain words.** No dropdown of foods you don't eat. An agent turns *"tea with two sugars, two parathas, rajma-chawal at lunch…"* into meals with calorie estimates, flags conflicts ("you said vegetarian but mentioned chicken"), and asks up to three follow-up questions when it matters.
- **You list your pantry the same way.** A second agent sorts it, and your shopping list only contains what's missing.
- **You get a 7-day plan:** meal times, portions in local household measures (katori, cups, slices), recipes that only use your equipment, the shopping list, and a chat assistant for swaps ("make Wednesday's dinner cheaper"). Every swap is a proposal you approve with one click.

**Who would pay:**
- **Nutrition coaches and dietitians** with clients in different countries. Today they hand-edit the same template for a vegetarian client in Pune and a halal client in Manchester; this does the first draft in seconds.
- **Students, expats and people cooking on tight budgets** who've been failed by generic plans.

The model behind it runs on free tiers today, so a free tier for individuals and a small monthly plan for coaches are both viable.

## Demo

🔗 **Live:** https://kilobite-planner-web-lv88.onrender.com
*(Free Render instance: the first visit after a quiet spell can take ~1 minute to wake up.)*

![A generated week: 7 days, 16 recipes and one shopping list. Each day shows meal times, portions, macros and cost; the green dashed cards are top-ups added by code to hit the day's targets.](https://raw.githubusercontent.com/Karan9bhat/meal-planner/main/generated-plan.png)
*A generated week: meals with times, portions, macros and cost per day; green "added to hit your targets" items from the balancer; the day's totals against its targets; and a shopping list of only what's missing from the pantry.*

<!-- Optional extra shots: the "Your food" step resolving a city (e.g. Kraków → Polish, PLN), the "Your day" step parsing free text,
     and the chat assistant proposing a swap with the Apply button. -->

## Code

{% embed https://github.com/Karan9bhat/meal-planner %}

- `backend/`: FastAPI. Calorie maths, knowledge graph, model router, planner, balancer and variety checks, tests and evals.
- `frontend/`: Next.js app plus the **Mastra** agents (intake, pantry, chat) and the topic guardrail.
- `render.yaml`: the Render Blueprint for both services.

## How I Built It

### The rule: models pick the dishes, code does the maths

Small mistakes in calories hurt people, so no model ever decides a number that matters:

- **Targets come from formulas:** Mifflin-St Jeor energy needs, a calorie floor (1,200/1,500 kcal), weight loss capped at 1% of body weight per week, and no target below BMI 18.5.
- **The model drafts the week; code re-adds every day.** A deterministic **balancer** then fixes days that fall short. It adds a diet-safe top-up (tofu for a vegan, cottage cheese for a vegetarian), or swaps out a serving of the rice or bread *that day already contains* to make room for protein. Every change is marked in green in the UI.
- **Variety is checked by code too.** If a main dish appears more than twice a week, or two days are identical, only those days go back to the model, with a "don't use these again" list.

### Open-weight models, routed by task (no model picker)

| Task | Models (first available wins, the rest are fallbacks) |
|---|---|
| Full week plan | **gpt-oss-120b** (Groq) → Qwen 3.8 27B → **Gemma 4 26B-A4B / 31B** |
| Reading location, day and pantry text | Qwen 3.8 27B → gpt-oss-120b → Gemma 4. **Non-Latin text goes to Gemma 4 first** (trained on 140+ languages). |
| Writing a new region into the knowledge base | **Gemma 4** → gpt-oss-120b |
| Chat with tool calls | gpt-oss-120b → Qwen → Gemma 4 |
| Topic guardrail | **gpt-oss-safeguard-20b** |

Every model is open-weight behind an OpenAI-compatible API, so swapping hosts is a config change.

**Making Gemma 4 practical on a free tier:**
- **Thinking that can't be turned off:** Gemma 4 on Google AI Studio always "thinks" before answering, and the API rejects every setting to turn it off. One line in the system prompt ("think briefly, then output compact JSON") cut an outline call from **82 s to 24 s**.
- **Slow output:** at about 40 tokens/s a full week in one call takes minutes. So for Gemma the planner writes a **7-day menu outline first, then fills days and recipes in parallel**.
- **It works when it counts:** during testing, Groq's free quota ran out mid-evaluation and Gemma 4 produced a complete, valid Chennai week (eggetarian, no onion or garlic) that passed every check.

### Mastra agents

- **Intake and pantry agents** use Mastra structured output with per-request model chains. They're grounded in the knowledge base (the same data the Atlas graph holds), which supplies nutrition for the dishes you mention and your region's usual meal times.
- **The chat agent** has three tools: `searchFoods` (knowledge-base nutrition lookup), `getDay` and `proposeSwap`. Swaps come back as cards with an *Apply* button; the agent can't change your plan by itself.
- **A custom input processor** runs `gpt-oss-safeguard-20b` against a written policy. Anything that isn't about food, diet or your plan is refused in about a second, before it reaches the main model.

### A knowledge graph on MongoDB Atlas

Regions, cuisines, dishes and diet rules live in Atlas as a graph:

```
place ─IN→ country ─USES→ currency        place ─EATS→ cuisine ─HAS_DISH→ dish ─CONTAINS→ tag
diet / restriction ─EXCLUDES→ tag         allergy ─IS→ tag      tag ─INCLUDES→ tag
```

- **Diet rules are a hierarchy.** "Vegan" excludes `animal_product`, and a `$graphLookup` walks *animal_product → meat → red_meat → beef*. "Which French dishes can a halal pescatarian with a peanut allergy eat?" is one traversal.
- **The graph grows itself.** 14 cuisines are hand-curated. Any other place is mapped by a fast model in under a second, then **Gemma 4 writes a full cuisine profile in the background** (Polish took 69 s) and saves it to Atlas, so the next person searching Kraków gets it instantly, even after a redeploy.
- Atlas is reached with **X.509 certificate authentication**. Without it, everything falls back to a local JSON copy with identical rules, and the tests check the two agree exactly.

![MongoDB Atlas: Cluster0 on the free tier, AWS Mumbai, 3-node replica set](https://raw.githubusercontent.com/Karan9bhat/meal-planner/main/mongo-db.png)
*The knowledge graph runs on a free Atlas cluster (AWS Mumbai, 3-node replica set).*

### Seeing what the agents do: Sentry

- **Backend:** every plan is an `invoke_agent planner` trace, with each model call (model, latency, tokens) and the draft, variety and balance steps nested inside.
- **Agents:** Mastra's Sentry exporter sends traces for the intake, pantry and chat agents and their tool calls.
- **Privacy:** prompt and answer text is redacted before it leaves the server. Traces show the shape of a run, never what a user typed.

![Sentry AI Agents Overview for meal-planner: agent runs, estimated cost, duration, LLM calls and tokens by model](https://raw.githubusercontent.com/Karan9bhat/meal-planner/main/sentry.png)
*Sentry's AI Agents dashboard for a test session: agent runs, estimated cost, duration, and calls and tokens per model. gpt-oss-120b made 6 calls (20,403 tokens), Qwen 3.8 27B 3 calls (1,247 tokens), and the gpt-oss-safeguard-20b guardrail 1 call (454 tokens), for a total estimated cost of under one US cent.*

### Tested against real-world data

- **Nutrition vs USDA:** I pulled USDA FoodData Central's survey foods and compared 27 knowledge-base dishes per portion. The median gap was **29%**. Fixing the 11 worst dishes (my palak paneer and cappuccino were far too high) brought it to **17%**, and the test now fails if any dish drifts more than 60%.
- **Currencies:** checked against an open countries dataset. **12/12** places outside the knowledge base (São Paulo, Lagos, Seoul, Hanoi…) resolved to the right currency.
- **End-to-end evaluation:** 10 region and diet profiles (Pune vegetarian, Baramulla halal, London on a tight budget, Lyon vegetarian with a peanut allergy, Moscow pescatarian, Mexico City gluten-free, Tokyo high-protein, New York vegan, Kraków keto, Chennai eggetarian with no onion or garlic). Across the 7-day plans:
  - **Calories on target on 70/70 days**, and the correct currency for every region
  - **No real diet violations.** The keyword scanner flagged 3 meals, all false alarms (goat's cheese and tofu yogurt).
  - **17–27 distinct dishes per week**, after the variety fix took Lyon from 9 to 26
- **97 offline tests** cover the maths, rules, graph-vs-local agreement, balancer and variety. Live tests call every model directly, so a retired model or broken key shows up immediately.

### Deployment

Two **Render** services from one Blueprint: FastAPI, and Next.js with the Mastra agents. The browser reads the API address at runtime, so moving the backend never needs a rebuild.

![Render: kilobite-planner-web (Node) and kilobite-planner-api (Python 3), both deployed in Singapore](https://raw.githubusercontent.com/Karan9bhat/meal-planner/main/render.png)
*Both services live on Render's free tier in Singapore: the Next.js web app with the agents, and the Python API.*

### What went wrong (and what it taught me)

- **Llama 3.3 was retired from Groq mid-build.** The router made switching to gpt-oss-120b a one-line change.
- **Telling Gemma to "adjust portions until within 5%"** made it re-add numbers in its head for over 3 minutes and never answer. Telling it the truth ("our code re-checks the totals") fixed it. Models are bad at arithmetic, so stop asking them to do it.
- **My first plans rotated the same 9 dishes all week.** The cause was my own prompt ("reuse dishes, at most 10 recipes"). Variety is now a measured, enforced check.
- **Groq's free tier rejects a request when prompt plus output allowance exceeds its per-minute budget.** A longer prompt caused `413` errors until I capped the output allowance and recipe count.
- **Protein for plant-based diets at low calories is the hardest target.** Even with the balancer, vegan and vegetarian plans sometimes land 10% under on a couple of days. The app says so instead of hiding it.

## Why Does Open Innovation Matter?

- **The business only works because the models are open and cheap to run.** A week of meals is a long structured answer. On open models served on free and low-cost tiers it costs nothing today, which is what makes a free tier for individuals and a cheap coach plan realistic. With per-token prices from a closed API, that margin is gone.
- **No lock-in. I swapped models mid-build without touching product code.** Llama 3.3 was retired and gpt-oss took its place; Gemma 4 covers for gpt-oss when Groq is rate-limited. Every model speaks the same API, so the router is just an ordered list per task.
- **Different open models for different jobs.** gpt-oss-120b for long plans, fast Qwen for extraction, Gemma 4 for multilingual input and world-food knowledge, gpt-oss-safeguard for a written policy guardrail. One closed model would have to do everything at one price.
- **Your health data doesn't have to leave you.** Answers and plans live only in your browser, and nothing about a user is stored server-side. The same open models also run locally through Ollama: an offline mode routes planning to a local Gemma model, though I haven't tested it end to end yet.
- **I can inspect and fix it.** Because the stack is open (Mastra, the models, the data), I could measure exactly where it was wrong against USDA data and fix the knowledge, rather than hoping a black box gets it right.

## My Agent Session

The whole build, with Claude Code: from "diet apps ignore what's in your kitchen" to a deployed multi-agent app. It includes every wrong turn: a model retired mid-build, Gemma thinking itself into a 3-minute loop, the same 9 dishes on repeat, and the Render deploy debugging. API keys, connection strings and private paths were scrubbed before saving.

{% agent_session 1028 %}

## Prize Categories

- **Best Use of Render:** both services (FastAPI, and Next.js with the Mastra agents) deploy from one Render Blueprint. The browser reads the backend address at runtime, and the Atlas certificate is a Render Secret File.
- **Best Use of Gemma:**
  - Gemma 4 writes new regions into the knowledge base (Polish in 69 s, saved for everyone after).
  - It reads non-Latin text in the forms first and is the fallback planner.
  - It planned a complete, valid week when Groq's quota ran out.
  - I made it practical on a free tier: a brevity instruction (82 s → 24 s) and an outline-then-parallel planner.
- **Best Use of Mastra:** three Mastra agents (intake, pantry, chat) with structured output, per-request model fallback chains, tools (`searchFoods`, `getDay`, `proposeSwap`), and a custom input processor guardrail running gpt-oss-safeguard-20b.
- **Best Use of Sentry Agent Tracing:** planner traces with model calls, token usage and the draft, variety and balance steps, plus Mastra agent traces with tool calls via the Sentry exporter. Prompt text is redacted so users' answers never leave the server.
- **Best Use of MongoDB Atlas:** a knowledge graph (`kg_nodes` / `kg_edges`) queried with `$graphLookup` to expand diet rules through a tag hierarchy and find the dishes a person can eat. It grows as Gemma writes new regions, survives redeploys, and uses X.509 certificate authentication.
