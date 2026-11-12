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
import { ShieldCheck } from "lucide-react";
import { authApi, type AdminAccessRequestResponse } from "@/lib/api";
import toast from "react-hot-toast";

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div
      className={`bg-qc-surface border border-qc-line rounded-xl p-4 flex flex-col gap-2 hover:border-qc-line-strong transition-colors`}
    >
      <div
        className={`w-9 h-9 rounded-lg bg-qc-surface-2 flex items-center justify-center`}
      >
        <Icon className="w-5 h-5 text-qc-muted" />
      </div>
      <div>
        <p className="text-2xl font-bold text-qc-fg leading-tight">{value}</p>
        <p className="text-[11px] text-qc-muted font-medium uppercase tracking-wide mt-0.5">
          {label}
        </p>
        {sub && (
          <p className="text-[10px] text-qc-subtle mt-0.5">
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
      <Icon className="w-5 h-5 text-qc-accent" />
      <h2 className="text-lg font-bold text-qc-fg">{title}</h2>
      {badge && (
        <span className="text-xs text-qc-subtle bg-qc-surface-2 px-2 py-0.5 rounded-full">
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
      <div className="h-48 bg-qc-surface-2 rounded-xl" />
      <div className="grid grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 bg-qc-surface-2 rounded-xl" />
        ))}
      </div>
      <div className="h-32 bg-qc-surface-2 rounded-xl" />
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
  const [adminAccessStatus, setAdminAccessStatus] =
    useState<AdminAccessRequestResponse["status"]>(
      user?.role === "admin" ? "approved" : "not_requested",
    );
  const [adminRequestLoading, setAdminRequestLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !token || user?.role === "demo") return;

    let cancelled = false;
    authApi.getAdminAccessRequestStatus(token).then((response) => {
      if (cancelled) return;
      // Status is secondary on this page: on failure keep the default
      // rather than interrupting every profile visit with a toast.
      if (!response.success || !response.data) return;
      setAdminAccessStatus(response.data.status);
    });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, token, user?.role]);

  const handleAdminAccessRequest = async () => {
    if (!token) return;
    setAdminRequestLoading(true);
    try {
      const response = await authApi.requestAdminAccess(token);
      if (!response.success || !response.data) {
        throw new Error(response.error || "Failed to request admin access");
      }
      setAdminAccessStatus(response.data.status);
      toast.success(response.data.message);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to request admin access",
      );
    } finally {
      setAdminRequestLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated && token) {
      fetchStats(token);
      fetchAchievements(token);
    }
  }, [isAuthenticated, token, fetchStats, fetchAchievements]);

  if (loading) {
    return (
      <div className="qc-page">
        <SimpleTopBar />
        <div className="h-20" />
        <div className="mx-auto max-w-[96rem] p-4 md:p-8 lg:px-10">
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
    <div className="qc-page">
      <SimpleTopBar />

      {/* Spacer below topbar */}
      <div className="h-14" />


      <div className="p-4 md:p-8">
        <div className="mx-auto max-w-[96rem] lg:px-4">
          {/* ── 3-column grid ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* ─ Left Column ─────────────────────────────────────── */}
            <div className="lg:col-span-1 space-y-5">
              {/* Profile card */}
              <ProfileHeader />

              {user?.role !== "demo" && (
                <section className="rounded-xl border border-qc-line bg-qc-surface p-5" aria-labelledby="admin-access-heading">
                  <div className="flex items-start gap-3">
                    <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-qc-accent" aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 id="admin-access-heading" className="text-sm font-semibold text-qc-fg">
                          Admin access
                        </h2>
                        {adminAccessStatus !== "not_requested" && (
                          <span
                            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                              adminAccessStatus === "approved"
                                ? "bg-qc-success/10 text-qc-success"
                                : "bg-qc-warning/10 text-qc-warning"
                            }`}
                          >
                            {adminAccessStatus === "approved" ? "Approved" : "Pending"}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm leading-relaxed text-qc-muted">
                        {adminAccessStatus === "approved"
                          ? "Your account has admin access."
                          : adminAccessStatus === "pending"
                            ? "Your request is waiting for the master administrator. You can ask again after 24 hours if it is not approved."
                            : "Ask the master administrator to give this account admin access. They approve requests by email."}
                      </p>
                      {adminAccessStatus === "not_requested" && user?.role !== "admin" && (
                        <button
                          type="button"
                          onClick={handleAdminAccessRequest}
                          disabled={adminRequestLoading}
                          className="qc-btn qc-btn-secondary qc-btn-sm mt-3"
                        >
                          {adminRequestLoading ? "Sending request…" : "Request admin access"}
                        </button>
                      )}
                    </div>
                  </div>
                </section>
              )}

              {/* Stats grid */}
              <div className="grid grid-cols-3 gap-3">
                <StatCard
                  icon={Zap}
                  label="Total XP"
                  value={formatXP(totalXP)}
                />
                <StatCard
                  icon={Flame}
                  label="Streak"
                  value={currentStreak}
                  sub="days"
                />
                <StatCard
                  icon={Award}
                  label="Best"
                  value={longestStreak}
                  sub="days"
                />
              </div>

              {/* Progress card */}
              <div className="bg-qc-surface border border-qc-line rounded-xl p-5">
                <SectionHeader icon={Target} title="Progress" />
                <div className="space-y-4">
                  {/* Level */}
                  <div
                    title={`${stats?.xp_to_next_level.toLocaleString()} XP remaining to Level ${level + 1}`}
                    className="group/xp cursor-help"
                  >
                    <div className="flex justify-between text-xs text-qc-subtle mb-1.5 transition-colors group-hover/xp:text-qc-accent">
                      <span className="font-medium">
                        Level {level} — {getLevelBadge(level)}
                      </span>
                      <span className="font-bold">
                        {Math.round(stats?.progress_percentage || 0)}%
                      </span>
                    </div>
                    <div className="h-2 bg-qc-surface-3 rounded-full overflow-hidden relative">
                      <div
                        className="h-full rounded-full transition-[width] duration-500 ease-out-quick"
                        style={{
                          backgroundImage:
                            "linear-gradient(rgb(var(--qc-accent)), rgb(var(--qc-accent)))",
                          width: `${Math.min(stats?.progress_percentage || 0, 100)}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Achievements completion */}
                  <div className="group/ach hover:opacity-90 transition-opacity">
                    <div className="flex justify-between text-xs text-qc-subtle mb-1.5">
                      <span className="font-medium">
                        Achievements ({unlockedCount}/{totalAchievements})
                      </span>
                      <span className="text-qc-warning font-bold">
                        {completionPct}%
                      </span>
                    </div>
                    <div className="h-2 bg-qc-surface-3 rounded-full overflow-hidden relative">
                      <div
                        className="h-full rounded-full transition-[width] duration-500 ease-out-quick"
                        style={{
                          backgroundImage:
                            "linear-gradient(rgb(var(--qc-warning)), rgb(var(--qc-warning)))",
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
                      className="bg-qc-surface-2 border border-qc-line rounded-lg p-3 flex items-center gap-3"
                    >
                      <Ic className="w-4 h-4 text-qc-subtle shrink-0" />
                      <div>
                        <p className="text-base font-bold text-qc-fg">
                          {value}
                        </p>
                        <p className="text-[10px] text-qc-subtle">
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
              <div className="bg-qc-surface border border-qc-line rounded-xl p-1.5 flex gap-1">
                {tabs.map(({ id, label, icon: TIcon }) => (
                  <button
                    key={id}
                    id={`profile-tab-${id}`}
                    onClick={() => setActiveTab(id)}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                      activeTab === id
                        ? "bg-qc-surface-3 text-qc-fg "
                        : "text-qc-subtle hover:text-qc-fg hover:bg-qc-surface-2"
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
                  <div className="bg-qc-surface border border-qc-line rounded-xl p-5">
                    <SectionHeader icon={TrendingUp} title="Weekly XP" />
                    <XPHistoryChart />
                  </div>

                  {/* Recent Activity (preview) */}
                  <div className="bg-qc-surface border border-qc-line rounded-xl p-5">
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
                <div className="bg-qc-surface border border-qc-line rounded-xl p-5">
                  <SectionHeader
                    icon={Trophy}
                    title="Achievements"
                    badge={`${unlockedCount} unlocked`}
                  />
                  <AchievementsPreview expanded />
                </div>
              )}

              {activeTab === "activity" && (
                <div className="bg-qc-surface border border-qc-line rounded-xl p-5">
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
