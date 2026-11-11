"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/lib/authStore";
import {
  useGamificationStore,
  getActivityDisplayName,
  getActivityIcon,
} from "@/lib/gamificationStore";
import {
  Zap,
  Play,
  Save,
  FolderPlus,
  Trophy,
  Rocket,
  Share,
  Book,
} from "@/components/Icons";
import { Repeat, Users, Sparkles } from "lucide-react";

// Icon mapping
const iconMap: Record<string, any> = {
  play: Play,
  rocket: Rocket,
  repeat: Repeat,
  sparkles: Sparkles,
  save: Save,
  "folder-plus": FolderPlus,
  "book-check": Book,
  trophy: Trophy,
  "share-2": Share,
  users: Users,
  zap: Zap,
};

export default function RecentActivityList({
  preview = false,
  limit = 10,
}: {
  preview?: boolean;
  limit?: number;
}) {
  const { token } = useAuthStore();
  const { recentActivities, fetchRecentActivities } = useGamificationStore();

  useEffect(() => {
    if (token) {
      fetchRecentActivities(token, limit);
    }
  }, [token, fetchRecentActivities, limit]);

  // Format timestamp
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const displayActivities = recentActivities.slice(0, limit);

  if (preview) {
    // Stripped version — no outer card (parent provides it)
    if (displayActivities.length === 0) {
      return (
        <p className="text-qc-subtle text-sm text-center py-6">
          No recent activity yet
        </p>
      );
    }
    return (
      <div className="space-y-3">
        {displayActivities.map((activity) => {
          const iconName = getActivityIcon(activity.activity_type);
          const Icon = iconMap[iconName] || Zap;
          const displayName = getActivityDisplayName(activity.activity_type);
          const isFirstTime = activity.activity_type.startsWith("first_");
          return (
            <div
              key={activity.id}
              className={`flex items-center gap-3 p-3 rounded-lg transition-all hover:bg-qc-surface-2 border ${isFirstTime ? "border-qc-accent/30 bg-qc-accent/5" : "border-qc-line bg-qc-surface-2"}`}
            >
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${isFirstTime ? "bg-qc-accent/15 text-qc-accent" : "bg-qc-surface-3 text-qc-muted"}`}
              >
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-qc-fg truncate">
                  {displayName}
                </p>
                <p className="text-xs text-qc-subtle">
                  {formatTime(activity.created_at)}
                </p>
              </div>
              <div
                className={`px-2 py-0.5 rounded text-xs font-bold ${isFirstTime ? "bg-qc-accent/15 text-qc-accent" : "bg-qc-surface-3 text-qc-fg"}`}
              >
                +{activity.xp_awarded} XP
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-qc-fg flex items-center gap-2">
          <Zap className="w-5 h-5 text-qc-warning" />
          Recent Activity
        </h2>
        <span className="text-xs text-qc-subtle">
          {recentActivities.length} activities
        </span>
      </div>

      {displayActivities.length === 0 ? (
        <div className="text-center py-12">
          <div className="w-16 h-16 rounded-full bg-qc-surface-2 flex items-center justify-center mx-auto mb-3">
            <Zap className="w-8 h-8 text-qc-subtle" />
          </div>
          <p className="text-qc-subtle text-sm">
            No recent activity yet
          </p>
          <p className="text-qc-subtle text-xs mt-1">
            Run a circuit to start earning XP.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {displayActivities.map((activity) => {
            const iconName = getActivityIcon(activity.activity_type);
            const Icon = iconMap[iconName] || Zap;
            const displayName = getActivityDisplayName(activity.activity_type);
            const isFirstTime = activity.activity_type.startsWith("first_");

            return (
              <div
                key={activity.id}
                className={`flex items-center gap-3 p-3 rounded-lg transition-all hover:bg-qc-surface-2 border ${
                  isFirstTime
                    ? "border-qc-accent/30 bg-qc-accent/5"
                    : "border-qc-line bg-qc-surface-2"
                }`}
              >
                {/* Icon */}
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                    isFirstTime
                      ? "bg-qc-accent/15 text-qc-accent"
                      : "bg-qc-surface-3 text-qc-muted"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-qc-fg truncate">
                      {displayName}
                    </p>
                    {isFirstTime && (
                      <span className="text-[10px] bg-qc-accent/15 text-qc-accent px-1.5 py-0.5 rounded font-medium">
                        First time
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-qc-subtle">
                    {formatTime(activity.created_at)}
                  </p>
                </div>

                {/* XP Badge */}
                <div
                  className={`px-2 py-0.5 rounded font-mono font-medium text-xs tabular-nums ${
                    isFirstTime
                      ? "bg-qc-accent/15 text-qc-accent"
                      : "bg-qc-surface-3 text-qc-fg"
                  }`}
                >
                  +{activity.xp_awarded} XP
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
