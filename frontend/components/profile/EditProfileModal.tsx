"use client";

import { useState, useEffect, useRef } from "react";
import { FileText, Save, Loader2, AlertCircle } from "@/components/Icons";
import { X, User, AtSign, Camera, Sparkles, CheckCircle2 } from "lucide-react";
import { useAuthStore } from "@/lib/authStore";
import { authApi } from "@/lib/api";
import toast from "react-hot-toast";

interface EditProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const MAX_BIO_LENGTH = 200;

export default function EditProfileModal({
  isOpen,
  onClose,
}: EditProfileModalProps) {
  const { user, token, updateUser } = useAuthStore();

  const [fullName, setFullName] = useState(user?.full_name || "");
  const [username, setUsername] = useState(user?.username || "");
  const [bio, setBio] = useState(user?.bio || "");
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<{
    fullName?: string;
    username?: string;
    bio?: string;
  }>({});
  const [success, setSuccess] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  // Sync form when user changes (e.g. on open)
  useEffect(() => {
    if (isOpen) {
      setFullName(user?.full_name || "");
      setUsername(user?.username || "");
      setBio(user?.bio || "");
      setErrors({});
      setSuccess(false);
    }
  }, [isOpen, user]);

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  // Close on backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      onClose();
    }
  };

  const validate = () => {
    const newErrors: typeof errors = {};
    if (!fullName.trim()) newErrors.fullName = "Full name is required.";
    else if (fullName.trim().length < 2)
      newErrors.fullName = "Full name must be at least 2 characters.";
    if (!username.trim()) newErrors.username = "Username is required.";
    else if (!/^[a-zA-Z0-9_.-]{3,50}$/.test(username.trim()))
      newErrors.username = "3–50 chars: letters, numbers, _, . or - only.";
    if (bio.length > MAX_BIO_LENGTH)
      newErrors.bio = `Max ${MAX_BIO_LENGTH} characters.`;
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate() || !token) return;
    setSaving(true);
    setErrors({});
    try {
      const response = await authApi.updateProfile(
        {
          full_name: fullName.trim(),
          username: username.trim(),
          bio: bio.trim(),
        },
        token,
      );
      if (response.success && response.data) {
        // Update the auth store
        updateUser({
          full_name: response.data.full_name,
          username: response.data.username,
          bio: bio.trim(),
        });
        setSuccess(true);
        toast.success("Profile updated");
        setTimeout(() => {
          setSuccess(false);
          onClose();
        }, 1200);
      } else {
        const msg = response.error || "Failed to update profile.";
        if (msg.toLowerCase().includes("username")) {
          setErrors({ username: msg });
        } else {
          toast.error(msg);
        }
      }
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const initials = fullName
    ? fullName
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "QU";

  const hasChanges =
    fullName !== (user?.full_name || "") ||
    username !== (user?.username || "") ||
    bio !== (user?.bio || "");

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)" }}
      onClick={handleBackdropClick}
    >
      {/* Modal Card */}
      <div
        ref={modalRef}
        className="relative w-full max-w-lg bg-qc-surface border border-qc-line rounded-2xl shadow-qc overflow-hidden animate-modal-in"
        style={{
          animation: "modalIn 0.22s cubic-bezier(.22,1,.36,1) both",
        }}
      >

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-qc-accent/15 text-qc-accent flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-qc-fg">Edit Profile</h2>
              <p className="text-[11px] text-qc-subtle">
                Update your public information
              </p>
            </div>
          </div>
          <button
            id="edit-profile-close-btn"
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-qc-muted hover:text-qc-fg hover:bg-qc-surface-3 transition-all"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Avatar Section */}
        <div className="px-6 pb-5">
          <div className="flex items-center gap-4 p-4 rounded-xl bg-qc-surface-2 border border-qc-line">
            <div className="relative shrink-0">
              <div className="w-16 h-16 rounded-full bg-qc-surface-3 flex items-center justify-center text-2xl font-bold text-qc-fg">
                {initials || "?"}
              </div>
              <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-qc-surface border border-qc-line flex items-center justify-center">
                <Camera className="w-3 h-3 text-qc-muted" />
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-qc-fg">
                {fullName || "Your Name"}
              </p>
              <p className="text-xs text-qc-subtle">
                @{username || "username"}
              </p>
              <p className="text-[10px] text-qc-subtle mt-1">
                Avatar is auto-generated from your initials
              </p>
            </div>
          </div>
        </div>

        {/* Form */}
        <div className="px-6 pb-2 space-y-4">
          {/* Full Name */}
          <div>
            <label className="block text-xs font-semibold text-qc-muted uppercase tracking-wider mb-1.5">
              Full Name
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-qc-subtle pointer-events-none" />
              <input
                id="edit-profile-fullname"
                type="text"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  if (errors.fullName)
                    setErrors((p) => ({ ...p, fullName: undefined }));
                }}
                placeholder="e.g. Umer Farooq"
                className={`w-full bg-white/[0.05] border ${
                  errors.fullName
                    ? "border-red-500/60 focus:border-red-500"
                    : "border-qc-line focus:border-quantum-blue/60"
                } rounded-lg pl-9 pr-4 py-2.5 text-sm text-qc-fg placeholder:text-qc-subtle outline-none transition-colors`}
              />
            </div>
            {errors.fullName && (
              <p className="flex items-center gap-1 text-[11px] text-qc-danger mt-1">
                <AlertCircle className="w-3 h-3 shrink-0" /> {errors.fullName}
              </p>
            )}
          </div>

          {/* Username */}
          <div>
            <label className="block text-xs font-semibold text-qc-muted uppercase tracking-wider mb-1.5">
              Username
            </label>
            <div className="relative">
              <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-qc-subtle pointer-events-none" />
              <input
                id="edit-profile-username"
                type="text"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value.toLowerCase().replace(/\s/g, ""));
                  if (errors.username)
                    setErrors((p) => ({ ...p, username: undefined }));
                }}
                placeholder="e.g. umer_farooq"
                className={`w-full bg-white/[0.05] border ${
                  errors.username
                    ? "border-red-500/60 focus:border-red-500"
                    : "border-qc-line focus:border-quantum-blue/60"
                } rounded-lg pl-9 pr-4 py-2.5 text-sm text-qc-fg placeholder:text-qc-subtle outline-none transition-colors font-mono`}
              />
            </div>
            {errors.username && (
              <p className="flex items-center gap-1 text-[11px] text-qc-danger mt-1">
                <AlertCircle className="w-3 h-3 shrink-0" /> {errors.username}
              </p>
            )}
          </div>

          {/* Bio */}
          <div>
            <label className="block text-xs font-semibold text-qc-muted uppercase tracking-wider mb-1.5">
              Bio{" "}
              <span className="text-qc-subtle normal-case font-normal">
                (optional)
              </span>
            </label>
            <div className="relative">
              <FileText className="absolute left-3 top-3 w-4 h-4 text-qc-subtle pointer-events-none" />
              <textarea
                id="edit-profile-bio"
                value={bio}
                onChange={(e) => {
                  setBio(e.target.value);
                  if (errors.bio) setErrors((p) => ({ ...p, bio: undefined }));
                }}
                rows={3}
                placeholder="Tell the quantum realm about yourself…"
                className={`w-full bg-white/[0.05] border ${
                  errors.bio
                    ? "border-red-500/60 focus:border-red-500"
                    : "border-qc-line focus:border-quantum-blue/60"
                } rounded-lg pl-9 pr-4 py-2.5 text-sm text-qc-fg placeholder:text-qc-subtle outline-none transition-colors resize-none`}
              />
              <span
                className={`absolute bottom-2 right-3 text-[10px] ${bio.length > MAX_BIO_LENGTH ? "text-qc-danger" : "text-qc-subtle"}`}
              >
                {bio.length}/{MAX_BIO_LENGTH}
              </span>
            </div>
            {errors.bio && (
              <p className="flex items-center gap-1 text-[11px] text-qc-danger mt-1">
                <AlertCircle className="w-3 h-3 shrink-0" /> {errors.bio}
              </p>
            )}
          </div>

          {/* Email (read-only) */}
          <div>
            <label className="block text-xs font-semibold text-qc-muted uppercase tracking-wider mb-1.5">
              Email{" "}
              <span className="text-qc-subtle normal-case font-normal">
                (cannot be changed)
              </span>
            </label>
            <div className="relative">
              <input
                type="email"
                value={user?.email || ""}
                disabled
                className="w-full bg-qc-surface-2 border border-qc-line rounded-lg px-4 py-2.5 text-sm text-qc-subtle outline-none cursor-not-allowed select-none"
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <span className="text-[10px] bg-qc-surface-2 text-qc-subtle px-1.5 py-0.5 rounded">
                  locked
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 mt-2 flex items-center justify-between border-t border-qc-line">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-qc-muted hover:text-qc-fg bg-qc-surface-2 hover:bg-qc-surface-3 border border-qc-line rounded-lg transition-all"
          >
            Cancel
          </button>

          <button
            id="edit-profile-save-btn"
            onClick={handleSave}
            disabled={saving || !hasChanges || success}
            className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-all
 ${
                              success
                                ? "bg-qc-success/15 border border-qc-success/40 text-qc-success"
                                : hasChanges
                                  ? "bg-qc-accent-solid text-qc-on-accent hover:opacity-90"
                                  : "bg-qc-surface-2 border border-qc-line text-qc-subtle cursor-not-allowed"
                            }`}
          >
            {success ? (
              <>
                <CheckCircle2 className="w-4 h-4" /> Saved
              </>
            ) : saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Saving…
              </>
            ) : (
              <>
                <Save className="w-4 h-4" /> Save Changes
              </>
            )}
          </button>
        </div>
      </div>

      <style>{`
                @keyframes modalIn {
                    from { opacity: 0; transform: scale(0.94) translateY(12px); }
                    to   { opacity: 1; transform: scale(1)    translateY(0px); }
                }
            `}</style>
    </div>
  );
}
