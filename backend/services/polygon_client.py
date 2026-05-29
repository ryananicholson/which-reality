import logging

logger = logging.getLogger(__name__)


def _client():
    from config import settings
    from massive.rest import RESTClient
    if not settings.polygon_api_key:
        raise RuntimeError("POLYGON_API_KEY is not configured")
    return RESTClient(settings.polygon_api_key, read_timeout=30.0, connect_timeout=10.0, pagination=False, base="https://api.polygon.io")


def get_market_status() -> dict:
    """Current trading status of US equity markets."""
    c = _client()
    s = c.get_market_status()
    is_open = (s.market or "").lower() == "open"
    after_hours = s.after_hours or False
    early_hours = s.early_hours or False
    if is_open:
        label = "open"
    elif after_hours:
        label = "after_hours"
    elif early_hours:
        label = "pre_market"
    else:
        label = "closed"
    return {
        "label": label,
        "is_open": is_open,
        "after_hours": after_hours,
        "early_hours": early_hours,
        "server_time": s.server_time,
    }


def get_movers(direction: str = "gainers", limit: int = 25) -> list[dict]:
    """Top gainers or losers by % change today, returned as plain dicts."""
    c = _client()
    snapshots = c.get_snapshot_direction("stocks", direction)
    result = []
    for s in (snapshots or []):
        if len(result) >= limit:
            break
        day = s.day
        prev = s.prev_day
        result.append({
            "ticker": s.ticker,
            "todaysChangePerc": s.todays_change_percent or 0,
            "day": {
                "c": day.close if day else None,
                "h": day.high if day else None,
                "l": day.low if day else None,
                "o": day.open if day else None,
                "v": day.volume if day else None,
                "vw": day.vwap if day else None,
            },
            "prevDay": {
                "c": prev.close if prev else None,
                "v": prev.volume if prev else None,
            },
        })
    return result


def get_short_data(ticker: str) -> dict:
    """Most recent short interest and short volume ratio for a ticker."""
    c = _client()
    result = {}

    try:
        items = list(c.list_short_interest(ticker=ticker, limit=1, order="desc"))
        if items:
            si = items[0]
            result["short_interest"] = si.short_interest
            result["days_to_cover"] = round(float(si.days_to_cover), 1) if si.days_to_cover else None
            result["settlement_date"] = si.settlement_date
    except Exception as e:
        logger.debug("short_interest failed for %s: %s", ticker, e)

    try:
        vols = list(c.list_short_volume(ticker=ticker, limit=1, order="desc"))
        if vols:
            sv = vols[0]
            if sv.short_volume_ratio is not None:
                result["short_volume_ratio_pct"] = round(float(sv.short_volume_ratio) * 100, 1)
    except Exception as e:
        logger.debug("short_volume failed for %s: %s", ticker, e)

    return result


def get_aggregates(
    ticker: str,
    from_date: str,
    to_date: str,
    timespan: str = "day",
    multiplier: int = 1,
) -> list[dict]:
    """OHLCV bars, returned as plain dicts."""
    c = _client()
    aggs = c.get_aggs(ticker, multiplier, timespan, from_date, to_date,
                      adjusted=True, sort="asc", limit=50)
    return [
        {"o": a.open, "h": a.high, "l": a.low, "c": a.close,
         "v": a.volume, "vw": a.vwap, "t": a.timestamp}
        for a in (aggs or [])
    ]


def get_options_chain_snapshot(
    ticker: str,
    dte_max: int = 45,
    contract_type: str | None = None,
    near_price: float | None = None,
    strike_pct_range: float = 0.20,
) -> list:
    """Real-time options chain snapshot with Greeks via Polygon (requires Options plan).

    near_price: if provided, restricts strikes to ±strike_pct_range of that price
                so we fetch active ATM/near-OTM contracts instead of deep ITM junk.
    """
    from datetime import date, timedelta
    c = _client()
    today = date.today()
    params = {
        "expiration_date.gte": today.isoformat(),
        "expiration_date.lte": (today + timedelta(days=dte_max)).isoformat(),
        "limit": 250,
    }
    if contract_type:
        params["contract_type"] = contract_type.lower()
    if near_price and near_price > 0:
        params["strike_price.gte"] = round(near_price * (1 - strike_pct_range), 2)
        params["strike_price.lte"] = round(near_price * (1 + strike_pct_range), 2)
    try:
        return list(c.list_snapshot_options_chain(ticker, params=params))
    except Exception as e:
        logger.warning("options_chain_snapshot failed for %s: %s", ticker, e)
        return []


def get_snapshots_batch(tickers: list[str]) -> dict[str, dict]:
    """Batch equity snapshots. Returns {ticker: {price, open, high, low, volume, change_pct, prev_close}}."""
    c = _client()
    try:
        snaps = c.get_snapshot_all("stocks", tickers=tickers)
        result = {}
        for snap in (snaps or []):
            t = snap.ticker
            if not t:
                continue
            day = snap.day
            prev = snap.prev_day
            result[t] = {
                "price": float(day.close or 0) if day else 0,
                "open": float(day.open or 0) if day else 0,
                "high": float(day.high or 0) if day else 0,
                "low": float(day.low or 0) if day else 0,
                "volume": float(day.volume or 0) if day else 0,
                "vwap": float(day.vwap or 0) if day else 0,
                "change_pct": round(float(snap.todays_change_percent or 0), 2),
                "prev_close": float(prev.close or 0) if prev else 0,
            }
        return result
    except Exception as e:
        logger.warning("get_snapshots_batch failed: %s", e)
        return {}


