from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.config import settings


app = FastAPI(title=settings.APP_NAME)
app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "AgentBench"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
