import logging
import json
import math
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False
    logger.warning("yfinance not available — using Yahoo Finance JSON API fallback")

DEFAULT_UNIVERSE = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ORCL",
    # Mid/large-cap tech & semiconductors
    "AMD", "INTC", "QCOM", "MU", "LRCX", "KLAC", "MRVL", "TXN", "AMAT", "ON",
    # Software / cloud / cybersecurity
    "CRM", "NOW", "ADBE", "PANW", "CRWD", "NET", "SNOW", "DDOG", "ZS", "OKTA",
    "PLTR", "HUBS", "WDAY", "TEAM", "MDB", "CFLT",
    # Consumer / e-commerce / travel
    "UBER", "LYFT", "ABNB", "BKNG", "DASH", "COIN", "RBLX",
    # Financials
    "JPM", "BAC", "GS", "MS", "WFC", "V", "MA", "PYPL", "AXP", "BLK",
    # Healthcare
    "JNJ", "PFE", "UNH", "ABBV", "MRK", "LLY", "DHR", "TMO", "ISRG", "CVS",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY",
    # Industrials / defense
    "BA", "CAT", "DE", "LMT", "RTX", "HON", "GE", "ETN",
    # Consumer staples / retail
    "COST", "WMT", "TGT", "HD", "KO", "PEP", "MCD", "SBUX", "NKE",
    # Media / telecom
    "DIS", "NFLX", "CMCSA", "T", "VZ",
    # ETFs (broad market + sector)
    "SPY", "QQQ", "IWM", "GLD", "TLT",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# Technical indicator calculations (pure numpy/pandas, no extra libraries)
# ---------------------------------------------------------------------------

def _rsi(closes: pd.Series, period: int = 14) -> float:
    """Relative Strength Index."""
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1) if not rsi.empty else None


def _macd(closes: pd.Series) -> dict:
    """MACD line, signal line, and histogram."""
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal
    return {
        "macd": round(float(macd_line.iloc[-1]), 3),
        "signal": round(float(signal.iloc[-1]), 3),
        "histogram": round(float(histogram.iloc[-1]), 3),
        "crossover": (
            "bullish" if histogram.iloc[-1] > 0 and histogram.iloc[-2] <= 0
            else "bearish" if histogram.iloc[-1] < 0 and histogram.iloc[-2] >= 0
            else "neutral"
        ),
    }


def _bollinger_bands(closes: pd.Series, period: int = 20) -> dict:
    """Bollinger Bands: upper, middle (SMA), lower, and %B."""
    sma = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    price = closes.iloc[-1]
    pct_b = (price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1]) if upper.iloc[-1] != lower.iloc[-1] else 0.5
    return {
        "upper": round(float(upper.iloc[-1]), 2),
        "middle": round(float(sma.iloc[-1]), 2),
        "lower": round(float(lower.iloc[-1]), 2),
        "pct_b": round(float(pct_b), 2),        # 0=at lower, 1=at upper, 0.5=at middle
        "squeeze": bool(((upper - lower) / sma).iloc[-1] < 0.10),  # tight bands = squeeze
    }


def _moving_averages(closes: pd.Series) -> dict:
    """20, 50, and 200-day simple moving averages + trend signals."""
    price = closes.iloc[-1]
    ma20 = closes.rolling(20).mean().iloc[-1] if len(closes) >= 20 else None
    ma50 = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else None
    ma200 = closes.rolling(200).mean().iloc[-1] if len(closes) >= 200 else None
    return {
        "ma20": round(float(ma20), 2) if ma20 else None,
        "ma50": round(float(ma50), 2) if ma50 else None,
        "ma200": round(float(ma200), 2) if ma200 else None,
        "above_ma20": bool(price > ma20) if ma20 else None,
        "above_ma50": bool(price > ma50) if ma50 else None,
        "above_ma200": bool(price > ma200) if ma200 else None,
        "golden_cross": bool(ma50 > ma200) if (ma50 and ma200) else None,   # bullish
        "death_cross": bool(ma50 < ma200) if (ma50 and ma200) else None,    # bearish
    }


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Average True Range — measures daily volatility in dollar terms."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return round(float(atr), 2) if not np.isnan(atr) else None


def _vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> float:
    """Volume-Weighted Average Price over the available window."""
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()
    return round(float(vwap.iloc[-1]), 2)


def _fibonacci_levels(closes: pd.Series, window: int = 50) -> dict:
    """Key Fibonacci retracement levels based on recent high/low."""
    recent = closes.tail(window)
    high = float(recent.max())
    low = float(recent.min())
    diff = high - low
    return {
        "high": round(high, 2),
        "low": round(low, 2),
        "fib_236": round(high - 0.236 * diff, 2),
        "fib_382": round(high - 0.382 * diff, 2),
        "fib_500": round(high - 0.500 * diff, 2),
        "fib_618": round(high - 0.618 * diff, 2),
        "fib_786": round(high - 0.786 * diff, 2),
    }


def _support_resistance(closes: pd.Series, window: int = 50) -> dict:
    """Simple pivot-point based support and resistance levels."""
    recent = closes.tail(window)
    pivot = float(recent.mean())
    std = float(recent.std())
    return {
        "resistance_1": round(pivot + std, 2),
        "resistance_2": round(pivot + 2 * std, 2),
        "support_1": round(pivot - std, 2),
        "support_2": round(pivot - 2 * std, 2),
        "pivot": round(pivot, 2),
    }


def _volume_trend(volumes: pd.Series) -> dict:
    """Compare recent 5-day avg volume to 20-day avg volume."""
    vol_5 = float(volumes.tail(5).mean())
    vol_20 = float(volumes.tail(20).mean())
    ratio = vol_5 / vol_20 if vol_20 else 1.0
    return {
        "avg_vol_5d": int(vol_5),
        "avg_vol_20d": int(vol_20),
        "ratio": round(ratio, 2),
        "trend": "high" if ratio > 1.5 else "low" if ratio < 0.7 else "normal",
    }


def _compute_all_indicators(df: pd.DataFrame) -> dict:
    """Given a DataFrame with Open/High/Low/Close/Volume, compute all indicators."""
    closes = df["Close"].dropna()
    if len(closes) < 26:
        return {}   # not enough history

    indicators = {}
    try:
        indicators["rsi"] = _rsi(closes)
    except Exception:
        pass
    try:
        indicators["macd"] = _macd(closes)
    except Exception:
        pass
    try:
        indicators["bollinger"] = _bollinger_bands(closes)
    except Exception:
        pass
    try:
        indicators["moving_averages"] = _moving_averages(closes)
    except Exception:
        pass
    try:
        indicators["atr"] = _atr(df["High"], df["Low"], df["Close"])
    except Exception:
        pass
    try:
        indicators["vwap"] = _vwap(df["High"], df["Low"], df["Close"], df["Volume"])
    except Exception:
        pass
    try:
        indicators["fibonacci"] = _fibonacci_levels(closes)
    except Exception:
        pass
    try:
        indicators["support_resistance"] = _support_resistance(closes)
    except Exception:
        pass
    try:
        indicators["volume_trend"] = _volume_trend(df["Volume"])
    except Exception:
        pass
    return indicators


# ---------------------------------------------------------------------------
# Black-Scholes helpers for real options chain data
# ---------------------------------------------------------------------------

