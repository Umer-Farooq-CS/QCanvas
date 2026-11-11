"use client";

import { useEffect, useState } from "react";
import { Trophy, Star, Zap, Award, Target, Activity } from '@/components/Icons';
import { X } from 'lucide-react';
import { AchievementUnlock } from "@/lib/gamificationStore";

interface AchievementToastProps {
    achievement: AchievementUnlock | null;
    onClose: () => void;
}

// Rarity is shown as a small coloured dot and label rather than a full
// gradient card, so the toast stays calm next to the editor.
const RARITY_DOT: Record<string, string> = {
    common: "bg-qc-subtle",
    uncommon: "bg-qc-success",
    rare: "bg-qc-accent",
    epic: "bg-qc-pennylane",
    legendary: "bg-qc-warning",
};

const RARITY_LABELS: Record<string, string> = {
    common: "Common",
    uncommon: "Uncommon",
    rare: "Rare",
    epic: "Epic",
    legendary: "Legendary",
};

const getIcon = (name: string) => {
    switch (name) {
        case "rocket": return Zap;
        case "target": return Target;
        case "compass": return Activity;
        case "award": return Award;
        case "star": return Star;
        default: return Trophy;
    }
};

export default function AchievementToast({ achievement, onClose }: AchievementToastProps) {
    const [isVisible, setIsVisible] = useState(false);
    const [isExiting, setIsExiting] = useState(false);

    useEffect(() => {
        if (achievement) {
            setIsVisible(true);
            setIsExiting(false);

            const timer = setTimeout(() => {
                handleClose();
            }, 6000);

            return () => clearTimeout(timer);
        }
    }, [achievement]);

    const handleClose = () => {
        setIsExiting(true);
        setTimeout(() => {
            setIsVisible(false);
            setIsExiting(false);
            onClose();
        }, 400);
    };

    if (!achievement || !isVisible) return null;

    const rarity = achievement.rarity?.toLowerCase() || "common";
    const dot = RARITY_DOT[rarity] || RARITY_DOT.common;
    const rarityLabel = RARITY_LABELS[rarity] || "Common";
    const Icon = getIcon(achievement.icon_name);

    return (
        <div
            role="status"
            aria-live="polite"
            className={`fixed right-6 top-6 z-[9999] w-[340px] max-w-[calc(100vw-2rem)] transition-[opacity,transform] duration-200 ease-out-quick ${
                isExiting ? "translate-x-4 opacity-0" : "achievement-toast-in"
            }`}
        >
            <div className="overflow-hidden rounded-lg border border-qc-line bg-qc-surface-2 shadow-qc">
                <div className="flex items-start gap-3 p-4">
                    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-qc-warning/15 text-qc-warning">
                        <Icon className="h-5 w-5" />
                    </div>

                    <div className="min-w-0 flex-1">
                        <p className="text-xs text-qc-subtle">Achievement unlocked</p>
                        <h4 className="truncate text-sm font-semibold text-qc-fg">{achievement.name}</h4>
                        <p className="line-clamp-2 text-xs leading-relaxed text-qc-muted">
                            {achievement.description}
                        </p>
                        <div className="mt-2 flex items-center gap-3 text-xs">
                            <span className="inline-flex items-center gap-1.5 text-qc-muted">
                                <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden="true" />
                                {rarityLabel}
                            </span>
                            <span className="font-mono tabular-nums text-qc-fg">+{achievement.xp_reward} XP</span>
                        </div>
                    </div>

                    <button
                        type="button"
                        onClick={handleClose}
                        className="qc-focus -m-1 grid h-7 w-7 place-items-center rounded-md text-qc-subtle transition-colors duration-150 hover:bg-qc-surface-3 hover:text-qc-fg"
                        aria-label="Dismiss"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                {/* Time remaining before auto-dismiss */}
                <div className="h-0.5 bg-qc-surface-3">
                    <div className="achievement-toast-timer h-full origin-left bg-qc-subtle" />
                </div>
            </div>

            <style jsx>{`
        .achievement-toast-in {
          animation: achievementIn 220ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
        }
        .achievement-toast-timer {
          animation: achievementTimer 6s linear forwards;
        }
        @keyframes achievementIn {
          from {
            transform: translateX(16px);
            opacity: 0;
          }
          to {
            transform: none;
            opacity: 1;
          }
        }
        @keyframes achievementTimer {
          from {
            transform: scaleX(1);
          }
          to {
            transform: scaleX(0);
          }
        }
      `}</style>
        </div>
    );
}
