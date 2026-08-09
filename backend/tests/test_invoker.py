"""Invoker behaviour that does not need a live agent."""

import pytest

from app.services.evaluation.trace_model import InvocationState, TERMINAL_FAILURE_STATES
from app.services.invokers.agent_engine import (
    AgentEngineInvoker,
    _text_from_chunks,
    _unwrap_json_text,
    _usage_from_chunks,
)


def test_answer_is_the_last_text_chunk_not_the_first():
    # streamQuery emits intermediate agent output before the final answer.
    chunks = [
        {"content": {"parts": [{"text": "thinking..."}]}},
        {"content": {"parts": [{"functionCall": {"name": "search_documents"}}]}},
        {"content": {"parts": [{"text": "final answer"}]}},
    ]
    assert _text_from_chunks(chunks) == "final answer"


def test_usage_summed_across_chunks():
    chunks = [
        {"usage_metadata": {"prompt_token_count": 100, "candidates_token_count": 10}},
        {"usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 5}},
        {"content": {"parts": [{"text": "hi"}]}},
    ]
    assert _usage_from_chunks(chunks) == (150, 15)


def test_json_envelope_is_unwrapped():
    # The live formatter agent returns {"text": ...}; scoring the envelope
    # would penalise the agent for its own serialization.
    assert _unwrap_json_text('{"text": "the answer"}') == "the answer"
    assert _unwrap_json_text('{"answer": "second"}') == "second"


def test_plain_text_and_unparseable_json_pass_through():
    assert _unwrap_json_text("plain answer") == "plain answer"
    assert _unwrap_json_text('{"broken": ') == '{"broken": '
    # A JSON object with no text-like key is left alone rather than mangled.
    assert _unwrap_json_text('{"count": 3}') == '{"count": 3}'


def test_judge_errors_are_not_counted_as_agent_failures():
    assert InvocationState.JUDGE_ERROR not in TERMINAL_FAILURE_STATES
    assert InvocationState.AGENT_ERROR in TERMINAL_FAILURE_STATES
    assert InvocationState.AUTH_ERROR in TERMINAL_FAILURE_STATES


@pytest.mark.asyncio
async def test_cancel_short_circuits_the_batch():
    invoker = AgentEngineInvoker()
    invoker.cancel()
    results = await invoker.batch_invoke("projects/p/locations/us-central1/reasoningEngines/1", [
        {"input": "a"},
        {"input": "b"},
    ])
    assert [r.state for r in results] == [InvocationState.CANCELLED] * 2


@pytest.mark.asyncio
async def test_empty_batch_makes_no_calls():
    assert await AgentEngineInvoker().batch_invoke("whatever", []) == []
