"use client";

import { useEffect, useState } from "react";
import { useRequireAuth } from "@/lib/auth";
import { useAuthStore } from "@/lib/authStore";
import {
  useGamificationStore,
  formatXP,
  getLevelBadge,
} from "@/lib/gamificationStore";
import ProfileHeader from "@/components/profile/ProfileHeader";
import XPHistoryChart from "@/components/profile/XPHistoryChart";
import RecentActivityList from "@/components/profile/RecentActivityList";
import AchievementsPreview from "@/components/profile/AchievementsPreview";
import SimpleTopBar from "@/components/SimpleTopBar";
import {
  Zap,
  Flame,
  Award,
  TrendingUp,
  Activity,
  Trophy,
  Star,
  Target,
  Layers,
  BarChart3,
} from "@/components/Icons";

// ─── Stat Card ────────────────────────────────────────────────────────────────
// Tailwind only generates classes it can find as complete strings in the source,
// so accent classes must be listed statically (not built as `bg-${accent}/10`).
const STAT_CARD_ACCENTS = {
  "yellow-400": {
    hoverBorder: "hover:border-yellow-400/30",
    iconBg: "bg-yellow-400/10",
    iconText: "text-yellow-400",
  },
  "orange-500": {
    hoverBorder: "hover:border-orange-500/30",
    iconBg: "bg-orange-500/10",
    iconText: "text-orange-500",
  },
  "purple-400": {
    hoverBorder: "hover:border-purple-400/30",
    iconBg: "bg-purple-400/10",
    iconText: "text-purple-400",
  },
} as const;

