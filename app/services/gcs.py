"""
gcs.py
------
Thin wrapper around Google Cloud Storage for fetching the boundary datasets
from the private bucket.

Authentication uses Application Default Credentials (ADC) only — no key
files live in this repository:
  - locally:   `gcloud auth application-default login`
  - Cloud Run: the service account attached to the Cloud Run service
"""

import html
import logging
import os
import time
from functools import lru_cache
from pathlib import Path

from google.api_core import exceptions as gapi_exceptions
from google.auth import exceptions as auth_exceptions
from google.cloud import storage

logger = logging.getLogger(__name__)

_LOGIN_HINT = (
    "Locally, run `gcloud auth application-default login` with an account that "
    "can read the bucket. On Cloud Run, grant the service account "
    "roles/storage.objectViewer on the bucket."
)


class GCSError(RuntimeError):
    """Raised when a dataset cannot be fetched from Cloud Storage."""


@lru_cache(maxsize=1)
def get_client() -> storage.Client:
    """
    Return a shared Storage client authenticated via ADC.
    Reading objects needs no project, so GOOGLE_CLOUD_PROJECT is optional;
    an explicit None stops the client failing when none can be inferred
    (e.g. inside a local Docker container).
    """
    try:
        return storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
    except auth_exceptions.DefaultCredentialsError as exc:
        raise GCSError(
            f"No Google Application Default Credentials found. {_LOGIN_HINT}"
        ) from exc


def download_to_file(bucket_name: str, object_path: str, dest: Path) -> int:
    """
    Download gs://<bucket_name>/<object_path> to `dest`, streaming to disk
    so the object is never held in memory as a whole.
    Returns the number of bytes downloaded.
    """
    uri = f"gs://{bucket_name}/{object_path}"
    logger.info("  Downloading %s …", uri)
    started = time.perf_counter()

    blob = get_client().bucket(bucket_name).blob(object_path)
    try:
        blob.download_to_filename(str(dest))
    except gapi_exceptions.NotFound as exc:
        raise GCSError(
            f"{uri} not found. Check GCS_BUCKET_NAME and the object path."
        ) from exc
    except gapi_exceptions.Forbidden as exc:
        raise GCSError(
            f"Permission denied reading {uri} (needs storage.objects.get). "
            f"{_LOGIN_HINT} Google said: {html.unescape(exc.message)}"
        ) from exc
    except auth_exceptions.RefreshError as exc:
        raise GCSError(
            f"Google credentials are expired or revoked while reading {uri}. "
            f"{_LOGIN_HINT}"
        ) from exc
    except (gapi_exceptions.GoogleAPIError, auth_exceptions.GoogleAuthError) as exc:
        raise GCSError(f"Failed to download {uri}: {exc}") from exc

    size = dest.stat().st_size
    logger.info(
        "  Downloaded %s (%.1f MB in %.1fs)",
        uri, size / 1e6, time.perf_counter() - started,
    )
    return size
