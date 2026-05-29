"""
In-memory run status tracker.
Each engine updates this on start/success/failure.
Exposed via /api/status so the frontend can surface errors to the user.
"""
from datetime import datetime, timezone

_status: dict = {
    "options":  {"state": "idle", "last_run": None, "error": None},
    "wheel":    {"state": "idle", "last_run": None, "error": None},
    "longterm": {"state": "idle", "last_run": None, "error": None},
}


def set_running(engine: str) -> None:
    _status[engine] = {"state": "running", "last_run": None, "error": None}


def set_success(engine: str) -> None:
    _status[engine] = {
        "state": "ok",
        "last_run": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }


def set_error(engine: str, msg: str) -> None:
    _status[engine] = {
        "state": "error",
        "last_run": datetime.now(timezone.utc).isoformat(),
        "error": str(msg),
    }


def get_all() -> dict:
    return dict(_status)
