from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Citation(BaseModel):
    segment_id: str
    page_or_section: str
    supporting_excerpt: str = Field(min_length=1, max_length=800)


class ContentBlock(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    content_kind: Literal["direct_excerpt", "generated_from_source"]
    citations: list[Citation] = Field(min_length=1, max_length=10)


class PacketStep(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal["read", "explain", "worked_example", "practice"]
    title: str = Field(min_length=1, max_length=200)
    blocks: list[ContentBlock] = Field(min_length=1, max_length=10)


class MultipleChoiceQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=1000)
    options: dict[str, str] = Field(min_length=2, max_length=5)
    answer_key: str
    rationale: str = Field(min_length=1, max_length=1000)
    citations: list[Citation] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def answer_key_is_an_option(self):
        if self.answer_key not in self.options:
            raise ValueError("answer_key must identify one option")
        return self


class PacketCandidate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    objectives: list[str] = Field(min_length=1, max_length=20)
    estimated_minutes: int = Field(ge=1, le=120)
    steps: list[PacketStep] = Field(min_length=4, max_length=4)
    questions: list[MultipleChoiceQuestion] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def required_step_order(self):
        kinds = [step.kind for step in self.steps]
        if kinds != ["read", "explain", "worked_example", "practice"]:
            raise ValueError(
                "steps must be ordered read, explain, worked_example, practice"
            )
        identifiers = [step.id for step in self.steps] + [
            question.id for question in self.questions
        ]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("step and question IDs must be unique")
        return self
