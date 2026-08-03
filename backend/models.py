from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now():
    return datetime.now(timezone.utc)


class Pipeline(Base):
    __tablename__ = "pipelines"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(80), default="You")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    connections: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    executions: Mapped[list["Execution"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )


class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    pipeline_id: Mapped[str] = mapped_column(ForeignKey("pipelines.id"))
    status: Mapped[str] = mapped_column(String(20), default="running")
    version: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_files: Mapped[list] = mapped_column(JSON, default=list)
    output_rows: Mapped[int] = mapped_column(Integer, default=0)
    validation_errors: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[int] = mapped_column(Integer, default=0)
    user: Mapped[str] = mapped_column(String(80), default="You")
    log: Mapped[list] = mapped_column(JSON, default=list)
    node_results: Mapped[list] = mapped_column(JSON, default=list)
    pipeline: Mapped[Pipeline] = relationship(back_populates="executions")
