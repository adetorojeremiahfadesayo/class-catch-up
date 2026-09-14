from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import Principal, get_principal, require_teacher, require_teacher_read
from app.config import get_settings
from app.db import get_db
from app.materials import (
    extract_pdf,
    extract_text,
    sha256_bytes,
    stable_segment_id,
    tokenize,
)
from app.models import (
    ExtractionStatus,
    Assignment,
    Enrollment,
    MappingProposal,
    MappingStatus,
    Material,
    PacketRevision,
    PacketStatus,
    Role,
    Segment,
    TimetableSlot,
    Topic,
)
from app.routes.classes import get_owned_class
from app.schemas import (
    MappingApproval,
    MappingProposalResponse,
    MaterialResponse,
    SourceResponse,
    TimetableSlotCreate,
    TimetableSlotResponse,
    TopicBatchCreate,
    TopicResponse,
)
from app.storage import LocalPrivateStorage


router = APIRouter(tags=["materials"])
ALLOWED_MEDIA_TYPES = {"application/pdf", "text/plain"}


@router.get("/classes/{class_id}/planning")
def planning(class_id: str, principal: Principal = Depends(require_teacher_read), db: Session = Depends(get_db)):
    get_owned_class(db, principal, class_id)
    topics = db.scalars(select(Topic).where(Topic.tenant_id == principal.user.tenant_id, Topic.class_id == class_id)).all()
    segments = db.execute(select(Segment, Material).join(Material, Material.id == Segment.material_id).where(Segment.tenant_id == principal.user.tenant_id, Segment.class_id == class_id)).all()
    mappings = db.scalars(select(MappingProposal).where(MappingProposal.tenant_id == principal.user.tenant_id, MappingProposal.class_id == class_id)).all()
    return {
        "topics": [{"id": item.id, "title": item.title} for item in topics],
        "segments": [{"id": item.id, "label": f"{material.filename} · {('page ' + str(item.page_1_based)) if item.page_1_based else item.text_section}", "text": item.text} for item, material in segments],
        "mappings": [MappingProposalResponse.model_validate(item) for item in mappings],
    }


@router.post(
    "/classes/{class_id}/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_material(
    class_id: str,
    upload: UploadFile = File(...),
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    get_owned_class(db, principal, class_id)
    media_type = (upload.content_type or "").lower()
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=422, detail="Only text-based PDF and plain-text files are supported"
        )

    max_bytes = get_settings().material_max_bytes
    content = await upload.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Material exceeds the 20 MB limit")
    if not content:
        raise HTTPException(status_code=422, detail="Material is empty")
    if media_type == "application/pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="File content is not a PDF")

    content_hash = sha256_bytes(content)
    existing_versions = db.scalars(
        select(Material.version).where(
            Material.tenant_id == principal.user.tenant_id,
            Material.class_id == class_id,
            Material.content_hash == content_hash,
        )
    ).all()
    version = max(existing_versions, default=0) + 1
    material = Material(
        tenant_id=principal.user.tenant_id,
        class_id=class_id,
        filename=(upload.filename or "material")[:255],
        media_type=media_type,
        content_hash=content_hash,
        storage_key="pending",
        version=version,
        extraction_status=ExtractionStatus.uploaded,
    )
    db.add(material)
    db.flush()
    material.storage_key = (
        f"{principal.user.tenant_id}/{class_id}/{material.id}/v{version}.bin"
    )
    LocalPrivateStorage().write(material.storage_key, content)
    material.extraction_status = ExtractionStatus.extracting
    db.commit()

    try:
        extracted = (
            extract_pdf(content)
            if media_type == "application/pdf"
            else extract_text(content)
        )
    except (ValueError, UnicodeDecodeError, OSError) as error:
        material.extraction_status = ExtractionStatus.failed
        material.extraction_error = f"Text extraction failed: {type(error).__name__}"
        db.commit()
        return material

    if not extracted:
        material.extraction_status = ExtractionStatus.needs_text
        material.extraction_error = (
            "No selectable text was found. Paste text or upload a text-based PDF."
        )
        db.commit()
        return material

    for item in extracted:
        db.add(
            Segment(
                id=stable_segment_id(
                    material.id, item.position, item.text, item.page_1_based
                ),
                tenant_id=principal.user.tenant_id,
                class_id=class_id,
                material_id=material.id,
                position=item.position,
                page_1_based=item.page_1_based,
                text_section=item.text_section,
                text=item.text,
                content_hash=sha256_bytes(item.text.encode("utf-8")),
            )
        )
    material.extraction_status = ExtractionStatus.ready
    material.extraction_error = None
    db.commit()
    db.refresh(material)
    return material


@router.get("/materials/{material_id}/status", response_model=MaterialResponse)
def material_status(
    material_id: str,
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    material = db.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.tenant_id == principal.user.tenant_id,
        )
    )
    if material is None:
        raise HTTPException(status_code=404)
    get_owned_class(db, principal, material.class_id)
    return material


