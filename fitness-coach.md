# Plan: WhatsApp AI Fitness Coach (RAG + Agentic showcase)

## Decisions from user
- New standalone repo (separate from Educosys_Claude_Code), but reuse its proven patterns as blueprint.
- Stack: LangChain + LangGraph agent, Chroma for RAG, DeepEval for evals, LLM factory (OpenAI/Anthropic) pattern — mirrors Educosys_Claude_Code.
- WhatsApp via Twilio Sandbox (not Meta Cloud API directly).
- Voice: transcribe incoming voice notes (STT), always reply in text (no TTS out for v1).
- Food photos: Cloud vision LLM (GPT-4o/Claude vision) — no local OCR/vision model for v1.
- Wearable data: simulated via CSV/JSON import or mock generator (no real Fitbit/Google Fit API for v1).
- Structured data: SQLite (Postgres-ready schema via SQLAlchemy) alongside Chroma vector KB.
- All calorie/score/TDEE arithmetic MUST be deterministic Python tool functions — LLM never computes numbers, only narrates/recommends.

## Reference patterns from Educosys_Claude_Code (to replicate, not copy verbatim)
- `context/indexers/factory.py` + `semantic_chroma.py`: indexer factory + Chroma persistent store pattern for the nutrition/exercise knowledge base.
- `context/retrievers/factory.py` + `semantic_chroma.py`: retriever factory, returns list[dict] with content/source/distance.
- `llm/factory.py`: `get_llm()`/`get_embedder()` abstraction for OpenAI/Anthropic swap.
- `agent/orchestrator.py` + `agent/tools.py`: `@observe`-decorated tool-using agent, semantic-cache-gated invocation.
- `memory/short_term.py`: `AsyncSqliteSaver` (LangGraph) + `SummarizationMiddleware` for rolling conversation memory — thread_id keyed by WhatsApp phone number (continuous session, no "new session" concept needed).
- `tools/filesystem_tools.py` style: `@tool` decorator, returns str, errors as "Error: ..." strings, not exceptions.
- `tests/evals/metrics.py` + `conftest.py` + dataset_*.json + DeepEval `GEval`/contextual metrics: mirror for fitness-coach eval suites.
- `observability/logger.py`: singleton logger pattern.
- No existing guardrail/intent-detection code found in repo — this is new for the fitness coach (needs design from scratch).

## Target architecture (new repo: `ai_fitness_coach_rag/`)
```
ai_fitness_coach_rag/
  main.py                      # FastAPI app: Twilio webhook + scheduler startup
  config.py / config.yaml
  whatsapp/
    twilio_client.py           # send text (media send if needed)
    webhook.py                 # parse inbound Twilio payload (text / MediaUrl for audio+image)
  agent/
    factory.py                 # build_agent(): LLM + tools + system prompt
    orchestrator.py             # handle_message(user_id, text) entry point
    router.py                  # intent/guardrail classifier (new)
    tools/
      logging_tools.py         # log_food, log_workout, log_metric, log_water (writes DB)
      nutrition_tools.py       # lookup_nutrition: fuzzy-match (rapidfuzz) against db/seed_data, labeled estimated fallback
      onboarding_tools.py      # NEW: slot-filling profile capture (age/weight/goals/dietary pref/units/timezone)
      calc_tools.py            # tool wrappers around db/scoring.py (deterministic)
      knowledge_tools.py       # search_knowledge_base (Qdrant hybrid+reranked RAG, routes to fitness_principles/exercise_technique)
      personal_doc_tools.py    # NEW: ingest_personal_document, search_personal_documents (per-user isolated Qdrant collection)
      plan_tools.py            # get_meal_plan, get_workout_plan (fuzzy-match seed_data + dietary pref/allergy filter)
      vision_tools.py          # estimate_calories_from_image (vision LLM call)
      profile_tools.py         # get/update profile (post-onboarding edits)
  llm/
    factory.py                 # get_llm(), get_embedder(), get_vision_llm(), get_stt()
  memory/
    short_term.py              # AsyncSqliteSaver + SummarizationMiddleware, thread_id=phone
    long_term.py                # NEW: per-user fact store (preferences learned over time)
  context/
    indexers/ , retrievers/     # Chroma-based, reusing semantic_chroma.py pattern
    knowledge_docs/             # curated fitness/nutrition corpus (md/json)
  cache/
    semantic_cache.py            # NEW: Redis semantic cache, scoped to knowledge_tools RAG queries only
  db/
    models.py                  # SQLAlchemy: User, DailyLog, DeviceMetric, Score, Plan
    session.py                  # engine/session factory (SQLite file, Postgres-ready)
    scoring.py                  # NEW: pure deterministic functions (BMR/TDEE, daily score, trend projection) — heavily unit tested
  jobs/
    morning_nudge.py            # APScheduler daily job: score + observation + goal trend -> push message
  observability/
    logger.py                   # reused pattern
tests/
  unit/test_scoring.py, test_tools.py
  evals/ (conftest.py, metrics.py, dataset_guardrails.json, dataset_logging_agent.json,
          dataset_rag_nutrition.json, dataset_summary_scoring.json,
          test_guardrails.py, test_logging_agent.py, test_rag_pipeline.py)
data/fixtures/ (sample device CSV, sample food images, onboarding transcripts)
README.md, pyproject.toml, .env.example
```

