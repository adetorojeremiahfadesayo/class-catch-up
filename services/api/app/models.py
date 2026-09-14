from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Date,
    Time,
    Boolean,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    teacher = "teacher"
    student = "student"


class EducationSystem(str, enum.Enum):
    united_states_high_school = "united_states_high_school"
    england_wales_secondary = "england_wales_secondary"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    username: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(200))
    introduction: Mapped[str | None] = mapped_column(String(500))
    selected_class_id: Mapped[str | None] = mapped_column(String(36))
    password_hash: Mapped[str] = mapped_column(String(500))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class SchoolClass(Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_teacher_id", "name"),
        Index("ix_classes_tenant_owner", "tenant_id", "owner_teacher_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    owner_teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(100), default="Africa/Lagos")
    education_system: Mapped[EducationSystem | None] = mapped_column(
        Enum(EducationSystem, native_enum=False)
    )
    level_label: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "class_id", "user_id"),
        UniqueConstraint("tenant_id", "student_id"),
        Index("ix_enrollments_scope", "tenant_id", "class_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[str] = mapped_column(String(36), default=new_id)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_token_hash", "token_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ExtractionStatus(str, enum.Enum):
    uploaded = "uploaded"
    extracting = "extracting"
    ready = "ready"
    needs_text = "needs_text"
    failed = "failed"


class MappingStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "class_id", "content_hash", "version"),
        Index("ix_materials_scope", "tenant_id", "class_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, native_enum=False)
    )
    extraction_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        UniqueConstraint("material_id", "position"),
        Index("ix_segments_scope", "tenant_id", "class_id", "material_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    position: Mapped[int] = mapped_column(Integer)
    page_1_based: Mapped[int | None] = mapped_column(Integer)
    text_section: Mapped[str | None] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "class_id", "title"),
        Index("ix_topics_scope", "tenant_id", "class_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    title: Mapped[str] = mapped_column(String(250))
    objectives: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class TimetableSlot(Base):
    __tablename__ = "timetable_slots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "class_id", "weekday", "period_key", "effective_from"
        ),
        Index("ix_timetable_scope", "tenant_id", "class_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    weekday: Mapped[int] = mapped_column(Integer)
    period_key: Mapped[str] = mapped_column(String(100))
    start_local: Mapped[time] = mapped_column(Time)
    end_local: Mapped[time] = mapped_column(Time)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class MappingProposal(Base):
    __tablename__ = "mapping_proposals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "class_id", "topic_id"),
        Index("ix_mapping_proposals_scope", "tenant_id", "class_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"))
    suggested_segment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    approved_segment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    unmatched: Mapped[bool] = mapped_column(default=False)
    proposal_method: Mapped[str] = mapped_column(String(100))
    status: Mapped[MappingStatus] = mapped_column(
        Enum(MappingStatus, native_enum=False), default=MappingStatus.pending
    )
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class CoverageStatus(str, enum.Enum):
    covered = "covered"
    partly_covered = "partly_covered"
    moved = "moved"
    not_yet_confirmed = "not_yet_confirmed"


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    unknown = "unknown"


class JobState(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    retry_wait = "retry_wait"
    failed = "failed"
    cancelled = "cancelled"


class LessonOccurrence(Base):
    __tablename__ = "lesson_occurrences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "class_id", "local_date", "period_key"),
        Index(
            "ix_lesson_occurrences_lookup",
            "tenant_id",
            "class_id",
            "local_date",
            "period_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    local_date: Mapped[date] = mapped_column(Date)
    period_key: Mapped[str] = mapped_column(String(100))
    planned_topic_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    actual_topic_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    segment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    coverage_status: Mapped[CoverageStatus] = mapped_column(
        Enum(CoverageStatus, native_enum=False),
        default=CoverageStatus.not_yet_confirmed,
    )
    moved_to_date: Mapped[date | None] = mapped_column(Date)
    moved_to_period_key: Mapped[str | None] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("tenant_id", "lesson_id", "student_id"),
        Index("ix_attendance_scope", "tenant_id", "lesson_id", "student_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lesson_occurrences.id"))
    student_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False)
    )
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class PacketJob(Base):
    __tablename__ = "packet_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        Index("ix_packet_jobs_claim", "state", "lease_until"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lesson_occurrences.id"))
    lesson_revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[JobState] = mapped_column(
        Enum(JobState, native_enum=False), default=JobState.queued
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(250))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class IdempotencyReceipt(Base):
    __tablename__ = "idempotency_receipts"
    __table_args__ = (UniqueConstraint("tenant_id", "actor_id", "request_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    request_key: Mapped[str] = mapped_column(String(200))
    operation: Mapped[str] = mapped_column(String(100))
    response_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_scope", "tenant_id", "class_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str | None] = mapped_column(ForeignKey("classes.id"))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(100))
    source_event_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class PacketStatus(str, enum.Enum):
    draft = "draft"
    needs_review = "needs_review"
    needs_revision = "needs_revision"
    approved = "approved"
    published = "published"
    superseded = "superseded"


