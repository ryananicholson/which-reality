import { useState } from 'react'
import { api } from '../api'

const TIER_CONFIG = {
  aggressive: {
    label: 'Aggressive',
    sublabel: 'Highest income · Shares likely sold',
    borderColor: '#c53030',
    bg: '#1f0a0a',
    headerBg: '#3a1212',
    accentColor: '#fc8181',
    icon: '🔴',
  },
  balanced: {
    label: 'Balanced',
    sublabel: 'Good income · Moderate risk',
    borderColor: '#b7791f',
    bg: '#1a1400',
    headerBg: '#2d2200',
    accentColor: '#f6e05e',
    icon: '🟡',
  },
  conservative: {
    label: 'Conservative',
    sublabel: 'Keep shares · Lower premium',
    borderColor: '#276749',
    bg: '#071410',
    headerBg: '#0d2218',
    accentColor: '#68d391',
    icon: '🟢',
  },
}

const QUICK_TICKERS = ['BMNR', 'SCHD', 'VTI', 'QQQM', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'COIN', 'PLTR']

const s = {
  header: { marginBottom: '24px' },
  title: { fontSize: '20px', fontWeight: 700, color: '#e2e8f0', marginBottom: '4px' },
  subtitle: { fontSize: '13px', color: '#718096' },
  formRow: {
    display: 'flex',
    gap: '10px',
    marginBottom: '16px',
    alignItems: 'flex-end',
    flexWrap: 'wrap',
  },
  inputGroup: { display: 'flex', flexDirection: 'column', gap: '4px' },
  label: { fontSize: '11px', color: '#718096', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' },
  tickerInput: {
    width: '120px',
    padding: '10px 14px',
    background: '#1a1f2e',
    border: '1px solid #2d3748',
    borderRadius: '8px',
    color: '#e2e8f0',
    fontSize: '16px',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    outline: 'none',
  },
  costInput: {
    width: '130px',
    padding: '10px 14px',
    background: '#1a1f2e',
    border: '1px solid #2d3748',
    borderRadius: '8px',
    color: '#e2e8f0',
    fontSize: '14px',
    outline: 'none',
  },
  generateBtn: (loading) => ({
    padding: '10px 22px',
    background: loading ? '#2d3748' : '#2b6cb0',
    color: loading ? '#718096' : '#fff',
    border: 'none',
    borderRadius: '8px',
    cursor: loading ? 'not-allowed' : 'pointer',
    fontSize: '14px',
    fontWeight: 600,
    alignSelf: 'flex-end',
    whiteSpace: 'nowrap',
  }),
  quickRow: { display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' },
  chip: {
    padding: '4px 11px',
    background: '#1a1f2e',
    border: '1px solid #2d3748',
    borderRadius: '20px',
    color: '#a0aec0',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  hint: { fontSize: '12px', color: '#4a5568', marginBottom: '24px' },
  error: { color: '#fc8181', padding: '14px 16px', background: '#2d1515', border: '1px solid #742a2a', borderRadius: '8px', fontSize: '14px', marginBottom: '20px' },
  metaBar: {
    display: 'flex',
    gap: '20px',
    flexWrap: 'wrap',
    alignItems: 'center',
    background: '#1a1f2e',
    border: '1px solid #2d3748',
    borderRadius: '8px',
    padding: '12px 16px',
    marginBottom: '20px',
    fontSize: '13px',
    color: '#a0aec0',
  },
  metaItem: { display: 'flex', flexDirection: 'column', gap: '2px' },
  metaLabel: { fontSize: '10px', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 },
  metaValue: { fontSize: '14px', fontWeight: 700, color: '#e2e8f0' },
  ivNote: { fontSize: '13px', color: '#90cdf4', fontStyle: 'italic', flex: 1 },
  tiersGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '16px',
    marginBottom: '20px',
  },
  tierCard: (cfg) => ({
    background: cfg.bg,
    border: `1px solid ${cfg.borderColor}`,
    borderRadius: '12px',
    overflow: 'hidden',
  }),
  tierHeader: (cfg) => ({
    background: cfg.headerBg,
    borderBottom: `1px solid ${cfg.borderColor}`,
    padding: '14px 16px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  }),
  tierIcon: { fontSize: '20px' },
  tierLabelGroup: { flex: 1 },
  tierLabel: (cfg) => ({ fontSize: '16px', fontWeight: 700, color: cfg.accentColor }),
  tierSublabel: { fontSize: '11px', color: '#718096', marginTop: '1px' },
  premiumBig: (cfg) => ({
    fontSize: '22px',
    fontWeight: 800,
    color: cfg.accentColor,
    textAlign: 'right',
  }),
  premiumLabel: { fontSize: '10px', color: '#718096', textAlign: 'right', marginTop: '1px' },
  tierBody: { padding: '16px' },
  section: { marginBottom: '14px' },
  sectionLabel: {
    fontSize: '10px',
    color: '#718096',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontWeight: 600,
    marginBottom: '5px',
  },
  sectionText: { fontSize: '13px', color: '#cbd5e0', lineHeight: 1.6 },
  statsRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '8px',
    marginBottom: '14px',
  },
  statBox: {
    background: 'rgba(0,0,0,0.3)',
    borderRadius: '6px',
    padding: '8px 10px',
  },
  statLabel: { fontSize: '10px', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 },
  statValue: { fontSize: '14px', fontWeight: 700, color: '#e2e8f0', marginTop: '2px' },
  bestFor: (cfg) => ({
    fontSize: '12px',
    color: cfg.accentColor,
    fontStyle: 'italic',
    padding: '8px 10px',
    background: 'rgba(0,0,0,0.3)',
    borderRadius: '6px',
    lineHeight: 1.5,
  }),
  thinWarning: {
    fontSize: '12px',
    color: '#f6e05e',
    background: '#2d2200',
    border: '1px solid #b7791f',
    borderRadius: '6px',
    padding: '6px 10px',
    marginTop: '10px',
  },
  disclaimer: { fontSize: '11px', color: '#4a5568', marginTop: '16px' },
  dataSourceNote: { fontSize: '12px', color: '#4a5568', marginTop: '4px' },
  statPill: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  statVal: { fontSize: '14px', fontWeight: 700, color: '#e2e8f0' },
}

function fmt(val) {
  if (val == null) return '—'
  return `$${Number(val).toFixed(2)}`
}

function TierCard({ tier, data, cfg }) {
  if (!data) return null
  const rawTier = tier    // 'aggressive' | 'balanced' | 'conservative'

  return (
    <div style={s.tierCard(cfg)}>
      <div style={s.tierHeader(cfg)}>
        <span style={s.tierIcon}>{cfg.icon}</span>
        <div style={s.tierLabelGroup}>
          <div style={s.tierLabel(cfg)}>{cfg.label}</div>
          <div style={s.tierSublabel}>{cfg.sublabel}</div>
        </div>
        <div>
          <div style={s.premiumBig(cfg)}>{fmt(data.premium_per_contract)}</div>
          <div style={s.premiumLabel}>per contract</div>
        </div>
      </div>

      <div style={s.tierBody}>
        {/* Key stats */}
        <div style={s.statsRow}>
          <div style={s.statBox}>
            <div style={s.statLabel}>Strike</div>
            <div style={s.statValue}>{fmt(data.strike)}</div>
          </div>
          <div style={s.statBox}>
            <div style={s.statLabel}>Expiry</div>
            <div style={s.statValue}>{data.expiry} ({data.dte}d)</div>
          </div>
          <div style={s.statBox}>
            <div style={s.statLabel}>Call-Away Chance</div>
            <div style={s.statValue}>{data.call_away_chance_pct ?? '—'}%</div>
          </div>
          <div style={s.statBox}>
            <div style={s.statLabel}>Weekly Yield</div>
            <div style={s.statValue}>{data.pct_of_stock_weekly ?? '—'}%</div>
          </div>
        </div>

        {/* AI plain-English explanation */}
        {data.premium_plain && (
          <div style={s.section}>
            <div style={s.sectionLabel}>What you collect</div>
            <div style={s.sectionText}>{data.premium_plain}</div>
          </div>
        )}

        {data.callaway_plain && (
          <div style={s.section}>
            <div style={s.sectionLabel}>Chance of losing shares</div>
            <div style={s.sectionText}>{data.callaway_plain}</div>
          </div>
        )}

        {data.if_called_plain && (
          <div style={s.section}>
            <div style={s.sectionLabel}>If your shares get called away</div>
            <div style={s.sectionText}>{data.if_called_plain}</div>
          </div>
        )}

        {data.if_not_called_plain && (
          <div style={s.section}>
            <div style={s.sectionLabel}>If shares stay below strike</div>
            <div style={s.sectionText}>{data.if_not_called_plain}</div>
          </div>
        )}

        {data.best_for && (
          <div style={s.bestFor(cfg)}>Best for: {data.best_for}</div>
        )}

        {data.thin_market_note && (
          <div style={s.thinWarning}>⚠ {data.thin_market_note}</div>
        )}

        {data.below_threshold && !data.thin_market_note && (
          <div style={s.thinWarning}>
            ⚠ Premium is below 0.3%/week — options are thin on {rawTier} strikes this week
          </div>
        )}
      </div>
    </div>
  )
}

export default function CoveredCallsTab() {
  const [ticker, setTicker] = useState('')
  const [costBasis, setCostBasis] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const generate = async (sym) => {
    const symbol = (sym || ticker).trim().toUpperCase()
    if (!symbol) return
    setTicker(symbol)
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const cb = costBasis ? parseFloat(costBasis) : null
      const data = await api.coveredCalls.analyze(symbol, cb)
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter') generate()
  }

  const tiers = result?.tiers ?? []
  const tierMap = {}
  tiers.forEach((t) => { tierMap[t.tier] = t })

  return (
    <div>
      <div style={s.header}>
        <div style={s.title}>Covered Call Income Generator</div>
        <div style={s.subtitle}>
          Own 100 shares? Generate three call strategies to earn income — works with weekly and monthly options.
        </div>
      </div>

      <div style={s.formRow}>
        <div style={s.inputGroup}>
          <div style={s.label}>Ticker</div>
          <input
            style={s.tickerInput}
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={handleKey}
            placeholder="SCHD"
            maxLength={6}
            autoFocus
          />
        </div>
        <div style={s.inputGroup}>
          <div style={s.label}>Cost Basis / share (optional)</div>
          <input
            style={s.costInput}
            type="number"
            step="0.01"
            min="0"
            value={costBasis}
            onChange={(e) => setCostBasis(e.target.value)}
            onKeyDown={handleKey}
            placeholder="e.g. 28.50"
          />
        </div>
        <button
          style={s.generateBtn(loading)}
          onClick={() => generate()}
          disabled={loading || !ticker.trim()}
        >
          {loading ? '⏳ Analyzing...' : '📊 Generate Calls'}
        </button>
      </div>

      <div style={s.quickRow}>
        {QUICK_TICKERS.map((sym) => (
          <button key={sym} style={s.chip} onClick={() => generate(sym)}>{sym}</button>
        ))}
      </div>
      <div style={s.hint}>Click a ticker above or type your own — works for stocks and ETFs</div>

      {error && <div style={s.error}>⚠ {error}</div>}

      {result && (
        <>
          {/* Meta bar */}
          <div style={s.metaBar}>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Ticker</div>
              <div style={s.metaValue}>{result.ticker}</div>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Current Price</div>
              <div style={s.metaValue}>{fmt(result.current_price)}</div>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Expiry</div>
              <div style={s.metaValue}>{result.expiry} ({result.dte}d)</div>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Option Cycle</div>
              <div style={{
                ...s.metaValue,
                color: result.options_type === 'monthly' ? '#f6e05e' : '#68d391',
                fontSize: '13px',
                fontWeight: 700,
              }}>
                {result.options_type === 'monthly' ? '📅 Monthly' : '📆 Weekly'}
              </div>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>ATM IV</div>
              <div style={s.metaValue}>{result.atm_iv_pct ?? '—'}%</div>
            </div>
            {result.iv_rank?.iv_rank != null && (
              <div style={s.statPill}>
                <span style={s.statLabel}>IV Rank</span>
                <span style={{
                  ...s.statVal,
                  color: result.iv_rank.iv_rank >= 50 ? '#68d391' : result.iv_rank.iv_rank < 25 ? '#fc8181' : '#fbd38d'
                }}>
                  {result.iv_rank.iv_rank}
                  <span style={{ fontSize:'10px', color:'#718096', marginLeft:'3px' }}>/ 100</span>
                </span>
              </div>
            )}
            {result.iv_environment && (
              <div style={s.ivNote}>{result.iv_environment}</div>
            )}
          </div>

          {result.iv_rank?.label === 'high' && (
            <div style={{ fontSize:'12px', color:'#68d391', padding:'4px 0' }}>
              🔥 IV Rank {result.iv_rank.iv_rank} — premium is historically rich. Good time to sell calls.
            </div>
          )}
          {result.iv_rank?.label === 'low' && (
            <div style={{ fontSize:'12px', color:'#fc8181', padding:'4px 0' }}>
              ❄️ IV Rank {result.iv_rank.iv_rank} — premium is historically cheap. Consider waiting for higher IV.
            </div>
          )}

          {result.options_type === 'monthly' && (
            <div style={{ ...s.dataSourceNote, color: '#f6e05e', marginBottom: '8px' }}>
              📅 {result.ticker} uses monthly options — no weekly options are listed for this ticker.
              These strategies expire on {result.expiry}.
            </div>
          )}
          {result.data_source === 'last_trade' && (
            <div style={s.dataSourceNote}>
              ℹ Markets closed — using last-trade prices. Live bid/ask available during market hours.
            </div>
          )}
          {result.data_source === 'synthetic_bs' && (
            <div style={{ ...s.dataSourceNote, color: '#fbd38d', background: '#2d2000', border: '1px solid #b7791f', borderRadius: '6px', padding: '8px 12px' }}>
              🧮 Live options data unavailable — premiums are estimated using Black-Scholes with {result.atm_iv_pct}% historical volatility. Verify actual quotes with your broker before trading.
            </div>
          )}

          {/* Three tier cards */}
          <div style={s.tiersGrid}>
            {['aggressive', 'balanced', 'conservative'].map((tier) => (
              <TierCard
                key={tier}
                tier={tier}
                data={tierMap[tier]}
                cfg={TIER_CONFIG[tier]}
              />
            ))}
          </div>

          <div style={s.disclaimer}>
            AI analysis only — not financial advice. Verify strikes and premiums with your broker before trading.
          </div>
        </>
      )}
    </div>
  )
}
