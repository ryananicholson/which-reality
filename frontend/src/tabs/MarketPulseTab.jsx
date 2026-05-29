import { useState, useEffect } from 'react'
import { api } from '../api'

// ─── Shared config ────────────────────────────────────────────────────────────
const MARKET_STATUS = {
  open:        { label: '● MARKET OPEN',   color: '#68d391', bg: '#071a0a', border: '#276749' },
  after_hours: { label: '◐ AFTER HOURS',  color: '#f6e05e', bg: '#1a1400', border: '#b7791f' },
  pre_market:  { label: '◑ PRE-MARKET',   color: '#90cdf4', bg: '#0a1220', border: '#2b6cb0' },
  closed:      { label: '○ MARKET CLOSED',color: '#718096', bg: '#131825', border: '#2d3748' },
}

const CONFIDENCE_COLORS = {
  high:   { bg: '#071a0a', border: '#276749', text: '#68d391', badge: '#0d2218' },
  medium: { bg: '#1a1400', border: '#b7791f', text: '#f6e05e', badge: '#2d2200' },
  low:    { bg: '#1a1209', border: '#744210', text: '#f6ad55', badge: '#2d1a09' },
}

const TIMEFRAME_COLORS = {
  intraday:          { bg: '#0a1220', border: '#2b6cb0', text: '#63b3ed' },
  'intraday (same day)': { bg: '#0a1220', border: '#2b6cb0', text: '#63b3ed' },
  swing:             { bg: '#1a0a1f', border: '#6b46c1', text: '#b794f4' },
  '2-3 day':         { bg: '#1a0a1f', border: '#6b46c1', text: '#b794f4' },
  '2-3 day swing':   { bg: '#1a0a1f', border: '#6b46c1', text: '#b794f4' },
}

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

