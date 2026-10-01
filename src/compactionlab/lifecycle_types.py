"""Typed event transport and probe outputs, separate from fixtures and grading."""

from typing import Literal

from pydantic import Field

from compactionlab.schemas import InferenceSettings, StrictModel


class LedgerEvent(StrictModel):
    id: str
    entity: str
    kind: Literal["goal", "constraint", "task", "note", "claim"]
    source: Literal["user", "tool", "assistant"]
    text: str
    revision: str = ""
    value: str = ""
    state: Literal["", "active", "pending", "completed", "canceled"] = ""
    action: str = ""
    requires: list[str] = Field(default_factory=list)
    replaces: list[str] = Field(default_factory=list)

    def packet(self):
        return {key: value for key, value in self.model_dump().items() if value not in ("", [])}


class LifecycleFacts(StrictModel):
    revision: Literal["R1", "R2", "unknown"]
    current_value: str
    task_state: Literal["pending", "completed", "canceled", "unknown"]


class LifecycleAnswer(StrictModel):
    facts: LifecycleFacts
    next_actions: list[str] = Field(max_length=8)
    completed_actions: list[str] = Field(max_length=8)
    complete: bool
    fact_source_ids: list[str] = Field(max_length=12)
    completion_evidence_ids: list[str] = Field(max_length=12)


class LifecycleRequest(StrictModel):
    reader_model: str = Field(default="qwen3:8b", min_length=1, max_length=100)
    token_budget: int = Field(default=512, ge=128, le=2048)
    seed: int = Field(default=314159, ge=0, le=1000000)
    reader_settings: InferenceSettings = Field(default_factory=InferenceSettings)