## Gap-check additions (found on recheck, folded into architecture/phases below)
- **Onboarding flow** was under-specified: needs explicit slot-filling state machine (age, sex, height, weight, activity level, dietary pref/allergies, units metric/imperial, goal type, target weight, target date) held in STM until all required fields captured, then written to User profile. Added `agent/tools/onboarding_tools.py`.
- **Nutrition lookup for text-logged food**: when user types a food item without calories (e.g. "ate 2 rotis and dal"), need a lookup step (knowledge base / nutrition dataset) before logging — not just trusting free-text numbers or only handling the photo path. Added `agent/tools/nutrition_tools.py` (lookup_nutrition, used by both logging_tools and vision_tools).
- **Webhook security (OWASP)**: must validate Twilio's `X-Twilio-Signature` header on every inbound webhook request to prevent spoofed requests. Added to Phase 5.
- **Idempotency**: Twilio may retry webhook delivery — dedupe on Twilio `MessageSid` to avoid double-logging. Added to Phase 5.
- **Secrets handling**: Twilio/OpenAI/Anthropic keys via `.env`, never committed; `.env.example` with placeholders only.
- **PII/data minimization**: hash/salt phone number as internal user_id rather than storing raw; food images downloaded transiently for vision processing then discarded (not persisted) unless user opts in.
- **Data lifecycle command**: a `/forget_me` style chat command to wipe a user's DB rows + STM thread (privacy-friendly for a health-data showcase).
- **Timezone & units**: profile stores IANA timezone + unit system (metric/imperial); "daily" boundaries and morning nudge scheduling computed in user's local time, not server UTC.
- **Confirm-flow expiry**: a pending vision-estimate confirmation expires after N minutes/messages to avoid stale state blocking the router.
- **Dietary-preference filtering**: `plan_tools.py` must filter meal/workout suggestions against profile's dietary pref/allergies, not just return generic plans.
- **Semantic cache**: reinstate Redis semantic cache (mirroring `cache/semantic_cache.py`), scoped ONLY to `knowledge_tools` RAG lookups (e.g. "how much protein in eggs") — never caches logging/scoring/personalized responses. Key includes query + domain tag; TTL-based.
- **Eval coverage gap**: added `dataset_onboarding.json` + onboarding slot-filling accuracy to Phase 8.
- **Deployment note**: ngrok is sufficient for local/demo use (Phase 5 verification); a persistent public host (Render/Fly.io/Railway) is a stretch goal only, not required for v1.

