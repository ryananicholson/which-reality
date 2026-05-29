import { useState, useEffect, useRef } from 'react'

const API = import.meta.env.VITE_API_URL || ''

// ── Styles ─────────────────────────────────────────────────────────────────────────
const S = {
  page: {
    minHeight: '100vh',
    background: '#0f1117',
    color: '#e2e8f0',
    fontFamily: "'Inter', sans-serif",
    padding: '0 0 60px',
  },
  hero: {
    background: 'linear-gradient(135deg, #0d1f3c 0%, #1a0a2e 50%, #0d1f3c 100%)',
    borderBottom: '1px solid #2d3748',
    padding: '28px 20px 24px',
    textAlign: 'center',
  },
  heroTitle: {
    fontSize: '22px',
    fontWeight: 800,
    color: '#fff',
    margin: '0 0 4px',
    letterSpacing: '-0.3px',
  },
  heroSub: {
    fontSize: '13px',
    color: '#718096',
    margin: '0 0 18px',
  },
  scanBtn: {
    background: 'linear-gradient(135deg, #6c63ff, #a855f7)',
    color: '#fff',
    border: 'none',
    borderRadius: '10px',
    padding: '11px 28px',
    fontSize: '14px',
    fontWeight: 700,
    cursor: 'pointer',
    letterSpacing: '0.3px',
  },
  scanBtnDisabled: {
    background: '#2d3748',
    color: '#718096',
    border: 'none',
    borderRadius: '10px',
    padding: '11px 28px',
    fontSize: '14px',
    fontWeight: 700,
    cursor: 'not-allowed',
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '10px',
    marginTop: '14px',
    fontSize: '12px',
    color: '#718096',
  },
  progressWrap: {
    width: '220px',
    height: '4px',
    background: '#2d3748',
    borderRadius: '2px',
    overflow: 'hidden',
  },
  progressBar: (pct) => ({
    width: `${Math.round(pct * 100)}%`,
    height: '100%',
    background: 'linear-gradient(90deg, #6c63ff, #a855f7)',
    borderRadius: '2px',
    transition: 'width 0.4s ease',
  }),
  section: {
    padding: '24px 16px 8px',
    maxWidth: '800px',
    margin: '0 auto',
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '16px',
  },
  sectionTitle: {
    fontSize: '17px',
    fontWeight: 800,
    color: '#fff',
    margin: 0,
  },
  sectionBadge: (color) => ({
    background: color,
    color: '#fff',
    borderRadius: '6px',
    padding: '2px 9px',
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '0.4px',
  }),
  sectionDesc: {
    fontSize: '12px',
    color: '#718096',
    marginBottom: '14px',
    lineHeight: 1.5,
  },
  card: {
    background: '#1a202c',
    borderRadius: '14px',
    border: '1px solid #2d3748',
    marginBottom: '14px',
    overflow: 'hidden',
  },
  cardHeader: {
    padding: '14px 16px 10px',
    borderBottom: '1px solid #2d3748',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: '10px',
  },
  cardTicker: {
    fontSize: '18px',
    fontWeight: 800,
    color: '#fff',
    letterSpacing: '-0.3px',
  },
  cardName: {
    fontSize: '12px',
    color: '#718096',
    marginTop: '1px',
  },
  cardSector: {
    fontSize: '11px',
    color: '#4a5568',
    background: '#2d3748',
    borderRadius: '5px',
    padding: '2px 7px',
    whiteSpace: 'nowrap',
  },
  cardBody: {
    padding: '12px 16px',
  },
  thesis: {
    fontSize: '13px',
    color: '#cbd5e0',
    lineHeight: 1.6,
    marginBottom: '12px',
  },
  metrics: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    marginBottom: '12px',
  },
  metric: {
    background: '#2d3748',
    borderRadius: '7px',
    padding: '5px 10px',
    fontSize: '11px',
    color: '#a0aec0',
    display: 'flex',
    flexDirection: 'column',
    gap: '1px',
  },
  metricLabel: {
    color: '#718096',
    fontSize: '10px',
  },
  metricValue: {
    color: '#e2e8f0',
    fontWeight: 700,
    fontSize: '12px',
  },
  catalystBox: {
    background: 'rgba(108,99,255,0.08)',
    borderLeft: '3px solid #6c63ff',
    borderRadius: '0 6px 6px 0',
    padding: '8px 10px',
    marginBottom: '8px',
  },
  catalystLabel: {
    fontSize: '10px',
    color: '#6c63ff',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '2px',
  },
  catalystText: {
    fontSize: '12px',
    color: '#a0aec0',
    lineHeight: 1.4,
  },
  riskBox: {
    background: 'rgba(252,129,74,0.07)',
    borderLeft: '3px solid #fc814a',
    borderRadius: '0 6px 6px 0',
    padding: '8px 10px',
  },
  riskLabel: {
    fontSize: '10px',
    color: '#fc814a',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '2px',
  },
  riskText: {
    fontSize: '12px',
    color: '#a0aec0',
    lineHeight: 1.4,
  },
  keyMetricBadge: {
    display: 'inline-block',
    background: 'rgba(104,211,145,0.12)',
    color: '#68d391',
    borderRadius: '6px',
    padding: '3px 9px',
    fontSize: '11px',
    fontWeight: 700,
    marginBottom: '10px',
  },
  insiderBuyBadge: {
    display: 'inline-block',
    background: 'rgba(104,211,145,0.15)',
    color: '#68d391',
    border: '1px solid rgba(104,211,145,0.3)',
    borderRadius: '6px',
    padding: '3px 9px',
    fontSize: '11px',
    fontWeight: 700,
    marginBottom: '10px',
    marginLeft: '6px',
  },
  insiderSellBadge: {
    display: 'inline-block',
    background: 'rgba(252,129,74,0.12)',
    color: '#fc814a',
    border: '1px solid rgba(252,129,74,0.3)',
    borderRadius: '6px',
    padding: '3px 9px',
    fontSize: '11px',
    fontWeight: 700,
    marginBottom: '10px',
    marginLeft: '6px',
  },
  emptyState: {
    textAlign: 'center',
    padding: '40px 20px',
    color: '#718096',
    fontSize: '14px',
  },
  scanNote: {
    fontSize: '12px',
    color: '#718096',
    textAlign: 'center',
    padding: '12px 20px 0',
    lineHeight: 1.5,
  },
  bullCaseBox: {
    background: 'rgba(104,211,145,0.06)',
    borderLeft: '3px solid #68d391',
    borderRadius: '0 6px 6px 0',
    padding: '8px 10px',
    marginTop: '8px',
    marginBottom: '8px',
  },
  bullCaseLabel: {
    fontSize: '10px',
    color: '#68d391',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '2px',
  },
  bearCaseBox: {
    background: 'rgba(252,129,74,0.07)',
    borderLeft: '3px solid #fc814a',
    borderRadius: '0 6px 6px 0',
    padding: '8px 10px',
  },
  bearCaseLabel: {
    fontSize: '10px',
    color: '#fc814a',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '2px',
  },
  dcfSection: {
    marginTop: '14px',
    borderTop: '1px solid #2d3748',
    paddingTop: '12px',
  },
  dcfTitle: {
    fontSize: '10px',
    color: '#718096',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '8px',
  },
  dcfGrid: {
    display: 'flex',
    gap: '6px',
    marginBottom: '10px',
  },
  dcfCell: (color) => ({
    flex: 1,
    background: '#2d3748',
    borderRadius: '8px',
    padding: '8px 6px',
    textAlign: 'center',
    borderTop: `2px solid ${color}`,
  }),
  dcfCellLabel: {
    fontSize: '10px',
    color: '#718096',
    marginBottom: '4px',
  },
  dcfCellValue: {
    fontSize: '13px',
    fontWeight: 700,
    marginBottom: '2px',
  },
  dcfCellUpside: {
    fontSize: '11px',
  },
  dcfRecsRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flexWrap: 'wrap',
  },
  recBadge: (color) => ({
    fontSize: '11px',
    fontWeight: 700,
    color,
    background: `${color}18`,
    border: `1px solid ${color}40`,
    borderRadius: '6px',
    padding: '3px 10px',
  }),
  dcfNote: {
    fontSize: '10px',
    color: '#4a5568',
    marginLeft: 'auto',
  },
}

