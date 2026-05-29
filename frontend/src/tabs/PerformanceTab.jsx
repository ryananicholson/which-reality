import { useState, useEffect } from 'react'
import { api } from '../api'

const STATUS_LABELS = {
  put_active: 'Selling Put',
  assigned: 'Owns Shares',
  call_active: 'Selling Call',
  closed: 'Closed',
}

const STATUS_COLORS = {
  put_active: '#63b3ed',
  assigned: '#f6ad55',
  call_active: '#68d391',
  closed: '#718096',
}

const s = {
  page: { display: 'flex', flexDirection: 'column', gap: '24px' },
  title: { fontSize: '20px', fontWeight: 700, color: '#e2e8f0', marginBottom: '4px' },
  subtitle: { fontSize: '13px', color: '#718096' },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
    gap: '12px',
  },
  statCard: (highlight) => ({
    background: highlight ? '#0d1f12' : '#131825',
    border: `1px solid ${highlight ? '#276749' : '#2d3748'}`,
    borderRadius: '10px', padding: '14px 16px',
    display: 'flex', flexDirection: 'column', gap: '4px',
  }),
  statLabel: { fontSize: '10px', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em' },
  statVal: (color) => ({ fontSize: '24px', fontWeight: 800, color: color || '#e2e8f0' }),
  statSub: { fontSize: '11px', color: '#4a5568' },
  sectionTitle: {
    fontSize: '14px', fontWeight: 700, color: '#a0aec0',
    textTransform: 'uppercase', letterSpacing: '0.04em',
    marginBottom: '12px',
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: {
    textAlign: 'left', padding: '8px 12px',
    borderBottom: '1px solid #2d3748',
    color: '#718096', fontSize: '11px',
    textTransform: 'uppercase', letterSpacing: '0.04em',
    fontWeight: 600,
  },
  tr: (i) => ({
    background: i % 2 === 0 ? '#0d1117' : '#131825',
    borderBottom: '1px solid #1a1f2e',
  }),
  td: { padding: '10px 12px', color: '#a0aec0' },
  tdTicker: { padding: '10px 12px', color: '#90cdf4', fontWeight: 700 },
  badge: (status) => ({
    padding: '2px 8px',
    background: 'rgba(0,0,0,0.3)',
    border: `1px solid ${STATUS_COLORS[status] || '#2d3748'}`,
    borderRadius: '4px',
    color: STATUS_COLORS[status] || '#718096',
    fontSize: '11px', fontWeight: 600,
  }),
  pnl: (val) => ({
    fontWeight: 700,
    color: val > 0 ? '#68d391' : val < 0 ? '#fc8181' : '#a0aec0',
  }),
  empty: {
    background: '#131825', border: '1px solid #2d3748',
    borderRadius: '10px', padding: '40px',
    textAlign: 'center', color: '#718096', fontSize: '14px',
  },
  winRate: (rate) => {
    if (rate >= 70) return '#68d391'
    if (rate >= 50) return '#f6ad55'
    return '#fc8181'
  },
}

export default function PerformanceTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.performance.getSummary()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ color: '#718096', padding: '32px' }}>Loading performance data…</div>
  if (error) return <div style={{ color: '#fc8181', padding: '16px' }}>Error: {error}</div>
  if (!data) return null

  const { summary, active_positions, closed_positions } = data

  return (
    <div style={s.page}>
      <div>
        <div style={s.title}>Performance Tracker</div>
        <div style={s.subtitle}>Your wheel strategy results — all trades, all time</div>
      </div>

      {summary.total_closed_trades === 0 && active_positions.length === 0 ? (
        <div style={s.empty}>
          No trade history yet. Accept wheel recommendations and close positions to see your stats here.
        </div>
      ) : (
        <>
          {/* Summary stats */}
          <div style={s.statsGrid}>
            <div style={s.statCard(summary.total_pnl > 0)}>
              <span style={s.statLabel}>Total P&L</span>
              <span style={s.statVal(summary.total_pnl > 0 ? '#68d391' : summary.total_pnl < 0 ? '#fc8181' : '#e2e8f0')}>
                {summary.total_pnl >= 0 ? '+' : ''}${summary.total_pnl.toLocaleString()}
              </span>
              <span style={s.statSub}>all closed trades</span>
            </div>

            <div style={s.statCard()}>
              <span style={s.statLabel}>Win Rate</span>
              <span style={s.statVal(s.winRate(summary.win_rate_pct))}>
                {summary.win_rate_pct}%
              </span>
              <span style={s.statSub}>{summary.wins}W / {summary.losses}L</span>
            </div>

            <div style={s.statCard()}>
              <span style={s.statLabel}>Trades Closed</span>
              <span style={s.statVal()}>{summary.total_closed_trades}</span>
            </div>

            <div style={s.statCard()}>
              <span style={s.statLabel}>Avg Return / Trade</span>
              <span style={s.statVal(summary.avg_return_pct > 0 ? '#68d391' : '#a0aec0')}>
                {summary.avg_return_pct != null ? `${summary.avg_return_pct > 0 ? '+' : ''}${summary.avg_return_pct}%` : '—'}
              </span>
              <span style={s.statSub}>on capital deployed</span>
            </div>

            <div style={s.statCard()}>
              <span style={s.statLabel}>Active Positions</span>
              <span style={s.statVal('#63b3ed')}>{summary.active_positions}</span>
              <span style={s.statSub}>currently open</span>
            </div>

            <div style={s.statCard()}>
              <span style={s.statLabel}>Avg P&L / Trade</span>
              <span style={s.statVal(summary.avg_pnl_per_trade > 0 ? '#68d391' : '#a0aec0')}>
                {summary.avg_pnl_per_trade >= 0 ? '+' : ''}${summary.avg_pnl_per_trade}
              </span>
            </div>
          </div>

          {/* Active positions */}
          {active_positions.length > 0 && (
            <div>
              <div style={s.sectionTitle}>Open Positions</div>
              <div style={{ overflowX: 'auto' }}>
                <table style={s.table}>
                  <thead>
                    <tr>
                      {['Ticker', 'Status', 'Put Strike', 'Expiry', 'Premium Rcvd', 'Capital at Risk', 'Opened'].map(h => (
                        <th key={h} style={s.th}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {active_positions.map((p, i) => (
                      <tr key={p.id} style={s.tr(i)}>
                        <td style={s.tdTicker}>{p.ticker}</td>
                        <td style={s.td}><span style={s.badge(p.status)}>{STATUS_LABELS[p.status] || p.status}</span></td>
                        <td style={s.td}>{p.put_strike ? `$${p.put_strike}` : '—'}</td>
                        <td style={s.td}>{p.put_expiry || '—'}</td>
                        <td style={{ ...s.td, color: '#68d391' }}>
                          {p.put_premium_rcvd ? `$${p.put_premium_rcvd}` : '—'}
                        </td>
                        <td style={s.td}>{p.capital_at_risk ? `$${p.capital_at_risk.toLocaleString()}` : '—'}</td>
                        <td style={s.td}>
                          {p.put_opened_at ? new Date(p.put_opened_at).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Closed positions */}
          {closed_positions.length > 0 && (
            <div>
              <div style={s.sectionTitle}>Closed Trades</div>
              <div style={{ overflowX: 'auto' }}>
                <table style={s.table}>
                  <thead>
                    <tr>
                      {['Ticker', 'P&L', 'Return %', 'Capital Deployed', 'Opened', 'Closed', 'Notes'].map(h => (
                        <th key={h} style={s.th}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {closed_positions.map((p, i) => (
                      <tr key={p.id} style={s.tr(i)}>
                        <td style={s.tdTicker}>{p.ticker}</td>
                        <td style={{ ...s.td, ...s.pnl(p.total_pnl) }}>
                          {p.total_pnl >= 0 ? '+' : ''}${p.total_pnl.toLocaleString()}
                        </td>
                        <td style={{ ...s.td, ...s.pnl(p.return_pct) }}>
                          {p.return_pct != null ? `${p.return_pct > 0 ? '+' : ''}${p.return_pct}%` : '—'}
                        </td>
                        <td style={s.td}>
                          {p.cost_basis ? `$${((p.cost_basis) * (p.shares || 100)).toLocaleString()}` : '—'}
                        </td>
                        <td style={s.td}>
                          {p.put_opened_at ? new Date(p.put_opened_at).toLocaleDateString() : '—'}
                        </td>
                        <td style={s.td}>
                          {p.closed_at ? new Date(p.closed_at).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ ...s.td, fontSize: '12px' }}>{p.notes || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
