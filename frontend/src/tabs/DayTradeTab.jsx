import { useState, useEffect } from 'react'
import { api } from '../api'

const MARKET_STATUS = {
  open:        { label: '● MARKET OPEN',      color: '#68d391', bg: '#071a0a', border: '#276749' },
  after_hours: { label: '◐ AFTER HOURS',      color: '#f6e05e', bg: '#1a1400', border: '#b7791f' },
  pre_market:  { label: '◑ PRE-MARKET',       color: '#90cdf4', bg: '#0a1220', border: '#2b6cb0' },
  closed:      { label: '○ MARKET CLOSED',    color: '#718096', bg: '#131825', border: '#2d3748' },
}

const CONFIDENCE_COLORS = {
  high:   { bg: '#071a0a', border: '#276749', text: '#68d391', badge: '#0d2218' },
  medium: { bg: '#1a1400', border: '#b7791f', text: '#f6e05e', badge: '#2d2200' },
  low:    { bg: '#1a1209', border: '#744210', text: '#f6ad55', badge: '#2d1a09' },
}

const TIMEFRAME_COLORS = {
  intraday:  { bg: '#0a1220', border: '#2b6cb0', text: '#63b3ed' },
  'intraday (same day)': { bg: '#0a1220', border: '#2b6cb0', text: '#63b3ed' },
  swing:     { bg: '#1a0a1f', border: '#6b46c1', text: '#b794f4' },
  '2-3 day': { bg: '#1a0a1f', border: '#6b46c1', text: '#b794f4' },
  '2-3 day swing': { bg: '#1a0a1f', border: '#6b46c1', text: '#b794f4' },
}

