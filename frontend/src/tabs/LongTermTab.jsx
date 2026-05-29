import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { useRefreshPoller } from '../hooks/useRefreshPoller'
import GradeChip from '../components/GradeChip'
import ScoreBar from '../components/ScoreBar'
import DualScorePanel from '../components/DualScorePanel'
import TradingViewWidget from '../components/TradingViewWidget'
import LastUpdated from '../components/LastUpdated'

const s = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px',
    flexWrap: 'wrap',
    gap: '12px',
  },
  title: { fontSize: '20px', fontWeight: 700, color: '#e2e8f0' },
  refreshBtn: {
    padding: '8px 16px',
    background: '#2b6cb0',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: 500,
  },
  filters: { display: 'flex', gap: '8px', marginBottom: '20px' },
  filterBtn: (active) => ({
    padding: '6px 14px',
    borderRadius: '20px',
    border: `1px solid ${active ? '#63b3ed' : '#2d3748'}`,
    background: active ? '#1a2f3a' : 'transparent',
    color: active ? '#63b3ed' : '#718096',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 500,
  }),
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))',
    gap: '16px',
  },
  card: {
    background: '#1a1f2e',
    border: '1px solid #2d3748',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  ticker: { fontSize: '22px', fontWeight: 800, color: '#90cdf4' },
  typeBadge: (type) => ({
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    background: type === 'growth' ? '#1a2a3a' : '#1a2f2a',
    color: type === 'growth' ? '#63b3ed' : '#68d391',
    border: `1px solid ${type === 'growth' ? '#2b6cb0' : '#276749'}`,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  }),
  rankBadge: {
    background: '#2d3748',
    color: '#a0aec0',
    borderRadius: '4px',
    padding: '2px 8px',
    fontSize: '11px',
    fontWeight: 600,
  },
  sectionLabel: { fontSize: '11px', color: '#718096', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  td: { padding: '5px 0', color: '#a0aec0', width: '50%' },
  tdVal: { padding: '5px 0', color: '#e2e8f0', fontWeight: 600, textAlign: 'right' },
  metaRow: { display: 'flex', gap: '16px', flexWrap: 'wrap' },
  metaItem: { display: 'flex', flexDirection: 'column', gap: '2px' },
  metaLabel: { fontSize: '10px', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em' },
  metaValue: { fontSize: '14px', color: '#e2e8f0', fontWeight: 600 },
  explanation: { fontSize: '13px', color: '#a0aec0', lineHeight: 1.6 },
  empty: { color: '#718096', textAlign: 'center', padding: '48px', fontSize: '14px' },
  error: { color: '#fc8181', textAlign: 'center', padding: '24px', fontSize: '14px' },
}

function fmt(val) {
  if (val == null) return '—'
  return `$${Number(val).toFixed(2)}`
}

export default function LongTermTab() {
  const [recs, setRecs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')

  const fetchFn = useCallback(() => api.longterm.getRecommendations(), [])
  const { start: startPolling } = useRefreshPoller(
    fetchFn,
    (data) => { setRecs(data) },
    setError,
    'longterm'
  )

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.longterm.getRecommendations()
      setRecs(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      await api.longterm.refresh()
      startPolling(recs[0]?.run_at, () => setRefreshing(false))
    } catch (e) {
      setError(e.message)
      setRefreshing(false)
    }
  }

  const filtered = filter === 'all' ? recs : recs.filter((r) => r.investment_type === filter)
  const lastRunAt = recs[0]?.run_at

  return (
    <div>
      <div style={s.header}>
        <div>
          <div style={s.title}>Long-Term Growth & Income</div>
          <LastUpdated timestamp={lastRunAt} loading={loading} />
        </div>
        <button style={s.refreshBtn} onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? '⏳ Analyzing...' : '↻ Run Analysis'}
        </button>
      </div>

      <div style={s.filters}>
        {['all', 'growth', 'income'].map((f) => (
          <button key={f} style={s.filterBtn(filter === f)} onClick={() => setFilter(f)}>
            {f === 'all' ? 'All' : f === 'growth' ? '📈 Growth' : '💰 Income'}
          </button>
        ))}
      </div>

      {error && <div style={s.error}>Error: {error}</div>}

      {!loading && filtered.length === 0 && !error && (
        <div style={s.empty}>
          No recommendations yet. Click "Run Analysis" to generate long-term picks.
          <br />
          <small style={{ color: '#4a5568', marginTop: '8px', display: 'block' }}>
            12+ month investment horizon · Based on fundamentals, news, and technical trend
          </small>
        </div>
      )}

      <div style={s.grid}>
        {filtered.map((rec) => (
          <div key={rec.id} style={s.card}>
            <div style={s.cardHeader}>
              <div>
                <span style={s.ticker}>{rec.ticker}</span>
                {rec.investment_type && (
                  <span style={{ marginLeft: '10px', ...s.typeBadge(rec.investment_type) }}>
                    {rec.investment_type}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={s.rankBadge}>#{rec.rank}</span>
                <GradeChip grade={rec.grade} />
              </div>
            </div>

            {/* Dual confidence score */}
            {rec.combined_score != null ? (
              <div>
                <div style={s.sectionLabel}>Confidence Score</div>
                <DualScorePanel
                  quantScore={rec.quant_score}
                  qualScore={rec.qual_score}
                  combinedScore={rec.combined_score}
                />
              </div>
            ) : (
              <div>
                <div style={s.sectionLabel}>Conviction Score</div>
                <ScoreBar score={rec.score} />
              </div>
            )}

            <TradingViewWidget ticker={rec.ticker} />

            {/* Price target + horizon */}
            <div style={s.metaRow}>
              {rec.target_price && (
                <div style={s.metaItem}>
                  <span style={s.metaLabel}>12-Mo Target</span>
                  <span style={{ ...s.metaValue, color: '#68d391' }}>{fmt(rec.target_price)}</span>
                </div>
              )}
              {rec.time_horizon && (
                <div style={s.metaItem}>
                  <span style={s.metaLabel}>Horizon</span>
                  <span style={s.metaValue}>{rec.time_horizon}</span>
                </div>
              )}
            </div>

            {/* Entry zone + invalidation */}
            {(rec.buy_zone_low || rec.buy_zone_high || rec.invalidation_stop) && (
              <div>
                <div style={s.sectionLabel}>Entry & Risk Levels</div>
                <table style={s.table}>
                  <tbody>
                    <tr>
                      <td style={s.td}>Buy Zone Low</td>
                      <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.buy_zone_low)}</td>
                      <td style={s.td}>Buy Zone High</td>
                      <td style={{ ...s.tdVal, color: '#63b3ed' }}>{fmt(rec.buy_zone_high)}</td>
                    </tr>
                    <tr>
                      <td style={s.td}>Invalidation Stop</td>
                      <td style={{ ...s.tdVal, color: '#fc8181' }}>{fmt(rec.invalidation_stop)}</td>
                      <td style={s.td}></td>
                      <td style={s.tdVal}></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            <div>
              <div style={s.sectionLabel}>Thesis</div>
              <p style={s.explanation}>{rec.explanation}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