## Key design details
- **Intent/guardrail router**: cheap/fast LLM call (or small model) classifies each inbound message into allowed intents (onboarding, log_food, log_metric, log_workout, query_knowledge, request_summary, request_plan, image_food_log, confirm_pending, off_topic). Off-topic/unsafe -> canned refusal, short-circuits before RAG/agent/tools (saves tokens). Router must check "pending flow state" (e.g. awaiting confirmation of a vision calorie estimate) stored alongside STM so a bare "yes"/correction isn't misclassified as off-topic.
- **STM vs LTM**: STM = LangGraph checkpointer per phone number (rolling conversation + summarization, "session" = always-on, no manual switching). LTM = (a) structured SQL tables for profile/logs/scores (source of truth, queryable), (b) lightweight long_term.py fact store for soft preferences extracted opportunistically (e.g. "dislikes running", "vegetarian") — analogous to a notes file, not vectorized.
- **Knowledge base (RAG)**: curated nutrition/exercise/recipe corpus (markdown + JSON) indexed into Chroma via indexer factory pattern (static corpus, not live-watched like codebase).
- **Deterministic tools** (db/scoring.py): BMR/TDEE (Mifflin-St Jeor), calorie balance, macro tracking, weighted daily score (e.g. 30% calorie adherence, 25% protein, 20% steps/workout, 15% water, 10% consistency streak — weights in config.yaml), weekly/monthly aggregation (SQL/pandas), goal-achievability trend projection (compare required vs actual rolling 7-day average deficit/surplus, project ETA to goal).
- **Vision flow**: image -> vision LLM with structured JSON prompt (food items, qty estimate, calories, macros, confidence) -> shown to user as editable estimate -> user confirms or corrects via text reply -> logged to DB only after confirmation.
- **Voice flow**: inbound audio media URL -> download -> Whisper STT -> transcript treated as normal text message through same pipeline -> reply always text.
- **Morning nudge job**: APScheduler daily per active user: computes yesterday's score + observation, projects goal achievability, generates LLM narration from deterministic facts (LLM never invents numbers), pushes via Twilio. Note: proactive outbound messages outside a 24h session window require approved WhatsApp template (Twilio/Meta constraint) — flag as a constraint, plan for sandbox limitation/demo workaround.
- **Reliability**: all numeric logic in db/scoring.py as pure functions with full unit test coverage; agent/tools call these functions rather than doing math in prompts; DeepEval evals validate agent picks correct tool/extracts correct values rather than hallucinating.

## Steps (phased, each independently verifiable)

**Phase 0 — Scaffold** (no deps)
1. New repo structure, pyproject.toml, config.yaml, .env.example, logger setup (mirror observability/logger.py).

**Phase 1 — Data layer & deterministic scoring** (parallel with Phase 2)
2. SQLAlchemy models (User, DailyLog, DeviceMetric, Score, Plan) + db/session.py.
3. db/scoring.py: BMR/TDEE, score formula, trend projection — pure functions.
4. Unit tests (tests/unit/test_scoring.py) covering edge cases (missing data, goal directions gain/lose/maintain).

**Phase 2 — Knowledge base RAG** (parallel with Phase 1)
5. Curate `fitness_principles` + `exercise_technique` corpora (knowledge_docs/, two collections).
6. Reuse indexer/retriever factory pattern (Qdrant hybrid) to build context/indexers, context/retrievers, parameterized by collection name.
7. Index both corpora; add `reranker.py` (cross-encoder) on top of hybrid retrieval; smoke-test retrieval + rerank.
7b. cache/semantic_cache.py (Redis, mirrors repo pattern) — gates `knowledge_tools` lookups only.
7c. `personal_doc_tools.py` ingestion pipeline (PDF/text extraction → chunk → embed → per-user-isolated Qdrant collection) + strict user_id metadata filter at query time.

