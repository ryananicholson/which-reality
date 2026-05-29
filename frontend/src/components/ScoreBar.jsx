function scoreColor(score) {
  if (score >= 90) return '#68d391'
  if (score >= 80) return '#63b3ed'
  if (score >= 70) return '#f6e05e'
  if (score >= 60) return '#fbd38d'
  return '#fc8181'
}

export default function ScoreBar({ score }) {
  const color = scoreColor(score)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div
        style={{
          flex: 1,
          height: '6px',
          background: '#2d3748',
          borderRadius: '3px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${score}%`,
            height: '100%',
            background: color,
            borderRadius: '3px',
            transition: 'width 0.5s ease',
          }}
        />
      </div>
      <span style={{ fontSize: '12px', color, fontWeight: 600, minWidth: '32px' }}>
        {Math.round(score)}
      </span>
    </div>
  )
}
