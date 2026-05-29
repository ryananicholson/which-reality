"""
Thin wrapper around the Public.com Brokerage API.
Used for real-time quotes and options chain data with Greeks.
Auth: secret key → bearer token exchange; token cached until expiry.
"""
import logging
import time
import requests

from config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.public.com"

# Token cache: {token, expires_at}
_token_cache: dict = {}
_account_id: str | None = None


def _get_token() -> str:
    """Exchange secret key for a bearer token, caching until expiry."""
    now = time.time()
    if _token_cache.get("token") and now < _token_cache.get("expires_at", 0) - 60:
        return _token_cache["token"]

    secret = settings.public_api_key
    if not secret:
        raise RuntimeError("PUBLIC_API_KEY is not set")

    resp = requests.post(
        f"{BASE_URL}/userapiauthservice/personal/access-tokens",
        json={"secretKey": secret},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("accessToken") or data.get("access_token") or ""
    if not token:
        raise RuntimeError(f"Public API token exchange failed: {data}")

    # Most JWT tokens include expiry; default to 55 minutes if not provided
    expires_in = data.get("expiresIn") or data.get("expires_in") or 3300
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + int(expires_in)
    logger.debug("Public.com token refreshed, expires in %ds", expires_in)
    return token


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}", "Accept": "application/json"}


def _get_account_id() -> str:
    global _account_id
    if _account_id:
        return _account_id
    resp = requests.get(f"{BASE_URL}/userapigateway/trading/account", headers=_headers(), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # Handle both list and dict responses
    if isinstance(data, list):
        data = data[0]
    acct_id = data.get("accountId") or data.get("account_id") or data.get("id") or ""
    if not acct_id:
        raise RuntimeError(f"Could not find accountId in response: {data}")
    _account_id = str(acct_id)
    logger.info("Public.com accountId resolved: %s", _account_id)
    return _account_id


def get_quote(ticker: str) -> dict | None:
    """
    Fetch real-time quote for a single ticker.
    Returns dict with keys: last, bid, ask, or None on failure.
    """
    try:
        acct = _get_account_id()
        resp = requests.get(
            f"{BASE_URL}/userapigateway/marketdata/{acct}/quotes",
            headers=_headers(),
            params={"symbols": ticker},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # Response is typically a list or dict keyed by symbol
        if isinstance(data, list):
            item = next((x for x in data if x.get("symbol", "").upper() == ticker.upper()), None)
        elif isinstance(data, dict):
            item = data.get(ticker) or data.get(ticker.upper()) or (list(data.values())[0] if data else None)
        else:
            item = None
        return item
    except Exception as e:
        logger.warning("Public.com quote failed for %s: %s", ticker, e)
        return None


def get_last_price(ticker: str) -> float | None:
    """
    Return the current last-trade price for a ticker, or None on failure.
    Tries lastPrice, last, mark, midpoint fields.
    """
    try:
        q = get_quote(ticker)
        if not q:
            return None
        for field in ("lastPrice", "last_price", "last", "mark", "midpoint", "close"):
            val = q.get(field)
            if val:
                return float(val)
        return None
    except Exception as e:
        logger.warning("Public.com get_last_price failed for %s: %s", ticker, e)
        return None


def get_option_expirations(ticker: str) -> list[str]:
    """Return list of available expiration date strings (YYYY-MM-DD) for ticker."""
    try:
        acct = _get_account_id()
        resp = requests.get(
            f"{BASE_URL}/userapigateway/marketdata/{acct}/option-expirations",
            headers=_headers(),
            params={"symbol": ticker},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return [str(x) for x in data if x]
        if isinstance(data, dict):
            return [str(x) for x in (data.get("expirations") or data.get("dates") or []) if x]
        return []
    except Exception as e:
        logger.warning("Public.com option expirations failed for %s: %s", ticker, e)
        return []


def get_option_chain(ticker: str, expiration: str, contract_type: str = "call") -> list[dict]:
    """
    Fetch options chain for a ticker/expiry/type.
    Returns list of dicts with: strike, bid, ask, mid, iv, delta, gamma, theta, vega, volume, oi.
    """
    try:
        acct = _get_account_id()
        resp = requests.get(
            f"{BASE_URL}/userapigateway/marketdata/{acct}/option-chain",
            headers=_headers(),
            params={
                "symbol": ticker,
                "expirationDate": expiration,
                "type": contract_type,
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()
        if isinstance(raw, dict):
            raw = raw.get("options") or raw.get("contracts") or raw.get("chain") or []
        results = []
        for item in raw:
            try:
                bid = float(item.get("bid") or 0)
                ask = float(item.get("ask") or 0)
                mid = round((bid + ask) / 2, 2) if bid > 0 else float(item.get("lastPrice") or item.get("last") or 0)
                if mid <= 0:
                    continue
                results.append({
                    "strike": float(item.get("strike") or item.get("strikePrice") or 0),
                    "bid": bid,
                    "ask": ask,
                    "mid": mid,
                    "iv_pct": round(float(item.get("impliedVolatility") or item.get("iv") or 0) * 100, 1),
                    "delta": float(item.get("delta") or 0),
                    "gamma": float(item.get("gamma") or 0),
                    "theta": float(item.get("theta") or 0),
                    "vega": float(item.get("vega") or 0),
                    "volume": int(item.get("volume") or 0),
                    "open_interest": int(item.get("openInterest") or item.get("open_interest") or 0),
                })
            except Exception:
                continue
        return results
    except Exception as e:
        logger.warning("Public.com option chain failed for %s %s %s: %s", ticker, expiration, contract_type, e)
        return []