class AssignmentState(str, enum.Enum):
    assigned = "assigned"
    opened = "opened"
    in_progress = "in_progress"
    submitted = "submitted"


class RunOutcome(str, enum.Enum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    content_gap = "content_gap"


class PacketRevision(Base):
    __tablename__ = "packet_revisions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "lesson_id", "revision_number"),
        Index("ix_packet_revisions_scope", "tenant_id", "lesson_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lesson_occurrences.id"))
    lesson_revision: Mapped[int] = mapped_column(Integer)
    revision_number: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("packet_revisions.id")
    )
    material_version_ids: Mapped[list[str]] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)
    validation_results: Mapped[dict] = mapped_column(JSON)
    status: Mapped[PacketStatus] = mapped_column(
        Enum(PacketStatus, native_enum=False)
    )
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    content_hash: Mapped[str] = mapped_column(String(64))
    approved_hash: Mapped[str | None] = mapped_column(String(64))
    generation_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.id", use_alter=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "lesson_id", "packet_revision_id"),
        Index("ix_assignments_student", "tenant_id", "student_id", "superseded_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    student_id: Mapped[str] = mapped_column(String(36))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lesson_occurrences.id"))
    packet_revision_id: Mapped[str] = mapped_column(
        ForeignKey("packet_revisions.id")
    )
    state: Mapped[AssignmentState] = mapped_column(
        Enum(AssignmentState, native_enum=False), default=AssignmentState.assigned
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    help_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_scope", "tenant_id", "lesson_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lesson_occurrences.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("packet_jobs.id"))
    actor: Mapped[str] = mapped_column(String(100), default="packet_agent")
    tools: Mapped[list[dict]] = mapped_column(JSON, default=list)
    model_config: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome: Mapped[RunOutcome] = mapped_column(
        Enum(RunOutcome, native_enum=False), default=RunOutcome.running
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExceptionRecord(Base):
    __tablename__ = "exceptions"
    __table_args__ = (
        Index("ix_exceptions_scope", "tenant_id", "class_id", "open"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    student_id: Mapped[str | None] = mapped_column(String(36))
    lesson_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesson_occurrences.id")
    )
    reason: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    open: Mapped[bool] = mapped_column(Boolean, default=True)
    source_event_id: Mapped[str | None] = mapped_column(String(36))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ProgressEvent(Base):
    __tablename__ = "progress_events"
    __table_args__ = (
        Index("ix_progress_assignment", "tenant_id", "assignment_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"))
    step_id: Mapped[str] = mapped_column(String(100))
    event: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        Index("ix_attempts_assignment", "tenant_id", "assignment_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"))
    question_id: Mapped[str] = mapped_column(String(100))
    answer: Mapped[str] = mapped_column(String(100))
    correctness: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