def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _historical_volatility(ticker: str, days: int = 30) -> float | None:
    """Annualised historical volatility from recent daily closes. Polygon primary, yfinance fallback."""
    import math
    # Polygon primary
    try:
        from services.polygon_client import get_close_prices
        closes = get_close_prices(ticker, days=max(days * 3, 60))
        if len(closes) >= 10:
            log_returns = [math.log(closes[i] / closes[i-1]) for i in range(1, len(closes)) if closes[i] > 0 and closes[i-1] > 0]
            if len(log_returns) >= 5:
                mean = sum(log_returns) / len(log_returns)
                variance = sum((r - mean) ** 2 for r in log_returns) / max(len(log_returns) - 1, 1)
                hv = math.sqrt(variance * 252)
                return hv if 0 < hv < 5.0 else None
    except Exception:
        pass
    # yfinance fallback
    if not _YF_AVAILABLE:
        return None
    try:
        hist = yf.download(ticker, period="60d", interval="1d", progress=False, auto_adjust=True)
        closes_s = hist["Close"]
        if hasattr(closes_s, "columns"):
            closes_s = closes_s.iloc[:, 0]
        closes_s = closes_s.dropna()
        if len(closes_s) < 10:
            return None
        returns = closes_s.pct_change().dropna()
        hv = float(returns.std() * (252 ** 0.5))
        return hv if hv > 0 else None
    except Exception:
        return None


def _bs_call_delta(price: float, strike: float, iv: float, T: float, r: float = 0.045) -> float | None:
    """Call delta via Black-Scholes. Returns value 0–1 (probability shares get called away)."""
    try:
        if T <= 0 or iv <= 0 or price <= 0 or strike <= 0:
            return None
        sigma_sqrtT = iv * math.sqrt(T)
        d1 = (math.log(price / strike) + (r + 0.5 * iv ** 2) * T) / sigma_sqrtT
        return round(_ncdf(d1), 3)
    except Exception:
        return None


def _bs_call_theta_daily(price: float, strike: float, iv: float, T: float, r: float = 0.045) -> float | None:
    """Daily income per share earned by the call SELLER from time decay. Positive = good."""
    try:
        if T <= 0 or iv <= 0 or price <= 0 or strike <= 0:
            return None
        sigma_sqrtT = iv * math.sqrt(T)
        d1 = (math.log(price / strike) + (r + 0.5 * iv ** 2) * T) / sigma_sqrtT
        d2 = d1 - sigma_sqrtT
        npdf_d1 = math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi)
        theta_annual = (
            -(price * npdf_d1 * iv) / (2 * math.sqrt(T))
            - r * strike * math.exp(-r * T) * _ncdf(d2)
        )
        return round(-theta_annual / 365.0, 4)
    except Exception:
        return None


def _bs_put_delta(price: float, strike: float, iv: float, T: float, r: float = 0.045) -> float | None:
    """Put delta via Black-Scholes. iv is annual vol as fraction (0.28 = 28%)."""
    try:
        if T <= 0 or iv <= 0 or price <= 0 or strike <= 0:
            return None
        sigma_sqrtT = iv * math.sqrt(T)
        d1 = (math.log(price / strike) + (r + 0.5 * iv ** 2) * T) / sigma_sqrtT
        return round(_ncdf(d1) - 1.0, 3)   # negative for puts
    except Exception:
        return None


def _bs_put_theta_daily(price: float, strike: float, iv: float, T: float, r: float = 0.045) -> float | None:
    """
    Daily income per share earned by the put SELLER from time decay.
    Positive value = seller collects this per share per day just from time passing.
    """
    try:
        if T <= 0 or iv <= 0 or price <= 0 or strike <= 0:
            return None
        sigma_sqrtT = iv * math.sqrt(T)
        d1 = (math.log(price / strike) + (r + 0.5 * iv ** 2) * T) / sigma_sqrtT
        d2 = d1 - sigma_sqrtT
        npdf_d1 = math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi)
        # BS annual theta for put: -(S*N'(d1)*σ)/(2√T) + r*K*e^{-rT}*N(-d2)
        theta_annual = (
            -(price * npdf_d1 * iv) / (2 * math.sqrt(T))
            + r * strike * math.exp(-r * T) * _ncdf(-d2)
        )
        # Seller receives the decay: positive, daily per share
        return round(-theta_annual / 365.0, 4)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Finnhub OHLCV helper — primary data source
# ---------------------------------------------------------------------------

