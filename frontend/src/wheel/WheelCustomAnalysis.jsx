import { useState } from 'react'
import { api } from '../api'
import ScoreBar from '../components/ScoreBar'
import GradeChip from '../components/GradeChip'
import TradingViewWidget from '../components/TradingViewWidget'

const POPULAR = ['AAPL', 'MSFT', 'AMZN', 'COST', 'KO', 'AMD', 'NVDA', 'JNJ', 'V', 'HD']

const TIER_COLORS = {
  0: { bg: '#1a120a', border: '#744210', label: '#ed8936', badge: '#c05621' },
  1: { bg: '#0a1520', border: '#2b6cb0', label: '#63b3ed', badge: '#2c5282' },
  2: { bg: '#0a1a12', border: '#276749', label: '#68d391', badge: '#276749' },
}

const s = {
  wrap: {
    background: '#131825',
    border: '1px solid #2d3748',
    borderRadius: '12px',
    padding: '24px',
    marginBottom: '32px',
  },
  sectionTitle: {
    fontSize: '16px', fontWeight: 700, color: '#e2e8f0', marginBottom: '4px',
  },
  subtitle: { fontSize: '13px', color: '#718096', marginBottom: '20px' },
  searchRow: { display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '12px' },
  input: {
    flex: '1', minWidth: '140px', maxWidth: '200px',
    padding: '10px 14px',
    background: '#1a1f2e', border: '1px solid #2d3748', borderRadius: '8px',
    color: '#e2e8f0', fontSize: '16px', fontWeight: 700,
    textTransform: 'uppercase', letterSpacing: '0.08em', outline: 'none',
  },
  btn: (disabled) => ({
    padding: '10px 20px',
    background: disabled ? '#2d3748' : '#276749',
    color: disabled ? '#718096' : '#fff',
    border: 'none', borderRadius: '8px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: '14px', fontWeight: 600, whiteSpace: 'nowrap',
  }),
  chips: { display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '20px' },
  chip: {
    padding: '4px 12px', background: '#1a1f2e',
    border: '1px solid #2d3748', borderRadius: '20px',
    color: '#a0aec0', fontSize: '12px', fontWeight: 600, cursor: 'pointer',
  },
  error: { color: '#fc8181', fontSize: '13px', padding: '12px 0' },
  resultWrap: { display: 'flex', flexDirection: 'column', gap: '20px' },
  ratingRow: { display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' },
  tickerLabel: { fontSize: '26px', fontWeight: 800, color: '#90cdf4' },
  priceLabel: { fontSize: '20px', fontWeight: 700, color: '#e2e8f0' },
  ratingBadge: (r) => ({
    padding: '6px 18px', borderRadius: '6px', fontWeight: 800, fontSize: '14px',
    letterSpacing: '0.06em',
    background: r === 'GOOD' ? '#0d2218' : r === 'AVOID' ? '#220d0d' : '#1a1a0d',
    color: r === 'GOOD' ? '#68d391' : r === 'AVOID' ? '#fc8181' : '#f6e05e',
    border: `1px solid ${r === 'GOOD' ? '#276749' : r === 'AVOID' ? '#742a2a' : '#744210'}`,
  }),
  label: {
    fontSize: '11px', color: '#718096', textTransform: 'uppercase',
    letterSpacing: '0.06em', fontWeight: 600, marginBottom: '6px',
  },
  assessmentBox: {
    background: '#0d1117', border: '1px solid #2d3748',
    borderRadius: '8px', padding: '14px 16px',
    fontSize: '14px', color: '#cbd5e0', lineHeight: 1.7,
  },
  tiersGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: '14px',
  },
  tierCard: (i) => ({
    background: TIER_COLORS[i].bg,
    border: `1px solid ${TIER_COLORS[i].border}`,
    borderRadius: '10px', padding: '16px',
    display: 'flex', flexDirection: 'column', gap: '10px',
  }),
  tierLabel: (i) => ({
    fontSize: '12px', fontWeight: 700, textTransform: 'uppercase',
    letterSpacing: '0.05em', color: TIER_COLORS[i].label,
    marginBottom: '2px',
  }),
  tierStrike: { fontSize: '24px', fontWeight: 800, color: '#e2e8f0' },
  tierExpiry: { fontSize: '12px', color: '#718096', marginTop: '-6px' },
  premiumBig: { fontSize: '18px', fontWeight: 700, color: '#68d391' },
  divider: { borderTop: '1px solid rgba(255,255,255,0.06)', margin: '4px 0' },
  factRow: { display: 'flex', flexDirection: 'column', gap: '2px' },
  factLabel: { fontSize: '10px', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.04em' },
  factValue: { fontSize: '13px', color: '#a0aec0', lineHeight: 1.5 },
  bestFor: {
    fontSize: '11px', color: '#718096', fontStyle: 'italic',
    borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px', marginTop: '4px',
  },
  verdictBox: {
    background: '#0d1420', border: '1px solid #2b6cb0',
    borderRadius: '8px', padding: '14px 16px',
    fontSize: '14px', color: '#bee3f8', lineHeight: 1.7,
  },
  ivBox: {
    background: '#0d1117', border: '1px solid #2d3748',
    borderRadius: '8px', padding: '12px 14px',
    fontSize: '13px', color: '#a0aec0', lineHeight: 1.6,
  },
}

function TierCard({ tier, idx }) {
  if (!tier) return (
    <div style={s.tierCard(idx)}>
      <div style={s.tierLabel(idx)}>No suitable option found</div>
    </div>
  )
  return (
    <div style={s.tierCard(idx)}>
      <div>
        <div style={s.tierLabel(idx)}>{tier.tier_name}</div>
        <div style={s.tierStrike}>${tier.strike}</div>
        <div style={s.tierExpiry}>Expires {tier.expiry} · {tier.dte} days</div>
      </div>

      <div style={s.premiumBig}>{tier.premium_plain}</div>

      <div style={s.divider} />

      <div style={s.factRow}>
        <span style={s.factLabel}>Chance of buying the shares</span>
        <span style={s.factValue}>{tier.assignment_plain}</span>
      </div>
      <div style={s.factRow}>
        <span style={s.factLabel}>Daily time-decay income</span>
        <span style={s.factValue}>{tier.time_decay_plain}</span>
      </div>
      <div style={s.factRow}>
        <span style={s.factLabel}>Your protection</span>
        <span style={s.factValue}>{tier.protection_plain}</span>
      </div>
      <div style={s.factRow}>
        <span style={s.factLabel}>Annualized return</span>
        <span style={s.factValue}>{tier.return_plain}</span>
      </div>

      {tier.best_for && (
        <div style={s.bestFor}>Best for: {tier.best_for}</div>
      )}
    </div>
  )
}

export default function WheelCustomAnalysis() {
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const analyze = async (sym) => {
    const symbol = (sym || ticker).trim().toUpperCase()
    if (!symbol) return
    setTicker(symbol)
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.wheel.customAnalyze(symbol)
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.wrap}>
      <div style={s.sectionTitle}>🔍 Analyze Any Stock for Wheel Strategy</div>
      <div style={s.subtitle}>
        Enter a ticker and the AI will pull live options data to show you the best put-selling opportunities
      </div>

      <div style={s.searchRow}>
        <input
          style={s.input}
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && analyze()}
          placeholder="e.g. AAPL"
          maxLength={5}
        />
        <button
          style={s.btn(loading || !ticker.trim())}
          onClick={() => analyze()}
          disabled={loading || !ticker.trim()}
        >
          {loading ? '⏳ Analyzing...' : '▶ Analyze'}
        </button>
      </div>

      <div style={s.chips}>
        {POPULAR.map((sym) => (
          <button key={sym} style={s.chip} onClick={() => analyze(sym)}>{sym}</button>
        ))}
      </div>

      {error && <div style={s.error}>⚠ {error}</div>}

      {result && (
        <div style={s.resultWrap}>
          {/* Header */}
          <div style={s.ratingRow}>
            <span style={s.tickerLabel}>{result.ticker}</span>
            <span style={s.priceLabel}>${Number(result.current_price).toFixed(2)}</span>
            <span style={s.ratingBadge(result.wheel_rating)}>
              {result.wheel_rating === 'GOOD' ? '✓ Good Wheel Stock' :
               result.wheel_rating === 'AVOID' ? '✗ Avoid for Wheel' : '~ Neutral'}
            </span>
            <GradeChip grade={result.grade} />
          </div>

          <div>
            <div style={s.label}>Confidence</div>
            <ScoreBar score={result.wheel_score} />
          </div>

          <TradingViewWidget ticker={result.ticker} />

          {/* Company assessment */}
          {result.company_assessment && (
            <div>
              <div style={s.label}>Is this a good company to own if assigned?</div>
              <div style={s.assessmentBox}>{result.company_assessment}</div>
            </div>
          )}

          {/* IV environment */}
          {result.iv_environment_plain && (
            <div>
              <div style={s.label}>Options market conditions</div>
              <div style={s.ivBox}>{result.iv_environment_plain}</div>
            </div>
          )}

          {/* Chart setup */}
          {result.technicals_plain && (
            <div>
              <div style={s.label}>Chart setup</div>
              <div style={s.ivBox}>{result.technicals_plain}</div>
            </div>
          )}

          {/* 3 put tiers */}
          {result.tiers?.length > 0 && (
            <div>
              <div style={s.label}>Put-Selling Options (Live Market Prices)</div>
              <div style={s.tiersGrid}>
                {result.tiers.map((tier, i) => (
                  <TierCard key={i} tier={tier} idx={i} />
                ))}
              </div>
            </div>
          )}

          {/* Overall verdict */}
          {result.overall_verdict && (
            <div>
              <div style={s.label}>Our recommendation</div>
              <div style={s.verdictBox}>{result.overall_verdict}</div>
            </div>
          )}

          <div style={{ fontSize: '11px', color: '#4a5568' }}>
            {result.data_source === 'live'
              ? 'Live bid/ask from Yahoo Finance (market hours). Prices may differ slightly from your broker.'
              : 'Prices from last recorded trades — markets are currently closed. Refresh during market hours for live bid/ask.'}
            {' '}Not financial advice.
          </div>
        </div>
      )}
    </div>
  )
}
