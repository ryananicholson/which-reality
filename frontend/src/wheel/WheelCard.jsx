import { useState } from 'react'
import GradeChip from '../components/GradeChip'
import ScoreBar from '../components/ScoreBar'
import DualScorePanel from '../components/DualScorePanel'
import TradingViewWidget from '../components/TradingViewWidget'
import AcceptModal from './AcceptModal'

const RISK_CONFIG = {
  LOW:      { label: 'Low chance of owning shares',      color: '#c6f6d5', bg: '#1a3a2a', border: '#2f855a', dot: '#68d391', icon: '🟢' },
  MODERATE: { label: 'Moderate chance of owning shares', color: '#fefcbf', bg: '#3a3000', border: '#b7791f', dot: '#f6e05e', icon: '🟡' },
  HIGH:     { label: 'High chance of owning shares',     color: '#fed7d7', bg: '#3a1a1a', border: '#c53030', dot: '#fc8181', icon: '🔴' },
}

const s = {
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
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  td: { padding: '5px 0', color: '#a0aec0', width: '50%' },
  tdVal: { padding: '5px 0', color: '#e2e8f0', fontWeight: 600, textAlign: 'right' },
  explanation: { fontSize: '13px', color: '#a0aec0', lineHeight: 1.6 },
  acceptedBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '6px 14px',
    background: '#1a3a2a',
    color: '#68d391',
    border: '1px solid #2f855a',
    borderRadius: '6px',
    fontSize: '13px',
    fontWeight: 600,
  },
  acceptBtn: {
    padding: '8px 20px',
    background: '#276749',
    color: '#c6f6d5',
    border: '1px solid #2f855a',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: 600,
    width: '100%',
  },
}

const sizingStyle = (isOver) => ({
  background: isOver ? '#1a0a0a' : '#0a1f12',
  border: `1px solid ${isOver ? '#742a2a' : '#276749'}`,
  borderRadius: '6px', padding: '7px 10px',
  fontSize: '12px', color: isOver ? '#fc8181' : '#68d391',
  marginTop: '-4px',
})

function IvRankBadge({ ivData }) {
  if (!ivData || ivData.iv_rank == null) return null
  const rank = ivData.iv_rank
  const isHigh = rank >= 50
  const isLow = rank < 25
  const color = isHigh ? '#68d391' : isLow ? '#fc8181' : '#fbd38d'
  const bg = isHigh ? '#0a2218' : isLow ? '#2d1515' : '#2d2000'
  const border = isHigh ? '#276749' : isLow ? '#742a2a' : '#b7791f'
  const icon = isHigh ? '🔥' : isLow ? '❄️' : '〜'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:'10px', padding:'8px 12px',
                  background:bg, border:`1px solid ${border}`, borderRadius:'8px' }}>
      <span style={{ fontSize:'16px', lineHeight:1, flexShrink:0 }}>{icon}</span>
      <div style={{ flex:1 }}>
        <div style={{ display:'flex', alignItems:'center', gap:'8px' }}>
          <span style={{ fontSize:'12px', fontWeight:700, color }}>
            IV Rank {rank}
          </span>
          <span style={{ fontSize:'11px', color:'#718096' }}>
            · {ivData.current_iv_pct}% IV · 52w range: {ivData.iv_52w_low_pct}%–{ivData.iv_52w_high_pct}%
          </span>
        </div>
        <div style={{ fontSize:'11px', color:'#a0aec0', marginTop:'1px' }}>{ivData.signal}</div>
      </div>
      {/* Simple rank bar */}
      <div style={{ width:'60px', flexShrink:0 }}>
        <div style={{ height:'4px', background:'#2d3748', borderRadius:'2px', overflow:'hidden' }}>
          <div style={{ width:`${rank}%`, height:'100%', background:color, borderRadius:'2px' }} />
        </div>
        <div style={{ fontSize:'9px', color:'#718096', textAlign:'right', marginTop:'2px' }}>
          {ivData.iv_percentile}th pctile
        </div>
      </div>
    </div>
  )
}

function AssignmentBadge({ chance, risk }) {
  const cfg = RISK_CONFIG[risk] || RISK_CONFIG.MODERATE
  const pct = chance != null ? Math.round(chance) : null

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '10px 14px',
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
      borderRadius: '8px',
    }}>
      <span style={{ fontSize: '20px', lineHeight: 1 }}>{cfg.icon}</span>
      <div>
        <div style={{ fontSize: '13px', fontWeight: 700, color: cfg.color }}>
          {risk ? `${risk} ASSIGNMENT RISK` : 'ASSIGNMENT RISK UNKNOWN'}
        </div>
        <div style={{ fontSize: '12px', color: cfg.color, opacity: 0.85, marginTop: '2px' }}>
          {pct != null
            ? `~${pct} in 100 chance you end up buying 100 shares`
            : cfg.label}
        </div>
      </div>
    </div>
  )
}

