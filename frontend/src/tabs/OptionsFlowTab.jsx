import { useState } from 'react'
import { api } from '../api'

const CONF_COLORS = {
  high:   { bg: '#071a0a', border: '#276749', text: '#68d391' },
  medium: { bg: '#1a1400', border: '#b7791f', text: '#f6e05e' },
  low:    { bg: '#131825', border: '#2d3748', text: '#718096' },
}

const VERDICT_CONFIG = {
  PROCEED: { bg: '#0a2218', border: '#276749', text: '#68d391', icon: '✅', label: 'PROCEED' },
  CAUTION: { bg: '#2d2000', border: '#b7791f', text: '#fbd38d', icon: '⚠️', label: 'CAUTION' },
  AVOID:   { bg: '#2d1515', border: '#742a2a', text: '#fc8181', icon: '🚫', label: 'AVOID'   },
}

function fmt(n) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`
  return `$${n}`
}

const s = {
  header: { marginBottom: '20px' },
  title: { fontSize: '20px', fontWeight: 700, color: '#e2e8f0', marginBottom: '4px' },
  subtitle: { fontSize: '13px', color: '#718096' },

  sentimentBar: {
    display: 'flex', alignItems: 'center', gap: '12px',
    marginBottom: '16px', flexWrap: 'wrap',
  },
  sentimentBadge: (sentiment) => ({
    padding: '5px 16px', fontSize: '12px', fontWeight: 700, borderRadius: '20px',
    background: sentiment === 'bullish' ? '#071a0a' : sentiment === 'bearish' ? '#1f0a0a' : '#131825',
    border: `1px solid ${sentiment === 'bullish' ? '#276749' : sentiment === 'bearish' ? '#742a2a' : '#2d3748'}`,
    color: sentiment === 'bullish' ? '#68d391' : sentiment === 'bearish' ? '#fc8181' : '#718096',
  }),
  ratio: { fontSize: '12px', color: '#718096' },

  toolbar: {
    display: 'flex', alignItems: 'center', gap: '12px',
    marginBottom: '20px', flexWrap: 'wrap',
  },
  scanBtn: (loading) => ({
    padding: '10px 24px',
    background: loading ? '#2d3748' : '#553c9a',
    color: loading ? '#718096' : '#fff',
    border: 'none', borderRadius: '8px',
    cursor: loading ? 'not-allowed' : 'pointer',
    fontSize: '14px', fontWeight: 700,
  }),
  note: { fontSize: '11px', color: '#4a5568', fontStyle: 'italic' },
  scannedNote: { fontSize: '12px', color: '#718096' },
  error: {
    color: '#fc8181', background: '#2d1515', border: '1px solid #742a2a',
    borderRadius: '8px', padding: '14px 16px', fontSize: '14px', marginBottom: '20px',
  },
  emptyState: {
    background: '#131825', border: '1px solid #2d3748', borderRadius: '12px',
    padding: '48px', textAlign: 'center', color: '#718096', fontSize: '14px',
  },

  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
    gap: '16px',
  },

  card: (sentiment) => ({
    background: sentiment === 'bullish' ? '#071a0a' : '#1f0a0a',
    border: `1px solid ${sentiment === 'bullish' ? '#276749' : '#742a2a'}`,
    borderRadius: '12px', overflow: 'hidden',
  }),
  cardHeader: (sentiment) => ({
    background: sentiment === 'bullish' ? '#0d2218' : '#2d1515',
    borderBottom: `1px solid ${sentiment === 'bullish' ? '#276749' : '#742a2a'}`,
    padding: '12px 16px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px',
  }),
  tickerRow: { display: 'flex', alignItems: 'center', gap: '10px' },
  ticker: { fontSize: '22px', fontWeight: 900, color: '#e2e8f0' },
  dirBadge: (sentiment) => ({
    padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '20px',
    background: sentiment === 'bullish' ? 'rgba(104,211,145,0.15)' : 'rgba(252,129,129,0.15)',
    border: `1px solid ${sentiment === 'bullish' ? '#276749' : '#742a2a'}`,
    color: sentiment === 'bullish' ? '#68d391' : '#fc8181',
  }),
  price: { fontSize: '13px', color: '#a0aec0' },

  cardBody: { padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: '10px' },

  contractRow: {
    display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center',
  },
  contractBadge: (sentiment) => ({
    padding: '4px 12px', fontSize: '12px', fontWeight: 700, borderRadius: '6px',
    background: 'rgba(0,0,0,0.3)',
    color: sentiment === 'bullish' ? '#68d391' : '#fc8181',
  }),
  dteBadge: {
    padding: '4px 10px', fontSize: '11px', fontWeight: 600, borderRadius: '6px',
    background: 'rgba(0,0,0,0.3)', color: '#a0aec0',
  },
  otmBadge: {
    padding: '4px 10px', fontSize: '11px', fontWeight: 600, borderRadius: '6px',
    background: 'rgba(0,0,0,0.3)', color: '#718096',
  },

  statsRow: {
    display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px',
  },
  stat: {
    background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '7px 10px',
  },
  statLabel: {
    fontSize: '10px', color: '#718096', textTransform: 'uppercase',
    letterSpacing: '0.05em', fontWeight: 600,
  },
  statValue: { fontSize: '14px', fontWeight: 700, color: '#e2e8f0', marginTop: '2px' },

  notionalBig: (sentiment) => ({
    fontSize: '22px', fontWeight: 900,
    color: sentiment === 'bullish' ? '#68d391' : '#fc8181',
  }),

  interpretation: {
    fontSize: '13px', color: '#a0aec0', lineHeight: 1.6,
    background: 'rgba(0,0,0,0.2)', borderRadius: '6px', padding: '10px 12px',
  },
  impliedTarget: (sentiment) => ({
    fontSize: '12px', fontWeight: 700, borderRadius: '6px', padding: '6px 10px',
    background: sentiment === 'bullish' ? 'rgba(104,211,145,0.08)' : 'rgba(252,129,129,0.08)',
    border: `1px solid ${sentiment === 'bullish' ? 'rgba(39,103,73,0.5)' : 'rgba(116,42,42,0.5)'}`,
    color: sentiment === 'bullish' ? '#68d391' : '#fc8181',
  }),
  actionNote: {
    fontSize: '12px', color: '#90cdf4', lineHeight: 1.5,
    background: 'rgba(43,108,176,0.08)',
    border: '1px solid rgba(43,108,176,0.2)',
    borderRadius: '6px', padding: '8px 10px',
  },

  recommendation: (rec) => {
    const isBuy = typeof rec === 'string' && rec.toUpperCase().startsWith('BUY')
    return {
      fontSize: '12px', fontWeight: 600, lineHeight: 1.5,
      background: isBuy ? 'rgba(104,211,145,0.06)' : 'rgba(252,129,129,0.06)',
      border: `1px solid ${isBuy ? 'rgba(39,103,73,0.4)' : 'rgba(116,42,42,0.4)'}`,
      color: isBuy ? '#68d391' : '#fc8181',
      borderRadius: '6px', padding: '8px 10px',
    }
  },

  premiumRow: {
    display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center',
  },
  premiumBadge: (rating) => ({
    padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '6px',
    background: rating === 'RICH' ? 'rgba(252,129,129,0.12)'
              : rating === 'CHEAP' ? 'rgba(104,211,145,0.12)'
              : 'rgba(160,174,192,0.1)',
    border: `1px solid ${rating === 'RICH' ? 'rgba(116,42,42,0.5)'
           : rating === 'CHEAP' ? 'rgba(39,103,73,0.5)'
           : 'rgba(74,85,104,0.5)'}`,
    color: rating === 'RICH' ? '#fc8181'
         : rating === 'CHEAP' ? '#68d391'
         : '#a0aec0',
  }),
  premiumMeta: {
    fontSize: '11px', color: '#718096',
  },

  disclaimer: { fontSize: '11px', color: '#4a5568', marginTop: '16px' },
}

function FlowCard({ alert }) {
  const sent = alert.sentiment || 'bullish'
  const conf = (alert.confidence || 'medium').toLowerCase()
  const confColors = CONF_COLORS[conf] ?? CONF_COLORS.medium
  const pct_otm = alert.pct_otm ?? 0
  const otmLabel = pct_otm >= 0 ? `${pct_otm}% OTM` : `${Math.abs(pct_otm)}% ITM`
  const volOiRatio = alert.vol_oi_ratio ?? 0
  const volOiLabel = alert.is_new_contract ? 'NEW ✦' : `${volOiRatio}×`
  const volOiColor = alert.is_new_contract ? '#b794f4' : volOiRatio >= 10 ? '#f6e05e' : '#e2e8f0'

  return (
    <div style={s.card(sent)}>
      <div style={s.cardHeader(sent)}>
        <div style={s.tickerRow}>
          <span style={s.ticker}>{alert.ticker || '—'}</span>
          <span style={s.dirBadge(sent)}>
            {sent === 'bullish' ? '▲ CALLS' : '▼ PUTS'}
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
          <span style={s.price}>${alert.price ?? '—'}</span>
          <span style={{
            padding: '2px 8px', fontSize: '10px', fontWeight: 700, borderRadius: '20px',
            background: confColors.bg, border: `1px solid ${confColors.border}`, color: confColors.text,
          }}>
            {conf.toUpperCase()}
          </span>
        </div>
      </div>

      <div style={s.cardBody}>
        {/* Verdict banner */}
        {alert.verdict && (() => {
          const vc = VERDICT_CONFIG[alert.verdict] ?? VERDICT_CONFIG.CAUTION
          return (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '10px 14px',
              background: vc.bg, border: `1px solid ${vc.border}`,
              borderRadius: '8px',
            }}>
              <span style={{ fontSize: '20px', lineHeight: 1 }}>{vc.icon}</span>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 800, color: vc.text, letterSpacing: '0.05em' }}>
                  {vc.label}
                </div>
                {alert.verdict_reason && (
                  <div style={{ fontSize: '12px', color: vc.text, opacity: 0.8, marginTop: '1px' }}>
                    {alert.verdict_reason}
                  </div>
                )}
              </div>
            </div>
          )
        })()}

        {/* Catalyst section: price move + earnings + news */}
        {(alert.change_pct != null || alert.earnings_context || (alert.news && alert.news.length > 0)) && (
          <div style={{
            background: 'rgba(0,0,0,0.25)', borderRadius: '8px', padding: '8px 10px',
            display: 'flex', flexDirection: 'column', gap: '5px',
          }}>
            {/* Price move today */}
            {alert.change_pct != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '11px', color: '#718096' }}>Today</span>
                <span style={{
                  fontSize: '12px', fontWeight: 700,
                  color: alert.change_pct >= 0 ? '#68d391' : '#fc8181',
                }}>
                  {alert.change_pct >= 0 ? '▲' : '▼'} {Math.abs(alert.change_pct)}%
                </span>
              </div>
            )}
            {/* Earnings */}
            {alert.earnings_context && (
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#f6e05e' }}>
                📅 {alert.earnings_context}
              </div>
            )}
            {/* News headlines */}
            {alert.news && alert.news.slice(0, 2).map((headline, i) => (
              <div key={i} style={{
                fontSize: '11px', color: '#a0aec0', lineHeight: 1.4,
                borderLeft: '2px solid #4a5568', paddingLeft: '6px',
              }}>
                {headline}
              </div>
            ))}
          </div>
        )}

        {/* Contract details */}
        <div style={s.contractRow}>
          <span style={s.contractBadge(sent)}>
            ${alert.strike ?? '—'} {(alert.option_type || 'call').toUpperCase()} {alert.expiry ?? '—'}
          </span>
          <span style={s.dteBadge}>{alert.dte ?? '—'}d to exp</span>
          <span style={s.otmBadge}>{otmLabel}</span>
        </div>

        {/* Key metrics */}
        <div style={s.statsRow}>
          <div style={s.stat}>
            <div style={s.statLabel}>Notional</div>
            <div style={{ ...s.statValue, ...s.notionalBig(sent) }}>
              {fmt(alert.notional ?? 0)}
            </div>
          </div>
          <div style={s.stat}>
            <div style={s.statLabel}>Vol / OI</div>
            <div style={{ ...s.statValue, color: volOiColor }}>
              {volOiLabel}
            </div>
          </div>
          <div style={s.stat}>
            <div style={s.statLabel}>Volume</div>
            <div style={s.statValue}>{(alert.volume ?? 0).toLocaleString()}</div>
          </div>
        </div>

        {/* Greeks row */}
        {(alert.delta != null || alert.theta != null || alert.vega != null || alert.gamma != null) && (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {alert.delta != null && (
              <span style={{ padding: '3px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(0,0,0,0.3)', color: '#a0aec0' }}>
                Δ {Math.abs(alert.delta)}
              </span>
            )}
            {alert.gamma != null && (
              <span style={{ padding: '3px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(0,0,0,0.3)', color: '#718096' }}>
                Γ {alert.gamma}
              </span>
            )}
            {alert.theta != null && (
              <span style={{ padding: '3px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(116,42,42,0.2)', color: '#fc8181' }}>
                Θ {alert.theta}/d
              </span>
            )}
            {alert.vega != null && (
              <span style={{ padding: '3px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(43,108,176,0.15)', color: '#90cdf4' }}>
                V {alert.vega}
              </span>
            )}
          </div>
        )}

        {/* Implied target */}
        {alert.implied_target && (
          <div style={s.impliedTarget(sent)}>
            🎯 {alert.implied_target}
          </div>
        )}

        {/* Premium analysis */}
        {(alert.premium_rating || alert.breakeven || alert.pct_move_needed != null) && (
          <div style={s.premiumRow}>
            {alert.premium_rating && (
              <span style={s.premiumBadge(alert.premium_rating)}>
                {alert.premium_rating === 'RICH' ? '🔥 RICH' : alert.premium_rating === 'CHEAP' ? '✅ CHEAP' : '◆ FAIR'} premium
              </span>
            )}
            {alert.breakeven != null && (
              <span style={s.premiumMeta}>BE: ${alert.breakeven}</span>
            )}
            {alert.pct_move_needed != null && (
              <span style={s.premiumMeta}>needs {alert.pct_move_needed}% move</span>
            )}
            {alert.iv_pct != null && alert.hv_pct != null && (
              <span style={s.premiumMeta}>IV {alert.iv_pct}% / HV {alert.hv_pct}%</span>
            )}
          </div>
        )}

        {/* Interpretation */}
        {alert.interpretation && (
          <div style={s.interpretation}>{alert.interpretation}</div>
        )}

        {/* Recommendation */}
        {alert.recommendation && (
          <div style={s.recommendation(alert.recommendation)}>
            {alert.recommendation.toUpperCase().startsWith('BUY') ? '✅' : '⛔'} {alert.recommendation}
          </div>
        )}

        {/* Action note */}
        {alert.action_note && (
          <div style={s.actionNote}>⚡ {alert.action_note}</div>
        )}
      </div>
    </div>
  )
}

export default function OptionsFlowTab() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [scannedAt, setScannedAt] = useState(null)

  const runScan = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.flow.scan()
      setResult(data)
      setScannedAt(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const alerts = result?.alerts ?? []
  const sentiment = result?.overall_sentiment
  const sentimentLabel =
    sentiment === 'bullish' ? '▲ BULLISH FLOW'
    : sentiment === 'bearish' ? '▼ BEARISH FLOW'
    : '◆ NEUTRAL FLOW'

  return (
    <div>
      <div style={s.header}>
        <div style={s.title}>🌊 Options Flow Scanner</div>
        <div style={s.subtitle}>
          Detects unusual options activity — when volume far exceeds open interest, big money is making a move.
        </div>
      </div>

      {result && (
        <div style={s.sentimentBar}>
          <span style={s.sentimentBadge(sentiment)}>{sentimentLabel}</span>
          <span style={s.ratio}>
            {result.sentiment_ratio}% calls · {100 - result.sentiment_ratio}% puts
            &nbsp;·&nbsp;
            {fmt(result.call_notional)} call flow vs {fmt(result.put_notional)} put flow
          </span>
        </div>
      )}

      <div style={s.toolbar}>
        <button style={s.scanBtn(loading)} onClick={runScan} disabled={loading}>
          {loading ? '⏳ Scanning flow…' : '🌊 Scan Flow'}
        </button>
        {scannedAt && (
          <span style={s.scannedNote}>
            Last scan: {scannedAt.toLocaleTimeString()}
            {result?.total_alerts_found != null && ` · ${result.total_alerts_found} unusual contracts found`}
            {result?.tickers_scanned != null && ` across ${result.tickers_scanned} tickers`}
          </span>
        )}
        {result && (
          <span style={s.note}>yfinance options chains · vol/OI ratio ≥ 3× flagged</span>
        )}
      </div>

      {error && <div style={s.error}>⚠ {error}</div>}

      {!result && !loading && (
        <div style={s.emptyState}>
          Click <strong>Scan Flow</strong> to detect unusual options activity across {' '}
          top liquid names.
          <br />
          <small style={{ color: '#4a5568', display: 'block', marginTop: '8px' }}>
            Flags contracts where volume is 3× or more above open interest — a signal that new, large
            positions are being opened. Best during market hours.
          </small>
        </div>
      )}

      {alerts.length > 0 && (
        <>
          <div style={s.grid}>
            {alerts.map((alert, i) => (
              <FlowCard key={`${alert.ticker}-${alert.strike}-${alert.option_type}-${i}`} alert={alert} />
            ))}
          </div>
          <div style={s.disclaimer}>
            Unusual volume ≠ guaranteed direction. Flow can be hedging, spread legs, or noise.
            Use alongside price action — not as a standalone signal. Not financial advice.
          </div>
        </>
      )}

      {alerts.length === 0 && result && !loading && (
        <div style={s.emptyState}>
          <div style={{ marginBottom: '8px', fontWeight: 600, color: '#a0aec0' }}>
            No unusual flow detected in this scan.
          </div>
          <div style={{ fontSize: '12px', color: '#4a5568' }}>
            Options volume is within normal ranges across the universe.
            Try again during active market hours when flow is heaviest (10am–3pm ET).
          </div>
        </div>
      )}
    </div>
  )
}
