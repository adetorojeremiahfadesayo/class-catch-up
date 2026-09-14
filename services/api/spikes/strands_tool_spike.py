from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from strands import Agent, tool


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PROOF_PATH = WORKSPACE_ROOT / "artifacts" / "runtime-spike" / "strands-tool-call.json"
ALLOWED_SEGMENT_ID = "segment_fixture_equivalent_fractions_p1"
tool_events: list[dict[str, Any]] = []


@tool
def read_confirmed_source(segment_id: str) -> dict[str, Any]:
    """Read one source segment allowed by the confirmed lesson scope.

    Args:
        segment_id: Stable identifier for the requested source segment.
    """
    if segment_id != ALLOWED_SEGMENT_ID:
        raise ValueError("segment_id is outside the confirmed lesson scope")

    event = {
        "tool": "read_confirmed_source",
        "segment_id": segment_id,
        "called_at": datetime.now(UTC).isoformat(),
    }
    tool_events.append(event)
    return {
        "segment_id": segment_id,
        "page_1_based": 1,
        "supporting_excerpt": (
            "Equivalent fractions name the same amount even when their "
            "numerators and denominators are different."
        ),
        "source_kind": "synthetic_teacher_owned_fixture",
    }


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def main() -> None:
    agent = Agent(tools=[read_confirmed_source], callback_handler=None)
    result = agent.tool.read_confirmed_source(segment_id=ALLOWED_SEGMENT_ID)

    proof = {
        "proof_type": "live_local_strands_sdk_tool_execution",
        "model_driven_agent_run": False,
        "provider_call": {
            "attempted": False,
            "reason": (
                "No AWS or other supported model-provider credentials and no "
                "configured model ID were available."
            ),
        },
        "strands_agents_version": version("strands-agents"),
        "registered_tools": agent.tool_names,
        "tool_events": tool_events,
        "tool_result": to_jsonable(result),
        "data_classification": {
            "student_records": "none",
            "source_material": "synthetic_teacher_owned_fixture",
        },
        "completed_at": datetime.now(UTC).isoformat(),
    }

    PROOF_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
