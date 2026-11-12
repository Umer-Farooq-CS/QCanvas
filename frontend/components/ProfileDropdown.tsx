"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Award } from "@/components/Icons";
import { User, LogOut, ChevronDown } from "lucide-react";
import { useAuthStore } from "@/lib/authStore";
import {
  useGamificationStore,
  getLevelBadge,
  formatXP,
} from "@/lib/gamificationStore";

interface ProfileDropdownProps {
  onLogout: () => void;
}

export default function ProfileDropdown({ onLogout }: ProfileDropdownProps) {
  const { user, token } = useAuthStore();
  const { stats, fetchStats } = useGamificationStore();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch gamification stats when component mounts
  useEffect(() => {
    if (user && token) {
      fetchStats(token);
    }
  }, [user, token, fetchStats]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKey);
    };
  }, []);

  if (!user) return null;
  const isGuest = user.role === "demo";

  // Initials for avatar
  const initials = user.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : user.icon_name || "U";

  // Use real stats or fallback to defaults
  const level = stats?.level || 1;
  const badge = getLevelBadge(level);
  const xp = stats?.total_xp || 0;
  const nextLevelXp = stats?.xp_next_level || 100;
  const currentLevelXp = stats?.xp_current_level || 0;

  // Calculate progress for progress bar
  // Calculate progress for progress bar locally to ensure consistency with display text
  const range = Math.max(0, nextLevelXp - currentLevelXp);
  const earnedInLevel = Math.max(0, xp - currentLevelXp);
  const progressPercent =
    range > 0 ? Math.min(100, (earnedInLevel / range) * 100) : 0;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        className="flex items-center space-x-2 p-1.5 rounded-lg hover:bg-indigo-500/10 transition-colors duration-150 group border border-transparent hover:border-indigo-400/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
      >
        {/* Avatar / Level Indicator */}
        <div className="relative">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 on-fill flex items-center justify-center text-white text-xs font-bold ring-2 ring-white/10 group-hover:ring-indigo-300/50 transition-[box-shadow]">
            {initials}
          </div>
          <div className="absolute -bottom-1 -right-1 bg-[#0a0a1a] border border-quantum-blue-light rounded-full w-4 h-4 flex items-center justify-center">
            <span className="text-[9px] font-bold text-quantum-blue-light">
              {level}
            </span>
          </div>
        </div>

        {/* Name & Badge (Hidden on mobile) */}
        <div className="hidden lg:flex flex-col items-start">
          <span className="text-xs font-semibold text-black dark:text-gray-300 group-hover:text-black dark:group-hover:text-white transition-colors">
            {user.username}
          </span>
          <span className="text-[10px] text-quantum-blue-light flex items-center gap-1">
            <Award className="w-3 h-3" />
            {badge}
          </span>
        </div>

        <ChevronDown
          className={`w-4 h-4 text-black dark:text-gray-400 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="menu"
          className="qc-menu-in absolute right-0 top-full z-50 mt-2 w-72 origin-top-right overflow-hidden rounded-xl border border-editor-border bg-editor-sidebar shadow-[0_24px_56px_-16px_rgba(0,0,0,0.7)]"
        >
          {/* Header */}
          <div className="p-4 border-b border-editor-border">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-11 h-11 shrink-0 rounded-full bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 on-fill flex items-center justify-center text-white text-base font-bold">
                {initials}
              </div>
              <div className="flex-1 overflow-hidden">
                <h3 className="font-semibold text-white truncate">
                  {user.full_name}
                </h3>
                <p className="text-xs text-black dark:text-gray-400 truncate">
                  {isGuest ? "Guest workspace" : user.email}
                </p>
              </div>
            </div>

            {/* Gamification Progress */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-black dark:text-gray-300 font-medium">
                  Level {level}
                </span>
                <span className="text-quantum-blue-light">
                  {formatXP(Math.max(0, xp - currentLevelXp))} /{" "}
                  {formatXP(Math.max(0, nextLevelXp - currentLevelXp))} XP
                </span>
              </div>
              <div className="h-1.5 bg-black/40 rounded-full overflow-hidden">
                <div
                  className="qc-grow-x h-full rounded-full bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-400"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          </div>

          {/* Menu Items */}
          <div className="p-1.5 space-y-0.5">
            <Link
              href="/profile"
              role="menuitem"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-black dark:text-gray-300 hover:bg-indigo-500/10 hover:text-white transition-colors duration-100 group"
              onClick={() => setIsOpen(false)}
            >
              <User className="w-4 h-4 text-black dark:text-gray-400 group-hover:text-quantum-blue-light" />
              <span>Profile</span>
            </Link>

            <Link
              href="/achievements"
              role="menuitem"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-black dark:text-gray-300 hover:bg-indigo-500/10 hover:text-white transition-colors duration-100 group"
              onClick={() => setIsOpen(false)}
            >
              <Award className="w-4 h-4 text-black dark:text-gray-400 group-hover:text-yellow-600 dark:group-hover:text-yellow-400" />
              <span>Achievements</span>
            </Link>

            <div className="h-px bg-editor-border my-1 mx-2"></div>

            <button
              onClick={() => {
                onLogout();
                setIsOpen(false);
              }}
              role="menuitem"
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors duration-100 group"
            >
              <LogOut className="w-4 h-4" />
              <span>Log out</span>
            </button>
            {isGuest && (
              <p className="px-3 pb-1.5 pt-0.5 text-[11px] leading-relaxed text-gray-500">
                Logging out deletes this guest workspace and its files.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
