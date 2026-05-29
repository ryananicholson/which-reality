import threading
import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models.recommendation import Recommendation, TabType
from schemas.recommendation import RecommendationSchema
from routers.options import _latest_batch

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/recommendations", response_model=List[RecommendationSchema])
def get_longterm_recommendations(db: Session = Depends(get_db)):
    return _latest_batch(db, TabType.longterm)


@router.post("/refresh")
def refresh_longterm():
    def _run():
        from database import SessionLocal
        from services.longterm_engine import LongTermEngine
        s = SessionLocal()
        try:
            LongTermEngine(s).run()
        finally:
            s.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "queued", "message": "Long-term analysis started in background"}