**Phase 3 — Agent + memory** (*depends on 1, 2*)
8. llm/factory.py (get_llm/get_embedder/get_vision_llm/get_stt).
9. Tools: logging_tools, nutrition_tools, onboarding_tools, calc_tools (wrap scoring.py), knowledge_tools (RAG), plan_tools, profile_tools.
10. memory/short_term.py (AsyncSqliteSaver + SummarizationMiddleware, thread_id=phone) and memory/long_term.py (fact store).
11. agent/router.py (intent/guardrail classifier incl. pending-flow-state + onboarding-in-progress awareness).
12. agent/factory.py + orchestrator.py wiring agent + tools + router + memory.

**Phase 4 — Vision + STT** (*depends on 3*, can start once tool interface conventions from step 9 exist)
13. vision_tools.py: estimate_calories_from_image + confirm/edit flow (stores pending estimate in state).
14. STT integration (Whisper) in message ingestion path before router.

**Phase 5 — WhatsApp gateway** (*depends on 3, 4*)
15. FastAPI app (main.py), Twilio webhook parsing (text/audio/image), **X-Twilio-Signature validation**, **MessageSid idempotency dedupe**, twilio_client.py for replies.
16. End-to-end local test via ngrok + Twilio sandbox.

**Phase 6 — Summaries & proactive nudge** (*depends on 1, 3*)
17. Daily/weekly/monthly summary tool (aggregation queries + narration).
18. jobs/morning_nudge.py (APScheduler) — score, observation, trend, suggestion push.

**Phase 7 — Wearable ingestion** (*depends on 1*, parallelizable with 3-6)
19. CSV/JSON import endpoint + mock device-data generator script; merge into DeviceMetric/scoring.

**Phase 8 — Evals & guardrail tests** (*depends on all functional phases*)
20. DeepEval metrics.py (mirror repo pattern): logging-accuracy GEval, guardrail refusal metric, RAG contextual precision/recall for knowledge base, score-explanation GEval, onboarding slot-filling accuracy GEval.
21. Datasets: dataset_guardrails.json (off-topic/malicious prompts expecting refusal), dataset_logging_agent.json, dataset_rag_nutrition.json, dataset_summary_scoring.json, dataset_onboarding.json, dataset_personal_doc_rag.json (retrieval quality + cross-user isolation).
22. test_guardrails.py, test_logging_agent.py, test_rag_pipeline.py, test_onboarding.py, test_personal_doc_isolation.py.

**Phase 9 — Docs**
23. README with setup (Twilio sandbox config, ngrok, env vars), architecture diagram, run instructions.

## Verification
- `pytest tests/unit` — scoring.py correctness across scenarios (deficit/surplus/maintenance, missing device data).
- `pytest tests/evals` via DeepEval — guardrail refusal rate, logging extraction accuracy, RAG contextual precision/recall ≥ threshold.
- Manual: Twilio sandbox round-trip (text log → DB row → score reflects it); send off-topic message → canned refusal, no tool/RAG calls (check logs/traces); send food photo → editable estimate → confirm → DB log; send voice note → transcribed and processed as text.
- Manual: trigger morning_nudge job manually → verify message content references real DB numbers (not hallucinated).

## Scope boundaries (explicitly excluded for v1)
- No real Meta WhatsApp Business Cloud API (Twilio sandbox only).
- No TTS/voice replies (text replies only).
- No local/offline vision or OCR models (cloud vision LLM only).
- No real wearable API integrations (Google Fit/Apple Health/Fitbit) — simulated data only.
- No multi-tenant auth/security hardening beyond basic guardrails (showcase project, not production).
- No Postgres setup in v1 (SQLite only, schema designed to be Postgres-compatible).

## Further considerations (flagged to user, not yet decided)
1. Twilio sandbox only supports session-based replies within a 24h window after user-initiated contact; true proactive "every morning" push requires an approved WhatsApp message template — may need to mention/accept this limitation or design nudge as "available when user next messages" fallback for demo purposes.
2. Daily score weighting (30/25/20/15/10 split) is a proposed default — open to adjustment once user reviews.

