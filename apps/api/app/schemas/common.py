from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

AgentTypeLiteral = Literal["commercial", "facturation", "support", "operations"]
SuggestionStatusLiteral = Literal["draft", "approved", "rejected"]


def _check_password_bytes(v: str) -> str:
    # bcrypt ignore/refuse au-delà de 72 octets : on le signale explicitement.
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Le mot de passe ne doit pas dépasser 72 octets")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(default="", max_length=255)
    organization_name: str = Field(min_length=2, max_length=255)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return _check_password_bytes(v)

    @field_validator("organization_name", "full_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    organization_id: UUID

    model_config = {"from_attributes": True}


class IntegrationOut(BaseModel):
    id: UUID
    provider: str
    status: str
    scopes: str
    last_sync_at: datetime | None
    is_demo: bool = False

    model_config = {"from_attributes": True}


class SyncRequest(BaseModel):
    provider: Literal["gmail", "outlook", "demo"] = "gmail"
    demo: bool = False


class InsightItem(BaseModel):
    label: str
    value: str
    detail: str | None = None


class DashboardMetrics(BaseModel):
    period_start: datetime
    period_end: datetime
    hours_lost_estimate: float
    repetitive_tasks_count: int
    automation_potential_score: float
    category_breakdown: dict[str, int]
    insights: list[InsightItem]


class DiscoveredProcessOut(BaseModel):
    id: UUID
    name: str
    trigger_label: str
    steps: list
    frequency: int
    avg_duration_minutes: float

    model_config = {"from_attributes": True}


class ProcessInstanceOut(BaseModel):
    id: UUID
    process_id: UUID
    case_id: str
    timeline: list
    duration_minutes: float
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class SuggestionOut(BaseModel):
    id: UUID
    title: str
    description: str
    monthly_frequency: int
    estimated_hours_saved: float
    workflow_draft: dict | None
    status: str
    roi_score: float
    risk_notes: str | None

    model_config = {"from_attributes": True}


class SuggestionUpdate(BaseModel):
    status: SuggestionStatusLiteral


class WorkflowOut(BaseModel):
    id: UUID
    suggestion_id: UUID | None = None
    name: str
    definition: dict
    status: str
    kill_switch: bool

    model_config = {"from_attributes": True}


class WorkflowExecuteRequest(BaseModel):
    workflow_id: UUID


class WorkflowExecutionOut(BaseModel):
    id: UUID
    workflow_id: UUID
    status: str
    logs: list | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class AgentRunRequest(BaseModel):
    agent_type: AgentTypeLiteral
    task: str = Field(min_length=1, max_length=4000)


class AgentRunResponse(BaseModel):
    id: UUID
    agent_type: str
    task: str
    result: dict | None
    tools_used: list | None
    status: str

    model_config = {"from_attributes": True}


class PredictionOut(BaseModel):
    id: UUID
    prediction_type: str
    entity_ref: str
    score: float
    explanation: str

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: UUID
    subject: str | None
    sender: str | None
    category: str
    confidence: float
    occurred_at: datetime


class AuditLogOut(BaseModel):
    id: UUID
    action: str
    actor: str | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
