from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import replay, strategy, sessions

app = FastAPI(
    title="F1 Strategy Analysis Platform",
    description="Historical F1 race strategy analysis and pit window recommendations",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(strategy.router)
app.include_router(sessions.router)
app.include_router(replay.router)


@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}


frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/")
    def serve_frontend():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/replay-view/{session_key}")
    def serve_replay_view(session_key: int):
        return FileResponse(frontend_dist / "index.html")
