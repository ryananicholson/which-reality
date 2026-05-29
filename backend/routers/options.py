import threading
import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models.recommendation import Recommendation, TabType
from schemas.recommendation import RecommendationSchema

router = APIRouter()
logger = logging.getLogger(__name__)


def _latest_batch(db: Session, tab: TabType) -> List[Recommendation]:
    """Return the 5 recommendations from the most recent run_at batch."""
    latest = (
        db.query(Recommendation.run_at)
        .filter(Recommendation.tab == tab)
        .order_by(desc(Recommendation.run_at))
        .first()
    )
    if not latest:
        return []
    return (
        db.query(Recommendation)
        .filter(Recommendation.tab == tab, Recommendation.run_at == latest[0])
        .order_by(Recommendation.rank)
        .all()
    )


@router.get("/recommendations", response_model=List[RecommendationSchema])
def get_options_recommendations(db: Session = Depends(get_db)):
    return _latest_batch(db, TabType.options)


@router.post("/refresh")
def refresh_options(db: Session = Depends(get_db)):
    from services.options_engine import OptionsEngine

    def _run():
        from database import SessionLocal
        s = SessionLocal()
        try:
            OptionsEngine(s).run()
        finally:
            s.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "queued", "message": "Options analysis started in background"}
