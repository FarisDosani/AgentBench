# AgentBench frontend

Next.js dashboard for browsing coding tasks and running coding-agent benchmarks
through the AgentBench FastAPI service.

## Setup

```powershell
copy .env.example .env.local
npm install
npm run dev
```

The dashboard runs at `http://localhost:3000`. Set
`NEXT_PUBLIC_API_BASE_URL` when the API is not available at
`http://127.0.0.1:8000`.

Provider credentials belong only in the backend `.env`; never place them in a
`NEXT_PUBLIC_` variable.
