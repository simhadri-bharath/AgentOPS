"""Dataset Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import ORMBase


class DatasetCreate(ORMBase):
    name: str
    description: str | None = None


class DatasetRead(ORMBase):
    id: uuid.UUID
    name: str
    description: str | None = None
    file_path: str
    format: str
    row_count: int
    source: str = "upload"
    review_status: str = "human_reviewed"
    version: int = 1
    created_by: str | None = None
    agent_id: uuid.UUID | None = None
    category_distribution: dict[str, int] = Field(default_factory=dict)
    created_at: datetime


class DatasetListResponse(ORMBase):
    items: list[DatasetRead]
    total: int


class DatasetUploadResponse(ORMBase):
    dataset: DatasetRead
    message: str = "Dataset uploaded successfully"
    warnings: list[str] = Field(default_factory=list)


# A trajectory captured from production is what the agent did, not what it
# should have done, so a bootstrapped set has to be reviewed before it can be
# used as a regression baseline.
REVIEW_STATUSES = ["bootstrapped", "needs_review", "human_reviewed", "golden"]


class SessionHarvestRequest(ORMBase):
    agent_id: uuid.UUID
    limit_sessions: int = Field(default=20, ge=1, le=200)
    max_cases: int = Field(default=100, ge=1, le=1000)
    exclude_agentops_traffic: bool = Field(
        default=True,
        description="Skip sessions created by AgentOps itself (eval and red-team runs)",
    )


class HarvestedCase(ORMBase):
    input: str
    actual_output: str
    expected_output: str = ""
    retrieval_context: list[str] = Field(default_factory=list)
    reference_trajectory: list[dict[str, Any]] = Field(default_factory=list)
    conversation: list[dict[str, str]] = Field(default_factory=list)
    category: str = "uncategorized"
    session_id: str = ""
    invocation_id: str = ""
    tool_names: list[str] = Field(default_factory=list)
    agent_path: list[str] = Field(default_factory=list)
    health: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SessionHarvestPreview(ORMBase):
    agent_id: uuid.UUID
    total: int
    category_distribution: dict[str, int] = Field(default_factory=dict)
    preview: list[HarvestedCase] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    notice: str = (
        "reference_trajectory is what the agent did, not what it should have done. "
        "Review each row before promoting this dataset to golden."
    )


class SessionDatasetCreate(ORMBase):
    agent_id: uuid.UUID
    name: str
    description: str | None = None
    cases: list[HarvestedCase]
    created_by: str | None = None


class DatasetReviewUpdate(ORMBase):
    review_status: str

    @field_validator("review_status")
    @classmethod
    def _known_status(cls, value: str) -> str:
        if value not in REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {REVIEW_STATUSES}")
        return value
