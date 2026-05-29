import { useState, useEffect } from 'react'
import { api } from '../api'
import GradeChip from '../components/GradeChip'
import ScoreBar from '../components/ScoreBar'

const STRATEGY_LABELS = {
  wheel: '🔄 Wheel Strategy',
  options: '📈 Options Trading',
  longterm: '🌱 Long-Term Investing',
  'long-term': '🌱 Long-Term Investing',
}

const CHAMPION_COLORS = {
  wheel:   { bg: '#0a1f12', border: '#276749', label: '#68d391', badge: '#0d2218' },
  options: { bg: '#0a1220', border: '#2b6cb0', label: '#63b3ed', badge: '#0d1a2e' },
  longterm:{ bg: '#0f1a0a', border: '#2f6b2f', label: '#9ae6b4', badge: '#0d1f0d' },
}

const s = {
  page: { display: 'flex', flexDirection: 'column', gap: '28px' },
  title: { fontSize: '20px', fontWeight: 700, color: '#e2e8f0', marginBottom: '4px' },
  subtitle: { fontSize: '13px', color: '#718096' },

  // Champions section
  championsWrap: { display: 'flex', flexDirection: 'column', gap: '12px' },
  championsHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  sectionTitle: {
    fontSize: '14px', fontWeight: 700, color: '#a0aec0',
    textTransform: 'uppercase', letterSpacing: '0.05em',
  },
  championsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: '14px',
  },
  championCard: (strategy) => ({
    background: CHAMPION_COLORS[strategy]?.bg ?? '#131825',
    border: `1px solid ${CHAMPION_COLORS[strategy]?.border ?? '#2d3748'}`,
    borderRadius: '12px', padding: '18px',
    display: 'flex', flexDirection: 'column', gap: '10px',
  }),
  champStratLabel: (strategy) => ({
    fontSize: '11px', fontWeight: 700, textTransform: 'uppercase',
    letterSpacing: '0.05em',
    color: CHAMPION_COLORS[strategy]?.label ?? '#718096',
  }),
  champTicker: { fontSize: '28px', fontWeight: 900, color: '#e2e8f0' },
  champScore: { fontSize: '13px', color: '#718096' },
  champReason: { fontSize: '13px', color: '#a0aec0', lineHeight: 1.6 },
  champFooter: {
    display: 'flex', justifyContent: 'space-between',
    alignItems: 'center', marginTop: '4px',
    flexWrap: 'wrap', gap: '6px',
  },
  addToWatchlistBtn: (strategy) => ({
    padding: '5px 12px', fontSize: '11px', fontWeight: 600,
    background: CHAMPION_COLORS[strategy]?.badge ?? '#1a1f2e',
    border: `1px solid ${CHAMPION_COLORS[strategy]?.border ?? '#2d3748'}`,
    color: CHAMPION_COLORS[strategy]?.label ?? '#718096',
    borderRadius: '5px', cursor: 'pointer',
  }),
  deepScoreBtn: {
    padding: '5px 12px', fontSize: '11px', fontWeight: 600,
    background: '#1a1f2e', border: '1px solid #2d3748',
    color: '#90cdf4', borderRadius: '5px', cursor: 'pointer',
  },
  deepScorePanel: {
    marginTop: '4px', borderTop: '1px solid #2d3748',
    paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px',
  },
  deepScoreRow: {
    display: 'flex', alignItems: 'center', gap: '8px',
  },
  deepScoreLabel: {
    fontSize: '10px', color: '#718096', textTransform: 'uppercase',
    letterSpacing: '0.04em', minWidth: '72px',
  },
  deepScoreNote: {
    fontSize: '11px', color: '#718096', fontStyle: 'italic',
  },
  deepScoreSummary: {
    fontSize: '12px', color: '#a0aec0', lineHeight: 1.6,
    background: 'rgba(0,0,0,0.2)', borderRadius: '6px', padding: '8px 10px',
  },
  deepScoreWarning: {
    fontSize: '11px', color: '#f6ad55', background: '#1a1209',
    border: '1px solid #744210', borderRadius: '5px', padding: '6px 10px',
  },
  champDisclaimer: {
    fontSize: '11px', color: '#4a5568', fontStyle: 'italic', marginTop: '4px',
  },
  refreshBtn: {
    padding: '6px 14px', background: 'transparent',
    border: '1px solid #2d3748', borderRadius: '6px',
    color: '#718096', cursor: 'pointer', fontSize: '12px',
  },
  runAt: { fontSize: '11px', color: '#4a5568' },
  noChampions: {
    background: '#131825', border: '1px solid #2d3748',
    borderRadius: '10px', padding: '24px',
    textAlign: 'center', color: '#718096', fontSize: '13px',
  },

  // Divider
  divider: { border: 'none', borderTop: '1px solid #2d3748', margin: '4px 0' },

  // Watchlist section
  addRow: { display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' },
  input: {
    padding: '10px 14px', background: '#1a1f2e',
    border: '1px solid #2d3748', borderRadius: '8px',
    color: '#e2e8f0', fontSize: '16px', fontWeight: 700,
    textTransform: 'uppercase', letterSpacing: '0.08em',
    outline: 'none', width: '140px',
  },
  noteInput: {
    flex: 1, minWidth: '180px',
    padding: '10px 14px', background: '#1a1f2e',
    border: '1px solid #2d3748', borderRadius: '8px',
    color: '#a0aec0', fontSize: '13px', outline: 'none',
  },
  addBtn: {
    padding: '10px 20px', background: '#276749',
    color: '#fff', border: 'none', borderRadius: '8px',
    cursor: 'pointer', fontSize: '14px', fontWeight: 600,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '14px',
  },
  card: (hasWarning) => ({
    background: '#131825',
    border: `1px solid ${hasWarning ? '#744210' : '#2d3748'}`,
    borderRadius: '12px', padding: '18px',
    display: 'flex', flexDirection: 'column', gap: '12px',
  }),
  cardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  ticker: { fontSize: '22px', fontWeight: 800, color: '#90cdf4' },
  addedDate: { fontSize: '11px', color: '#4a5568' },
  scoreRow: { display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' },
  stratLabel: {
    fontSize: '10px', color: '#718096',
    textTransform: 'uppercase', letterSpacing: '0.04em',
    minWidth: '70px',
  },
  bestBadge: (strat) => ({
    padding: '3px 10px',
    background: strat === 'wheel' ? '#0a1f12' : strat === 'options' ? '#0a1220' : '#0f1f0a',
    border: `1px solid ${strat === 'wheel' ? '#276749' : strat === 'options' ? '#2b6cb0' : '#276749'}`,
    borderRadius: '4px',
    color: strat === 'wheel' ? '#68d391' : strat === 'options' ? '#63b3ed' : '#9ae6b4',
    fontSize: '11px', fontWeight: 700,
  }),
  warning: {
    background: '#1a1209', border: '1px solid #744210',
    borderRadius: '6px', padding: '8px 10px',
    fontSize: '12px', color: '#f6ad55',
  },
  summary: { fontSize: '13px', color: '#a0aec0', lineHeight: 1.6 },
  notes: { fontSize: '12px', color: '#4a5568', fontStyle: 'italic' },
  lastScored: { fontSize: '11px', color: '#4a5568' },
  btnRow: { display: 'flex', gap: '6px', marginTop: '4px' },
  scoreBtn: {
    padding: '6px 14px', background: '#1a1f2e',
    border: '1px solid #2d3748', borderRadius: '6px',
    color: '#a0aec0', cursor: 'pointer', fontSize: '12px',
  },
  removeBtn: {
    padding: '6px 10px', background: 'transparent',
    border: '1px solid #4a5568', borderRadius: '6px',
    color: '#718096', cursor: 'pointer', fontSize: '12px',
  },
  empty: {
    background: '#131825', border: '1px solid #2d3748',
    borderRadius: '10px', padding: '40px',
    textAlign: 'center', color: '#718096', fontSize: '14px',
  },
  error: { color: '#fc8181', fontSize: '13px' },
}

// ─── Champions Section ────────────────────────────────────────────────────────

function ChampionsSection({ watchlistTickers, onAddToWatchlist }) {
  const [data, setData] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [deepScores, setDeepScores] = useState({})   // { [ticker]: result | 'loading' | 'error' }

  const load = async () => {
    try {
      const result = await api.champions.get()
      setData(result)
      return result
    } catch {
      return null
    }
  }

  useEffect(() => { load() }, [])

  // Poll every 8 seconds while scan is running
  useEffect(() => {
    if (!refreshing) return
    let count = 0
    const iv = setInterval(async () => {
      count += 8
      setElapsed(count)
      const result = await load()
      // Stop polling when scan finishes (scan_running goes false)
      if (result && !result.scan_running) {
        setRefreshing(false)
        clearInterval(iv)
      }
      // Safety stop after 3 minutes
      if (count >= 180) {
        setRefreshing(false)
        clearInterval(iv)
      }
    }, 8000)
    return () => clearInterval(iv)
  }, [refreshing])

  const handleRefresh = async () => {
    if (refreshing) return
    setElapsed(0)
    try {
      await api.champions.refresh()
      setRefreshing(true)
    } catch (e) {
      // ignore
    }
  }

  const handleDeepScore = async (ticker) => {
    setDeepScores(prev => ({ ...prev, [ticker]: 'loading' }))
    try {
      const result = await api.watchlist.quickScore(ticker)
      setDeepScores(prev => ({ ...prev, [ticker]: result }))
    } catch (e) {
      setDeepScores(prev => ({ ...prev, [ticker]: 'error' }))
    }
  }

  const champions = data?.champions || []
  const runAt = data?.run_at ? new Date(data.run_at).toLocaleString() : null

  return (
    <div style={s.championsWrap}>
      <div style={s.championsHeader}>
        <div>
          <div style={s.sectionTitle}>🏆 Today's Champions</div>
          {runAt && <div style={s.runAt}>Scanned from 50-stock universe · {runAt}</div>}
        </div>
        <button style={s.refreshBtn} onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? `⏳ Scanning… ${elapsed}s` : '↻ Run Scan'}
        </button>
      </div>

      {refreshing && (
        <div style={{ fontSize: '12px', color: '#f6ad55', padding: '6px 0' }}>
          Scanning 50 stocks and asking AI to pick today's best… this takes about 30-60 seconds.
        </div>
      )}

      {!refreshing && data?.last_error && (
        <div style={{ fontSize: '12px', color: '#fc8181', background: '#1a0a0a', border: '1px solid #742a2a', borderRadius: '6px', padding: '10px 12px' }}>
          ⚠ Scan failed: {data.last_error}
        </div>
      )}

      {champions.length === 0 ? (
        <div style={s.noChampions}>
          No champions yet. Click <strong>Run Scan</strong> to scan 50 top stocks and find today's best picks.
          <br />
          <small style={{ color: '#4a5568', display: 'block', marginTop: '6px' }}>
            Runs automatically every trading day at 9:10am Eastern
          </small>
        </div>
      ) : (
        <>
          <div style={s.champDisclaimer}>
            Champions are chosen by relative comparison within today's screened universe — not absolute scoring.
            Click <strong>Deep Score</strong> on any card for a full independent analysis.
          </div>
          <div style={s.championsGrid}>
            {champions.map((c) => {
              const alreadyAdded = watchlistTickers.has(c.ticker)
              const ds = deepScores[c.ticker]
              const dsLoading = ds === 'loading'
              const dsError = ds === 'error'
              const dsResult = ds && ds !== 'loading' && ds !== 'error' ? ds : null

              return (
                <div key={c.strategy} style={s.championCard(c.strategy)}>
                  <div style={s.champStratLabel(c.strategy)}>
                    {STRATEGY_LABELS[c.strategy] || c.strategy} Champion
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={s.champTicker}>{c.ticker}</span>
                    <GradeChip grade={c.grade} />
                  </div>
                  {c.score != null && (
                    <ScoreBar score={c.score} />
                  )}
                  {c.reason && (
                    <div style={s.champReason}>{c.reason}</div>
                  )}
                  <div style={s.champFooter}>
                    {c.survivors_count && (
                      <span style={s.champScore}>
                        Best of {c.survivors_count} qualifying stocks
                      </span>
                    )}
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      <button
                        style={s.deepScoreBtn}
                        onClick={() => handleDeepScore(c.ticker)}
                        disabled={dsLoading}
                      >
                        {dsLoading ? '⏳ Scoring…' : dsResult ? '↻ Re-score' : '📊 Deep Score'}
                      </button>
                      <button
                        style={s.addToWatchlistBtn(c.strategy)}
                        onClick={() => onAddToWatchlist(c.ticker)}
                        disabled={alreadyAdded}
                      >
                        {alreadyAdded ? '✓ In Watchlist' : '+ Add to Watchlist'}
                      </button>
                    </div>
                  </div>

                  {dsError && (
                    <div style={s.deepScoreWarning}>⚠ Score failed — try again in a moment.</div>
                  )}

                  {dsResult && (
                    <div style={s.deepScorePanel}>
                      {dsResult.earnings_warning && (
                        <div style={s.deepScoreWarning}>{dsResult.earnings_warning}</div>
                      )}
                      {[
                        { key: 'wheel', label: 'Wheel', score: dsResult.wheel_score, grade: dsResult.wheel_grade },
                        { key: 'options', label: 'Options', score: dsResult.options_score, grade: dsResult.options_grade },
                        { key: 'longterm', label: 'Long-Term', score: dsResult.longterm_score, grade: dsResult.longterm_grade },
                      ].filter(r => r.score != null).map(r => (
                        <div key={r.key} style={s.deepScoreRow}>
                          <span style={s.deepScoreLabel}>{r.label}</span>
                          <div style={{ flex: 1 }}><ScoreBar score={r.score} /></div>
                          <GradeChip grade={r.grade} />
                        </div>
                      ))}
                      {dsResult.summary && (
                        <div style={s.deepScoreSummary}>{dsResult.summary}</div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

// ─── Watchlist Card ───────────────────────────────────────────────────────────

function WatchlistCard({ item, onScore, onRemove, scoring }) {
  const hasWarning = !!item.earnings_warning
  const strategies = [
    { key: 'wheel', score: item.wheel_score, grade: item.wheel_grade },
    { key: 'options', score: item.options_score, grade: item.options_grade },
    { key: 'longterm', score: item.longterm_score, grade: item.longterm_grade },
  ].filter(s => s.score != null)

  return (
    <div style={s.card(hasWarning)}>
      <div style={s.cardHeader}>
        <div>
          <div style={s.ticker}>{item.ticker}</div>
          <div style={s.addedDate}>Added {new Date(item.added_at).toLocaleDateString()}</div>
        </div>
        {item.best_strategy && (
          <span style={s.bestBadge(item.best_strategy)}>
            Best: {STRATEGY_LABELS[item.best_strategy] || item.best_strategy}
          </span>
        )}
      </div>

      {hasWarning && (
        <div style={s.warning}>{item.earnings_warning}</div>
      )}

      {strategies.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {strategies.map(({ key, score, grade }) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={s.stratLabel}>{STRATEGY_LABELS[key] || key}</span>
              <div style={{ flex: 1 }}><ScoreBar score={score} /></div>
              <GradeChip grade={grade} />
            </div>
          ))}
        </div>
      )}

      {item.score_summary && (
        <div style={s.summary}>{item.score_summary}</div>
      )}

      {item.notes && <div style={s.notes}>Note: {item.notes}</div>}

      {item.last_scored && (
        <div style={s.lastScored}>
          Last scored: {new Date(item.last_scored).toLocaleString()}
        </div>
      )}

      <div style={s.btnRow}>
        <button style={s.scoreBtn} onClick={() => onScore(item.ticker)} disabled={scoring}>
          {scoring ? '⏳ Analyzing…' : item.last_scored ? '↻ Refresh Score' : '▶ Score This Stock'}
        </button>
        <button style={s.removeBtn} onClick={() => onRemove(item.ticker)}>
          ✕ Remove
        </button>
      </div>
    </div>
  )
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

export default function WatchlistTab() {
  const [items, setItems] = useState([])
  const [ticker, setTicker] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [scoring, setScoring] = useState({})
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      const data = await api.watchlist.list()
      setItems(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleAdd = async (sym = null) => {
    const symbol = (sym || ticker).trim().toUpperCase()
    if (!symbol) return
    setAdding(true)
    setError(null)
    try {
      const item = await api.watchlist.add(symbol, notes)
      setItems(prev => [item, ...prev])
      if (!sym) { setTicker(''); setNotes('') }
    } catch (e) {
      setError(e.message)
    } finally {
      setAdding(false)
    }
  }

  const handleScore = async (sym) => {
    setScoring(prev => ({ ...prev, [sym]: true }))
    try {
      const updated = await api.watchlist.score(sym)
      setItems(prev => prev.map(i => i.ticker === sym ? updated : i))
    } catch (e) {
      setError(e.message)
    } finally {
      setScoring(prev => ({ ...prev, [sym]: false }))
    }
  }

  const handleRemove = async (sym) => {
    try {
      await api.watchlist.remove(sym)
      setItems(prev => prev.filter(i => i.ticker !== sym))
    } catch (e) {
      setError(e.message)
    }
  }

  const watchlistTickers = new Set(items.map(i => i.ticker))

  return (
    <div style={s.page}>
      <div>
        <div style={s.title}>Watchlist</div>
        <div style={s.subtitle}>
          Today's best picks from a 50-stock universe, plus your personal tracking list
        </div>
      </div>

      <ChampionsSection
        watchlistTickers={watchlistTickers}
        onAddToWatchlist={handleAdd}
      />

      <hr style={s.divider} />

      <div style={s.sectionTitle}>👁 My Watchlist</div>

      <div style={s.addRow}>
        <input
          style={s.input}
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
          placeholder="AAPL"
          maxLength={5}
        />
        <input
          style={s.noteInput}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
          placeholder="Optional note (e.g. 'watching for breakout')"
          maxLength={200}
        />
        <button style={s.addBtn} onClick={() => handleAdd()} disabled={adding || !ticker.trim()}>
          {adding ? '⏳' : '+ Add to Watchlist'}
        </button>
      </div>

      {error && <div style={s.error}>⚠ {error}</div>}

      {!loading && items.length === 0 && (
        <div style={s.empty}>
          Your watchlist is empty. Add tickers above or click "+ Add to Watchlist" on any champion card.
        </div>
      )}

      <div style={s.grid}>
        {items.map(item => (
          <WatchlistCard
            key={item.ticker}
            item={item}
            onScore={handleScore}
            onRemove={handleRemove}
            scoring={!!scoring[item.ticker]}
          />
        ))}
      </div>
    </div>
  )
}
