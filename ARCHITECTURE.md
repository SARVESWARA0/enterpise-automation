# Enterprise Autopilot: End-to-End Architecture & Documentation

## Overview
**Enterprise Autopilot** is a next-generation, multi-agent autonomous workflow system designed for enterprise environments. It fundamentally replaces rigid, predefined workflow templates with dynamic, intent-driven execution. 

Unlike a standard chatbot that simply answers questions, the Autopilot is an active orchestrator: it listens to a high-level enterprise goal (e.g., *"Audit recent employee changes"* or *"Address SLA breaches in the engineering department"*), autonomously breaks it down into an actionable step-by-step plan, delegates tasks to specialized agents, executes real tools against the database, verifies results, and recovers from errors on the fly. All of this execution runs transparently while streaming real-time status and logs directly into a modern, native Chat UI.

---

## Core Objectives achieved for the Hackathon
1. **Autonomy Depth:** The system is capable of full intent translation. It can take a completely novel scenario, build a 5+ step execution plan dynamically, run through it using actual enterprise tools (like `execute_sql`, `create_jira_task`, etc.), and execute it to completion without further human intervention.
2. **Multi-Agent Design:** The workload is elegantly distributed among four distinct AI Agents using the Strands SDK:
   - **Planner Agent:** Ingests the raw goal and available schema/tools to generate a JSON-based dynamic execution plan.
   - **Execution Agent:** The "doer" — it receives commands and exact parameters to execute tools securely.
   - **Verification Agent:** Evaluates the JSON outputs of the Execution Agent to confirm if a task actually succeeded functionally.
   - **Recovery Agent:** Steps in upon verification failure. It analyzes the error, decides whether a retry is viable (e.g., transient error), or escalates the task (e.g., permanent failure or missing prerequisites).
3. **Enterprise Readiness:** The entire state is durably logged. An immutable **Audit Trail** ensures every decision, query, input, and output is saved. System states are preserved locally in JSON datastores, ensuring crash resilience and robust session management.
4. **Technical Creativity:** We implemented a seamless **Server-Sent Events (SSE)** architecture. Instead of relying on manual refresh buttons or static dashboard tables, all backend agent thoughts, executions, and warnings are streamed in real-time as stylized chat messages to the Next.js frontend, creating an engaging and transparent UI.

---

## Technical Stack
- **Frontend:** Next.js (React), Vanilla CSS (modern glassmorphism, dynamic gradients, responsive chat UI).
- **Backend:** Python (FastAPI, Uvicorn), `strands` Agent SDK, Asyncio.
- **Database / Data Layer:** Prisma Schema (PostgreSQL mocked via SQLite/JSON for the scope of the prototype), providing real SQL constraints to the LLM context.
- **LLM Engine:** OpenAI Compatible Model API (`gpt-4.1-nano` / equivalent configured in `.env`).

---

## End-to-End Execution Flow

### 1. Intent Capture (Frontend)
The user inputs a goal such as *"Check database constraints for recent employee additions"* into the Workflows Chat UI. The Next.js client sends an asynchronous `POST` request to `/api/workflows` and immediately navigates the user to a dedicated visual monitoring chat room (`/workflows/[id]`).

### 2. Dynamic Planning (Backend)
FastAPI accepts the workflow and spins off an asynchronous background task to begin execution. The string prompt is passed to the **Planner Agent**. The Planner is injected with a list of all raw function signatures `[t.tool_name for t in ALL_ENTERPRISE_TOOLS]` and the Prisma DB schema, and computes a dependent JSON array of execution steps (the dynamic template).

### 3. Agentic Execution Run-loop (Backend)
The orchestrator walks through each generated step sequentially:
- A `chat:agent_assigned` event is broadcasted.
- The **Execution Agent** runs the tool (e.g., querying the DB).
- The output is captured and sent to the **Verification Agent**.
- The Verification Agent replies with either `VERIFIED` or `FAILED`.
- If `VERIFIED`, the step is successfully completed (`chat:step_complete`).

### 4. Failure Recovery & Escalation (Backend)
If a step fails (e.g., no employees found, or SQL syntax error):
- The **Recovery Agent** acts on the failure. 
- It assesses the type of failure and determines if a `RETRY` or `ESCALATE` action is required.
- If retried, the Execution Agent fires again. Limits protect against infinite loops (max 2 retries). 
- If escalated, the workflow cleanly halts execution, marks itself as `ESCALATED`, and warns the user via the frontend (`chat:error`), preserving all logs up to that exact step.

### 5. Real-Time Streaming (SSE)
Every major decision, print statement, and state mutation emits a `chat:*` or `agent:*` event to a file-backed `streams` directory in the backend state. The `/api/workflows/[id]/stream` endpoint constantly tails this file and pushes the events to the Next.js frontend, transforming raw backend strings into beautiful, avatar-annotated AI chat bubbles. 

---

## How to Run It
1. **Start the Frontend:**
   ```bash
   npm install
   npm run dev
   ```
   *Runs on `http://localhost:3000`*

2. **Start the Backend:**
   ```bash
   cd backend
   .\venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```
   *Runs on `http://localhost:8000`*

3. **Usage:**
   - Navigate to **Workflows** in the sidebar.
   - Enter a dynamic goal in the input prompt (e.g., "Find recent employees who are onboarding").
   - Watch the multi-agent system securely fulfill your prompt in real-time.