function chip(label, colors) {
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

const emptyState = {
  background: '#131825', border: '1px solid #2d3748',
  borderRadius: '12px', padding: '48px',
  textAlign: 'center', color: '#718096', fontSize: '14px',
}

// ─── PlayCard (Day Scanner) ───────────────────────────────────────────────────
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

  const cardStyle = {
    background: confColors.bg, border: `1px solid ${confColors.border}`,
    borderRadius: '12px', overflow: 'hidden',
  }
  const headerStyle = {
    background: confColors.badge, borderBottom: `1px solid ${confColors.border}`,
    padding: '14px 16px', display: 'flex', alignItems: 'center',
    justifyContent: 'space-between', gap: '10px',
  }

  return (
    <div style={cardStyle}>
      <div style={headerStyle}>
        <span style={{ fontSize: '26px', fontWeight: 900, color: '#e2e8f0' }}>{play.ticker}</span>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          {chip(dirLong ? '▲ LONG' : '▼ SHORT', {
            bg: dirLong ? '#071a0a' : '#1f0a0a',
            border: dirLong ? '#276749' : '#742a2a',
            text: dirLong ? '#68d391' : '#fc8181',
          })}
          {chip(play.setup || 'Setup', { bg: confColors.badge, border: confColors.border, text: confColors.text })}
          {chip(tf || 'intraday', tfColors)}
          {squeezeRisk && chip('🔥 Squeeze Risk', { bg: 'rgba(107,70,193,0.15)', border: '#6b46c1', text: '#b794f4' })}
        </div>
      </div>

      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
          {[['Entry Zone', play.entry_zone, '#e2e8f0'], ['Target', play.target, confColors.text], ['Stop Loss', play.stop_loss, '#fc8181']].map(([lbl, val, color]) => (
            <div key={lbl} style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '8px 10px' }}>
              <div style={{ fontSize: '10px', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>{lbl}</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color, marginTop: '2px' }}>{val || '—'}</div>
            </div>
          ))}
        </div>

        {(dtc != null || svr != null) && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', background: squeezeRisk ? 'rgba(107,70,193,0.1)' : 'rgba(0,0,0,0.2)', border: `1px solid ${squeezeRisk ? '#6b46c1' : '#2d3748'}`, borderRadius: '6px', padding: '7px 10px', alignItems: 'center' }}>
            <span style={{ fontSize: '10px', color: '#718096', fontWeight: 600, textTransform: 'uppercase' }}>Short:</span>
            {dtc != null && <span style={{ fontSize: '13px', fontWeight: 700, color: squeezeRisk ? '#b794f4' : '#a0aec0' }}>{dtc}d to cover</span>}
            {svr != null && <span style={{ fontSize: '13px', fontWeight: 700, color: svr > 50 ? '#b794f4' : '#a0aec0' }}>{svr}% of vol today shorted</span>}
            {squeezeRisk && <span style={{ fontSize: '11px', color: '#b794f4', fontWeight: 700, background: 'rgba(107,70,193,0.15)', border: '1px solid #6b46c1', borderRadius: '4px', padding: '2px 8px' }}>⚡ squeeze potential</span>}
          </div>
        )}

        {(rsi != null || atr != null || vsspy != null) && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {rsi != null && <span style={{ padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '20px', background: rsi > 70 ? '#2d1515' : rsi < 30 ? '#071a0a' : '#131825', border: `1px solid ${rsi > 70 ? '#742a2a' : rsi < 30 ? '#276749' : '#2d3748'}`, color: rsi > 70 ? '#fc8181' : rsi < 30 ? '#68d391' : '#718096' }}>RSI {rsi}{rsi > 70 ? ' ⚠' : rsi < 30 ? ' ↩' : ''}</span>}
            {atr != null && <span style={{ padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '20px', background: '#131825', border: '1px solid #2d3748', color: '#718096' }}>ATR ${atr}</span>}
            {vsspy != null && <span style={{ padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '20px', background: vsspy >= 0 ? '#071a0a' : '#1f0a0a', border: `1px solid ${vsspy >= 0 ? '#276749' : '#742a2a'}`, color: vsspy >= 0 ? '#68d391' : '#fc8181' }}>vs S&P {vsspy >= 0 ? '+' : ''}{vsspy}%</span>}
          </div>
        )}

        {play.risk_reward && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '8px 12px' }}>
            <span style={{ fontSize: '11px', color: '#718096', fontWeight: 600 }}>Risk / Reward</span>
            <span style={{ fontSize: '16px', fontWeight: 800, color: '#e2e8f0' }}>{play.risk_reward}</span>
          </div>
        )}

        {play.option_play && (
          <div style={{ background: 'rgba(43,108,176,0.07)', border: '1px solid rgba(43,108,176,0.25)', borderRadius: '8px', padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontSize: '10px', color: '#63b3ed', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>📋 Options Entry</div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#e2e8f0' }}>
              ${play.option_play.strike} {play.option_play.option_type} · exp {play.option_play.expiry}
              {play.option_play.dte != null && ` (${play.option_play.dte}d)`}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '6px' }}>
              {[['Buy for', `$${play.option_play.entry_premium ?? '—'}`, '#90cdf4'], ['Target', play.option_play.target_premium != null ? `$${play.option_play.target_premium}` : '—', '#68d391'], ['Stop', play.option_play.stop_premium != null ? `$${play.option_play.stop_premium}` : '—', '#fc8181'], ['BE Stock', `$${play.option_play.breakeven_stock ?? '—'}`, '#f6e05e']].map(([lbl, val, color]) => (
                <div key={lbl} style={{ background: 'rgba(0,0,0,0.25)', borderRadius: '5px', padding: '5px 8px' }}>
                  <div style={{ fontSize: '9px', color: '#4a5568', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>{lbl}</div>
                  <div style={{ fontSize: '13px', fontWeight: 700, marginTop: '1px', color }}>{val}</div>
                </div>
              ))}
            </div>
            {play.option_play.likelihood && (() => {
              const cfg = { likely: { bg: 'rgba(104,211,145,0.1)', border: 'rgba(39,103,73,0.5)', color: '#68d391', icon: '✅' }, possible: { bg: 'rgba(246,224,94,0.08)', border: 'rgba(183,121,31,0.4)', color: '#f6e05e', icon: '⚠️' }, speculative: { bg: 'rgba(252,129,129,0.08)', border: 'rgba(116,42,42,0.4)', color: '#fc8181', icon: '🎲' } }[play.option_play.likelihood] ?? {}
              return (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 10px', borderRadius: '6px', background: cfg.bg, border: `1px solid ${cfg.border}` }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: cfg.color }}>{play.option_play.likelihood.toUpperCase()}</span>
                  <span style={{ fontSize: '11px', color: '#718096', marginLeft: 'auto' }}>
                    {play.option_play.delta != null && `Δ${Math.abs(play.option_play.delta)}`}
                    {play.option_play.move_feasibility != null && ` · ${play.option_play.move_feasibility}× ATR needed`}
                  </span>
                </div>
              )
            })()}
            {(play.option_play.theta != null || play.option_play.vega != null || play.option_play.iv_pct != null) && (
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {play.option_play.theta != null && <span style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 600, borderRadius: '4px', background: 'rgba(116,42,42,0.2)', color: '#fc8181' }}>Θ {play.option_play.theta}/d</span>}
                {play.option_play.vega != null && <span style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 600, borderRadius: '4px', background: 'rgba(43,108,176,0.15)', color: '#90cdf4' }}>V {play.option_play.vega}</span>}
                {play.option_play.iv_pct != null && <span style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 600, borderRadius: '4px', background: 'rgba(0,0,0,0.3)', color: '#718096' }}>IV {play.option_play.iv_pct}%</span>}
              </div>
            )}
            {(play.option_play.bid != null || play.option_play.pct_move_needed != null) && (
              <div style={{ fontSize: '11px', color: '#718096' }}>
                {play.option_play.bid != null && play.option_play.ask != null && `Bid $${play.option_play.bid} / Ask $${play.option_play.ask}`}
                {play.option_play.bid != null && play.option_play.pct_move_needed != null && ' · '}
                {play.option_play.pct_move_needed != null && `stock needs ${play.option_play.pct_move_needed}% move`}
              </div>
            )}
          </div>
        )}

        {play.catalyst && <div style={{ fontSize: '12px', color: '#90cdf4', background: 'rgba(43,108,176,0.08)', border: '1px solid rgba(43,108,176,0.2)', borderRadius: '6px', padding: '8px 10px', lineHeight: 1.5 }}>⚡ {play.catalyst}</div>}
        {play.reasoning && <div style={{ fontSize: '13px', color: '#a0aec0', lineHeight: 1.65 }}>{play.reasoning}</div>}
      </div>
    </div>
  )
}

