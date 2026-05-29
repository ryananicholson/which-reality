export default function LastUpdated({ timestamp, loading }) {
  if (loading) {
    return <span style={{ fontSize: '12px', color: '#718096' }}>Refreshing...</span>
  }
  if (!timestamp) {
    return <span style={{ fontSize: '12px', color: '#718096' }}>No data yet — click Refresh to run analysis</span>
  }
  const dt = new Date(timestamp)
  return (
    <span style={{ fontSize: '12px', color: '#718096' }}>
      Last updated: {dt.toLocaleString('en-US', { timeZoneName: 'short' })}
    </span>
  )
}
