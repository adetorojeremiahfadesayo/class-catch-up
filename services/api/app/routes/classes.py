from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_student, require_teacher, require_teacher_read
from app.db import get_db
from app.models import EducationSystem, Enrollment, SchoolClass, User
from app.schemas import (
    ClassCreate,
    ClassResponse,
    EducationSystemOption,
    RosterStudentResponse,
    StudentSchoolContext,
    TeacherOnboardingResponse,
    TeacherOnboardingUpdate,
)


router = APIRouter(tags=["classes"])

EDUCATION_SYSTEMS = {
    EducationSystem.united_states_high_school: EducationSystemOption(
        id="united_states_high_school",
        label="United States High School",
        class_label="Course",
        period_label="Period",
        level_label="Grade",
        levels=["Grade 9", "Grade 10", "Grade 11", "Grade 12"],
        timezones=[
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
        ],
    ),
    EducationSystem.england_wales_secondary: EducationSystemOption(
        id="england_wales_secondary",
        label="England & Wales Secondary / Sixth Form",
        class_label="Class",
        period_label="Lesson",
        level_label="Year group",
        levels=[
            "Year 7",
            "Year 8",
            "Year 9",
            "Year 10",
            "Year 11",
            "Year 12",
            "Year 13",
        ],
        timezones=["Europe/London"],
    ),
}


def get_owned_class(
    db: Session, principal: Principal, class_id: str
) -> SchoolClass:
    school_class = db.scalar(
        select(SchoolClass).where(
            SchoolClass.id == class_id,
            SchoolClass.tenant_id == principal.user.tenant_id,
            SchoolClass.owner_teacher_id == principal.user.id,
        )
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return school_class


@router.post("/classes", response_model=ClassResponse, status_code=201)
def create_class(
    payload: ClassCreate,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    school_class = SchoolClass(
        tenant_id=principal.user.tenant_id,
        owner_teacher_id=principal.user.id,
        name=payload.name,
        subject=payload.subject,
        timezone=payload.timezone,
    )
    db.add(school_class)
    db.commit()
    db.refresh(school_class)
    return school_class


@router.get("/classes", response_model=list[ClassResponse])
def list_classes(
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(SchoolClass).where(
            SchoolClass.tenant_id == principal.user.tenant_id,
            SchoolClass.owner_teacher_id == principal.user.id,
        )
    ).all()


@router.get(
    "/classes/{class_id}/students", response_model=list[RosterStudentResponse]
)
def list_roster(
    class_id: str,
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    get_owned_class(db, principal, class_id)
    rows = db.execute(
        select(Enrollment, User)
        .join(User, User.id == Enrollment.user_id)
        .where(
            Enrollment.tenant_id == principal.user.tenant_id,
            Enrollment.class_id == class_id,
            User.username.not_like("demo-visitor-%"),
        )
    ).all()
    return [
        RosterStudentResponse(
            user_id=user.id,
            student_id=enrollment.student_id,
            display_name=user.display_name,
        )
        for enrollment, user in rows
    ]


@router.get("/student/class", response_model=ClassResponse)
def student_class(
    principal: Principal = Depends(require_student),
    db: Session = Depends(get_db),
):
    school_class = db.scalar(
        select(SchoolClass)
        .join(Enrollment, Enrollment.class_id == SchoolClass.id)
        .where(
            Enrollment.tenant_id == principal.user.tenant_id,
            Enrollment.user_id == principal.user.id,
        )
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return school_class


def onboarding_response(
    db: Session, principal: Principal
) -> TeacherOnboardingResponse:
    classes = list(
        db.scalars(
            select(SchoolClass).where(
                SchoolClass.tenant_id == principal.user.tenant_id,
                SchoolClass.owner_teacher_id == principal.user.id,
            )
        ).all()
    )
    selected = next(
        (
            school_class
            for school_class in classes
            if school_class.id == principal.user.selected_class_id
        ),
        None,
    )
    return TeacherOnboardingResponse(
        completed=bool(
            principal.user.introduction
            and selected
            and selected.education_system
            and selected.level_label
        ),
        teacher_display_name=principal.user.display_name,
        introduction=principal.user.introduction or "",
        selected_class_id=principal.user.selected_class_id,
        classes=classes,
        education_systems=list(EDUCATION_SYSTEMS.values()),
    )


@router.get("/teacher/onboarding", response_model=TeacherOnboardingResponse)
def get_onboarding(
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    return onboarding_response(db, principal)


@router.put("/teacher/onboarding", response_model=TeacherOnboardingResponse)
def update_onboarding(
    payload: TeacherOnboardingUpdate,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    school_class = get_owned_class(db, principal, payload.class_id)
    education_system = EducationSystem(payload.education_system)
    option = EDUCATION_SYSTEMS[education_system]
    if payload.level_label not in option.levels:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {option.level_label.lower()} for this school system",
        )
    if payload.timezone not in option.timezones:
        raise HTTPException(
            status_code=422, detail="Invalid timezone for this school system"
        )
    principal.user.display_name = payload.display_name
    principal.user.introduction = payload.introduction
    principal.user.selected_class_id = school_class.id
    school_class.education_system = education_system
    school_class.level_label = payload.level_label
    school_class.timezone = payload.timezone
    db.commit()
    db.refresh(principal.user)
    return onboarding_response(db, principal)


@router.get("/student/context", response_model=StudentSchoolContext)
def student_context(
    principal: Principal = Depends(require_student),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(SchoolClass, User)
        .join(Enrollment, Enrollment.class_id == SchoolClass.id)
        .join(User, User.id == SchoolClass.owner_teacher_id)
        .where(
            Enrollment.tenant_id == principal.user.tenant_id,
            Enrollment.user_id == principal.user.id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404)
    school_class, teacher = row
    option = (
        EDUCATION_SYSTEMS.get(school_class.education_system)
        if school_class.education_system
        else None
    )
    return StudentSchoolContext(
        class_id=school_class.id,
        class_name=school_class.name,
        subject=school_class.subject,
        education_system=(
            school_class.education_system.value
            if school_class.education_system
            else None
        ),
        education_system_label=option.label if option else None,
        level_label=school_class.level_label,
        period_label=option.period_label if option else "Period",
        teacher_display_name=teacher.display_name,
        teacher_introduction=teacher.introduction,
    )
