from fastapi import APIRouter
from services import discovery_engine

router = APIRouter(prefix="/api/discovery", tags=["Discovery"])


@router.get("")
def get_discovery():
    """Return cached discovery results, or current scan status."""
    return discovery_engine.get_state()


@router.post("/scan")
def trigger_scan():
    """Force a fresh scan (ignores cache)."""
    started = discovery_engine.trigger_scan(force=True)
    state = discovery_engine.get_state()
    return {"started": started, "status": state["status"]}
