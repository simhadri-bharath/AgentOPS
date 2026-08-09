"""Metric registry, deterministic executors, and profile selection."""

import pytest

from app.services.evaluation.executors.deterministic import (
    argument_match,
    run_deterministic,
    trajectory_in_order_match,
    trajectory_precision,
    trajectory_recall,
)
from app.services.evaluation.metric_registry import (
    METRIC_REGISTRY,
    UnknownMetricError,
    availability,
    group_by_executor,
    specs_for,
    validate_metrics,
)
from app.services.evaluation.profiles import recommend
from app.services.evaluation.trace_model import EvaluationCase, ToolCall


def test_unknown_metric_is_rejected_not_rewritten():
    # The old map turned faithfulness into contains_expected before the run was
    # even queued. Anything unrecognised must now fail loudly.
    with pytest.raises(UnknownMetricError) as exc:
        validate_metrics(["faithfulness", "vibes"])
    assert "vibes" in str(exc.value)


def test_known_metrics_pass_through_deduplicated_and_ordered():
    assert validate_metrics(["faithfulness", "toxicity", "faithfulness"]) == [
        "faithfulness",
        "toxicity",
    ]


def test_no_metric_silently_maps_to_string_matching():
    # Every judged metric must have a real executor, not a deterministic stand-in.
    for name in ("faithfulness", "answer_relevancy", "toxicity", "hallucination"):
        assert METRIC_REGISTRY[name].executor == "deepeval"


def test_metrics_group_by_executor():
    grouped = group_by_executor(["exact_match", "faithfulness", "trace_no_loop"])
    assert {k: [s.name for s in v] for k, v in grouped.items()} == {
        "deterministic": ["exact_match"],
        "deepeval": ["faithfulness"],
        "trace_health": ["trace_no_loop"],
    }


def test_unavailable_metric_explains_itself():
    case = EvaluationCase(input="q", actual_output="a")
    results = {a.name: a for a in availability(["faithfulness", "answer_relevancy"], case)}
    assert results["answer_relevancy"].available is True
    assert results["faithfulness"].available is False
    # A reason a user can act on, not a bare None.
    assert "retrieval_context" in results["faithfulness"].reason


def test_reference_metric_reports_the_missing_column():
    case = EvaluationCase(input="q", actual_output="a")
    reason = specs_for(["exact_match"])[0].unavailable_reason(case.available_fields())
    assert "expected_output" in reason


def test_deterministic_skips_rather_than_scoring_zero():
    # A metric that cannot run must produce no score at all -- a zero would be
    # indistinguishable from a genuine failure.
    case = EvaluationCase(input="q", actual_output="a")
    assert run_deterministic(specs_for(["exact_match", "response_nonempty"]), case) == {
        "response_nonempty": 1.0
    }


def _case(predicted, reference):
    return EvaluationCase(
        input="q",
        actual_output="a",
        predicted_trajectory=predicted,
        reference_trajectory=reference,
    )


def test_argument_match_catches_a_wrong_query():
    # Tool-name-only metrics cannot tell a good search from a bad one.
    reference = [ToolCall(name="search_documents", args={"query": "illinois tax"})]
    right = _case([ToolCall(name="search_documents", args={"query": "Illinois Tax"})], reference)
    wrong = _case([ToolCall(name="search_documents", args={"query": "texas tax"})], reference)
    assert argument_match(right) == 1.0
    assert argument_match(wrong) == 0.0
    # Both call the same tool, so the name-only metric cannot separate them.
    assert trajectory_in_order_match(right) == trajectory_in_order_match(wrong) == 1.0


def test_argument_match_is_partial_when_some_args_match():
    reference = [ToolCall(name="search", args={"query": "a", "state": "IL"})]
    predicted = [ToolCall(name="search", args={"query": "a", "state": "TX"})]
    assert argument_match(_case(predicted, reference)) == 0.5


def test_trajectory_order_matters():
    reference = [ToolCall(name="a"), ToolCall(name="b")]
    in_order = _case([ToolCall(name="a"), ToolCall(name="b")], reference)
    reversed_order = _case([ToolCall(name="b"), ToolCall(name="a")], reference)
    assert trajectory_in_order_match(in_order) == 1.0
    assert trajectory_in_order_match(reversed_order) == 0.0


def test_trajectory_precision_and_recall_differ_on_extra_calls():
    reference = [ToolCall(name="a")]
    noisy = _case([ToolCall(name="a"), ToolCall(name="b")], reference)
    assert trajectory_recall(noisy) == 1.0
    assert trajectory_precision(noisy) == 0.5


def test_multi_agent_profile_scores_spans_as_well_as_the_trace():
    pack = recommend("multi_agent", ["retrieval", "tool_use"])
    assert "faithfulness" in pack["span_metrics"]
    assert "task_completion" in pack["metrics"]


def test_capabilities_extend_the_type_pack():
    # A multi_agent agent that also retrieves needs the RAG metrics; type alone
    # would have missed them.
    without = recommend("multi_agent", [])
    with_retrieval = recommend("multi_agent", ["retrieval"])
    assert "faithfulness" not in without["metrics"]
    assert "faithfulness" in with_retrieval["metrics"]


def test_rag_profile_picks_retrieval_metrics():
    pack = recommend("rag", ["retrieval"])
    for name in ("faithfulness", "contextual_precision", "contextual_recall"):
        assert name in pack["metrics"]


def test_profiles_flag_which_metrics_need_a_reference():
    pack = recommend("tool_calling", ["tool_use"])
    assert "tool_correctness" in pack["reference_based"]
    assert pack["note"]


def test_baseline_metrics_need_no_reference():
    pack = recommend("unknown", [])
    for name in pack["metrics"]:
        if name in METRIC_REGISTRY and name.startswith("trace_"):
            assert METRIC_REGISTRY[name].requires_reference is False
