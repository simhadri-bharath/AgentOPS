"""Build an evaluation dataset from an agent's production sessions.

Curating cases from real traffic beats inventing prompts: the inputs are ones
users actually asked, the retrieval context is what the agent actually found,
and the trajectory is what it actually did.

The trajectory it actually did is NOT the trajectory it should have done. Rows
produced here are seeded, not golden -- see review_status on the dataset.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.evaluation.trace_health import compute_trace_health, trace_health_details
from app.services.evaluation.trace_model import Trace
from app.services.evaluation.trace_normalizer import traces_from_session
from app.services.gcp.agent_engine_client import AgentEngineClient, AgentEngineError

logger = get_logger(__name__)

MIN_INPUT_CHARS = 8

# Sessions AgentOps created itself. Harvesting these would feed the platform's
# own test traffic back in as if it were production usage. Matched on session
# owner rather than prompt text, which is the only reliable signal.
# agentops_eval_user is the legacy id used before session cleanup existed.
AGENTOPS_USER_IDS = {
    "agentops-eval",
    "agentops-redteam",
    "agentops-probe",
    "agentops_eval_user",
    "agentops_redteam",
}


@dataclass
class BootstrappedCase:
    input: str
    actual_output: str
    expected_output: str = ""
    retrieval_context: list[str] = field(default_factory=list)
    reference_trajectory: list[dict[str, Any]] = field(default_factory=list)
    conversation: list[dict[str, str]] = field(default_factory=list)
    category: str = "uncategorized"
    session_id: str = ""
    invocation_id: str = ""
    tool_names: list[str] = field(default_factory=list)
    agent_path: list[str] = field(default_factory=list)
    health: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        """The dataset row shape the validator accepts."""
        return {
            "input": self.input,
            "expected_output": self.expected_output,
            "retrieval_context": self.retrieval_context,
            "reference_trajectory": self.reference_trajectory,
            "conversation": self.conversation,
            "category": self.category,
        }


def _categorize(trace: Trace, health: dict[str, float], turn_index: int) -> tuple[str, list[str]]:
    """Label the case so a dataset's difficulty mix is visible.

    Forty easy questions scoring 95% is a misleading result; the label is what
    makes that visible on the dataset page.
    """
    notes: list[str] = []
    if not trace.output.strip():
        notes.append("Agent produced no answer")
        return "failure_case", notes
    if any(call.error for call in trace.trajectory):
        notes.append("A tool call failed in this turn")
        return "tool_failure", notes
    if trace.trajectory and not trace.retrieval_context:
        notes.append("Retrieval tool ran but returned no usable documents")
        return "retrieval_failure", notes
    if health.get("trace_no_loop", 1.0) < 1.0:
        notes.append("Same tool called repeatedly with identical arguments")
        return "edge_case", notes
    if health.get("trace_no_redundant_calls", 1.0) < 1.0:
        notes.append("Duplicate tool calls within one turn")
        return "edge_case", notes
    if turn_index > 0:
        return "multi_turn", notes
    if len(trace.input) > 2000:
        return "long_context", notes
    return "happy_path", notes


def cases_from_traces(traces: list[Trace], *, session_id: str) -> list[BootstrappedCase]:
    cases: list[BootstrappedCase] = []
    conversation: list[dict[str, str]] = []

    for turn_index, trace in enumerate(traces):
        if trace.input.strip():
            conversation.append({"role": "user", "content": trace.input})
        if trace.output.strip():
            conversation.append({"role": "assistant", "content": trace.output})

        if len(trace.input.strip()) < MIN_INPUT_CHARS:
            continue

        health = compute_trace_health(trace)
        category, notes = _categorize(trace, health, turn_index)
        details = trace_health_details(trace)
        if details.get("duplicate_detail"):
            notes.append(f"Duplicates: {', '.join(details['duplicate_detail'])}")

        cases.append(
            BootstrappedCase(
                input=trace.input,
                actual_output=trace.output,
                # Left blank on purpose: what the agent said is not what it
                # should have said. A reviewer fills this in.
                expected_output="",
                retrieval_context=[doc.text for doc in trace.retrieval_context],
                reference_trajectory=[
                    {"name": call.name, "args": call.args} for call in trace.trajectory
                ],
                # Everything before this turn, so multi-turn metrics have history.
                conversation=list(conversation[:-2]) if turn_index else [],
                category=category,
                session_id=session_id,
                invocation_id=trace.invocation_id,
                tool_names=[call.name for call in trace.trajectory],
                agent_path=list(trace.agent_path),
                health=health,
                notes=notes,
            )
        )
    return cases


async def build_cases_from_sessions(
    resource_name: str,
    *,
    limit_sessions: int = 20,
    max_cases: int = 100,
    exclude_agentops_traffic: bool = True,
    tool_overrides: dict[str, str] | None = None,
) -> tuple[list[BootstrappedCase], list[str]]:
    """Harvest recent sessions into candidate evaluation cases."""
    errors: list[str] = []
    cases: list[BootstrappedCase] = []
    skipped_own = 0

    async with AgentEngineClient() as client:
        try:
            sessions = await client.list_sessions(
                resource_name, page_size=limit_sessions, order_by="updateTime desc"
            )
        except AgentEngineError as exc:
            return [], [f"sessions.list: {exc}"]

        for session in sessions:
            if len(cases) >= max_cases:
                break
            if exclude_agentops_traffic and session.get("userId") in AGENTOPS_USER_IDS:
                skipped_own += 1
                continue
            session_id = session["name"].split("/")[-1]
            try:
                raw_events = await client.list_events(resource_name, session_id)
            except AgentEngineError as exc:
                errors.append(f"session {session_id}: {exc}")
                continue

            traces = traces_from_session(
                raw_events, session_id=session_id, tool_overrides=tool_overrides
            )
            cases.extend(cases_from_traces(traces, session_id=session_id))

    if skipped_own:
        errors.append(
            f"Skipped {skipped_own} session(s) created by AgentOps itself "
            "(evaluation, red-team or probe traffic)."
        )

    if len(cases) > max_cases:
        # Say so rather than silently truncating -- a quietly capped dataset
        # reads as full coverage.
        errors.append(
            f"Capped at {max_cases} cases; {len(cases)} were available. "
            "Raise max_cases to include more."
        )
        cases = cases[:max_cases]

    return cases, errors
