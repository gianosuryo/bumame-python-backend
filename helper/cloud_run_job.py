
import os
import aiohttp
from typing import Any, Dict, List, Optional
from config.logging import logger

METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
METADATA_HEADERS = {"Metadata-Flavor": "Google"}


async def _get_access_token() -> Optional[str]:
    """Fetch an OAuth2 access token.

    Preference order:
    1) Application Default Credentials (supports GOOGLE_APPLICATION_CREDENTIALS)
    2) GCE Metadata server (when running on GCP)
    """
    # Try ADC first (works with GOOGLE_APPLICATION_CREDENTIALS and many environments)
    try:
        # Import lazily to avoid hard dependency if not installed
        import google.auth
        from google.auth.transport.requests import Request

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not credentials.valid:
            credentials.refresh(Request())
        if credentials.token:
            return credentials.token
    except Exception as exc:
        logger.debug(f"ADC token fetch error: {exc}")

    # Fallback to metadata server
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(METADATA_TOKEN_URL, headers=METADATA_HEADERS) as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to get metadata token (status={resp.status})")
                    return None
                data = await resp.json()
                return data.get("access_token")
    except Exception as exc:
        logger.debug(f"Metadata token fetch error: {exc}")
        return None


def _get_env(name: str) -> Optional[str]:
    value = os.getenv(name, "").strip()
    return value or None


def _get_cr_job_params() -> Optional[Dict[str, str]]:
    project = _get_env("CLOUD_RUN_JOB_PROJECT")
    region = _get_env("CLOUD_RUN_JOB_REGION")
    job = _get_env("CLOUD_RUN_JOB_NAME")

    if not project or not region or not job:
        logger.debug("Cloud Run Job env vars not fully set; skipping ensure_cloud_run_job_started")
        return None

    return {"project": project, "region": region, "job": job}


async def _list_job_executions(project: str, region: str, job: str) -> List[Dict[str, Any]]:
    token = await _get_access_token()
    if not token:
        logger.debug("No access token available; skipping Cloud Run Job trigger")
        return

    url = f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}/executions?pageSize=10"
    headers = {"Authorization": f"Bearer {token}"}
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"List executions failed (status={resp.status}): {text}")
                return []
            payload = await resp.json()
            return payload.get("executions", [])


def _has_running_execution(executions: List[Dict[str, Any]]) -> bool:
    # Check all execution, if all execution has completionTime, then return False
    for execution in executions:
        completion_time = execution.get("completionTime")
        delete_time = execution.get("deleteTime")
        if (completion_time is None or completion_time == "") and (delete_time is None or delete_time == ""):
            # Detected running execution
            logger.debug(f"Detected running execution: {execution}")
            return True
    return False


async def _run_job(
    job: str,
    task_count: int = 1,
) -> bool:
    """Run a Cloud Run job with specified configuration.
    
    Args:
        job: Cloud Run job name
        task_count: Number of parallel tasks to run (default: 1)
        args: List of arguments to pass to the container
        env_vars: List of environment variables in format [{"name": "KEY", "value": "VALUE"}]
        timeout: Job execution timeout in format like "3600s" or "1h"
    
    Returns:
        bool: True if job was triggered successfully, False otherwise
    """
    project = os.getenv("CLOUD_RUN_JOB_PROJECT", "").strip()
    region = os.getenv("CLOUD_RUN_JOB_REGION", "").strip()
    token = await _get_access_token()

    if not token:
        logger.debug("No access token available; skipping Cloud Run Job trigger")
        return
    
    url = f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}:run"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Build request body with overrides
    body = {}    
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=body) as resp:
            if resp.status not in (200, 202):
                text = await resp.text()
                logger.warning(f"Run job failed (status={resp.status}): {text}")
                return False
            logger.info(f"Triggered Cloud Run Job '{job}' in {region} with {task_count} parallel task(s)")
            return True

async def ensure_cloud_run_job_started(
    args: Optional[List[str]] = None,
    env_vars: Optional[List[Dict[str, str]]] = None,
    task_count: int = 1,
    timeout: Optional[str] = None
) -> None:
    """Ensure a Cloud Run Job execution exists if none currently running.

    Reads CLOUD_RUN_JOB_PROJECT, CLOUD_RUN_JOB_REGION, CLOUD_RUN_JOB_NAME from env.
    Safe no-op when env vars are missing or token can't be obtained.

    Args:
        args: List of arguments to pass to the container
        env_vars: List of environment variables in format [{"name": "KEY", "value": "VALUE"}]
        task_count: Number of parallel tasks to run (default: 1)
        timeout: Job execution timeout in format like "3600s" or "1h"
    """
    params = _get_cr_job_params()
    if not params:
        return

    try:
        executions = await _list_job_executions(params["project"], params["region"], params["job"])
        if _has_running_execution(executions):
            logger.debug("Cloud Run Job execution already running; not triggering a new one")
            return

        await _run_job(
            job=params["job"],
            args=args,
            env_vars=env_vars,
            task_count=task_count,
            timeout=timeout
        )
    except Exception as exc:
        logger.error(f"Error ensuring Cloud Run Job is started: {exc}")
        return

