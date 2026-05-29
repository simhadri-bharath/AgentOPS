"""Verify Vertex AI evaluation dependencies are installed."""

import importlib


def check_evals_dependencies() -> tuple[bool, str | None]:
    """
    run_inference requires google-cloud-aiplatform[evaluation] (pandas, tqdm, etc.).
    """
    try:
        importlib.import_module("vertexai._genai.evals")
        return True, None
    except ImportError as exc:
        return False, (
            "Vertex AI evaluation dependencies missing. "
            "Run: pip install 'google-cloud-aiplatform[evaluation]>=1.74.0' "
            f"Detail: {exc}"
        )
