# AgentBench

AgentBench is a benchmark platform for evaluating LLM agents on deterministic
tasks and repository-level software engineering work. It combines a FastAPI
backend, isolated Docker execution, multiple coding-agent strategies, and a
Next.js dashboard.

## Project structure

```text
AgentBench/
├── backend/
│   ├── app/                 FastAPI, CLI, models, services, and strategies
│   ├── benchmarks/          Generic benchmark tasks
│   ├── coding_benchmarks/   Repository-level coding fixtures
│   ├── docker/              Isolated Python benchmark image
│   ├── scripts/             Real end-to-end validation
│   ├── tests/               Backend test suite
│   ├── .env.example
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/                Next.js dashboard
├── results/                 Generated generic benchmark results
└── README.md
```

## Backend setup

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

The API documentation is available at `http://127.0.0.1:8000/docs`.

Provider configuration belongs in `backend/.env`. Available settings are:

- `GEMINI_API_KEY` and `GEMINI_MODEL`
- `OPENROUTER_BASE_URL` and `OPENROUTER_API_KEY`
- `OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY`, and
  `OMNIROUTE_TIMEOUT_SECONDS`

Do not commit real API keys.

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The dashboard calls the FastAPI service using
`NEXT_PUBLIC_API_BASE_URL`, which defaults to `http://127.0.0.1:8000` in
`frontend/.env.example`. Provider APIs are never called directly from the
browser.

## CLI

Run a generic benchmark from `backend/`:

```powershell
python -m app.cli run --provider openrouter --name "OpenRouter Agent" --model "MODEL_ID"
```

Run a coding benchmark:

```powershell
python -m app.cli coding-run --provider openrouter --task easy-arithmetic-helper --model "openai/gpt-4o-mini" --strategy direct
```

Supported providers are Gemini, OpenRouter, and OmniRoute. Coding benchmarks
support Direct, Planner / Executor, and Reviewer strategies.

## Docker coding environment

From `backend/`, build the isolated image with:

```powershell
docker build -f docker/agentbench-python.Dockerfile -t agentbench-python .
```

The runtime disables networking and applies CPU and memory limits. Each strategy
operates on its own copied workspace; hidden tests remain inaccessible to agents,
and visible benchmark tests are read-only.

## Real coding validation

With Docker running and the selected provider configured, run from `backend/`:

```powershell
python scripts/validate_coding_benchmark.py --task easy-arithmetic-helper --provider openrouter --model "openai/gpt-4o-mini" --strategy direct
```

The validator checks baseline failure, executes the production strategy pipeline,
runs post-change visible and hidden tests, checks regressions, and verifies that
the original fixture remains unchanged. Add `--keep-workspace` to preserve the
isolated copy for local debugging.

## Tests

Run the backend suite from `backend/`:

```powershell
pytest
```

Build the frontend from `frontend/`:

```powershell
npm install
npm run build
```

Generated result JSON files are stored in the root `results/` directory and are
ignored by Git.
