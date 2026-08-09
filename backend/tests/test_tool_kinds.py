"""Tool classification and retrieval extraction.

The important case is the negative one: a tool that is not retrieval must not
contribute retrieval_context, because faithfulness scored against a calculator
result is confidently meaningless.
"""

from app.services.evaluation.tool_kinds import (
    ToolKind,
    classify_tool,
    extract_retrieval_docs,
    infer_agent_type,
    infer_capabilities,
)


def test_classifies_retrieval_by_name():
    assert classify_tool("search_documents") is ToolKind.RETRIEVAL
    assert classify_tool("vector_lookup") is ToolKind.RETRIEVAL
    assert classify_tool("retrieve_context") is ToolKind.RETRIEVAL


def test_classifies_non_retrieval_families():
    assert classify_tool("send_email") is ToolKind.COMMUNICATION
    assert classify_tool("calculate_premium") is ToolKind.COMPUTATION
    assert classify_tool("create_ticket") is ToolKind.ACTION


def test_unnamed_tool_with_document_payload_is_retrieval():
    payload = {"results": [{"id": "d1", "text": "alpha", "score": 0.9}]}
    assert classify_tool("mystery_tool", payload) is ToolKind.RETRIEVAL


def test_unknown_tool_stays_unknown_rather_than_guessing():
    # A bare confirmation string must not be mistaken for retrieved evidence.
    assert classify_tool("mystery_tool", {"status": "ok"}) is ToolKind.UNKNOWN
    assert classify_tool("mystery_tool", "done") is ToolKind.UNKNOWN


def test_per_agent_override_wins_over_heuristic():
    kind = classify_tool("search_documents", overrides={"search_documents": "action"})
    assert kind is ToolKind.ACTION


def test_extract_docs_normalizes_and_ranks():
    docs = extract_retrieval_docs(
        {
            "documents": [
                {"document_id": "a", "text": "first", "score": 0.8, "source": "s3://a"},
                {"document_id": "b", "content": "second", "relevance": 0.4},
            ]
        }
    )
    assert [d.document_id for d in docs] == ["a", "b"]
    assert [d.rank for d in docs] == [0, 1]
    assert docs[0].score == 0.8
    assert docs[1].text == "second"


def test_extract_docs_skips_empty_text():
    docs = extract_retrieval_docs({"results": [{"id": "a", "text": "  "}, {"id": "b", "text": "x"}]})
    assert len(docs) == 1
    assert docs[0].document_id == "b"


def test_capabilities_from_tools():
    caps = infer_capabilities(["search_documents", "run_python"])
    assert "retrieval" in caps
    assert "tool_use" in caps
    assert "code_execution" in caps


def test_multi_agent_wins_over_rag_when_subagents_present():
    # The live chat agent: research_agent hands off to formatter_agent.
    assert (
        infer_agent_type(
            ["search_documents"], ["user", "research_agent", "formatter_agent"]
        )
        == "multi_agent"
    )


def test_single_agent_with_retrieval_is_rag():
    assert infer_agent_type(["search_documents"], ["user", "agent"]) == "rag"


def test_no_tools_no_subagents_falls_back_to_conversational():
    assert (
        infer_agent_type([], ["user", "agent"], class_methods=["stream_query"])
        == "conversational"
    )