@router.get("/sources/{segment_id}", response_model=SourceResponse)
def source_excerpt(
    segment_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(Segment, Material)
        .join(Material, Material.id == Segment.material_id)
        .where(
            Segment.id == segment_id,
            Segment.tenant_id == principal.user.tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404)
    segment, material = row
    if principal.user.role is Role.teacher:
        get_owned_class(db, principal, segment.class_id)
    else:
        enrollment = db.scalar(
            select(Enrollment).where(
                Enrollment.tenant_id == principal.user.tenant_id,
                Enrollment.class_id == segment.class_id,
                Enrollment.user_id == principal.user.id,
            )
        )
        if enrollment is None:
            raise HTTPException(status_code=404)
        packets = db.scalars(
            select(PacketRevision)
            .join(Assignment, Assignment.packet_revision_id == PacketRevision.id)
            .where(
                Assignment.tenant_id == principal.user.tenant_id,
                Assignment.student_id == enrollment.student_id,
                Assignment.superseded_at.is_(None),
                PacketRevision.status == PacketStatus.published,
            )
        ).all()
        cited_ids = {
            citation["segment_id"]
            for packet in packets
            for step in packet.payload.get("steps", [])
            for block in step.get("blocks", [])
            for citation in block.get("citations", [])
        } | {
            citation["segment_id"]
            for packet in packets
            for question in packet.payload.get("questions", [])
            for citation in question.get("citations", [])
        }
        if segment.id not in cited_ids:
            raise HTTPException(status_code=404)
    return SourceResponse(
        segment_id=segment.id,
        material_id=material.id,
        filename=material.filename,
        page_1_based=segment.page_1_based,
        text_section=segment.text_section,
        supporting_excerpt=segment.text,
    )


@router.post(
    "/classes/{class_id}/topics",
    response_model=list[TopicResponse],
    status_code=201,
)
def create_topics(
    class_id: str,
    payload: TopicBatchCreate,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    get_owned_class(db, principal, class_id)
    topics = [
        Topic(
            tenant_id=principal.user.tenant_id,
            class_id=class_id,
            title=item.title,
            objectives=item.objectives,
        )
        for item in payload.topics
    ]
    db.add_all(topics)
    db.commit()
    return topics


@router.post(
    "/classes/{class_id}/timetable",
    response_model=TimetableSlotResponse,
    status_code=201,
)
def create_timetable_slot(
    class_id: str,
    payload: TimetableSlotCreate,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    get_owned_class(db, principal, class_id)
    if payload.end_local <= payload.start_local:
        raise HTTPException(status_code=422, detail="end_local must follow start_local")
    if payload.effective_to and payload.effective_to < payload.effective_from:
        raise HTTPException(
            status_code=422, detail="effective_to cannot precede effective_from"
        )
    slot = TimetableSlot(
        tenant_id=principal.user.tenant_id,
        class_id=class_id,
        **payload.model_dump(),
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@router.post(
    "/classes/{class_id}/mapping-proposals",
    response_model=list[MappingProposalResponse],
)
def create_mapping_proposals(
    class_id: str,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    get_owned_class(db, principal, class_id)
    topics = db.scalars(
        select(Topic).where(
            Topic.tenant_id == principal.user.tenant_id, Topic.class_id == class_id
        )
    ).all()
    segments = db.scalars(
        select(Segment).where(
            Segment.tenant_id == principal.user.tenant_id,
            Segment.class_id == class_id,
        )
    ).all()

    proposals = []
    for topic in topics:
        topic_tokens = tokenize(" ".join([topic.title, *topic.objectives]))
        scored = [
            (len(topic_tokens & tokenize(segment.text)), segment.id)
            for segment in segments
        ]
        suggested_ids = [
            segment_id
            for score, segment_id in sorted(scored, reverse=True)
            if score > 0
        ][:5]
        proposal = db.scalar(
            select(MappingProposal).where(
                MappingProposal.tenant_id == principal.user.tenant_id,
                MappingProposal.class_id == class_id,
                MappingProposal.topic_id == topic.id,
            )
        )
        if proposal is None:
            proposal = MappingProposal(
                tenant_id=principal.user.tenant_id,
                class_id=class_id,
                topic_id=topic.id,
                proposal_method="deterministic_keyword_v1",
            )
            db.add(proposal)
        proposal.suggested_segment_ids = suggested_ids
        proposal.approved_segment_ids = []
        proposal.unmatched = not suggested_ids
        proposal.status = MappingStatus.pending
        proposal.reviewer_id = None
        proposals.append(proposal)
    db.commit()
    return proposals


@router.patch(
    "/mapping-proposals/{proposal_id}/approve",
    response_model=MappingProposalResponse,
)
def approve_mapping(
    proposal_id: str,
    payload: MappingApproval,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    proposal = db.scalar(
        select(MappingProposal).where(
            MappingProposal.id == proposal_id,
            MappingProposal.tenant_id == principal.user.tenant_id,
        )
    )
    if proposal is None:
        raise HTTPException(status_code=404)
    get_owned_class(db, principal, proposal.class_id)
    valid_ids = set(
        db.scalars(
            select(Segment.id).where(
                Segment.tenant_id == principal.user.tenant_id,
                Segment.class_id == proposal.class_id,
                Segment.id.in_(payload.segment_ids),
            )
        ).all()
    )
    if valid_ids != set(payload.segment_ids):
        raise HTTPException(
            status_code=422, detail="One or more segments are outside this class"
        )
    proposal.approved_segment_ids = payload.segment_ids
    proposal.unmatched = not payload.segment_ids
    proposal.status = MappingStatus.approved
    proposal.reviewer_id = principal.user.id
    db.commit()
    db.refresh(proposal)
    return proposal
