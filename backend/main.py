import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _auto_run_if_empty() -> None:
    """Run all analysis engines in a background thread if the DB has no data yet."""
    import threading

    def _run():
        import time
        time.sleep(3)  # let the app finish starting before hammering the DB
        from database import SessionLocal
        from models.recommendation import Recommendation
        db = SessionLocal()
        try:
            count = db.query(Recommendation).count()
            if count > 0:
                logger.info("Auto-seed: DB already has %d recommendations — skipping", count)
                return
            logger.info("Auto-seed: database is empty — running initial analysis now")
            from services.options_engine import OptionsEngine
            from services.wheel_engine import WheelEngine
            from services.longterm_engine import LongTermEngine
            from services.champions_engine import run as run_champions
            OptionsEngine(db).run()
            WheelEngine(db).run()
            LongTermEngine(db).run()
            run_champions(db)
            logger.info("Auto-seed: initial analysis complete")
        except Exception as e:
            logger.error("Auto-seed failed: %s", e, exc_info=True)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database import init_db
    from scheduler import start_scheduler

    init_db()
    logger.info("Database initialised")
    scheduler = start_scheduler()
    _auto_run_if_empty()
    yield
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(
    title="Trading Recommendations API",
    description="AI-powered options, wheel strategy, and long-term investment recommendations",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import options, wheel, longterm  # noqa: E402
from routers import market, account, performance, watchlist, champions, covered_calls, scanner, options_flow, discovery, dcf, triggers, advanced_scanner, top_rated_scanner, momentum  # noqa: E402

app.include_router(options.router, prefix="/api/options", tags=["Options"])
app.include_router(wheel.router, prefix="/api/wheel", tags=["Wheel Strategy"])
app.include_router(longterm.router, prefix="/api/longterm", tags=["Long-Term"])
app.include_router(covered_calls.router)
app.include_router(advanced_scanner.router)
app.include_router(top_rated_scanner.router)
app.include_router(momentum.router)
app.include_router(market.router)
app.include_router(account.router)
app.include_router(performance.router)
app.include_router(watchlist.router)
app.include_router(champions.router)
app.include_router(scanner.router)
app.include_router(options_flow.router)
app.include_router(discovery.router)
app.include_router(dcf.router)
app.include_router(triggers.router)


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.get("/api/status", tags=["Health"])
def run_status_endpoint():
    from services.run_status import get_all
    return get_all()


# Serve the built React frontend — must come last
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        return FileResponse(os.path.join(_frontend_dist, "index.html"))
