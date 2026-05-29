import { useState, useEffect } from 'react'
import { api } from '../api'

const STATUS_CONFIG = {
  put_active:  { label: 'Put Active',  color: '#f6e05e', bg: '#3a3a1a', border: '#b7791f' },
  assigned:    { label: 'Assigned',    color: '#fbd38d', bg: '#3a2a1a', border: '#c05621' },
  call_active: { label: 'Call Active', color: '#68d391', bg: '#1a3a2a', border: '#2f855a' },
  closed:      { label: 'Closed',      color: '#a0aec0', bg: '#2d3748', border: '#4a5568' },
}

const s = {
  card: {
    background: '#161b27',
    border: '1px solid #2d3748',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
  },
  topRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  ticker: { fontSize: '20px', fontWeight: 800, color: '#90cdf4' },
  statusBadge: (status) => {
    const c = STATUS_CONFIG[status] || STATUS_CONFIG.put_active
    return {
      padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 700,
      background: c.bg, color: c.color, border: `1px solid ${c.border}`,
      textTransform: 'uppercase', letterSpacing: '0.05em',
    }
  },
  section: { borderTop: '1px solid #2d3748', paddingTop: '12px' },
  sectionTitle: { fontSize: '11px', color: '#718096', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' },
  metaGrid: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' },
  metaItem: { display: 'flex', flexDirection: 'column', gap: '2px' },
  metaLabel: { fontSize: '10px', color: '#718096' },
  metaVal: { fontSize: '13px', color: '#e2e8f0', fontWeight: 600 },
  btnRow: { display: 'flex', gap: '8px', flexWrap: 'wrap' },
  btn: (color) => ({
    padding: '7px 14px', borderRadius: '6px', border: 'none',
    background: color, color: '#fff', cursor: 'pointer', fontSize: '12px', fontWeight: 600,
  }),
  input: {
    background: '#0f1117', border: '1px solid #2d3748', borderRadius: '6px',
    padding: '6px 10px', color: '#e2e8f0', fontSize: '13px', width: '140px',
  },
  suggestion: {
    background: '#1a2a3a', border: '1px solid #2b6cb0', borderRadius: '8px',
    padding: '12px', fontSize: '13px', color: '#a0aec0', lineHeight: 1.6,
  },
  suggTitle: { color: '#63b3ed', fontWeight: 600, marginBottom: '6px', fontSize: '13px' },
  error: { color: '#fc8181', fontSize: '12px' },
  history: { fontSize: '11px', color: '#4a5568', marginTop: '4px' },
  rollWarning: {
    display: 'flex', alignItems: 'flex-start', gap: '10px',
    padding: '12px 14px', borderRadius: '8px',
    background: '#3a3000', border: '1px solid #b7791f',
  },
  rollDanger: {
    display: 'flex', alignItems: 'flex-start', gap: '10px',
    padding: '12px 14px', borderRadius: '8px',
    background: '#3a1a1a', border: '1px solid #c53030',
  },
  rollSuggestionBox: {
    background: '#1a1f2e', border: '1px solid #553c9a', borderRadius: '8px',
    padding: '14px', fontSize: '13px', color: '#e2e8f0', lineHeight: 1.7,
  },
}

function fmt(val, pre = '$') {
  if (val == null) return '—'
  return `${pre}${Number(val).toFixed(2)}`
}

export default function PositionTracker({ position: initialPos, onUpdated }) {
  const [pos, setPos] = useState(initialPos)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [suggestion, setSuggestion] = useState(null)
  const [loadingSuggestion, setLoadingSuggestion] = useState(false)
  const [rollAlert, setRollAlert] = useState(null)
  const [rollSuggestion, setRollSuggestion] = useState(null)
  const [loadingRoll, setLoadingRoll] = useState(false)

  useEffect(() => {
    if (pos.status === 'put_active') {
      api.wheel.getRollAlert(pos.id)
        .then(data => { if (data.alert_level !== 'none') setRollAlert(data) })
        .catch(() => {})
    }
  }, [pos.id, pos.status])
  // Inline inputs for call details
  const [callStrike, setCallStrike] = useState('')
  const [callExpiry, setCallExpiry] = useState('')
  const [callPremium, setCallPremium] = useState('')
  const [totalPnl, setTotalPnl] = useState('')
  const [showHistory, setShowHistory] = useState(false)

  const transition = async (newStatus, extra = {}) => {
    setLoading(true)
    setError(null)
    try {
      const updated = await api.wheel.updateStatus(pos.id, { new_status: newStatus, ...extra })
      setPos(updated)
      onUpdated && onUpdated(updated)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const loadSuggestion = async () => {
    setLoadingSuggestion(true)
    try {
      const data = await api.wheel.getCallSuggestion(pos.id)
      setSuggestion(data.suggestion)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingSuggestion(false)
    }
  }

  const refreshSuggestion = async () => {
    setLoadingSuggestion(true)
    try {
      await api.wheel.refreshCallSuggestion(pos.id)
      setTimeout(loadSuggestion, 20000)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingSuggestion(false)
    }
  }

  const cfg = STATUS_CONFIG[pos.status] || STATUS_CONFIG.put_active

  return (
    <div style={s.card}>
      <div style={s.topRow}>
        <span style={s.ticker}>{pos.ticker}</span>
        <span style={s.statusBadge(pos.status)}>{cfg.label}</span>
      </div>

      {/* Put details */}
      <div style={s.section}>
        <div style={s.sectionTitle}>Put Leg</div>
        <div style={s.metaGrid}>
          <div style={s.metaItem}><span style={s.metaLabel}>Strike</span><span style={s.metaVal}>{fmt(pos.put_strike)}</span></div>
          <div style={s.metaItem}><span style={s.metaLabel}>Expiry</span><span style={s.metaVal}>{pos.put_expiry || '—'}</span></div>
          <div style={s.metaItem}><span style={s.metaLabel}>Premium Rcvd</span><span style={{ ...s.metaVal, color: '#68d391' }}>{fmt(pos.put_premium_rcvd)}</span></div>
          {pos.cost_basis && (
            <div style={s.metaItem}><span style={s.metaLabel}>Cost Basis</span><span style={s.metaVal}>{fmt(pos.cost_basis)}</span></div>
          )}
        </div>
      </div>

      {/* Roll Alert — only for put_active when stock is near the strike */}
      {rollAlert && rollAlert.alert_level !== 'none' && (
        <div style={rollAlert.alert_level === 'danger' ? s.rollDanger : s.rollWarning}>
          <span style={{ fontSize: '22px', lineHeight: 1 }}>
            {rollAlert.alert_level === 'danger' ? '🔴' : '🟡'}
          </span>
          <div style={{ flex: 1 }}>
            <div style={{
              fontWeight: 700, fontSize: '13px', marginBottom: '4px',
              color: rollAlert.alert_level === 'danger' ? '#fc8181' : '#f6e05e',
            }}>
              {rollAlert.alert_level === 'danger' ? 'CONSIDER ROLLING — HIGH RISK' : 'HEADS UP — GETTING CLOSE'}
            </div>
            <div style={{ fontSize: '12px', color: '#e2e8f0', marginBottom: '10px' }}>
              {rollAlert.message}
            </div>

            {!rollSuggestion ? (
              <button
                style={{ ...s.btn('#553c9a'), fontSize: '12px' }}
                onClick={async () => {
                  setLoadingRoll(true)
                  try {
                    const data = await api.wheel.getRollSuggestion(pos.id)
                    setRollSuggestion(data)
                  } catch (e) {
                    setError('Roll suggestion failed: ' + e.message)
                  } finally {
                    setLoadingRoll(false)
                  }
                }}
                disabled={loadingRoll}
              >
                {loadingRoll ? '⏳ Analyzing roll options...' : '🤖 Get Roll Recommendation'}
              </button>
            ) : (
              <div style={s.rollSuggestionBox}>
                <div style={{ fontWeight: 700, color: '#b794f4', marginBottom: '8px', fontSize: '13px' }}>
                  {rollSuggestion.should_roll ? '📋 Recommended Roll' : '✋ Hold For Now'}
                </div>
                {rollSuggestion.should_roll && rollSuggestion.action_plain && (
                  <div style={{ fontWeight: 600, color: '#e2e8f0', marginBottom: '8px' }}>
                    {rollSuggestion.action_plain}
                  </div>
                )}
                {rollSuggestion.new_strike && (
                  <div style={{ display: 'flex', gap: '16px', marginBottom: '8px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '12px', color: '#a0aec0' }}>
                      New strike: <strong style={{ color: '#fc8181' }}>${rollSuggestion.new_strike}</strong>
                    </span>
                    {rollSuggestion.new_expiry && (
                      <span style={{ fontSize: '12px', color: '#a0aec0' }}>
                        New expiry: <strong style={{ color: '#e2e8f0' }}>{rollSuggestion.new_expiry}</strong>
                      </span>
                    )}
                    {rollSuggestion.net_description && (
                      <span style={{ fontSize: '12px', color: '#68d391' }}>
                        {rollSuggestion.net_description}
                      </span>
                    )}
                  </div>
                )}
                <p style={{ fontSize: '12px', color: '#a0aec0', margin: '6px 0 4px' }}>
                  {rollSuggestion.rationale}
                </p>
                {rollSuggestion.if_no_action && (
                  <p style={{ fontSize: '11px', color: '#718096', margin: '4px 0 0', fontStyle: 'italic' }}>
                    If you do nothing: {rollSuggestion.if_no_action}
                  </p>
                )}
                <button
                  style={{ ...s.btn('#4a5568'), fontSize: '11px', marginTop: '10px' }}
                  onClick={() => setRollSuggestion(null)}
                >
                  ↻ Refresh
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Assignment details */}
      {(pos.status === 'assigned' || pos.status === 'call_active' || pos.status === 'closed') && (
        <div style={s.section}>
          <div style={s.sectionTitle}>Assignment</div>
          <div style={s.metaGrid}>
            <div style={s.metaItem}><span style={s.metaLabel}>Assigned</span><span style={s.metaVal}>{pos.assigned_at ? new Date(pos.assigned_at).toLocaleDateString() : '—'}</span></div>
            <div style={s.metaItem}><span style={s.metaLabel}>Shares</span><span style={s.metaVal}>{pos.shares}</span></div>
            <div style={s.metaItem}><span style={s.metaLabel}>Cost Basis</span><span style={s.metaVal}>{fmt(pos.cost_basis)}</span></div>
          </div>
        </div>
      )}

      {/* Covered call details */}
      {pos.status === 'call_active' && (
        <div style={s.section}>
          <div style={s.sectionTitle}>Covered Call</div>
          <div style={s.metaGrid}>
            <div style={s.metaItem}><span style={s.metaLabel}>Call Strike</span><span style={{ ...s.metaVal, color: '#63b3ed' }}>{fmt(pos.call_strike)}</span></div>
            <div style={s.metaItem}><span style={s.metaLabel}>Call Expiry</span><span style={s.metaVal}>{pos.call_expiry || '—'}</span></div>
            <div style={s.metaItem}><span style={s.metaLabel}>Call Premium</span><span style={{ ...s.metaVal, color: '#68d391' }}>{fmt(pos.call_premium_rcvd)}</span></div>
          </div>
        </div>
      )}

      {/* Closed PnL */}
      {pos.status === 'closed' && pos.total_pnl != null && (
        <div style={s.section}>
          <div style={s.sectionTitle}>Result</div>
          <div style={{ ...s.metaVal, fontSize: '18px', color: pos.total_pnl >= 0 ? '#68d391' : '#fc8181' }}>
            {pos.total_pnl >= 0 ? '+' : ''}{fmt(pos.total_pnl)} total P&L
          </div>
        </div>
      )}

      {/* Call suggestion for assigned positions */}
      {pos.status === 'assigned' && (
        <div style={s.section}>
          <div style={s.sectionTitle}>This Week's Call Suggestion</div>
          {suggestion ? (
            <div style={s.suggestion}>
              <div style={s.suggTitle}>
                Sell {suggestion.call_expiry} ${suggestion.call_strike} Call
                {suggestion.estimated_premium && ` — est. $${suggestion.estimated_premium}/contract`}
              </div>
              <p>{suggestion.rationale}</p>
            </div>
          ) : (
            <button style={{ ...s.btn('#2b6cb0'), marginBottom: '4px' }} onClick={loadSuggestion} disabled={loadingSuggestion}>
              {loadingSuggestion ? 'Loading...' : '🤖 Get This Week\'s Call Suggestion'}
            </button>
          )}
          {suggestion && (
            <button style={{ ...s.btn('#4a5568'), marginTop: '6px', fontSize: '11px' }} onClick={refreshSuggestion} disabled={loadingSuggestion}>
              ↻ Refresh Suggestion
            </button>
          )}
        </div>
      )}

      {error && <div style={s.error}>{error}</div>}

      {/* Action buttons */}
      {pos.status !== 'closed' && (
        <div style={s.section}>
          <div style={s.sectionTitle}>Actions</div>
          <div style={s.btnRow}>
            {pos.status === 'put_active' && (
              <button style={s.btn('#c05621')} onClick={() => transition('assigned')} disabled={loading}>
                📌 Mark Assigned
              </button>
            )}

            {pos.status === 'assigned' && (
              <>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <input style={s.input} type="number" placeholder="Call Strike" value={callStrike} onChange={e => setCallStrike(e.target.value)} />
                  <input style={s.input} type="text" placeholder="Expiry YYYY-MM-DD" value={callExpiry} onChange={e => setCallExpiry(e.target.value)} />
                  <input style={s.input} type="number" placeholder="Premium $" value={callPremium} onChange={e => setCallPremium(e.target.value)} />
                  <button
                    style={s.btn('#276749')}
                    disabled={loading || !callStrike}
                    onClick={() => transition('call_active', {
                      call_strike: parseFloat(callStrike) || null,
                      call_expiry: callExpiry || null,
                      call_premium_rcvd: parseFloat(callPremium) || null,
                    })}
                  >
                    📞 Open Covered Call
                  </button>
                </div>
              </>
            )}

            {pos.status === 'call_active' && (
              <>
                <button style={s.btn('#b7791f')} onClick={() => transition('assigned', { note: 'Call expired worthless — new call cycle' })} disabled={loading}>
                  ↻ Call Expired (New Cycle)
                </button>
              </>
            )}

            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <input style={{ ...s.input, width: '120px' }} type="number" placeholder="Total P&L $" value={totalPnl} onChange={e => setTotalPnl(e.target.value)} />
              <button
                style={s.btn('#4a5568')}
                onClick={() => transition('closed', { total_pnl: parseFloat(totalPnl) || null })}
                disabled={loading}
              >
                ✓ Close Position
              </button>
            </div>
          </div>
        </div>
      )}

      {/* History toggle */}
      {pos.history && pos.history.length > 0 && (
        <button
          style={{ background: 'none', border: 'none', color: '#718096', cursor: 'pointer', fontSize: '11px', textAlign: 'left' }}
          onClick={() => setShowHistory(!showHistory)}
        >
          {showHistory ? '▲' : '▼'} History ({pos.history.length} events)
        </button>
      )}
      {showHistory && pos.history && (
        <div style={{ fontSize: '11px', color: '#4a5568', borderTop: '1px solid #2d3748', paddingTop: '8px' }}>
          {pos.history.map((h) => (
            <div key={h.id} style={{ marginBottom: '4px' }}>
              {new Date(h.changed_at).toLocaleString()} — {h.from_status || 'new'} → {h.to_status}
              {h.note && ` (${h.note})`}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
