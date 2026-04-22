# AI SDR Lead Research Agent

## Project
Multi-agent AI system for researching B2B SaaS companies (seed–Series B). Input: company URL. Output: one-page dossier with company profile, decision-maker contact, buying signals, fit score (0–100), and personalized outreach email.

## Stack
- Python 3.11, FastAPI, LangGraph 1.1 (`langgraph>=1.1,<1.2`, `langchain>=1.0,<1.1`)
- LLMs: Gemini 2.5 Flash-Lite (agents), OpenAI GPT-4o-mini (email writer only)
- Tools: Tavily (search), Hunter.io (email), httpx+BeautifulSoup (scrape)
- Persistence: Supabase Postgres via `AsyncPostgresSaver`
- UI: Chainlit v2 mounted on FastAPI at `/chainlit`
- Observability: Langfuse v3
- Package manager: **uv only** (never pip)

## Architecture Rules
- State: `TypedDict` with `Annotated` reducers, never Pydantic
- Supervisor: tool-calling pattern via `langchain.agents.create_agent`, never `create_supervisor`
- Run company_researcher + contact_finder + signal_detector in parallel (one super-step)
- Human-in-the-loop: `interrupt()` before email send; resume with `Command(resume=...)`
- thread_id format: `lead:{domain}`
- Durability: `"async"` default, `"sync"` around interrupts
- Mount Chainlit **last** in FastAPI or routes 404

## Commands
- Install: `uv sync`
- Run: `uv run uvicorn src.saas_lead_agent.api.main:app --reload --port 8080`
- Test: `uv run pytest -x --ff`
- Lint: `uv run ruff check`
- Type check: `uv run mypy src/`

## Conventions
- Branch: `feat/<slug>`, `fix/<slug>`, `refactor/<slug>`
- Commits: Conventional Commits, one per verified step
- Secrets: `.env` (gitignored); never commit keys
- Never send real client PII through Gemini free tier

## Gotchas
- Gemini model string: `"gemini-2.5-flash-lite"`
- Langfuse: `from langfuse.langchain import CallbackHandler`
- `langgraph-prebuilt` has shipped breaking changes on patch versions — pin every sub-package explicitly
- Scraper needs realistic User-Agent headers or sites block requests

## Folder Structure
src/saas_lead_agent/
graph.py            # StateGraph assembly
state.py            # TypedDict LeadState
agents/             # orchestrator, company_researcher, contact_finder, signal_detector, dossier_writer
tools/              # web_search, scraper, hunter
memory/             # checkpointer, store
api/                # main (FastAPI+Chainlit mount), routes, schemas
cl_app.py             # Chainlit entry
specs/                # in-progress/ and done/
decisions.md          # append-only ADRs
TODO.md               # live state

## External Docs
Use Context7 MCP for current API shapes on: FastAPI, LangGraph, Pydantic v2, SQLAlchemy. Do not rely on training data.