export default function WheelCard({ rec, account, onAccepted }) {
  const [showModal, setShowModal] = useState(false)

  const capitalRequired = rec.put_strike ? rec.put_strike * 100 : null
  const isOverLimit = account && capitalRequired && capitalRequired > account.max_single_position
  const pctOfAccount = account && capitalRequired && account.balance > 0
    ? Math.round((capitalRequired / account.balance) * 100)
    : null

  return (
    <div style={s.card}>
      <div style={s.cardHeader}>
        <span style={s.ticker}>{rec.ticker}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={s.rankBadge}>#{rec.rank}</span>
          <GradeChip grade={rec.grade} />
        </div>
      </div>

      {rec.combined_score != null ? (
        <div>
          <div style={{ fontSize: '11px', color: '#718096', marginBottom: '4px' }}>CONFIDENCE SCORE</div>
          <DualScorePanel
            quantScore={rec.quant_score}
            qualScore={rec.qual_score}
            combinedScore={rec.combined_score}
          />
        </div>
      ) : (
        <div>
          <div style={{ fontSize: '11px', color: '#718096', marginBottom: '4px' }}>CONVICTION SCORE</div>
          <ScoreBar score={rec.score} />
        </div>
      )}

      <IvRankBadge ivData={rec.iv_rank} />

      <AssignmentBadge chance={rec.assignment_chance_pct} risk={rec.assignment_risk} />

      {rec.earnings_days != null && rec.earnings_days <= 14 && (
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '10px',
          padding: '10px 14px',
          background: '#2d2000',
          border: '1px solid #b7791f',
          borderRadius: '8px',
        }}>
          <span style={{ fontSize: '18px', lineHeight: 1, flexShrink: 0 }}>⚠️</span>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#fbd38d' }}>
              Earnings in {rec.earnings_days === 0 ? 'today' : `${rec.earnings_days} day${rec.earnings_days === 1 ? '' : 's'}`} — elevated IV risk
            </div>
            <div style={{ fontSize: '12px', color: '#d69e2e', marginTop: '2px' }}>
              Consider waiting until after earnings to enter this trade.
            </div>
          </div>
        </div>
      )}

      <TradingViewWidget ticker={rec.ticker} />

      <table style={s.table}>
        <tbody>
          <tr>
            <td style={s.td}>Suggested Put Strike</td>
            <td style={{ ...s.tdVal, color: '#fc8181' }}>
              {rec.put_strike ? `$${rec.put_strike}` : '—'}
            </td>
            <td style={s.td}>Expiry</td>
            <td style={s.tdVal}>{rec.put_expiry || '—'}</td>
          </tr>
          <tr>
            <td style={s.td}>Premium / Contract</td>
            <td style={{ ...s.tdVal, color: '#68d391' }}>
              {rec.put_premium ? `$${rec.put_premium}` : '—'}
            </td>
            <td style={s.td}>IV Rank</td>
            <td style={s.tdVal}>{rec.iv_rank?.iv_rank != null ? `${rec.iv_rank.iv_rank}` : '—'}</td>
          </tr>
          {(rec.pct_otm != null || rec.breakeven != null) && (
            <tr>
              <td style={s.td}>% OTM</td>
              <td style={s.tdVal}>{rec.pct_otm != null ? `${rec.pct_otm}%` : '—'}</td>
              <td style={s.td}>Breakeven</td>
              <td style={{ ...s.tdVal, color: '#fbd38d' }}>
                {rec.breakeven != null ? `$${Number(rec.breakeven).toFixed(2)}` : '—'}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {capitalRequired && account && (
        <div style={sizingStyle(isOverLimit)}>
          {isOverLimit
            ? `⚠ This trade requires ~$${capitalRequired.toLocaleString()} (${pctOfAccount}% of your account) — exceeds your ${account.max_position_pct}% position limit of $${account.max_single_position.toLocaleString()}. Consider skipping or reducing size.`
            : `✓ Capital required: ~$${capitalRequired.toLocaleString()} (${pctOfAccount}% of account) — within your $${account.max_single_position.toLocaleString()} position limit.`
          }
        </div>
      )}

      <div>
        <div style={{ fontSize: '11px', color: '#718096', marginBottom: '6px' }}>WHY THIS STOCK</div>
        <p style={s.explanation}>{rec.explanation}</p>
      </div>

      {rec.accepted ? (
        <div style={s.acceptedBadge}>✓ Accepted — tracking in positions below</div>
      ) : (
        <button style={s.acceptBtn} onClick={() => setShowModal(true)}>
          ✓ Accept &amp; Track This Trade
        </button>
      )}

      {showModal && (
        <AcceptModal
          rec={rec}
          onClose={() => setShowModal(false)}
          onAccepted={(pos) => {
            setShowModal(false)
            onAccepted(pos)
          }}
        />
      )}
    </div>
  )
}