// ── Subcomponents ──────────────────────────────────────────────────────────────────────

function fmtDcfVal(m) {
  if (m == null) return '—'
  if (m >= 1_000_000) return `$${(m / 1_000_000).toFixed(1)}T`
  if (m >= 1_000) return `$${(m / 1_000).toFixed(0)}B`
  return `$${Math.round(m)}M`
}

function fmtPrice(p) {
  if (p == null) return null
  if (p >= 10_000) return `$${(Math.round(p / 100) * 100).toLocaleString()}`
  if (p >= 1_000) return `$${(Math.round(p / 10) * 10).toLocaleString()}`
  if (p >= 100) return `$${Math.round(p)}`
  if (p >= 10) return `$${p.toFixed(1)}`
  return `$${p.toFixed(2)}`
}

const REC_COLORS = {
  'Strong Buy': '#48bb78',
  'Buy': '#68d391',
  'Hold': '#f6ad55',
  'Pass': '#fc8181',
}

function DcfSection({ pick }) {
  if (pick.dcf_base == null) return null

  const scenarios = [
    { label: 'Bear', val: pick.dcf_bear, price: pick.dcf_bear_price, upside: pick.dcf_bear_upside, color: '#fc8181' },
    { label: 'Base', val: pick.dcf_base, price: pick.dcf_base_price, upside: pick.dcf_base_upside, color: '#f6ad55' },
    { label: 'Bull', val: pick.dcf_bull, price: pick.dcf_bull_price, upside: pick.dcf_bull_upside, color: '#68d391' },
  ]

  const dcfRec = pick.dcf_recommendation
  const dcfColor = REC_COLORS[dcfRec] || '#718096'
  const aiRec = pick.long_term_rec
  const aiColor = REC_COLORS[aiRec] || '#718096'
  const currPriceStr = pick.current_price ? fmtPrice(pick.current_price) : null

  return (
    <div style={S.dcfSection}>
      <div style={S.dcfTitle}>
        📊 DCF Intrinsic Value (10-yr model){currPriceStr && <span style={{ color: '#4a5568', fontWeight: 400, textTransform: 'none', marginLeft: '6px' }}>· current {currPriceStr}</span>}
      </div>
      <div style={S.dcfGrid}>
        {scenarios.map(s => (
          <div key={s.label} style={S.dcfCell(s.color)}>
            <div style={S.dcfCellLabel}>{s.label}</div>
            <div style={{ ...S.dcfCellValue, color: s.color }}>{fmtDcfVal(s.val)}</div>
            {fmtPrice(s.price) && (
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#e2e8f0', marginBottom: '2px' }}>
                {fmtPrice(s.price)}
              </div>
            )}
            <div style={{ ...S.dcfCellUpside, color: (s.upside ?? 0) >= 0 ? '#68d391' : '#fc8181' }}>
              {s.upside != null ? `${s.upside >= 0 ? '+' : ''}${s.upside}%` : '—'}
            </div>
          </div>
        ))}
      </div>
      <div style={S.dcfRecsRow}>
        {dcfRec && <span style={S.recBadge(dcfColor)}>{dcfRec}</span>}
        {aiRec && <span style={S.recBadge(aiColor)}>AI: {aiRec}</span>}
        {pick.market_cap_b > 0 && (
          <span style={S.dcfNote}>vs ${pick.market_cap_b}B current mkt cap</span>
        )}
      </div>
    </div>
  )
}

