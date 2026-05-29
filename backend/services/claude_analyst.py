import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import anthropic
from config import settings

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"


def _clean_json(text: str) -> str:
    """Extract the outermost JSON object or array, whichever comes first."""
    text = re.sub(r"```(?:json)?|```", "", text).strip()
    obj = text.find('{')
    arr = text.find('[')
    # Pick whichever opening bracket appears first
    if obj == -1 and arr == -1:
        return text
    if obj == -1 or (arr != -1 and arr < obj):
        start, end_ch = arr, ']'
    else:
        start, end_ch = obj, '}'
    end = text.rfind(end_ch)
    if end > start:
        return text[start:end + 1]
    return text


def _valid_expiry_dates(n: int = 6) -> list[str]:
    """Return the next n upcoming Friday dates that are at least 5 calendar days away.
    These are real tradeable weekly/monthly expiries."""
    today = datetime.now(timezone.utc).date()
    days_to_friday = (4 - today.weekday()) % 7  # weekday 4 = Friday
    # Ensure at least 5 calendar days gap so we're not expiring imminently
    if days_to_friday < 5:
        days_to_friday += 7
    fridays = []
    d = today + timedelta(days=days_to_friday)
    for _ in range(n):
        fridays.append(d.strftime("%Y-%m-%d"))
        d += timedelta(weeks=1)
    return fridays


