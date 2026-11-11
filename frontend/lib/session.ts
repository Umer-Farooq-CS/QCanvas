'use client'

import { useEffect } from 'react'
import { authApi } from './api'
import { handleSessionExpired, isTokenExpired, useAuthStore } from './authStore'

const REFRESH_INTERVAL_MS = 60 * 60 * 1000 // refresh at most once an hour while active
let lastRefreshAt = 0
let inFlight: Promise<SessionStatus> | null = null

export type SessionStatus = 'valid' | 'expired' | 'offline'

/**
 * Confirm the stored session with the backend and swap in a fresh token.
 *
 * - 'valid'   → token refreshed (or recently refreshed); safe to load user data.
 * - 'expired' → token is dead; the user has been sent to /login.
 * - 'offline' → backend unreachable; keep the local session rather than logging
 *               the user out because of a network blip.
 */
export function refreshSession(force = false): Promise<SessionStatus> {
  if (inFlight) return inFlight

  const { token } = useAuthStore.getState()
  if (!token || isTokenExpired(token)) {
    handleSessionExpired()
    return Promise.resolve('expired')
  }
  if (!force && Date.now() - lastRefreshAt < REFRESH_INTERVAL_MS) {
    return Promise.resolve('valid')
  }

  inFlight = (async (): Promise<SessionStatus> => {
    const res = await authApi.refreshToken(token)
    if (res.success && res.data?.access_token) {
      lastRefreshAt = Date.now()
      useAuthStore.getState().setAuth(res.data.user, res.data.access_token)
      return 'valid'
    }
    // 401 is already handled inside apiRequest (redirects to /login).
    if (!useAuthStore.getState().token) return 'expired'
    return 'offline'
  })().finally(() => {
    inFlight = null
  })

  return inFlight
}

/**
 * Keeps an open IDE tab logged in: refreshes hourly and whenever the tab
 * becomes visible again (e.g. laptop wakes up after a few hours).
 */
export function useSessionKeepAlive(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return

    const onVisible = () => {
      if (document.visibilityState === 'visible') void refreshSession()
    }
    const interval = window.setInterval(() => void refreshSession(), 10 * 60 * 1000)
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)

    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
    }
  }, [enabled])
}
