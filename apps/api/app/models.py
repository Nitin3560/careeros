import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType


class Base(DeclarativeBase):
    pass


class Vector768(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "vector(768)"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            return "[" + ",".join(str(float(item)) for item in value) + "]"

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None or isinstance(value, list):
                return value
            return [float(item) for item in str(value).strip("[]").split(",") if item]

        return process


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["CandidateProfile"] = relationship(
        back_populates="user", uselist=False
    )


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    profile_version: Mapped[int] = mapped_column(default=1, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class CandidateFact(Base):
    __tablename__ = "candidate_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    fact_key: Mapped[str] = mapped_column(String, nullable=False)
    fact_value: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="ATTESTED")
    source: Mapped[str] = mapped_column(String, nullable=False, default="user")
    project: Mapped[str | None] = mapped_column(String, nullable=True)
    project_weight: Mapped[int] = mapped_column(default=1, nullable=False)
    usability: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class CandidateEmployment(Base):
    __tablename__ = "candidate_employment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    company: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_type: Mapped[str] = mapped_column(String, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=True)
    description_text: Mapped[str] = mapped_column(String, nullable=True)
    application_url: Mapped[str] = mapped_column(String, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String, nullable=True)
    identity_key: Mapped[str | None] = mapped_column(String, nullable=True)
    queue_key: Mapped[str | None] = mapped_column(String, nullable=True)
    date_posted: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingestion_status: Mapped[str] = mapped_column(String, nullable=False, default="new")
    seen_count: Mapped[int] = mapped_column(default=1, nullable=False)
    eligible: Mapped[bool | None] = mapped_column(nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    matched_pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    filter_version: Mapped[int | None] = mapped_column(nullable=True)
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ats_boards.id"), nullable=True, deferred=True
    )
    raw_payload: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, deferred=True
    )
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True, deferred=True)
    description_status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="pending", deferred=True
    )
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    description_normalizer_version: Mapped[int] = mapped_column(
        server_default="1", nullable=False, deferred=True
    )
    description_attempts: Mapped[int] = mapped_column(server_default="0", nullable=False, deferred=True)
    description_next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, deferred=True
    )


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[int] = mapped_column(nullable=False)
    key_index: Mapped[int | None] = mapped_column(nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AtsBoard(Base):
    __tablename__ = "ats_boards"
    __table_args__ = (UniqueConstraint("ats", "slug", name="uq_ats_board"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ats: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    job_count: Mapped[int | None] = mapped_column(nullable=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(default=0, nullable=False)
    priority: Mapped[int] = mapped_column(default=3, nullable=False)
    source_list: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    tier: Mapped[str] = mapped_column(String, nullable=False, server_default="B", deferred=True)
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, deferred=True)
    poll_interval_seconds: Mapped[int] = mapped_column(server_default="3600", nullable=False, deferred=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, deferred=True)
    last_status_code: Mapped[int | None] = mapped_column(nullable=True, deferred=True)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    last_modified: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    list_hash: Mapped[str | None] = mapped_column(String, nullable=True, deferred=True)
    company_display: Mapped[str | None] = mapped_column(String, nullable=True, deferred=True)
    empty_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, deferred=True)
    not_found_count: Mapped[int] = mapped_column(server_default="0", nullable=False, deferred=True)


class CompanyRegistry(Base):
    __tablename__ = "company_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    careers_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_tags: Mapped[list[str]] = mapped_column(
        JSON().with_variant(ARRAY(Text), "postgresql"), nullable=False, default=list
    )
    priority: Mapped[int] = mapped_column(nullable=False, default=3)
    detected_ats: Mapped[str | None] = mapped_column(String, nullable=True)
    detected_slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    workday_host: Mapped[str | None] = mapped_column(Text, nullable=True)
    workday_tenant: Mapped[str | None] = mapped_column(Text, nullable=True)
    workday_site: Mapped[str | None] = mapped_column(Text, nullable=True)
    adapter_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detection_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    detection_confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    detection_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ats_boards.id"), nullable=True
    )
    last_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PollRun(Base):
    __tablename__ = "poll_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    boards_due: Mapped[int] = mapped_column(default=0, nullable=False)
    boards_polled: Mapped[int] = mapped_column(default=0, nullable=False)
    ok: Mapped[int] = mapped_column(default=0, nullable=False)
    not_modified: Mapped[int] = mapped_column(default=0, nullable=False)
    unchanged_hash: Mapped[int] = mapped_column(default=0, nullable=False)
    empty: Mapped[int] = mapped_column(default=0, nullable=False)
    failed: Mapped[int] = mapped_column(default=0, nullable=False)
    dead: Mapped[int] = mapped_column(default=0, nullable=False)
    new_jobs: Mapped[int] = mapped_column(default=0, nullable=False)
    updated_jobs: Mapped[int] = mapped_column(default=0, nullable=False)
    expired_jobs: Mapped[int] = mapped_column(default=0, nullable=False)
    reappeared_jobs: Mapped[int] = mapped_column(default=0, nullable=False)
    detail_fetches: Mapped[int] = mapped_column(default=0, nullable=False)
    p50_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class CompanyTarget(Base):
    __tablename__ = "company_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="greenhouse")
    active: Mapped[bool] = mapped_column(default=True)
    last_ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompanyIntelligence(Base):
    __tablename__ = "company_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    canonical_domain: Mapped[str | None] = mapped_column(String, nullable=True)
    ats: Mapped[str | None] = mapped_column(String, nullable=True)
    ats_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    careers_url: Mapped[str | None] = mapped_column(String, nullable=True)
    open_job_count: Mapped[int] = mapped_column(default=0, nullable=False)
    new_grad_job_count: Mapped[int] = mapped_column(default=0, nullable=False)
    matching_job_count: Mapped[int] = mapped_column(default=0, nullable=False)
    h1b_lca_1y: Mapped[int] = mapped_column(default=0, nullable=False)
    h1b_software_lca_1y: Mapped[int] = mapped_column(default=0, nullable=False)
    perm_3y: Mapped[int] = mapped_column(default=0, nullable=False)
    explicit_sponsorship_status: Mapped[str] = mapped_column(
        String, nullable=False, default="unknown"
    )
    latest_warn_notice: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    warn_severity: Mapped[str] = mapped_column(String, nullable=False, default="green")
    salary_min: Mapped[int | None] = mapped_column(nullable=True)
    salary_max: Mapped[int | None] = mapped_column(nullable=True)
    target_locations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    recruiter_profiles: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    intelligence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class JobMatch(Base):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job_match"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False
    )
    overall_score: Mapped[int | None] = mapped_column(nullable=True)
    strengths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_version: Mapped[int] = mapped_column(nullable=False, default=1)
    prompt_version: Mapped[int] = mapped_column(nullable=False, default=1)
    is_estimated: Mapped[bool] = mapped_column(default=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AiRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_type: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="started")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApplicationPacket(Base):
    __tablename__ = "application_packets"
    __table_args__ = (
        UniqueConstraint("job_id", "profile_version", name="uq_packet_job_profile_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    profile_version: Mapped[int] = mapped_column(nullable=False)
    fact_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    bullets: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resume_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_claims: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_runs.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AnswerBank(Base):
    __tablename__ = "answer_bank"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    archetype: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector768(), nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    times_used: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job_resume_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False
    )
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job_application"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False
    )
    resume_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_versions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="Applied")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    queue_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
