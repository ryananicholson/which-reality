import { useCallback, useRef } from 'react'
import { api } from '../api'

/**
 * After triggering a refresh, poll for new data every `interval` ms
 * for up to `maxAttempts` attempts. Stops early when a newer batch appears.
 * If the backend reports an error via /api/status, surfaces it immediately.
 */
export function useRefreshPoller(
  fetchFn,
  setData,
  setError,
  engineKey,            // "options" | "wheel" | "longterm"
  interval = 10000,
  maxAttempts = 18      // 18 × 10s = 3 minutes
) {
  const timerRef = useRef(null)
  const attemptsRef = useRef(0)
  const baseRunAtRef = useRef(null)

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    attemptsRef.current = 0
  }, [])

  const poll = useCallback((onDone) => {
    if (attemptsRef.current >= maxAttempts) {
      stop()
      if (setError) setError('Analysis timed out. Check the Render logs for details.')
      if (onDone) onDone()
      return
    }
    attemptsRef.current += 1
    timerRef.current = setTimeout(async () => {
      try {
        // Check backend status for errors first
        const status = await api.getStatus().catch(() => null)
        if (status && engineKey && status[engineKey]?.state === 'error') {
          const msg = status[engineKey].error || 'Analysis failed'
          if (setError) setError(`Analysis error: ${msg}`)
          stop()
          if (onDone) onDone()
          return
        }

        // Try to fetch new data
        const data = await fetchFn()
        if (data && data.length > 0) {
          const latestRunAt = data[0]?.run_at
          if (!baseRunAtRef.current || new Date(latestRunAt) > new Date(baseRunAtRef.current)) {
            setData(data)
            stop()
            if (onDone) onDone()
            return
          }
        }
      } catch (_) {
        // ignore transient fetch errors
      }
      poll(onDone)
    }, interval)
  }, [fetchFn, setData, setError, engineKey, interval, maxAttempts, stop])

  const start = useCallback((currentRunAt, onDone) => {
    stop()
    baseRunAtRef.current = currentRunAt || null
    attemptsRef.current = 0
    poll(onDone)
  }, [poll, stop])

  return { start, stop }
}
