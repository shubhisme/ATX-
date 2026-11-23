from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    STATIC_FAILED = "STATIC_FAILED"
    AI_REVIEWING = "AI_REVIEWING"
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"
    FAILED = "FAILED"


class GateCheckResponse(BaseModel):
    check_type: str  # "secret_scan" | "syntax_check"
    passed: bool
    details: list[dict]
    duration_ms: float


class GateResultResponse(BaseModel):
    passed: bool
    checks: list[GateCheckResponse]
    duration_ms: float
    failed_checks: list[str]


class FindingItem(BaseModel):
    file_path: str
    line_number: int | None = None
    severity: str  # "critical" | "warning" | "info" | "suggestion"
    category: str  # "bug" | "security" | "performance" | "style" | "logic"
    message: str
    suggestion: str | None = None


class ReviewResultResponse(BaseModel):
    findings: list[FindingItem]
    summary: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    model: str
    cached: bool = False


class JobSubmitRequest(BaseModel):
    repo_url: str | None = None
    pr_number: int | None = None
    commit_sha: str
    diff_content: str
    changed_files: list[dict]  # [{"path": str, "content": str}]
    branch: str | None = None


class JobResponse(BaseModel):
    job_id: str
    pr_number: int | None
    commit_sha: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latency_ms: int | None = None
    gate_result: GateResultResponse | None = None
    review_result: ReviewResultResponse | None = None


class BatchSubmitRequest(BaseModel):
    count: int = Field(ge=1, le=20, default=5)
    repo_path: str | None = None


class TelemetrySummary(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    cached_jobs: int
    avg_latency_ms: float
    total_tokens: int
    total_cost_usd: float
    cache_hit_rate: float
