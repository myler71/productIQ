# ProductIQ — AI Retail Decision Engine

> Turn your store data into business decisions. Built for the Egyptian market — bilingual (Arabic/English), EGP-native.

ProductIQ is an AI decision-support platform for Egyptian retailers. Upload sales + inventory CSVs → get deterministic analytics, AI recommendations (Arabic/English), Product DNA profiles, a weekly CEO report, and a what-if decision simulator.

**Core principle:** the code does the math, the LLM does the reasoning. Deterministic Pandas analytics compute the numbers; LangChain + Groq turn them into plain-language decisions.

---

## The 5 Engines

| Engine | What it does | How |
|---|---|---|
| **Core Analytics** | Top sellers, slow movers, dead stock, turnover, margins, stock risk | Pandas (deterministic) |
| **AI Recommendations** | Restock / discount / bundle / remove, with reasoning + confidence, AR + EN | LangChain + Groq |
| **Product DNA** | 8-dimension visual fingerprint + health score, side-by-side compare | Deterministic scoring → Chart.js radar |
| **Weekly CEO Report** | Executive summary, revenue, action items, supplier alerts — printable | LLM-generated, bilingual |
| **What-If Simulator** | Price/discount scenarios → demand, revenue, profit, risk + stated assumptions | LLM with honest-assumption JSON |
| **AI Board Meeting** | CFO, Marketing, Inventory & CEO agents debate a product, CEO delivers the final verdict | Multi-agent sequential LLM chain |

All AI features degrade gracefully to deterministic rule-based output if the LLM is offline — **the demo never breaks**.

---

## Quick Start

### 1. Backend

```powershell
cd ProductIQ/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Then open **http://127.0.0.1:8000** — the backend serves the frontend.

API docs: **http://127.0.0.1:8000/docs**

### 2. LLM keys

Copy `backend/.env.example` → `backend/.env` and add your keys:

```
GROQ_API_KEY=your-key
GROQ_MODEL=llama-3.3-70b-versatile
```

No key? Everything still works with deterministic fallback output.

### 3. Frontend only (no backend)

Open any file in `frontend/` directly in a browser — the UI falls back to built-in mock data automatically. Perfect for a quick design demo.

### 4. Sample data

The Egyptian electronics-shop dataset (10 products, ~330 sales over 4 months, 5 suppliers) is pre-generated in `datasets/` and `frontend/assets/sample-data/`. Regenerate:

```powershell
python datasets/generate_sample_data.py
```

---

## Project Structure

```
ProductIQ/
├── frontend/                  # Vanilla HTML/CSS/JS — no build step
│   ├── index.html             # Landing page
│   ├── upload.html            # CSV upload + validation
│   ├── dashboard.html         # Analytics + AI recommendations
│   ├── product-dna.html       # DNA radar + comparison
│   ├── ceo-report.html        # Weekly executive report (printable)
│   ├── simulator.html         # What-if simulator
│   ├── board-meeting.html     # AI Board Meeting (multi-agent)
│   ├── css/                   # Design system, layout, components, RTL, responsive
│   ├── js/                    # i18n (AR/EN), charts, API client (mock fallback), utils
│   └── assets/sample-data/    # Egyptian sample CSVs
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entry + static frontend serving
│   │   ├── api/routes.py      # /api/* endpoints
│   │   ├── core/config.py     # .env config
│   │   ├── database/store.py  # In-memory DataFrame store + CSV validation
│   │   └── services/
│   │       ├── analysis/engine.py   # Deterministic Pandas analytics + DNA scoring
│   │       └── ai/                  # LLM service, chains, crew (board meeting)
│   ├── requirements.txt
│   └── .env.example
├── datasets/                  # Sample data generator + CSVs
├── notebooks/
│   └── ProductIQ_AI_Operations.ipynb   # LangChain · RAG · CrewAI · What-If
└── tests/smoke_test.py
```

---

## API Reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Service + data source status |
| `/api/load-sample` | POST | Load bundled Egyptian dataset |
| `/api/upload` | POST | Upload CSV files (multipart) |
| `/api/analytics` | GET | KPIs, top sellers, trends, slow movers, stock risk |
| `/api/recommendations?lang=` | GET | AI recommendations (`en`/`ar`) |
| `/api/products` | GET | Product list |
| `/api/product-dna/{id}` | GET | 8-dimension DNA + health score |
| `/api/ceo-report?lang=` | POST | Weekly executive report |
| `/api/simulate` | POST | What-if simulation |
| `/api/board-meeting` | POST | 4-agent board meeting on a product |

---

## The AI Operations Notebook

`notebooks/ProductIQ_AI_Operations.ipynb` demonstrates every AI pattern in one place:

1. **LangChain** — structured JSON recommendations (Pydantic + Groq)
2. **RAG** — FAISS vector search over a product knowledge base
3. **CrewAI** — 4-agent board meeting (CEO/CFO/Marketing/Inventory)
4. **What-If** — simulation chain with stated assumptions

---

## Design System

- **Colors:** Deep navy `#0B1F3A` · Teal `#00A6A6` · Gold `#D4A537`
- **Fonts:** Inter (EN) + Cairo (AR) — full RTL layout mirroring
- **Charts:** Chart.js (bar / line / doughnut / radar)
- **No framework, no build step** — open and run

---

## "Why not just ChatGPT + a spreadsheet?"

ProductIQ is not a chatbot. It's a domain decision engine: deterministic retail math (turnover, reorder points, tied capital) computed reliably in code, multi-file joins (sales + inventory + suppliers + pricing) done cleanly every time, a persistent bilingual interface, and AI that states its assumptions and confidence — none of which ad-hoc ChatGPT use provides.

---

## Notes

- `.env` is git-ignored. Never commit API keys.
- The frontend works standalone (mock fallback) — the backend makes it real.
- Run tests: `python tests/smoke_test.py` (from `backend/`)
