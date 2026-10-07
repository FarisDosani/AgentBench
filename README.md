# AgentBench

AgentBench is a small FastAPI and command-line benchmark runner for evaluating LLM
agents against deterministic tasks. It supports direct Gemini execution and an
OpenAI-compatible local OmniRoute provider.

## Architecture

Benchmark tasks are loaded from JSON and executed by an `AgentRunner` using the
selected provider. `ExactMatchEvaluator` scores each response, `BenchmarkRunner`
aggregates the results, and `ResultStore` saves them as JSON. The comparison service
ranks saved benchmark runs by score, latency, and agent name.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a local `.env` file with the provider settings you need. Do not commit real
keys.

## Environment variables

- `APP_NAME` — FastAPI application name.
- `APP_ENV` — application environment label.
- `GEMINI_API_KEY` — Gemini API key.
- `GEMINI_MODEL` — fallback Gemini model.
- `OMNIROUTE_BASE_URL` — OmniRoute OpenAI-compatible base URL.
- `OMNIROUTE_API_KEY` — optional OmniRoute API key.
- `OMNIROUTE_TIMEOUT_SECONDS` — provider request timeout in seconds.

## Gemini usage

```powershell
python -m app.cli run --provider gemini --name "Gemini Agent" --model "gemini-3.5-flash"
```

## OmniRoute usage

```powershell
python -m app.cli run --provider omniroute --name "OmniRoute Agent" --model "auto/best-coding"
```

## CLI

The `run` command also accepts `--system-prompt`, `--temperature`, `--max-tokens`,
`--benchmarks`, and `--results`. Gemini is the default provider.

## API

Start the API:

```powershell
uvicorn app.main:app --reload
```

The API exposes task listing, benchmark execution, saved-result access, and result
comparison under `/api`. Health status is available at `/health`.

## Benchmark workflow

Add tasks to JSON files under `benchmarks/`, run a provider through the CLI or API,
and inspect the generated JSON under `results/`. Generated result files are ignored
by Git; `results/.gitkeep` preserves the directory.

## Tests

```powershell
pytest
```
