import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface User {
    id: string
    email: string
    username: string
    full_name: string
    role: 'user' | 'admin' | 'demo'
    is_active: boolean
    is_verified: boolean
    created_at: string
    last_login_at: string | null
    icon_name?: string
    bio?: string
}


interface AuthState {
    user: User | null
    token: string | null
    isAuthenticated: boolean
    isLoading: boolean

    // Actions
    setAuth: (user: User, token: string) => void
    clearAuth: () => void
    setLoading: (loading: boolean) => void
    updateUser: (user: Partial<User>) => void
}

/**
 * Read the `exp` claim (seconds since epoch) from a JWT without verifying it.
 * Returns null if the token is malformed or has no expiry.
 */
export function getTokenExpiry(token: string | null | undefined): number | null {
    if (!token) return null
    const parts = token.split('.')
    if (parts.length !== 3) return null
    try {
        const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
        const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
        const payload = JSON.parse(atob(padded))
        return typeof payload?.exp === 'number' ? payload.exp : null
    } catch {
        return null
    }
}

/**
 * True when the token is missing, malformed, or expires within `skewSeconds`.
 * The skew avoids sending a request with a token that dies mid-flight.
 */
export function isTokenExpired(token: string | null | undefined, skewSeconds = 30): boolean {
    const exp = getTokenExpiry(token)
    if (exp === null) return true
    return exp * 1000 <= Date.now() + skewSeconds * 1000
}

export function hasValidAuth(auth: {
    isAuthenticated?: boolean | null
    token?: string | null
} | null | undefined): boolean {
    return Boolean(
        auth?.isAuthenticated === true &&
        typeof auth?.token === 'string' &&
        auth.token.trim().length > 0 &&
        !isTokenExpired(auth.token)
    )
}

let sessionExpiryInProgress = false

/**
 * Called when the backend rejects our token (401) or we detect it has expired.
 * Clears the stale session and sends the user to /login exactly once, instead of
 * leaving the IDE in a half-logged-in state where every request silently fails.
 */
export function handleSessionExpired(message = 'Your session has expired. Please sign in again.') {
    if (typeof window === 'undefined') return
    if (sessionExpiryInProgress) return
    const state = useAuthStore.getState()
    if (!state.token && !state.isAuthenticated) return
    sessionExpiryInProgress = true

    state.clearAuth()

    try {
        sessionStorage.setItem('qcanvas-auth-message', message)
    } catch { }

    const path = window.location.pathname
    if (!path.startsWith('/login')) {
        const next = encodeURIComponent(path + window.location.search)
        window.location.replace(`/login?next=${next}`)
    }
    // Allow a future expiry to be handled again (e.g. after re-login without a reload).
    setTimeout(() => { sessionExpiryInProgress = false }, 2000)
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,

            setAuth: (user, token) => {
                set({
                    user,
                    token,
                    isAuthenticated: true,
                    isLoading: false
                })
            },

            clearAuth: () => {
                const currentUser = get().user

                // If demo user, clear all localStorage
                if (currentUser?.role === 'demo') {
                    if (typeof window !== 'undefined') {
                        // Clear all QCanvas data
                        Object.keys(localStorage).forEach(key => {
                            if (key.startsWith('qcanvas-')) {
                                localStorage.removeItem(key)
                            }
                        })
                        console.log('[Auth] Demo account data cleared')
                    }
                }

                // Clear gamification data
                if (typeof window !== 'undefined') {
                    const { useGamificationStore } = require('@/lib/gamificationStore');
                    useGamificationStore.getState().clearGamification();
                }

                set({
                    user: null,
                    token: null,
                    isAuthenticated: false,
                    isLoading: false
                })
            },

            setLoading: (loading) => {
                set({ isLoading: loading })
            },

            updateUser: (updates) => {
                set((state) => ({
                    user: state.user ? { ...state.user, ...updates } : null
                }))
            },
        }),
        {
            name: 'qcanvas-auth',
            // Only persist user and token, not loading state
            partialize: (state) => ({
                user: state.user,
                token: state.token,
                isAuthenticated: state.isAuthenticated,
            }),
        }
    )
)
