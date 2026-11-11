"use client";

import { useState } from "react";
import { useAuthStore } from "@/lib/authStore";
import { useGamificationStore, getLevelBadge } from "@/lib/gamificationStore";
import { Edit2, MapPin, Calendar, Shield, Sparkles } from "lucide-react";
import { useEffect } from "react";
import EditProfileModal from "@/components/profile/EditProfileModal";

export default function ProfileHeader() {
  const { user, token } = useAuthStore();
  const { stats, fetchStats } = useGamificationStore();
  const [editOpen, setEditOpen] = useState(false);

  useEffect(() => {
    if (user && token) {
      fetchStats(token);
    }
  }, [user, token, fetchStats]);

  const displayUser = user || {
    username: "QuantumUser",
    full_name: "Quantum Explorer",
    email: "explorer@qcanvas.com",
    created_at: new Date().toISOString(),
    bio: undefined,
  };

  const initials = displayUser.full_name
    ? displayUser.full_name
        .split(" ")
        .map((n: string) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "QU";

  const level = stats?.level || 1;
  const badge = getLevelBadge(level);
  const xpProgress = stats?.progress_percentage || 0;

  const joinDate = new Date(displayUser.created_at).toLocaleDateString(
    "en-US",
    {
      month: "long",
      year: "numeric",
    },
  );

  const bio =
    (displayUser as typeof displayUser & { bio?: string }).bio ||
    "No bio provided yet. Use Edit profile to add one.";

  return (
    <>
      <div className="bg-qc-surface border border-qc-line rounded-xl overflow-hidden relative group">
        {/* Cover Banner */}
        <div className="h-20 relative overflow-hidden border-b border-qc-line">
          <div className="absolute inset-0 bg-qc-surface-2" />
        </div>

        <div className="px-5 pb-5 relative">
          {/* Avatar + Edit Row */}
          <div className="flex items-start justify-between">
            {/* Avatar */}
            <div className="absolute -top-12 left-5">
              <div className="w-[88px] h-[88px] rounded-full bg-qc-surface p-[3px] shadow-qc">
                <div className="w-full h-full rounded-full bg-gray-700/30 flex items-center justify-center text-3xl font-bold text-qc-fg select-none">
                  {initials}
                </div>
              </div>
              {/* Online dot */}
              <div
                className="absolute bottom-1.5 right-1.5 w-4 h-4 bg-qc-success rounded-full border-[3px] border-qc-surface"
                title="Online"
              />
            </div>

            {/* Edit button */}
            <div className="flex justify-end pt-3 w-full mb-3">
              <button
                id="open-edit-profile-btn"
                onClick={() => setEditOpen(true)}
                className="flex items-center gap-2 px-3.5 py-1.5 bg-qc-surface-2 hover:bg-qc-surface-3 border border-qc-line hover:border-qc-line-strong rounded-lg text-sm font-medium text-qc-muted hover:text-qc-fg transition-all group/btn"
              >
                <Edit2 className="w-3.5 h-3.5 group-hover/btn:text-qc-accent transition-colors" />
                Edit Profile
              </button>
            </div>
          </div>

          {/* User Info */}
          <div className="mt-2">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold text-qc-fg">
                {displayUser.full_name}
              </h1>
              <span className="inline-flex items-center gap-1 text-[11px] bg-quantum-blue/20 text-qc-accent px-2 py-0.5 rounded border border-qc-line-strong font-mono font-medium">
                <Sparkles className="w-3 h-3" />
                Lv.{level}
              </span>
            </div>
            <p className="text-qc-muted text-sm mt-0.5">
              @{displayUser.username}
            </p>
          </div>

          {/* Bio */}
          <p className="mt-3 text-qc-muted text-sm leading-relaxed">
            {bio}
          </p>

          {/* Metadata row */}
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-qc-subtle">
            <div className="flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-qc-subtle" />
              <span>{badge}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-qc-subtle" />
              <span>Quantum Realm</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-qc-subtle" />
              <span>Joined {joinDate}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Edit Modal */}
      <EditProfileModal isOpen={editOpen} onClose={() => setEditOpen(false)} />
    </>
  );
}
