# AgentBench

AgentBench is a minimal FastAPI service scaffold for evaluating agent systems.

## Setup

Create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the API:

```powershell
uvicorn app.main:app --reload
```

Run the tests:

```powershell
pytest
```
