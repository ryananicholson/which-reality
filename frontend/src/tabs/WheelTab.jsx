import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { useRefreshPoller } from '../hooks/useRefreshPoller'
import LastUpdated from '../components/LastUpdated'
import AccountWidget from '../components/AccountWidget'
import WheelCard from '../wheel/WheelCard'
import PositionTracker from '../wheel/PositionTracker'
import WheelCustomAnalysis from '../wheel/WheelCustomAnalysis'

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
  btnRow: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
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
  exportBtn: {
    padding: '8px 14px',
    background: 'transparent',
    color: '#68d391',
    border: '1px solid #276749',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 500,
  },
  sectionTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: '#a0aec0',
    marginBottom: '16px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  divider: {
    border: 'none',
    borderTop: '1px solid #2d3748',
    margin: '32px 0',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))',
    gap: '16px',
  },
  empty: { color: '#718096', textAlign: 'center', padding: '32px', fontSize: '14px' },
  error: { color: '#fc8181', padding: '16px', fontSize: '14px' },
  showClosedBtn: {
    padding: '6px 14px',
    background: 'transparent',
    border: '1px solid #2d3748',
    borderRadius: '6px',
    color: '#718096',
    cursor: 'pointer',
    fontSize: '12px',
    marginBottom: '16px',
  },
}

function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function WheelTab() {
  const [recs, setRecs] = useState([])
  const [positions, setPositions] = useState([])
  const [account, setAccount] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingPositions, setLoadingPositions] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState(null)
  const [showClosed, setShowClosed] = useState(false)

  const loadRecs = async () => {
    setLoading(true)
    try {
      const data = await api.wheel.getRecommendations()
      setRecs(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const loadPositions = useCallback(async () => {
    setLoadingPositions(true)
    try {
      const data = await api.wheel.getPositions(showClosed)
      setPositions(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingPositions(false)
    }
  }, [showClosed])

  useEffect(() => { loadRecs() }, [])
  useEffect(() => { loadPositions() }, [loadPositions])
  useEffect(() => { api.account.getBalance().then(setAccount).catch(() => {}) }, [])

  const wheelFetchFn = useCallback(() => api.wheel.getRecommendations(), [])
  const { start: startPolling } = useRefreshPoller(
    wheelFetchFn,
    (data) => { setRecs(data) },
    setError,
    'wheel'
  )

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await api.wheel.refresh()
      startPolling(recs[0]?.run_at, () => setRefreshing(false))
    } catch (e) {
      setError(e.message)
      setRefreshing(false)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const data = await api.wheel.exportPositions()
      const date = new Date().toISOString().slice(0, 10)
      downloadJson(data, `wheel-positions-${date}.json`)
    } catch (e) {
      setError(e.message)
    } finally {
      setExporting(false)
    }
  }

  const handleAccepted = (newPosition) => {
    setPositions((prev) => [newPosition, ...prev])
    setRecs((prev) =>
      prev.map((r) => (r.id === newPosition.recommendation_id ? { ...r, accepted: true } : r))
    )
  }

  const handlePositionUpdated = (updated) => {
    setPositions((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
  }

  const lastRunAt = recs[0]?.run_at
  const activePositions = positions.filter((p) => p.status !== 'closed')
  const closedPositions = positions.filter((p) => p.status === 'closed')

  return (
    <div>
      <AccountWidget showSizing />
      <WheelCustomAnalysis />

      <div style={s.header}>
        <div>
          <div style={s.title}>Wheel Strategy</div>
          <LastUpdated timestamp={lastRunAt} loading={loading} />
        </div>
        <div style={s.btnRow}>
          {positions.length > 0 && (
            <button style={s.exportBtn} onClick={handleExport} disabled={exporting} title="Download all positions as JSON backup">
              {exporting ? '⏳' : '⬇'} Backup Positions
            </button>
          )}
          <button style={s.refreshBtn} onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? '⏳ Analyzing...' : '↻ Run Analysis'}
          </button>
        </div>
      </div>

      {error && <div style={s.error}>Error: {error}</div>}

      {/* New recommendations */}
      <div style={s.sectionTitle}>
        <span>🎯</span> Put-Selling Candidates
      </div>

      {!loading && recs.length === 0 && !error && (
        <div style={s.empty}>
          No recommendations yet. Click "Run Analysis" to identify wheel candidates.
          <br />
          <small style={{ color: '#4a5568', marginTop: '8px', display: 'block' }}>
            Looks for high IV-rank stocks with strong support for cash-secured put selling
          </small>
        </div>
      )}

      <div style={s.grid}>
        {recs.map((rec) => (
          <WheelCard key={rec.id} rec={rec} account={account} onAccepted={handleAccepted} />
        ))}
      </div>

      <hr style={s.divider} />

      {/* Tracked positions */}
      <div style={{ ...s.sectionTitle, marginBottom: '8px' }}>
        <span>📊</span> Tracked Positions
        {activePositions.length > 0 && (
          <span style={{
            background: '#2d3748',
            color: '#a0aec0',
            borderRadius: '10px',
            padding: '1px 8px',
            fontSize: '11px',
          }}>
            {activePositions.length} active
          </span>
        )}
      </div>

      {!loadingPositions && activePositions.length === 0 && (
        <div style={s.empty}>
          No active positions. Accept a recommendation above to start tracking a wheel trade.
        </div>
      )}

      <div style={s.grid}>
        {activePositions.map((pos) => (
          <PositionTracker
            key={pos.id}
            position={pos}
            onUpdated={handlePositionUpdated}
          />
        ))}
      </div>

      {/* Closed positions toggle */}
      {closedPositions.length > 0 && (
        <button style={s.showClosedBtn} onClick={() => setShowClosed(!showClosed)}>
          {showClosed ? '▲ Hide' : '▼ Show'} {closedPositions.length} closed position{closedPositions.length !== 1 ? 's' : ''}
        </button>
      )}
      {showClosed && (
        <div style={{ ...s.grid, opacity: 0.6 }}>
          {closedPositions.map((pos) => (
            <PositionTracker
              key={pos.id}
              position={pos}
              onUpdated={handlePositionUpdated}
            />
          ))}
        </div>
      )}
    </div>
  )
}
