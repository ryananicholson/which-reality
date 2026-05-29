import { useState, useEffect } from 'react'
import { api } from '../api'

const s = {
  wrap: {
    background: '#131825',
    border: '1px solid #2d3748',
    borderRadius: '12px',
    padding: '18px 20px',
    marginBottom: '24px',
  },
  title: { fontSize: '13px', fontWeight: 700, color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '14px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '12px', marginBottom: '16px' },
  stat: { display: 'flex', flexDirection: 'column', gap: '2px' },
  statLabel: { fontSize: '10px', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.04em' },
  statVal: { fontSize: '20px', fontWeight: 800, color: '#e2e8f0' },
  statSub: { fontSize: '11px', color: '#4a5568' },
  row: { display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' },
  input: {
    flex: 1, minWidth: '120px', maxWidth: '180px',
    padding: '8px 12px', background: '#1a1f2e',
    border: '1px solid #2d3748', borderRadius: '6px',
    color: '#e2e8f0', fontSize: '14px', outline: 'none',
  },
  noteInput: {
    flex: 2, minWidth: '160px',
    padding: '8px 12px', background: '#1a1f2e',
    border: '1px solid #2d3748', borderRadius: '6px',
    color: '#a0aec0', fontSize: '13px', outline: 'none',
  },
  btn: (color) => ({
    padding: '8px 16px', background: color || '#276749',
    color: '#fff', border: 'none', borderRadius: '6px',
    cursor: 'pointer', fontSize: '13px', fontWeight: 600, whiteSpace: 'nowrap',
  }),
  warning: {
    background: '#1a1209', border: '1px solid #744210',
    borderRadius: '6px', padding: '8px 12px',
    fontSize: '12px', color: '#f6ad55',
  },
  positionSizing: {
    background: '#0d1420', border: '1px solid #2b6cb0',
    borderRadius: '8px', padding: '10px 14px', marginTop: '12px',
    fontSize: '12px', color: '#bee3f8', lineHeight: 1.6,
  },
}

export default function AccountWidget({ showSizing = false }) {
  const [account, setAccount] = useState(null)
  const [amount, setAmount] = useState('')
  const [note, setNote] = useState('')
  const [mode, setMode] = useState(null) // 'deposit' | 'withdraw' | 'set'
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      const data = await api.account.getBalance()
      setAccount(data)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async () => {
    const val = parseFloat(amount)
    if (!val || isNaN(val)) return
    setSaving(true)
    try {
      let data
      if (mode === 'set') {
        data = await api.account.setBalance(val, note || 'Manual balance update')
      } else {
        const delta = mode === 'withdraw' ? -Math.abs(val) : Math.abs(val)
        data = await api.account.deposit(delta, note || (mode === 'deposit' ? 'Deposit' : 'Withdrawal'))
      }
      setAccount(data)
      setAmount('')
      setNote('')
      setMode(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (!account) return null

  const atRiskPct = account.balance > 0
    ? Math.round((account.capital_at_risk / account.balance) * 100)
    : 0

  return (
    <div style={s.wrap}>
      <div style={s.title}>💼 Account Overview</div>

      <div style={s.grid}>
        <div style={s.stat}>
          <span style={s.statLabel}>Total Capital</span>
          <span style={{ ...s.statVal, color: '#90cdf4' }}>${account.balance.toLocaleString()}</span>
        </div>
        <div style={s.stat}>
          <span style={s.statLabel}>Available</span>
          <span style={{ ...s.statVal, color: '#68d391' }}>${account.available_capital.toLocaleString()}</span>
          <span style={s.statSub}>after open positions</span>
        </div>
        <div style={s.stat}>
          <span style={s.statLabel}>Capital at Risk</span>
          <span style={{ ...s.statVal, color: atRiskPct > 40 ? '#fc8181' : '#f6ad55' }}>
            ${account.capital_at_risk.toLocaleString()}
          </span>
          <span style={s.statSub}>{atRiskPct}% of account</span>
        </div>
        <div style={s.stat}>
          <span style={s.statLabel}>Max Per Trade</span>
          <span style={{ ...s.statVal, color: '#e2e8f0' }}>${account.max_single_position.toLocaleString()}</span>
          <span style={s.statSub}>{account.max_position_pct}% position limit</span>
        </div>
      </div>

      {atRiskPct > 50 && (
        <div style={s.warning}>
          ⚠ {atRiskPct}% of your capital is at risk across open positions. Professional traders keep this under 30-40%.
          Consider not adding new positions until some close.
        </div>
      )}

      {showSizing && account.balance > 0 && (
        <div style={s.positionSizing}>
          <strong>Position sizing rule:</strong> With ${account.balance.toLocaleString()} in your account,
          the maximum you should allocate to a single wheel trade is ${account.max_single_position.toLocaleString()} ({account.max_position_pct}% rule).
          This limits the damage if one stock goes against you.
        </div>
      )}

      <div style={{ marginTop: '14px' }}>
        {!mode ? (
          <div style={s.row}>
            <button style={s.btn('#276749')} onClick={() => setMode('deposit')}>+ Add Funds</button>
            <button style={s.btn('#2b6cb0')} onClick={() => setMode('set')}>✎ Set Balance</button>
            {account.capital_at_risk > 0 && (
              <button style={s.btn('#4a5568')} onClick={() => setMode('withdraw')}>− Withdraw</button>
            )}
          </div>
        ) : (
          <div style={s.row}>
            <input
              style={s.input}
              type="number"
              min="0"
              step="100"
              placeholder={mode === 'set' ? 'New balance' : 'Amount'}
              value={amount}
              onChange={e => setAmount(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            />
            <input
              style={s.noteInput}
              placeholder="Note (optional)"
              value={note}
              onChange={e => setNote(e.target.value)}
            />
            <button style={s.btn('#276749')} onClick={handleSubmit} disabled={saving}>
              {saving ? '⏳' : '✓'} Save
            </button>
            <button style={s.btn('#4a5568')} onClick={() => { setMode(null); setAmount(''); setNote('') }}>
              Cancel
            </button>
          </div>
        )}
      </div>

      {error && <div style={{ color: '#fc8181', fontSize: '12px', marginTop: '8px' }}>⚠ {error}</div>}
    </div>
  )
}
