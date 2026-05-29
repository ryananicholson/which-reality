import { useState, useEffect, useRef } from 'react'

const API = import.meta.env.VITE_API_URL || ''

function relativeTime(iso) {
  if (!iso) return null
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'less than 1 hour ago'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function fmtNotional(n) {
  if (!n) return null
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`
  return `$${n}`
}

function scoreColor(score) {
  if (score >= 5) return { bg: '#071a0a', border: '#276749', text: '#68d391' }
  if (score >= 3) return { bg: '#1a1400', border: '#b7791f', text: '#f6e05e' }
  return { bg: '#131825', border: '#2d3748', text: '#718096' }
}

function SignalPill({ label, score, maxScore, detail }) {
  const active = score > 0
  return (
    <div style={{
      padding: '8px 12px', borderRadius: '8px', fontSize: '12px',
      background: active ? '#0d2218' : '#1a1f2e',
      border: `1px solid ${active ? '#276749' : '#2d3748'}`,
      color: active ? '#68d391' : '#4a5568',
      minWidth: '120px', flex: '1',
    }}>
      <div style={{ fontWeight: 700, marginBottom: '2px' }}>
        {label} <span style={{ color: active ? '#48bb78' : '#4a5568' }}>{score}/{maxScore}</span>
      </div>
      {detail && <div style={{ fontSize: '11px', color: '#718096' }}>{detail}</div>}
    </div>
  )
}

function AlertCard({ alert, rank }) {
  const sc = scoreColor(alert.total_score)
  const signals = alert.signals || {}
  const optFlow = signals.options_flow || {}
  const insider = signals.insider_cluster || {}
  const drift = signals.pre_earnings_drift || {}

  const optDetail = (optFlow.unusual_contracts || 0) > 0
    ? `${optFlow.unusual_contracts} unusual contracts${optFlow.total_notional > 0 ? ' · ' + (fmtNotional(optFlow.total_notional) || '') : ''}`
    : 'no unusual flow detected'
  const insiderDetail = (insider.distinct_buyers || 0) > 0
    ? `${insider.distinct_buyers} buyer${insider.distinct_buyers > 1 ? 's' : ''} · net ${insider.net_change > 0 ? '+' : ''}${insider.net_change || 0} shares`
    : 'no cluster buys in 21d'
  const driftDetail = drift.days_to_earnings != null
    ? `${drift.days_to_earnings}d to earnings · α${drift.alpha != null ? (drift.alpha >= 0 ? '+' : '') + drift.alpha : '?'}% vs SPY`
    : 'no earnings in 14-42d window'

  return (
    <div style={{
      background: sc.bg, border: `1px solid ${sc.border}`,
      borderRadius: '12px', overflow: 'hidden',
    }}>
      <div style={{
        background: sc.bg, borderBottom: `1px solid ${sc.border}`,
        padding: '12px 16px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '13px', color: '#4a5568', fontWeight: 700 }}>#{rank}</span>
          <span style={{ fontSize: '22px', fontWeight: 900, color: '#e2e8f0' }}>{alert.ticker}</span>
          {alert.convergence && (
            <span style={{
              padding: '2px 8px', fontSize: '10px', fontWeight: 800, borderRadius: '20px',
              background: 'rgba(104,211,145,0.15)', border: '1px solid #276749', color: '#68d391',
              letterSpacing: '0.05em',
            }}>
              CONVERGING
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {alert.price > 0 && <span style={{ fontSize: '13px', color: '#a0aec0' }}>${alert.price}</span>}
          <span style={{
            padding: '4px 12px', borderRadius: '20px', fontSize: '14px', fontWeight: 800,
            background: sc.bg, border: `1px solid ${sc.border}`, color: sc.text,
          }}>
            {alert.total_score}/6
          </span>
        </div>
      </div>

      <div style={{ padding: '14px 16px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <SignalPill label="Options Flow" score={optFlow.score || 0} maxScore={2} detail={optDetail} />
        <SignalPill label="Insider Cluster" score={insider.score || 0} maxScore={2} detail={insiderDetail} />
        <SignalPill label="Pre-Earnings Drift" score={drift.score || 0} maxScore={2} detail={driftDetail} />
      </div>
    </div>
  )
}

export default function MomentumTab() {
  const [data, setData] = useState(null)
  const [status, setStatus] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const pollRef = useRef(null)

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  const fetchResults = async () => {
    try {
      const resp = await fetch(`${API}/api/momentum/alerts`)
      if (!resp.ok) return
      const body = await resp.json().catch(() => ({}))
      if (body.scanning) {
        startPolling()
      } else {
        setData(body)
        stopPolling()
      }
    } catch (e) {
      console.error('Momentum fetch error', e)
    }
  }

  const fetchStatus = async () => {
    try {
      const resp = await fetch(`${API}/api/momentum/status`)
      if (!resp.ok) return
      const body = await resp.json().catch(() => ({}))
      setStatus(body)
      if (body.status === 'complete') {
        stopPolling()
        fetchResults()
      } else if (body.status === 'error') {
        stopPolling()
      }
    } catch {}
  }

  const startPolling = () => {
    if (pollRef.current) return
    pollRef.current = setInterval(fetchStatus, 3000)
  }

  useEffect(() => {
    fetchResults()
    fetchStatus()
    return () => stopPolling()
  }, []) // eslint-disable-line

  const handleRefresh = async () => {
    setRefreshing(true)
    setData(null)
    try {
      await fetch(`${API}/api/momentum/refresh`, { method: 'POST' })
      startPolling()
    } catch {}
    setRefreshing(false)
  }

  const isRunning = status?.status === 'running'
  const phase = status?.phase || ''
  const phasePct = isRunning ? (
    phase === 'stage1_price_volume' ? 15 :
    phase === 'scoring' ? Math.round(15 + ((status?.current || 0) / Math.max(status?.total || 1, 1)) * 80) :
    95
  ) : 0

  const phaseLabel = (
    phase === 'init' ? 'Initializing…' :
    phase === 'stage1_price_volume' ? 'Stage 1 · Price & volume filter…' :
    phase === 'scoring' ? `Scoring signals… ${status?.current_ticker ? `· ${status.current_ticker}` : ''} (${status?.current || 0}/${status?.total || '?'})` :
    phase === 'done' ? 'Complete' :
    phase || ''
  )

  const alerts = data?.alerts || []

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', color: '#e2e8f0' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#f6ad55', margin: '0 0 4px' }}>
            ⚡ Momentum Alerts
          </h2>
          <p style={{ fontSize: '13px', color: '#718096', margin: 0 }}>
            S&P 500 + Nasdaq 100 · unusual options flow · insider cluster buys · pre-earnings drift
          </p>
          {data?.scanned_at && (
            <div style={{ fontSize: '11px', color: '#4a5568', marginTop: '4px' }}>
              Last scan: {relativeTime(data.scanned_at)}
              {data.universe_count != null && ` · ${data.universe_count} tickers → ${data.stage1_survivors} screened → ${data.total_scored} scored`}
            </div>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRunning || refreshing}
          style={{
            padding: '7px 16px',
            background: isRunning || refreshing ? '#2d3748' : '#3a1a00',
            color: isRunning || refreshing ? '#718096' : '#f6ad55',
            border: `1px solid ${isRunning || refreshing ? '#2d3748' : '#b7791f'}`,
            borderRadius: '7px', cursor: isRunning || refreshing ? 'not-allowed' : 'pointer',
            fontSize: '12px', fontWeight: 600,
          }}
        >
          {isRunning ? '⟳ Scanning…' : '⟳ Refresh Scan'}
        </button>
      </div>

      {/* Progress bar */}
      {isRunning && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '12px', color: '#fbd38d', marginBottom: '6px' }}>{phaseLabel}</div>
          <div style={{ height: '6px', background: '#1a1f2e', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{
              width: `${phasePct}%`, height: '100%',
              background: 'linear-gradient(90deg, #b7791f, #f6ad55)',
              borderRadius: '3px', transition: 'width 0.5s ease',
            }} />
          </div>
        </div>
      )}

      {/* Error */}
      {status?.status === 'error' && (
        <div style={{ color: '#fc8181', padding: '12px 16px', background: '#2d1515', border: '1px solid #742a2a', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
          Scan error: {status.error}
        </div>
      )}

      {/* No data yet */}
      {!data && !isRunning && status?.status !== 'error' && (
        <div style={{ background: '#131825', border: '1px solid #2d3748', borderRadius: '12px', padding: '48px', textAlign: 'center', color: '#718096', fontSize: '14px' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚡</div>
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>No scan results yet</div>
          <div style={{ fontSize: '13px', marginBottom: '16px' }}>
            Click <strong style={{ color: '#f6ad55' }}>Refresh Scan</strong> to find stocks with converging signals.
          </div>
          <button
            onClick={handleRefresh}
            style={{ padding: '8px 20px', background: '#3a1a00', color: '#f6ad55', border: '1px solid #b7791f', borderRadius: '7px', cursor: 'pointer', fontWeight: 600 }}
          >
            Run Scan Now
          </button>
        </div>
      )}

      {/* Results */}
      {alerts.length > 0 && (
        <>
          <div style={{ fontSize: '13px', color: '#a0aec0', marginBottom: '12px' }}>
            Top {alerts.length} convergence candidates · Threshold: 3/6 signals · sorted by score
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {alerts.map((alert, i) => (
              <AlertCard key={alert.ticker} alert={alert} rank={i + 1} />
            ))}
          </div>
          <div style={{ fontSize: '11px', color: '#4a5568', marginTop: '16px', lineHeight: '1.5' }}>
            Signal convergence ≠ guaranteed direction. Options flow, insider buying, and pre-earnings drift are indicators only. Not financial advice.
          </div>
        </>
      )}

      {/* Empty results state */}
      {alerts.length === 0 && data && !isRunning && (
        <div style={{ background: '#131825', border: '1px solid #2d3748', borderRadius: '12px', padding: '40px', textAlign: 'center', color: '#718096', fontSize: '14px' }}>
          <div style={{ fontWeight: 600, marginBottom: '8px' }}>No convergence alerts this scan</div>
          <div style={{ fontSize: '12px', color: '#4a5568' }}>
            No stocks reached the 3-signal threshold. Try again after market hours when insider data updates.
          </div>
        </div>
      )}
    </div>
  )
}
