"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Book, Play, Moon, Sun, CodeSquareIcon } from "@/components/Icons";
import { Eye, EyeOff, Github } from "lucide-react";
import toast from "react-hot-toast";
import { useFileStore } from "@/lib/store";
import { hasValidAuth, useAuthStore } from "@/lib/authStore";
import { authApi } from "@/lib/api";
import Image from "next/image";

export default function LoginPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useFileStore();
  const { isAuthenticated, token, setAuth, setLoading } = useAuthStore();
  const canAccessApp = hasValidAuth({ isAuthenticated, token });

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLogoHovered, setIsLogoHovered] = useState(false);

  // Where to go after login: honour ?next= (same-origin paths only).
  const getNextPath = () => {
    if (typeof window === "undefined") return "/app";
    const next = new URLSearchParams(window.location.search).get("next");
    // Reject backslashes/control chars (browsers normalise "/\evil.com" to
    // "//evil.com") and anything that resolves to another origin.
    if (!next || !next.startsWith("/") || /[\\\u0000-\u001f]/.test(next)) {
      return "/app";
    }
    try {
      const url = new URL(next, window.location.origin);
      if (url.origin !== window.location.origin) return "/app";
      return url.pathname + url.search + url.hash;
    } catch {
      return "/app";
    }
  };

  // Check if already authenticated (expiry-aware, so a stale token can't
  // bounce the user between /login and /app).
  useEffect(() => {
    if (canAccessApp) {
      router.replace(getNextPath() as Parameters<typeof router.replace>[0]);
    }
  }, [canAccessApp, router]); // eslint-disable-line react-hooks/exhaustive-deps

  // Explain why the user landed here (e.g. session expired).
  useEffect(() => {
    try {
      const msg = sessionStorage.getItem("qcanvas-auth-message");
      if (msg) {
        sessionStorage.removeItem("qcanvas-auth-message");
        toast(msg, { icon: "🔒", id: "auth-message" });
      }
    } catch {}
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setLoading(true);

    try {
      // Basic validation
      if (!formData.email || !formData.password) {
        throw new Error("Please fill in all fields");
      }

      if (!formData.email.includes("@")) {
        throw new Error("Please enter a valid email");
      }

      if (formData.password.length < 6) {
        throw new Error("Password must be at least 6 characters");
      }

      // Call backend login API
      const response = await authApi.login(formData.email, formData.password);

      if (!response.success || !response.data) {
        if (response.error?.toLowerCase().includes("verification")) {
          router.push(
            `/verify-email?email=${encodeURIComponent(formData.email)}`,
          );
          throw new Error("Please verify your email before signing in");
        }
        throw new Error(response.error || "Login failed");
      }

      const { access_token, user } = response.data;

      // Store auth data
      setAuth(user, access_token);

      // Show success message with user's name
      toast.success(`Welcome back, ${user.full_name}!`);

      // Navigate to app
      router.push(getNextPath() as Parameters<typeof router.push>[0]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Login failed");
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setIsLoading(true);
    setLoading(true);

    try {
      // Each visitor gets a private, temporary guest workspace (previously
      // everyone shared one demo account and could overwrite each other's files).
      const response = await authApi.guestLogin();

      if (!response.success || !response.data) {
        throw new Error(response.error || "Could not start a demo session");
      }

      const { access_token, user } = response.data;
      setAuth(user, access_token);

      toast.success("You're in! This is your private guest workspace.");
      toast(
        "Guest files are deleted when you log out or after 3 days. Create an account to keep your work.",
        { icon: "ℹ️", duration: 7000 },
      );

      router.push(getNextPath() as Parameters<typeof router.push>[0]);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not start a demo session",
      );
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a1a] p-4 relative overflow-auto">
      {/* Grid dot background */}
      <div className="absolute inset-0 bg-grid-pattern opacity-60"></div>

      {/* Hero spotlight radial glow */}
      <div className="absolute inset-0 hero-spotlight"></div>

      {/* Theme Toggle Button */}
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

      {/* Subtle background orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-32 -right-32 w-[500px] h-[500px] bg-indigo-500 opacity-[0.07] rounded-full blur-[100px]"></div>
        <div className="absolute -bottom-32 -left-32 w-[500px] h-[500px] bg-violet-500 opacity-[0.07] rounded-full blur-[100px]"></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-cyan-500 opacity-[0.05] rounded-full blur-[80px]"></div>
      </div>

      <div className="w-full max-w-md relative z-10">
        {/* Logo and Header */}
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
            {/* Centered logo container */}
            <div className="relative flex items-center justify-center">
              {/* Animated container - logo moves left on hover */}
              <div
                className={`transition-all duration-500 ease-out ${isLogoHovered ? "-translate-x-40" : "translate-x-0"}`}
              >
                {/* Light mode logo (black) */}
                <Image
                  src="/QCanvas-logo-Black.svg"
                  alt="QCanvas Logo"
                  width={96}
                  height={96}
                  className={`object-contain block dark:hidden transition-all duration-300 ${isLogoHovered ? "scale-110 drop-shadow-lg" : "scale-100 hover:scale-105"} animate-pulse`}
                  priority
                />

                {/* Dark mode logo (white) */}
                <Image
                  src="/QCanvas-logo-White.svg"
                  alt="QCanvas Logo"
                  width={96}
                  height={96}
                  className={`object-contain hidden dark:block transition-all duration-300 ${isLogoHovered ? "scale-110 drop-shadow-2xl" : "scale-100 hover:scale-105"} animate-pulse`}
                  priority
                />
              </div>

              {/* Animated text that appears on hover - centered above logo */}
              <div
                className={`absolute -top-16 left-1/2 transform -translate-x-1/2 transition-all duration-500 ease-out ${isLogoHovered ? "opacity-100 translate-y-[5.5rem]" : "opacity-0 -translate-y-4"}`}
              >
                <h1 className="text-4xl font-bold text-white whitespace-nowrap text-center">
                  <span className="quantum-gradient bg-clip-text text-transparent animate-pulse">
                    QCanvas
                  </span>
                </h1>
                <div className="w-24 h-0.5 bg-quantum-blue-light rounded-full animate-pulse delay-200 mx-auto mt-1"></div>
              </div>
            </div>
          </div>

          <div
            className={`transition-all duration-500 ${isLogoHovered ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0"}`}
          >
            <h1 className="text-4xl font-bold text-white mb-3">
              Welcome to{" "}
              <span className="quantum-gradient bg-clip-text text-transparent">
                QCanvas
              </span>
            </h1>
            {/* SEO: low-word-count fix — hidden paragraph visible to crawlers */}
            <p className="sr-only">
              Sign in to your QCanvas account to access the quantum circuit
              integrated development environment. QCanvas is a browser-based
              quantum simulator that supports Google Cirq, IBM Qiskit, and
              Xanadu PennyLane frameworks. Write quantum programs, compile them
              to OpenQASM 3.0, and simulate with the QSim backend engine.
              Explore pre-built examples including Bell states, quantum
              teleportation, Grover&apos;s search, and Deutsch-Jozsa. The
              platform is secured with JWT token authentication. New users can
              create a free account or start a private guest session without signing up.
            </p>
            <p className="text-editor-text text-lg">
              Quantum Unified Simulator
            </p>
            <p className="text-black dark:text-gray-400 text-sm mt-2">
              Write in Qiskit, Cirq, or PennyLane • Compile to OpenQASM 3.0 •
              Simulate with QSim
            </p>
          </div>
        </div>

        {/* Login Form */}
        <div className="quantum-glass-dark rounded-2xl p-8 backdrop-blur-xl shadow-[0_0_40px_rgba(99,102,241,0.1)] border border-indigo-500/10 hover:border-indigo-500/20 transition-colors duration-500">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Email Field */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-black dark:text-gray-300 mb-2"
              >
                Email Address
              </label>
              <input
                id="email"
                type="email"
                required
                value={formData.email}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, email: e.target.value }))
                }
                className="w-full px-4 py-3 bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-lg focus-quantum text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 transition-all duration-200 hover:border-gray-400 dark:hover:border-white/20 hover:bg-white dark:hover:bg-white/10 focus:bg-white dark:focus:bg-white/10"
                placeholder="Enter your email"
                disabled={isLoading}
              />
            </div>

            {/* Password Field */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-black dark:text-gray-300 mb-2"
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
                  className="w-full px-4 py-3 bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-lg focus-quantum text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 pr-12 transition-all duration-200 hover:border-gray-400 dark:hover:border-white/20 hover:bg-white dark:hover:bg-white/10 focus:bg-white dark:focus:bg-white/10"
                  placeholder="Enter your password"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-black dark:text-gray-400 hover:text-white transition-colors"
                  disabled={isLoading}
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn-quantum disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center py-3 text-lg font-semibold"
            >
              {isLoading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full spinner mr-2"></div>
                  Signing In...
                </>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          {/* Sign Up Link */}
          <div className="mt-6 pt-6 border-t border-white/10 text-center">
            <p className="text-sm text-black dark:text-gray-400">
              Don&apos;t have an account?{" "}
              <a
                href="/signup"
                className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
              >
                Sign Up
              </a>
            </p>
            <p className="text-sm text-black dark:text-gray-400 mt-2">
              <a
                href="/admin/signup"
                className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                Request admin access
              </a>
            </p>
            <p className="text-sm text-black dark:text-gray-400 mt-2">
              <a
                href="/forgot-password"
                className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
              >
                Forgot password?
              </a>
            </p>
          </div>

          {/* Demo Login */}
          <div className="mt-6 pt-6 border-t border-white/10">
            <p className="text-sm text-black dark:text-gray-400 text-center mb-3">
              Want to try without signing up?
            </p>
            <button
              onClick={handleDemoLogin}
              disabled={isLoading}
              className="w-full btn-ghost flex items-center justify-center py-3 bg-white/5 hover:bg-white/10 text-white border-white/10"
            >
              <Play className="w-4 h-4 mr-2" />
              Use Demo Account
            </button>
          </div>

          {/* Quick Links */}
          <div className="mt-6 pt-6 border-t border-white/10">
            <div className="flex justify-center space-x-4">
              <a
                href="/about"
                className="flex items-center text-sm text-black dark:text-gray-400 hover:text-indigo-400 transition-colors"
              >
                <Book className="w-4 h-4 mr-1" />
                About
              </a>
              <a
                href="/examples"
                className="flex items-center text-sm text-black dark:text-gray-400 hover:text-violet-400 transition-colors"
              >
                <CodeSquareIcon className="w-4 h-4 mr-1" />
                Examples
              </a>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center text-sm text-black dark:text-gray-400 hover:text-cyan-400 transition-colors"
              >
                <Github className="w-4 h-4 mr-1" />
                GitHub
              </a>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-6 text-center">
            <p className="text-xs text-black dark:text-gray-500">
              No account? &ldquo;Try demo&rdquo; gives you a private guest
              workspace instantly.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
