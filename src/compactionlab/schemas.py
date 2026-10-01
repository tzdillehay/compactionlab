"""Transport-independent records. Schema validity is not evidence of truth."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    mode: Literal["plain", "structured", "compact"] = "structured"
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


class InferenceSettings(StrictModel):
    thinking: bool = False
    context_tokens: int = Field(default=8192, ge=1024, le=131072)
    max_output_tokens: int = Field(default=2048, ge=1, le=32768)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    top_k: int = Field(default=20, ge=1, le=100)
    min_p: float = Field(default=0, ge=0, le=1)

    @model_validator(mode="after")
    def reserve_input(self):
        if self.max_output_tokens >= self.context_tokens:
            raise ValueError("Output allowance must leave space for model input")
        return self

    def options(self, seed: int) -> dict:
        return {
            "seed": seed,
            "temperature": self.temperature
            if self.temperature is not None
            else (0.6 if self.thinking else 0.7),
            "top_p": self.top_p if self.top_p is not None else (0.95 if self.thinking else 0.8),
            "top_k": self.top_k,
            "min_p": self.min_p,
            "num_ctx": self.context_tokens,
            "num_predict": self.max_output_tokens,
        }


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
    token_budget: int | None = Field(default=None, ge=16, le=16000)
    writer_settings: InferenceSettings = Field(default_factory=InferenceSettings)
    reader_settings: InferenceSettings = Field(default_factory=InferenceSettings)

    @model_validator(mode="after")
    def unique_cases(self):
        if len(set(self.cases)) != len(self.cases):
            raise ValueError("Cases must be unique")
        return self


class QualificationRequest(StrictModel):
    model: str = Field(default="qwen3:8b", min_length=1, max_length=100)
    workflows: list[Literal["release_handoff", "conversation", "budgeting"]] = Field(
        default_factory=lambda: ["release_handoff", "conversation", "budgeting"],
        min_length=1,
        max_length=3,
    )
    cases_per_workflow: int = Field(default=20, ge=4, le=40)
    seed: int = Field(default=20261001, ge=0, le=2147483647)
    calculator: bool = True
    settings: InferenceSettings = Field(default_factory=InferenceSettings)

    @model_validator(mode="after")
    def unique_workflows(self):
        if len(set(self.workflows)) != len(self.workflows):
            raise ValueError("Workflows must be unique")
        return self


class RepresentationRequest(StrictModel):
    reader_model: str = Field(default="qwen3:8b", min_length=1, max_length=100)
    budgets: list[int] = Field(
        default_factory=lambda: [128, 256, 384, 512], min_length=1, max_length=6
    )
    seeds: list[int] = Field(default_factory=lambda: [42, 43, 44], min_length=1, max_length=5)
    reader_settings: InferenceSettings = Field(default_factory=InferenceSettings)

    @model_validator(mode="after")
    def unique_bounded_values(self):
        if len(set(self.budgets)) != len(self.budgets) or not all(
            16 <= budget <= 16000 for budget in self.budgets
        ):
            raise ValueError("Use unique historical allowances between 16 and 16000 tokens")
        if len(set(self.seeds)) != len(self.seeds) or not all(
            0 <= seed <= 1000000 for seed in self.seeds
        ):
            raise ValueError("Use unique seeds between 0 and 1000000")
        return self