class ClaudeAnalyst:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def _call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        msg = self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            temperature=0.3,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text

    def _parse(self, text: str) -> Any:
        return json.loads(_clean_json(text))

    # ------------------------------------------------------------------
    # Options analysis
    # ------------------------------------------------------------------
    def analyze_options(self, news_bullets: str, technical_data: str, market_context: str,
                        quant_scores: dict | None = None) -> list[dict]:
        system = (
            "You are a professional options trader and technical analyst with 20+ years of experience. "
            "You have deep expertise in single-leg options, iron condors, bull put spreads, bear call "
            "spreads, and debit spreads. You select the BEST strategy structure for each setup:\n"
            "  - single_leg CALL/PUT: strong directional momentum or BB squeeze breakout\n"
            "  - iron_condor: range-bound price with high IV (sell premium both sides)\n"
            "  - bull_put_spread: mildly bullish with high IV (credit spread)\n"
            "  - bear_call_spread: mildly bearish with high IV (credit spread)\n"
            "  - bull_call_spread: moderately bullish with lower IV (debit spread)\n"
            "  - bear_put_spread: moderately bearish with lower IV (debit spread)\n"
            "Respond ONLY with a valid JSON array — no prose, no markdown fences."
        )

        quant_ctx = ""
        if quant_scores:
            lines = []
            for ticker, qs in quant_scores.items():
                comp  = qs.get("composite", 50)
                ee    = qs.get("entry_exit", {})
                strat = qs.get("recommended_strategy", "single_leg")
                ml    = qs.get("multi_leg", {})
                if strat == "single_leg":
                    lines.append(
                        f"  {ticker}: quant={comp}/100 | strategy={strat} | "
                        f"underlying entry=${ee.get('underlying_entry','?')} "
                        f"target=${ee.get('underlying_target','?')} "
                        f"stop=${ee.get('underlying_stop','?')} | "
                        f"suggested strike=${ee.get('suggested_strike','?')} "
                        f"BS-premium-est entry=${ee.get('entry_premium_est','?')} "
                        f"target=${ee.get('target_premium_est','?')} "
                        f"stop=${ee.get('stop_premium_est','?')}"
                    )
                else:
                    sc = ml.get("short_call_strike","?")
                    lc = ml.get("long_call_strike","?")
                    sp = ml.get("short_put_strike","?")
                    lp = ml.get("long_put_strike","?")
                    lines.append(
                        f"  {ticker}: quant={comp}/100 | strategy={strat} | "
                        f"strikes SC={sc} LC={lc} SP={sp} LP={lp} | "
                        f"BS-credit-est=${ml.get('net_credit','?')} "
                        f"max_profit=${ml.get('max_profit','?')} "
                        f"max_loss=${ml.get('max_loss','?')}"
                    )
            quant_ctx = (
                "\nQuantitative analysis with Black-Scholes estimated premiums "
                "(use these as realistic anchors — adjust based on your judgment):\n"
                + "\n".join(lines) + "\n"
            )

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        valid_expiries = _valid_expiry_dates(6)
        expiry_list = ", ".join(valid_expiries)
        # Use nearest and second-nearest as concrete examples in the schema
        ex_expiry1 = valid_expiries[0]
        ex_expiry2 = valid_expiries[1] if len(valid_expiries) > 1 else valid_expiries[0]

        user = (
            f"Today's date (UTC): {today_str}\n"
            f"Valid option expiry dates — YOU MUST use one of these exact dates for every expiry field: "
            f"{expiry_list}\n"
            f"IMPORTANT: Never use a date not in the list above. Never use example dates from the schema.\n\n"
            f"{market_context}\n"
            f"{quant_ctx}\n"
            f"Recent news:\n{news_bullets}\n\n"
            f"Technical data (RSI, MACD, Bollinger, MAs, Fibonacci, ATR, VWAP, volume):\n"
            f"{technical_data}\n\n"
            "Instructions:\n"
            "- Select the strategy_type that best fits the technical setup (use the suggestions above "
            "as a starting point but override if the setup calls for it)\n"
            "- For single_leg: set option_type (CALL/PUT), strike, entry_price, exit_price, stop_loss, "
            "underlying_entry, underlying_target, underlying_stop\n"
            "- For multi-leg (iron_condor, spreads): set the appropriate strikes from "
            "short_call_strike, long_call_strike, short_put_strike, long_put_strike, "
            "net_credit (positive=credit received, negative=debit paid), max_profit, max_loss, "
            "breakeven_low, breakeven_high. Also set expiry.\n"
            "- Cite specific indicator readings in your explanation\n"
            "- Your qual_score is your qualitative judgment (0-100)\n\n"
            "Return a JSON array of exactly 5 objects. For single_leg:\n"
            f'  {{"rank":1,"ticker":"AAPL","strategy_type":"single_leg","option_type":"CALL",'
            f'"strike":195.0,"expiry":"{ex_expiry1}","entry_price":2.40,"exit_price":4.80,'
            '"stop_loss":1.20,"underlying_entry":192.5,"underlying_target":198.0,'
            '"underlying_stop":189.0,"qual_score":82,"score":87,"grade":"B",'
            '"explanation":"RSI 32 oversold, bouncing off Fib 61.8%..."}}\n\n'
            "For iron_condor:\n"
            f'  {{"rank":2,"ticker":"SPY","strategy_type":"iron_condor","option_type":"N/A",'
            f'"expiry":"{ex_expiry2}","short_call_strike":512.0,"long_call_strike":515.0,'
            '"short_put_strike":490.0,"long_put_strike":487.0,"net_credit":1.85,'
            '"max_profit":185.0,"max_loss":115.0,"breakeven_low":488.15,'
            '"breakeven_high":513.85,"qual_score":79,"score":83,"grade":"B",'
            '"explanation":"RSI neutral at 52, BB %B at 0.45 range-bound, IV rank 48..."}}\n\n'
            "For spreads (bull_put_spread example):\n"
            f'  {{"rank":3,"ticker":"MSFT","strategy_type":"bull_put_spread","option_type":"N/A",'
            f'"expiry":"{ex_expiry1}","short_put_strike":380.0,"long_put_strike":375.0,'
            '"net_credit":1.20,"max_profit":120.0,"max_loss":380.0,"breakeven_low":378.80,'
            '"qual_score":85,"score":88,"grade":"B",'
            '"explanation":"Strong uptrend above MA50+200, Fib 61.8% support at 381..."}}\n\n'
            "Scoring rubric for qual_score and score (0-100):\n"
            "- Technical setup quality (RSI, MACD, Fib, MA alignment): 35%\n"
            "- Catalyst/news strength: 25%\n"
            "- IV environment and premium value: 20%\n"
            "- Risk/reward of chosen structure: 20%\n"
            "Grade: A=90-100, B=80-89, C=70-79, D=60-69, F=below 60."
        )
        raw = self._call(system, user)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Wheel strategy analysis
    # ------------------------------------------------------------------
    def analyze_wheel(self, news_bullets: str, screening_data: str,
                      quant_scores: dict | None = None) -> list[dict]:
        system = (
            "You are a professional options income trader specialising in the Wheel Strategy. "
            "You use technical analysis to identify the safest put-selling opportunities: "
            "stocks in uptrends (above MA50 and MA200), with elevated IV rank for premium, "
            "and put strikes placed below strong Fibonacci or moving average support. "
            "Respond ONLY with a valid JSON array — no prose, no markdown fences."
        )
        quant_ctx = ""
        if quant_scores:
            lines = []
            for ticker, qs in quant_scores.items():
                comp = qs.get("composite", 50)
                ee = qs.get("entry_exit", {})
                lines.append(
                    f"  {ticker}: quant_score={comp}/100 | "
                    f"suggested_strike=${ee.get('suggested_put_strike','?')} "
                    f"pct_otm={ee.get('pct_otm','?')}%"
                )
            quant_ctx = "\nPre-computed quantitative scores:\n" + "\n".join(lines) + "\n"

        valid_expiries = _valid_expiry_dates(6)
        expiry_list = ", ".join(valid_expiries)
        ex_expiry1 = valid_expiries[0]

        user = (
            f"Current date/time (UTC): {datetime.now(timezone.utc).isoformat()}\n"
            f"Valid option expiry dates — YOU MUST use one of these exact dates for every expiry field: "
            f"{expiry_list}\n"
            f"IMPORTANT: Never use a date not in the list above.\n\n"
            f"{quant_ctx}\n"
            f"Recent market news:\n{news_bullets}\n\n"
            f"Technical screening data:\n{screening_data}\n\n"
            "Selection criteria — prioritise stocks where:\n"
            "1. Price is above MA50 AND MA200 (uptrend — safer to own if assigned)\n"
            "2. RSI is between 40-65 (not overbought, not in freefall)\n"
            "3. Put strike can be placed at or below a Fibonacci support level\n"
            "4. IV is elevated (better premium) but stock is fundamentally sound\n"
            "5. Volume trend is normal or high (liquid, active stock)\n"
            "6. Avoid stocks in death cross (MA50 < MA200) or with RSI below 30\n\n"
            "In your explanation, state: the trend, the support level where you'd place the put, "
            "and why IV makes it attractive right now.\n"
            "Your 'qual_score' is your qualitative judgment (0-100) incorporating stock quality, "
            "news context, and willingness-to-own assessment.\n\n"
            "For assignment_chance_pct: estimate the probability the put gets assigned "
            "(roughly delta × 100 — e.g. a 30-delta put = 30%). "
            "Set assignment_risk to 'LOW' if <25%, 'MODERATE' if 25-40%, 'HIGH' if >40%.\n\n"
            "Return a JSON array of exactly 5 objects:\n"
            "[\n"
            f'  {{"rank":1,"ticker":"MSFT","put_strike":380.0,"put_expiry":"{ex_expiry1}",'
            '"put_premium":4.20,"iv_rank":52,"assignment_chance_pct":28,"assignment_risk":"MODERATE",'
            '"qual_score":88,"score":91,"grade":"A",'
            '"explanation":"3-4 sentences citing trend, support level, and IV context"}}\n'
            "]\n\n"
            "Scoring rubric for qual_score and score (0-100):\n"
            "- Technical trend strength (MA, Fib support quality): 30%\n"
            "- IV rank / premium yield: 25%\n"
            "- Stock quality / willingness to own: 25%\n"
            "- Assignment risk (lower = better for conservative wheel): 10%\n"
            "- RSI and momentum safety: 10%\n"
            "Grade: A=90-100, B=80-89, C=70-79, D=60-69, F=below 60."
        )
        raw = self._call(system, user)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Long-term growth & income analysis
    # ------------------------------------------------------------------
    def analyze_longterm(self, news_bullets: str, fundamental_data: str,
                         quant_scores: dict | None = None) -> list[dict]:
        system = (
            "You are a fundamental equity analyst and portfolio manager with expertise in "
            "long-term investing (12+ month horizon). You combine fundamental analysis with "
            "long-term technical trend analysis: stocks must be in structural uptrends (above MA200), "
            "ideally with a golden cross (MA50 > MA200), and showing accumulation in volume trends. "
            "Respond ONLY with a valid JSON array — no prose, no markdown fences."
        )
        quant_ctx = ""
        if quant_scores:
            lines = []
            for ticker, qs in quant_scores.items():
                comp = qs.get("composite", 50)
                ee = qs.get("entry_exit", {})
                lines.append(
                    f"  {ticker}: quant_score={comp}/100 | "
                    f"buy_zone=${ee.get('buy_zone_low','?')}-${ee.get('buy_zone_high','?')} "
                    f"stop=${ee.get('invalidation_stop','?')}"
                )
            quant_ctx = "\nPre-computed quantitative scores:\n" + "\n".join(lines) + "\n"

        user = (
            f"Current date/time (UTC): {datetime.now(timezone.utc).isoformat()}\n"
            f"{quant_ctx}\n"
            f"Recent news and sentiment:\n{news_bullets}\n\n"
            f"Fundamental + technical data:\n{fundamental_data}\n\n"
            "Selection criteria:\n"
            "- Growth picks: strong revenue/EPS growth, above MA200, ideally golden cross, "
            "RSI not above 75 (avoid buying at peak)\n"
            "- Income picks: dividend yield >2%, above MA200 for capital preservation, "
            "low RSI volatility, stable volume trend\n"
            "- Avoid stocks in death cross or below MA200 (structural downtrend)\n"
            "- Note the 52-week range position to assess entry quality\n\n"
            "In your explanation, cite: the fundamental thesis, the technical trend status "
            "(MA50/200 relationship), and the key risk.\n"
            "Your 'qual_score' is your qualitative judgment (0-100) incorporating fundamental "
            "quality, competitive moat, and macro tailwinds beyond the math.\n"
            "Also provide buy_zone_low, buy_zone_high (ideal entry price range), and "
            "invalidation_stop (price below which the thesis is broken).\n\n"
            "Return a JSON array of exactly 5 objects:\n"
            "[\n"
            '  {"rank":1,"ticker":"NVDA","investment_type":"growth","target_price":1200.0,'
            '"time_horizon":"18-24 months","buy_zone_low":850.0,"buy_zone_high":920.0,'
            '"invalidation_stop":780.0,"qual_score":91,"score":94,"grade":"A",'
            '"explanation":"3-4 sentences on fundamentals, trend, catalyst, and risk"}\n'
            "]\n\n"
            "Scoring rubric for qual_score and score (0-100):\n"
            "Growth: earnings growth 30% + technical trend 25% + market position 25% + valuation 20%.\n"
            "Income: dividend yield+safety 35% + technical trend 25% + balance sheet 25% + sector 15%.\n"
            "Grade: A=90-100, B=80-89, C=70-79, D=60-69, F=below 60."
        )
        raw = self._call(system, user)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Covered call suggestion for assigned wheel position
    # ------------------------------------------------------------------
    def generate_call_suggestion(
        self,
        ticker: str,
        cost_basis: float,
        current_price: float,
        assigned_date: str,
        iv_rank: float | None,
        earnings_date: str | None,
        news_bullets: str,
        technicals: dict | None = None,
    ) -> dict:
        system = (
            "You are a professional options income trader. Generate an optimal weekly covered "
            "call recommendation using technical analysis to select the best strike. "
            "Respond ONLY with a valid JSON object — no prose, no markdown fences."
        )

        tech_str = ""
        if technicals:
            ma = technicals.get("moving_averages", {})
            fib = technicals.get("fibonacci", {})
            rsi = technicals.get("rsi", "?")
            bb = technicals.get("bollinger", {})
            tech_str = (
                f"\nTechnical context:\n"
                f"RSI={rsi} | MA50={ma.get('ma50','?')} MA200={ma.get('ma200','?')}\n"
                f"Bollinger upper={bb.get('upper','?')} middle={bb.get('middle','?')}\n"
                f"Fib resistance levels: 23.6%={fib.get('fib_236','?')} 38.2%={fib.get('fib_382','?')}\n"
                f"ATR={technicals.get('atr','?')} (daily expected move)"
            )

        valid_expiries = _valid_expiry_dates(4)
        expiry_list = ", ".join(valid_expiries)
        ex_expiry1 = valid_expiries[0]

        user = (
            f"Today's date (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            f"Valid expiry dates — use one of these exactly: {expiry_list}\n\n"
            f"I own 100 shares of {ticker} at cost basis ${cost_basis:.2f}/share "
            f"(assigned on {assigned_date}).\n"
            f"Current price: ${current_price:.2f}\n"
            f"IV rank: {iv_rank if iv_rank else 'unknown'}\n"
            f"Earnings date: {earnings_date if earnings_date else 'none known — avoid selling through earnings'}\n"
            f"{tech_str}\n\n"
            f"Recent news for {ticker}:\n{news_bullets}\n\n"
            "Select the call strike at a Fibonacci resistance level or near the Bollinger upper band "
            "where price is likely to stall. Do NOT go below cost basis. "
            "Use ATR to estimate realistic premium. Use the nearest date from the valid expiry list above.\n\n"
            "Return JSON:\n"
            f'{{"call_strike":195.0,"call_expiry":"{ex_expiry1}",'
            '"estimated_premium":1.85,"rationale":"cite the specific technical level used"}}'
        )
        raw = self._call(system, user, max_tokens=1024)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # On-demand single-stock analysis (Stock Lookup tab)
    # ------------------------------------------------------------------
    def analyze_stock(
        self,
        ticker: str,
        current_price: float,
        technicals: dict,
        fundamentals: dict,
        news_bullets: str,
    ) -> dict:
        system = (
            "You are a senior equity analyst combining technical analysis, fundamental research, "
            "and market sentiment to produce actionable stock ratings. "
            "Respond ONLY with a valid JSON object — no prose, no markdown fences."
        )

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        ma = technicals.get("moving_averages", {})
        fib = technicals.get("fibonacci", {})
        bb = technicals.get("bollinger", {})
        macd = technicals.get("macd", {})

        tech_str = (
            f"Price: ${current_price} | RSI={technicals.get('rsi','?')} | "
            f"ATR={technicals.get('atr','?')} | VWAP={technicals.get('vwap','?')}\n"
            f"MA20={ma.get('ma20','?')} MA50={ma.get('ma50','?')} MA200={ma.get('ma200','?')}\n"
            f"Bollinger: upper={bb.get('upper','?')} mid={bb.get('middle','?')} lower={bb.get('lower','?')} "
            f"%B={bb.get('pct_b','?')}\n"
            f"MACD={macd.get('macd','?')} signal={macd.get('signal','?')} "
            f"hist={macd.get('histogram','?')} [{macd.get('crossover','?')}]\n"
            f"Fib levels (from recent swing): "
            f"23.6%={fib.get('fib_236','?')} 38.2%={fib.get('fib_382','?')} "
            f"50%={fib.get('fib_500','?')} 61.8%={fib.get('fib_618','?')}\n"
            f"5d change: {technicals.get('change_5d_pct','?')}% | "
            f"Vol vs avg: {technicals.get('volume_trend', {}).get('ratio','?')}x"
        )

        fund_str = ""
        if fundamentals:
            fund_str = (
                f"\nFundamentals: PE={fundamentals.get('pe_ratio','?')} | "
                f"EPS growth={fundamentals.get('eps_growth_ttm','?')} | "
                f"Revenue growth={fundamentals.get('revenue_growth_ttm','?')} | "
                f"Div yield={fundamentals.get('div_yield','?')} | "
                f"Sector={fundamentals.get('sector','?')}"
            )

        user = (
            f"Today: {today_str}\n"
            f"Analyze {ticker} and produce a structured buy/sell/hold rating with price predictions.\n\n"
            f"Technical indicators:\n{tech_str}\n"
            f"{fund_str}\n\n"
            f"Recent news and sentiment:\n{news_bullets}\n\n"
            "Produce a comprehensive analysis covering:\n"
            "- Overall rating: BUY, SELL, or HOLD\n"
            "- Conviction: HIGH, MEDIUM, or LOW\n"
            "- Short-term outlook (1-4 weeks): direction, price target, key catalyst\n"
            "- Long-term outlook (3-12 months): direction, price target, thesis\n"
            "- Key support levels (2-3 price levels where buyers likely step in)\n"
            "- Key resistance levels (2-3 price levels where sellers likely emerge)\n"
            "- Main upside catalysts (2-3 bullet points)\n"
            "- Main risks (2-3 bullet points)\n"
            "- Technical summary: cite RSI, MACD status, MA alignment, Bollinger position\n"
            "- Score 0-100 for overall confidence\n\n"
            "Return JSON:\n"
            '{"ticker":"AAPL","rating":"BUY","conviction":"HIGH","score":84,"grade":"B",'
            '"current_price":192.50,'
            '"short_term":{"direction":"bullish","price_target":205.0,'
            '"timeframe":"2-3 weeks","catalyst":"RSI bounce from oversold, MACD crossover imminent"},'
            '"long_term":{"direction":"bullish","price_target":240.0,'
            '"timeframe":"6-9 months","thesis":"AI integration across product line drives margin expansion"},'
            '"support_levels":[188.0,182.5,175.0],'
            '"resistance_levels":[198.0,205.0,215.0],'
            '"upside_catalysts":["iPhone supercycle","Services revenue acceleration","India expansion"],'
            '"risks":["China demand slowdown","Valuation premium at risk if rates rise","Regulatory headwinds"],'
            '"technical_summary":"RSI at 38 approaching oversold; price below MA50 but above MA200 — '
            'dip within uptrend. MACD histogram turning less negative. BB %B at 0.15 near lower band.",'
            '"explanation":"2-3 sentence overall thesis combining technical and fundamental view"}'
        )
        raw = self._call(system, user, max_tokens=2048)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # On-demand Wheel Strategy custom analysis (user enters any ticker)
    # ------------------------------------------------------------------
    def analyze_wheel_custom(
        self,
        ticker: str,
        current_price: float,
        put_tiers: dict,
        fundamentals: dict,
        technicals: dict,
        news_bullets: str,
    ) -> dict:
        system = (
            "You are a friendly options income coach. Your job is to help everyday investors "
            "understand the Wheel Strategy in plain, simple English — no jargon, no confusing "
            "finance terms. Write as if explaining to a smart friend who has never traded options. "
            "Respond ONLY with a valid JSON object — no prose, no markdown fences."
        )

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ma = technicals.get("moving_averages", {})
        bb = technicals.get("bollinger", {})
        rsi = technicals.get("rsi", "?")
        atr = technicals.get("atr", "?")

        def _fmt_tier(t: dict | None, label: str) -> str:
            if not t:
                return f"  {label}: No suitable option found\n"
            return (
                f"  {label}:\n"
                f"    Strike=${t['strike']} | Expiry={t['expiry']} ({t['dte']} days)\n"
                f"    Bid=${t['bid']} / Ask=${t['ask']} | Mid=${t['mid_premium']} "
                f"(collect ${t['premium_per_contract']} per contract = 100 shares)\n"
                f"    IV={t['iv_pct']}% | Delta={t['delta_abs']} "
                f"(~{t['assignment_chance_pct']}% assignment chance)\n"
                f"    Daily time-decay income per contract=${t['daily_income_per_contract']}\n"
                f"    Breakeven=${t['breakeven']} (protected until stock drops {t['drop_to_breakeven_pct']}%)\n"
                f"    Annualized return on capital={t['annualized_return_pct']}%\n"
                f"    Volume={t['volume']} Open Interest={t['open_interest']}\n"
            )

        data_src = put_tiers.get("data_source", "last_trade")
        src_note = (
            "live bid/ask prices from open market"
            if data_src == "live"
            else "last-trade prices (markets closed — most recent actual transactions)"
        )
        tiers_str = (
            f"REAL OPTIONS DATA ({src_note}):\n"
            f"Current price: ${current_price} | ATM IV: {put_tiers.get('atm_iv_pct','?')}%\n\n"
            + _fmt_tier(put_tiers.get("likely"),   "TIER 1 — HIGH PREMIUM, HIGHER ASSIGNMENT RISK (~45% delta)")
            + _fmt_tier(put_tiers.get("moderate"), "TIER 2 — BALANCED PREMIUM AND RISK (~30% delta)")
            + _fmt_tier(put_tiers.get("unlikely"), "TIER 3 — CONSERVATIVE, LOWER PREMIUM (~16% delta)")
        )

        tech_str = (
            f"RSI={rsi} | MA50={ma.get('ma50','?')} MA200={ma.get('ma200','?')} "
            f"| Price {'above' if current_price > (ma.get('ma200') or 0) else 'below'} 200-day average\n"
            f"Bollinger %B={bb.get('pct_b','?')} | ATR={atr} (typical daily move)"
        )

        fund_str = (
            f"PE ratio={fundamentals.get('pe_ratio','?')} | "
            f"Revenue growth={fundamentals.get('revenue_growth_ttm','?')} | "
            f"Dividend yield={fundamentals.get('div_yield','?')} | "
            f"Sector={fundamentals.get('sector','?')}"
        ) if fundamentals else "Fundamental data unavailable"

        user = (
            f"Today: {today_str}\n"
            f"Analyze {ticker} (price=${current_price}) for the Wheel Strategy.\n\n"
            f"Technical picture:\n{tech_str}\n\n"
            f"Fundamentals: {fund_str}\n\n"
            f"Recent news:\n{news_bullets}\n\n"
            f"{tiers_str}\n"
            "Write everything in plain English. Avoid words like 'delta', 'theta', 'IV', 'volatility'. "
            "Instead use phrases like:\n"
            "- 'assignment chance' → 'chance you end up buying the shares'\n"
            "- 'IV is high' → 'options are pricier than usual right now — great time to sell'\n"
            "- 'theta decay' → 'earns money just from time passing'\n"
            "- 'breakeven' → 'you only lose money if the stock drops below $X'\n\n"
            "Return JSON with these exact fields:\n"
            '{"ticker":"AAPL","current_price":192.50,'
            '"wheel_rating":"GOOD",'
            '"wheel_score":82,'
            '"grade":"B",'
            '"company_assessment":"2-3 sentences: Is this a good company to own if assigned? '
            'Mention stability, business quality, and whether you are comfortable owning shares.",'
            '"technicals_plain":"1-2 sentences in plain English about the chart setup. '
            'No indicator names — just what it means (e.g. The stock is in a healthy uptrend)",'
            '"iv_environment_plain":"1 sentence: are options cheap, fair, or expensive right now? '
            'What does that mean for the seller? (e.g. Options are pricier than usual — '
            'great time to collect premium)",'
            '"tiers":['
            '{"tier_name":"Higher premium, more likely to buy shares",'
            '"strike":190.0,"expiry":"2026-05-01","dte":9,'
            '"premium_plain":"You collect $420 upfront for agreeing to buy 100 shares",'
            '"assignment_plain":"Roughly a 45-in-100 chance you end up buying the shares at $190",'
            '"time_decay_plain":"Earns about $18 per day automatically just from time passing",'
            '"protection_plain":"You only start losing money if the stock drops below $186",'
            '"return_plain":"If this keeps expiring worthless, it is like earning 28% per year on your cash",'
            '"best_for":"Investors who actually want to own the shares and want maximum premium"},'
            '{"tier_name":"Balanced — decent premium with a reasonable safety cushion",...},'
            '{"tier_name":"Conservative — smaller premium but much safer",...}'
            '],'
            '"overall_verdict":"2-3 sentences recommending which tier makes most sense right now and why."}'
        )
        raw = self._call(system, user, max_tokens=3000)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Watchlist multi-strategy scoring
    # ------------------------------------------------------------------
    def score_watchlist_ticker(self, ticker: str, info: dict) -> dict:
        from datetime import datetime, timezone, timedelta

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Earnings proximity check
        earnings_date = info.get("earnings_date")
        earnings_warning = None
        if earnings_date:
            try:
                ed = datetime.strptime(str(earnings_date)[:10], "%Y-%m-%d").date()
                days_away = (ed - datetime.now(timezone.utc).date()).days
                if 0 <= days_away <= 14:
                    earnings_warning = (
                        f"⚠ Earnings in {days_away} days ({earnings_date}). "
                        "High risk for wheel or options — avoid opening new positions."
                    )
                elif days_away < 0:
                    earnings_date = None  # past earnings, not relevant
            except Exception:
                pass

        price = info.get("price") or info.get("current_price", "?")
        sector = info.get("sector", "?")
        pe = info.get("pe_ratio", "?")
        div = info.get("div_yield", "?")
        iv_rank = info.get("iv_rank", "?")
        rsi = info.get("rsi", "?")
        ma50 = info.get("ma50", "?")
        ma200 = info.get("ma200", "?")

        system = (
            "You are a senior portfolio manager at Goldman Sachs. "
            "Evaluate a stock for three strategies and return ONLY valid JSON."
        )
        user = (
            f"Today: {today_str}\n"
            f"Stock: {ticker} | Price: ${price} | Sector: {sector}\n"
            f"PE: {pe} | Dividend Yield: {div} | IV Rank: {iv_rank}\n"
            f"RSI: {rsi} | MA50: {ma50} | MA200: {ma200}\n"
            f"Earnings date: {earnings_date or 'unknown'}\n\n"
            "Score this stock for three strategies on a 0-100 scale with a letter grade (A/B/C/D/F):\n"
            "1. WHEEL STRATEGY: Is it a good stock to sell cash-secured puts on?\n"
            "   Score rubric: IV rank 25% + stock quality/stability 30% + premium yield 25% + technical support 20%\n"
            "2. OPTIONS TRADING: Is there a compelling short-term options trade (call or put)?\n"
            "   Score rubric: catalyst strength 30% + technical momentum 30% + IV environment 20% + risk/reward 20%\n"
            "3. LONG-TERM INVESTING: Is it worth buying and holding for 1-3 years?\n"
            "   Score rubric: earnings growth 35% + market position 25% + valuation 20% + dividend/income 20%\n\n"
            "Return JSON only:\n"
            '{"wheel_score":75,"wheel_grade":"B","wheel_note":"1 sentence why",'
            '"options_score":60,"options_grade":"C","options_note":"1 sentence why",'
            '"longterm_score":82,"longterm_grade":"B","longterm_note":"1 sentence why",'
            '"best_strategy":"wheel",'
            '"summary":"2-3 sentence plain-English verdict on this stock right now."}'
        )
        raw = self._call(system, user, max_tokens=600)
        result = self._parse(raw)
        result["earnings_date"] = str(earnings_date) if earnings_date else None
        result["earnings_warning"] = earnings_warning
        return result

    # ------------------------------------------------------------------
    # Roll suggestion for put_active wheel positions
    # ------------------------------------------------------------------
    def suggest_roll(
        self,
        ticker: str,
        current_price: float,
        put_strike: float,
        put_expiry: str,
        premium_received: float | None,
        put_tiers: dict,
    ) -> dict:
        pct_from_strike = round((current_price - put_strike) / put_strike * 100, 1)
        premium_str = f"${premium_received:.2f}/share (${premium_received*100:.0f}/contract)" if premium_received else "unknown"

        def _fmt_tier(t: dict | None, label: str) -> str:
            if not t:
                return f"  {label}: not available\n"
            net = round(t["mid_premium"] - (premium_received or 0), 2) if premium_received else None
            net_str = f" | net credit vs current: ${net:.2f}" if net and net > 0 else (f" | net debit: ${abs(net):.2f}" if net else "")
            return (
                f"  {label}: Strike=${t['strike']} Expiry={t['expiry']} ({t['dte']} DTE)\n"
                f"    Premium mid=${t['mid_premium']} (collect ${t['premium_per_contract']}/contract){net_str}\n"
                f"    Assignment chance ~{t['assignment_chance_pct']}% | Breakeven=${t['breakeven']}\n"
            )

        tiers_str = (
            f"Available puts to roll into (current price ${current_price}):\n"
            + _fmt_tier(put_tiers.get("likely"),   "Higher premium (~45% assignment chance)")
            + _fmt_tier(put_tiers.get("moderate"), "Balanced (~30% assignment chance)")
            + _fmt_tier(put_tiers.get("unlikely"), "Conservative (~16% assignment chance)")
        )

        system = (
            "You are a friendly options income coach helping an everyday investor manage a Wheel Strategy position. "
            "Explain everything in plain English — no jargon. "
            "Respond ONLY with a valid JSON object — no prose, no markdown."
        )
        user = (
            f"My open position: I sold a ${put_strike} put on {ticker} expiring {put_expiry}. "
            f"I collected {premium_str} in premium.\n"
            f"Today {ticker} is trading at ${current_price} — that's {pct_from_strike}% above my strike.\n\n"
            f"{tiers_str}\n"
            "Should I roll this put? If yes, tell me exactly what to do in plain English.\n"
            "A roll means: buy back my current put (to close it), then sell a new put at a lower strike "
            "and/or later expiry to collect more premium and give myself more breathing room.\n\n"
            "Return JSON with these fields:\n"
            '{"should_roll": true,'
            '"urgency": "low|medium|high",'
            '"action_plain": "One clear sentence: exactly what to do (e.g. Roll your $190 put down to $185, '
            'push the expiry to May 16)",'
            '"new_strike": 185.0,'
            '"new_expiry": "2026-05-16",'
            '"estimated_net": 0.45,'
            '"net_description": "Plain English: e.g. You collect an extra $45 per contract by rolling",'
            '"rationale": "2-3 sentences in plain English explaining why this roll makes sense right now — '
            'what risk it reduces and what it costs you.",'
            '"if_no_action": "1 sentence: what happens if you do nothing"}'
        )
        raw = self._call(system, user, max_tokens=600)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Covered calls — weekly income from 100 shares already owned
    # ------------------------------------------------------------------
    def suggest_covered_calls(
        self,
        ticker: str,
        current_price: float,
        call_tiers: dict,
        cost_basis: float | None = None,
    ) -> dict:
        system = (
            "You are a friendly options income coach helping an everyday investor generate "
            "weekly income from 100 shares they already own. Explain everything in plain, "
            "simple English — no jargon, no confusing finance terms. "
            "Respond ONLY with a valid JSON object — no prose, no markdown fences."
        )

        def _fmt_tier(t: dict | None, label: str) -> str:
            if not t:
                return f"  {label}: No suitable option found\n"
            below = " [THIN MARKET — premium below 0.3%/week]" if t.get("below_threshold") else ""
            profit_str = ""
            if cost_basis and t["strike"] > cost_basis:
                total = round((t["strike"] - cost_basis + t["mid_premium"]) * 100, 2)
                profit_str = f" | Total profit if called away: ${total}/contract"
            return (
                f"  {label}:{below}\n"
                f"    Strike=${t['strike']} | Expiry={t['expiry']} ({t['dte']} days)\n"
                f"    Bid=${t['bid']} / Ask=${t['ask']} | Mid=${t['mid_premium']} "
                f"(collect ${t['premium_per_contract']} for 100 shares){profit_str}\n"
                f"    Call-away chance ~{t['call_away_chance_pct']}% | "
                f"Premium = {t['pct_of_stock_weekly']}% of stock price this week\n"
                f"    Stock must stay below ${t['strike']} for you to keep shares "
                f"({t['upside_to_strike_pct']}% upside room)\n"
                f"    Volume={t['volume']} | Open Interest={t['open_interest']}\n"
            )

        data_src = call_tiers.get("data_source", "last_trade")
        src_note = "live bid/ask" if data_src == "live" else "last-trade prices (markets closed)"
        cost_str = (
            f"${cost_basis:.2f}/share (${cost_basis * 100:.0f} total cost basis for 100 shares)"
            if cost_basis else "not provided"
        )
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        tiers_str = (
            f"WEEKLY CALL OPTIONS ({src_note}):\n"
            f"Current price: ${current_price} | ATM IV: {call_tiers.get('atm_iv_pct', '?')}%\n"
            f"Cost basis: {cost_str}\n\n"
            + _fmt_tier(call_tiers.get("aggressive"),   "TIER 1 — AGGRESSIVE (~70% call-away chance, highest premium)")
            + _fmt_tier(call_tiers.get("balanced"),     "TIER 2 — BALANCED (~45% call-away chance, good premium)")
            + _fmt_tier(call_tiers.get("conservative"), "TIER 3 — CONSERVATIVE (~20% call-away chance, lower premium)")
        )

        user = (
            f"Today: {today_str}\n"
            f"I own 100 shares of {ticker} at ${current_price} and want to sell a weekly covered "
            f"call to generate income. Give me plain-English explanations of my three options.\n\n"
            f"{tiers_str}\n"
            "For each tier explain in simple terms:\n"
            "- Exactly how much I collect upfront (dollars for 100 shares)\n"
            "- How likely my shares get called away, and what that means\n"
            "- What happens if the stock rallies past my strike\n"
            "- Who this option is best for\n\n"
            'Return JSON with exactly this structure:\n'
            '{"iv_environment": "1 sentence: are premiums rich or thin this week and what that means for me",'
            '"tiers": ['
            '{"tier": "aggressive",'
            '"strike": 95.0,'
            '"expiry": "2026-05-09",'
            '"dte": 7,'
            '"premium_per_contract": 180.0,'
            '"call_away_chance_pct": 70,'
            '"premium_plain": "You collect $180 upfront for agreeing to sell your 100 shares at $95",'
            '"callaway_plain": "About a 70-in-100 chance your shares get called away at $95 by Friday",'
            '"if_called_plain": "If called away: you sell at $95 and keep the $180 premium",'
            '"if_not_called_plain": "If the stock stays below $95: you keep your shares and the $180 is yours",'
            '"best_for": "Investors who want maximum income now and are OK selling at $95",'
            '"thin_market_note": null},'
            '{"tier": "balanced", ...},'
            '{"tier": "conservative", ...}]}'
        )
        raw = self._call(system, user, max_tokens=2500)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Champions — one batched call to pick best stock per strategy
    # ------------------------------------------------------------------
    def pick_champions(self, survivors: list[dict]) -> dict:
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        lines = []
        for s in survivors:
            pe_str = f"PE={s['pe']:.0f}" if s.get("pe") else "PE=n/a"
            div_str = f"div={s['div_yield_pct']}%" if s.get("div_yield_pct") else "div=none"
            iv_str = f"IV_rank≈{s['iv_rank']}" if s.get("iv_rank") else "IV_rank=unknown"
            lines.append(
                f"{s['ticker']}: ${s['price']} | RSI={s['rsi']} | {iv_str} | "
                f"vol={s['avg_vol_m']}M/day | {pe_str} | {div_str} | "
                f"sector={s.get('sector','?')} | analyst={s.get('analyst','?')}"
            )

        stocks_block = "\n".join(lines)

        system = (
            "You are a senior Goldman Sachs portfolio manager. "
            "Pick the single best stock for each of three strategies. "
            "Return ONLY valid JSON — no prose, no markdown."
        )
        user = (
            f"Today: {today_str}\n"
            f"These {len(survivors)} stocks passed a quantitative pre-screen "
            "(price >$5, volume >500k/day, RSI 25-75, no earnings within 14 days).\n\n"
            f"{stocks_block}\n\n"
            "Pick the single BEST stock for each strategy:\n"
            "1. WHEEL STRATEGY — best for selling cash-secured puts right now\n"
            "   (favor: high IV rank, stable/quality company, strong price support, good premium yield)\n"
            "2. OPTIONS TRADING — best for a directional call or put play right now\n"
            "   (favor: clear momentum, strong catalyst, favorable risk/reward)\n"
            "3. LONG-TERM INVESTING — best buy and hold for the next 1-3 years\n"
            "   (favor: earnings growth, dominant market position, reasonable valuation)\n\n"
            "Return JSON only — no extra keys:\n"
            '{"wheel":{"ticker":"AAPL","score":88,"grade":"A",'
            '"reason":"2 sentences plain English — why this is the best wheel stock right now."},'
            '"options":{"ticker":"NVDA","score":82,"grade":"B",'
            '"reason":"2 sentences plain English — why this is the best options play right now."},'
            '"longterm":{"ticker":"MSFT","score":91,"grade":"A",'
            '"reason":"2 sentences plain English — why this is the best long-term hold right now."}}'
        )
        raw = self._call(system, user, max_tokens=500)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Day Trade Scanner — rank top movers into high-confidence plays
    # ------------------------------------------------------------------
    def scan_day_trades(self, candidates: list[dict], spy_change: float | None = None) -> list[dict]:
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        spy_ctx = f"SPY is {'+' if (spy_change or 0) >= 0 else ''}{spy_change}% today." if spy_change is not None else ""

        # Near-term expiry dates for options suggestions
        near_expiries = _valid_expiry_dates(3)
        expiry_list = ", ".join(near_expiries)

        lines = []
        for c in candidates:
            news_str = " | ".join(c.get("news", [])[:2]) or "No recent news"
            arrow = "▲" if c["change_pct"] >= 0 else "▼"

            ta_parts = []
            if c.get("rsi") is not None:
                rsi_label = "overbought" if c["rsi"] > 70 else ("oversold" if c["rsi"] < 30 else "neutral")
                ta_parts.append(f"RSI={c['rsi']}({rsi_label})")
            if c.get("atr") is not None:
                ta_parts.append(f"ATR={c['atr']}")
            if c.get("ma20") is not None:
                rel = "above" if c["price"] > c["ma20"] else "below"
                ta_parts.append(f"20MA={c['ma20']}({rel})")
            if c.get("vs_spy") is not None:
                ta_parts.append(f"vsS&P={'+' if c['vs_spy'] >= 0 else ''}{c['vs_spy']}%")
            if c.get("days_to_cover") is not None:
                ta_parts.append(f"DTC={c['days_to_cover']}d")
            if c.get("short_volume_ratio_pct") is not None:
                ta_parts.append(f"ShortVol={c['short_volume_ratio_pct']}%")

            ta_str = " | " + ", ".join(ta_parts) if ta_parts else ""
            lines.append(
                f"{c['ticker']}: ${c['price']} ({arrow}{abs(c['change_pct'])}% today) | "
                f"Vol: {c['volume_m']}M ({c['vol_ratio']}x avg) | "
                f"O:{c['open']} H:{c['high']} L:{c['low']} VWAP:{c['vwap']}"
                f"{ta_str} | News: {news_str}"
            )

        stocks_block = "\n".join(lines)

        system = (
            "You are an elite day trader and options analyst at a prop trading firm. "
            "Analyze the provided movers and identify the best trade setups. "
            "You MUST always return between 3 and 5 plays — never return an empty list. "
            "For each play, suggest a specific options entry: strike, expiry, estimated entry premium, "
            "target premium, and stock break-even. Use ATM or slightly OTM strikes for momentum plays. "
            "Use RSI to avoid chasing overbought entries; use ATR for stop sizing. "
            "Be specific with entry zones, targets, and stops. "
            "Return ONLY valid JSON — no prose, no markdown."
        )
        user = (
            f"Today: {today_str}. {spy_ctx}\n"
            f"Near-term option expiries available: {expiry_list}\n\n"
            f"Top movers (yfinance daily data, RSI-14 + ATR-14 enriched):\n\n"
            f"{stocks_block}\n\n"
            "Select the 3–5 best setups. Prioritize:\n"
            "1. Momentum continuation: vol_ratio ≥ 2x + clear direction + catalyst\n"
            "2. VWAP reclaim/hold: price above VWAP with volume\n"
            "3. Oversold bounce: RSI < 35 + down on volume — reversal near low\n"
            "4. Breakout: stock breaking prior high with vol surge\n"
            "5. Short squeeze: high DTC + stock ripping — shorts trapped\n\n"
            "Use ATR for stop sizing (1–1.5× ATR below entry for longs). "
            "RSI > 75 = avoid chasing, prefer pullback entry.\n\n"
            "For option_play: use CALL for long, PUT for short. "
            "Pick the nearest ATM or 1-strike OTM. "
            "For intraday, use the nearest expiry. For swing (2-3d), use the second expiry. "
            "entry_premium = your estimated mid price. target_premium = estimated value if stock hits target. "
            "stop_premium = 50% of entry (e.g. entry $2.00 → stop $1.00). "
            "breakeven_stock = strike + entry_premium for calls, strike - entry_premium for puts.\n\n"
            "Return JSON only:\n"
            '{"plays": ['
            '{"ticker": "NVDA",'
            '"direction": "long",'
            '"setup": "Momentum breakout",'
            '"confidence": "high",'
            '"entry_zone": "$88.50–$89.00",'
            '"target": "$93.00",'
            '"stop_loss": "$86.50",'
            '"timeframe": "intraday",'
            '"risk_reward": "2.5:1",'
            '"catalyst": "One sentence: what is driving this move",'
            '"reasoning": "2-3 sentences: why this setup and what to watch",'
            '"option_play": {'
            '"option_type": "CALL",'
            '"strike": 89.0,'
            f'"expiry": "{near_expiries[0]}",'
            '"entry_premium": 1.50,'
            '"target_premium": 3.20,'
            '"stop_premium": 0.75,'
            '"breakeven_stock": 90.50'
            '}}'
            "]}'"
        )
        raw = self._call(system, user, max_tokens=2500)
        result = self._parse(raw)
        return result.get("plays", [])

    def interpret_options_flow(
        self, alerts: list[dict], sentiment_ratio: int, overall: str
    ) -> list[dict]:
        """Interpret unusual options flow and add narrative context to each alert."""
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        lines = []
        for a in alerts:
            notional_k = round(a.get("notional", 0) / 1_000)
            pct_otm = a.get("pct_otm", 0)
            itm_otm = f"{abs(pct_otm)}% {'OTM' if pct_otm >= 0 else 'ITM'}"
            opt_type = (a.get("option_type") or "call").upper()
            vol_oi = a.get("vol_oi_ratio", 0)
            oi = a.get("open_interest", 0)
            ratio_str = "NEW (no prior OI)" if a.get("is_new_contract") else f"{vol_oi}x"
            earnings = a.get("earnings_context")
            earnings_str = f" | {earnings}" if earnings else ""
            change_pct = a.get("change_pct")
            move_str = f" | Today {'+' if (change_pct or 0) >= 0 else ''}{change_pct}%" if change_pct is not None else ""
            news_items = a.get("news") or []
            news_str = f" | News: {' // '.join(news_items[:2])}" if news_items else ""
            # Premium richness context
            prem_parts = []
            if a.get("breakeven"):
                prem_parts.append(f"BE=${a['breakeven']}")
            if a.get("pct_move_needed") is not None:
                prem_parts.append(f"needs {a['pct_move_needed']}% move")
            if a.get("iv_pct"):
                prem_parts.append(f"IV={a['iv_pct']}%")
            if a.get("hv_pct"):
                prem_parts.append(f"HV={a['hv_pct']}%")
            if a.get("premium_rating"):
                prem_parts.append(f"premium={a['premium_rating']}")
            richness_str = f" | {', '.join(prem_parts)}" if prem_parts else ""
            lines.append(
                f"{a.get('ticker','?')} ${a.get('strike','?')} {opt_type} "
                f"exp {a.get('expiry','?')} ({a.get('dte','?')}d) | "
                f"Vol:{a.get('volume',0):,} OI:{oi:,} Ratio:{ratio_str} | "
                f"${notional_k}K notional | {itm_otm} | Stock=${a.get('price','?')}"
                f"{richness_str}{earnings_str}{move_str}{news_str}"
            )
        flow_block = "\n".join(lines)

        system = (
            "You are an expert options flow analyst at a prop trading desk. "
            "Interpret unusual options activity — high vol/OI ratios mean fresh positioning. "
            "'NEW (no prior OI)' means a brand-new contract with zero prior open interest — very significant. "
            "Large OTM prints are directional bets. Near-ATM prints could be hedges or income plays. "
            "CRITICAL: If earnings context is provided (e.g. 'Earnings 2d ago'), factor that in — "
            "post-earnings flow is repositioning, NOT an earnings play. Pre-earnings flow is often a straddle or directional bet. "
            "When premium=RICH (IV >> HV), the option buyer is paying a large premium — they need a big move to profit. "
            "When premium=CHEAP, IV is below historical volatility — relatively inexpensive. "
            "Use break-even and % move needed to assess whether the flow is realistic or a long shot. "
            "Be direct and concise. A day trader needs actionable takeaways, not theory. "
            "Return ONLY valid JSON — no prose, no markdown."
        )
        user = (
            f"Today: {today_str}\n"
            f"Flow summary: {sentiment_ratio}% call volume vs puts = overall {overall} bias\n\n"
            f"Unusual contracts (sorted by notional premium, biggest bets first):\n\n"
            f"{flow_block}\n\n"
            "For EACH alert, return all original fields plus these new fields:\n"
            "- interpretation: what this flow likely means given any earnings context\n"
            "- implied_target: specific price target implied by the bet (e.g. '$115+ by May 15')\n"
            "- confidence: high / medium / low\n"
            "- action_note: one sentence for a day trader watching this stock\n"
            "- recommendation: 'BUY' or 'AVOID' plus one specific condition\n"
            "- verdict: exactly one of 'PROCEED' | 'CAUTION' | 'AVOID'\n"
            "  PROCEED = strong signal, good risk/reward, worth following\n"
            "  CAUTION = interesting flow but meaningful red flags (0-1 DTE, earnings imminent,\n"
            "            RICH premium, large move needed, possible hedge)\n"
            "  AVOID = too risky (0-DTE into earnings, IV crushed after earnings, very large move\n"
            "          needed, low notional that smells like retail noise)\n"
            "- verdict_reason: one short phrase (≤8 words) explaining the verdict\n"
            "  Examples: 'High Vol/OI with price confirmation'\n"
            "            'Earnings in 2d — IV crush risk'\n"
            "            '0-DTE needs 3% move — long shot'\n"
            "            'Possible hedge, not directional'\n\n"
            "Return JSON only:\n"
            '{"alerts": [{'
            '"ticker": "NVDA", "option_type": "call", "strike": 900.0, '
            '"expiry": "2026-05-10", "dte": 5, "volume": 15420, "open_interest": 1200, '
            '"vol_oi_ratio": 12.8, "is_new_contract": false, "mid_premium": 2.50, '
            '"notional": 3855000, "pct_otm": 2.9, "price": 875.0, "sentiment": "bullish", '
            '"earnings_context": null, "breakeven": 902.50, "pct_move_needed": 3.1, '
            '"iv_pct": 55.0, "hv_pct": 42.0, "iv_hv_ratio": 1.31, "premium_rating": "FAIR", '
            '"interpretation": "Aggressive sweep — fresh bullish positioning ahead of a catalyst", '
            '"implied_target": "$900+ by May 10", '
            '"confidence": "high", '
            '"action_note": "Watch for break above $880 with volume — flow confirms upside bias", '
            '"recommendation": "BUY if stock breaks $880 with volume confirmation. AVOID if market opens flat.", '
            '"verdict": "PROCEED", '
            '"verdict_reason": "High Vol/OI with price confirmation"'
            "}]}"
        )
        raw = self._call(system, user, max_tokens=3500)
        try:
            result = self._parse(raw)
            interpreted = result.get("alerts", [])
            if interpreted:
                return interpreted
            logger.warning("interpret_options_flow: Claude returned empty alerts list")
        except Exception as e:
            logger.warning("interpret_options_flow: parse failed (%s), returning raw alerts", e)
        return alerts
