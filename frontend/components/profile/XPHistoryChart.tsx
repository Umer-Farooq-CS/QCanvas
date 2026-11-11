"use client";

import { useEffect } from "react";
import { TrendingUp } from "@/components/Icons";
import { useGamificationStore } from "@/lib/gamificationStore";
import { useAuthStore } from "@/lib/authStore";

export default function XPHistoryChart({
  standalone = false,
}: {
  standalone?: boolean;
}) {
  const { recentActivities, fetchRecentActivities } = useGamificationStore();
  const { token } = useAuthStore();

  useEffect(() => {
    if (token) {
      fetchRecentActivities(token, 30);
    }
  }, [token, fetchRecentActivities]);

  // Build 7-day buckets from recent activities
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const today = new Date();
  const buckets: { day: string; xp: number; date: Date }[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    buckets.push({ day: days[d.getDay()], xp: 0, date: d });
  }
  recentActivities.forEach((a) => {
    const actDate = new Date(a.created_at);
    const bucket = buckets.find(
      (b) => b.date.toDateString() === actDate.toDateString(),
    );
    if (bucket) bucket.xp += a.xp_awarded;
  });

  const maxXP = Math.max(...buckets.map((d) => d.xp), 1);
  const totalWeeklyXP = buckets.reduce((s, b) => s + b.xp, 0);

  const chart = (
    <div className="flex items-end justify-between h-44 gap-2 pt-4">
      {buckets.map((item, index) => {
        const heightPercent = maxXP > 0 ? (item.xp / maxXP) * 100 : 0;
        const isToday = index === buckets.length - 1;
        return (
          <div
            key={index}
            className="flex flex-col items-center gap-2 flex-1 group"
          >
            <div className="w-full relative flex items-end justify-center h-full">
              {/* Tooltip */}
              <div className="absolute -top-8 bg-gray-800 text-qc-fg text-[10px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 border border-qc-line pointer-events-none">
                {item.xp > 0 ? `${item.xp} XP` : "No activity"}
              </div>

              {/* Bar background (always visible) */}
              <div className="w-full max-w-[32px] relative">
                <div className="w-full bg-gray-500/20 dark:bg-white/5 rounded-t-sm h-36" />
                {/* Actual bar */}
                {item.xp > 0 && (
                  <div
                    className={`absolute bottom-0 w-full rounded-t-sm transition-all duration-500 ${
                      isToday
                        ? "bg-qc-accent"
                        : "bg-qc-accent/45 hover:bg-qc-accent/70"
                    }`}
                    style={{ height: `${heightPercent}%` }}
                  />
                )}
              </div>
            </div>
            <span
              className={`text-[10px] font-medium uppercase ${isToday ? "text-qc-accent" : "text-qc-subtle"}`}
            >
              {item.day}
            </span>
          </div>
        );
      })}
    </div>
  );

  if (standalone) {
    return (
      <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-lg text-qc-fg flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-qc-accent" />
            Weekly Activity
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-qc-muted bg-qc-surface-2 px-2 py-1 rounded">
              {totalWeeklyXP > 0
                ? `+${totalWeeklyXP} XP this week`
                : "Last 7 Days"}
            </span>
          </div>
        </div>
        {chart}
      </div>
    );
  }

  // Inline mode (inside parent card)
  return (
    <div className="space-y-4">
      {totalWeeklyXP > 0 && (
        <div className="flex flex-col -mt-2">
          <span className="text-2xl font-semibold tabular-nums text-qc-fg">
            +{totalWeeklyXP} XP
          </span>
          <span className="text-[10px] uppercase tracking-wider text-qc-subtle font-semibold opacity-80">
            This Week&apos;s Gains
          </span>
        </div>
      )}
      <div className="mt-8">{chart}</div>
    </div>
  );
}
