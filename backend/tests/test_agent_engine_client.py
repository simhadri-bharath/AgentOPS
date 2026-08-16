"""Agent Engine REST client: stream parsing and error classification."""

import pytest

from app.services.gcp.agent_engine_client import (
    INVOCATION_CLASS_METHOD,
    INVOCATION_ENDPOINT,
    AgentEngineClient,
    classify_http_error,
    _consume_stream_line,
)


def test_invocation_interface_matches_phase1_gate():
    # :query 404s against ADK agents -- see docs/invocation_compatibility.md.
    assert INVOCATION_ENDPOINT == "streamQuery"
    assert INVOCATION_CLASS_METHOD == "stream_query"


def test_auth_failures_are_not_reported_as_agent_bugs():
    assert classify_http_error(401, "") == "AUTH_ERROR"
    assert classify_http_error(403, "") == "AUTH_ERROR"
    assert classify_http_error(429, "") == "RATE_LIMITED"
    assert classify_http_error(504, "") == "TIMEOUT"


def test_missing_class_method_is_an_agent_error():
    body = 'Agent Engine Error: User-specified method `query` not found.'
    assert classify_http_error(404, body) == "AGENT_ERROR"


def test_region_parsed_from_resource_name():
    name = "projects/1/locations/europe-west4/reasoningEngines/9"
    assert AgentEngineClient.region_of(name) == "europe-west4"


def test_stream_line_with_array_punctuation():
    parsed, buffer = _consume_stream_line('[{"author": "user"}', "")
    assert parsed == {"author": "user"}
    assert buffer == ""


def test_stream_object_spanning_multiple_lines():
    parsed, buffer = _consume_stream_line('{"author":', "")
    assert parsed is None
    parsed, buffer = _consume_stream_line('"research_agent"}', buffer)
    assert parsed == {"author": "research_agent"}
    assert buffer == ""


def test_sse_data_prefix_is_stripped():
    parsed, _ = _consume_stream_line('data: {"x": 1}', "")
    assert parsed == {"x": 1}


def test_blank_and_punctuation_only_lines_are_ignored():
    assert _consume_stream_line("", "abc") == (None, "abc")
    assert _consume_stream_line("]", "") == (None, "")


@pytest.mark.asyncio
async def test_client_requires_context_manager():
    client = AgentEngineClient("proj")
    with pytest.raises(RuntimeError, match="context manager"):
        client._require_client()


def test_quota_project_follows_the_resource_not_the_config():
    """An agent discovered under a different GCP_PROJECT_ID still belongs to its
    own project. Billing the configured project instead yields a 403 that reads
    like a permissions problem rather than a misconfiguration."""
    from app.services.gcp.agent_engine_client import project_of

    assert (
        project_of("projects/936666675765/locations/us-west1/reasoningEngines/7")
        == "936666675765"
    )
    assert project_of(None) is None
    assert project_of("not-a-resource-name") is None