function badge(label, colors) {
  return (
    <span style={{
      padding: '3px 10px', fontSize: '11px', fontWeight: 700,
      background: colors.bg ?? '#1a1f2e',
      border: `1px solid ${colors.border ?? '#2d3748'}`,
      color: colors.text ?? '#a0aec0',
      borderRadius: '20px', whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  )
}

const s = {
  header: { marginBottom: '24px' },
  title: { fontSize: '20px', fontWeight: 700, color: '#e2e8f0', marginBottom: '4px' },
  subtitle: { fontSize: '13px', color: '#718096' },

  statusBar: {
    display: 'flex', alignItems: 'center', gap: '10px',
    marginBottom: '16px', flexWrap: 'wrap',
  },
  marketBadge: (label) => {
    const cfg = MARKET_STATUS[label] ?? MARKET_STATUS.closed
    return {
      padding: '5px 14px', fontSize: '12px', fontWeight: 700,
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      color: cfg.color, borderRadius: '20px',
    }
  },
  serverTime: { fontSize: '11px', color: '#4a5568' },

  toolbar: {
    display: 'flex', alignItems: 'center', gap: '12px',
    marginBottom: '20px', flexWrap: 'wrap',
  },
  scanBtn: (loading) => ({
    padding: '10px 24px',
    background: loading ? '#2d3748' : '#2b6cb0',
    color: loading ? '#718096' : '#fff',
    border: 'none', borderRadius: '8px',
    cursor: loading ? 'not-allowed' : 'pointer',
    fontSize: '14px', fontWeight: 700,
  }),
  dataNote: {
    fontSize: '11px', color: '#4a5568', fontStyle: 'italic',
  },
  scannedNote: { fontSize: '12px', color: '#718096' },

  error: {
    color: '#fc8181', background: '#2d1515',
    border: '1px solid #742a2a', borderRadius: '8px',
    padding: '14px 16px', fontSize: '14px', marginBottom: '20px',
  },

  emptyState: {
    background: '#131825', border: '1px solid #2d3748',
    borderRadius: '12px', padding: '48px',
    textAlign: 'center', color: '#718096', fontSize: '14px',
  },

  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
    gap: '16px',
  },

  card: (conf) => {
    const c = CONFIDENCE_COLORS[conf] ?? CONFIDENCE_COLORS.medium
    return {
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: '12px', overflow: 'hidden',
    }
  },

  cardHeader: (conf) => {
    const c = CONFIDENCE_COLORS[conf] ?? CONFIDENCE_COLORS.medium
    return {
      background: c.badge,
      borderBottom: `1px solid ${c.border}`,
      padding: '14px 16px',
      display: 'flex', alignItems: 'center',
      justifyContent: 'space-between', gap: '10px',
    }
  },

  ticker: { fontSize: '26px', fontWeight: 900, color: '#e2e8f0' },
  badges: { display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' },

  cardBody: { padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' },

  statsGrid: {
    display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
    gap: '8px',
  },
  statBox: {
    background: 'rgba(0,0,0,0.3)', borderRadius: '6px',
    padding: '8px 10px',
  },
  statLabel: {
    fontSize: '10px', color: '#718096',
    textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600,
  },
  statValue: (conf) => ({
    fontSize: '14px', fontWeight: 700, marginTop: '2px',
    color: CONFIDENCE_COLORS[conf]?.text ?? '#e2e8f0',
  }),

  rrBox: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '8px 12px',
  },
  rrLabel: { fontSize: '11px', color: '#718096', fontWeight: 600 },
  rrValue: { fontSize: '16px', fontWeight: 800, color: '#e2e8f0' },

  shortBox: (squeeze) => ({
    display: 'flex', gap: '8px', flexWrap: 'wrap',
    background: squeeze ? 'rgba(107,70,193,0.1)' : 'rgba(0,0,0,0.2)',
    border: `1px solid ${squeeze ? '#6b46c1' : '#2d3748'}`,
    borderRadius: '6px', padding: '7px 10px', alignItems: 'center',
  }),
  shortLabel: { fontSize: '10px', color: '#718096', fontWeight: 600, textTransform: 'uppercase' },
  shortValue: (squeeze) => ({
    fontSize: '13px', fontWeight: 700,
    color: squeeze ? '#b794f4' : '#a0aec0',
  }),
  squeezeAlert: {
    fontSize: '11px', color: '#b794f4', fontWeight: 700,
    background: 'rgba(107,70,193,0.15)', border: '1px solid #6b46c1',
    borderRadius: '4px', padding: '2px 8px',
  },

  catalystBox: {
    fontSize: '12px', color: '#90cdf4',
    background: 'rgba(43,108,176,0.08)',
    border: '1px solid rgba(43,108,176,0.2)',
    borderRadius: '6px', padding: '8px 10px', lineHeight: 1.5,
  },

  reasoning: {
    fontSize: '13px', color: '#a0aec0', lineHeight: 1.65,
  },

  optionsBox: {
    background: 'rgba(43,108,176,0.07)',
    border: '1px solid rgba(43,108,176,0.25)',
    borderRadius: '8px',
    padding: '10px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  optionsTitle: {
    fontSize: '10px', color: '#63b3ed', fontWeight: 700,
    textTransform: 'uppercase', letterSpacing: '0.05em',
  },
  optionsContract: {
    fontSize: '13px', fontWeight: 800, color: '#e2e8f0',
  },
  optionsGrid: {
    display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr',
    gap: '6px',
  },
  optStat: {
    background: 'rgba(0,0,0,0.25)', borderRadius: '5px', padding: '5px 8px',
  },
  optLabel: {
    fontSize: '9px', color: '#4a5568', textTransform: 'uppercase',
    letterSpacing: '0.05em', fontWeight: 600,
  },
  optValue: (color) => ({
    fontSize: '13px', fontWeight: 700, marginTop: '1px', color: color || '#e2e8f0',
  }),
  optBreakeven: {
    fontSize: '11px', color: '#718096',
  },
  likelihoodBadge: (label) => {
    const cfg = {
      likely:      { bg: 'rgba(104,211,145,0.1)',  border: 'rgba(39,103,73,0.5)',  color: '#68d391', icon: '✅' },
      possible:    { bg: 'rgba(246,224,94,0.08)',  border: 'rgba(183,121,31,0.4)', color: '#f6e05e', icon: '⚠️' },
      speculative: { bg: 'rgba(252,129,129,0.08)', border: 'rgba(116,42,42,0.4)', color: '#fc8181', icon: '🎲' },
    }[label] ?? { bg: 'rgba(0,0,0,0.2)', border: '#2d3748', color: '#718096', icon: '◆' }
    return {
      display: 'flex', alignItems: 'center', gap: '8px',
      padding: '6px 10px', borderRadius: '6px',
      background: cfg.bg, border: `1px solid ${cfg.border}`,
    }
  },
  likelihoodText: (label) => {
    const colors = { likely: '#68d391', possible: '#f6e05e', speculative: '#fc8181' }
    return { fontSize: '12px', fontWeight: 700, color: colors[label] ?? '#718096' }
  },
  likelihoodMeta: {
    fontSize: '11px', color: '#718096', marginLeft: 'auto',
  },

  disclaimer: { fontSize: '11px', color: '#4a5568', marginTop: '16px' },

  moversWrap: { marginTop: '28px' },
  moversTitle: {
    fontSize: '12px', color: '#4a5568', fontWeight: 600,
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px',
  },
  moversGrid: {
    display: 'flex', flexWrap: 'wrap', gap: '8px',
  },
  moverChip: (dir) => ({
    padding: '5px 12px', fontSize: '12px', fontWeight: 600,
    background: dir === 'up' ? '#071a0a' : '#1f0a0a',
    border: `1px solid ${dir === 'up' ? '#276749' : '#742a2a'}`,
    color: dir === 'up' ? '#68d391' : '#fc8181',
    borderRadius: '20px',
  }),
}

function PlayCard({ play, shortData }) {
  const conf = (play.confidence || 'medium').toLowerCase()
  const tf = (play.timeframe || '').toLowerCase()
  const tfColors = TIMEFRAME_COLORS[tf] ?? TIMEFRAME_COLORS.swing
  const confColors = CONFIDENCE_COLORS[conf] ?? CONFIDENCE_COLORS.medium
  const dirLong = play.direction === 'long'

  const dtc = shortData?.days_to_cover ?? null
  const svr = shortData?.short_volume_ratio_pct ?? null
  const squeezeRisk = dtc != null && dtc > 3 && dirLong
  const rsi = shortData?.rsi ?? null
  const atr = shortData?.atr ?? null
  const vsspy = shortData?.vs_spy ?? null

  return (
    <div style={s.card(conf)}>
      <div style={s.cardHeader(conf)}>
        <span style={s.ticker}>{play.ticker}</span>
        <div style={s.badges}>
          {badge(dirLong ? '▲ LONG' : '▼ SHORT', {
            bg: dirLong ? '#071a0a' : '#1f0a0a',
            border: dirLong ? '#276749' : '#742a2a',
            text: dirLong ? '#68d391' : '#fc8181',
          })}
          {badge(play.setup || 'Setup', {
            bg: confColors.badge,
            border: confColors.border,
            text: confColors.text,
          })}
          {badge(tf || 'intraday', tfColors)}
          {squeezeRisk && badge('🔥 Squeeze Risk', { bg: 'rgba(107,70,193,0.15)', border: '#6b46c1', text: '#b794f4' })}
        </div>
      </div>

      <div style={s.cardBody}>
        {/* Entry / Target / Stop */}
        <div style={s.statsGrid}>
          <div style={s.statBox}>
            <div style={s.statLabel}>Entry Zone</div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#e2e8f0', marginTop: '2px' }}>
              {play.entry_zone || '—'}
            </div>
          </div>
          <div style={s.statBox}>
            <div style={s.statLabel}>Target</div>
            <div style={s.statValue(conf)}>{play.target || '—'}</div>
          </div>
          <div style={s.statBox}>
            <div style={s.statLabel}>Stop Loss</div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#fc8181', marginTop: '2px' }}>
              {play.stop_loss || '—'}
            </div>
          </div>
        </div>

        {/* Short Interest */}
        {(dtc != null || svr != null) && (
          <div style={s.shortBox(squeezeRisk)}>
            <span style={s.shortLabel}>Short:</span>
            {dtc != null && (
              <span style={s.shortValue(squeezeRisk)}>
                {dtc}d to cover
              </span>
            )}
            {svr != null && (
              <span style={s.shortValue(svr > 50)}>
                {svr}% of vol today shorted
              </span>
            )}
            {squeezeRisk && (
              <span style={s.squeezeAlert}>⚡ squeeze potential</span>
            )}
          </div>
        )}

        {/* Technicals row */}
        {(rsi != null || atr != null || vsspy != null) && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {rsi != null && (
              <span style={{
                padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '20px',
                background: rsi > 70 ? '#2d1515' : rsi < 30 ? '#071a0a' : '#131825',
                border: `1px solid ${rsi > 70 ? '#742a2a' : rsi < 30 ? '#276749' : '#2d3748'}`,
                color: rsi > 70 ? '#fc8181' : rsi < 30 ? '#68d391' : '#718096',
              }}>
                RSI {rsi}{rsi > 70 ? ' ⚠' : rsi < 30 ? ' ↩' : ''}
              </span>
            )}
            {atr != null && (
              <span style={{ padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '20px', background: '#131825', border: '1px solid #2d3748', color: '#718096' }}>
                ATR ${atr}
              </span>
            )}
            {vsspy != null && (
              <span style={{
                padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '20px',
                background: vsspy >= 0 ? '#071a0a' : '#1f0a0a',
                border: `1px solid ${vsspy >= 0 ? '#276749' : '#742a2a'}`,
                color: vsspy >= 0 ? '#68d391' : '#fc8181',
              }}>
                vs S&P {vsspy >= 0 ? '+' : ''}{vsspy}%
              </span>
            )}
          </div>
        )}

        {/* Risk/Reward */}
        {play.risk_reward && (
          <div style={s.rrBox}>
            <span style={s.rrLabel}>Risk / Reward</span>
            <span style={s.rrValue}>{play.risk_reward}</span>
          </div>
        )}

        {/* Options Entry */}
        {play.option_play && (
          <div style={s.optionsBox}>
            <div style={s.optionsTitle}>📋 Options Entry</div>
            <div style={s.optionsContract}>
              ${play.option_play.strike} {play.option_play.option_type} &nbsp;·&nbsp; exp {play.option_play.expiry}
              {play.option_play.dte != null && ` (${play.option_play.dte}d)`}
            </div>
            <div style={s.optionsGrid}>
              <div style={s.optStat}>
                <div style={s.optLabel}>Buy for</div>
                <div style={s.optValue('#90cdf4')}>
                  ${play.option_play.entry_premium ?? '—'}
                </div>
              </div>
              <div style={s.optStat}>
                <div style={s.optLabel}>Target</div>
                <div style={s.optValue('#68d391')}>
                  {play.option_play.target_premium != null ? `$${play.option_play.target_premium}` : '—'}
                </div>
              </div>
              <div style={s.optStat}>
                <div style={s.optLabel}>Stop</div>
                <div style={s.optValue('#fc8181')}>
                  {play.option_play.stop_premium != null ? `$${play.option_play.stop_premium}` : '—'}
                </div>
              </div>
              <div style={s.optStat}>
                <div style={s.optLabel}>BE Stock</div>
                <div style={s.optValue('#f6e05e')}>
                  ${play.option_play.breakeven_stock ?? '—'}
                </div>
              </div>
            </div>
            {(play.option_play.likelihood || play.option_play.delta != null || play.option_play.move_feasibility != null) && (
              <div style={s.likelihoodBadge(play.option_play.likelihood)}>
                <span style={s.likelihoodText(play.option_play.likelihood)}>
                  {play.option_play.likelihood === 'likely' ? '✅ LIKELY'
                   : play.option_play.likelihood === 'possible' ? '⚠ POSSIBLE'
                   : play.option_play.likelihood === 'speculative' ? '🎲 SPECULATIVE'
                   : '◆ UNKNOWN'}
                </span>
                <span style={s.likelihoodMeta}>
                  {play.option_play.delta != null && `Δ${Math.abs(play.option_play.delta)} (~${Math.round(Math.abs(play.option_play.delta) * 100)}% ITM)`}
                  {play.option_play.delta != null && play.option_play.move_feasibility != null && '  ·  '}
                  {play.option_play.move_feasibility != null && `${play.option_play.move_feasibility}× daily ATR needed`}
                </span>
              </div>
            )}
            {(play.option_play.theta != null || play.option_play.vega != null || play.option_play.iv_pct != null) && (
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {play.option_play.theta != null && (
                  <span style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 600, borderRadius: '4px', background: 'rgba(116,42,42,0.2)', color: '#fc8181' }}>
                    Θ {play.option_play.theta}/d
                  </span>
                )}
                {play.option_play.vega != null && (
                  <span style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 600, borderRadius: '4px', background: 'rgba(43,108,176,0.15)', color: '#90cdf4' }}>
                    V {play.option_play.vega}
                  </span>
                )}
                {play.option_play.iv_pct != null && (
                  <span style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 600, borderRadius: '4px', background: 'rgba(0,0,0,0.3)', color: '#718096' }}>
                    IV {play.option_play.iv_pct}%
                  </span>
                )}
              </div>
            )}
            {(play.option_play.bid != null || play.option_play.pct_move_needed != null) && (
              <div style={s.optBreakeven}>
                {play.option_play.bid != null && play.option_play.ask != null && `Bid $${play.option_play.bid} / Ask $${play.option_play.ask}`}
                {play.option_play.bid != null && play.option_play.pct_move_needed != null && ' · '}
                {play.option_play.pct_move_needed != null && `stock needs ${play.option_play.pct_move_needed}% move`}
              </div>
            )}
          </div>
        )}

        {/* Catalyst */}
        {play.catalyst && (
          <div style={s.catalystBox}>
            ⚡ {play.catalyst}
          </div>
        )}

        {/* Reasoning */}
        {play.reasoning && (
          <div style={s.reasoning}>{play.reasoning}</div>
        )}
      </div>
    </div>
  )
}

