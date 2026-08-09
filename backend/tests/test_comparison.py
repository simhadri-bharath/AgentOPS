"""Run-over-run comparison.

The point of the comparison is not the arithmetic; it is refusing to present a
delta as evidence about the agent when the harness moved too.
"""

import uuid
from types import SimpleNamespace

from app.services.evaluation.comparison import SIGNIFICANT_DELTA, build_comparison


def _run(aggregates, config=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        aggregate_scores=aggregates,
        run_config=config
        if config is not None
        else {
            "evaluator_model": "gemini-2.5-flash",
            "evaluator_temperature": 0.0,
            "metric_config_version": "1",
            "dataset_id": "ds-1",
            "dataset_version": 1,
            "invocation_interface": "streamQuery/stream_query",
            "agent_resource_name": "engines/1",
            "framework_versions": {"deepeval": "3.9.9"},
        },
    )


def _result(index, scores, spans=None, text="a question"):
    return SimpleNamespace(
        sample_index=index, input=text, scores=scores, span_scores=spans or []
    )


def test_regression_is_detected_and_named():
    current = _run({"avg_faithfulness": 0.84, "avg_answer_relevancy": 0.95})
    baseline = _run({"avg_faithfulness": 0.91, "avg_answer_relevancy": 0.95})
    out = build_comparison(current, baseline, [], [])

    deltas = {d["metric"]: d for d in out.metric_deltas}
    assert deltas["faithfulness"]["direction"] == "regressed"
    assert deltas["faithfulness"]["delta"] == -0.07
    assert deltas["answer_relevancy"]["direction"] == "unchanged"
    assert "faithfulness" in out.summary


def test_noise_below_the_threshold_is_not_a_regression():
    current = _run({"avg_faithfulness": 0.90})
    baseline = _run({"avg_faithfulness": 0.90 + (SIGNIFICANT_DELTA / 2)})
    out = build_comparison(current, baseline, [], [])
    assert out.metric_deltas[0]["direction"] == "unchanged"
    assert out.summary == "No significant change."


def test_a_different_judge_makes_the_runs_incomparable():
    # The whole reason run_config is snapshotted: a judge change moves scores
    # on its own, and must not be read as the agent getting worse.
    current = _run({"avg_faithfulness": 0.70})
    baseline = _run(
        {"avg_faithfulness": 0.91},
        config={"evaluator_model": "gemini-2.5-pro", "metric_config_version": "1"},
    )
    out = build_comparison(current, baseline, [], [])
    assert out.comparable is False
    assert any("judge model" in w for w in out.warnings)


def test_a_different_dataset_version_is_flagged():
    current = _run({"avg_faithfulness": 0.80})
    baseline = _run(
        {"avg_faithfulness": 0.80},
        config={"dataset_id": "ds-1", "dataset_version": 2},
    )
    out = build_comparison(current, baseline, [], [])
    assert out.comparable is False
    assert any("dataset version" in w for w in out.warnings)


def test_runs_without_snapshots_are_not_silently_trusted():
    current = _run({"avg_faithfulness": 0.80}, config={})
    baseline = _run({"avg_faithfulness": 0.90}, config={})
    out = build_comparison(current, baseline, [], [])
    assert out.comparable is False
    assert any("predate run snapshots" in w for w in out.warnings)


def test_new_and_dropped_metrics_are_not_treated_as_movement():
    current = _run({"avg_faithfulness": 0.9, "avg_toxicity": 1.0})
    baseline = _run({"avg_faithfulness": 0.9, "avg_bias": 1.0})
    deltas = {d["metric"]: d for d in build_comparison(current, baseline, [], []).metric_deltas}
    assert deltas["toxicity"]["direction"] == "new"
    assert deltas["bias"]["direction"] == "dropped"
    assert deltas["toxicity"]["delta"] is None


def test_regressed_samples_point_at_specific_cases():
    current = _run({"avg_faithfulness": 0.7})
    baseline = _run({"avg_faithfulness": 0.9})
    out = build_comparison(
        current,
        baseline,
        [_result(0, {"faithfulness": 0.4}), _result(1, {"faithfulness": 0.95})],
        [_result(0, {"faithfulness": 0.95}), _result(1, {"faithfulness": 0.95})],
    )
    assert len(out.regressed_samples) == 1
    assert out.regressed_samples[0]["sample_index"] == 0
    assert out.regressed_samples[0]["delta"] == -0.55


def test_span_delta_attributes_the_drop_to_a_subagent():
    # "faithfulness fell" is a fact; "research_agent's faithfulness fell" is a
    # place to look.
    spans_now = [{"author": "research_agent", "scores": {"faithfulness": 0.4}},
                 {"author": "formatter_agent", "scores": {"faithfulness": 1.0}}]
    spans_before = [{"author": "research_agent", "scores": {"faithfulness": 0.95}},
                    {"author": "formatter_agent", "scores": {"faithfulness": 1.0}}]
    out = build_comparison(
        _run({"avg_faithfulness": 0.7}),
        _run({"avg_faithfulness": 0.97}),
        [_result(0, {"faithfulness": 0.7}, spans_now)],
        [_result(0, {"faithfulness": 0.97}, spans_before)],
    )
    assert [s["author"] for s in out.span_deltas] == ["research_agent"]
    assert out.span_deltas[0]["delta"] == -0.55
    assert "research_agent" in out.summary
