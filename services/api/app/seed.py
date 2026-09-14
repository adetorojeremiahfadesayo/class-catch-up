import os
from datetime import date, time, timedelta
from pathlib import Path

from sqlalchemy import select

from app.auth import password_hasher
from app.db import SessionLocal
from app.materials import extract_pdf, sha256_bytes, stable_segment_id
from app.models import (
    Assignment,
    AssignmentState,
    Attendance,
    AttendanceStatus,
    CoverageStatus,
    Enrollment,
    ExtractionStatus,
    LessonOccurrence,
    MappingProposal,
    MappingStatus,
    Material,
    PacketStatus,
    Role,
    SchoolClass,
    Segment,
    Tenant,
    TimetableSlot,
    Topic,
    User,
)
from app.packets import save_packet_draft
from app.storage import LocalPrivateStorage


STUDENTS = ("Ada", "Bola", "Chidi", "Dami", "Eniola", "Femi")
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "fractions-source.pdf"


def fixture_packet(segment_id: str, excerpt: str) -> dict:
    citation = {
        "segment_id": segment_id,
        "page_or_section": "page 1",
        "supporting_excerpt": excerpt,
    }
    step_details = [
        ("read-1", "read", "Read the source", excerpt, "direct_excerpt"),
        (
            "explain-1",
            "explain",
            "Connect the idea",
            "Different fraction names can describe the same amount.",
            "generated_from_source",
        ),
        (
            "worked-1",
            "worked_example",
            "Follow an example",
            "One half and two quarters represent the same amount.",
            "generated_from_source",
        ),
        (
            "practice-1",
            "practice",
            "Try it",
            "Use the source rule to identify another equivalent pair.",
            "generated_from_source",
        ),
    ]
    return {
        "title": "Catch up: Equivalent fractions",
        "objectives": ["Recognize equivalent fractions"],
        "estimated_minutes": 15,
        "steps": [
            {
                "id": step_id,
                "kind": kind,
                "title": title,
                "blocks": [
                    {
                        "text": text,
                        "content_kind": content_kind,
                        "citations": [citation],
                    }
                ],
            }
            for step_id, kind, title, text, content_kind in step_details
        ],
        "questions": [
            {
                "id": f"q-{number}",
                "prompt": "Which statement matches the source?",
                "options": {
                    "a": "Equivalent fractions can name the same amount.",
                    "b": "Equivalent fractions must use identical numbers.",
                },
                "answer_key": "a",
                "rationale": "The cited source says they name the same amount.",
                "citations": [citation],
            }
            for number in range(1, 4)
        ],
    }


def required_password(name: str) -> str:
    value = os.environ.get(name)
    if value is None or len(value) < 8:
        raise RuntimeError(f"{name} must be set to at least 8 characters")
    return value


