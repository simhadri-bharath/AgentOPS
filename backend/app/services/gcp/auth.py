"""Google Cloud Application Default Credentials validation."""

from dataclasses import dataclass

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ADC_SETUP_HINT = (
    "GCP Application Default Credentials not found or invalid. "
    "Run: gcloud auth application-default login\n"
    "Then set GCP_PROJECT_ID and GCP_REGION in your .env file."
)


@dataclass
class GCPAuthStatus:
    available: bool
    project_id: str | None
    credentials_type: str | None
    error: str | None = None


def validate_adc_credentials() -> GCPAuthStatus:
    """Verify ADC credentials are available and refreshable."""
    settings = get_settings()
    try:
        credentials, default_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(Request())
        project_id = settings.gcp_project_id or default_project
        cred_type = type(credentials).__name__
        logger.info(
            "GCP ADC validated",
            extra={"component": "gcp_auth", "project_id": project_id, "cred_type": cred_type},
        )
        return GCPAuthStatus(
            available=True,
            project_id=project_id,
            credentials_type=cred_type,
        )
    except DefaultCredentialsError as exc:
        logger.error("GCP ADC missing: %s", exc, extra={"component": "gcp_auth"})
        return GCPAuthStatus(
            available=False,
            project_id=None,
            credentials_type=None,
            error=ADC_SETUP_HINT,
        )
    except Exception as exc:
        logger.error("GCP ADC validation failed: %s", exc, extra={"component": "gcp_auth"})
        return GCPAuthStatus(
            available=False,
            project_id=None,
            credentials_type=None,
            error=f"{ADC_SETUP_HINT}\nDetail: {exc}",
        )


def require_adc() -> GCPAuthStatus:
    status = validate_adc_credentials()
    if not status.available:
        raise RuntimeError(status.error or ADC_SETUP_HINT)
    return status
