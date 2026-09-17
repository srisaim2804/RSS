"""Thin REST client for the ire-a2-tester-api, matching /openapi.json:

POST   /v1/sessions?seed=...
GET    /v1/sessions/{sid}/rounds/{r}/traffic
POST   /v1/sessions/{sid}/rounds/{r}/submission   (multipart file=...)
GET    /v1/sessions/{sid}/rounds/{r}/actions
GET    /v1/sessions/{sid}/rounds/{r}/report
GET    /v1/sessions/{sid}/report
DELETE /v1/sessions/{sid}
"""
from __future__ import annotations

from pathlib import Path

import requests


class TesterClient:
    def __init__(self, base: str, timeout: float = 1800.0) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout

    def create_session(self, seed: int = 42) -> dict:
        r = requests.post(f"{self.base}/v1/sessions", params={"seed": seed}, timeout=60)
        r.raise_for_status()
        return r.json()

    def get_traffic(self, session_id: str, round_index: int, out_path: str | Path) -> Path:
        url = f"{self.base}/v1/sessions/{session_id}/rounds/{round_index}/traffic"
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        out_path = Path(out_path)
        out_path.write_bytes(r.content)
        return out_path

    def submit(self, session_id: str, round_index: int, submission_path: str | Path) -> dict:
        url = f"{self.base}/v1/sessions/{session_id}/rounds/{round_index}/submission"
        submission_path = Path(submission_path)
        with submission_path.open("rb") as fh:
            files = {"file": (submission_path.name, fh, "application/octet-stream")}
            r = requests.post(url, files=files, timeout=self.timeout)
        if r.status_code == 422:
            return {"_status": 422, "_errors": r.json()}
        r.raise_for_status()
        return r.json()

    def get_actions(self, session_id: str, round_index: int, out_path: str | Path) -> Path:
        url = f"{self.base}/v1/sessions/{session_id}/rounds/{round_index}/actions"
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        out_path = Path(out_path)
        out_path.write_bytes(r.content)
        return out_path

    def get_round_report(self, session_id: str, round_index: int) -> dict:
        url = f"{self.base}/v1/sessions/{session_id}/rounds/{round_index}/report"
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_session_report(self, session_id: str) -> dict:
        r = requests.get(f"{self.base}/v1/sessions/{session_id}/report", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def delete_session(self, session_id: str) -> None:
        r = requests.delete(f"{self.base}/v1/sessions/{session_id}", timeout=60)
        r.raise_for_status()
