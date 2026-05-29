import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from models.wheel import WheelRecommendation, WheelPosition, WheelStatus
from services.news_scraper import NewsScraper
from services.stock_data import StockDataService, DEFAULT_UNIVERSE
from services.claude_analyst import ClaudeAnalyst
from services.quant_scorer import compute_wheel_quant_score, compute_entry_exit_wheel
import services.run_status as run_status

logger = logging.getLogger(__name__)

WHEEL_UNIVERSE = DEFAULT_UNIVERSE


def _format_news(items) -> str:
    lines = []
    for it in items[:40]:
        lines.append(f"- [{it.ticker or 'MARKET'}] {it.source}: {it.headline}")
    if not lines:
        return (
            "Live news feeds are unavailable in this environment. "
            "Base recommendations on current market conditions, recent macro trends, "
            "and typical high-IV stocks suitable for the wheel strategy. "
            f"Today's date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}."
        )
    return "\n".join(lines)


def _format_screening(data: dict) -> str:
    """Format technical data for wheel strategy — emphasise support levels and IV."""
    lines = []
    for ticker, d in data.items():
        if not d:
            continue
        price = d.get("price", "?")
        rsi = d.get("rsi", "?")
        iv = d.get("atm_iv") or d.get("iv_rank_approx", "?")
        atr = d.get("atr", "?")

        ma = d.get("moving_averages", {})
        trend = "UPTREND" if ma.get("above_ma50") and ma.get("above_ma200") else \
                "DOWNTREND" if not ma.get("above_ma50") and not ma.get("above_ma200") else "MIXED"
        ma_str = f"MA50={ma.get('ma50','?')} MA200={ma.get('ma200','?')} [{trend}]" if ma else ""

        fib = d.get("fibonacci", {})
        fib_str = (
            f"Support zones: Fib38.2%={fib.get('fib_382','?')} "
            f"Fib50%={fib.get('fib_500','?')} Fib61.8%={fib.get('fib_618','?')}"
            if fib else ""
        )

        sr = d.get("support_resistance", {})
        sr_str = f"S1={sr.get('support_1','?')} S2={sr.get('support_2','?')}" if sr else ""

        bb = d.get("bollinger", {})
        bb_str = f"BB%B={bb.get('pct_b','?')} squeeze={'YES' if bb.get('squeeze') else 'no'}" if bb else ""

        vol = d.get("volume_trend", {})
        vol_str = f"vol={vol.get('trend','?')}" if vol else ""

        lines.append(
            f"{ticker}: ${price} RSI={rsi} IV≈{iv}% ATR={atr} {vol_str}\n"
            f"  {ma_str}\n"
            f"  {fib_str} | {sr_str}\n"
            f"  {bb_str}"
        )
    return "\n\n".join(lines) if lines else "No screening data available."


