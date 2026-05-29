import { useState } from 'react'
import { api } from '../api'

const overlay = {
  position: 'fixed', inset: 0,
  background: 'rgba(0,0,0,0.7)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 1000,
}
const modal = {
  background: '#1a1f2e',
  border: '1px solid #2d3748',
  borderRadius: '12px',
  padding: '28px',
  width: '100%',
  maxWidth: '420px',
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
}
const label = { fontSize: '12px', color: '#718096', display: 'block', marginBottom: '4px' }
const input = {
  width: '100%',
  background: '#0f1117',
  border: '1px solid #2d3748',
  borderRadius: '6px',
  padding: '8px 12px',
  color: '#e2e8f0',
  fontSize: '14px',
}
const btnRow = { display: 'flex', gap: '8px', justifyContent: 'flex-end' }
const cancelBtn = {
  padding: '8px 16px', background: 'transparent',
  border: '1px solid #2d3748', borderRadius: '6px',
  color: '#a0aec0', cursor: 'pointer', fontSize: '13px',
}
const confirmBtn = {
  padding: '8px 20px', background: '#276749',
  border: '1px solid #2f855a', borderRadius: '6px',
  color: '#c6f6d5', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
}

export default function AcceptModal({ rec, onClose, onAccepted }) {
  const [putStrike, setPutStrike] = useState(rec.put_strike ?? '')
  const [putExpiry, setPutExpiry] = useState(rec.put_expiry ?? '')
  const [putPremium, setPutPremium] = useState(rec.put_premium ?? '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleConfirm = async () => {
    if (!putStrike) { setError('Put strike is required'); return }
    setLoading(true)
    setError(null)
    try {
      const pos = await api.wheel.acceptRecommendation(rec.id, {
        put_strike: parseFloat(putStrike),
        put_expiry: putExpiry || null,
        put_premium_rcvd: putPremium ? parseFloat(putPremium) : null,
      })
      onAccepted(pos)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={modal}>
        <div style={{ fontSize: '16px', fontWeight: 700, color: '#e2e8f0' }}>
          Accept Wheel Trade — {rec.ticker}
        </div>
        <div style={{ fontSize: '13px', color: '#a0aec0' }}>
          Confirm the details below. You can adjust from the suggested values.
        </div>

        <div>
          <label style={label}>Put Strike *</label>
          <input
            style={input}
            type="number"
            step="0.5"
            value={putStrike}
            onChange={(e) => setPutStrike(e.target.value)}
            placeholder="e.g. 380.00"
          />
        </div>
        <div>
          <label style={label}>Expiry Date (YYYY-MM-DD)</label>
          <input
            style={input}
            type="text"
            value={putExpiry}
            onChange={(e) => setPutExpiry(e.target.value)}
            placeholder="e.g. 2025-04-18"
          />
        </div>
        <div>
          <label style={label}>Premium Received per Contract ($)</label>
          <input
            style={input}
            type="number"
            step="0.01"
            value={putPremium}
            onChange={(e) => setPutPremium(e.target.value)}
            placeholder="e.g. 4.20"
          />
        </div>

        {error && <div style={{ color: '#fc8181', fontSize: '13px' }}>{error}</div>}

        <div style={btnRow}>
          <button style={cancelBtn} onClick={onClose}>Cancel</button>
          <button style={confirmBtn} onClick={handleConfirm} disabled={loading}>
            {loading ? 'Saving...' : 'Confirm & Track'}
          </button>
        </div>
      </div>
    </div>
  )
}
