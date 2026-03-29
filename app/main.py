from fastapi import FastAPI
from app.api.routes import strategy, sessions

app = FastAPI(
    title="F1 Strategy Analysis Platform",
    description="Historical F1 race strategy analysis and pit window recommendations",
    version="0.1.0"
)

app.include_router(strategy.router)
app.include_router(sessions.router)


@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}
