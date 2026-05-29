import logging
from datetime import date, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

EASTERN = pytz.timezone("America/New_York")
# Weekdays only — holiday check happens inside the job before running
RUN_TIMES = [(9, 0), (9, 45), (12, 0), (15, 0), (18, 0)]


# ---------------------------------------------------------------------------
# NYSE holiday calendar
# ---------------------------------------------------------------------------

def _easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(114 + h + l - 7 * m, 31)
    return date(year, month, day + 1)


def _observed(d: date) -> date:
    """If holiday falls on Saturday → Friday; Sunday → Monday."""
    if d.weekday() == 5:   # Saturday
        return d - timedelta(days=1)
    if d.weekday() == 6:   # Sunday
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence of weekday (0=Mon) in the given month/year."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last occurrence of weekday in the given month/year."""
    # Start from last day of month and work back
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def nyse_holidays(year: int) -> set[date]:
    """Return the set of NYSE market holidays for the given year."""
    easter = _easter(year)
    good_friday = easter - timedelta(days=2)

    holidays = {
        # New Year's Day
        _observed(date(year, 1, 1)),
        # Martin Luther King Jr. Day — 3rd Monday of January
        _nth_weekday(year, 1, 0, 3),
        # Presidents' Day — 3rd Monday of February
        _nth_weekday(year, 2, 0, 3),
        # Good Friday
        good_friday,
        # Memorial Day — last Monday of May
        _last_weekday(year, 5, 0),
        # Juneteenth — June 19 (observed)
        _observed(date(year, 6, 19)),
        # Independence Day — July 4 (observed)
        _observed(date(year, 7, 4)),
        # Labor Day — 1st Monday of September
        _nth_weekday(year, 9, 0, 1),
        # Thanksgiving — 4th Thursday of November
        _nth_weekday(year, 11, 3, 4),
        # Christmas — December 25 (observed)
        _observed(date(year, 12, 25)),
    }
    return holidays


def is_trading_day(d: date | None = None) -> bool:
    """Return True if the given date (default: today Eastern) is an NYSE trading day."""
    if d is None:
        d = date.today()   # caller should pass Eastern-local date
    if d.weekday() >= 5:   # Saturday=5, Sunday=6
        return False
    return d not in nyse_holidays(d.year)


# ---------------------------------------------------------------------------
# Scheduler jobs
# ---------------------------------------------------------------------------

def run_all_analyses() -> None:
    from database import SessionLocal
    from services.options_engine import OptionsEngine
    from services.wheel_engine import WheelEngine
    from services.longterm_engine import LongTermEngine

    today_eastern = date.today()   # server runs in UTC; check via pytz below
    import datetime as _dt
    today_eastern = _dt.datetime.now(EASTERN).date()

    if not is_trading_day(today_eastern):
        logger.info(
            "Scheduler: skipping run on %s — not a trading day (weekend or NYSE holiday)",
            today_eastern,
        )
        return

    logger.info("Scheduler: starting all analysis pipelines for %s", today_eastern)
    db = SessionLocal()
    try:
        OptionsEngine(db).run()
        WheelEngine(db).run()
        LongTermEngine(db).run()
    except Exception as e:
        logger.error("Scheduled run failed: %s", e, exc_info=True)
    finally:
        db.close()


def run_champions_scan() -> None:
    from database import SessionLocal
    from services.champions_engine import run as run_champions
    import datetime as _dt

    today_eastern = _dt.datetime.now(EASTERN).date()
    if not is_trading_day(today_eastern):
        logger.info("Scheduler: skipping champions scan — not a trading day")
        return

    logger.info("Scheduler: running daily champions scan")
    db = SessionLocal()
    try:
        run_champions(db)
    except Exception as e:
        logger.error("Champions scan failed: %s", e, exc_info=True)
    finally:
        db.close()


def run_advanced_scans() -> None:
    """Run dividend income + big mover scans overnight so results are ready at market open."""
    import datetime as _dt

    today_eastern = _dt.datetime.now(EASTERN).date()
    if not is_trading_day(today_eastern):
        logger.info("Scheduler: skipping advanced scans — not a trading day")
        return

    logger.info("Scheduler: running overnight dividend + mover scans")
    from services.advanced_scanner_service import run_dividend_scan, run_mover_scan
    try:
        run_dividend_scan(force=True)
        logger.info("Scheduler: dividend scan complete")
    except Exception as e:
        logger.error("Overnight dividend scan failed: %s", e, exc_info=True)
    try:
        run_mover_scan(force=True)
        logger.info("Scheduler: mover scan complete")
    except Exception as e:
        logger.error("Overnight mover scan failed: %s", e, exc_info=True)


def run_top_rated_scan_job() -> None:
    """Run the top-rated market scanner — fires daily at 10 AM Eastern."""
    import datetime as _dt

    today_eastern = _dt.datetime.now(EASTERN).date()
    if not is_trading_day(today_eastern):
        logger.info("Scheduler: skipping top-rated scan — not a trading day")
        return

    logger.info("Scheduler: running top-rated market scan")
    from services.top_rated_scanner_service import run_top_rated_scan
    try:
        run_top_rated_scan(force=True)
        logger.info("Scheduler: top-rated scan complete")
    except Exception as e:
        logger.error("Top-rated scan failed: %s", e, exc_info=True)


def refresh_call_suggestions() -> None:
    from database import SessionLocal
    from services.wheel_engine import WheelEngine
    import datetime as _dt

    today_eastern = _dt.datetime.now(EASTERN).date()
    if not is_trading_day(today_eastern):
        logger.info("Scheduler: skipping call suggestion refresh — not a trading day")
        return

    logger.info("Scheduler: refreshing weekly call suggestions")
    db = SessionLocal()
    try:
        WheelEngine(db).refresh_all_call_suggestions()
    except Exception as e:
        logger.error("Call suggestion refresh failed: %s", e, exc_info=True)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=EASTERN)

    for hour, minute in RUN_TIMES:
        scheduler.add_job(
            run_all_analyses,
            # day_of_week="mon-fri" fires the job — trading day check happens inside
            CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute, timezone=EASTERN),
            id=f"analysis_{hour:02d}{minute:02d}",
            replace_existing=True,
            misfire_grace_time=300,
        )

    # Daily 9:10 AM Eastern — champions scan (one batched Claude call)
    scheduler.add_job(
        run_champions_scan,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=10, timezone=EASTERN),
        id="champions_daily",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Daily 6:00 AM Eastern — overnight dividend + mover scans (results ready at open)
    scheduler.add_job(
        run_advanced_scans,
        CronTrigger(day_of_week="mon-fri", hour=6, minute=0, timezone=EASTERN),
        id="advanced_scans_overnight",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # Daily 10:00 AM Eastern — top-rated market scanner (after open, prices settled)
    scheduler.add_job(
        run_top_rated_scan_job,
        CronTrigger(day_of_week="mon-fri", hour=10, minute=0, timezone=EASTERN),
        id="top_rated_scan_daily",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # Weekly Tuesday 9:05 AM Eastern — refresh covered call suggestions
    # (Monday could be a holiday, so Tuesday is safer)
    scheduler.add_job(
        refresh_call_suggestions,
        CronTrigger(day_of_week="tue", hour=9, minute=5, timezone=EASTERN),
        id="call_suggestions_weekly",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started. Jobs fire Mon-Fri at %s Eastern (skips NYSE holidays automatically).",
        ", ".join(f"{h:02d}:{m:02d}" for h, m in RUN_TIMES),
    )
    return scheduler
