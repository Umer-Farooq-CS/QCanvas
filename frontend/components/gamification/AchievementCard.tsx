"use client";

import { Award, Target, Star, Zap, Activity } from '@/components/Icons';
import { Lock } from 'lucide-react';

export type AchievementRarity = "Common" | "Uncommon" | "Rare" | "Epic" | "Legendary";

export interface Achievement {
  id: string;
  name: string;
  description: string;
  category: string;
  rarity: AchievementRarity;
  xpReward: number;
  iconName: string; // Map to Lucide icons
  isUnlocked: boolean;
  progress: number;
  target: number;
  unlockedAt?: string;
}

interface AchievementCardProps {
  achievement: Achievement;
}

// Rarity is a small dot + label; the card itself stays neutral.
const RARITY_DOT: Record<AchievementRarity, string> = {
  Common: "bg-qc-subtle",
  Uncommon: "bg-qc-success",
  Rare: "bg-qc-accent",
  Epic: "bg-qc-pennylane",
  Legendary: "bg-qc-warning",
};

// Helper to get icon component
const getIcon = (name: string) => {
  switch (name) {
    case "rocket": return Zap;
    case "target": return Target;
    case "compass": return Activity;
    case "award": return Award;
    case "star": return Star;
    default: return Award;
  }
};

export default function AchievementCard({ achievement }: AchievementCardProps) {
  const Icon = getIcon(achievement.iconName);
  const isLocked = !achievement.isUnlocked;

  // Progress calculation
  const progressPercent = Math.min(100, (achievement.progress / achievement.target) * 100);
  const status = !isLocked ? "Completed" : achievement.progress > 0 ? "In progress" : "Not started";

  return (
    <div
      className={`flex gap-4 rounded-lg border p-4 transition-colors duration-150 ${
        isLocked
          ? "border-qc-line bg-qc-surface/60"
          : "border-qc-line bg-qc-surface hover:border-qc-line-strong"
      }`}
    >
      <div
        className={`grid h-11 w-11 shrink-0 place-items-center rounded-md ${
          isLocked ? "bg-qc-surface-2 text-qc-subtle" : "bg-qc-warning/15 text-qc-warning"
        }`}
      >
        {isLocked ? <Lock className="h-5 w-5" aria-hidden="true" /> : <Icon className="h-5 w-5" />}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <h3 className={`truncate text-sm font-semibold ${isLocked ? "text-qc-muted" : "text-qc-fg"}`}>
            {achievement.name}
          </h3>
          <span className="shrink-0 font-mono text-xs tabular-nums text-qc-subtle">
            +{achievement.xpReward} XP
          </span>
        </div>

        <p className="mt-1 line-clamp-2 text-sm text-qc-muted">{achievement.description}</p>

        <div className="mt-3 flex items-center justify-between text-xs text-qc-subtle">
          <span className="inline-flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${RARITY_DOT[achievement.rarity] ?? "bg-qc-subtle"}`} aria-hidden="true" />
            {achievement.rarity} · {status}
          </span>
          <span className="font-mono tabular-nums">
            {achievement.progress} / {achievement.target}
          </span>
        </div>

        <div
          className="mt-1.5 h-1 overflow-hidden rounded-full bg-qc-surface-3"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={achievement.target}
          aria-valuenow={achievement.progress}
          aria-label={`${achievement.name} progress`}
        >
          <div
            className={`h-full rounded-full transition-[width] duration-300 ease-out-quick ${
              isLocked ? "bg-qc-subtle" : "bg-qc-accent"
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}
