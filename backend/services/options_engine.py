import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.recommendation import Recommendation, TabType, GradeEnum
from services.news_scraper import NewsScraper
from services.stock_data import StockDataService, DEFAULT_UNIVERSE
from services.claude_analyst import ClaudeAnalyst
from services.quant_scorer import (
    compute_options_quant_score, compute_entry_exit_options,
    recommend_strategy_type, compute_entry_exit_multi_leg,
)
import services.run_status as run_status

logger = logging.getLogger(__name__)

OPTIONS_UNIVERSE = DEFAULT_UNIVERSE[:30]


def _format_news(items) -> str:
    lines = []
    for it in items[:40]:
        lines.append(f"- [{it.ticker or 'MARKET'}] {it.source}: {it.headline}")
    if not lines:
        return (
            "Live news feeds are unavailable in this environment. "
            "Base recommendations on current market conditions, recent macro trends "
            "(tariff news, Fed policy, earnings season), and technical price action. "
            f"Today's date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}."
        )
    return "\n".join(lines)


def _format_technicals(data: dict, chain_context: dict | None = None) -> str:
    """Format full technical indicator suite for Claude, including real options chain prices."""
    lines = []
    for ticker, d in data.items():
        if not d:
            continue
        price = d.get("price", "?")
        chg = d.get("change_5d_pct", "?")
        rsi = d.get("rsi", "?")
        iv = d.get("atm_iv") or d.get("iv_rank_approx", "?")

        macd = d.get("macd", {})
        macd_str = (
            f"MACD={macd.get('macd','?')} signal={macd.get('signal','?')} "
            f"hist={macd.get('histogram','?')} [{macd.get('crossover','?')}]"
            if macd else "MACD=n/a"
        )

        bb = d.get("bollinger", {})
        bb_str = (
            f"BB upper={bb.get('upper','?')} lower={bb.get('lower','?')} "
            f"%B={bb.get('pct_b','?')} squeeze={'YES' if bb.get('squeeze') else 'no'}"
            if bb else "BB=n/a"
        )

        ma = d.get("moving_averages", {})
        ma_str = (
            f"MA20={ma.get('ma20','?')} MA50={ma.get('ma50','?')} MA200={ma.get('ma200','?')} "
            f"[above_50={'Y' if ma.get('above_ma50') else 'N'} "
            f"above_200={'Y' if ma.get('above_ma200') else 'N'} "
            f"{'GOLDEN_CROSS' if ma.get('golden_cross') else 'DEATH_CROSS' if ma.get('death_cross') else 'no_cross'}]"
            if ma else "MA=n/a"
        )

        fib = d.get("fibonacci", {})
        fib_str = (
            f"Fib: high={fib.get('high','?')} 61.8%={fib.get('fib_618','?')} "
            f"50%={fib.get('fib_500','?')} 38.2%={fib.get('fib_382','?')} low={fib.get('low','?')}"
            if fib else "Fib=n/a"
        )

        atr = d.get("atr", "?")
        vwap = d.get("vwap", "?")
        vol = d.get("volume_trend", {})
        vol_str = f"vol_trend={vol.get('trend','?')}({vol.get('ratio','?')}x)" if vol else ""

        # Real options chain prices — use these for entry/exit, NOT estimated premiums
        chain_str = ""
        if chain_context and ticker in chain_context:
            ctx = chain_context[ticker]
            chain_str = (
                f"\n  LIVE OPTIONS (exp {ctx['expiry']}) — use these real prices for entry/exit:\n"
                f"  Calls: {ctx['calls']}\n"
                f"  Puts:  {ctx['puts']}"
            )

        lines.append(
            f"{ticker}: ${price} 5d={chg}% RSI={rsi} IV≈{iv}% ATR={atr} VWAP={vwap}\n"
            f"  {macd_str}\n"
            f"  {bb_str}\n"
            f"  {ma_str}\n"
            f"  {fib_str} {vol_str}"
            f"{chain_str}"
        )
    return "\n\n".join(lines) if lines else "No technical data available."


def _grade_to_enum(grade: str) -> GradeEnum:
    mapping = {"A": GradeEnum.A, "B": GradeEnum.B, "C": GradeEnum.C, "D": GradeEnum.D, "F": GradeEnum.F}
    return mapping.get(grade.upper(), GradeEnum.C)


