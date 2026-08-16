"""Evaluation services.

Deliberately empty of eager imports. Re-exporting EvaluationRunner here created
a cycle: importing invokers.agent_engine pulls evaluation.trace_model, which
triggers this package, which imported runner, which imports agent_engine again
while it is still initialising. It only surfaced when agent_engine happened to
be imported first, so it survived as a latent failure.
"""
