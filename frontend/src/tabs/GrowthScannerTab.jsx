import { useState, useEffect, useRef, useCallback } from 'react'

const API = (path) => `/api/advanced-scanner${path}`

// ─── Helpers ────────────────────────────────────────────────────────────────

function fmt(n, decimals = 1) {
  if (n == null) return '—'
  return Number(n).toFixed(decimals)
}

function fmtPct(n, decimals = 1, showPlus = false) {
  if (n == null) return '—'
  const s = Number(n).toFixed(decimals)
  return showPlus && n > 0 ? `+${s}%` : `${s}%`
}

function maLabel(above, crossover) {
  if (crossover) return { text: '↑ MA cross', color: '#68d391', bg: '#1a3a2a' }
  if (above)     return { text: '▲ Above MA', color: '#90cdf4', bg: '#1a2a3a' }
  return           { text: '▼ Below MA', color: '#fc8181', bg: '#3a1a1a' }
}

function actionColor(action) {
  if (!action) return '#718096'
  if (action === 'STRONG BUY') return '#68d391'
  if (action === 'SMALL BUY')  return '#90cdf4'
  if (action === 'WATCH')      return '#f6e05e'
  if (action === 'BLOCKED')    return '#fc8181'
  return '#718096'
}

function relativeTime(iso) {
  if (!iso) return null
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'less than 1 hour ago'
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

// ─── Styles ─────────────────────────────────────────────────────────────────

const s = {
  root: { fontFamily: 'system-ui, sans-serif', color: '#e2e8f0' },
  header: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' },
  title: { fontSize: '20px', fontWeight: 700, color: '#63b3ed', margin: 0 },
  modeBar: { display: 'flex', gap: '8px', marginLeft: 'auto', flexWrap: 'wrap' },
  modeBtn: (active) => ({
    padding: '7px 16px', borderRadius: '6px', border: 'none', cursor: 'pointer',
    fontSize: '13px', fontWeight: 600,
    background: active ? '#2b6cb0' : '#2d3748',
    color: active ? '#fff' : '#a0aec0',
  }),
  refreshBtn: {
    padding: '7px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer',
    fontSize: '13px', background: '#276749', color: '#9ae6b4', fontWeight: 600,
  },
  meta: { fontSize: '12px', color: '#718096', marginBottom: '16px' },
  progressWrap: { background: '#1a202c', borderRadius: '8px', padding: '20px', marginBottom: '20px' },
  progressLabel: { fontSize: '13px', color: '#90cdf4', marginBottom: '10px' },
  barOuter: { background: '#2d3748', borderRadius: '4px', height: '8px', overflow: 'hidden' },
  barInner: (pct) => ({
    height: '8px', borderRadius: '4px',
    background: 'linear-gradient(90deg, #2b6cb0, #63b3ed)',
    width: `${Math.min(pct, 100)}%`,
    transition: 'width 0.4s ease',
  }),
  emptyBox: { background: '#1a202c', borderRadius: '8px', padding: '40px', textAlign: 'center', color: '#718096' },
  grid: { display: 'flex', flexDirection: 'column', gap: '14px' },
  card: {
    background: '#1a202c', borderRadius: '10px', padding: '18px',
    border: '1px solid #2d3748',
  },
  cardHeader: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px', flexWrap: 'wrap' },
  rank: { fontSize: '16px', fontWeight: 700, color: '#718096', minWidth: '28px' },
  ticker: { fontSize: '18px', fontWeight: 700, color: '#e2e8f0' },
  name: { fontSize: '13px', color: '#718096', flex: 1 },
  scoreBadge: (score) => ({
    padding: '3px 10px', borderRadius: '12px', fontSize: '13px', fontWeight: 700,
    background: score >= 7 ? '#1a3a2a' : score >= 5 ? '#1a2a3a' : '#2d3748',
    color: score >= 7 ? '#68d391' : score >= 5 ? '#90cdf4' : '#a0aec0',
    border: `1px solid ${score >= 7 ? '#276749' : score >= 5 ? '#2b6cb0' : '#4a5568'}`,
  }),
  actionBadge: (action) => ({
    padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 700,
    color: actionColor(action), background: '#2d3748', border: `1px solid ${actionColor(action)}44`,
  }),
  metrics: { display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '10px' },
  pill: (color = '#2d3748', textColor = '#a0aec0') => ({
    padding: '4px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: 600,
    background: color, color: textColor,
  }),
  speculativeTag: {
    padding: '3px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 700,
    background: '#3a1a1a', color: '#fc8181', border: '1px solid #fc818144',
    marginLeft: 'auto',
  },
  watchlistBtn: {
    padding: '5px 12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
    fontSize: '12px', fontWeight: 600, background: '#744210', color: '#fbd38d',
  },
  inWatchlist: {
    padding: '5px 12px', borderRadius: '6px', border: 'none',
    fontSize: '12px', fontWeight: 600, background: '#1a3a2a', color: '#68d391',
  },
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function ProgressBar({ status, mode }) {
  if (!status?.running) return null
  const phase = status.phase || ''
  const pct = status.total > 0 ? Math.round((status.current / status.total) * 100) : 0

  const phaseLabel = {
    prefetch: 'Pre-filtering stocks (Finnhub fundamentals)…',
    fundamental_filter: 'Applying fundamental filters…',
    polygon_filter: 'Running Polygon volume screen…',
    deep_analysis: 'Deep analysis — Monte Carlo DCF + MA + earnings…',
    done: 'Complete',
  }[phase] || `Scanning… (${phase})`

  return (
    <div style={s.progressWrap}>
      <div style={s.progressLabel}>
        {phaseLabel}
        {status.total > 0 && ` (${status.current} / ${status.total})`}
      </div>
      <div style={s.barOuter}>
        <div style={s.barInner(status.total > 0 ? pct : 30)} />
      </div>
    </div>
  )
}

function ResultCard({ result, rank, mode, onAddWatchlist, inWatchlist }) {
  const score = result.trigger_score ?? 0
  const action = result.trigger_action
  const ma = maLabel(result.above_ma, result.crossover_5d)
  const baseUp = result.dcf_base_upside
  const bearUp = result.dcf_bear_upside

  return (
    <div style={s.card}>
      <div style={s.cardHeader}>
        <span style={s.rank}>#{rank}</span>
        <span style={s.ticker}>{result.ticker}</span>
        <span style={s.name}>{result.name || ''}</span>
        <span style={s.scoreBadge(score)}>{score}/8</span>
        <span style={s.actionBadge(action)}>{action}</span>
        {mode === 'movers' && <span style={s.speculativeTag}>⚠ SPECULATIVE</span>}
      </div>

      <div style={s.metrics}>
        {/* Mode-specific primary metric */}
        {mode === 'dividend' && result.dividend_yield_pct != null && (
          <span style={s.pill('#1a2a1a', '#9ae6b4')}>
            Yield {fmt(result.dividend_yield_pct)}%
          </span>
        )}
        {mode === 'movers' && result.revenue_growth_display != null && (
          <span style={s.pill('#1a2035', '#90cdf4')}>
            Rev growth {fmtPct(result.revenue_growth_display, 1, true)}
          </span>
        )}

        {/* Base / Bear */}
        <span style={s.pill(baseUp > 20 ? '#1a2a3a' : '#2d3748', baseUp > 20 ? '#90cdf4' : '#a0aec0')}>
          Base {fmtPct(baseUp, 0, true)}
        </span>
        <span style={s.pill(bearUp != null && bearUp > -30 ? '#1a3a2a' : '#3a1a1a',
                             bearUp != null && bearUp > -30 ? '#68d391' : '#fc8181')}>
          Bear {fmtPct(bearUp, 0, true)}
        </span>

        {/* MA status */}
        <span style={s.pill(ma.bg, ma.color)}>{ma.text}</span>

        {/* Earnings */}
        {result.earnings_days != null && (
          <span style={s.pill(result.earnings_days <= 14 ? '#3a1a1a' : '#2d3748',
                               result.earnings_days <= 14 ? '#fc8181' : '#718096')}>
            Earnings {result.earnings_days}d
          </span>
        )}

        {/* MC probability */}
        {result.monte_carlo?.prob_undervalued_pct != null && (
          <span style={s.pill('#2d2040', '#c084fc')}>
            MC {fmt(result.monte_carlo.prob_undervalued_pct)}%
          </span>
        )}
      </div>

      {/* Speculative warning */}
      {mode === 'movers' && (
        <div style={{ fontSize: '11px', color: '#fc8181', marginBottom: '8px' }}>
          HIGH RISK — speculative growth play. Size position accordingly.
        </div>
      )}

      {/* Watchlist button */}
      {inWatchlist ? (
        <span style={s.inWatchlist}>✓ In watchlist</span>
      ) : (
        <button style={s.watchlistBtn} onClick={() => onAddWatchlist(result)}>
          + Add to Watchlist
        </button>
      )}
    </div>
  )
}

// ─── Main Tab ────────────────────────────────────────────────────────────────

export default function GrowthScannerTab() {
  const [mode, setMode] = useState('dividend')
  const [data, setData] = useState({ dividend: null, movers: null })
  const [loading, setLoading] = useState({ dividend: false, movers: false })
  const [scanStatus, setScanStatus] = useState({ dividend: null, movers: null })
  const [watchlist, setWatchlist] = useState(() => {
    try { return JSON.parse(localStorage.getItem('trigger_watchlist') || '[]') }
    catch { return [] }
  })
  const pollRef = useRef(null)

  // ── Poll progress while scan is running ──────────────────────────────────
  const startPolling = useCallback((m) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(API(`/status/${m}`))
        if (!res.ok) return
        const status = await res.json()
        setScanStatus(prev => ({ ...prev, [m]: status }))
        if (!status.running) {
          clearInterval(pollRef.current)
          pollRef.current = null
          fetchResults(m)
        }
      } catch { /* ignore */ }
    }, 2000)
  }, [])

  // ── Fetch results for a mode ─────────────────────────────────────────────
  const fetchResults = useCallback(async (m) => {
    setLoading(prev => ({ ...prev, [m]: true }))
    try {
      const res = await fetch(API(`/${m}`))
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(prev => ({ ...prev, [m]: json }))
      if (json.scanning) {
        startPolling(m)
      }
    } catch (e) {
      console.error('fetch results error', e)
    } finally {
      setLoading(prev => ({ ...prev, [m]: false }))
    }
  }, [startPolling])

  // ── Load on mode change ───────────────────────────────────────────────────
  useEffect(() => {
    if (!data[mode]) {
      fetchResults(mode)
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [mode])

  // ── Refresh (force rescan) ────────────────────────────────────────────────
  const handleRefresh = async () => {
    try {
      await fetch(API(`/refresh/${mode}`), { method: 'POST' })
      setData(prev => ({ ...prev, [mode]: null }))
      setScanStatus(prev => ({ ...prev, [mode]: { running: true } }))
      startPolling(mode)
    } catch (e) {
      console.error('refresh error', e)
    }
  }

  // ── Watchlist ─────────────────────────────────────────────────────────────
  const addToWatchlist = (r) => {
    const item = {
      ticker: r.ticker,
      scoreAtAdd: r.trigger_score,
      actionAtAdd: r.trigger_action,
      addedAt: new Date().toISOString(),
      currentScore: r.trigger_score,
      currentAction: r.trigger_action,
      lastChecked: new Date().toISOString(),
    }
    const next = [...watchlist.filter(w => w.ticker !== r.ticker), item]
    setWatchlist(next)
    localStorage.setItem('trigger_watchlist', JSON.stringify(next))
  }

  const isInWatchlist = (ticker) => watchlist.some(w => w.ticker === ticker)

  // ── Render ────────────────────────────────────────────────────────────────
  const current = data[mode]
  const isScanning = loading[mode] || scanStatus[mode]?.running || current?.scanning
  const status = scanStatus[mode]

  const modeLabel = { dividend: 'Dividend Income', movers: 'Big Movers' }
  const modeDesc = {
    dividend: 'High-yield dividend growers with confirmed upside (Nasdaq Dividend Achievers universe)',
    movers: 'High-growth companies trading well below 52-week highs (S&P 500 + Nasdaq 100)',
  }

  return (
    <div style={s.root}>
      <div style={s.header}>
        <h2 style={s.title}>Growth Scanner</h2>
        <div style={s.modeBar}>
          <button style={s.modeBtn(mode === 'dividend')} onClick={() => setMode('dividend')}>
            💰 Dividend Income
          </button>
          <button style={s.modeBtn(mode === 'movers')} onClick={() => setMode('movers')}>
            🚀 Big Movers
          </button>
          <button style={s.refreshBtn} onClick={handleRefresh} disabled={isScanning}>
            {isScanning ? '⏳ Scanning…' : '↺ Refresh'}
          </button>
        </div>
      </div>

      <div style={s.meta}>
        {modeDesc[mode]}
        {current?.scanned_at && (
          <span style={{ marginLeft: '8px', color: '#4a5568' }}>
            · Last scan: {relativeTime(current.scanned_at)}
            {current.universe_size != null && ` · ${current.universe_size} stocks screened`}
            {current.survivors != null && ` · ${current.survivors} passed filters`}
          </span>
        )}
      </div>

      <ProgressBar status={status} mode={mode} />

      {isScanning && !status?.running && (
        <div style={s.progressWrap}>
          <div style={s.progressLabel}>Connecting to scanner…</div>
          <div style={s.barOuter}><div style={s.barInner(20)} /></div>
        </div>
      )}

      {!isScanning && current && current.results?.length === 0 && (
        <div style={s.emptyBox}>
          <div style={{ fontSize: '32px', marginBottom: '8px' }}>🔍</div>
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>No results this scan</div>
          <div style={{ fontSize: '13px', marginBottom: current.rejection_stats ? '10px' : '0' }}>
            {current.survivors === 0
              ? `All ${current.fundamentals_fetched ?? current.universe_size} stocks failed fundamental pre-filter.`
              : `${current.survivors} stocks passed pre-filter but none had sufficient trigger scores.`}
          </div>
          {current.rejection_stats && (
            <div style={{ fontSize: '11px', color: '#4a5568', textAlign: 'left', display: 'inline-block' }}>
              {Object.entries(current.rejection_stats)
                .filter(([, v]) => v > 0)
                .map(([k, v]) => `${k}: ${v}`)
                .join(' · ')}
            </div>
          )}
        </div>
      )}

      {!isScanning && current?.results?.length > 0 && (
        <>
          <div style={{ fontSize: '13px', color: '#a0aec0', marginBottom: '12px' }}>
            Top {current.results.length} {modeLabel[mode]} picks
            {mode === 'dividend' && ' · Ranked by trigger score'}
            {mode === 'movers' && ' · Ranked by Monte Carlo × base upside'}
          </div>
          <div style={s.grid}>
            {current.results.map((r, i) => (
              <ResultCard
                key={r.ticker}
                result={r}
                rank={i + 1}
                mode={mode}
                onAddWatchlist={addToWatchlist}
                inWatchlist={isInWatchlist(r.ticker)}
              />
            ))}
          </div>
        </>
      )}

      {!isScanning && !current && (
        <div style={s.emptyBox}>
          <div style={{ fontSize: '32px', marginBottom: '8px' }}>📊</div>
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>No cached results</div>
          <div style={{ fontSize: '13px', marginBottom: '12px' }}>
            Hit Refresh to run a fresh scan (~5–8 min). Scans also run automatically at 6 AM on trading days.
          </div>
          <button style={s.refreshBtn} onClick={handleRefresh}>Run Scan Now</button>
        </div>
      )}
    </div>
  )
}
