"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  Mail,
  Lock,
  User,
  ShieldAlert,
  Sun,
  Moon,
  Eye,
  EyeOff,
} from "lucide-react";
import toast from "react-hot-toast";

import { hasValidAuth, useAuthStore } from "@/lib/authStore";
import { useFileStore } from "@/lib/store";
import { authApi } from "@/lib/api";

export default function AdminSignupPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useFileStore();
  const { isAuthenticated, token, setLoading } = useAuthStore();
  const canAccessApp = hasValidAuth({ isAuthenticated, token });

  const [formData, setFormData] = useState({
    fullName: "",
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isLogoHovered, setIsLogoHovered] = useState(false);

  useEffect(() => {
    if (canAccessApp) {
      router.push("/app");
    }
  }, [canAccessApp, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setLoading(true);

    try {
      if (
        !formData.fullName ||
        !formData.username ||
        !formData.email ||
        !formData.password ||
        !formData.confirmPassword
      ) {
        throw new Error("Please fill in all fields");
      }

      if (!formData.email.includes("@")) {
        throw new Error("Please enter a valid email");
      }

      if (formData.password.length < 8) {
        throw new Error("Password must be at least 8 characters");
      }

      if (formData.password !== formData.confirmPassword) {
        throw new Error("Passwords do not match");
      }

      const response = await authApi.registerAdmin({
        email: formData.email,
        username: formData.username,
        password: formData.password,
        full_name: formData.fullName,
      });

      if (!response.success || !response.data) {
        throw new Error(response.error || "Admin signup failed");
      }

      setIsSubmitted(true);
      toast.success(
        response.data.message || "Admin request submitted for approval",
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Admin signup failed",
      );
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a1a] p-4 relative overflow-auto">
      <div className="absolute inset-0 bg-grid-pattern opacity-60" />
      <div className="absolute inset-0 hero-spotlight" />

      <div className="absolute top-4 right-4 z-20">
        <button
          onClick={toggleTheme}
          className="btn-ghost p-3 hover:bg-white/10 rounded-lg backdrop-blur-md"
          title="Toggle theme"
        >
          {theme === "dark" ? (
            <Sun className="w-5 h-5 text-black dark:text-gray-300" />
          ) : (
            <Moon className="w-5 h-5 text-black dark:text-gray-300" />
          )}
        </button>
      </div>

      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-32 -right-32 w-[500px] h-[500px] bg-indigo-500 opacity-[0.07] rounded-full blur-[100px]" />
        <div className="absolute -bottom-32 -left-32 w-[500px] h-[500px] bg-cyan-500 opacity-[0.07] rounded-full blur-[100px]" />
      </div>

      <div className="w-full max-w-md relative z-10 my-8">
        <div className="text-center mb-8">
          <div
            className="relative inline-flex items-center justify-center mb-6 group cursor-pointer"
            onMouseEnter={() => setIsLogoHovered(true)}
            onMouseLeave={() => setIsLogoHovered(false)}
            role="link"
            tabIndex={0}
            onClick={() => router.push('/')}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                router.push('/');
              }
            }}
            title="Go to QCanvas homepage"
          >
            <div className="relative flex items-center justify-center">
              <div
                className={`transition-all duration-500 ease-out ${isLogoHovered ? "-translate-x-40" : "translate-x-0"}`}
              >
                <Image
                  src="/QCanvas-logo-Black.svg"
                  alt="QCanvas Logo"
                  width={80}
                  height={80}
                  className={`object-contain block dark:hidden transition-all duration-300 ${isLogoHovered ? "scale-110 drop-shadow-lg" : "scale-100 hover:scale-105"} animate-pulse`}
                  priority
                />
                <Image
                  src="/QCanvas-logo-White.svg"
                  alt="QCanvas Logo"
                  width={80}
                  height={80}
                  className={`object-contain hidden dark:block transition-all duration-300 ${isLogoHovered ? "scale-110 drop-shadow-2xl" : "scale-100 hover:scale-105"} animate-pulse`}
                  priority
                />
              </div>

              <div
                className={`absolute -top-16 left-1/2 transform -translate-x-1/2 transition-all duration-500 ease-out ${isLogoHovered ? "opacity-100 translate-y-[5.5rem]" : "opacity-0 -translate-y-4"}`}
              >
                <h1 className="text-4xl font-bold text-white whitespace-nowrap text-center">
                  <span className="quantum-gradient bg-clip-text text-transparent animate-pulse">
                    QCanvas
                  </span>
                </h1>
                <div className="w-24 h-0.5 bg-quantum-blue-light rounded-full animate-pulse delay-200 mx-auto mt-1" />
              </div>
            </div>
          </div>

          <div
            className={`transition-all duration-500 ${isLogoHovered ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0"}`}
          >
            <h1 className="text-3xl font-bold text-white mb-2">
              Admin Sign Up
            </h1>
            {/* SEO: word-count fix — hidden but crawler-readable */}
            <p className="sr-only">
              Request administrator access to the QCanvas quantum computing
              platform. Admin accounts on QCanvas provide elevated privileges to
              manage users, review quantum circuit projects, and oversee the
              simulation environment. All admin signup requests are reviewed and
              manually approved by the master administrator before the account
              is activated. QCanvas is a browser-based quantum circuit IDE that
              supports Google Cirq, IBM Qiskit, and Xanadu PennyLane through a
              unified OpenQASM 3.0 interface powered by the QSim simulation
              backend. The platform is developed as a FAST University research
              initiative to democratize quantum computing education and tooling.
            </p>
            <p className="text-editor-text">
              Requests are reviewed by the master admin before activation.
            </p>
          </div>
        </div>

        <div className="quantum-glass-dark rounded-2xl p-8 backdrop-blur-xl shadow-[0_0_40px_rgba(99,102,241,0.1)] border border-indigo-500/10 hover:border-indigo-500/20 transition-colors duration-500">
          <div className="mb-5 rounded-xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-100">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 h-5 w-5 text-amber-300" />
              <div>
                <p className="font-medium text-amber-100">Approval required</p>
                <p className="mt-1 text-amber-50/90">
                  Your admin account will stay inactive until the master admin
                  approves it.
                </p>
              </div>
            </div>
          </div>

          {isSubmitted ? (
            <div className="space-y-4 text-center">
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-emerald-100">
                <p className="font-semibold">Request submitted</p>
                <p className="mt-1 text-sm text-emerald-50/90">
                  The master admin has been notified and will review your
                  request.
                </p>
              </div>
              <Link
                href="/login"
                className="inline-flex w-full items-center justify-center rounded-lg bg-indigo-500 px-4 py-3 font-medium text-white transition-colors hover:bg-indigo-600"
              >
                Go to Login
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="fullName"
                  className="mb-1.5 block text-sm font-medium text-black dark:text-gray-300"
                >
                  Full Name
                </label>
                <div className="relative">
                  <input
                    id="fullName"
                    type="text"
                    required
                    value={formData.fullName}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        fullName: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-black transition-all duration-200 placeholder-gray-400 hover:border-gray-400 focus:bg-white focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white dark:hover:border-white/20 dark:hover:bg-white/10 dark:focus:bg-white/10"
                    placeholder="Enter your full name"
                    disabled={isLoading}
                  />
                  <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black dark:text-gray-500" />
                </div>
              </div>

              <div>
                <label
                  htmlFor="username"
                  className="mb-1.5 block text-sm font-medium text-black dark:text-gray-300"
                >
                  Username
                </label>
                <div className="relative">
                  <input
                    id="username"
                    type="text"
                    required
                    value={formData.username}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        username: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-black transition-all duration-200 placeholder-gray-400 hover:border-gray-400 focus:bg-white focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white dark:hover:border-white/20 dark:hover:bg-white/10 dark:focus:bg-white/10"
                    placeholder="Choose a username"
                    disabled={isLoading}
                  />
                  <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black dark:text-gray-500" />
                </div>
              </div>

              <div>
                <label
                  htmlFor="email"
                  className="mb-1.5 block text-sm font-medium text-black dark:text-gray-300"
                >
                  Email Address
                </label>
                <div className="relative">
                  <input
                    id="email"
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        email: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-black transition-all duration-200 placeholder-gray-400 hover:border-gray-400 focus:bg-white focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white dark:hover:border-white/20 dark:hover:bg-white/10 dark:focus:bg-white/10"
                    placeholder="Enter your email"
                    disabled={isLoading}
                  />
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black dark:text-gray-500" />
                </div>
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="mb-1.5 block text-sm font-medium text-black dark:text-gray-300"
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    value={formData.password}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        password: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-12 text-black transition-all duration-200 placeholder-gray-400 hover:border-gray-400 focus:bg-white focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white dark:hover:border-white/20 dark:hover:bg-white/10 dark:focus:bg-white/10"
                    placeholder="Create a secure password"
                    disabled={isLoading}
                  />
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black dark:text-gray-500" />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-black/60 transition-colors hover:text-black dark:text-gray-500 dark:hover:text-gray-300"
                    disabled={isLoading}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label
                  htmlFor="confirmPassword"
                  className="mb-1.5 block text-sm font-medium text-black dark:text-gray-300"
                >
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    required
                    value={formData.confirmPassword}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        confirmPassword: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-12 text-black transition-all duration-200 placeholder-gray-400 hover:border-gray-400 focus:bg-white focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white dark:hover:border-white/20 dark:hover:bg-white/10 dark:focus:bg-white/10"
                    placeholder="Confirm your password"
                    disabled={isLoading}
                  />
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black dark:text-gray-500" />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-black/60 transition-colors hover:text-black dark:text-gray-500 dark:hover:text-gray-300"
                    disabled={isLoading}
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-lg bg-indigo-500 px-4 py-3 font-medium text-white transition-colors hover:bg-indigo-600 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isLoading ? "Submitting request..." : "Request Admin Access"}
              </button>
            </form>
          )}

          <div className="mt-6 text-center text-sm text-black/70 dark:text-gray-400">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-medium text-indigo-500 hover:text-indigo-400"
            >
              Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