def get_ohlcv_bars(ticker: str, days: int = 35) -> list[dict]:
    """Daily OHLCV bars ascending. Returns list of {o,h,l,c,v} dicts."""
    from datetime import date, timedelta
    c = _client()
    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=days + 30)).isoformat()
    try:
        aggs = c.get_aggs(ticker, 1, "day", from_date, to_date, adjusted=True, sort="asc", limit=days + 30)
        return [{"o": a.open, "h": a.high, "l": a.low, "c": a.close, "v": a.volume} for a in (aggs or []) if a.close]
    except Exception as e:
        logger.warning("get_ohlcv_bars failed for %s: %s", ticker, e)
        return []


def get_vix() -> float | None:
    """Current VIX level via Polygon index daily bars."""
    from datetime import date, timedelta
    c = _client()
    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=10)).isoformat()
    try:
        aggs = c.get_aggs("I:VIX", 1, "day", from_date, to_date, adjusted=False, sort="desc", limit=3)
        for a in (aggs or []):
            if a.close:
                return float(a.close)
    except Exception as e:
        logger.debug("get_vix failed: %s", e)
    return None


def get_close_prices(ticker: str, days: int = 250) -> list[float]:
    """Daily close prices ascending for the last N calendar days. Used for MA/HV computation."""
    from datetime import date, timedelta
    c = _client()
    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=days + 60)).isoformat()
    try:
        aggs = c.get_aggs(ticker, 1, "day", from_date, to_date, adjusted=True, sort="asc", limit=days + 60)
        closes = [float(a.close) for a in (aggs or []) if a.close]
        return closes[-days:] if len(closes) > days else closes
    except Exception as e:
        logger.warning("get_close_prices failed for %s: %s", ticker, e)
        return []


def get_ticker_snapshot(ticker: str) -> dict:
    """Current price, day change %, OHLCV for a single equity ticker."""
    c = _client()
    try:
        snap = c.get_snapshot_ticker("stocks", ticker)
        if not snap:
            return {}
        day = snap.day
        prev = snap.prev_day
        return {
            "price": float(day.close or 0) if day else 0,
            "open": float(day.open or 0) if day else 0,
            "high": float(day.high or 0) if day else 0,
            "low": float(day.low or 0) if day else 0,
            "volume": float(day.volume or 0) if day else 0,
            "vwap": float(day.vwap or 0) if day else 0,
            "change_pct": round(float(snap.todays_change_percent or 0), 2),
            "prev_close": float(prev.close or 0) if prev else 0,
        }
    except Exception as e:
        logger.warning("get_ticker_snapshot failed for %s: %s", ticker, e)
        return {}


def get_analyst_ratings(ticker: str, limit: int = 5) -> list[dict]:
    """Recent analyst upgrades/downgrades and price targets via Polygon Benzinga feed."""
    c = _client()
    try:
        items = c.list_benzinga_analyst_insights(
            ticker=ticker, limit=limit, sort="published_utc", order="desc"
        )
        result = []
        for item in (items or []):
            result.append({
                "analyst": getattr(item, "analyst", None),
                "rating": getattr(item, "rating_current", None),
                "prior_rating": getattr(item, "rating_prior", None),
                "action": getattr(item, "action_company", None),
                "pt": getattr(item, "pt_current", None),
                "prior_pt": getattr(item, "pt_prior", None),
                "published": getattr(item, "published_utc", None),
            })
            if len(result) >= limit:
                break
        return result
    except Exception as e:
        logger.debug("get_analyst_ratings failed for %s: %s", ticker, e)
        return []


def get_financials(ticker: str) -> dict:
    """
    Latest annual financials from Polygon (SEC-sourced).
    Returns normalized dict: revenue, gross_profit, net_income, operating_cash_flow,
    free_cash_flow, total_debt, cash, equity.
    """
    c = _client()

    def _val(obj, *attrs):
        for a in attrs:
            v = getattr(obj, a, None)
            if v is not None:
                try:
                    return float(v)
                except Exception:
                    pass
        return None

    result: dict = {}
    try:
        items = list(c.list_financials(
            ticker=ticker, timeframe="annual", limit=1, order="desc", include_sources=False
        ))
        if not items:
            return result
        fin = items[0]
        fins = getattr(fin, "financials", None)
        if not fins:
            return result

        inc = getattr(fins, "income_statement", None)
        if inc:
            result["revenue"] = _val(inc, "revenues", "revenue")
            result["gross_profit"] = _val(inc, "gross_profit")
            result["operating_income"] = _val(inc, "operating_income_loss")
            result["net_income"] = _val(inc, "net_income_loss")

        bs = getattr(fins, "balance_sheet", None)
        if bs:
            result["total_debt"] = _val(bs, "long_term_debt")
            result["cash"] = _val(bs, "cash_and_cash_equivalents_including_restricted_cash", "cash")
            result["equity"] = _val(bs, "equity")

        cf = getattr(fins, "cash_flow_statement", None)
        if cf:
            ocf = _val(cf, "net_cash_flow_from_operating_activities")
            capex = _val(cf, "capital_expenditure")
            result["operating_cash_flow"] = ocf
            result["capex"] = capex
            if ocf is not None and capex is not None:
                result["free_cash_flow"] = ocf + capex  # capex is negative in SEC
    except Exception as e:
        logger.debug("get_financials failed for %s: %s", ticker, e)

    return result


def get_news(ticker: str | None = None, limit: int = 5) -> list[dict]:
    """Recent news articles, returned as plain dicts."""
    c = _client()
    kwargs = {"limit": limit, "order": "desc"}
    if ticker:
        kwargs["ticker"] = ticker
    articles = c.list_ticker_news(**kwargs)
    result = []
    for n in (articles or []):
        result.append({"title": getattr(n, "title", "") or ""})
        if len(result) >= limit:
            break
    return result
