# Enterprise Autopilot

An AI-assisted enterprise workflow platform that combines a **Next.js** dashboard, a **FastAPI** backend, **PostgreSQL**, and **Strands**-based multi-agent orchestration (interpreter, execution, verification, recovery, and context-handling agents) with tools exposed through an **MCP** server. The system supports natural-language workflow requests, onboarding automation, approvals, SLA-related flows, and live progress via streaming.

---

## Table of contents

1. [Architecture overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [PostgreSQL setup](#postgresql-setup)
4. [Repository setup](#repository-setup)
5. [Environment variables](#environment-variables)
6. [Prisma (database schema and seed)](#prisma-database-schema-and-seed)
7. [Backend setup and run](#backend-setup-and-run)
8. [Frontend setup and run](#frontend-setup-and-run)
9. [Switching the LLM provider (OpenAI vs Ollama)](#switching-the-llm-provider-openai-vs-ollama)
10. [Documentation for reviewers](#documentation-for-reviewers)
11. [Troubleshooting](#troubleshooting)
12. [Security notes for submission](#security-notes-for-submission)

---

## Architecture overview


| Layer           | Technology                                 | Role                                                                                  |
| --------------- | ------------------------------------------ | ------------------------------------------------------------------------------------- |
| **Frontend**    | Next.js (App Router), TypeScript           | Employees, workflows, tasks, onboarding, audits, SLA views; calls the REST API.       |
| **Backend API** | FastAPI                                    | HTTP API, SSE streams, workflow engine integration, background tasks.                 |
| **Agents**      | Strands (`Agent`, OpenAI or Ollama models) | Planning, tool execution, verification, recovery, parameter resolution.               |
| **Tools**       | MCP (stdio)                                | SQL, email, integrations exposed to agents.                                           |
| **Database**    | PostgreSQL                                 | Shared schema managed with Prisma; backend uses `psycopg2` against the same database. |


The shared model configuration lives in `backend/agents/model_provider.py` (`get_model()`). All agents use this factory so you can switch providers in one place via environment variables.

---

## Prerequisites

- **Node.js** 20+ (LTS recommended) and **npm**
- **Python** 3.11+ (3.12+ supported)
- **PostgreSQL** 14+ (local or hosted)
- **Git**

Optional (only if using local open-source models):

- **Ollama** installed and running ([ollama.ai](https://ollama.ai)), with a suitable model pulled (e.g. `ollama pull llama3.1`)

---

## PostgreSQL setup

Create a database and user (adjust names and passwords to match your environment).

**Using `psql`:**

```bash
# Connect as a superuser (e.g. postgres)
psql -U postgres -h localhost

-- Inside psql:
CREATE DATABASE enterprise_autopilot;
CREATE USER autopilot WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE enterprise_autopilot TO autopilot;
\q
```

**Connection string format** (used by Prisma and the backend):

```text
postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME
```

Example for local default port:

```text
postgresql://autopilot:your_secure_password@localhost:5432/enterprise_autopilot
```

---

## Repository setup

```bash
git clone <your-repo-url>
cd ET-2
```

Install frontend dependencies from the **repository root**:

```bash
npm install
```

---

## Environment variables

Do **not** commit real API keys or passwords. Copy the examples below into local files only.

### Frontend — repository root (`.env` or `.env.local`)

Next.js reads env files from the project root. The app uses:


| Variable       | Required             | Description                                                                                              |
| -------------- | -------------------- | -------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL` | Yes (for Prisma CLI) | PostgreSQL URL for `prisma migrate`, `db push`, and `db seed`. Must match the database the backend uses. |


Example (root `.env.local`):

```env
DATABASE_URL="postgresql://autopilot:your_secure_password@localhost:5432/enterprise_autopilot"
```

**API base URL:** Pages default to `http://localhost:8000` if unset. To point the UI at another host (e.g. deployed API), set:


| Variable              | Required | Description                                                                        |
| --------------------- | -------- | ---------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL` | No       | Base URL of the FastAPI backend (no trailing slash), e.g. `http://localhost:8000`. |


```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend — `backend/.env`

The FastAPI app loads `backend/.env` (via `python-dotenv`). The database layer accepts either name:


| Variable                   | Required          | Description                                                                                                                     |
| -------------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL` or `DB_URL` | Yes               | Same PostgreSQL connection string as the frontend Prisma setup.                                                                 |
| `OPENAI_API_KEY`           | Yes (OpenAI path) | API key for the OpenAI-compatible endpoint.                                                                                     |
| `OPENAI_MODEL_ID`          | No                | Model name your proxy or OpenAI serves (default in code: `gpt-4.1-nano` if unset).                                              |
| `STATE_DIR`                | No                | Directory for workflow stream state files (default relative to backend if configured in your env).                              |
| `SMTP_SERVER`              | No*               | SMTP host for email-related tools (e.g. `smtp.gmail.com`).                                                                      |
| `SMTP_PORT`                | No*               | SMTP port (e.g. `465`).                                                                                                         |
| `SMTP_USERNAME`            | No*               | SMTP username.                                                                                                                  |
| `SMTP_PASSWORD`            | No*               | SMTP app password or secret.                                                                                                    |


Required only if you exercise features that send email through the configured SMTP.

Example `backend/.env` (placeholders only):

```env
# Database (same logical DB as Prisma)
DATABASE_URL=postgresql://autopilot:your_secure_password@localhost:5432/enterprise_autopilot


OPENAI_API_KEY=your_key_here

OPENAI_MODEL_ID=gpt-5-mini

# Optional persistence for streams
STATE_DIR=./state

# Optional SMTP
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_app_password
```

---

## Prisma (database schema and seed)

Run these commands from the **repository root** (where `package.json` and `prisma/schema.prisma` live).

1. **Generate the Prisma Client**
  ```bash
   npx prisma generate
  ```
2. **Apply the schema to the database**
  If the repository does not yet include migration history, sync the schema with either:
   Or, to create a proper migration for version control:
3. **Seed sample data** (employees and related tables cleared/recreated per `prisma/seed.ts`)
  ```bash
   npx prisma db seed
  ```

The backend also runs startup hooks (`ensure_enterprise_tables`, etc.) against the same database; keeping Prisma and the backend on **one** `DATABASE_URL` avoids drift.

---

## Backend setup and run

From the repository root:

```bash
cd backend
python -m venv .venv
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Ensure `backend/.env` is filled out (see [Backend — `backend/.env](#backend---backendenv)`).

**Start the API** (default port **8000** as defined in `backend/main.py`):

```bash
python main.py
```

Or explicitly with Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- API: `http://localhost:8000`  
- Interactive docs: `http://localhost:8000/docs`

---

## Frontend setup and run

From the **repository root** (with root `.env` / `.env.local` and `NEXT_PUBLIC_API_URL` aligned with the backend):

```bash
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** in the browser.

**Production build (optional):**

```bash
npm run build
npm run start
```

---

## Switching the LLM provider (OpenAI vs Ollama)

The backend uses a single **model provider** module: `backend/agents/model_provider.py`. It supports:

1. **OpenAI-compatible HTTP APIs** (default), including **proxy gateways** — set `OPENAI_BASE_URL` and `OPENAI_API_KEY` accordingly.
2. **Ollama** (local open-source models via Strands `OllamaModel`).

Dependencies: `requirements.txt` includes `strands-agents[ollama]` so the Ollama client is available when you choose that provider.

### Default: OpenAI or proxy

- Leave `STRANDS_MODEL_PROVIDER` unset, or set `STRANDS_MODEL_PROVIDER=openai`.  
- Configure `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, and optional `OPENAI_MODEL_ID`.

### Local open-source models: Ollama

1. Install and start Ollama; pull a model, e.g. `ollama pull llama3.1`.
2. In `backend/.env`, set:

```env
STRANDS_MODEL_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL_ID=llama3.1
```

Optional tuning (supported by the factory):


| Variable             | Description                                         |
| -------------------- | --------------------------------------------------- |
| `OLLAMA_TEMPERATURE` | Sampling temperature.                               |
| `OLLAMA_TOP_P`       | Nucleus sampling.                                   |
| `OLLAMA_MAX_TOKENS`  | Max tokens to generate.                             |
| `OLLAMA_KEEP_ALIVE`  | How long the model stays loaded (e.g. `5m`, `10m`). |


Choose a model that supports **tool calling** and structured behavior if you rely heavily on agent tools; smaller models may not match hosted API quality.

---

## Documentation for reviewers

For a deeper understanding of **agents, orchestration, and workflows**, see:

- `[docs/agents-orchestration.md](docs/agents-orchestration.md)` — agent roles and orchestration flow.  
- `[docs/architecture_review.md](docs/architecture_review.md)` — architectural notes and review context.

These documents are the recommended starting point after this README.

---

## Troubleshooting


| Issue                                                     | What to check                                                                                                         |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL or DB_URL environment variable is required` | `backend/.env` includes `DATABASE_URL` or `DB_URL`.                                                                   |
| Prisma errors                                             | Root `.env` / `.env.local` has `DATABASE_URL`; PostgreSQL is running; database exists.                                |
| Frontend cannot reach API                                 | `NEXT_PUBLIC_API_URL` matches where Uvicorn is bound; CORS is permissive in dev (`allow_origins=["*"]` in `main.py`). |
| LLM errors (OpenAI path)                                  | `OPENAI_API_KEY` and, if using a proxy, `OPENAI_BASE_URL` and model id match what the gateway expects.                |
| Ollama errors                                             | `ollama serve` running; `OLLAMA_HOST` correct; model pulled; `STRANDS_MODEL_PROVIDER=ollama`.                         |


---

## Security notes for submission

- Never commit `.env` files containing real keys; use `.env.example` patterns in documentation only.  
- Rotate any key that was ever committed to a public repository.  
- For hackathon demos, prefer short-lived keys and a non-production database.

---

## License

See the repository license file if present; otherwise treat usage terms as defined by the submitting team.