def _finnhub_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch OHLCV via Finnhub candles, returned as a DataFrame matching yfinance format."""
    try:
        from services.finnhub_client import get_candles
        days = {"1mo": 35, "3mo": 95, "6mo": 185, "1y": 375, "2y": 755}.get(period, 375)
        candles = get_candles(ticker, days=days)
        if candles.get("s") != "ok" or not candles.get("c"):
            return pd.DataFrame()
        df = pd.DataFrame({
            "Open":   candles.get("o", [None] * len(candles["c"])),
            "High":   candles.get("h", [None] * len(candles["c"])),
            "Low":    candles.get("l", [None] * len(candles["c"])),
            "Close":  candles["c"],
            "Volume": candles.get("v", [0] * len(candles["c"])),
        }, index=pd.to_datetime(candles["t"], unit="s")).dropna(subset=["Close"])
        return df
    except Exception as e:
        logger.debug("Finnhub history error for %s: %s", ticker, e)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Yahoo Finance HTTP fallback (no yfinance)
# ---------------------------------------------------------------------------

def _yf_fetch_ohlcv(ticker: str, period_days: int = 200) -> pd.DataFrame:
    """Fetch OHLCV history via Yahoo Finance chart API."""
    import requests
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?interval=1d&range={period_days}d"
        )
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return pd.DataFrame()
        result = r.json().get("chart", {}).get("result", [])
        if not result:
            return pd.DataFrame()
        timestamps = result[0].get("timestamp", [])
        q = result[0].get("indicators", {}).get("quote", [{}])[0]
        df = pd.DataFrame({
            "Date": pd.to_datetime(timestamps, unit="s"),
            "Open":   q.get("open", []),
            "High":   q.get("high", []),
            "Low":    q.get("low", []),
            "Close":  q.get("close", []),
            "Volume": q.get("volume", []),
        }).dropna(subset=["Close"])
        df.set_index("Date", inplace=True)
        return df
    except Exception as e:
        logger.debug("OHLCV fetch error for %s: %s", ticker, e)
        return pd.DataFrame()


def _yf_fetch_summary(ticker: str) -> dict:
    import requests
    try:
        url = (
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
            "?modules=summaryDetail,financialData,defaultKeyStatistics"
        )
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json().get("quoteSummary", {}).get("result", [{}])[0]
        sd = data.get("summaryDetail", {})
        fd = data.get("financialData", {})
        return {
            "pe_ratio": sd.get("trailingPE", {}).get("raw"),
            "eps_growth_ttm": fd.get("earningsGrowth", {}).get("raw"),
            "revenue_growth_ttm": fd.get("revenueGrowth", {}).get("raw"),
            "div_yield": sd.get("dividendYield", {}).get("raw"),
            "sector": "",
            "analyst_rating": fd.get("recommendationKey", "none"),
            "52w_high": sd.get("fiftyTwoWeekHigh", {}).get("raw"),
            "52w_low": sd.get("fiftyTwoWeekLow", {}).get("raw"),
        }
    except Exception as e:
        logger.debug("YF summary error for %s: %s", ticker, e)
        return {}


# ---------------------------------------------------------------------------
# Public service class
# ---------------------------------------------------------------------------

class StockDataService:

    def _get_history(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """Return OHLCV DataFrame. Finnhub primary; yfinance per-ticker fallback."""
        df = _finnhub_history(ticker, period)
        if not df.empty:
            return df
        if _YF_AVAILABLE:
            try:
                df = yf.Ticker(ticker).history(period=period)
                if not df.empty:
                    return df
            except Exception:
                pass
        days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 252, "2y": 504}.get(period, 252)
        return _yf_fetch_ohlcv(ticker, period_days=days)

    def get_price_and_technicals(self, ticker: str) -> dict:
        """
        Returns current price + full technical indicator suite for one ticker.
        This is the main method used by all three analysis engines.
        """
        df = self._get_history(ticker, period="1y")
        if df.empty or len(df) < 26:
            return {}

        closes = df["Close"].dropna()
        price = float(closes.iloc[-1])
        price_5d_ago = float(closes.iloc[max(0, len(closes) - 6)])
        change_5d_pct = round(((price - price_5d_ago) / price_5d_ago) * 100, 2)

        result = {
            "price": round(price, 2),
            "change_5d_pct": change_5d_pct,
            "volume": int(df["Volume"].iloc[-1]),
        }
        result.update(_compute_all_indicators(df))
        return result

    def get_price_data(self, tickers: list[str]) -> dict:
        """Lightweight price-only data (used when full technicals not needed)."""
        result = {}
        for ticker in tickers:
            try:
                d = self.get_price_and_technicals(ticker)
                if d:
                    result[ticker] = {k: d[k] for k in ("price", "change_5d_pct", "volume") if k in d}
            except Exception as e:
                logger.debug("Price data error for %s: %s", ticker, e)
        return result

    def get_technicals_bulk(self, tickers: list[str]) -> dict:
        """Full price + technicals for a list of tickers."""
        result = {}
        for ticker in tickers:
            try:
                d = self.get_price_and_technicals(ticker)
                if d:
                    result[ticker] = d
            except Exception as e:
                logger.debug("Technicals error for %s: %s", ticker, e)
        return result

    def get_options_data(self, tickers: list[str]) -> dict:
        result = {}
        for ticker in tickers:
            # Try Polygon first for live IV
            try:
                from services.polygon_client import get_options_chain_snapshot
                snaps = get_options_chain_snapshot(ticker, dte_max=7)
                if snaps:
                    price = None
                    for s in snaps:
                        if s.underlying_asset and s.underlying_asset.price:
                            price = float(s.underlying_asset.price)
                            break
                    if price:
                        atm = min(
                            (s for s in snaps if s.details and s.implied_volatility and s.details.contract_type == "call"),
                            key=lambda s: abs(float(s.details.strike_price or 0) - price),
                            default=None,
                        )
                        if atm and atm.implied_volatility:
                            iv = round(float(atm.implied_volatility) * 100, 1)
                            expiry = str(atm.details.expiration_date)
                            result[ticker] = {
                                "nearest_expiry": expiry,
                                "atm_iv": iv,
                                "iv_rank_approx": min(100, round(iv / 0.5, 1)),
                                "data_source": "polygon_live",
                            }
                            continue
            except Exception:
                pass

            # yfinance fallback
            if not _YF_AVAILABLE:
                continue
            try:
                t = yf.Ticker(ticker)
                expiries = t.options
                if not expiries:
                    continue
                chain = t.option_chain(expiries[0])
                calls = chain.calls
                info = t.fast_info
                current_price = getattr(info, "last_price", None)
                if not current_price or calls.empty:
                    continue
                atm = calls.iloc[(calls["strike"] - current_price).abs().argsort()[:1]]
                atm_iv = float(atm["impliedVolatility"].iloc[0]) * 100 if not atm.empty else None
                result[ticker] = {
                    "nearest_expiry": expiries[0],
                    "atm_iv": round(atm_iv, 1) if atm_iv else None,
                    "iv_rank_approx": min(100, round(atm_iv / 0.5, 1)) if atm_iv else None,
                }
            except Exception as e:
                logger.debug("Options data error for %s: %s", ticker, e)
        return result

    def get_fundamentals(self, tickers: list[str]) -> dict:
        result = {}
        for ticker in tickers:
            try:
                from services.finnhub_client import get_basic_financials, get_company_profile
                metrics = get_basic_financials(ticker)
                profile = get_company_profile(ticker)
                if metrics or profile:
                    result[ticker] = {
                        "pe_ratio": metrics.get("peNormalizedAnnual") or metrics.get("peTTM"),
                        "eps_growth_ttm": metrics.get("epsGrowthTTMYoy"),
                        "revenue_growth_ttm": metrics.get("revenueGrowthTTMYoy"),
                        "div_yield": metrics.get("dividendYieldIndicatedAnnual"),
                        "sector": profile.get("finnhubIndustry", "Unknown"),
                        "analyst_rating": None,
                        "52w_high": metrics.get("52WeekHigh"),
                        "52w_low": metrics.get("52WeekLow"),
                    }
                    continue
            except Exception as e:
                logger.debug("Finnhub fundamentals error for %s: %s", ticker, e)
            # Fallback: yfinance per-ticker
            try:
                if _YF_AVAILABLE:
                    info = yf.Ticker(ticker).info
                    result[ticker] = {
                        "pe_ratio": info.get("trailingPE"),
                        "eps_growth_ttm": info.get("earningsGrowth"),
                        "revenue_growth_ttm": info.get("revenueGrowth"),
                        "div_yield": info.get("dividendYield"),
                        "sector": info.get("sector", "Unknown"),
                        "analyst_rating": info.get("recommendationKey", "none"),
                    }
                else:
                    fund = _yf_fetch_summary(ticker)
                    if fund:
                        result[ticker] = fund
            except Exception as e:
                logger.debug("Fundamentals fallback error for %s: %s", ticker, e)
        return result

    def get_current_price(self, ticker: str) -> Optional[float]:
        try:
            from services.finnhub_client import get_quote
            q = get_quote(ticker)
            if q.get("c"):
                return float(q["c"])
        except Exception:
            pass
        try:
            if _YF_AVAILABLE:
                return float(yf.Ticker(ticker).fast_info.last_price)
        except Exception:
            pass
        try:
            df = _yf_fetch_ohlcv(ticker, period_days=5)
            return float(df["Close"].iloc[-1]) if not df.empty else None
        except Exception:
            return None

    def get_wheel_screening_data(self, tickers: list[str]) -> dict:
        """Full technicals + options IV for wheel strategy screening."""
        technicals = self.get_technicals_bulk(tickers)
        options = self.get_options_data(tickers)
        for ticker in technicals:
            if ticker in options:
                technicals[ticker].update(options[ticker])
        return technicals

    def _polygon_options_chain(
        self, ticker: str, contract_type: str, dte_min: int, dte_max: int,
        near_price: float | None = None,
    ) -> tuple[list[dict], float | None]:
        """
        Fetch options chain from Polygon with real Greeks and live quotes.
        Returns (list_of_option_dicts, underlying_price). Falls back to [] on error.
        Each dict: strike, expiry, dte, bid, ask, mid, iv_pct, delta, delta_abs,
                   theta_seller (positive = seller income per share/day), gamma, vega,
                   volume, open_interest.
        near_price filters to ATM ±25% so Polygon doesn't return deep-ITM junk first.
        """
        try:
            from services.polygon_client import get_options_chain_snapshot
            snapshots = get_options_chain_snapshot(
                ticker, dte_max=dte_max, contract_type=contract_type,
                near_price=near_price, strike_pct_range=0.25,
            )
            if not snapshots:
                logger.warning("_polygon_options_chain: no snapshots returned for %s (near_price=%s, dte_max=%s)", ticker, near_price, dte_max)
                return [], None

            today = date.today()
            # Polygon often doesn't populate underlying_asset.price — use near_price as seed
            underlying_price = near_price or None
            result = []
            skipped_dte = skipped_mid = skipped_delta = skipped_exc = 0

            for snap in snapshots:
                if not snap.details:
                    continue
                if not underlying_price and snap.underlying_asset and snap.underlying_asset.price:
                    underlying_price = float(snap.underlying_asset.price)
                try:
                    exp = str(snap.details.expiration_date)
                    dte = (date.fromisoformat(exp) - today).days
                    if dte < dte_min or dte > dte_max:
                        skipped_dte += 1
                        continue
                    strike = float(snap.details.strike_price or 0)
                    if strike <= 0:
                        continue

                    bid = ask = mid = 0.0
                    if snap.last_quote:
                        bid = float(snap.last_quote.bid or 0)
                        ask = float(snap.last_quote.ask or 0)
                        mp = snap.last_quote.midpoint
                        mid = float(mp) if mp else (round((bid + ask) / 2, 2) if bid > 0 else 0.0)
                    if mid <= 0 and snap.last_trade:
                        mid = float(snap.last_trade.price or 0)
                    # Market-closed fallbacks: Polygon fair_market_value then prior day close
                    if mid <= 0 and snap.fair_market_value:
                        mid = float(snap.fair_market_value)
                    if mid <= 0 and snap.day and snap.day.close:
                        mid = float(snap.day.close)
                    mid = round(mid, 2)  # round before filter so tiny values (e.g. 0.001) don't pass as non-zero then store as 0.0
                    if mid <= 0:
                        skipped_mid += 1
                        continue

                    iv_pct = round(float(snap.implied_volatility or 0) * 100, 1)

                    # Real Greeks from Polygon; BS fallback when market closed
                    delta = gamma = theta_holder = vega = None
                    if snap.greeks:
                        delta = float(snap.greeks.delta) if snap.greeks.delta is not None else None
                        gamma = float(snap.greeks.gamma) if snap.greeks.gamma is not None else None
                        theta_holder = float(snap.greeks.theta) if snap.greeks.theta is not None else None
                        vega = float(snap.greeks.vega) if snap.greeks.vega is not None else None

                    if delta is None and iv_pct > 0 and underlying_price:
                        T = max(dte, 1) / 365
                        iv_dec = iv_pct / 100
                        if contract_type == "call":
                            delta = _bs_call_delta(underlying_price, strike, iv_dec, T)
                            theta_holder = -(_bs_call_theta_daily(underlying_price, strike, iv_dec, T) or 0)
                        else:
                            delta = _bs_put_delta(underlying_price, strike, iv_dec, T)
                            theta_holder = -(_bs_put_theta_daily(underlying_price, strike, iv_dec, T) or 0)

                    if delta is None:
                        skipped_delta += 1
                        continue

                    # theta_seller = income to the seller per share per day (positive)
                    theta_seller = round(abs(theta_holder), 4) if theta_holder is not None else None

                    result.append({
                        "strike": strike,
                        "expiry": exp,
                        "dte": dte,
                        "bid": round(bid, 2),
                        "ask": round(ask, 2),
                        "mid": round(mid, 2),
                        "iv_pct": iv_pct,
                        "delta": delta,
                        "delta_abs": abs(delta),
                        "theta_seller": theta_seller,
                        "gamma": gamma,
                        "vega": vega,
                        "volume": int(snap.day.volume or 0) if snap.day else 0,
                        "open_interest": int(snap.open_interest or 0),
                    })
                except Exception:
                    skipped_exc += 1
                    continue

            logger.warning(
                "_polygon_options_chain %s: kept=%d skipped(dte=%d mid=%d delta=%d exc=%d) underlying_price=%s",
                ticker, len(result), skipped_dte, skipped_mid, skipped_delta, skipped_exc, underlying_price,
            )
            return result, underlying_price
        except Exception as e:
            logger.warning("_polygon_options_chain failed for %s: %s", ticker, e)
            return [], None

    def get_put_tiers(self, ticker: str) -> dict | None:
        """
        Fetch real put options chain and return three tiers for wheel strategy analysis.
        Uses Polygon real-time data (with Greeks) when available; falls back to yfinance.
        """
        # Pre-fetch live price: Public → Finnhub → yfinance
        _live_price: float | None = None
        try:
            from services.public_client import get_last_price as _pub_price
            _live_price = _pub_price(ticker)
        except Exception:
            pass
        if not _live_price:
            try:
                from services.finnhub_client import get_quote
                q = get_quote(ticker)
                _live_price = float(q.get("c") or q.get("pc") or 0) or None
            except Exception:
                pass
        if not _live_price:
            try:
                fi = yf.Ticker(ticker).fast_info
                raw_last = float(fi.last_price or 0) or None
                prev_close = float(fi.previous_close or 0) or None
                if raw_last and prev_close and not (0.5 <= raw_last / prev_close <= 2.0):
                    logger.warning("Price sanity %s: last_price=%s vs prev_close=%s — using prev_close", ticker, raw_last, prev_close)
                    _live_price = prev_close
                else:
                    _live_price = raw_last or prev_close
            except Exception:
                pass

        # --- Polygon path (preferred) ---
        try:
            puts, price = self._polygon_options_chain(ticker, "put", 14, 45, near_price=_live_price)
            if not price:
                price = _live_price
            if puts and price:
                today = date.today()
                # Pick expiry closest to 21 DTE (sweet spot for wheel)
                expiries = sorted(set(p["expiry"] for p in puts))
                target_expiry = min(expiries, key=lambda e: abs((date.fromisoformat(e) - today).days - 21))
                puts = [p for p in puts if p["expiry"] == target_expiry]
                if not puts:
                    raise ValueError("no puts for target expiry")
                dte = (date.fromisoformat(target_expiry) - today).days
                atm = min(puts, key=lambda p: abs(p["strike"] - price))
                atm_iv_pct = atm["iv_pct"]

                def _poly_tier(target_delta_abs: float) -> dict | None:
                    best = min(puts, key=lambda p: abs(p["delta_abs"] - target_delta_abs))
                    if abs(best["delta_abs"] - target_delta_abs) > 0.15:
                        return None
                    mid = best["mid"]
                    strike = best["strike"]
                    breakeven = round(strike - mid, 2)
                    drop_pct = round((price - breakeven) / price * 100, 1)
                    ann_return = round((mid / strike) * (365 / dte) * 100, 1) if strike > 0 and dte > 0 else None
                    daily_income = round((best["theta_seller"] or 0) * 100, 2)
                    return {
                        "strike": strike,
                        "expiry": target_expiry,
                        "dte": dte,
                        "bid": best["bid"],
                        "ask": best["ask"],
                        "mid_premium": mid,
                        "premium_per_contract": round(mid * 100, 2),
                        "iv_pct": best["iv_pct"],
                        "delta_abs": round(best["delta_abs"], 2),
                        "assignment_chance_pct": round(best["delta_abs"] * 100),
                        "daily_income_per_contract": daily_income,
                        "breakeven": breakeven,
                        "drop_to_breakeven_pct": drop_pct,
                        "annualized_return_pct": ann_return,
                        "volume": best["volume"],
                        "open_interest": best["open_interest"],
                    }

                return {
                    "current_price": round(price, 2),
                    "expiry": target_expiry,
                    "dte": dte,
                    "atm_iv_pct": atm_iv_pct,
                    "data_source": "polygon_live",
                    "likely": _poly_tier(0.45),
                    "moderate": _poly_tier(0.30),
                    "unlikely": _poly_tier(0.16),
                }
        except Exception as e:
            logger.warning("get_put_tiers Polygon path failed for %s: %s", ticker, e)

        # --- yfinance fallback ---
        if not _YF_AVAILABLE:
            return None
        try:
            t = yf.Ticker(ticker)
            expiries = t.options
            if not expiries:
                return None

            # Prefer expiry 14-45 days out — best premium-to-risk ratio for wheel
            today = date.today()
            target_expiry = None
            for exp in expiries:
                days = (date.fromisoformat(exp) - today).days
                if 14 <= days <= 45:
                    target_expiry = exp
                    break
            if not target_expiry:
                target_expiry = expiries[0]

            price = _live_price
            if not price:
                price = getattr(t.fast_info, "last_price", None)
            if not price:
                return None

            chain = t.option_chain(target_expiry)
            puts = chain.puts.copy()
            if puts.empty:
                return None

            exp_date = date.fromisoformat(target_expiry)
            T = max((exp_date - today).days, 1) / 365.0
            dte = (exp_date - today).days

            # Use real bid/ask when markets are open; fall back to lastPrice when closed.
            puts["_mid"] = puts.apply(
                lambda r: round((float(r["bid"]) + float(r["ask"])) / 2, 2)
                          if float(r["bid"]) > 0
                          else float(r.get("lastPrice", 0) or 0),
                axis=1,
            )
            puts["_is_live"] = puts["bid"] > 0
            puts = puts[puts["_mid"] > 0].copy()
            if puts.empty:
                return None

            data_source = "live" if puts["_is_live"].any() else "last_trade"

            # Compute delta and daily theta for each put using per-strike IV
            puts["_delta"] = puts.apply(
                lambda r: _bs_put_delta(price, r["strike"], float(r["impliedVolatility"]), T),
                axis=1,
            )
            puts["_theta_daily"] = puts.apply(
                lambda r: _bs_put_theta_daily(price, r["strike"], float(r["impliedVolatility"]), T),
                axis=1,
            )
            puts = puts[puts["_delta"].notna()].copy()
            puts["_delta_abs"] = puts["_delta"].abs()

            # ATM IV for context (put closest to current price)
            atm_idx = (puts["strike"] - price).abs().idxmin()
            atm_row = puts.loc[atm_idx]
            atm_iv_pct = round(float(atm_row["impliedVolatility"]) * 100, 1)

            def _best_near_delta(target: float) -> dict | None:
                if puts.empty:
                    return None
                idx = (puts["_delta_abs"] - target).abs().idxmin()
                row = puts.loc[idx]
                mid = float(row["_mid"])   # uses lastPrice when bid=0 (markets closed)
                bid = float(row["bid"]) if float(row["bid"]) > 0 else mid
                ask = float(row["ask"]) if float(row["ask"]) > 0 else mid
                strike = float(row["strike"])
                iv_pct = round(float(row["impliedVolatility"]) * 100, 1)
                delta_abs = round(float(row["_delta_abs"]), 2)
                theta = row["_theta_daily"]
                daily_per_contract = round(float(theta) * 100, 2) if theta else None
                breakeven = round(strike - mid, 2)
                drop_pct = round((price - breakeven) / price * 100, 1)
                ann_return = round((mid / strike) * (365 / dte) * 100, 1)
                return {
                    "strike": strike,
                    "expiry": target_expiry,
                    "dte": dte,
                    "bid": bid,
                    "ask": ask,
                    "mid_premium": mid,
                    "premium_per_contract": round(mid * 100, 2),
                    "iv_pct": iv_pct,
                    "delta_abs": delta_abs,
                    "assignment_chance_pct": round(delta_abs * 100),
                    "daily_income_per_contract": daily_per_contract,
                    "breakeven": breakeven,
                    "drop_to_breakeven_pct": drop_pct,
                    "annualized_return_pct": ann_return,
                    "volume": int(row.get("volume", 0) or 0),
                    "open_interest": int(row.get("openInterest", 0) or 0),
                }

            return {
                "current_price": round(price, 2),
                "expiry": target_expiry,
                "dte": dte,
                "atm_iv_pct": atm_iv_pct,
                "data_source": data_source,
                "likely": _best_near_delta(0.45),
                "moderate": _best_near_delta(0.30),
                "unlikely": _best_near_delta(0.16),
            }
        except Exception as e:
            logger.warning("get_put_tiers yfinance path failed for %s: %s", ticker, e)

        # --- Public.com fallback ---
        try:
            from services.public_client import get_option_expirations, get_option_chain
            from datetime import date as _date
            today = _date.today()
            expirations = get_option_expirations(ticker)
            if expirations:
                target_expiry = None
                for exp in sorted(expirations):
                    dte_check = (_date.fromisoformat(exp) - today).days
                    if 14 <= dte_check <= 45:
                        target_expiry = exp
                        break
                if not target_expiry:
                    target_expiry = sorted(expirations)[0]

                price = _live_price
                dte = (_date.fromisoformat(target_expiry) - today).days
                puts = get_option_chain(ticker, target_expiry, "put")
                puts = [p for p in puts if p.get("strike", 0) > 0 and p.get("mid", 0) > 0]

                if puts and price and dte > 0:
                    atm = min(puts, key=lambda p: abs(p["strike"] - price))
                    atm_iv_pct = atm.get("iv_pct", 0)

                    def _pub_tier(target_delta_abs: float) -> dict | None:
                        valid = [p for p in puts if abs(p.get("delta", 0)) > 0]
                        if not valid:
                            return None
                        best = min(valid, key=lambda p: abs(abs(p["delta"]) - target_delta_abs))
                        if abs(abs(best["delta"]) - target_delta_abs) > 0.15:
                            return None
                        mid = best["mid"]
                        strike = best["strike"]
                        delta_abs = round(abs(best["delta"]), 2)
                        theta = best.get("theta", 0) or 0
                        breakeven = round(strike - mid, 2)
                        drop_pct = round((price - breakeven) / price * 100, 1)
                        ann_return = round((mid / strike) * (365 / dte) * 100, 1) if strike > 0 else None
                        return {
                            "strike": strike,
                            "expiry": target_expiry,
                            "dte": dte,
                            "bid": best.get("bid", mid),
                            "ask": best.get("ask", mid),
                            "mid_premium": mid,
                            "premium_per_contract": round(mid * 100, 2),
                            "iv_pct": best.get("iv_pct", 0),
                            "delta_abs": delta_abs,
                            "assignment_chance_pct": round(delta_abs * 100),
                            "daily_income_per_contract": round(abs(theta) * 100, 2) if theta else None,
                            "breakeven": breakeven,
                            "drop_to_breakeven_pct": drop_pct,
                            "annualized_return_pct": ann_return,
                            "volume": best.get("volume", 0),
                            "open_interest": best.get("open_interest", 0),
                        }

                    return {
                        "current_price": round(price, 2),
                        "expiry": target_expiry,
                        "dte": dte,
                        "atm_iv_pct": atm_iv_pct,
                        "data_source": "public_com",
                        "likely": _pub_tier(0.45),
                        "moderate": _pub_tier(0.30),
                        "unlikely": _pub_tier(0.16),
                    }
        except Exception as e:
            logger.warning("get_put_tiers Public.com path failed for %s: %s", ticker, e)

        return None

    def snap_put_strike(self, ticker: str, suggested_strike: float, prefer_dte: tuple = (14, 45)) -> dict | None:
        """
        Given Claude's suggested put strike, snap to the nearest real tradeable strike.
        Uses Polygon real-time data when available; falls back to yfinance.
        """
        min_dte, max_dte = prefer_dte
        # --- Polygon path (preferred) ---
        try:
            puts, price = self._polygon_options_chain(
                ticker, "put", min_dte, max_dte, near_price=suggested_strike
            )
            if puts:
                best = min(puts, key=lambda p: abs(p["strike"] - suggested_strike))
                return {
                    "strike": best["strike"],
                    "expiry": best["expiry"],
                    "dte": best["dte"],
                    "mid_premium": best["mid"],
                    "bid": best["bid"],
                    "ask": best["ask"],
                    "volume": best["volume"],
                    "open_interest": best["open_interest"],
                }
        except Exception as e:
            logger.debug("snap_put_strike Polygon path failed for %s: %s", ticker, e)

        # --- yfinance fallback ---
        if not _YF_AVAILABLE:
            return None
        try:
            t = yf.Ticker(ticker)
            expiries = t.options
            if not expiries:
                return None

            today = date.today()
            min_dte, max_dte = prefer_dte
            target_expiry = None
            for exp in expiries:
                days = (date.fromisoformat(exp) - today).days
                if min_dte <= days <= max_dte:
                    target_expiry = exp
                    break
            if not target_expiry:
                for exp in expiries:
                    if (date.fromisoformat(exp) - today).days >= 7:
                        target_expiry = exp
                        break
            if not target_expiry:
                return None

            chain = t.option_chain(target_expiry)
            puts = chain.puts.copy()
            if puts.empty:
                return None

            # Find nearest real strike to suggested
            nearest_idx = (puts["strike"] - suggested_strike).abs().idxmin()
            row = puts.loc[nearest_idx]
            strike = float(row["strike"])
            bid = float(row.get("bid") or 0)
            ask = float(row.get("ask") or 0)
            last = float(row.get("lastPrice") or 0)
            mid = round((bid + ask) / 2, 2) if bid > 0 else last

            dte = (date.fromisoformat(target_expiry) - today).days
            return {
                "strike": strike,
                "expiry": target_expiry,
                "dte": dte,
                "mid_premium": mid,
                "bid": bid,
                "ask": ask,
                "volume": int(row.get("volume") or 0),
                "open_interest": int(row.get("openInterest") or 0),
            }
        except Exception as e:
            logger.debug("snap_put_strike failed for %s: %s", ticker, e)
            return None


    def get_call_tiers(self, ticker: str) -> dict | None:
        """
        Fetch call options chain for covered call income strategy.
        Returns three tiers: aggressive, balanced, conservative.
        Uses Polygon real-time data (with Greeks) when available; falls back to yfinance.
        """
        # Pre-fetch live price: Public → Finnhub → yfinance
        _live_price: float | None = None
        try:
            from services.public_client import get_last_price as _pub_price
            _live_price = _pub_price(ticker)
        except Exception:
            pass
        if not _live_price:
            try:
                from services.finnhub_client import get_quote
                q = get_quote(ticker)
                _live_price = float(q.get("c") or q.get("pc") or 0) or None
            except Exception:
                pass
        if not _live_price:
            try:
                fi = yf.Ticker(ticker).fast_info
                raw_last = float(fi.last_price or 0) or None
                prev_close = float(fi.previous_close or 0) or None
                if raw_last and prev_close and not (0.5 <= raw_last / prev_close <= 2.0):
                    logger.warning("Price sanity %s: last_price=%s vs prev_close=%s — using prev_close", ticker, raw_last, prev_close)
                    _live_price = prev_close
                else:
                    _live_price = raw_last or prev_close
            except Exception:
                pass

        # --- Polygon path (preferred) ---
        try:
            calls, price = self._polygon_options_chain(ticker, "call", 4, 30, near_price=_live_price)
            if not price:
                price = _live_price
            if calls and price:
                today = date.today()
                # Pick expiry closest to 14 DTE (weekly/bi-weekly sweet spot for covered calls)
                expiries = sorted(set(c["expiry"] for c in calls))
                target_expiry = min(expiries, key=lambda e: abs((date.fromisoformat(e) - today).days - 14))
                calls = [c for c in calls if c["expiry"] == target_expiry]
                if not calls:
                    raise ValueError("no calls for target expiry")
                dte = (date.fromisoformat(target_expiry) - today).days
                atm = min(calls, key=lambda c: abs(c["strike"] - price))
                atm_iv_pct = atm["iv_pct"]
                options_type = "weekly" if dte <= 14 else "monthly"
                weeks = dte / 7.0
                min_premium = round(price * 0.003 * weeks, 2)

                def _poly_call_tier(target_delta: float) -> dict | None:
                    sane = [c for c in calls if 0.8 * price <= c["strike"] <= 3.0 * price]
                    pool = sane if sane else calls
                    best = min(pool, key=lambda c: abs(c["delta"] - target_delta))
                    if abs(best["delta"] - target_delta) > 0.20:
                        return None
                    mid = best["mid"]
                    strike = best["strike"]
                    daily_income = round((best["theta_seller"] or 0) * 100, 2)
                    upside_pct = round((strike - price) / price * 100, 1)
                    pct_of_stock = round(mid / price * 100, 2) if mid > 0 else 0
                    return {
                        "strike": strike,
                        "expiry": target_expiry,
                        "dte": dte,
                        "bid": best["bid"],
                        "ask": best["ask"],
                        "mid_premium": mid,
                        "premium_per_contract": round(mid * 100, 2),
                        "iv_pct": best["iv_pct"],
                        "delta": round(best["delta"], 2),
                        "call_away_chance_pct": round(best["delta"] * 100),
                        "daily_income_per_contract": daily_income,
                        "upside_to_strike_pct": upside_pct,
                        "pct_of_stock_weekly": pct_of_stock,
                        "below_threshold": mid < min_premium,
                        "volume": best["volume"],
                        "open_interest": best["open_interest"],
                    }

                return {
                    "current_price": round(price, 2),
                    "expiry": target_expiry,
                    "dte": dte,
                    "options_type": options_type,
                    "atm_iv_pct": atm_iv_pct,
                    "data_source": "polygon_live",
                    "min_premium_threshold": min_premium,
                    "aggressive": _poly_call_tier(0.70),
                    "balanced": _poly_call_tier(0.45),
                    "conservative": _poly_call_tier(0.20),
                }
        except Exception as e:
            logger.debug("get_call_tiers Polygon path failed for %s: %s", ticker, e)

        # --- yfinance fallback ---
        if not _YF_AVAILABLE:
            return None
        try:
            t = yf.Ticker(ticker)
            expiries = t.options
            if not expiries:
                logger.warning("get_call_tiers: no options expiries for %s", ticker)
                return None

            today = date.today()
            # Prefer 4-30 DTE to catch both weeklies and monthlies (e.g. SCHD)
            target_expiry = None
            for exp in expiries:
                days = (date.fromisoformat(exp) - today).days
                if 4 <= days <= 30:
                    target_expiry = exp
                    break
            # Fallback: any future expiry up to 60 days
            if not target_expiry:
                for exp in expiries:
                    days = (date.fromisoformat(exp) - today).days
                    if 1 <= days <= 60:
                        target_expiry = exp
                        break
            # Last resort: nearest available
            if not target_expiry:
                for exp in expiries:
                    if (date.fromisoformat(exp) - today).days >= 1:
                        target_expiry = exp
                        break
            if not target_expiry:
                logger.warning("get_call_tiers: no suitable expiry for %s (expiries=%s)", ticker, expiries[:5])
                return None

            # Price: try fast_info first, then Finnhub, then t.info
            price = _live_price
            if not price:
                try:
                    price = getattr(t.fast_info, "last_price", None)
                except Exception:
                    pass
            if not price:
                try:
                    from services.finnhub_client import get_quote
                    q = get_quote(ticker)
                    price = float(q.get("c") or q.get("pc") or 0) or None
                except Exception:
                    pass
            if not price:
                logger.warning("get_call_tiers: could not get price for %s", ticker)
                return None

            chain = t.option_chain(target_expiry)
            calls = chain.calls.copy()
            if calls.empty:
                logger.warning("get_call_tiers: empty calls chain for %s exp=%s", ticker, target_expiry)
                return None

            exp_date = date.fromisoformat(target_expiry)
            T = max((exp_date - today).days, 1) / 365.0
            dte = (exp_date - today).days

            calls["_mid"] = calls.apply(
                lambda r: (
                    round((float(r.get("bid") or 0) + float(r.get("ask") or 0)) / 2, 2)
                    if float(r.get("bid") or 0) > 0
                    else float(r.get("lastPrice") or 0)
                ),
                axis=1,
            )
            calls["_is_live"] = calls["bid"].gt(0) if "bid" in calls.columns else False

            # Keep rows with a real mid price; fall back to any row with valid IV
            calls_with_mid = calls[calls["_mid"] > 0].copy()
            if not calls_with_mid.empty:
                calls = calls_with_mid
            elif "impliedVolatility" in calls.columns:
                calls = calls[calls["impliedVolatility"].fillna(0) > 0].copy()
            if calls.empty:
                logger.warning("get_call_tiers: no usable premium data for %s exp=%s", ticker, target_expiry)
                return None

            data_source = "live" if calls["_is_live"].any() else "last_trade"

            # If most rows have IV=0 (market closed / newly listed), fall back to HV then default
            mean_iv = calls["impliedVolatility"].fillna(0).mean() if "impliedVolatility" in calls.columns else 0
            if mean_iv < 0.01:
                hv = _historical_volatility(ticker)
                if hv:
                    logger.info("get_call_tiers: using HV=%.2f for %s (chain IV near zero)", hv, ticker)
                    calls["impliedVolatility"] = hv
                else:
                    logger.info("get_call_tiers: using default IV=0.30 for %s (HV unavailable)", ticker)
                    calls["impliedVolatility"] = 0.30

            calls["_delta"] = calls.apply(
                lambda r: _bs_call_delta(price, r["strike"], float(r.get("impliedVolatility") or 0), T),
                axis=1,
            )
            calls["_theta_daily"] = calls.apply(
                lambda r: _bs_call_theta_daily(price, r["strike"], float(r.get("impliedVolatility") or 0), T),
                axis=1,
            )
            calls = calls[calls["_delta"].notna()].copy()
            if calls.empty:
                logger.warning("get_call_tiers: no valid delta computed for %s", ticker)
                return None

            atm_idx = (calls["strike"] - price).abs().idxmin()
            atm_row = calls.loc[atm_idx]
            atm_iv_pct = round(float(atm_row.get("impliedVolatility") or 0) * 100, 1)

            # 0.3% of stock price per week — threshold for "meaningful" premium
            weeks = dte / 7.0
            min_premium = round(price * 0.003 * weeks, 2)
            # Weekly = ≤14 DTE; monthly = >14 DTE
            options_type = "weekly" if dte <= 14 else "monthly"

            def _best_near_delta(target: float) -> dict | None:
                if calls.empty:
                    return None
                sane = calls[(calls["strike"] >= price * 0.8) & (calls["strike"] <= price * 3.0)]
                pool = sane if not sane.empty else calls
                idx = (pool["_delta"] - target).abs().idxmin()
                row = pool.loc[idx]
                mid = float(row["_mid"])
                bid = float(row.get("bid") or 0)
                ask = float(row.get("ask") or 0)
                bid = bid if bid > 0 else mid
                ask = ask if ask > 0 else mid
                strike = float(row["strike"])
                iv_pct = round(float(row.get("impliedVolatility") or 0) * 100, 1)
                delta = round(float(row["_delta"]), 2)
                theta = row["_theta_daily"]
                daily_per_contract = round(float(theta) * 100, 2) if theta else None
                upside_pct = round((strike - price) / price * 100, 1)
                pct_of_stock = round(mid / price * 100, 2) if mid > 0 else 0
                return {
                    "strike": strike,
                    "expiry": target_expiry,
                    "dte": dte,
                    "bid": bid,
                    "ask": ask,
                    "mid_premium": mid,
                    "premium_per_contract": round(mid * 100, 2),
                    "iv_pct": iv_pct,
                    "delta": delta,
                    "call_away_chance_pct": round(delta * 100),
                    "daily_income_per_contract": daily_per_contract,
                    "upside_to_strike_pct": upside_pct,
                    "pct_of_stock_weekly": pct_of_stock,
                    "below_threshold": mid < min_premium,
                    "volume": int(row.get("volume") or 0),
                    "open_interest": int(row.get("openInterest") or 0),
                }

            return {
                "current_price": round(price, 2),
                "expiry": target_expiry,
                "dte": dte,
                "options_type": options_type,
                "atm_iv_pct": atm_iv_pct,
                "data_source": data_source,
                "min_premium_threshold": min_premium,
                "aggressive": _best_near_delta(0.70),
                "balanced": _best_near_delta(0.45),
                "conservative": _best_near_delta(0.20),
            }
        except Exception as e:
            logger.warning("get_call_tiers yfinance failed for %s: %s", ticker, e)

        # --- Synthetic Black-Scholes fallback ---
        # Runs when Polygon (no Options subscription) and yfinance (rate-limited on cloud) both fail.
        # Prices synthetic options using _historical_volatility (Polygon primary) and Black-Scholes.
        try:
            if not _live_price:
                return None
            price = _live_price

            hv: float = 0.30
            hv_computed = _historical_volatility(ticker)
            if hv_computed:
                hv = hv_computed

            from datetime import timedelta
            today = date.today()
            days_to_friday = (4 - today.weekday()) % 7
            if days_to_friday < 3:
                days_to_friday += 7
            target_expiry = (today + timedelta(days=days_to_friday)).isoformat()
            dte = days_to_friday
            T = max(dte, 1) / 365.0
            options_type = "weekly" if dte <= 14 else "monthly"
            min_premium = round(price * 0.003 * dte / 7.0, 2)

            rounding = 0.5 if price < 50 else (5.0 if price > 500 else 1.0)
            strikes = sorted(set(
                round(price * m / rounding) * rounding
                for m in [0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]
            ))

            r = 0.045
            synthetic_calls = []
            for strike in strikes:
                if strike <= 0:
                    continue
                delta = _bs_call_delta(price, strike, hv, T, r)
                theta = _bs_call_theta_daily(price, strike, hv, T, r)
                if delta is None:
                    continue
                sigma_sqrtT = hv * math.sqrt(T)
                d1 = (math.log(price / strike) + (r + 0.5 * hv ** 2) * T) / sigma_sqrtT
                d2 = d1 - sigma_sqrtT
                bs_price = round(max(price * _ncdf(d1) - strike * math.exp(-r * T) * _ncdf(d2), 0.01), 2)
                spread = round(max(bs_price * 0.10, 0.05), 2)
                synthetic_calls.append({
                    "strike": strike,
                    "mid": bs_price,
                    "bid": round(max(bs_price - spread / 2, 0.01), 2),
                    "ask": round(bs_price + spread / 2, 2),
                    "delta": delta,
                    "theta": theta,
                })

            if not synthetic_calls:
                return None

            atm_iv_pct = round(hv * 100, 1)

            def _synth_tier(target_delta: float) -> dict | None:
                best = min(synthetic_calls, key=lambda c: abs(c["delta"] - target_delta))
                mid = best["mid"]
                strike = best["strike"]
                delta_val = best["delta"]
                theta = best["theta"]
                daily_per_contract = round(float(theta) * 100, 2) if theta else None
                return {
                    "strike": strike,
                    "expiry": target_expiry,
                    "dte": dte,
                    "bid": best["bid"],
                    "ask": best["ask"],
                    "mid_premium": mid,
                    "premium_per_contract": round(mid * 100, 2),
                    "iv_pct": atm_iv_pct,
                    "delta": round(delta_val, 2),
                    "call_away_chance_pct": round(delta_val * 100),
                    "daily_income_per_contract": daily_per_contract,
                    "upside_to_strike_pct": round((strike - price) / price * 100, 1),
                    "pct_of_stock_weekly": round(mid / price * 100, 2),
                    "below_threshold": mid < min_premium,
                    "volume": 0,
                    "open_interest": 0,
                }

            logger.info("get_call_tiers synthetic BS for %s: price=%.2f hv=%.2f dte=%d", ticker, price, hv, dte)
            return {
                "current_price": round(price, 2),
                "expiry": target_expiry,
                "dte": dte,
                "options_type": options_type,
                "atm_iv_pct": atm_iv_pct,
                "data_source": "synthetic_bs",
                "min_premium_threshold": min_premium,
                "aggressive": _synth_tier(0.70),
                "balanced": _synth_tier(0.45),
                "conservative": _synth_tier(0.20),
            }
        except Exception as e:
            logger.warning("get_call_tiers synthetic BS failed for %s: %s", ticker, e)
            return None

    def get_chain_context(self, tickers: list[str]) -> dict:
        """
        For each ticker return a compact real-market options chain string.
        Used to give Claude actual bid/ask prices instead of BS estimates.
        """
        if not _YF_AVAILABLE:
            return {}
        result = {}
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                expiries = t.options
                if not expiries:
                    continue
                info = t.fast_info
                price = getattr(info, "last_price", None)
                if not price:
                    continue

                chain = t.option_chain(expiries[0])
                calls = chain.calls[chain.calls["bid"] > 0].copy()
                puts = chain.puts[chain.puts["bid"] > 0].copy()

                def _nearby(df, n_below=1, n_above=2):
                    if df.empty:
                        return df
                    atm_label = (df["strike"] - price).abs().idxmin()
                    atm_iloc = df.index.get_loc(atm_label)
                    return df.iloc[max(0, atm_iloc - n_below): atm_iloc + n_above + 1]

                call_rows = _nearby(calls, 0, 3)
                put_rows = _nearby(puts, 2, 1)

                def _fmt_row(row, suffix):
                    iv = round(float(row["impliedVolatility"]) * 100)
                    return f"{int(row['strike'])}{suffix} ${row['bid']:.2f}/${row['ask']:.2f} IV={iv}%"

                call_str = " | ".join(_fmt_row(r, "C") for _, r in call_rows.iterrows())
                put_str = " | ".join(_fmt_row(r, "P") for _, r in put_rows.iterrows())

                result[ticker] = {
                    "expiry": expiries[0],
                    "calls": call_str or "n/a",
                    "puts": put_str or "n/a",
                }
            except Exception as e:
                logger.debug("chain_context error for %s: %s", ticker, e)
        return result


# ---------------------------------------------------------------------------
# Convenience helper for watchlist / one-off scoring
# ---------------------------------------------------------------------------

def get_stock_info(ticker: str) -> dict:
    """Return a flat dict of price, technicals, and fundamentals for one ticker."""
    try:
        # OHLCV: Finnhub primary, Yahoo HTTP fallback
        df = _finnhub_history(ticker, "1y")
        if df.empty:
            df = _yf_fetch_ohlcv(ticker, period_days=252)
        price = float(df["Close"].iloc[-1]) if not df.empty else None
        indicators = _compute_all_indicators(df) if not df.empty else {}

        # Fundamentals + earnings: Finnhub primary
        summary: dict = {}
        earnings_date: str | None = None
        try:
            from services.finnhub_client import (
                get_basic_financials, get_company_profile, get_earnings_this_month
            )
            metrics = get_basic_financials(ticker)
            profile = get_company_profile(ticker)
            summary = {
                "pe_ratio": metrics.get("peNormalizedAnnual") or metrics.get("peTTM"),
                "div_yield": metrics.get("dividendYieldIndicatedAnnual"),
                "sector": profile.get("finnhubIndustry", ""),
                "analyst_rating": None,
                "52w_high": metrics.get("52WeekHigh"),
                "52w_low": metrics.get("52WeekLow"),
            }
            days_away = get_earnings_this_month(ticker)
            if days_away is not None:
                from datetime import date, timedelta
                earnings_date = (date.today() + timedelta(days=days_away)).isoformat()
        except Exception as e:
            logger.debug("Finnhub info error for %s: %s", ticker, e)
            summary = _yf_fetch_summary(ticker)

        return {
            "ticker": ticker,
            "price": round(price, 2) if price else None,
            "current_price": round(price, 2) if price else None,
            "rsi": indicators.get("rsi"),
            "ma50": indicators.get("moving_averages", {}).get("ma50"),
            "ma200": indicators.get("moving_averages", {}).get("ma200"),
            "pe_ratio": summary.get("pe_ratio"),
            "div_yield": summary.get("div_yield"),
            "sector": summary.get("sector"),
            "analyst_rating": summary.get("analyst_rating"),
            "52w_high": summary.get("52w_high"),
            "52w_low": summary.get("52w_low"),
            "earnings_date": earnings_date,
        }
    except Exception as e:
        logger.warning("get_stock_info failed for %s: %s", ticker, e)
        return {"ticker": ticker}
