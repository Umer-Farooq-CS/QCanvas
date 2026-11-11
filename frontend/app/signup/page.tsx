"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Book, Play, Moon, Sun, CodeSquareIcon } from "@/components/Icons";
import { Eye, EyeOff, Github, User, Mail, Lock } from "lucide-react";
import toast from "react-hot-toast";
import { useFileStore } from "@/lib/store";
import { hasValidAuth, useAuthStore } from "@/lib/authStore";
import { authApi } from "@/lib/api";
import Image from "next/image";
import Link from "next/link";

export default function SignupPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useFileStore();
  const { isAuthenticated, token, setAuth, setLoading } = useAuthStore();
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
  const [isLogoHovered, setIsLogoHovered] = useState(false);

  // Check if already authenticated
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
      // Validation
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

      // Must match the backend's register minimum (auth.py).
      if (formData.password.length < 8) {
        throw new Error("Password must be at least 8 characters");
      }

      if (formData.password !== formData.confirmPassword) {
        throw new Error("Passwords do not match");
      }

      // Call backend register API
      const response = await authApi.register({
        email: formData.email,
        username: formData.username,
        password: formData.password,
        full_name: formData.fullName,
      });

      if (!response.success || !response.data) {
        throw new Error(response.error || "Registration failed");
      }

      const registerResult = response.data;

      if (registerResult.verification_required) {
        toast.success(
          registerResult.message || "Verification code sent to your email",
        );
        router.push(
          `/verify-email?email=${encodeURIComponent(registerResult.user.email)}`,
        );
        return;
      }

      if (!registerResult.access_token) {
        throw new Error("Registration completed but no access token returned");
      }

      setAuth(registerResult.user, registerResult.access_token);
      toast.success(`Welcome to QCanvas, ${registerResult.user.full_name}!`);
      router.push("/app");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Registration failed",
      );
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

      router.push("/app");
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

      <div className="w-full max-w-md relative z-10 my-8">
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
                  width={80}
                  height={80}
                  className={`object-contain block dark:hidden transition-all duration-300 ${isLogoHovered ? "scale-110 drop-shadow-lg" : "scale-100 hover:scale-105"} animate-pulse`}
                  priority
                />

                {/* Dark mode logo (white) */}
                <Image
                  src="/QCanvas-logo-White.svg"
                  alt="QCanvas Logo"
                  width={80}
                  height={80}
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
            <h1 className="text-3xl font-bold text-white mb-2">
              Create Account
            </h1>
            {/* SEO: word-count fix — hidden but crawler-readable */}
            <p className="sr-only">
              Create a free QCanvas account to start building quantum circuits
              in your browser. QCanvas is a quantum computing platform that
              unifies Google Cirq, IBM Qiskit, and Xanadu PennyLane into a
              single integrated development environment powered by OpenQASM 3.0.
              After registering, you can write quantum programs, simulate
              measurement results with the QSim backend, explore Bell state
              preparation, quantum teleportation, Grover&apos;s search, and
              quantum machine learning examples. Your account stores projects
              server-side. Prefer not to register? Start a private guest session for
              instant access to the quantum simulator without any sign-up.
            </p>
            <p className="text-editor-text">
              Join the Quantum Unified Simulator
            </p>
          </div>
        </div>

        {/* Signup Form */}
        <div className="quantum-glass-dark rounded-2xl p-8 backdrop-blur-xl shadow-[0_0_40px_rgba(99,102,241,0.1)] border border-indigo-500/10 hover:border-indigo-500/20 transition-colors duration-500">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Full Name Field */}
            <div>
              <label
                htmlFor="fullName"
                className="block text-sm font-medium text-black dark:text-gray-300 mb-1.5"
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
                  className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-lg focus-quantum text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 transition-all duration-200 hover:border-gray-400 dark:hover:border-white/20 hover:bg-white dark:hover:bg-white/10 focus:bg-white dark:focus:bg-white/10"
                  placeholder="Enter your full name"
                  disabled={isLoading}
                />
                <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-black dark:text-gray-500" />
              </div>
            </div>

            {/* Username Field */}
            <div>
              <label
                htmlFor="username"
                className="block text-sm font-medium text-black dark:text-gray-300 mb-1.5"
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
                  className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-lg focus-quantum text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 transition-all duration-200 hover:border-gray-400 dark:hover:border-white/20 hover:bg-white dark:hover:bg-white/10 focus:bg-white dark:focus:bg-white/10"
                  placeholder="Enter username"
                  disabled={isLoading}
                />
                <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-black dark:text-gray-500" />
              </div>
            </div>

            {/* Email Field */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-black dark:text-gray-300 mb-1.5"
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
                    setFormData((prev) => ({ ...prev, email: e.target.value }))
                  }
                  className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-lg focus-quantum text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 transition-all duration-200 hover:border-gray-400 dark:hover:border-white/20 hover:bg-white dark:hover:bg-white/10 focus:bg-white dark:focus:bg-white/10"
                  placeholder="Enter your email address"
                  disabled={isLoading}
                />
                <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-black dark:text-gray-500" />
              </div>
            </div>

            {/* Password Field */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-black dark:text-gray-300 mb-1.5"
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
                  className="w-full pl-10 pr-12 py-2.5 bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-lg focus-quantum text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 transition-all duration-200 hover:border-gray-400 dark:hover:border-white/20 hover:bg-white dark:hover:bg-white/10 focus:bg-white dark:focus:bg-white/10"
                  placeholder="Create a password"
                  disabled={isLoading}
                />
                <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-black dark:text-gray-500" />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-black dark:text-gray-400 hover:text-white transition-colors"
                  disabled={isLoading}
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Confirm Password Field */}
            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-medium text-black dark:text-gray-300 mb-1.5"
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
                  className="w-full pl-10 pr-12 py-2.5 bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-lg focus-quantum text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 transition-all duration-200 hover:border-gray-400 dark:hover:border-white/20 hover:bg-white dark:hover:bg-white/10 focus:bg-white dark:focus:bg-white/10"
                  placeholder="Confirm your password"
                  disabled={isLoading}
                />
                <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-black dark:text-gray-500" />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-black dark:text-gray-400 hover:text-white transition-colors"
                  disabled={isLoading}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn-quantum disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center py-3 text-lg font-semibold mt-2"
            >
              {isLoading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full spinner mr-2"></div>
                  Creating Account...
                </>
              ) : (
                "Sign Up"
              )}
            </button>
          </form>

          {/* Login Link */}
          <div className="mt-6 pt-6 border-t border-white/10 text-center">
            <p className="text-sm text-black dark:text-gray-400">
              Already have an account?{" "}
              <Link
                href="/login"
                className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
              >
                Sign In
              </Link>
            </p>
            <p className="text-sm text-black dark:text-gray-400 mt-2">
              <Link
                href="/admin/signup"
                className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                Apply for admin access
              </Link>
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
        </div>
      </div>
    </div>
  );
}
