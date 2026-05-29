"""
Thin wrapper around the Finnhub REST API.
Used for reliable stock data (prices, candles, fundamentals, earnings).
Replaces yfinance bulk downloads which get rate-limited on cloud server IPs.
"""
import logging
import time
from datetime import datetime, timezone, timedelta

import finnhub

from config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> finnhub.Client:
    global _client
    if _client is None:
        key = settings.finnhub_api_key or ""
        if not key:
            raise RuntimeError("FINNHUB_API_KEY is not set")
        _client = finnhub.Client(api_key=key)
    return _client


def get_quote(symbol: str) -> dict:
    """Current price, open, high, low, prev close, change %."""
    try:
        return _get_client().quote(symbol) or {}
    except Exception as e:
        logger.warning("Finnhub quote failed for %s: %s", symbol, e)
        return {}


def get_candles(symbol: str, days: int = 90) -> dict:
    """
    Daily OHLCV candles going back `days` calendar days.
    Returns dict with keys: c (close), h, l, o, v (volume), t (timestamps), s (status).
    """
    to_ts = int(time.time())
    from_ts = to_ts - days * 24 * 3600
    try:
        data = _get_client().stock_candles(symbol, "D", from_ts, to_ts)
        return data or {}
    except Exception as e:
        logger.warning("Finnhub candles failed for %s: %s", symbol, e)
        return {}


def get_basic_financials(symbol: str) -> dict:
    """PE ratio, dividend yield, 52-week high/low, beta, etc."""
    try:
        data = _get_client().company_basic_financials(symbol, "all")
        return data.get("metric", {}) or {}
    except Exception as e:
        logger.warning("Finnhub financials failed for %s: %s", symbol, e)
        return {}


def get_company_profile(symbol: str) -> dict:
    """Sector, industry, name, market cap."""
    try:
        return _get_client().company_profile2(symbol=symbol) or {}
    except Exception as e:
        logger.warning("Finnhub profile failed for %s: %s", symbol, e)
        return {}


def get_insider_sentiment(symbol: str, days: int = 90) -> dict:
    """
    Net insider buying/selling over the last `days` days (direct transactions only).
    Returns signal ('buy'|'sell'|'neutral'), net_change, insiders_buying/selling count.
    Filters out derivative (options) transactions to focus on real share purchases.
    """
    try:
        from datetime import date, timedelta
        today = date.today()
        from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
        data = _get_client().stock_insider_transactions(symbol, from_date, to_date)
        txns = (data or {}).get("data", []) or []
        direct = [t for t in txns if not t.get("isDerivative", False)]
        if not direct:
            return {}
        buyers: dict[str, int] = {}
        sellers: dict[str, int] = {}
        for t in direct:
            change = int(t.get("change") or 0)
            name = t.get("name") or "Unknown"
            if change > 0:
                buyers[name] = buyers.get(name, 0) + change
            elif change < 0:
                sellers[name] = sellers.get(name, 0) + abs(change)
        net_change = sum(buyers.values()) - sum(sellers.values())
        if len(buyers) >= 2 and net_change > 0:
            signal = "buy"
        elif len(sellers) >= 2 and net_change < 0:
            signal = "sell"
        else:
            signal = "neutral"
        return {
            "signal": signal,
            "net_change": net_change,
            "insiders_buying": len(buyers),
            "insiders_selling": len(sellers),
        }
    except Exception as e:
        logger.debug("insider_sentiment failed for %s: %s", symbol, e)
        return {}


def get_earnings_this_month(symbol: str) -> int | None:
    """
    Returns days until next earnings announcement, or None if unknown.
    Only checks the next 30 days.
    """
    try:
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=30)
        cal = _get_client().earnings_calendar(
            _from=today.strftime("%Y-%m-%d"),
            to=end.strftime("%Y-%m-%d"),
            symbol=symbol,
        )
        earnings = cal.get("earningsCalendar", [])
        if not earnings:
            return None
        dates = []
        for e in earnings:
            try:
                d = datetime.strptime(e["date"], "%Y-%m-%d").date()
                days_away = (d - today).days
                if days_away >= 0:
                    dates.append(days_away)
            except Exception:
                pass
        return min(dates) if dates else None
    except Exception as e:
        logger.debug("Finnhub earnings failed for %s: %s", symbol, e)
        return None
