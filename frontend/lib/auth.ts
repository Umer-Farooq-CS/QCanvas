import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { handleSessionExpired, hasValidAuth, useAuthStore } from './authStore';

export function useRequireAuth(redirectUrl = '/login') {
    const { isAuthenticated, isLoading, token } = useAuthStore();
    const router = useRouter();
    const valid = hasValidAuth({ isAuthenticated, token });

    useEffect(() => {
        if (isLoading || valid) return;
        if (token) {
            // Stored token has expired: clear it and explain why.
            handleSessionExpired();
        } else {
            router.push(redirectUrl as Parameters<typeof router.push>[0]);
        }
    }, [valid, isLoading, token, router, redirectUrl]);

    return { isAuthenticated: valid, loading: isLoading };
}