## Wearable integration research (decided: stay simulated for v1)
Real options evaluated: Fitbit Web API (OAuth2 web-link, no app needed, free dev tier, webhook subscriptions) is the only real-device path compatible with a WhatsApp-only (no native app) product. Google Health Connect and Apple HealthKit both require a native companion app to read device data — not viable without one. Aggregators (Terra/Vital/Spike API) unify many wearables behind one OAuth widget + webhooks but add an external dependency/cost.
Decision: v1 stays simulated/CSV-JSON import only (per Scope boundaries). If extended later, Fitbit Web API is the recommended stretch path — add `/integrations/fitbit/callback` OAuth route + token storage + webhook/poll job writing into the existing `DeviceMetric` table (no schema or scoring changes needed).

## RAG architecture revision (supersedes earlier Chroma-only / single-RAG-pipeline design)
On recheck, the original plan wrongly treated nutrition/exercise/knowledge data as one RAG pipeline. Revised to 3 distinct strategies based on reliability needs:

1. **Nutrition facts & exercise database — structured lookup, NOT vector RAG.**
   - Source: **hand-curated dataset** (~100-200 common foods/dishes incl. composite/cooked dishes like roti/dal/paneer tikka, and ~100-200 exercises with muscle group/equipment/difficulty). Decided to skip USDA FoodData Central / Free Exercise DB external integration for v1 — curated-only keeps scope small.
   - Storage: SQLite tables, queried via exact + fuzzy string match (`rapidfuzz`), not embedding similarity. Feeds `nutrition_tools.lookup_nutrition` and `plan_tools.get_workout_plan` deterministically.
   - Fallback: if an item isn't in the curated set, LLM may estimate (e.g. vision calorie estimate, or obscure dish) — but MUST be labeled "estimated, not verified" in the reply and tagged `source=estimated` in DB (distinct from `source=database` verified lookups). Never silently blended with verified facts.

2. **General fitness/nutrition knowledge (articles, principles, Q&A, recipes) — Qdrant + hybrid retrieval (dense+BM25)**, mirroring reference repo's `hybrid_qdrant.py` (`FastEmbedSparse` BM25 + dense, `RetrievalMode.HYBRID`). Switched from Chroma-dense-only because: (a) Chroma has no hybrid/BM25 support in the reused patterns, (b) hybrid matters here — queries mix vague semantic asks ("high protein breakfast ideas") with exact-term asks ("what's DOMS", specific recipe/ingredient names) where keyword matching improves precision. Requires running Qdrant (local Docker or cloud free tier) — added as new infra dependency.
   - This is the ONLY data category served by `knowledge_tools.search_knowledge_base`. It must never be the source of truth for a logged calorie/macro number.

3. Recipes: included in the Qdrant hybrid corpus (category 2), filtered post-retrieval by structured dietary-tag metadata (vegetarian/allergies) from the user's profile.

### Architecture/file changes from this revision
- `context/indexers/` and `context/retrievers/`: now Qdrant-based (`hybrid_qdrant.py` pattern) instead of `semantic_chroma.py`. Drop Chroma dependency for the knowledge base.
- NEW `db/nutrition_data.py` or `db/seed_data/`: curated nutrition + exercise datasets (JSON/CSV) loaded into SQLite at setup/migration time.
- NEW fuzzy-match lookup logic in `nutrition_tools.py` (and workout equivalent in `plan_tools.py`) using `rapidfuzz` — add `rapidfuzz` to dependencies.
- `db/models.py`: add `source` field (`database` | `estimated`) to logged food/exercise entries for traceability.
- Infra: Qdrant (Docker Compose service for local dev, or Qdrant Cloud free tier) replaces Chroma's zero-infra embedded store — add to README setup steps and `.env.example` (QDRANT_URL/QDRANT_API_KEY).

