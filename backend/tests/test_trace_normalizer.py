"""Trace normalization against the real Agent Engine event shape.

The fixture mirrors a live session on Steptoe Chat Agent V1: two turns, a
research_agent -> formatter_agent handoff, and a second turn where
search_documents is called twice with identical arguments.
"""

import json
from pathlib import Path

import pytest

from app.services.evaluation.tool_kinds import ToolKind
from app.services.evaluation.trace_health import (
    compute_trace_health,
    duplicate_tool_calls,
    trace_health_details,
)
from app.services.evaluation.trace_model import EventType, SpanKind
from app.services.evaluation.trace_normalizer import (
    build_trace,
    group_by_invocation,
    normalize_events,
    traces_from_session,
)

FIXTURE = Path(__file__).parent / "fixtures" / "chat_agent_session_events.json"


@pytest.fixture
def raw_events():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def traces(raw_events):
    return traces_from_session(raw_events, session_id="abc123")


def test_events_are_typed_not_just_text(raw_events):
    events = normalize_events(raw_events, session_id="abc123")
    kinds = {e.event_type for e in events}
    assert EventType.USER_MESSAGE in kinds
    assert EventType.TOOL_CALL in kinds
    assert EventType.TOOL_RESULT in kinds
    assert EventType.AGENT_MESSAGE in kinds


def test_invocation_id_groups_turns(raw_events):
    grouped = group_by_invocation(normalize_events(raw_events, session_id="abc123"))
    assert set(grouped) == {"e-19e543ac-0464-41", "e-6df25124-768f-40"}


def test_first_turn_recovers_the_multi_agent_path(traces):
    turn = traces[0]
    assert turn.agent_path == ["research_agent", "formatter_agent"]
    # The answer is the last agent message, not the first.
    assert turn.output.startswith("**Illinois surplus lines**")
    assert "Illinois" in turn.input


def test_trajectory_is_the_real_tool_sequence(traces):
    turn = traces[0]
    assert [t.name for t in turn.trajectory] == ["search_documents"]
    assert turn.trajectory[0].args == {"query": "Illinois surplus lines premium tax"}


def test_retrieval_context_harvested_from_function_response(traces):
    docs = traces[0].retrieval_context
    assert len(docs) == 2
    assert docs[0].document_id == "il-215-ilcs-5"
    assert "3.5%" in docs[0].text
    assert docs[0].score == 0.93


def test_spans_cover_each_subagent_and_tool(traces):
    spans = traces[0].spans
    assert [s.kind for s in spans] == [SpanKind.TOOL, SpanKind.AGENT, SpanKind.AGENT]
    assert [s.author for s in spans] == ["research_agent", "research_agent", "formatter_agent"]
    tool_span = spans[0]
    assert tool_span.tool_name == "search_documents"
    assert tool_span.tool_kind is ToolKind.RETRIEVAL


def test_agent_span_carries_the_context_it_could_ground_on(traces):
    agent_spans = [s for s in traces[0].spans if s.kind is SpanKind.AGENT]
    assert all(len(s.retrieval_context) == 2 for s in agent_spans)


def test_tokens_are_summed_from_usage_metadata(traces):
    turn = traces[0]
    assert turn.tokens_in == 1200 + 2400 + 300
    assert turn.tokens_out == 40 + 180 + 90


def test_state_delta_is_attached_not_dropped(traces):
    deltas = [e.state_delta for e in traces[0].events if e.state_delta]
    assert deltas and deltas[0]["research_result"] == "drafted"


def test_duplicate_tool_calls_are_detected(traces):
    second = traces[1]
    assert [t.name for t in second.trajectory] == ["search_documents", "search_documents"]
    assert duplicate_tool_calls(second) == 1
    assert compute_trace_health(second)["trace_no_redundant_calls"] == 0.5
    assert "search_documents x2" in trace_health_details(second)["duplicate_detail"]


def test_identical_documents_are_not_double_counted(traces):
    # Both calls returned the same document; recall must not be inflated.
    assert len(traces[1].retrieval_context) == 1


def test_clean_turn_scores_well(traces):
    health = compute_trace_health(traces[0])
    assert health["trace_tool_success_rate"] == 1.0
    assert health["trace_no_redundant_calls"] == 1.0
    assert health["trace_no_loop"] == 1.0
    assert health["trace_answered"] == 1.0


def test_tool_call_without_response_is_recorded_as_an_error():
    trace = build_trace(
        normalize_events(
            [
                {
                    "invocationId": "i1",
                    "author": "agent",
                    "content": {"parts": [{"functionCall": {"name": "search_documents", "args": {}}}]},
                }
            ]
        ),
        invocation_id="i1",
    )
    assert trace.trajectory[0].error == "No tool response"
    assert compute_trace_health(trace)["trace_tool_success_rate"] == 0.0


def test_failed_tool_response_lowers_success_rate():
    trace = build_trace(
        normalize_events(
            [
                {
                    "invocationId": "i1",
                    "author": "agent",
                    "content": {"parts": [{"functionCall": {"name": "lookup", "args": {}}}]},
                },
                {
                    "invocationId": "i1",
                    "author": "agent",
                    "content": {
                        "parts": [
                            {"functionResponse": {"name": "lookup", "response": {"error": "boom"}}}
                        ]
                    },
                },
            ]
        ),
        invocation_id="i1",
    )
    assert trace.trajectory[0].error == "boom"
    assert compute_trace_health(trace)["trace_tool_success_rate"] == 0.0


def test_non_retrieval_tool_contributes_no_context():
    trace = build_trace(
        normalize_events(
            [
                {
                    "invocationId": "i1",
                    "author": "agent",
                    "content": {"parts": [{"functionCall": {"name": "send_email", "args": {}}}]},
                },
                {
                    "invocationId": "i1",
                    "author": "agent",
                    "content": {
                        "parts": [
                            {"functionResponse": {"name": "send_email", "response": {"status": "sent"}}}
                        ]
                    },
                },
            ]
        ),
        invocation_id="i1",
    )
    assert trace.retrieval_context == []
    assert trace.spans[0].tool_kind is ToolKind.COMMUNICATION
