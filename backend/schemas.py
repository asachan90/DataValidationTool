from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PipelineBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    created_by: str = "You"
    tags: list[str] = []
    favorite: bool = False
    nodes: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []


class PipelineCreate(PipelineBase):
    pass


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    favorite: bool | None = None
    nodes: list[dict[str, Any]] | None = None
    connections: list[dict[str, Any]] | None = None


class PipelineOut(PipelineBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    version: int
    created_at: datetime
    updated_at: datetime
    input_count: int = 0
    step_count: int = 0
    last_status: str = "never"
    last_run: datetime | None = None


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    pipeline_id: str
    status: str
    version: int
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int
    output_rows: int
    validation_errors: int
    warnings: int
    log: list
    node_results: list
