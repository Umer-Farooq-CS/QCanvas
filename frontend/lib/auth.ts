import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { handleSessionExpired, hasValidAuth, useAuthStore } from './authStore';

/**
 * Protect a page. Decides from the LIVE store, not the render snapshot: during
 * Next.js hydration Zustand renders the server snapshot (no token), and
 * deciding from that bounced signed-in users from /profile to /login.
 */
export function useRequireAuth(redirectUrl = '/login') {
    const { isAuthenticated, isLoading, token } = useAuthStore();
    const router = useRouter();
    const pathname = usePathname();
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);

    const valid = mounted && hasValidAuth({ isAuthenticated, token });

    useEffect(() => {
        if (!mounted) return;
        const live = useAuthStore.getState();
        if (live.isLoading || hasValidAuth(live)) return;
        if (live.token) {
            // Stored token has expired: clear it and explain why.
            handleSessionExpired();
            return;
        }
        const next = pathname ? `?next=${encodeURIComponent(pathname)}` : '';
        router.push(`${redirectUrl}${next}` as Parameters<typeof router.push>[0]);
    }, [mounted, isAuthenticated, token, isLoading, router, redirectUrl, pathname]);

    return { isAuthenticated: valid, loading: isLoading || !mounted };
}