function MetricChip({ label, value, accent }) {
  if (!value && value !== 0) return null
  const valueColor = accent === 'green' ? '#68d391' : accent === 'red' ? '#fc8181' : '#e2e8f0'
  return (
    <div style={S.metric}>
      <span style={S.metricLabel}>{label}</span>
      <span style={{ ...S.metricValue, color: valueColor }}>{value}</span>
    </div>
  )
}

function PickCard({ pick }) {
  const mc   = pick.market_cap_b > 0 ? `$${pick.market_cap_b}B` : null
  const revG = pick.revenue_growth_pct !== 0 ? `${pick.revenue_growth_pct > 0 ? '+' : ''}${pick.revenue_growth_pct}%` : null
  const gm   = pick.gross_margin_pct > 0 ? `${pick.gross_margin_pct}%` : null
  const pe   = pick.pe ? `${pick.pe}x` : null
  const ps   = pick.ps ? `${pick.ps}x` : null
  const roe  = pick.roe_pct !== 0 ? `${pick.roe_pct}%` : null
  const fcf  = pick.fcf_margin_pct != null && pick.fcf_margin_pct !== 0 ? `${pick.fcf_margin_pct}%` : null
  const roic = pick.roic_pct != null && pick.roic_pct !== 0 ? `${pick.roic_pct}%` : null
  const mom  = pick.return_6m_pct != null ? `${pick.return_6m_pct > 0 ? '+' : ''}${pick.return_6m_pct}%` : null
  const accel = pick.rev_accel_pct != null && Math.abs(pick.rev_accel_pct) >= 3
    ? `${pick.rev_accel_pct > 0 ? '↑' : '↓'}${Math.abs(pick.rev_accel_pct).toFixed(1)}%`
    : null
  const dtc = pick.days_to_cover != null && pick.days_to_cover > 3
    ? `${pick.days_to_cover}d` : null

  return (
    <div style={S.card}>
      <div style={S.cardHeader}>
        <div>
          <div style={S.cardTicker}>{pick.ticker}</div>
          <div style={S.cardName}>{pick.name}</div>
        </div>
        {pick.sector && <div style={S.cardSector}>{pick.sector}</div>}
      </div>
      <div style={S.cardBody}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0', alignItems: 'center', marginBottom: pick.key_metric || pick.insider_signal !== 'neutral' ? '0' : '0' }}>
          {pick.key_metric && (
            <div style={{ ...S.keyMetricBadge, marginLeft: 0 }}>⭐ {pick.key_metric}</div>
          )}
          {pick.insider_signal === 'buy' && (pick.insiders_buying ?? 0) >= 2 && (
            <div style={S.insiderBuyBadge}>🏦 Insiders Buying ({pick.insiders_buying})</div>
          )}
          {pick.insider_signal === 'sell' && (pick.insiders_selling ?? 0) >= 2 && (
            <div style={S.insiderSellBadge}>⚠️ Insiders Selling ({pick.insiders_selling})</div>
          )}
        </div>
        <p style={S.thesis}>{pick.thesis}</p>
        <div style={S.metrics}>
          {mc   && <MetricChip label="Mkt Cap" value={mc} />}
          {revG && <MetricChip label="Rev Growth" value={revG} accent={pick.revenue_growth_pct > 0 ? 'green' : 'red'} />}
          {accel && <MetricChip label="Acceleration" value={accel} accent={pick.rev_accel_pct > 0 ? 'green' : 'red'} />}
          {gm   && <MetricChip label="Gross Margin" value={gm} />}
          {fcf  && <MetricChip label="FCF Margin" value={fcf} />}
          {mom  && <MetricChip label="6mo Return" value={mom} accent={pick.return_6m_pct > 0 ? 'green' : 'red'} />}
          {pe   && <MetricChip label="P/E" value={pe} />}
          {ps   && <MetricChip label="P/S" value={ps} />}
          {roe  && <MetricChip label="ROE" value={roe} />}
          {roic && <MetricChip label="ROIC" value={roic} />}
          {dtc  && <MetricChip label="Short DTC" value={dtc} accent={pick.days_to_cover > 10 ? 'green' : null} />}
        </div>
        {(pick.bull_case || pick.catalyst) && (
          <div style={S.bullCaseBox}>
            <div style={S.bullCaseLabel}>🐂 Bull Case</div>
            <div style={S.catalystText}>{pick.bull_case || pick.catalyst}</div>
          </div>
        )}
        {(pick.bear_case || pick.risk) && (
          <div style={S.bearCaseBox}>
            <div style={S.bearCaseLabel}>🐻 Bear Case</div>
            <div style={S.riskText}>{pick.bear_case || pick.risk}</div>
          </div>
        )}
        <DcfSection pick={pick} />
      </div>
    </div>
  )
}

