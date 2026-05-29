import { useEffect, useRef } from 'react'

export default function TradingViewWidget({ ticker }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!ref.current) return
    ref.current.innerHTML = ''
    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      symbol: ticker,
      width: '100%',
      height: 150,
      locale: 'en',
      dateRange: '1M',
      colorTheme: 'dark',
      isTransparent: true,
      autosize: true,
      largeChartUrl: `https://www.tradingview.com/chart/?symbol=${ticker}`,
    })
    ref.current.appendChild(script)
  }, [ticker])

  return (
    <div
      ref={ref}
      style={{
        background: '#1a1f2e',
        borderRadius: '8px',
        overflow: 'hidden',
        minHeight: '150px',
      }}
    />
  )
}