type StatCardAccent = keyof typeof STAT_CARD_ACCENTS;

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  accent: StatCardAccent;
}) {
  const accentClasses = STAT_CARD_ACCENTS[accent];
  return (
    <div
      className={`bg-quantum-glass-dark border border-white/10 rounded-xl p-4 flex flex-col gap-2 ${accentClasses.hoverBorder} transition-all group`}
    >
      <div
        className={`w-9 h-9 rounded-lg ${accentClasses.iconBg} flex items-center justify-center group-hover:scale-110 transition-transform`}
      >
        <Icon className={`w-5 h-5 ${accentClasses.iconText}`} />
      </div>
      <div>
        <p className="text-2xl font-bold text-white leading-tight">{value}</p>
        <p className="text-[11px] text-black dark:text-gray-400 font-medium uppercase tracking-wide mt-0.5">
          {label}
        </p>
        {sub && (
          <p className="text-[10px] text-black dark:text-gray-600 mt-0.5">
            {sub}
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Section Header ───────────────────────────────────────────────────────────
function SectionHeader({
  icon: Icon,
  title,
  badge,
}: {
  icon: React.ElementType;
  title: string;
  badge?: string;
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon className="w-5 h-5 text-quantum-blue-light" />
      <h2 className="text-lg font-bold text-white">{title}</h2>
      {badge && (
        <span className="text-xs text-black dark:text-gray-500 bg-white/5 px-2 py-0.5 rounded-full">
          {badge}
        </span>
      )}
    </div>
  );
}

// ─── Skeleton Loader ──────────────────────────────────────────────────────────
function ProfileSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-48 bg-white/5 rounded-xl" />
      <div className="grid grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 bg-white/5 rounded-xl" />
        ))}
      </div>
      <div className="h-32 bg-white/5 rounded-xl" />
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function ProfilePage() {
  const { isAuthenticated, loading } = useRequireAuth();
  const { token, user } = useAuthStore();
  const { stats, fetchStats, achievements, fetchAchievements } =
    useGamificationStore();
  const [activeTab, setActiveTab] = useState<
    "overview" | "achievements" | "activity"
  >("overview");

  useEffect(() => {
    if (isAuthenticated && token) {
      fetchStats(token);
      fetchAchievements(token);
    }
  }, [isAuthenticated, token, fetchStats, fetchAchievements]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a1a]">
        <SimpleTopBar />
        <div className="h-20" />
        <div className="p-4 md:p-8 max-w-6xl mx-auto">
          <ProfileSkeleton />
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  // Derived stats
  const totalXP = stats?.total_xp || 0;
  const currentStreak = stats?.current_streak || 0;
  const longestStreak = stats?.longest_streak || 0;
  const level = stats?.level || 1;
  const unlockedCount = achievements.filter((a) => a.is_unlocked).length;
  const totalAchievements = achievements.length;
  const completionPct =
    totalAchievements > 0
      ? Math.round((unlockedCount / totalAchievements) * 100)
      : 0;

  const tabs = [
    { id: "overview" as const, label: "Overview", icon: BarChart3 },
    { id: "achievements" as const, label: "Achievements", icon: Trophy },
    { id: "activity" as const, label: "Activity", icon: Activity },
  ];

  return (
    <div className="min-h-screen dark:bg-[#0a0a1a] bg-gray-50 text-gray-900 dark:text-white transition-colors duration-300">
      <SimpleTopBar />

      {/* Spacer below topbar */}
      <div className="h-14" />

      {/* Subtle top gradient accent */}
      <div className="fixed top-14 left-0 right-0 h-px bg-gradient-to-r from-transparent via-quantum-blue/30 to-transparent pointer-events-none z-40" />

      <div className="p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          {/* ── 3-column grid ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* ─ Left Column ─────────────────────────────────────── */}
            <div className="lg:col-span-1 space-y-5">
              {/* Profile card */}
              <ProfileHeader />

              {/* Stats grid */}
              <div className="grid grid-cols-3 gap-3">
                <StatCard
                  icon={Zap}
                  label="Total XP"
                  value={formatXP(totalXP)}
                  accent="yellow-400"
                />
                <StatCard
                  icon={Flame}
                  label="Streak"
                  value={currentStreak}
                  sub="days"
                  accent="orange-500"
                />
                <StatCard
                  icon={Award}
                  label="Best"
                  value={longestStreak}
                  sub="days"
                  accent="purple-400"
                />
              </div>

              {/* Progress card */}
              <div className="bg-quantum-glass-dark border border-white/10 rounded-xl p-5">
                <SectionHeader icon={Target} title="Progress" />
                <div className="space-y-4">
                  {/* Level */}
                  <div
                    title={`${stats?.xp_to_next_level.toLocaleString()} XP remaining to Level ${level + 1}`}
                    className="group/xp cursor-help"
                  >
                    <div className="flex justify-between text-xs text-black dark:text-gray-500 mb-1.5 transition-colors group-hover/xp:text-quantum-blue-light">
                      <span className="font-medium">
                        Level {level} — {getLevelBadge(level)}
                      </span>
                      <span className="font-bold">
                        {Math.round(stats?.progress_percentage || 0)}%
                      </span>
                    </div>
                    <div className="h-3 bg-gray-200 dark:bg-white/10 rounded-full overflow-hidden border border-black/5 dark:border-white/5 relative">
                      <div
                        className="h-full rounded-full transition-all duration-1000 ease-out"
                        style={{
                          backgroundImage:
                            "linear-gradient(to right, #2563eb, #6366f1, #9333ea)",
                          width: `${Math.min(stats?.progress_percentage || 0, 100)}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Achievements completion */}
                  <div className="group/ach hover:opacity-90 transition-opacity">
                    <div className="flex justify-between text-xs text-black dark:text-gray-500 mb-1.5">
                      <span className="font-medium">
                        Achievements ({unlockedCount}/{totalAchievements})
                      </span>
                      <span className="text-yellow-500 font-bold">
                        {completionPct}%
                      </span>
                    </div>
                    <div className="h-3 bg-gray-200 dark:bg-white/10 rounded-full overflow-hidden border border-black/5 dark:border-white/5 relative">
                      <div
                        className="h-full rounded-full transition-all duration-1000 ease-out"
                        style={{
                          backgroundImage:
                            "linear-gradient(to right, #eab308, #f97316)",
                          width: `${completionPct}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Quick numbers */}
                <div className="grid grid-cols-2 gap-3 mt-5">
                  {[
                    { label: "Level", value: level, icon: Star },
                    {
                      label: "Achievements",
                      value: `${unlockedCount}/${totalAchievements}`,
                      icon: Trophy,
                    },
                  ].map(({ label, value, icon: Ic }) => (
                    <div
                      key={label}
                      className="bg-white/[0.03] border border-white/5 rounded-lg p-3 flex items-center gap-3"
                    >
                      <Ic className="w-4 h-4 text-black dark:text-gray-500 shrink-0" />
                      <div>
                        <p className="text-base font-bold text-white">
                          {value}
                        </p>
                        <p className="text-[10px] text-black dark:text-gray-500">
                          {label}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* ─ Right Column ────────────────────────────────────── */}
            <div className="lg:col-span-2 space-y-5">
              {/* Tab bar */}
              <div className="bg-quantum-glass-dark border border-white/10 rounded-xl p-1.5 flex gap-1">
                {tabs.map(({ id, label, icon: TIcon }) => (
                  <button
                    key={id}
                    id={`profile-tab-${id}`}
                    onClick={() => setActiveTab(id)}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                      activeTab === id
                        ? "bg-gray-200 dark:bg-gray-900 dark:bg-quantum-blue/20 text-white border border-quantum-blue/30 shadow-inner"
                        : "text-black dark:text-gray-500 hover:text-gray-900 hover:bg-white/5"
                    }`}
                  >
                    <TIcon className="w-4 h-4 shrink-0" />
                    <span className="hidden sm:inline">{label}</span>
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              {activeTab === "overview" && (
                <div className="space-y-5">
                  {/* XP Chart */}
                  <div className="bg-quantum-glass-dark border border-white/10 rounded-xl p-5">
                    <SectionHeader icon={TrendingUp} title="Weekly XP" />
                    <XPHistoryChart />
                  </div>

                  {/* Recent Activity (preview) */}
                  <div className="bg-quantum-glass-dark border border-white/10 rounded-xl p-5">
                    <SectionHeader
                      icon={Activity}
                      title="Recent Activity"
                      badge="Last 5"
                    />
                    <RecentActivityList preview limit={5} />
                  </div>
                </div>
              )}

              {activeTab === "achievements" && (
                <div className="bg-quantum-glass-dark border border-white/10 rounded-xl p-5">
                  <SectionHeader
                    icon={Trophy}
                    title="Achievements"
                    badge={`${unlockedCount} unlocked`}
                  />
                  <AchievementsPreview expanded />
                </div>
              )}

              {activeTab === "activity" && (
                <div className="bg-quantum-glass-dark border border-white/10 rounded-xl p-5">
                  <SectionHeader icon={Activity} title="All Activity" />
                  <RecentActivityList />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