## RAG showcase enhancements (added after reassessing RAG surface area — too thin otherwise)
Three enhancements selected to make this a stronger RAG demonstration without touching numeric reliability (nutrition/exercise facts stay structured lookup, untouched by this section):

### 1. Multi-collection knowledge base (replaces single collection)
Split the static Qdrant corpus into two collections, both hybrid (dense+BM25):
- `fitness_principles` — general articles/Q&A/myths (TDEE concepts, sleep science, periodization, supplement myths, meal-prep guides — corpus expanded beyond the original small set).
- `exercise_technique` — narrative form/technique/safety/injury-prevention text per exercise (distinct from the structured sets/reps/calories fields, which stay in SQL `seed_data`). E.g. "how to do a Romanian deadlift safely" is legitimately unstructured retrievable text even though "calories burned per minute" is a structured fact for the same exercise.
`knowledge_tools.search_knowledge_base` routes to the right collection (or searches both) based on router-classified sub-intent.

### 2. Reranking on top of hybrid retrieval
Hybrid (dense+BM25) retrieval returns top-k (~20) candidates → a **cross-encoder reranker** (local, e.g. `sentence-transformers` MiniLM cross-encoder — no extra API key/cost) rescores and trims to top 3-5 before passing context to the LLM. New `context/retrievers/reranker.py`. Improves precision, directly addresses the earlier semantic-vs-exact-match concern more rigorously than hybrid alone.

### 3. Personalized document RAG (dynamic, per-user — the strongest addition)
User can share a PDF/text (e.g. a doctor's diet chart, a trainer's plan) via WhatsApp media. This gets ingested into a **per-user-isolated Qdrant collection/namespace** and becomes retrievable only for that user's own queries — turns the RAG system from "static FAQ lookup" into a real dynamic ingestion pipeline.
- New `agent/tools/personal_doc_tools.py`: `ingest_personal_document(user_id, file)`, `search_personal_documents(user_id, query)`.
- Ingestion: download media → extract text (`pypdf`/`pdfplumber`) → chunk → embed → upsert into Qdrant tagged with hashed `user_id` metadata.
- **Critical security/isolation requirement (OWASP access control)**: every retrieval query MUST filter by the requesting user's hashed `user_id` at the Qdrant query level — never rely on the LLM to "only use relevant results"; one user's personal document must be structurally unreachable from another user's queries.
- New router intent: `upload_document` / `personal_doc_query`.
- `/forget_me` (data lifecycle command) extended to also purge that user's personal-doc vectors from Qdrant, not just SQL rows + STM thread.
- New eval dataset `dataset_personal_doc_rag.json`: must include isolation tests (user A's query must never surface user B's chunks) alongside retrieval-quality goldens.

### Scaffold/dependency changes from this section
- `context/indexers/hybrid_qdrant.py` and `retrievers/hybrid_qdrant.py`: parameterized by collection name (`fitness_principles`, `exercise_technique`, or `personal_docs_{user_hash}`).
- NEW `context/retrievers/reranker.py`.
- NEW `agent/tools/personal_doc_tools.py`.
- NEW `context/knowledge_docs/exercise_technique/` (narrative per-exercise content, separate from `db/seed_data/exercises.json` structured facts).
- New dependencies: `sentence-transformers` (cross-encoder reranker), `pypdf` or `pdfplumber` (PDF text extraction).
- New eval dataset: `dataset_personal_doc_rag.json` (Phase 8).


Recheck surfaced that this wasn't explicit anywhere as one picture — consolidated here:

