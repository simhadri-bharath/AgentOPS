"""Import-order robustness.

Three packages re-exported their runners from __init__, which made importing a
leaf module pull the whole subsystem and created cycles. They only fired when a
particular module happened to be imported first, so they survived as latent
failures -- app startup worked while a direct script import crashed.
"""

import importlib
import subprocess
import sys

# Each entry is imported FIRST in a fresh interpreter. Any cycle shows up as a
# non-zero exit, which importing them in the app's usual order would hide.
LEAF_MODULES = [
    "app.services.invokers.agent_engine",
    "app.services.evaluation.runner",
    "app.services.evaluation.trace_model",
    "app.services.redteam.runner",
    "app.services.redteam.deepteam_service",
    "app.services.redteam.library_loader",
    "app.services.redteam.strategies.base",
    "app.services.redteam.strategies.registry",
    "app.services.redteam.deepteam_catalog",
    "app.services.redteam.scoring_config",
]


def test_every_module_imports_first_without_a_cycle():
    for module in LEAF_MODULES:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"{module} fails when imported first:\n{result.stderr[-800:]}"
        )


def test_packages_do_not_eagerly_import_runners():
    # An empty package __init__ is what keeps the above true.
    for pkg in (
        "app.services.evaluation",
        "app.services.redteam",
        "app.services.redteam.strategies",
    ):
        module = importlib.import_module(pkg)
        assert not getattr(module, "__all__", None), (
            f"{pkg} re-exports {module.__all__}; that is how the cycles started"
        )