class WheelEngine:
    def __init__(self, db: Session):
        self.db = db
        self.scraper = NewsScraper()
        self.stock_data = StockDataService()
        self.analyst = ClaudeAnalyst()

    def run(self) -> None:
        logger.info("WheelEngine: starting analysis run")
        run_status.set_running("wheel")
        run_at = datetime.now(timezone.utc)
        try:
            news = self.scraper.fetch_all(WHEEL_UNIVERSE[:15])
            screening = self.stock_data.get_wheel_screening_data(WHEEL_UNIVERSE)
            news_str = _format_news(news)
            screening_str = _format_screening(screening)
            logger.info("WheelEngine: fetched technicals for %d tickers", len(screening))

            # Pre-compute quantitative scores
            quant_scores = {}
            for ticker, tech in screening.items():
                if tech:
                    qs = compute_wheel_quant_score(tech)
                    ee = compute_entry_exit_wheel(tech)
                    quant_scores[ticker] = {**qs, "entry_exit": ee}

            recs = self.analyst.analyze_wheel(news_str, screening_str, quant_scores=quant_scores)

            # Snap each Claude-suggested strike to the nearest real chain strike
            for rec in recs:
                ticker = str(rec.get("ticker", "")).upper()
                suggested = rec.get("put_strike")
                if suggested:
                    try:
                        snapped = self.stock_data.snap_put_strike(ticker, float(suggested))
                        if snapped:
                            rec["put_strike"] = snapped["strike"]
                            rec["put_expiry"] = snapped["expiry"]
                            if snapped["mid_premium"] > 0:
                                rec["put_premium"] = snapped["mid_premium"]
                            logger.info(
                                "WheelEngine: snapped %s strike %.2f → %.2f (exp %s)",
                                ticker, suggested, snapped["strike"], snapped["expiry"],
                            )
                    except Exception as snap_err:
                        logger.debug("snap_put_strike skipped for %s: %s", ticker, snap_err)

            self._store(recs, run_at, quant_scores)
            run_status.set_success("wheel")
            logger.info("WheelEngine: stored %d recommendations", len(recs))
        except Exception as e:
            run_status.set_error("wheel", str(e))
            logger.error("WheelEngine run failed: %s", e, exc_info=True)

    def _store(self, recs: list[dict], run_at: datetime, quant_scores: dict | None = None) -> None:
        quant_scores = quant_scores or {}
        for rec in recs:
            ticker = str(rec.get("ticker", "")).upper()
            qual_score = float(rec.get("qual_score") or rec.get("score", 50))
            qs_data = quant_scores.get(ticker, {})
            quant_score = qs_data.get("composite", None)
            combined = round(0.4 * quant_score + 0.6 * qual_score, 1) if quant_score is not None else qual_score

            put_strike = rec.get("put_strike")
            put_premium = rec.get("put_premium")
            ee = qs_data.get("entry_exit", {})
            pct_otm = ee.get("pct_otm")
            breakeven = round(put_strike - put_premium, 2) if put_strike and put_premium else None

            obj = WheelRecommendation(
                ticker=ticker,
                rank=int(rec.get("rank", 0)),
                score=float(rec.get("score", 50)),
                grade=str(rec.get("grade", "C")),
                explanation=str(rec.get("explanation", "")),
                put_strike=put_strike,
                put_expiry=rec.get("put_expiry"),
                put_premium=put_premium,
                iv_rank=rec.get("iv_rank"),
                quant_score=round(quant_score, 1) if quant_score is not None else None,
                qual_score=round(qual_score, 1),
                combined_score=combined,
                quant_components=json.dumps(qs_data.get("components", {})),
                pct_otm=pct_otm,
                breakeven=breakeven,
                assignment_chance_pct=rec.get("assignment_chance_pct"),
                assignment_risk=rec.get("assignment_risk"),
                run_at=run_at,
            )
            self.db.add(obj)
        self.db.commit()

    def generate_call_suggestion(self, position: WheelPosition) -> str | None:
        """Generate a covered call suggestion for an assigned position."""
        try:
            current_price = self.stock_data.get_current_price(position.ticker)
            if not current_price:
                return None
            news = self.scraper.fetch_all([position.ticker])
            news_str = _format_news(news)
            assigned_date = (
                position.assigned_at.strftime("%Y-%m-%d")
                if position.assigned_at
                else "unknown"
            )
            technicals = self.stock_data.get_price_and_technicals(position.ticker)
            suggestion = self.analyst.generate_call_suggestion(
                ticker=position.ticker,
                cost_basis=position.cost_basis or position.put_strike,
                current_price=current_price,
                assigned_date=assigned_date,
                iv_rank=technicals.get("iv_rank_approx"),
                earnings_date=None,
                news_bullets=news_str,
                technicals=technicals,
            )
            return json.dumps(suggestion)
        except Exception as e:
            logger.error("Call suggestion error for position %d: %s", position.id, e)
            return None

    def refresh_all_call_suggestions(self) -> None:
        """Weekly job: refresh call suggestions for all assigned positions."""
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        positions = (
            self.db.query(WheelPosition)
            .filter(WheelPosition.status == WheelStatus.assigned)
            .filter(
                (WheelPosition.call_suggestion_at == None) |  # noqa: E711
                (WheelPosition.call_suggestion_at < stale_cutoff)
            )
            .all()
        )
        for pos in positions:
            suggestion = self.generate_call_suggestion(pos)
            if suggestion:
                pos.call_suggestion = suggestion
                pos.call_suggestion_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info("Refreshed call suggestions for %d positions", len(positions))
