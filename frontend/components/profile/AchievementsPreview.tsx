"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Trophy } from '@/components/Icons';
import { ChevronRight } from 'lucide-react';;
import AchievementCard from "@/components/gamification/AchievementCard";
import { useGamificationStore, getCategoryDisplayName, AchievementData } from "@/lib/gamificationStore";
import { useAuthStore } from "@/lib/authStore";

// Map backend data to AchievementCard format
function mapToCardFormat(a: AchievementData) {
    const rarityMap: Record<string, "Common" | "Uncommon" | "Rare" | "Epic" | "Legendary"> = {
        common: "Common",
        uncommon: "Uncommon",
        rare: "Rare",
        epic: "Epic",
        legendary: "Legendary",
    };

    return {
        id: a.id,
        name: a.name,
        description: a.description,
        category: getCategoryDisplayName(a.category),
        rarity: rarityMap[a.rarity] || "Common" as const,
        xpReward: a.xp_reward,
        iconName: a.icon_name,
        isUnlocked: a.is_unlocked,
        progress: a.progress,
        target: a.target,
        unlockedAt: a.unlocked_at || undefined,
    };
}

export default function AchievementsPreview({ expanded = false }: { expanded?: boolean }) {
    const { achievements, fetchAchievements } = useGamificationStore();
    const { token } = useAuthStore();

    useEffect(() => {
        if (token) {
            fetchAchievements(token);
        }
    }, [token, fetchAchievements]);

    const mapped = achievements.map(mapToCardFormat);

    // Expanded: all achievements sorted (unlocked → in-progress → locked)
    const displayItems = expanded
        ? [
            ...mapped.filter((a) => a.isUnlocked).sort((a, b) =>
                (b.unlockedAt || "").localeCompare(a.unlockedAt || "")
            ),
            ...mapped.filter((a) => !a.isUnlocked && a.progress > 0)
                .sort((a, b) => b.progress / b.target - a.progress / a.target),
            ...mapped.filter((a) => !a.isUnlocked && a.progress === 0),
        ]
        : (() => {
            const unlocked = mapped.filter((a) => a.isUnlocked).slice(0, 2);
            const inProgress = mapped
                .filter((a) => !a.isUnlocked && a.progress > 0)
                .sort((a, b) => b.progress / b.target - a.progress / a.target)
                .slice(0, 3 - unlocked.length);
            return [...unlocked, ...inProgress].slice(0, 3);
        })();

    // Fallback if not signed in
    if (displayItems.length === 0 && !token) {
        return (
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-bold text-lg text-qc-fg flex items-center gap-2">
                        <Trophy className="w-5 h-5 text-qc-warning" />
                        Achievements
                    </h3>
                </div>
                <p className="text-qc-subtle text-sm">Sign in to track your achievements.</p>
            </div>
        );
    }

    if (expanded) {
        return (
            <div className="space-y-3">
                {displayItems.length === 0 ? (
                    <p className="text-qc-subtle text-sm text-center py-8">No achievements yet — run a circuit to earn one.</p>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {displayItems.map((achievement) => (
                            <AchievementCard key={achievement.id} achievement={achievement} />
                        ))}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-lg text-qc-fg flex items-center gap-2">
                    <Trophy className="w-5 h-5 text-qc-warning" />
                    Achievements
                    {achievements.length > 0 && (
                        <span className="text-xs text-qc-subtle font-normal">
                            {mapped.filter((a) => a.isUnlocked).length}/{mapped.length}
                        </span>
                    )}
                </h3>
                <Link
                    href="/achievements"
                    className="text-xs text-qc-accent hover:text-qc-fg flex items-center gap-1 transition-colors"
                >
                    View All <ChevronRight className="w-3 h-3" />
                </Link>
            </div>

            <div className="grid grid-cols-1 gap-3">
                {displayItems.map((achievement) => (
                    <AchievementCard key={achievement.id} achievement={achievement} />
                ))}
            </div>

            {displayItems.length === 0 && (
                <p className="text-qc-subtle text-sm text-center py-4">
                    Run a circuit in the editor to earn your first achievement.
                </p>
            )}
        </div>
    );
}
