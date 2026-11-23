"""
Shared dataclasses and enums used across all backend modules.
"""
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field


class PRStatus(str, Enum):
    QUEUED         = "QUEUED"
    STATIC_FAILED  = "STATIC_FAILED"
    AI_REVIEWING   = "AI_REVIEWING"
    COMPLETED      = "COMPLETED"
    SUPERSEDED     = "SUPERSEDED"


@dataclass
class PRSubmitRequest:
    pr_number: int
    title: str
    commit_sha: str        # 40-char hex SHA
    diff: str              # unified diff string
    files: list[str]       # list of changed file paths


@dataclass
class PRJobInsert:
    pr_number: int
    title: str
    commit_sha: str
    diff: str
    files: list[str]
    queued_at: str         # ISO-8601 UTC


@dataclass
class PRJobRow:
    id: int
    pr_number: int
    title: str
    commit_sha: str
    diff: str
    status: PRStatus
    files: list[str]
    static_result: dict | None
    review: dict | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    queued_at: str
    started_at: str | None
    completed_at: str | None
    latency_ms: int | None
    cache_hit: bool


@dataclass
class CacheRow:
    commit_sha: str
    review: dict
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    created_at: str


@dataclass
class CacheInsert:
    commit_sha: str
    review: dict
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    created_at: str


@dataclass
class WorkerStatus:
    worker_id: int
    status: str            # "idle" | "busy"
    current_job_id: int | None
