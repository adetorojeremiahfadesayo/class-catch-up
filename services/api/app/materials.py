import hashlib
import io
import re
import uuid
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedSegment:
    position: int
    page_1_based: int | None
    text_section: str | None
    text: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def stable_segment_id(
    material_id: str, position: int, text: str, page_1_based: int | None
) -> str:
    identity = f"{material_id}:{position}:{page_1_based}:{sha256_bytes(text.encode())}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def extract_pdf(content: bytes) -> list[ExtractedSegment]:
    reader = PdfReader(io.BytesIO(content))
    segments = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            segments.append(
                ExtractedSegment(
                    position=page_number,
                    page_1_based=page_number,
                    text_section=None,
                    text=text,
                )
            )
    return segments


def extract_text(content: bytes) -> list[ExtractedSegment]:
    decoded = content.decode("utf-8")
    sections = [part.strip() for part in re.split(r"\n\s*\n", decoded) if part.strip()]
    return [
        ExtractedSegment(
            position=index,
            page_1_based=None,
            text_section=f"section-{index}",
            text=text,
        )
        for index, text in enumerate(sections, start=1)
    ]


def tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2
    }
