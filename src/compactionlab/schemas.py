"""Transport-independent records. Schema validity is not evidence of truth."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Event(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    source: Literal["user", "tool", "assistant", "document"]
    text: str = Field(min_length=1, max_length=12000)


class MemoryRecord(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    kind: Literal["requirement", "fact", "decision", "task", "evidence", "artifact"]
    text: str = Field(min_length=1, max_length=1600)
    source_ids: list[str] = Field(min_length=1, max_length=20)
    entity: str = Field(default="", max_length=100)
    applies_to: str = Field(default="", max_length=100)
    state: Literal["active", "completed", "uncertain"] = "active"
    supersedes: list[str] = Field(default_factory=list, max_length=20)
    depends_on: list[str] = Field(default_factory=list, max_length=20)


class WriteBatch(StrictModel):
    expected_revision: int = Field(ge=0)
    events: list[Event] = Field(default_factory=list, max_length=100)
    records: list[MemoryRecord] = Field(default_factory=list, max_length=100)


class ContextRequest(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["plain", "structured"] = "structured"
    byte_budget: int = Field(default=6000, ge=256, le=32000)


class MemoryExtraction(StrictModel):
    records: list[MemoryRecord] = Field(max_length=40)


class Summary(StrictModel):
    summary: str = Field(min_length=1, max_length=6000)


class Continuation(StrictModel):
    """Declared state probe; this is not an executable agent action."""

    facts: dict[str, str]
    next_actions: list[str] = Field(max_length=20)
    complete: bool
    evidence_ids: list[str] = Field(max_length=20)


class ExperimentRequest(StrictModel):
    writer_model: str = Field(default="qwen3:4b", min_length=1, max_length=100)
    reader_model: str = Field(default="qwen3:8b", min_length=1, max_length=100)
    cases: list[Literal["release_handoff", "conversation", "budgeting"]] = Field(
        default_factory=lambda: ["release_handoff", "conversation", "budgeting"],
        min_length=1,
        max_length=3,
    )
    repetitions: int = Field(default=1, ge=1, le=5)
    byte_budget: int = Field(default=6000, ge=256, le=12000)
    seed: int = Field(default=42, ge=0, le=1000000)