def seed_demo() -> None:
    teacher_password = required_password("DEMO_TEACHER_PASSWORD")
    student_password = required_password("DEMO_STUDENT_PASSWORD")

    with SessionLocal.begin() as db:
        if db.scalar(select(Tenant).where(Tenant.name == "Synthetic Demo School")):
            raise RuntimeError("Synthetic demo tenant already exists")

        tenant = Tenant(name="Synthetic Demo School")
        db.add(tenant)
        db.flush()

        teacher = User(
            tenant_id=tenant.id,
            username="teacher.demo",
            display_name="Ms. Okafor",
            password_hash=password_hasher.hash(teacher_password),
            role=Role.teacher,
        )
        db.add(teacher)
        db.flush()

        school_class = SchoolClass(
            tenant_id=tenant.id,
            owner_teacher_id=teacher.id,
            name="JSS 1A",
            subject="Mathematics",
            timezone="Africa/Lagos",
        )
        db.add(school_class)
        db.flush()

        enrollments = {}
        for name in STUDENTS:
            student = User(
                tenant_id=tenant.id,
                username=f"{name.lower()}.demo",
                display_name=name,
                password_hash=password_hasher.hash(student_password),
                role=Role.student,
            )
            db.add(student)
            db.flush()
            enrollment = Enrollment(
                tenant_id=tenant.id,
                class_id=school_class.id,
                user_id=student.id,
            )
            db.add(enrollment)
            db.flush()
            enrollments[name] = enrollment

        content = FIXTURE_PATH.read_bytes()
        material = Material(
            tenant_id=tenant.id,
            class_id=school_class.id,
            filename=FIXTURE_PATH.name,
            media_type="application/pdf",
            content_hash=sha256_bytes(content),
            storage_key=f"{tenant.id}/{school_class.id}/fractions-source/v1.bin",
            version=1,
            extraction_status=ExtractionStatus.ready,
        )
        db.add(material)
        db.flush()
        LocalPrivateStorage().write(material.storage_key, content)

        segments = []
        for extracted in extract_pdf(content):
            segment = Segment(
                id=stable_segment_id(
                    material.id,
                    extracted.position,
                    extracted.text,
                    extracted.page_1_based,
                ),
                tenant_id=tenant.id,
                class_id=school_class.id,
                material_id=material.id,
                position=extracted.position,
                page_1_based=extracted.page_1_based,
                text_section=None,
                text=extracted.text,
                content_hash=sha256_bytes(extracted.text.encode("utf-8")),
            )
            db.add(segment)
            segments.append(segment)
        db.flush()

        topic_details = [
            ("Equivalent fractions", ["Recognize equivalent fractions"]),
            ("Comparing fractions", ["Compare fractions with like denominators"]),
            ("Adding fractions", ["Add fractions with like denominators"]),
        ]
        topics = []
        for index, (title, objectives) in enumerate(topic_details):
            topic = Topic(
                tenant_id=tenant.id,
                class_id=school_class.id,
                title=title,
                objectives=objectives,
            )
            db.add(topic)
            db.flush()
            topics.append(topic)
            db.add(
                MappingProposal(
                    tenant_id=tenant.id,
                    class_id=school_class.id,
                    topic_id=topic.id,
                    suggested_segment_ids=[segments[index].id],
                    approved_segment_ids=[segments[index].id],
                    unmatched=False,
                    proposal_method="synthetic_seed_fixture",
                    status=MappingStatus.approved,
                    reviewer_id=teacher.id,
                )
            )

        today = date.today()
        db.add(
            TimetableSlot(
                tenant_id=tenant.id,
                class_id=school_class.id,
                weekday=today.weekday(),
                period_key="P1",
                start_local=time(9, 0),
                end_local=time(9, 45),
                effective_from=today - timedelta(days=30),
            )
        )
        today_lesson = LessonOccurrence(
            tenant_id=tenant.id,
            class_id=school_class.id,
            local_date=today,
            period_key="P1",
            planned_topic_ids=[topics[0].id, topics[2].id],
        )
        db.add(today_lesson)

        review_lesson = LessonOccurrence(
            tenant_id=tenant.id,
            class_id=school_class.id,
            local_date=today - timedelta(days=1),
            period_key="P1",
            planned_topic_ids=[topics[0].id],
            actual_topic_ids=[topics[0].id],
            segment_ids=[segments[0].id],
            coverage_status=CoverageStatus.covered,
            revision=1,
        )
        db.add(review_lesson)
        db.flush()
        db.add(
            Attendance(
                tenant_id=tenant.id,
                lesson_id=review_lesson.id,
                student_id=enrollments["Ada"].student_id,
                status=AttendanceStatus.absent,
                revision=1,
            )
        )
        excerpt = (
            "Equivalent fractions name the same amount using different numbers."
        )
        packet = save_packet_draft(
            db,
            review_lesson,
            fixture_packet(segments[0].id, excerpt),
            expected_lesson_revision=1,
            generation_run_id=None,
        )
        packet.status = PacketStatus.published
        packet.reviewer_id = teacher.id
        packet.approved_hash = packet.content_hash
        db.add(
            Assignment(
                tenant_id=tenant.id,
                class_id=school_class.id,
                student_id=enrollments["Ada"].student_id,
                lesson_id=review_lesson.id,
                packet_revision_id=packet.id,
                state=AssignmentState.assigned,
            )
        )


if __name__ == "__main__":
    seed_demo()
    print(
        "Created synthetic demo class, six learners, fractions material, "
        "approved mappings, today's occurrence, and one fresh learner assignment."
    )
