from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class SessionResponse(BaseModel):
    user_id: str
    display_name: str
    role: Literal["teacher", "student"]
    csrf_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    role: Literal["teacher", "student"]


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=200)
    timezone: str = Field(default="Africa/Lagos", min_length=1, max_length=100)


class ClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    subject: str
    timezone: str
    education_system: (
        Literal["united_states_high_school", "england_wales_secondary"] | None
    )
    level_label: str | None


class RosterStudentResponse(BaseModel):
    user_id: str
    student_id: str
    display_name: str


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    media_type: str
    version: int
    extraction_status: Literal[
        "uploaded", "extracting", "ready", "needs_text", "failed"
    ]
    extraction_error: str | None


class SourceResponse(BaseModel):
    segment_id: str
    material_id: str
    filename: str
    page_1_based: int | None
    text_section: str | None
    supporting_excerpt: str


class TopicInput(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    objectives: list[str] = Field(default_factory=list, max_length=20)


class TopicBatchCreate(BaseModel):
    topics: list[TopicInput] = Field(min_length=1, max_length=100)


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    objectives: list[str]


class TimetableSlotCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    period_key: str = Field(min_length=1, max_length=100)
    start_local: time
    end_local: time
    effective_from: date
    effective_to: date | None = None


class TimetableSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    weekday: int
    period_key: str
    start_local: time
    end_local: time
    effective_from: date
    effective_to: date | None


class MappingApproval(BaseModel):
    segment_ids: list[str] = Field(max_length=100)


class MappingProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic_id: str
    suggested_segment_ids: list[str]
    approved_segment_ids: list[str]
    unmatched: bool
    proposal_method: str
    status: Literal["pending", "approved"]


class LessonOccurrenceCreate(BaseModel):
    local_date: date
    period_key: str = Field(min_length=1, max_length=100)
    planned_topic_ids: list[str] = Field(default_factory=list, max_length=50)


class LessonOccurrenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    class_id: str
    local_date: date
    period_key: str
    planned_topic_ids: list[str]
    actual_topic_ids: list[str]
    segment_ids: list[str]
    coverage_status: Literal[
        "covered", "partly_covered", "moved", "not_yet_confirmed"
    ]
    moved_to_date: date | None
    moved_to_period_key: str | None
    revision: int


class AttendanceInput(BaseModel):
    student_id: str
    status: Literal["present", "absent", "unknown"]


class LessonSessionSave(BaseModel):
    expected_revision: int = Field(ge=0)
    coverage_status: Literal[
        "covered", "partly_covered", "moved", "not_yet_confirmed"
    ]
    actual_topic_ids: list[str] = Field(default_factory=list, max_length=50)
    segment_ids: list[str] = Field(default_factory=list, max_length=100)
    moved_to_date: date | None = None
    moved_to_period_key: str | None = Field(default=None, max_length=100)
    attendance: list[AttendanceInput] = Field(max_length=200)


class LessonSessionResponse(BaseModel):
    lesson_id: str
    revision: int
    job_id: str | None
    job_state: str | None
    blocked_reason: str | None
    replayed: bool = False


class DayResponse(BaseModel):
    local_date: date
    occurrences: list[LessonOccurrenceResponse]
    attendance: dict[str, dict[str, str]] = Field(default_factory=dict)


class PacketResponse(BaseModel):
    id: str
    lesson_id: str
    lesson_revision: int
    revision_number: int
    parent_id: str | None
    payload: dict
    validation_results: dict
    status: Literal[
        "draft",
        "needs_review",
        "needs_revision",
        "approved",
        "published",
        "superseded",
    ]
    content_hash: str
    approved_hash: str | None
    generation_source: Literal["strands_run", "fixture_or_teacher_edit"]


class PacketEditRequest(BaseModel):
    expected_revision_number: int = Field(ge=1)
    expected_hash: str = Field(min_length=64, max_length=64)
    candidate: dict


class PacketApprovalRequest(BaseModel):
    expected_revision_number: int = Field(ge=1)
    expected_hash: str = Field(min_length=64, max_length=64)


class PacketPublicationResponse(BaseModel):
    packet_id: str
    status: Literal["published"]
    assignment_count: int


class JobResponse(BaseModel):
    id: str
    lesson_id: str
    lesson_revision: int
    state: Literal[
        "queued", "running", "succeeded", "retry_wait", "failed", "cancelled"
    ]
    attempts: int
    error_code: str | None


class AssignmentSummary(BaseModel):
    id: str
    lesson_id: str
    state: Literal["assigned", "opened", "in_progress", "submitted"]
    delivered_at: str
    help_requested: bool
    title: str


class AssignmentDetail(BaseModel):
    id: str
    lesson_id: str
    state: Literal["assigned", "opened", "in_progress", "submitted"]
    delivered_at: str
    help_requested: bool
    packet: dict
    completed_step_ids: list[str] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)


class ProgressCreate(BaseModel):
    step_id: str = Field(min_length=1, max_length=100)
    event: Literal["opened", "completed", "submitted"]


class AttemptCreate(BaseModel):
    question_id: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=100)


class AttemptResponse(BaseModel):
    attempt_id: str
    correctness: bool


class HelpCreate(BaseModel):
    step_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=400)


class ExceptionResponse(BaseModel):
    id: str
    class_id: str
    student_id: str | None
    lesson_id: str | None
    reason: str
    severity: str
    open: bool


class TeacherAssignmentResponse(BaseModel):
    id: str
    student_id: str
    lesson_id: str
    state: Literal["assigned", "opened", "in_progress", "submitted"]
    help_requested: bool
    reviewed: bool


class EducationSystemOption(BaseModel):
    id: Literal["united_states_high_school", "england_wales_secondary"]
    label: str
    class_label: str
    period_label: str
    level_label: str
    levels: list[str]
    timezones: list[str]


class TeacherOnboardingResponse(BaseModel):
    completed: bool
    teacher_display_name: str
    introduction: str
    selected_class_id: str | None
    classes: list[ClassResponse]
    education_systems: list[EducationSystemOption]


class TeacherOnboardingUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    introduction: str = Field(min_length=10, max_length=500)
    class_id: str
    education_system: Literal[
        "united_states_high_school", "england_wales_secondary"
    ]
    level_label: str = Field(min_length=1, max_length=50)
    timezone: str = Field(min_length=1, max_length=100)


class StudentSchoolContext(BaseModel):
    class_id: str
    class_name: str
    subject: str
    education_system: (
        Literal["united_states_high_school", "england_wales_secondary"] | None
    )
    education_system_label: str | None
    level_label: str | None
    period_label: str
    teacher_display_name: str
    teacher_introduction: str | None
