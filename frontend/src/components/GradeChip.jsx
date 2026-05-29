const GRADE_COLORS = {
  A: { bg: '#1a3a2a', color: '#68d391', border: '#2f855a' },
  B: { bg: '#1a2f3a', color: '#63b3ed', border: '#2b6cb0' },
  C: { bg: '#3a3a1a', color: '#f6e05e', border: '#b7791f' },
  D: { bg: '#3a2a1a', color: '#fbd38d', border: '#c05621' },
  F: { bg: '#3a1a1a', color: '#fc8181', border: '#c53030' },
}

export default function GradeChip({ grade }) {
  const colors = GRADE_COLORS[grade] || GRADE_COLORS.C
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '32px',
        height: '32px',
        borderRadius: '6px',
        fontSize: '16px',
        fontWeight: 700,
        background: colors.bg,
        color: colors.color,
        border: `1px solid ${colors.border}`,
      }}
    >
      {grade}
    </span>
  )
}