| Data | Where stored | Durable/raw or compacted? |
|---|---|---|
| **Live chat turns (user + agent replies), for conversational context** | STM: LangGraph `AsyncSqliteSaver` checkpoint (SQLite), keyed by `thread_id=phone` | Compacted — `SummarizationMiddleware` periodically summarizes/trims older turns to control context size. Not a permanent verbatim transcript. |
| **Agent responses (outbound text)** | Same STM checkpoint (part of the message history LangGraph persists) | Same as above — yes we store them, but only as long as STM retains/hasn't summarized them away. |
| **Durable raw conversation log (every inbound+outbound message, unmodified)** | **NEW** `db/models.py: ConversationLog` table (phone_hash, direction in/out, modality text/voice/image, raw_text, timestamp) | Append-only, never summarized/trimmed — needed for audit, debugging, and mining real transcripts into eval goldens (tests/evals datasets need real examples, not just summaries). |
| **Structured logs (food/workout/metric/water entries)** | SQL `DailyLog` table | Durable, source of truth for scoring. |
| **Device/wearable metrics** | SQL `DeviceMetric` table | Durable. |
| **Computed daily scores** | SQL `Score` table | Durable, derived from DailyLog/DeviceMetric via scoring.py. |
| **Profile (age/weight/goals/dietary pref/timezone/units)** | SQL `User` table | Durable, source of truth. |
| **Soft preference facts** (e.g. "dislikes running") | `memory/long_term.py` fact store (SQL table, not vectorized) | Durable, lightweight notes, not embeddings. |
| **Nutrition facts & exercise database** | SQL `seed_data` tables, fuzzy-matched | Durable, static reference data (not vectors). |
| **General fitness/nutrition knowledge + exercise technique** (two collections: `fitness_principles`, `exercise_technique`) | **Qdrant** — hybrid dense+BM25 vectors, reranked (cross-encoder) before use | Durable, static curated corpora — vectorized for genuine narrative/fuzzy-query content only. |
| **Personal documents** (user-uploaded diet charts/trainer plans) | **Qdrant** — per-user isolated collection/namespace (hashed `user_id` metadata filter enforced at query time) | Durable until `/forget_me` purges that user's vectors. Only retrievable by the owning user — never cross-user. |
| **Semantic cache** (past knowledge-base queries + cached answers) | Redis, vector index (HNSW) scoped to `knowledge_tools` only | TTL-based, not personalized, never caches logging/scoring/user-specific replies. |
| **Food images** | Downloaded transiently from Twilio media URL for vision processing | NOT persisted (discarded after processing, unless user opts in) — privacy minimization decision from earlier gap-check. |

