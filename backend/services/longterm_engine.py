import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.recommendation import Recommendation, TabType, GradeEnum
from services.news_scraper import NewsScraper
from services.stock_data import StockDataService, DEFAULT_UNIVERSE
from services.claude_analyst import ClaudeAnalyst
from services.quant_scorer import compute_longterm_quant_score, compute_entry_exit_longterm
import services.run_status as run_status

logger = logging.getLogger(__name__)

LONGTERM_UNIVERSE = DEFAULT_UNIVERSE


def _format_news(items) -> str:
    lines = []
    for it in items[:40]:
        lines.append(f"- [{it.ticker or 'MARKET'}] {it.source}: {it.headline}")
    if not lines:
        return (
            "Live news feeds are unavailable in this environment. "
            "Base recommendations on well-known fundamentals, long-term secular trends "
            "(AI, energy transition, healthcare, consumer staples), and dividend reliability. "
            f"Today's date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}."
        )
    return "\n".join(lines)


def _format_fundamentals_and_technicals(fund_data: dict, tech_data: dict) -> str:
    """Combine fundamentals + long-term technical trend data for Claude."""
    lines = []
    tickers = set(list(fund_data.keys()) + list(tech_data.keys()))
    for ticker in tickers:
        f = fund_data.get(ticker, {})
        t = tech_data.get(ticker, {})
        if not f and not t:
            continue

        # Fundamentals
        pe = f.get("pe_ratio", "?")
        eps = f.get("eps_growth_ttm", "?")
        rev = f.get("revenue_growth_ttm", "?")
        div = f.get("div_yield", "?")
        sector = f.get("sector", "?")
        rating = f.get("analyst_rating", "?")

        # Long-term technicals — focus on MAs and relative trend
        ma = t.get("moving_averages", {})
        trend = "STRONG_UPTREND" if (ma.get("above_ma50") and ma.get("above_ma200") and ma.get("golden_cross")) \
           else "UPTREND" if (ma.get("above_ma50") and ma.get("above_ma200")) \
           else "DOWNTREND" if (not ma.get("above_ma50") and not ma.get("above_ma200")) \
           else "MIXED"
        ma_str = (
            f"MA50={ma.get('ma50','?')} MA200={ma.get('ma200','?')} "
            f"price=${t.get('price','?')} [{trend}]"
            if ma else f"price=${t.get('price','?')}"
        )

        rsi = t.get("rsi", "?")
        vol = t.get("volume_trend", {})
        vol_str = f"vol_trend={vol.get('trend','?')}" if vol else ""

        fib = t.get("fibonacci", {})
        fib_str = f"52w range: {fib.get('low','?')}-{fib.get('high','?')}" if fib else ""

        lines.append(
            f"{ticker} ({sector}): PE={pe} EPS_growth={eps} rev_growth={rev} "
            f"div_yield={div} analyst={rating} RSI={rsi} {vol_str}\n"
            f"  {ma_str}\n"
            f"  {fib_str}"
        )
    return "\n\n".join(lines) if lines else "No fundamental/technical data available."


def _grade_to_enum(grade: str) -> GradeEnum:
    mapping = {"A": GradeEnum.A, "B": GradeEnum.B, "C": GradeEnum.C, "D": GradeEnum.D, "F": GradeEnum.F}
    return mapping.get(grade.upper(), GradeEnum.C)


class LongTermEngine:
    def __init__(self, db: Session):
        self.db = db
        self.scraper = NewsScraper()
        self.stock_data = StockDataService()
        self.analyst = ClaudeAnalyst()

    def run(self) -> None:
        logger.info("LongTermEngine: starting analysis run")
        run_status.set_running("longterm")
        run_at = datetime.now(timezone.utc)
        try:
            news = self.scraper.fetch_all(LONGTERM_UNIVERSE[:15])
            fundamentals = self.stock_data.get_fundamentals(LONGTERM_UNIVERSE)
            technicals = self.stock_data.get_technicals_bulk(LONGTERM_UNIVERSE)
            news_str = _format_news(news)
            fund_str = _format_fundamentals_and_technicals(fundamentals, technicals)

            # Pre-compute quantitative scores
            quant_scores = {}
            for ticker in set(list(technicals.keys()) + list(fundamentals.keys())):
                tech = technicals.get(ticker, {}) or {}
                fund = fundamentals.get(ticker, {}) or {}
                if tech or fund:
                    qs = compute_longterm_quant_score(tech, fund)
                    ee = compute_entry_exit_longterm(tech, fund)
                    quant_scores[ticker] = {**qs, "entry_exit": ee}

            recs = self.analyst.analyze_longterm(news_str, fund_str, quant_scores=quant_scores)
            self._store(recs, run_at, quant_scores)
            run_status.set_success("longterm")
            logger.info("LongTermEngine: stored %d recommendations", len(recs))
        except Exception as e:
            run_status.set_error("longterm", str(e))
            logger.error("LongTermEngine run failed: %s", e, exc_info=True)

    def _store(self, recs: list[dict], run_at: datetime, quant_scores: dict | None = None) -> None:
        quant_scores = quant_scores or {}
        for rec in recs:
            ticker = str(rec.get("ticker", "")).upper()
            qual_score = float(rec.get("qual_score") or rec.get("score", 50))
            qs_data = quant_scores.get(ticker, {})
            quant_score = qs_data.get("composite", None)
            combined = round(0.4 * quant_score + 0.6 * qual_score, 1) if quant_score is not None else qual_score

            ee = qs_data.get("entry_exit", {})
            obj = Recommendation(
                tab=TabType.longterm,
                ticker=ticker,
                rank=int(rec.get("rank", 0)),
                score=float(rec.get("score", 50)),
                grade=_grade_to_enum(str(rec.get("grade", "C"))),
                explanation=str(rec.get("explanation", "")),
                quant_score=round(quant_score, 1) if quant_score is not None else None,
                qual_score=round(qual_score, 1),
                combined_score=combined,
                quant_components=json.dumps(qs_data.get("components", {})),
                investment_type=str(rec.get("investment_type", "growth")).lower(),
                target_price=rec.get("target_price"),
                time_horizon=rec.get("time_horizon"),
                buy_zone_low=rec.get("buy_zone_low") or ee.get("buy_zone_low"),
                buy_zone_high=rec.get("buy_zone_high") or ee.get("buy_zone_high"),
                invalidation_stop=rec.get("invalidation_stop") or ee.get("invalidation_stop"),
                run_at=run_at,
            )
            self.db.add(obj)
        self.db.commit()