function SectionHeader({ emoji, title, badge, badgeColor, desc }) {
  return (
    <>
      <div style={S.sectionHeader}>
        <h2 style={S.sectionTitle}>{emoji} {title}</h2>
        <span style={S.sectionBadge(badgeColor)}>{badge}</span>
      </div>
      <p style={S.sectionDesc}>{desc}</p>
    </>
  )
}

// ── Main Tab ─────────────────────────────────────────────────────────────────────────

export default function DiscoveryTab() {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const pollRef = useRef(null)

  const fetchState = async () => {
    try {
      const res = await fetch(`${API}/api/discovery`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setState(data)
      return data.status
    } catch (e) {
      console.error('Discovery fetch error:', e)
      return 'error'
    } finally {
      setLoading(false)
    }
  }

  const startPolling = () => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      const status = await fetchState()
      if (status !== 'scanning') {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }, 4000)
  }

  useEffect(() => {
    fetchState().then((status) => {
      if (status === 'scanning') startPolling()
    })
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const handleScan = async () => {
    try {
      await fetch(`${API}/api/discovery/scan`, { method: 'POST' })
      setState((prev) => ({ ...prev, status: 'scanning', progress: 0 }))
      startPolling()
    } catch (e) {
      console.error('Scan trigger error:', e)
    }
  }

  const isScanning = state?.status === 'scanning'
  const hasResults = state?.status === 'ready' && state?.results
  const generatedAt = state?.generated_at
    ? new Date(state.generated_at).toLocaleString()
    : null

  return (
    <div style={S.page}>
      {/* Hero */}
      <div style={S.hero}>
        <h1 style={S.heroTitle}>🔭 Stock Discovery</h1>
        <p style={S.heroSub}>
          Scanning {state?.results?.universe_size || '~300'} tickers for life-changing opportunities
        </p>
        <button
          style={isScanning ? S.scanBtnDisabled : S.scanBtn}
          onClick={handleScan}
          disabled={isScanning}
        >
          {isScanning ? '⏳ Scanning...' : '🚀 Run Discovery Scan'}
        </button>
        {isScanning && (
          <div style={S.statusRow}>
            <div style={S.progressWrap}>
              <div style={S.progressBar(state?.progress || 0)} />
            </div>
            <span>{Math.round((state?.progress || 0) * 100)}%</span>
          </div>
        )}
        {!isScanning && generatedAt && (
          <div style={S.statusRow}>
            <span>Last scan: {generatedAt}</span>
            {state?.results && (
              <span>· {state.results.fundamentals_fetched} companies analyzed</span>
            )}
          </div>
        )}
        {!isScanning && !hasResults && !loading && (
          <p style={S.scanNote}>
            Click "Run Discovery Scan" to analyze ~300 stocks across all sectors.<br />
            Takes ~5–7 minutes. Results are cached for 24 hours.
          </p>
        )}
      </div>

      {/* Scanning placeholder */}
      {isScanning && !hasResults && (
        <div style={S.emptyState}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
          <div style={{ fontWeight: 700, color: '#e2e8f0', marginBottom: '6px' }}>
            Scanning the market...
          </div>
          <div>Fetching fundamentals, scoring companies, and writing AI theses.</div>
          <div style={{ marginTop: '6px' }}>This takes 5–7 minutes. Hang tight.</div>
        </div>
      )}

      {/* Error */}
      {state?.status === 'error' && (
        <div style={{ ...S.emptyState, color: '#fc8181' }}>
          ⚠️ Scan failed: {state.error || 'Unknown error'}. Try again.
        </div>
      )}

      {/* Claude fallback notice */}
      {hasResults && state.results?.claude_fallback && (
        <div style={{
          margin: '16px auto 0', maxWidth: '800px', padding: '0 16px',
        }}>
          <div style={{
            background: '#2d2000', border: '1px solid #b7791f',
            borderRadius: '8px', padding: '10px 14px',
            fontSize: '13px', color: '#fbd38d',
          }}>
            ⚠️ AI thesis generation failed (Claude API error) — showing top-ranked candidates by quant score. Theses will populate on the next successful scan.
          </div>
        </div>
      )}

      {/* Results */}
      {hasResults && (
        <>
          {/* Next Compounders */}
          <div style={S.section}>
            <SectionHeader
              emoji="🚀"
              title="Next Compounder"
              badge="High Growth"
              badgeColor="linear-gradient(135deg,#6c63ff,#a855f7)"
              desc="High-growth companies with dominant market positions and scalable business models — the profile of NVDA, TSLA, and PLTR before they became household names."
            />
            {state.results.compounders.length === 0 ? (
              <div style={S.emptyState}>No compounder picks found in this scan.</div>
            ) : (
              state.results.compounders.map((pick) => (
                <PickCard key={pick.ticker} pick={pick} />
              ))
            )}
          </div>

          <div style={{ height: '8px', background: '#0f1117' }} />

          {/* Sleeper Picks */}
          <div style={S.section}>
            <SectionHeader
              emoji="💎"
              title="Sleeper Picks"
              badge="Hidden Value"
              badgeColor="linear-gradient(135deg,#38b2ac,#4299e1)"
              desc="Profitable, under-the-radar companies with strong moats and growing earnings that Wall Street hasn't fully discovered yet."
            />
            {state.results.sleepers.length === 0 ? (
              <div style={S.emptyState}>No sleeper picks found in this scan.</div>
            ) : (
              state.results.sleepers.map((pick) => (
                <PickCard key={pick.ticker} pick={pick} />
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}
