import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import GradeChip from '../components/GradeChip'
import ScoreBar from '../components/ScoreBar'
import DualScorePanel from '../components/DualScorePanel'
import TradingViewWidget from '../components/TradingViewWidget'
import LastUpdated from '../components/LastUpdated'
import { useRefreshPoller } from '../hooks/useRefreshPoller'

const s = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
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
  rankBadge: {
    background: '#2d3748',
    color: '#a0aec0',
    borderRadius: '4px',
    padding: '2px 8px',
    fontSize: '11px',
    fontWeight: 600,
  },
  optionBadge: (type) => ({
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: 700,
    background: type === 'CALL' ? '#1a3a2a' : '#3a1a1a',
    color: type === 'CALL' ? '#68d391' : '#fc8181',
    border: `1px solid ${type === 'CALL' ? '#2f855a' : '#c53030'}`,
  }),
  strategyBadge: (st) => {
    const cfg = {
      iron_condor:     { bg: '#2d2a1a', color: '#f6e05e', border: '#b7791f' },
      bull_put_spread: { bg: '#1a3a2a', color: '#68d391', border: '#276749' },
      bear_call_spread:{ bg: '#3a1a1a', color: '#fc8181', border: '#c53030' },
      bull_call_spread:{ bg: '#1a2f3a', color: '#63b3ed', border: '#2b6cb0' },
      bear_put_spread: { bg: '#2d1a2a', color: '#d6bcfa', border: '#6b46c1' },
      single_leg:      { bg: '#1a2030', color: '#a0aec0', border: '#4a5568' },
    }[st] || { bg: '#1a2030', color: '#a0aec0', border: '#4a5568' }
    return {
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: '4px',
      fontSize: '11px',
      fontWeight: 700,
      background: cfg.bg,
      color: cfg.color,
      border: `1px solid ${cfg.border}`,
      textTransform: 'uppercase',
      letterSpacing: '0.04em',
    }
  },
  sectionLabel: { fontSize: '11px', color: '#718096', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  td: { padding: '5px 0', color: '#a0aec0', width: '50%' },
  tdVal: { padding: '5px 0', color: '#e2e8f0', fontWeight: 600, textAlign: 'right' },
  divider: { borderTop: '1px solid #2d3748', margin: '2px 0' },
  explanation: { fontSize: '13px', color: '#a0aec0', lineHeight: 1.6 },
  empty: { color: '#718096', textAlign: 'center', padding: '48px', fontSize: '14px' },
  error: { color: '#fc8181', textAlign: 'center', padding: '24px', fontSize: '14px' },
}

function fmt(val, prefix = '$') {
  if (val == null) return '—'
  return `${prefix}${Number(val).toFixed(2)}`
}

function calcRR(entry, stop, targets) {
  if (!entry || !stop || !targets?.length || entry === stop) return '—'
  const maxTarget = targets[targets.length - 1].price
  const rr = (maxTarget - entry) / Math.abs(entry - stop)
  return `${rr.toFixed(1)}x`
}

/** Generate scale-out targets at 25%, 50%, 75%, 100% gain from entry */
function scaleOutTargets(entry) {
  if (!entry) return []
  return [25, 50, 75, 100].map((pct) => ({
    pct,
    price: Math.round(entry * (1 + pct / 100) * 20) / 20,  // round to $0.05
    label: pct === 100 ? 'Final 25% · +100%' : `Sell 25% · +${pct}%`,
    color: pct === 25 ? '#68d391' : pct === 50 ? '#63b3ed' : pct === 75 ? '#f6e05e' : '#ed8936',
  }))
}

/** For credit spreads: buy-back targets as % of max profit captured */
function creditScaleOutTargets(netCredit) {
  if (!netCredit || netCredit <= 0) return []
  return [25, 50, 75].map((pct) => ({
    pct,
    price: Math.round(netCredit * (1 - pct / 100) * 20) / 20,
    label: `Close at ${pct}% profit`,
    color: pct === 25 ? '#68d391' : pct === 50 ? '#63b3ed' : '#f6e05e',
  }))
}

