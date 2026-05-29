import { useState, useEffect } from 'react'
import { api } from '../api'

const VERDICT_COLORS = {
  GREEN:   { bg: '#0a1f12', border: '#276749', dot: '#68d391', text: '#c6f6d5' },
  YELLOW:  { bg: '#1a150a', border: '#744210', dot: '#f6ad55', text: '#fbd38d' },
  RED:     { bg: '#1a0a0a', border: '#742a2a', dot: '#fc8181', text: '#fed7d7' },
  UNKNOWN: { bg: '#111827', border: '#2d3748', dot: '#718096', text: '#a0aec0' },
}

const REGIME_LABELS = {
  BULL: '📈 Bull Market',
  BEAR: '📉 Bear Market',
  SIDEWAYS: '➡ Sideways',
  VOLATILE: '⚡ Volatile',
  UNKNOWN: '— Unknown',
}

const VIX_COLORS = {
  CALM:     '#68d391',
  NORMAL:   '#63b3ed',
  ELEVATED: '#f6ad55',
  EXTREME:  '#fc8181',
  UNKNOWN:  '#718096',
}

const s = {
  banner: (verdict) => ({
    background: VERDICT_COLORS[verdict]?.bg ?? VERDICT_COLORS.UNKNOWN.bg,
    borderBottom: `2px solid ${VERDICT_COLORS[verdict]?.border ?? VERDICT_COLORS.UNKNOWN.border}`,
    padding: '10px 24px',
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
    flexWrap: 'wrap',
    fontSize: '13px',
  }),
  dot: (verdict) => ({
    width: '10px', height: '10px', borderRadius: '50%',
    background: VERDICT_COLORS[verdict]?.dot ?? VERDICT_COLORS.UNKNOWN.dot,
    flexShrink: 0,
    boxShadow: `0 0 6px ${VERDICT_COLORS[verdict]?.dot ?? VERDICT_COLORS.UNKNOWN.dot}`,
  }),
  verdict: (verdict) => ({
    fontWeight: 700, fontSize: '13px',
    color: VERDICT_COLORS[verdict]?.text ?? VERDICT_COLORS.UNKNOWN.text,
    whiteSpace: 'nowrap',
  }),
  stat: { color: '#a0aec0', whiteSpace: 'nowrap' },
  statVal: { color: '#e2e8f0', fontWeight: 600, marginLeft: '4px' },
  summary: { color: '#718096', fontSize: '12px', flex: 1, minWidth: '200px' },
  refreshBtn: {
    marginLeft: 'auto', padding: '4px 10px',
    background: 'transparent', border: '1px solid #2d3748',
    borderRadius: '5px', color: '#718096',
    cursor: 'pointer', fontSize: '11px', whiteSpace: 'nowrap',
  },
  expanded: (verdict) => ({
    background: VERDICT_COLORS[verdict]?.bg ?? VERDICT_COLORS.UNKNOWN.bg,
    borderBottom: `1px solid ${VERDICT_COLORS[verdict]?.border ?? VERDICT_COLORS.UNKNOWN.border}`,
    padding: '12px 24px 16px',
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: '12px',
  }),
  guideCard: {
    background: 'rgba(0,0,0,0.2)',
    border: '1px solid #2d3748',
    borderRadius: '8px',
    padding: '10px 14px',
  },
  guideLabel: {
    fontSize: '10px', fontWeight: 700, color: '#718096',
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px',
  },
  guideText: { fontSize: '12px', color: '#a0aec0', lineHeight: 1.5 },
}

export default function MarketBanner() {
  const [ctx, setCtx] = useState(null)
  const [expanded, setExpanded] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const load = async (refresh = false) => {
    try {
      const data = await api.market.getContext(refresh)
      setCtx(data)
    } catch {
      // silently fail — banner is non-critical
    }
  }

  useEffect(() => { load() }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    await load(true)
    setRefreshing(false)
  }

  if (!ctx) return null

  const verdict = ctx.trade_verdict || 'UNKNOWN'
  const verdictLabel = {
    GREEN: '✓ Good conditions to trade',
    YELLOW: '⚡ Trade with caution',
    RED: '✗ Difficult market — reduce risk',
    UNKNOWN: '— Market data unavailable',
  }[verdict]

  const guidance = ctx.strategy_guidance || {}

  return (
    <>
      <div style={s.banner(verdict)}>
        <div style={s.dot(verdict)} />
        <span style={s.verdict(verdict)}>{verdictLabel}</span>

        {ctx.vix != null && (
          <span style={s.stat}>
            VIX
            <span style={{ ...s.statVal, color: VIX_COLORS[ctx.vix_label] || '#e2e8f0' }}>
              {' '}{ctx.vix.toFixed(1)} ({ctx.vix_label})
            </span>
          </span>
        )}

        {ctx.market_regime && ctx.market_regime !== 'UNKNOWN' && (
          <span style={s.stat}>
            Market<span style={s.statVal}>{' '}{REGIME_LABELS[ctx.market_regime] || ctx.market_regime}</span>
          </span>
        )}

        {ctx.spy_vs_50ma_pct != null && (
          <span style={s.stat}>
            SPY vs 50d MA
            <span style={{ ...s.statVal, color: ctx.spy_vs_50ma_pct >= 0 ? '#68d391' : '#fc8181' }}>
              {' '}{ctx.spy_vs_50ma_pct > 0 ? '+' : ''}{ctx.spy_vs_50ma_pct}%
            </span>
          </span>
        )}

        {Object.keys(guidance).length > 0 && (
          <button style={s.refreshBtn} onClick={() => setExpanded(e => !e)}>
            {expanded ? '▲ Less' : '▼ Strategy guidance'}
          </button>
        )}

        <button
          style={{ ...s.refreshBtn, marginLeft: Object.keys(guidance).length > 0 ? '0' : 'auto' }}
          onClick={handleRefresh}
          disabled={refreshing}
        >
          {refreshing ? '⏳' : '↺'} Refresh
        </button>
      </div>

      {expanded && Object.keys(guidance).length > 0 && (
        <div style={s.expanded(verdict)}>
          {ctx.summary && (
            <div style={{ ...s.guideCard, gridColumn: '1 / -1' }}>
              <div style={s.guideLabel}>Market Summary</div>
              <div style={{ ...s.guideText, color: '#cbd5e0' }}>{ctx.summary}</div>
            </div>
          )}
          {guidance.options_buying && (
            <div style={s.guideCard}>
              <div style={s.guideLabel}>📊 Options Buying (Calls & Puts)</div>
              <div style={s.guideText}>{guidance.options_buying}</div>
            </div>
          )}
          {guidance.wheel_and_selling && (
            <div style={s.guideCard}>
              <div style={s.guideLabel}>🔄 Wheel / Selling Premium</div>
              <div style={s.guideText}>{guidance.wheel_and_selling}</div>
            </div>
          )}
          {guidance.long_term && (
            <div style={s.guideCard}>
              <div style={s.guideLabel}>🌱 Long-Term Investing</div>
              <div style={s.guideText}>{guidance.long_term}</div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
