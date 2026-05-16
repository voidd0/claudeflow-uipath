"""
UiPath Orchestrator REST API client for ClaudeFlow.
Handles OAuth 2.0 client-credentials auth with token caching,
process start, task query, and status polling.
"""

import os
import time
import json
import requests
from dataclasses import dataclass, field
from typing import Optional


UIPATH_TOKEN_URL = "https://account.uipath.com/oauth/token"
UIPATH_BASE_URL = "https://cloud.uipath.com/{account}/{tenant}/orchestrator_/api/v2"


@dataclass
class OrchestratorConfig:
    account_name: str
    tenant_name: str
    client_id: str
    client_secret: str
    folder_id: str  # UiPath Orchestrator folder (org unit) ID


@dataclass
class _TokenCache:
    access_token: str = ""
    expires_at: float = 0.0


class OrchestratorClient:
    """
    Thin wrapper around UiPath Orchestrator REST API v2.
    Uses OAuth 2.0 client credentials. Token is cached in-process
    and refreshed automatically when it expires.
    """

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._token = _TokenCache()
        self._base = UIPATH_BASE_URL.format(
            account=config.account_name,
            tenant=config.tenant_name,
        )

    # ── auth ────────────────────────────────────────────────────────────────

    def _ensure_token(self) -> str:
        if time.time() < self._token.expires_at - 60:
            return self._token.access_token

        resp = requests.post(
            UIPATH_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": "OR.Execution OR.Queues OR.Jobs OR.Tasks",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token.access_token = data["access_token"]
        self._token.expires_at = time.time() + data.get("expires_in", 3600)
        return self._token.access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Content-Type": "application/json",
            "X-UIPATH-OrganizationUnitId": self.config.folder_id,
        }

    # ── processes ────────────────────────────────────────────────────────────

    def list_processes(self) -> list[dict]:
        """Return available process releases in the configured folder."""
        resp = requests.get(
            f"{self._base}/Releases",
            headers=self._headers(),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_process_key(self, process_name: str) -> Optional[str]:
        """Resolve a process name to its release key."""
        for p in self.list_processes():
            if p.get("Name", "") == process_name:
                return p.get("Key")
        return None

    # ── jobs (process instances) ─────────────────────────────────────────────

    def start_job(
        self,
        release_key: str,
        input_arguments: dict | None = None,
        job_priority: str = "Normal",
    ) -> dict:
        """
        Start a process job in UiPath Orchestrator.
        Returns the created job object (includes Id, State).
        """
        payload = {
            "startInfo": {
                "ReleaseKey": release_key,
                "Strategy": "All",
                "JobPriority": job_priority,
                "InputArguments": json.dumps(input_arguments or {}),
            }
        }
        resp = requests.post(
            f"{self._base}/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        jobs = resp.json().get("value", [])
        return jobs[0] if jobs else {}

    def get_job(self, job_id: int) -> dict:
        """Return current state of a job by ID."""
        resp = requests.get(
            f"{self._base}/Jobs({job_id})",
            headers=self._headers(),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def wait_for_job(
        self,
        job_id: int,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> dict:
        """
        Poll until job reaches a terminal state (Successful, Faulted, Stopped).
        Raises TimeoutError if timeout expires.
        """
        terminal = {"Successful", "Faulted", "Stopped"}
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get_job(job_id)
            if job.get("State") in terminal:
                return job
            time.sleep(poll_interval)
        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

    # ── tasks (human-in-loop Action Center) ──────────────────────────────────

    def list_tasks(self, status_filter: str = "Pending") -> list[dict]:
        """List Action Center tasks. status_filter: Pending | Completed | Abandoned."""
        resp = requests.get(
            f"{self._base}/Tasks/UiPath.Server.Configuration.OData.GetTasksAcrossAllFolders",
            headers=self._headers(),
            params={"$filter": f"Status eq '{status_filter}'", "$top": 50},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def complete_task(self, task_id: int, action: str, comment: str = "") -> dict:
        """
        Complete (approve/reject) a human-in-loop task.
        action: 'Approve' | 'Reject' | str matching task's configured actions.
        """
        payload = {"action": action, "comment": comment}
        resp = requests.post(
            f"{self._base}/Tasks/UiPath.Server.Configuration.OData.CompleteTask",
            headers=self._headers(),
            json={"taskId": task_id, "taskData": payload},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    # ── queues (optional — for async work items) ─────────────────────────────

    def add_queue_item(self, queue_name: str, specific_content: dict) -> dict:
        """Add a work item to an Orchestrator queue."""
        payload = {
            "itemData": {
                "Name": queue_name,
                "Priority": "Normal",
                "SpecificContent": specific_content,
            }
        }
        resp = requests.post(
            f"{self._base}/Queues/UiPath.Server.Configuration.OData.AddQueueItem",
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()


def client_from_env() -> OrchestratorClient:
    """Build OrchestratorClient from environment variables."""
    return OrchestratorClient(
        OrchestratorConfig(
            account_name=os.environ["UIPATH_ACCOUNT_NAME"],
            tenant_name=os.environ["UIPATH_TENANT_NAME"],
            client_id=os.environ["UIPATH_CLIENT_ID"],
            client_secret=os.environ["UIPATH_CLIENT_SECRET"],
            folder_id=os.environ["UIPATH_FOLDER_ID"],
        )
    )
