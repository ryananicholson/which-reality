/**
 * Displays quantitative score, qualitative score, and combined confidence side by side.
 * Falls back gracefully if only one score is available.
 */
function miniBar(score, color) {
  return (
    <div style={{ flex: 1, height: '5px', background: '#2d3748', borderRadius: '3px', overflow: 'hidden' }}>
      <div style={{ width: `${score}%`, height: '100%', background: color, borderRadius: '3px', transition: 'width 0.5s ease' }} />
    </div>
  )
}

function scoreColor(score) {
  if (score >= 90) return '#68d391'
  if (score >= 80) return '#63b3ed'
  if (score >= 70) return '#f6e05e'
  if (score >= 60) return '#fbd38d'
  return '#fc8181'
}

export default function DualScorePanel({ quantScore, qualScore, combinedScore }) {
  const hasQuant = quantScore != null
  const hasQual = qualScore != null
  const hasCombined = combinedScore != null

  // If no dual scores, show nothing (caller handles fallback)
  if (!hasQuant && !hasQual) return null

  const combined = hasCombined ? combinedScore : (hasQual ? qualScore : quantScore)
  const combinedColor = scoreColor(combined)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {/* Combined confidence — prominent */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{ fontSize: '11px', color: '#718096', width: '80px', flexShrink: 0 }}>COMBINED</div>
        {miniBar(combined, combinedColor)}
        <span style={{ fontSize: '13px', color: combinedColor, fontWeight: 700, minWidth: '32px', textAlign: 'right' }}>
          {Math.round(combined)}
        </span>
      </div>

      {/* Quant + Qual side by side in smaller rows */}
      <div style={{ display: 'flex', gap: '12px' }}>
        {hasQuant && (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '10px', color: '#4a5568', width: '36px', flexShrink: 0 }}>QUANT</span>
            {miniBar(quantScore, '#805ad5')}
            <span style={{ fontSize: '11px', color: '#805ad5', fontWeight: 600, minWidth: '24px', textAlign: 'right' }}>
              {Math.round(quantScore)}
            </span>
          </div>
        )}
        {hasQual && (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '10px', color: '#4a5568', width: '36px', flexShrink: 0 }}>AI</span>
            {miniBar(qualScore, '#ed8936')}
            <span style={{ fontSize: '11px', color: '#ed8936', fontWeight: 600, minWidth: '24px', textAlign: 'right' }}>
              {Math.round(qualScore)}
            </span>
          </div>
        )}
      </div>

      <div style={{ fontSize: '10px', color: '#4a5568' }}>
        Combined = 40% math + 60% AI judgment
      </div>
    </div>
  )
}
