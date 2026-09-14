import io
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app import db as db_module
from app.models import SchoolClass


FIXTURE_PDF = Path(__file__).resolve().parents[3] / "fixtures" / "fractions-source.pdf"


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def own_class_id() -> str:
    with db_module.SessionLocal() as db:
        return db.query(SchoolClass.id).filter(SchoolClass.name == "Class A").scalar()


def test_plain_text_upload_mapping_and_source_scope(client: TestClient) -> None:
    csrf = login(client, "teacher.a", "teacher-a-password")
    class_id = own_class_id()
    material = client.post(
        f"/classes/{class_id}/materials",
        headers={"X-CSRF-Token": csrf},
        files={
            "upload": (
                "fractions.txt",
                (
                    b"Equivalent fractions name the same amount.\\n\\n"
                    b"Multiply numerator and denominator by the same number."
                ),
                "text/plain",
            )
        },
    )
    assert material.status_code == 201
    assert material.json()["extraction_status"] == "ready"

    topics = client.post(
        f"/classes/{class_id}/topics",
        headers={"X-CSRF-Token": csrf},
        json={
            "topics": [
                {
                    "title": "Equivalent fractions",
                    "objectives": ["Recognize the same amount"],
                }
            ]
        },
    )
    assert topics.status_code == 201

    proposals = client.post(
        f"/classes/{class_id}/mapping-proposals",
        headers={"X-CSRF-Token": csrf},
    )
    assert proposals.status_code == 200
    proposal = proposals.json()[0]
    assert proposal["proposal_method"] == "deterministic_keyword_v1"
    assert proposal["suggested_segment_ids"]

    approved = client.patch(
        f"/mapping-proposals/{proposal['id']}/approve",
        headers={"X-CSRF-Token": csrf},
        json={"segment_ids": proposal["suggested_segment_ids"]},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    source = client.get(f"/sources/{proposal['suggested_segment_ids'][0]}")
    assert source.status_code == 200
    assert source.json()["filename"] == "fractions.txt"

    client.cookies.clear()
    login(client, "teacher.b", "teacher-b-password")
    assert (
        client.get(f"/sources/{proposal['suggested_segment_ids'][0]}").status_code
        == 404
    )


def test_textless_pdf_has_actionable_state(client: TestClient) -> None:
    csrf = login(client, "teacher.a", "teacher-a-password")
    class_id = own_class_id()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    content = io.BytesIO()
    writer.write(content)

    response = client.post(
        f"/classes/{class_id}/materials",
        headers={"X-CSRF-Token": csrf},
        files={"upload": ("scan.pdf", content.getvalue(), "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["extraction_status"] == "needs_text"
    assert "No selectable text" in response.json()["extraction_error"]


def test_text_pdf_preserves_one_based_page_in_mapping(client: TestClient) -> None:
    csrf = login(client, "teacher.a", "teacher-a-password")
    class_id = own_class_id()
    uploaded = client.post(
        f"/classes/{class_id}/materials",
        headers={"X-CSRF-Token": csrf},
        files={
            "upload": (
                "fractions-source.pdf",
                FIXTURE_PDF.read_bytes(),
                "application/pdf",
            )
        },
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["extraction_status"] == "ready"

    created_topics = client.post(
        f"/classes/{class_id}/topics",
        headers={"X-CSRF-Token": csrf},
        json={"topics": [{"title": "Equivalent fractions", "objectives": []}]},
    )
    assert created_topics.status_code == 201
    proposal = client.post(
        f"/classes/{class_id}/mapping-proposals",
        headers={"X-CSRF-Token": csrf},
    ).json()[0]
    source = client.get(f"/sources/{proposal['suggested_segment_ids'][0]}")
    assert source.status_code == 200
    assert source.json()["page_1_based"] == 1