class OptionsEngine:
    def __init__(self, db: Session):
        self.db = db
        self.scraper = NewsScraper()
        self.stock_data = StockDataService()
        self.analyst = ClaudeAnalyst()

    def run(self) -> None:
        logger.info("OptionsEngine: starting analysis run")
        run_status.set_running("options")
        run_at = datetime.now(timezone.utc)
        try:
            news = self.scraper.fetch_all(OPTIONS_UNIVERSE[:15])
            technicals = self.stock_data.get_technicals_bulk(OPTIONS_UNIVERSE)
            top_tickers = list(technicals.keys())[:20]
            options_data = self.stock_data.get_options_data(top_tickers)
            for t in options_data:
                if t in technicals:
                    technicals[t].update(options_data[t])

            # Real options chain: actual bid/ask per strike so Claude uses live prices
            chain_context = self.stock_data.get_chain_context(top_tickers)

            # Pre-compute quantitative scores + strategy recommendation for each ticker
            quant_scores = {}
            for ticker, tech in technicals.items():
                if tech:
                    qs = compute_options_quant_score(tech)
                    strategy = recommend_strategy_type(tech)
                    ee = compute_entry_exit_options(tech, option_type="CALL")
                    ml = compute_entry_exit_multi_leg(tech, strategy)
                    quant_scores[ticker] = {
                        **qs,
                        "entry_exit": ee,
                        "recommended_strategy": strategy,
                        "multi_leg": ml,
                    }

            news_str = _format_news(news)
            tech_str = _format_technicals(technicals, chain_context)
            market_context = f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

            recs = self.analyst.analyze_options(news_str, tech_str, market_context,
                                                quant_scores=quant_scores)
            self._store(recs, run_at, technicals, quant_scores)
            run_status.set_success("options")
            logger.info("OptionsEngine: stored %d recommendations", len(recs))
        except Exception as e:
            run_status.set_error("options", str(e))
            logger.error("OptionsEngine run failed: %s", e, exc_info=True)

    def _store(self, recs: list[dict], run_at: datetime,
               technicals: dict | None = None, quant_scores: dict | None = None) -> None:
        technicals = technicals or {}
        quant_scores = quant_scores or {}
        for rec in recs:
            ticker = str(rec.get("ticker", "")).upper()
            qual_score = float(rec.get("qual_score") or rec.get("score", 50))
            qs_data = quant_scores.get(ticker, {})
            quant_score = qs_data.get("composite", None)
            combined = round(0.4 * quant_score + 0.6 * qual_score, 1) if quant_score is not None else qual_score

            # Entry/exit: prefer Claude's values; fall back to quant calculator
            ee = qs_data.get("entry_exit", {})
            opt_type = str(rec.get("option_type", "CALL")).upper()
            # Recompute if we need PUT entry/exit
            tech = technicals.get(ticker, {})
            if tech and opt_type == "PUT":
                from services.quant_scorer import compute_entry_exit_options as _cee
                ee = _cee(tech, option_type="PUT")

            strategy_type = str(rec.get("strategy_type") or qs_data.get("recommended_strategy") or "single_leg")
            ml = qs_data.get("multi_leg", {})

            # For single-leg, fall back to quant-computed suggested_strike if Claude didn't provide one
            strike = rec.get("strike")
            if not strike and strategy_type == "single_leg":
                strike = ee.get("suggested_strike")

            obj = Recommendation(
                tab=TabType.options,
                ticker=ticker,
                rank=int(rec.get("rank", 0)),
                score=float(rec.get("score", 50)),
                grade=_grade_to_enum(str(rec.get("grade", "C"))),
                explanation=str(rec.get("explanation", "")),
                quant_score=round(quant_score, 1) if quant_score is not None else None,
                qual_score=round(qual_score, 1),
                combined_score=combined,
                quant_components=json.dumps(qs_data.get("components", {})),
                option_type=opt_type if strategy_type == "single_leg" else "N/A",
                strategy_type=strategy_type,
                strike=strike,
                expiry=rec.get("expiry"),
                entry_price=rec.get("entry_price"),
                exit_price=rec.get("exit_price"),
                stop_loss=rec.get("stop_loss"),
                # Multi-leg strikes (Claude primary, quant fallback)
                short_call_strike=rec.get("short_call_strike") or ml.get("short_call_strike"),
                long_call_strike=rec.get("long_call_strike") or ml.get("long_call_strike"),
                short_put_strike=rec.get("short_put_strike") or ml.get("short_put_strike"),
                long_put_strike=rec.get("long_put_strike") or ml.get("long_put_strike"),
                net_credit=rec.get("net_credit") or ml.get("net_credit"),
                max_profit=rec.get("max_profit") or ml.get("max_profit"),
                max_loss=rec.get("max_loss") or ml.get("max_loss"),
                breakeven_low=rec.get("breakeven_low") or ml.get("breakeven_low"),
                breakeven_high=rec.get("breakeven_high") or ml.get("breakeven_high"),
                underlying_entry=rec.get("underlying_entry") or ee.get("underlying_entry"),
                underlying_target=rec.get("underlying_target") or ee.get("underlying_target"),
                underlying_stop=rec.get("underlying_stop") or ee.get("underlying_stop"),
                run_at=run_at,
            )
            self.db.add(obj)
        self.db.commit()
