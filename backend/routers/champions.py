import logging
import threading
import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.champion import Champion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/champions", tags=["Champions"])

STRATEGY_ORDER = ["wheel", "options", "longterm"]

_job: dict = {"running": False, "started_at": None, "error": None, "last_run": None}


def _serialize(row: Champion) -> dict:
    return {
        "strategy": row.strategy,
        "ticker": row.ticker,
        "score": row.score,
        "grade": row.grade,
        "reason": row.reason,
        "universe_size": row.universe_size,
        "survivors_count": row.survivors_count,
        "run_at": row.run_at.isoformat() if row.run_at else None,
    }


@router.get("")
def get_champions(db: Session = Depends(get_db)):
    rows = db.query(Champion).order_by(Champion.run_at.desc()).limit(3).all()
    ordered = sorted(
        rows,
        key=lambda r: STRATEGY_ORDER.index(r.strategy) if r.strategy in STRATEGY_ORDER else 99,
    )
    run_at = rows[0].run_at.isoformat() if rows else None
    return {
        "champions": [_serialize(r) for r in ordered],
        "run_at": run_at,
        "scan_running": _job["running"],
        "last_error": _job["error"],
    }


def _run_job():
    from database import SessionLocal
    from services.champions_engine import run as run_champions

    _job["running"] = True
    _job["error"] = None
    db = SessionLocal()
    try:
        success, error = run_champions(db)
        _job["error"] = error
        _job["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    except Exception as e:
        _job["error"] = str(e)
        logger.error("Champions refresh failed: %s", e, exc_info=True)
    finally:
        _job["running"] = False
        db.close()


@router.post("/refresh")
def refresh_champions():
    if _job["running"]:
        return {"status": "Scan already in progress — check back shortly"}
    _job["error"] = None
    _job["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t = threading.Thread(target=_run_job, daemon=True)
    t.start()
    return {"status": "started"}