**Answering the specific questions directly:**
1. **User logs and chats**: logs (food/workout/metric/water) → SQL `DailyLog`; chats (conversation) → STM SQLite checkpoint (live context) + new durable `ConversationLog` table (raw audit trail) — previously only the STM copy existed in the plan, which would lose exact history to summarization over time. Added `ConversationLog` to fix that gap.
2. **Are responses stored?**: Yes — agent replies are part of the STM message history (used for context) AND, with the new `ConversationLog` table, also durably logged verbatim for audit/eval purposes.
3. **What's in vectors?**: Only the general fitness/nutrition knowledge + exercise-technique corpora (Qdrant, hybrid dense+BM25, reranked) + per-user personal documents (Qdrant, isolated by hashed user_id), plus the Redis semantic cache's query embeddings (not the same data — that's cached Q&A pairs). Nothing else is vectorized: not chat history, not logs, not nutrition/exercise numeric facts, not profile data.


```
ai_fitness_coach_rag/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── config.yaml
│
├── ai_fitness_coach_rag/
│   ├── __init__.py
│   ├── main.py                              # FastAPI app entrypoint, scheduler startup
│   ├── config.py                            # load config.yaml + env vars
│   │
│   ├── whatsapp/
│   │   ├── __init__.py
│   │   ├── webhook.py                       # /webhook/twilio route, signature validation, idempotency
│   │   └── twilio_client.py                 # send_text(), send_media()
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── factory.py                       # build_agent()
│   │   ├── orchestrator.py                  # handle_message(user_id, text)
│   │   ├── router.py                        # intent/guardrail classifier + pending-flow-state check
│   │   ├── state.py                         # pending-flow/session state helpers (confirm expiry, onboarding-in-progress)
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── logging_tools.py             # log_food, log_workout, log_metric, log_water
│   │       ├── nutrition_tools.py           # lookup_nutrition
│   │       ├── onboarding_tools.py          # capture_profile_field, onboarding state machine
│   │       ├── calc_tools.py                # get_daily_score, get_summary, get_goal_projection
│   │       ├── knowledge_tools.py           # search_knowledge_base (RAG + semantic cache gate, routes collections)
│   │       ├── personal_doc_tools.py        # ingest_personal_document, search_personal_documents (per-user isolated)
│   │       ├── plan_tools.py                # get_meal_plan, get_workout_plan
│   │       ├── vision_tools.py              # estimate_calories_from_image
│   │       └── profile_tools.py             # get_profile, update_profile, forget_me (also purges personal-doc vectors)
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── factory.py                       # get_llm, get_embedder, get_vision_llm, get_stt
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── short_term.py                    # AsyncSqliteSaver + SummarizationMiddleware
│   │   └── long_term.py                     # per-user soft-preference fact store
│   │
│   ├── context/
│   │   ├── __init__.py
│   │   ├── indexers/
│   │   │   ├── __init__.py
│   │   │   ├── factory.py
│   │   │   └── hybrid_qdrant.py              # dense+BM25 hybrid indexing, parameterized by collection name
│   │   ├── retrievers/
│   │   │   ├── __init__.py
│   │   │   ├── factory.py
│   │   │   ├── hybrid_qdrant.py
│   │   │   └── reranker.py                   # NEW: cross-encoder rerank of top-k hybrid results
│   │   └── knowledge_docs/
│   │       ├── fitness_principles/           # -> Qdrant collection: fitness_principles
│   │       │   └── *.md
│   │       └── exercise_technique/           # -> Qdrant collection: exercise_technique (narrative form/safety)
│   │           └── *.md
│   │
│   ├── cache/
│   │   ├── __init__.py
│   │   └── semantic_cache.py                # Redis semantic cache (knowledge_tools only)
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py                        # User, DailyLog, DeviceMetric, Score, Plan, ConversationLog (+ source: database|estimated)
│   │   ├── session.py                       # engine/session factory
│   │   ├── scoring.py                       # BMR/TDEE, daily score, trend projection (pure functions)
│   │   └── seed_data/
│   │       ├── nutrition_facts.json         # curated ~100-200 foods/dishes, structured lookup (not vectorized)
│   │       └── exercises.json                # curated ~100-200 exercises, structured lookup (not vectorized)
│   │
│   ├── jobs/
│   │   ├── __init__.py
│   │   └── morning_nudge.py                 # APScheduler daily job
│   │
│   ├── integrations/
│   │   └── __init__.py                      # placeholder for future Fitbit stretch integration
│   │
│   └── observability/
│       ├── __init__.py
│       └── logger.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                          # shared fixtures (tmp db, tmp chroma dir)
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_scoring.py
│   │   ├── test_tools.py
│   │   ├── test_router.py                   # guardrail/intent classification unit tests
│   │   └── test_webhook.py                  # signature validation + idempotency
│   └── evals/
│       ├── __init__.py
│       ├── conftest.py
│       ├── metrics.py
│       ├── dataset_guardrails.json
│       ├── dataset_logging_agent.json
│       ├── dataset_rag_nutrition.json
│       ├── dataset_summary_scoring.json
│       ├── dataset_onboarding.json
│       ├── dataset_personal_doc_rag.json    # NEW: retrieval quality + cross-user isolation tests
│       ├── test_guardrails.py
│       ├── test_logging_agent.py
│       ├── test_rag_pipeline.py
│       ├── test_onboarding.py
│       └── test_personal_doc_isolation.py   # NEW: asserts user A query never returns user B chunks
│
└── data/
    └── fixtures/
        ├── sample_device_data.csv
        ├── sample_food_image.jpg
        └── sample_onboarding_transcript.json
```