export default function OptionsTab() {
  const [recs, setRecs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const fetchFn = useCallback(() => api.options.getRecommendations(), [])
  const { start: startPolling } = useRefreshPoller(
    fetchFn,
    (data) => { setRecs(data) },
    setError,
    'options'
  )

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.options.getRecommendations()
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
      await api.options.refresh()
      startPolling(recs[0]?.run_at, () => setRefreshing(false))
    } catch (e) {
      setError(e.message)
      setRefreshing(false)
    }
  }

  const lastRunAt = recs[0]?.run_at

  return (
    <div>
      <div style={s.header}>
        <div>
          <div style={s.title}>Options Trade Recommendations</div>
          <LastUpdated timestamp={lastRunAt} loading={loading} />
        </div>
        <button style={s.refreshBtn} onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? '⏳ Analyzing...' : '↻ Run Analysis'}
        </button>
      </div>

      {error && <div style={s.error}>Error: {error}</div>}

      {!loading && recs.length === 0 && !error && (
        <div style={s.empty}>
          No recommendations yet. Click "Run Analysis" to generate your first set.
          <br />
          <small style={{ color: '#4a5568', marginTop: '8px', display: 'block' }}>
            Scheduled runs: 9:00 AM, 9:45 AM, 12:00 PM, 3:00 PM, 6:00 PM Eastern
          </small>
        </div>
      )}

      <div style={s.grid}>
        {recs.map((rec) => (
          <div key={rec.id} style={s.card}>
            {/* Header row */}
            <div style={s.cardHeader}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <span style={s.ticker}>{rec.ticker}</span>
                {rec.strategy_type && rec.strategy_type !== 'single_leg' && (
                  <span style={s.strategyBadge(rec.strategy_type)}>
                    {rec.strategy_type.replace(/_/g, ' ')}
                  </span>
                )}
                {rec.strategy_type === 'single_leg' && rec.option_type && rec.option_type !== 'N/A' && (
                  <span style={s.optionBadge(rec.option_type)}>{rec.option_type}</span>
                )}
                {!rec.strategy_type && rec.option_type && rec.option_type !== 'N/A' && (
                  <span style={s.optionBadge(rec.option_type)}>{rec.option_type}</span>
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

            {/* Single-leg contract details */}
            {(!rec.strategy_type || rec.strategy_type === 'single_leg') && (() => {
              const targets = scaleOutTargets(rec.entry_price)
              return (
                <div>
                  <div style={s.sectionLabel}>
                    Option Contract
                    <span style={{ fontSize: '10px', color: '#4a5568', marginLeft: '6px', fontWeight: 400 }}>
                      est. premiums — verify with broker
                    </span>
                  </div>
                  <table style={s.table}>
                    <tbody>
                      <tr>
                        <td style={s.td}>Strike</td>
                        <td style={s.tdVal}>{fmt(rec.strike)}</td>
                        <td style={s.td}>Expiry</td>
                        <td style={s.tdVal}>{rec.expiry || '—'}</td>
                      </tr>
                      <tr>
                        <td style={s.td}>Est. Entry</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.entry_price)}</td>
                        <td style={s.td}>Stop Loss</td>
                        <td style={{ ...s.tdVal, color: '#fc8181' }}>{fmt(rec.stop_loss)}</td>
                      </tr>
                    </tbody>
                  </table>

                  {targets.length > 0 && (
                    <div style={{ marginTop: '10px' }}>
                      <div style={{ ...s.sectionLabel, marginBottom: '6px' }}>
                        Scale-Out Targets (sell 25% at each level)
                      </div>
                      <table style={s.table}>
                        <tbody>
                          {targets.map((t) => (
                            <tr key={t.pct}>
                              <td style={{ ...s.td, fontSize: '12px' }}>{t.label}</td>
                              <td style={{ ...s.tdVal, color: t.color }}>{fmt(t.price)}</td>
                              <td style={{ ...s.td, fontSize: '11px', color: '#4a5568' }}>
                                +${(t.price - rec.entry_price).toFixed(2)}/contract × 100
                              </td>
                              <td style={{ ...s.tdVal, fontSize: '11px', color: t.color }}>
                                +${((t.price - rec.entry_price) * 100).toFixed(0)}
                              </td>
                            </tr>
                          ))}
                          <tr>
                            <td style={{ ...s.td, fontSize: '12px' }}>Max R/R</td>
                            <td colSpan={3} style={{ ...s.tdVal, color: '#a0aec0', fontSize: '12px' }}>
                              {calcRR(rec.entry_price, rec.stop_loss, targets)}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Iron condor legs */}
            {rec.strategy_type === 'iron_condor' && (() => {
              const closeTargets = creditScaleOutTargets(rec.net_credit)
              return (
                <div>
                  <div style={s.sectionLabel}>Iron Condor · {rec.expiry || '—'}</div>
                  <table style={s.table}>
                    <tbody>
                      <tr>
                        <td style={{ ...s.td, color: '#68d391' }}>Long Put (wing)</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.long_put_strike)}</td>
                        <td style={{ ...s.td, color: '#fc8181' }}>Short Put</td>
                        <td style={{ ...s.tdVal, color: '#fc8181' }}>{fmt(rec.short_put_strike)}</td>
                      </tr>
                      <tr>
                        <td style={{ ...s.td, color: '#63b3ed' }}>Short Call</td>
                        <td style={{ ...s.tdVal, color: '#63b3ed' }}>{fmt(rec.short_call_strike)}</td>
                        <td style={{ ...s.td, color: '#a0aec0' }}>Long Call (wing)</td>
                        <td style={{ ...s.tdVal, color: '#a0aec0' }}>{fmt(rec.long_call_strike)}</td>
                      </tr>
                      <tr>
                        <td style={s.td}>Net Credit</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.net_credit)}</td>
                        <td style={s.td}>Profit Zone</td>
                        <td style={{ ...s.tdVal, color: '#f6e05e', fontSize: '11px' }}>
                          {rec.breakeven_low != null && rec.breakeven_high != null
                            ? `${fmt(rec.breakeven_low)} – ${fmt(rec.breakeven_high)}`
                            : '—'}
                        </td>
                      </tr>
                      <tr>
                        <td style={s.td}>Max Profit</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{rec.max_profit != null ? `$${rec.max_profit}` : '—'}</td>
                        <td style={s.td}>Max Loss</td>
                        <td style={{ ...s.tdVal, color: '#fc8181' }}>{rec.max_loss != null ? `$${rec.max_loss}` : '—'}</td>
                      </tr>
                    </tbody>
                  </table>
                  {closeTargets.length > 0 && (
                    <div style={{ marginTop: '10px' }}>
                      <div style={{ ...s.sectionLabel, marginBottom: '6px' }}>Early Close Targets (buy back spread)</div>
                      <table style={s.table}>
                        <tbody>
                          {closeTargets.map((t) => (
                            <tr key={t.pct}>
                              <td style={{ ...s.td, fontSize: '12px' }}>{t.label}</td>
                              <td style={{ ...s.tdVal, color: t.color }}>buy back at {fmt(t.price)}</td>
                              <td style={{ ...s.tdVal, color: t.color, fontSize: '11px' }}>
                                +${((rec.net_credit - t.price) * 100).toFixed(0)} profit
                              </td>
                            </tr>
                          ))}
                          <tr>
                            <td style={{ ...s.td, fontSize: '12px' }}>Let expire (100%)</td>
                            <td colSpan={2} style={{ ...s.tdVal, color: '#68d391', fontSize: '12px' }}>
                              keep full ${rec.max_profit} credit
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Bull put spread */}
            {rec.strategy_type === 'bull_put_spread' && (() => {
              const closeTargets = creditScaleOutTargets(rec.net_credit)
              return (
                <div>
                  <div style={s.sectionLabel}>Bull Put Spread · {rec.expiry || '—'}</div>
                  <table style={s.table}>
                    <tbody>
                      <tr>
                        <td style={{ ...s.td, color: '#fc8181' }}>Short Put (sell)</td>
                        <td style={{ ...s.tdVal, color: '#fc8181' }}>{fmt(rec.short_put_strike)}</td>
                        <td style={{ ...s.td, color: '#68d391' }}>Long Put (buy)</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.long_put_strike)}</td>
                      </tr>
                      <tr>
                        <td style={s.td}>Net Credit</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.net_credit)}</td>
                        <td style={s.td}>Breakeven</td>
                        <td style={{ ...s.tdVal, color: '#f6e05e' }}>{rec.breakeven_low != null ? fmt(rec.breakeven_low) : '—'}</td>
                      </tr>
                      <tr>
                        <td style={s.td}>Max Profit</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{rec.max_profit != null ? `$${rec.max_profit}` : '—'}</td>
                        <td style={s.td}>Max Loss</td>
                        <td style={{ ...s.tdVal, color: '#fc8181' }}>{rec.max_loss != null ? `$${rec.max_loss}` : '—'}</td>
                      </tr>
                    </tbody>
                  </table>
                  {closeTargets.length > 0 && (
                    <div style={{ marginTop: '10px' }}>
                      <div style={{ ...s.sectionLabel, marginBottom: '6px' }}>Early Close Targets</div>
                      <table style={s.table}>
                        <tbody>
                          {closeTargets.map((t) => (
                            <tr key={t.pct}>
                              <td style={{ ...s.td, fontSize: '12px' }}>{t.label}</td>
                              <td style={{ ...s.tdVal, color: t.color }}>buy back at {fmt(t.price)}</td>
                              <td style={{ ...s.tdVal, color: t.color, fontSize: '11px' }}>
                                +${((rec.net_credit - t.price) * 100).toFixed(0)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Bear call spread */}
            {rec.strategy_type === 'bear_call_spread' && (() => {
              const closeTargets = creditScaleOutTargets(rec.net_credit)
              return (
                <div>
                  <div style={s.sectionLabel}>Bear Call Spread · {rec.expiry || '—'}</div>
                  <table style={s.table}>
                    <tbody>
                      <tr>
                        <td style={{ ...s.td, color: '#63b3ed' }}>Short Call (sell)</td>
                        <td style={{ ...s.tdVal, color: '#63b3ed' }}>{fmt(rec.short_call_strike)}</td>
                        <td style={{ ...s.td, color: '#a0aec0' }}>Long Call (buy)</td>
                        <td style={{ ...s.tdVal, color: '#a0aec0' }}>{fmt(rec.long_call_strike)}</td>
                      </tr>
                      <tr>
                        <td style={s.td}>Net Credit</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.net_credit)}</td>
                        <td style={s.td}>Breakeven</td>
                        <td style={{ ...s.tdVal, color: '#f6e05e' }}>{rec.breakeven_high != null ? fmt(rec.breakeven_high) : '—'}</td>
                      </tr>
                      <tr>
                        <td style={s.td}>Max Profit</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{rec.max_profit != null ? `$${rec.max_profit}` : '—'}</td>
                        <td style={s.td}>Max Loss</td>
                        <td style={{ ...s.tdVal, color: '#fc8181' }}>{rec.max_loss != null ? `$${rec.max_loss}` : '—'}</td>
                      </tr>
                    </tbody>
                  </table>
                  {closeTargets.length > 0 && (
                    <div style={{ marginTop: '10px' }}>
                      <div style={{ ...s.sectionLabel, marginBottom: '6px' }}>Early Close Targets</div>
                      <table style={s.table}>
                        <tbody>
                          {closeTargets.map((t) => (
                            <tr key={t.pct}>
                              <td style={{ ...s.td, fontSize: '12px' }}>{t.label}</td>
                              <td style={{ ...s.tdVal, color: t.color }}>buy back at {fmt(t.price)}</td>
                              <td style={{ ...s.tdVal, color: t.color, fontSize: '11px' }}>
                                +${((rec.net_credit - t.price) * 100).toFixed(0)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Bull/bear debit spreads */}
            {(rec.strategy_type === 'bull_call_spread' || rec.strategy_type === 'bear_put_spread') && (() => {
              const debit = rec.net_credit != null ? Math.abs(rec.net_credit) : null
              const targets = scaleOutTargets(debit)
              const isBull = rec.strategy_type === 'bull_call_spread'
              return (
                <div>
                  <div style={s.sectionLabel}>
                    {isBull ? 'Bull Call Spread' : 'Bear Put Spread'} · {rec.expiry || '—'}
                  </div>
                  <table style={s.table}>
                    <tbody>
                      <tr>
                        {isBull ? (<>
                          <td style={{ ...s.td, color: '#68d391' }}>Long Call (buy)</td>
                          <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.long_call_strike)}</td>
                          <td style={{ ...s.td, color: '#a0aec0' }}>Short Call (sell)</td>
                          <td style={{ ...s.tdVal, color: '#a0aec0' }}>{fmt(rec.short_call_strike)}</td>
                        </>) : (<>
                          <td style={{ ...s.td, color: '#fc8181' }}>Long Put (buy)</td>
                          <td style={{ ...s.tdVal, color: '#fc8181' }}>{fmt(rec.long_put_strike)}</td>
                          <td style={{ ...s.td, color: '#a0aec0' }}>Short Put (sell)</td>
                          <td style={{ ...s.tdVal, color: '#a0aec0' }}>{fmt(rec.short_put_strike)}</td>
                        </>)}
                      </tr>
                      <tr>
                        <td style={s.td}>Net Debit</td>
                        <td style={{ ...s.tdVal, color: '#fc8181' }}>{debit != null ? fmt(debit) : '—'}</td>
                        <td style={s.td}>Breakeven</td>
                        <td style={{ ...s.tdVal, color: '#f6e05e' }}>
                          {(rec.breakeven_high || rec.breakeven_low) != null
                            ? fmt(rec.breakeven_high || rec.breakeven_low) : '—'}
                        </td>
                      </tr>
                      <tr>
                        <td style={s.td}>Max Profit</td>
                        <td style={{ ...s.tdVal, color: '#68d391' }}>{rec.max_profit != null ? `$${rec.max_profit}` : '—'}</td>
                        <td style={s.td}>Max Loss</td>
                        <td style={{ ...s.tdVal, color: '#fc8181' }}>{rec.max_loss != null ? `$${rec.max_loss}` : '—'}</td>
                      </tr>
                    </tbody>
                  </table>
                  {targets.length > 0 && (
                    <div style={{ marginTop: '10px' }}>
                      <div style={{ ...s.sectionLabel, marginBottom: '6px' }}>
                        Scale-Out Targets on spread value (sell 25% at each level)
                      </div>
                      <table style={s.table}>
                        <tbody>
                          {targets.map((t) => (
                            <tr key={t.pct}>
                              <td style={{ ...s.td, fontSize: '12px' }}>{t.label}</td>
                              <td style={{ ...s.tdVal, color: t.color }}>{fmt(t.price)}</td>
                              <td style={{ ...s.tdVal, color: t.color, fontSize: '11px' }}>
                                +${((t.price - debit) * 100).toFixed(0)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Underlying price targets (single leg only) */}
            {(!rec.strategy_type || rec.strategy_type === 'single_leg') &&
             (rec.underlying_entry || rec.underlying_target || rec.underlying_stop) && (
              <div>
                <div style={s.sectionLabel}>Underlying Price Targets (ATR-based)</div>
                <table style={s.table}>
                  <tbody>
                    <tr>
                      <td style={s.td}>Entry Zone</td>
                      <td style={{ ...s.tdVal, color: '#68d391' }}>{fmt(rec.underlying_entry)}</td>
                      <td style={s.td}>Price Target</td>
                      <td style={{ ...s.tdVal, color: '#63b3ed' }}>{fmt(rec.underlying_target)}</td>
                    </tr>
                    <tr>
                      <td style={s.td}>Invalidation</td>
                      <td style={{ ...s.tdVal, color: '#fc8181' }}>{fmt(rec.underlying_stop)}</td>
                      <td style={s.td}>Stock R/R</td>
                      <td style={s.tdVal}>{calcRR(rec.underlying_entry, rec.underlying_target, rec.underlying_stop)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            <div>
              <div style={s.sectionLabel}>Analysis</div>
              <p style={s.explanation}>{rec.explanation}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
