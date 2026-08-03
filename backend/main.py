import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Support both `python -m backend.main` and direct `python backend/main.py`.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "backend"

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .database import Base, UPLOAD_DIR, engine, get_db
from .models import Execution, Pipeline
from .pipeline import PipelineEngine
from .pipeline.engine import NodeExecutionError
from .schemas import ExecutionOut, PipelineCreate, PipelineOut, PipelineUpdate

Base.metadata.create_all(engine)
app = FastAPI(title="DataFlow Studio API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def out(p: Pipeline) -> PipelineOut:
    latest = max(p.executions, key=lambda x: x.started_at, default=None)
    return PipelineOut.model_validate({
        **{k: getattr(p, k) for k in ("id", "name", "description", "created_by", "tags", "favorite", "version", "nodes", "connections", "created_at", "updated_at")},
        "input_count": sum(n.get("type") == "input" for n in p.nodes),
        "step_count": len(p.nodes),
        "last_status": latest.status if latest else "never",
        "last_run": latest.started_at if latest else None,
    })


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/pipelines", response_model=list[PipelineOut])
def pipelines(db: Session = Depends(get_db)):
    return [out(p) for p in db.scalars(select(Pipeline).order_by(desc(Pipeline.updated_at))).all()]


@app.post("/api/pipelines", response_model=PipelineOut)
def create(payload: PipelineCreate, db: Session = Depends(get_db)):
    p = Pipeline(**payload.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return out(p)


@app.get("/api/pipelines/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(pipeline_id: str, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p: raise HTTPException(404, "Pipeline not found")
    return out(p)


@app.put("/api/pipelines/{pipeline_id}", response_model=PipelineOut)
def update(pipeline_id: str, payload: PipelineUpdate, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p: raise HTTPException(404, "Pipeline not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(p, key, value)
    p.version += 1; p.updated_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(p)
    return out(p)


@app.delete("/api/pipelines/{pipeline_id}", status_code=204)
def delete(pipeline_id: str, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p: raise HTTPException(404, "Pipeline not found")
    db.delete(p); db.commit()


@app.post("/api/pipelines/{pipeline_id}/duplicate", response_model=PipelineOut)
def duplicate(pipeline_id: str, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p: raise HTTPException(404, "Pipeline not found")
    copy = Pipeline(name=f"{p.name} (copy)", description=p.description, tags=p.tags, nodes=p.nodes, connections=p.connections)
    db.add(copy); db.commit(); db.refresh(copy)
    return out(copy)


@app.post("/api/uploads")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".csv", ".tsv", ".xlsx", ".parquet"}: raise HTTPException(400, "Unsupported file type")
    stored = f"{uuid4()}{ext}"
    with (UPLOAD_DIR / stored).open("wb") as target: shutil.copyfileobj(file.file, target)
    frame = PipelineEngine().load({"storedName": stored})
    from .pipeline.engine import preview
    return {"originalName": file.filename, "storedName": stored, "size": (UPLOAD_DIR / stored).stat().st_size, "preview": preview(frame)}


@app.post("/api/pipelines/{pipeline_id}/run", response_model=ExecutionOut)
def run(pipeline_id: str, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p: raise HTTPException(404, "Pipeline not found")
    return execute_pipeline(p, p.nodes, db)


@app.post("/api/pipelines/{pipeline_id}/run-to/{node_id}", response_model=ExecutionOut)
def run_to_node(pipeline_id: str, node_id: str, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p: raise HTTPException(404, "Pipeline not found")
    node_index = next((index for index, node in enumerate(p.nodes) if node.get("id") == node_id), None)
    if node_index is None: raise HTTPException(404, "Pipeline step not found")
    return execute_pipeline(p, p.nodes[:node_index + 1], db)


def execute_pipeline(p: Pipeline, nodes: list[dict], db: Session) -> Execution:
    execution = Execution(pipeline_id=p.id, version=p.version, status="running")
    db.add(execution); db.commit()
    try:
        result = PipelineEngine().run(nodes)
        execution.status = "success"; execution.duration_ms = result["durationMs"]
        execution.output_rows = result["outputRows"]; execution.validation_errors = result["validationErrors"]
        execution.log = result["log"]; execution.node_results = result["nodeResults"]
    except NodeExecutionError as exc:
        execution.status = "failed"; execution.duration_ms = exc.duration_ms
        execution.log = exc.logs; execution.node_results = exc.results
    except Exception as exc:
        execution.status = "failed"; execution.log = [str(exc)]
    execution.finished_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(execution)
    return execution


@app.get("/api/executions", response_model=list[ExecutionOut])
def history(limit: int = 50, db: Session = Depends(get_db)):
    return db.scalars(select(Execution).order_by(desc(Execution.started_at)).limit(limit)).all()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
