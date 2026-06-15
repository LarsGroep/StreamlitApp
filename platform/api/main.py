"""
LOFI Artist Intelligence — FastAPI backend.

Start:
    uvicorn api.main:app --reload --port 8000

Docs:
    http://localhost:8000/docs
"""

import sys
from pathlib import Path

# Ensure platform/ is on sys.path when run from any CWD
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import artists, dashboard, feedback, explain, discover

app = FastAPI(
    title="LOFI Artist Intelligence",
    description="Breakout detection and booking intelligence for LOFI Amsterdam.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(artists.router)
app.include_router(dashboard.router)
app.include_router(feedback.router)
app.include_router(explain.router)
app.include_router(discover.router)


@app.get("/health")
def health():
    return {"status": "ok"}
