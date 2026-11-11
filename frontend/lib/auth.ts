import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { handleSessionExpired, hasValidAuth, useAuthStore } from './authStore';

/** True once the persisted auth state has been read from localStorage. */
function useAuthHydrated(): boolean {
    const [hydrated, setHydrated] = useState(() => useAuthStore.persist?.hasHydrated?.() ?? true);
    useEffect(() => {
        if (hydrated) return;
        const unsub = useAuthStore.persist?.onFinishHydration?.(() => setHydrated(true));
        // Covers hydration that finished between render and this effect.
        if (useAuthStore.persist?.hasHydrated?.()) setHydrated(true);
        return () => unsub?.();
    }, [hydrated]);
    return hydrated;
}

export function useRequireAuth(redirectUrl = '/login') {
    const { isAuthenticated, isLoading, token } = useAuthStore();
    const router = useRouter();
    const hydrated = useAuthHydrated();
    const valid = hasValidAuth({ isAuthenticated, token });

    useEffect(() => {
        // Don't decide before the stored session has loaded; deciding early
        // bounced signed-in users from /profile to /login.
        if (!hydrated || isLoading || valid) return;
        if (token) {
            // Stored token has expired: clear it and explain why.
            handleSessionExpired();
        } else {
            router.push(redirectUrl as Parameters<typeof router.push>[0]);
        }
    }, [hydrated, valid, isLoading, token, router, redirectUrl]);

    return { isAuthenticated: valid, loading: isLoading || !hydrated };
}