// ─── FlowCard (Options Flow) ──────────────────────────────────────────────────
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
    <div style={{ background: sent === 'bullish' ? '#071a0a' : '#1f0a0a', border: `1px solid ${sent === 'bullish' ? '#276749' : '#742a2a'}`, borderRadius: '12px', overflow: 'hidden' }}>
      <div style={{ background: sent === 'bullish' ? '#0d2218' : '#2d1515', borderBottom: `1px solid ${sent === 'bullish' ? '#276749' : '#742a2a'}`, padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '22px', fontWeight: 900, color: '#e2e8f0' }}>{alert.ticker || '—'}</span>
          <span style={{ padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '20px', background: sent === 'bullish' ? 'rgba(104,211,145,0.15)' : 'rgba(252,129,129,0.15)', border: `1px solid ${sent === 'bullish' ? '#276749' : '#742a2a'}`, color: sent === 'bullish' ? '#68d391' : '#fc8181' }}>
            {sent === 'bullish' ? '▲ CALLS' : '▼ PUTS'}
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
          <span style={{ fontSize: '13px', color: '#a0aec0' }}>${alert.price ?? '—'}</span>
          <span style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 700, borderRadius: '20px', background: confColors.bg, border: `1px solid ${confColors.border}`, color: confColors.text }}>{conf.toUpperCase()}</span>
        </div>
      </div>

      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {alert.verdict && (() => {
          const vc = VERDICT_CONFIG[alert.verdict] ?? VERDICT_CONFIG.CAUTION
          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px', background: vc.bg, border: `1px solid ${vc.border}`, borderRadius: '8px' }}>
              <span style={{ fontSize: '20px', lineHeight: 1 }}>{vc.icon}</span>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 800, color: vc.text, letterSpacing: '0.05em' }}>{vc.label}</div>
                {alert.verdict_reason && <div style={{ fontSize: '12px', color: vc.text, opacity: 0.8, marginTop: '1px' }}>{alert.verdict_reason}</div>}
              </div>
            </div>
          )
        })()}

        {(alert.change_pct != null || alert.earnings_context || alert.news?.length > 0) && (
          <div style={{ background: 'rgba(0,0,0,0.25)', borderRadius: '8px', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {alert.change_pct != null && <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span style={{ fontSize: '11px', color: '#718096' }}>Today</span><span style={{ fontSize: '12px', fontWeight: 700, color: alert.change_pct >= 0 ? '#68d391' : '#fc8181' }}>{alert.change_pct >= 0 ? '▲' : '▼'} {Math.abs(alert.change_pct)}%</span></div>}
            {alert.earnings_context && <div style={{ fontSize: '11px', fontWeight: 700, color: '#f6e05e' }}>📅 {alert.earnings_context}</div>}
            {alert.news?.slice(0, 2).map((h, i) => <div key={i} style={{ fontSize: '11px', color: '#a0aec0', lineHeight: 1.4, borderLeft: '2px solid #4a5568', paddingLeft: '6px' }}>{h}</div>)}
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ padding: '4px 12px', fontSize: '12px', fontWeight: 700, borderRadius: '6px', background: 'rgba(0,0,0,0.3)', color: sent === 'bullish' ? '#68d391' : '#fc8181' }}>${alert.strike ?? '—'} {(alert.option_type || 'call').toUpperCase()} {alert.expiry ?? '—'}</span>
          <span style={{ padding: '4px 10px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(0,0,0,0.3)', color: '#a0aec0' }}>{alert.dte ?? '—'}d to exp</span>
          <span style={{ padding: '4px 10px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(0,0,0,0.3)', color: '#718096' }}>{otmLabel}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
          {[['Notional', fmt(alert.notional ?? 0), sent === 'bullish' ? '#68d391' : '#fc8181', '22px'], ['Vol / OI', volOiLabel, volOiColor, '14px'], ['Volume', (alert.volume ?? 0).toLocaleString(), '#e2e8f0', '14px']].map(([lbl, val, color, size]) => (
            <div key={lbl} style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '7px 10px' }}>
              <div style={{ fontSize: '10px', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>{lbl}</div>
              <div style={{ fontSize: size, fontWeight: 700, color, marginTop: '2px' }}>{val}</div>
            </div>
          ))}
        </div>

        {(alert.delta != null || alert.theta != null || alert.vega != null || alert.gamma != null) && (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {alert.delta != null && <span style={{ padding: '3px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(0,0,0,0.3)', color: '#a0aec0' }}>Δ {Math.abs(alert.delta)}</span>}
            {alert.gamma != null && <span style={{ padding: '3px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(0,0,0,0.3)', color: '#718096' }}>Γ {alert.gamma}</span>}
            {alert.theta != null && <span style={{ padding: '3px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(116,42,42,0.2)', color: '#fc8181' }}>Θ {alert.theta}/d</span>}
            {alert.vega != null && <span style={{ padding: '3px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '6px', background: 'rgba(43,108,176,0.15)', color: '#90cdf4' }}>V {alert.vega}</span>}
          </div>
        )}

        {alert.implied_target && <div style={{ fontSize: '12px', fontWeight: 700, borderRadius: '6px', padding: '6px 10px', background: sent === 'bullish' ? 'rgba(104,211,145,0.08)' : 'rgba(252,129,129,0.08)', border: `1px solid ${sent === 'bullish' ? 'rgba(39,103,73,0.5)' : 'rgba(116,42,42,0.5)'}`, color: sent === 'bullish' ? '#68d391' : '#fc8181' }}>🎯 {alert.implied_target}</div>}

        {(alert.premium_rating || alert.breakeven || alert.pct_move_needed != null) && (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            {alert.premium_rating && <span style={{ padding: '3px 10px', fontSize: '11px', fontWeight: 700, borderRadius: '6px', background: alert.premium_rating === 'RICH' ? 'rgba(252,129,129,0.12)' : alert.premium_rating === 'CHEAP' ? 'rgba(104,211,145,0.12)' : 'rgba(160,174,192,0.1)', border: `1px solid ${alert.premium_rating === 'RICH' ? 'rgba(116,42,42,0.5)' : alert.premium_rating === 'CHEAP' ? 'rgba(39,103,73,0.5)' : 'rgba(74,85,104,0.5)'}`, color: alert.premium_rating === 'RICH' ? '#fc8181' : alert.premium_rating === 'CHEAP' ? '#68d391' : '#a0aec0' }}>{alert.premium_rating === 'RICH' ? '🔥 RICH' : alert.premium_rating === 'CHEAP' ? '✅ CHEAP' : '◆ FAIR'} premium</span>}
            {alert.breakeven != null && <span style={{ fontSize: '11px', color: '#718096' }}>BE: ${alert.breakeven}</span>}
            {alert.pct_move_needed != null && <span style={{ fontSize: '11px', color: '#718096' }}>needs {alert.pct_move_needed}% move</span>}
            {alert.iv_pct != null && alert.hv_pct != null && <span style={{ fontSize: '11px', color: '#718096' }}>IV {alert.iv_pct}% / HV {alert.hv_pct}%</span>}
          </div>
        )}

        {alert.interpretation && <div style={{ fontSize: '13px', color: '#a0aec0', lineHeight: 1.6, background: 'rgba(0,0,0,0.2)', borderRadius: '6px', padding: '10px 12px' }}>{alert.interpretation}</div>}

        {alert.recommendation && (
          <div style={{ fontSize: '12px', fontWeight: 600, lineHeight: 1.5, background: alert.recommendation.toUpperCase().startsWith('BUY') ? 'rgba(104,211,145,0.06)' : 'rgba(252,129,129,0.06)', border: `1px solid ${alert.recommendation.toUpperCase().startsWith('BUY') ? 'rgba(39,103,73,0.4)' : 'rgba(116,42,42,0.4)'}`, color: alert.recommendation.toUpperCase().startsWith('BUY') ? '#68d391' : '#fc8181', borderRadius: '6px', padding: '8px 10px' }}>
            {alert.recommendation.toUpperCase().startsWith('BUY') ? '✅' : '⛔'} {alert.recommendation}
          </div>
        )}

        {alert.action_note && <div style={{ fontSize: '12px', color: '#90cdf4', lineHeight: 1.5, background: 'rgba(43,108,176,0.08)', border: '1px solid rgba(43,108,176,0.2)', borderRadius: '6px', padding: '8px 10px' }}>⚡ {alert.action_note}</div>}
      </div>
    </div>
  )
}

// ─── Section divider ──────────────────────────────────────────────────────────
function SectionHeader({ icon, title, subtitle, rightContent }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #2d3748', paddingTop: '20px', marginTop: '8px', flexWrap: 'wrap', gap: '8px' }}>
      <div>
        <div style={{ fontSize: '16px', fontWeight: 700, color: '#e2e8f0' }}>{icon} {title}</div>
        {subtitle && <div style={{ fontSize: '12px', color: '#718096', marginTop: '2px' }}>{subtitle}</div>}
      </div>
      {rightContent}
    </div>
  )
}

// ─── Main tab ─────────────────────────────────────────────────────────────────
export default function MarketPulseTab() {
  const [marketStatus, setMarketStatus] = useState(null)

  // Scanner state
  const [scanLoading, setScanLoading] = useState(false)
  const [scanError, setScanError] = useState(null)
  const [scanResult, setScanResult] = useState(null)
  const [scanAt, setScanAt] = useState(null)

  // Flow state
  const [flowLoading, setFlowLoading] = useState(false)
  const [flowError, setFlowError] = useState(null)
  const [flowResult, setFlowResult] = useState(null)
  const [flowAt, setFlowAt] = useState(null)

  useEffect(() => {
    api.scanner.marketStatus().then(setMarketStatus).catch(() => {})
  }, [])

  async function runScan() {
    setScanLoading(true)
    setScanError(null)
    try {
      const data = await api.scanner.scan()
      setScanResult(data)
      setScanAt(new Date())
      if (data.market_status) setMarketStatus(data.market_status)
    } catch (e) {
      setScanError(e.message)
    } finally {
      setScanLoading(false)
    }
  }

  async function runFlow() {
    setFlowLoading(true)
    setFlowError(null)
    try {
      const data = await api.flow.scan()
      setFlowResult(data)
      setFlowAt(new Date())
    } catch (e) {
      setFlowError(e.message)
    } finally {
      setFlowLoading(false)
    }
  }

  async function runBoth() {
    runScan()
    runFlow()
  }

  const plays = scanResult?.plays ?? []
  const movers = scanResult?.top_movers ?? []
  const shortMap = {}
  movers.forEach(m => { shortMap[m.ticker] = { days_to_cover: m.days_to_cover ?? null, short_volume_ratio_pct: m.short_volume_ratio_pct ?? null, rsi: m.rsi ?? null, atr: m.atr ?? null, vs_spy: m.vs_spy ?? null } })

  const alerts = flowResult?.alerts ?? []
  const flowSentiment = flowResult?.overall_sentiment
  const flowSentimentLabel = flowSentiment === 'bullish' ? '▲ BULLISH FLOW' : flowSentiment === 'bearish' ? '▼ BEARISH FLOW' : '◆ NEUTRAL FLOW'

  const status = marketStatus ?? scanResult?.market_status
  const statusCfg = status ? (MARKET_STATUS[status.label] ?? MARKET_STATUS.closed) : null

  const anyLoading = scanLoading || flowLoading

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ fontSize: '20px', fontWeight: 700, color: '#e2e8f0', marginBottom: '4px' }}>⚡ Market Pulse</div>
        <div style={{ fontSize: '13px', color: '#718096' }}>
          Day trade plays · Unusual options flow · Polygon real-time data
        </div>
      </div>

      {/* Market status bar */}
      {statusCfg && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <span style={{ padding: '5px 14px', fontSize: '12px', fontWeight: 700, background: statusCfg.bg, border: `1px solid ${statusCfg.border}`, color: statusCfg.color, borderRadius: '20px' }}>{statusCfg.label}</span>
          {status.server_time && <span style={{ fontSize: '11px', color: '#4a5568' }}>as of {new Date(status.server_time).toLocaleTimeString()}</span>}
          {scanResult?.spy_change != null && (
            <span style={{ padding: '4px 12px', fontSize: '12px', fontWeight: 700, borderRadius: '20px', background: scanResult.spy_change >= 0 ? '#071a0a' : '#1f0a0a', border: `1px solid ${scanResult.spy_change >= 0 ? '#276749' : '#742a2a'}`, color: scanResult.spy_change >= 0 ? '#68d391' : '#fc8181' }}>
              SPY {scanResult.spy_change >= 0 ? '+' : ''}{scanResult.spy_change}%
            </span>
          )}
          {flowResult && (
            <span style={{ padding: '5px 16px', fontSize: '12px', fontWeight: 700, borderRadius: '20px', background: flowSentiment === 'bullish' ? '#071a0a' : flowSentiment === 'bearish' ? '#1f0a0a' : '#131825', border: `1px solid ${flowSentiment === 'bullish' ? '#276749' : flowSentiment === 'bearish' ? '#742a2a' : '#2d3748'}`, color: flowSentiment === 'bullish' ? '#68d391' : flowSentiment === 'bearish' ? '#fc8181' : '#718096' }}>
              {flowSentimentLabel}
            </span>
          )}
          {flowResult && (
            <span style={{ fontSize: '12px', color: '#718096' }}>
              {flowResult.sentiment_ratio}% calls · {100 - flowResult.sentiment_ratio}% puts · {fmt(flowResult.call_notional)} vs {fmt(flowResult.put_notional)}
            </span>
          )}
        </div>
      )}

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '24px', flexWrap: 'wrap' }}>
        <button
          onClick={runScan} disabled={scanLoading}
          style={{ padding: '10px 20px', background: scanLoading ? '#2d3748' : '#2b6cb0', color: scanLoading ? '#718096' : '#fff', border: 'none', borderRadius: '8px', cursor: scanLoading ? 'not-allowed' : 'pointer', fontSize: '13px', fontWeight: 700 }}
        >
          {scanLoading ? '⏳ Scanning…' : '⚡ Day Plays'}
        </button>
        <button
          onClick={runFlow} disabled={flowLoading}
          style={{ padding: '10px 20px', background: flowLoading ? '#2d3748' : '#553c9a', color: flowLoading ? '#718096' : '#fff', border: 'none', borderRadius: '8px', cursor: flowLoading ? 'not-allowed' : 'pointer', fontSize: '13px', fontWeight: 700 }}
        >
          {flowLoading ? '⏳ Scanning…' : '🌊 Options Flow'}
        </button>
        <button
          onClick={runBoth} disabled={anyLoading}
          style={{ padding: '10px 20px', background: anyLoading ? '#2d3748' : '#276749', color: anyLoading ? '#718096' : '#c6f6d5', border: 'none', borderRadius: '8px', cursor: anyLoading ? 'not-allowed' : 'pointer', fontSize: '13px', fontWeight: 700 }}
        >
          {anyLoading ? '⏳ Running…' : '▶ Run Both'}
        </button>
        <div style={{ fontSize: '12px', color: '#718096', lineHeight: 1.5 }}>
          {scanAt && <div>Plays: {scanAt.toLocaleTimeString()}{scanResult?.candidates_scanned != null && ` · ${scanResult.candidates_scanned} movers`}</div>}
          {flowAt && <div>Flow: {flowAt.toLocaleTimeString()}{flowResult?.total_alerts_found != null && ` · ${flowResult.total_alerts_found} unusual contracts`}</div>}
        </div>
        <div style={{ fontSize: '11px', color: '#4a5568', fontStyle: 'italic', marginLeft: 'auto' }}>
          Polygon real-time · Finnhub earnings · Best during market hours
        </div>
      </div>

      {/* ── DAY PLAYS SECTION ─────────────────────────────────────── */}
      <SectionHeader
        icon="⚡"
        title="Day Trade Plays"
        subtitle="Polygon batch snapshots · RSI-14 · ATR-14 · Claude play selection"
        rightContent={scanResult?.data_note && <span style={{ fontSize: '11px', color: '#4a5568', fontStyle: 'italic' }}>{scanResult.data_note}</span>}
      />

      {scanError && <div style={{ color: '#fc8181', background: '#2d1515', border: '1px solid #742a2a', borderRadius: '8px', padding: '14px 16px', fontSize: '14px', margin: '16px 0' }}>⚠ {scanError}</div>}

      {!scanResult && !scanLoading && (
        <div style={{ ...emptyState, margin: '16px 0' }}>
          Click <strong>⚡ Day Plays</strong> to scan today's top movers for high-confidence intraday and swing setups.
        </div>
      )}

      {plays.length > 0 && (
        <div style={{ marginTop: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '16px' }}>
          {plays.map((play, i) => <PlayCard key={`${play.ticker}-${i}`} play={play} shortData={shortMap[play.ticker]} />)}
        </div>
      )}

      {plays.length === 0 && scanResult && !scanLoading && (
        <div style={{ ...emptyState, margin: '16px 0' }}>
          <div style={{ marginBottom: '8px', fontWeight: 600, color: '#a0aec0' }}>No plays returned.</div>
          <div style={{ fontSize: '12px', color: '#4a5568', lineHeight: 1.6 }}>
            {scanResult.candidates_scanned > 0
              ? `Screened ${scanResult.candidates_scanned} movers — Claude found no high-confidence setups.`
              : 'No movers met the thresholds. Market may be quiet or closed.'}
          </div>
        </div>
      )}

      {movers.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <div style={{ fontSize: '12px', color: '#4a5568', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>All screened movers ({movers.length})</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {movers.map(m => (
              <span key={m.ticker} style={{ padding: '5px 12px', fontSize: '12px', fontWeight: 600, background: m.direction === 'up' ? '#071a0a' : '#1f0a0a', border: `1px solid ${m.direction === 'up' ? '#276749' : '#742a2a'}`, color: m.direction === 'up' ? '#68d391' : '#fc8181', borderRadius: '20px' }}>
                {m.ticker} {m.change_pct >= 0 ? '+' : ''}{m.change_pct}% · {m.vol_ratio}x vol
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── OPTIONS FLOW SECTION ──────────────────────────────────── */}
      <SectionHeader
        icon="🌊"
        title="Unusual Options Flow"
        subtitle="Polygon options chain · Vol/OI ratio · Greeks · Claude interpretation"
      />

      {flowError && <div style={{ color: '#fc8181', background: '#2d1515', border: '1px solid #742a2a', borderRadius: '8px', padding: '14px 16px', fontSize: '14px', margin: '16px 0' }}>⚠ {flowError}</div>}

      {!flowResult && !flowLoading && (
        <div style={{ ...emptyState, margin: '16px 0' }}>
          Click <strong>🌊 Options Flow</strong> to detect unusual contract activity — when volume far exceeds open interest, big money is making a move.
        </div>
      )}

      {alerts.length > 0 && (
        <div style={{ marginTop: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '16px' }}>
          {alerts.map((alert, i) => <FlowCard key={`${alert.ticker}-${alert.strike}-${alert.option_type}-${i}`} alert={alert} />)}
        </div>
      )}

      {alerts.length === 0 && flowResult && !flowLoading && (
        <div style={{ ...emptyState, margin: '16px 0' }}>
          <div style={{ marginBottom: '8px', fontWeight: 600, color: '#a0aec0' }}>No unusual flow detected.</div>
          <div style={{ fontSize: '12px', color: '#4a5568' }}>Options volume is within normal ranges. Try again during active hours (10am–3pm ET).</div>
        </div>
      )}

      {(plays.length > 0 || alerts.length > 0) && (
        <div style={{ fontSize: '11px', color: '#4a5568', marginTop: '20px', lineHeight: 1.5 }}>
          AI analysis only — not financial advice. Unusual flow can be hedging, spread legs, or noise. Always use your own risk management.
        </div>
      )}
    </div>
  )
}
