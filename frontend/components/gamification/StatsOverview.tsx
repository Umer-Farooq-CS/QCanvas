"use client";

import { Trophy, Star, Zap } from '@/components/Icons';;
import { Achievement } from "./AchievementCard";

interface StatsOverviewProps {
    achievements: Achievement[];
}

export default function StatsOverview({ achievements }: StatsOverviewProps) {
    const totalXP = achievements.reduce((acc, curr) => curr.isUnlocked ? acc + curr.xpReward : acc, 0);
    const totalUnlocked = achievements.filter(a => a.isUnlocked).length;
    const completionRate = Math.round((totalUnlocked / achievements.length) * 100) || 0;

    // Find rarest unlocked achievement for display
    const priorityMap = { Legendary: 5, Epic: 4, Rare: 3, Uncommon: 2, Common: 1 };
    const rarestUnlocked = achievements
        .filter(a => a.isUnlocked)
        .sort((a, b) => priorityMap[b.rarity] - priorityMap[a.rarity])[0];

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            {/* Total XP Card */}
            <div className="bg-qc-surface border border-qc-line rounded-xl p-5 relative overflow-hidden group hover:border-qc-line-strong transition-colors">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Zap className="w-16 h-16 text-qc-accent" />
                </div>
                <div className="relative z-10">
                    <p className="text-qc-muted text-sm font-medium mb-1">Total XP Earned</p>
                    <div className="flex items-baseline gap-2">
                        <h3 className="text-3xl font-bold text-qc-fg tracking-tight">{totalXP.toLocaleString()}</h3>
                        <span className="text-xs text-qc-accent font-bold">XP</span>
                    </div>
                    <div className="mt-2 text-xs text-qc-subtle">From achievements only</div>
                </div>
            </div>

            {/* Completion Rate Card */}
            <div className="bg-qc-surface border border-qc-line rounded-xl p-5 relative overflow-hidden group hover:border-qc-line-strong transition-colors">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Trophy className="w-16 h-16 text-qc-success" />
                </div>
                <div className="relative z-10">
                    <p className="text-qc-muted text-sm font-medium mb-1">Badges Unlocked</p>
                    <div className="flex items-baseline gap-2">
                        <h3 className="text-3xl font-bold text-qc-fg tracking-tight">{totalUnlocked}</h3>
                        <span className="text-qc-subtle text-lg">/ {achievements.length}</span>
                    </div>
                    <div className="mt-2 w-full bg-black/30 h-1.5 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-qc-success transition-[width] duration-500"
                            style={{ width: `${completionRate}%` }}
                        />
                    </div>
                </div>
            </div>

            {/* Rarest Badge Card */}
            <div className="bg-qc-surface border border-qc-line rounded-xl p-5 relative overflow-hidden group hover:border-qc-line-strong transition-colors">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Star className="w-16 h-16 text-qc-warning" />
                </div>
                <div className="relative z-10">
                    <p className="text-qc-muted text-sm font-medium mb-1">Rarest Unlock</p>
                    {rarestUnlocked ? (
                        <div>
                            <h3 className="text-lg font-bold text-qc-fg truncate max-w-[180px]" title={rarestUnlocked.name}>
                                {rarestUnlocked.name}
                            </h3>
                            <span className={`inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border border-current text-qc-warning border-yellow-500/30`}>
                                {rarestUnlocked.rarity}
                            </span>
                        </div>
                    ) : (
                        <div className="text-qc-subtle text-sm italic py-2">No badges yet</div>
                    )}
                </div>
            </div>
        </div>
    );
}