export default function DayTradeTab() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [scannedAt, setScannedAt] = useState(null)
  const [marketStatus, setMarketStatus] = useState(null)

  useEffect(() => {
    api.scanner.marketStatus().then(setMarketStatus).catch(() => {})
  }, [])

  const runScan = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.scanner.scan()
      setResult(data)
      setScannedAt(new Date())
      if (data.market_status) setMarketStatus(data.market_status)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const plays = result?.plays ?? []
  const movers = result?.top_movers ?? []

  // Build a map of ticker -> enriched data from top_movers
  const shortMap = {}
  movers.forEach(m => {
    shortMap[m.ticker] = {
      days_to_cover: m.days_to_cover ?? null,
      short_volume_ratio_pct: m.short_volume_ratio_pct ?? null,
      rsi: m.rsi ?? null,
      atr: m.atr ?? null,
      vs_spy: m.vs_spy ?? null,
    }
  })

  const status = marketStatus ?? result?.market_status
  const statusCfg = status ? (MARKET_STATUS[status.label] ?? MARKET_STATUS.closed) : null

  return (
    <div>
      <div style={s.header}>
        <div style={s.title}>⚡ Day Trade Scanner</div>
        <div style={s.subtitle}>
          Scans today's top movers and uses AI to surface the highest-confidence intraday and swing plays.
        </div>
      </div>

      {statusCfg && (
        <div style={s.statusBar}>
          <span style={s.marketBadge(status.label)}>{statusCfg.label}</span>
          {status.server_time && (
            <span style={s.serverTime}>
              as of {new Date(status.server_time).toLocaleTimeString()}
            </span>
          )}
          {result?.spy_change != null && (
            <span style={{
              padding: '4px 12px', fontSize: '12px', fontWeight: 700, borderRadius: '20px',
              background: result.spy_change >= 0 ? '#071a0a' : '#1f0a0a',
              border: `1px solid ${result.spy_change >= 0 ? '#276749' : '#742a2a'}`,
              color: result.spy_change >= 0 ? '#68d391' : '#fc8181',
            }}>
              SPY {result.spy_change >= 0 ? '+' : ''}{result.spy_change}%
            </span>
          )}
          {!status.is_open && (
            <span style={{ fontSize: '11px', color: '#4a5568' }}>
              Data is delayed — scan during market hours for best results
            </span>
          )}
        </div>
      )}

      <div style={s.toolbar}>
        <button style={s.scanBtn(loading)} onClick={runScan} disabled={loading}>
          {loading ? '⏳ Scanning movers…' : '⚡ Run Scan'}
        </button>
        {scannedAt && (
          <span style={s.scannedNote}>
            Last scan: {scannedAt.toLocaleTimeString()}
            {result?.candidates_scanned != null && ` · ${result.candidates_scanned} movers screened`}
          </span>
        )}
        {result?.data_note && (
          <span style={s.dataNote}>{result.data_note}</span>
        )}
      </div>

      {error && <div style={s.error}>⚠ {error}</div>}

      {!result && !loading && (
        <div style={s.emptyState}>
          Click <strong>Run Scan</strong> to scan today's top movers and find high-confidence plays.
          <br />
          <small style={{ color: '#4a5568', display: 'block', marginTop: '8px' }}>
            Best used during market hours (9:30am – 4pm ET). Data is 15-minute delayed on the free plan.
          </small>
        </div>
      )}

      {plays.length > 0 && (
        <>
          <div style={s.grid}>
            {plays.map((play, i) => (
              <PlayCard key={`${play.ticker}-${i}`} play={play} shortData={shortMap[play.ticker]} />
            ))}
          </div>

          <div style={s.disclaimer}>
            AI analysis only — not financial advice. Always verify entries with your broker and use your own risk management.
            Data is 15-minute delayed on the Massive free tier.
          </div>
        </>
      )}

      {plays.length === 0 && result && !loading && (
        <div style={s.emptyState}>
          <div style={{ marginBottom: '8px', fontWeight: 600, color: '#a0aec0' }}>
            No plays returned for this scan.
          </div>
          <div style={{ fontSize: '12px', color: '#4a5568', lineHeight: 1.6 }}>
            {result.candidates_scanned > 0
              ? `Screened ${result.candidates_scanned} movers — Claude did not find high-confidence setups at current levels.`
              : 'No movers met the scan thresholds. Market may be quiet or closed.'}
            <br />
            {result.spy_change != null && `S&P 500 is ${result.spy_change >= 0 ? '+' : ''}${result.spy_change}% today. `}
            Best results during active market hours (9:30am–4pm ET).
          </div>
        </div>
      )}

      {movers.length > 0 && (
        <div style={s.moversWrap}>
          <div style={s.moversTitle}>All screened movers ({movers.length})</div>
          <div style={s.moversGrid}>
            {movers.map((m) => (
              <span key={m.ticker} style={s.moverChip(m.direction)}>
                {m.ticker} {m.change_pct >= 0 ? '+' : ''}{m.change_pct}%
                &nbsp;·&nbsp;{m.vol_ratio}x vol
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
