from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.database.db import get_connection, init_db, seed_database
from backend.services.component_service import (
    get_analytics,
    get_machines,
    get_component_detail,
    get_component_events,
    get_component_risk,
    get_components,
    get_model_metrics,
    get_overview,
)

app = FastAPI(title="MedOps Sentinel API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=False)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    seed_database()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/overview")
def overview() -> dict:
    return get_overview()


@app.get("/api/machines")
def machines() -> list[dict]:
    return get_machines()


@app.get("/api/components")
def components() -> list[dict]:
    return get_components()


@app.get("/api/components/{component_id}")
def component_detail(component_id: str) -> dict:
    try:
        return get_component_detail(component_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/components/{component_id}/events")
def component_events(component_id: str) -> list[dict]:
    return get_component_events(component_id)


@app.get("/api/components/{component_id}/risk")
def component_risk(component_id: str) -> dict:
    try:
        return get_component_risk(component_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/analytics")
def analytics() -> dict:
    return get_analytics()


@app.get("/api/model/metrics")
def model_metrics() -> dict:
    return get_model_metrics()


class SeedPayload(BaseModel):
    seed: Literal[303] = 303


@app.post("/api/seed")
def seed_database_endpoint(payload: SeedPayload) -> dict:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "ml.generate_service_data"], cwd=str(Path(__file__).resolve().parents[1]), check=True)
    subprocess.run([sys.executable, "-m", "ml.component_model"], cwd=str(Path(__file__).resolve().parents[1]), check=True)
    init_db()
    seed_database()
    return {"status": "seeded", "seed": payload.seed}
