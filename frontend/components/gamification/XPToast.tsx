/**
 * XP Toast Component
 * 
 * Shows a short notification when the user earns XP or levels up.
 */

"use client";

import { useEffect, useState } from 'react';
import { Zap, TrendingUp, Award } from '@/components/Icons';
import { XPGainEvent } from '@/lib/gamificationStore';

interface XPToastProps {
    event: XPGainEvent | null;
    onClose: () => void;
}

export default function XPToast({ event, onClose }: XPToastProps) {
    const [isVisible, setIsVisible] = useState(false);
    const [isExiting, setIsExiting] = useState(false);

    useEffect(() => {
        if (event) {
            setIsVisible(true);
            setIsExiting(false);

            // Auto-hide after duration
            const duration = event.level_up ? 5000 : 3000;
            const timer = setTimeout(() => {
                handleClose();
            }, duration);

            return () => clearTimeout(timer);
        }
    }, [event]);

    const handleClose = () => {
        setIsExiting(true);
        setTimeout(() => {
            setIsVisible(false);
            onClose();
        }, 300);
    };

    if (!event || !isVisible) return null;

    const isLevelUp = event.level_up;
    const isFirstTime = event.is_first_time;

    const progress = Math.min(
        100,
        ((event.total_xp - (event.total_xp - event.xp_gained)) / event.xp_to_next_level) * 100,
    );
    const Icon = isLevelUp ? TrendingUp : isFirstTime ? Award : Zap;

    return (
        <div
            role="status"
            aria-live="polite"
            className={`fixed bottom-6 right-6 z-[9999] w-[300px] max-w-[calc(100vw-2rem)] cursor-pointer transition-[opacity,transform] duration-200 ease-out-quick ${
                isExiting ? 'translate-y-2 opacity-0' : 'qc-fade-in'
            }`}
            onClick={handleClose}
        >
            <div className="overflow-hidden rounded-lg border border-qc-line bg-qc-surface-2 shadow-qc">
                <div className="flex items-center gap-3 p-3.5">
                    <div
                        className={`grid h-9 w-9 shrink-0 place-items-center rounded-md ${
                            isLevelUp ? 'bg-qc-warning/15 text-qc-warning' : 'bg-qc-accent/15 text-qc-accent'
                        }`}
                    >
                        <Icon className="h-[18px] w-[18px]" />
                    </div>

                    <div className="min-w-0 flex-1">
                        {isLevelUp ? (
                            <>
                                <p className="text-sm font-semibold text-qc-fg">Level {event.level} reached</p>
                                <p className="text-xs text-qc-muted">+{event.xp_gained} XP earned</p>
                            </>
                        ) : (
                            <>
                                <p className="flex items-center gap-2 text-sm font-semibold text-qc-fg">
                                    +{event.xp_gained} XP
                                    {isFirstTime && (
                                        <span className="rounded bg-qc-accent/15 px-1.5 py-px text-[10px] font-medium text-qc-accent">
                                            First time
                                        </span>
                                    )}
                                </p>
                                <p className="truncate text-xs text-qc-muted">
                                    {event.message || `${event.xp_to_next_level} XP to next level`}
                                </p>
                            </>
                        )}
                    </div>

                    {!isLevelUp && (
                        <div className="text-right">
                            <div className="text-[10px] text-qc-subtle">Level</div>
                            <div className="font-mono text-sm font-semibold tabular-nums text-qc-fg">{event.level}</div>
                        </div>
                    )}
                </div>

                {!isLevelUp && (
                    <div className="h-0.5 bg-qc-surface-3">
                        <div
                            className="h-full origin-left bg-qc-accent transition-transform duration-500 ease-out-quick"
                            style={{ transform: `scaleX(${progress / 100})` }}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
