"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import Navbar from "@/components/Navbar";
import SiteFooter from "@/components/site/SiteFooter";
import {
  Moon,
  Sun,
  Book,
  Code,
  Cpu,
  BarChart3,
  Zap,
  Settings,
  Play,
  Star,
  Atom,
  Lightbulb,
  Database,
  Layers,
  Terminal,
  FileText,
  Cloud,
  Server,
  Wrench,
  Target,
  Rocket,
  Clock,
  TrendingUp,
  GitBranch,
  FrameworkConversionIcon,
  FlagIcon,
  SparklesIcon,
  ApiIcon,
  CirqIcon,
  PennyLaneIcon,
  QiskitIcon,
} from "@/components/Icons";
import {
  Menu,
  X,
  ChevronRight,
  ArrowRight,
  CheckCircle,
  Shield,
  Monitor,
  Sparkles,
  Info,
} from "lucide-react";
import { config } from "@/lib/config";
import { hasValidAuth, useAuthStore } from "@/lib/authStore";

interface DocSection {
  id: string;
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  badge?: string;
  content: React.ReactNode;
  category?: string;
}

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("overview");
  const { isAuthenticated, token } = useAuthStore();
  const canAccessApp = hasValidAuth({ isAuthenticated, token });
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {

    // Intersection Observer for scroll spy
    const sectionIds = [
      "overview",
      "getting-started",
      "features",
      "architecture",
      "api",
      "hybrid-execution",
    ];

    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.id;
            setActiveSection(id);

            // Auto-scroll sub-nav horizontally when section changes
            const navItem = document.getElementById(`nav-${id}`);
            if (navItem) {
              navItem.scrollIntoView({
                behavior: "smooth",
                inline: "center",
                block: "nearest",
              });
            }
          }
        });
      },
      {
        // Detect when the section is in the top portion of the viewport
        rootMargin: "-10% 0% -70% 0%",
        threshold: 0,
      },
    );

    sectionIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observerRef.current?.observe(el);
    });

    return () => {
      observerRef.current?.disconnect();
    };
  }, []);

  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    if (element) {
      // Use scrollIntoView which respects scroll-margin-top
      element.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveSection(sectionId);

      // Synchronize horizontal sub-nav scroll
      const navItem = document.getElementById(`nav-${sectionId}`);
      if (navItem) {
        navItem.scrollIntoView({
          behavior: "smooth",
          inline: "center",
          block: "nearest",
        });
      }
    }
  };

  const sections: DocSection[] = [
    {
      id: "overview",
      title: "Overview",
      subtitle: "Introduction to QCanvas",
      icon: <Info className="w-5 h-5" />,
      badge: "Essential",
      category: "Getting Started",
      content: (
        <div className="space-y-8">
          <div className="mb-10 max-w-3xl">
            <h2 className="font-display text-display-2 font-semibold text-qc-fg">
              Overview
            </h2>
            <p className="text-lg text-qc-muted mt-3 leading-relaxed max-w-[65ch]">
              {config.project.description}
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6 text-center">
              <div className="w-12 h-12 bg-qc-surface-2 border border-qc-line rounded-lg flex items-center justify-center mx-auto mb-4">
                <FrameworkConversionIcon className="w-6 h-6 text-qc-accent" />
              </div>
              <h3 className="text-lg font-semibold text-qc-fg mb-2">
                Framework Conversion
              </h3>
              <p className="text-qc-muted text-sm">
                Convert between Qiskit, Cirq, and PennyLane seamlessly
              </p>
            </div>
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6 text-center">
              <div className="w-12 h-12 bg-qc-surface-2 border border-qc-line rounded-lg flex items-center justify-center mx-auto mb-4">
                <Play className="w-6 h-6 text-qc-accent" />
              </div>
              <h3 className="text-lg font-semibold text-qc-fg mb-2">
                Real-time Simulation
              </h3>
              <p className="text-qc-muted text-sm">
                Execute quantum circuits with multiple backends
              </p>
            </div>
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6 text-center">
              <div className="w-12 h-12 bg-qc-surface-2 border border-qc-line rounded-lg flex items-center justify-center mx-auto mb-4">
                <BarChart3 className="w-6 h-6 text-qc-accent" />
              </div>
              <h3 className="text-lg font-semibold text-qc-fg mb-2">
                Interactive Visualization
              </h3>
              <p className="text-qc-muted text-sm">
                Visualize quantum states and measurement results
              </p>
            </div>
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6 text-center">
              <div className="w-12 h-12 bg-qc-surface-2 border border-qc-line rounded-lg flex items-center justify-center mx-auto mb-4">
                <Book className="w-6 h-6 text-qc-accent" />
              </div>
              <h3 className="text-lg font-semibold text-qc-fg mb-2">
                Educational Platform
              </h3>
              <p className="text-qc-muted text-sm">
                Learn quantum computing through guided examples
              </p>
            </div>
          </div>

          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6 flex items-center">
              <Rocket className="w-6 h-6 mr-3 text-qc-accent" />
              Project Mission
            </h3>
            <p className="text-qc-muted text-lg leading-relaxed mb-6">
              QCanvas addresses the critical standardization gap in
              multi-framework quantum programming by providing a universal
              intermediary that translates quantum circuits into the
              standardized OpenQASM 3.0 intermediate representation. This
              enables seamless integration, comparison, and execution of quantum
              circuits across different hardware platforms and software
              ecosystems.
            </p>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="text-center">
                <div className="text-2xl font-bold mb-2 text-qc-fg">
                  Unification
                </div>
                <p className="text-qc-muted text-sm">
                  Bridge the gap between quantum frameworks
                </p>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold mb-2 text-qc-fg">
                  Accessibility
                </div>
                <p className="text-qc-muted text-sm">
                  Make quantum computing approachable for all
                </p>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold mb-2 text-qc-fg">
                  Innovation
                </div>
                <p className="text-qc-muted text-sm">
                  Accelerate quantum software development
                </p>
              </div>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "getting-started",
      title: "Getting Started",
      subtitle: "Quick start guide",
      icon: <FlagIcon className="w-5 h-5" />,
      badge: "Beginner",
      category: "Getting Started",
      content: (
        <div className="space-y-8">
          <div className="mb-10 max-w-3xl">
            <h2 className="font-display text-display-2 font-semibold text-qc-fg">
              Getting Started
            </h2>
            <p className="text-lg text-qc-muted mt-3">
              Get up and running with QCanvas in minutes. Learn the basics and
              start building quantum circuits.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <h3 className="text-xl font-semibold text-qc-fg mb-4 flex items-center">
                <Target className="w-5 h-5 mr-2 text-qc-accent" />
                Quick Start Guide
              </h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 bg-qc-accent/10 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-sm font-bold text-qc-accent">
                      1
                    </span>
                  </div>
                  <div>
                    <h4 className="text-qc-fg font-medium mb-1">
                      Access QCanvas
                    </h4>
                    <p className="text-qc-muted text-sm">
                      Navigate to the web application and create your account
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 bg-qc-surface-3 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-sm font-bold text-qc-accent">2</span>
                  </div>
                  <div>
                    <h4 className="text-qc-fg font-medium mb-1">
                      Choose Framework
                    </h4>
                    <p className="text-qc-muted text-sm">
                      Select your preferred quantum framework (Qiskit, Cirq,
                      PennyLane)
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 bg-qc-surface-3 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-sm font-bold text-qc-accent">3</span>
                  </div>
                  <div>
                    <h4 className="text-qc-fg font-medium mb-1">
                      Create Circuit
                    </h4>
                    <p className="text-qc-muted text-sm">
                      Write or paste your quantum circuit code
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 bg-qc-surface-3 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-sm font-bold text-qc-success">4</span>
                  </div>
                  <div>
                    <h4 className="text-qc-fg font-medium mb-1">
                      Convert & Simulate
                    </h4>
                    <p className="text-qc-muted text-sm">
                      Convert between frameworks and run simulations
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <h3 className="text-xl font-semibold text-qc-fg mb-4 flex items-center">
                <Lightbulb className="w-5 h-5 mr-2 text-qc-accent" />
                First Example
              </h3>
              <div className="bg-qc-surface-2 rounded-lg p-4 border border-qc-line mb-4">
                <h4 className="text-qc-fg font-medium mb-3">
                  Bell State Circuit
                </h4>
                <pre className="qc-code qc-code--plain overflow-x-auto text-xs">
                  {`# Qiskit Bell State
from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)
qc.h(0)      # Hadamard on qubit 0
qc.cx(0, 1)  # CNOT gate
qc.measure_all()

print(qc)`}
                </pre>
              </div>
              <p className="text-qc-muted text-sm">
                This creates a quantum entanglement between two qubits,
                producing the famous Bell state |Φ⁺⟩ = (|00⟩ + |11⟩)/√2
              </p>
            </div>
          </div>

          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6">
              Supported Frameworks
            </h3>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="text-center group transition-transform duration-300">
                <div className="w-16 h-16 bg-qc-surface-3 rounded-xl flex items-center justify-center mx-auto mb-4 group-hover:bg-qc-surface-3 transition-colors duration-300">
                  <QiskitIcon className="w-8 h-8 text-qc-accent" />
                </div>
                <h4 className="text-xl font-semibold text-qc-fg mb-2">
                  Qiskit
                </h4>
                <p className="text-qc-muted text-sm mb-3">
                  IBM&apos;s comprehensive quantum computing framework
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  <span className="px-2 py-1 bg-qc-surface-3 text-qc-accent text-xs rounded-full">
                    Circuit Design
                  </span>
                  <span className="px-2 py-1 bg-qc-surface-3 text-qc-accent text-xs rounded-full">
                    IBM Quantum
                  </span>
                </div>
              </div>
              <div className="text-center group transition-transform duration-300">
                <div className="w-16 h-16 bg-qc-surface-3 rounded-xl flex items-center justify-center mx-auto mb-4 group-hover:bg-qc-surface-3 transition-colors duration-300">
                  <CirqIcon className="w-8 h-8 text-qc-accent" />
                </div>
                <h4 className="text-xl font-semibold text-qc-fg mb-2">Cirq</h4>
                <p className="text-qc-muted text-sm mb-3">
                  Google&apos;s framework for near-term quantum devices
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  <span className="px-2 py-1 bg-qc-surface-3 text-qc-accent text-xs rounded-full">
                    Noise Modeling
                  </span>
                  <span className="px-2 py-1 bg-qc-surface-3 text-qc-accent text-xs rounded-full">
                    Google AI
                  </span>
                </div>
              </div>
              <div className="text-center group transition-transform duration-300">
                <div className="w-16 h-16 bg-qc-surface-3 rounded-xl flex items-center justify-center mx-auto mb-4 group-hover:bg-qc-surface-3 transition-colors duration-300">
                  <PennyLaneIcon className="w-8 h-8 text-qc-success" />
                </div>
                <h4 className="text-xl font-semibold text-qc-fg mb-2">
                  PennyLane
                </h4>
                <p className="text-qc-muted text-sm mb-3">
                  Xanadu&apos;s quantum machine learning framework
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  <span className="px-2 py-1 bg-qc-surface-3 text-qc-success text-xs rounded-full">
                    ML Integration
                  </span>
                  <span className="px-2 py-1 bg-qc-surface-3 text-qc-success text-xs rounded-full">
                    Variational
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <h3 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                <TrendingUp className="w-5 h-5 mr-2 text-qc-success" />
                Learning Path
              </h3>
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Basic quantum gates and circuits
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Framework conversion concepts
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <Clock className="w-4 h-4 text-qc-accent flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Advanced algorithms and optimization
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <Clock className="w-4 h-4 text-qc-accent flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Noise modeling and error correction
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <h3 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                <Wrench className="w-5 h-5 mr-2 text-qc-accent" />
                Resources
              </h3>
              <div className="space-y-3">
                <Link
                  href="/examples"
                  className="flex items-center space-x-3 text-qc-muted hover:text-qc-fg transition-colors group"
                >
                  <Play className="w-4 h-4 group-hover:text-qc-accent" />
                  <span className="text-sm">Interactive Examples</span>
                  <ChevronRight className="w-4 h-4 ml-auto group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link
                  href="/docs"
                  className="flex items-center space-x-3 text-qc-muted hover:text-qc-fg transition-colors group"
                >
                  <FileText className="w-4 h-4 group-hover:text-qc-accent" />
                  <span className="text-sm">Complete Documentation</span>
                  <ChevronRight className="w-4 h-4 ml-auto group-hover:translate-x-1 transition-transform" />
                </Link>
                <a
                  href={config.social.github}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-3 text-qc-muted hover:text-qc-fg transition-colors group"
                >
                  <GitBranch className="w-4 h-4 group-hover:text-qc-accent" />
                  <span className="text-sm">Source Code</span>
                  <ChevronRight className="w-4 h-4 ml-auto group-hover:translate-x-1 transition-transform" />
                </a>
              </div>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "features",
      title: "Features",
      subtitle: "Platform capabilities",
      icon: <SparklesIcon className="w-5 h-5" />,
      badge: "Complete",
      category: "Platform",
      content: (
        <div className="space-y-8">
          <div className="mb-10 max-w-3xl">
            <h2 className="font-display text-display-2 font-semibold text-qc-fg">
              Features
            </h2>
            <p className="text-lg text-qc-muted mt-3">
              Comprehensive quantum computing tools for conversion, simulation,
              and visualization
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <div className="flex items-center mb-4">
                <div className="w-12 h-12 bg-qc-surface-2 border border-qc-line rounded-lg flex items-center justify-center mr-4">
                  <FrameworkConversionIcon className="w-6 h-6 text-qc-accent" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-qc-fg">
                    Framework Conversion
                  </h3>
                  <p className="text-qc-muted text-sm">
                    Convert between Qiskit, Cirq, and PennyLane
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    AST-based parsing and intelligent gate mapping
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    OpenQASM 3.0 as universal intermediate representation
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Circuit optimization levels 0-3
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Validation and error reporting
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <div className="flex items-center mb-4">
                <div className="w-12 h-12 bg-qc-surface-2 border border-qc-line rounded-lg flex items-center justify-center mr-4">
                  <Play className="w-6 h-6 text-qc-accent" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-qc-fg">
                    Quantum Simulation
                  </h3>
                  <p className="text-qc-muted text-sm">
                    Multiple backends for accurate simulation
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Statevector backend for exact simulation
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Density matrix backend for noise modeling
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Stabilizer backend for Clifford circuits
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Configurable shot counts (up to 100,000)
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <div className="flex items-center mb-4">
                <div className="w-12 h-12 bg-qc-surface-2 border border-qc-line rounded-lg flex items-center justify-center mr-4">
                  <BarChart3 className="w-6 h-6 text-qc-accent" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-qc-fg">
                    Visualization
                  </h3>
                  <p className="text-qc-muted text-sm">
                    Interactive charts and circuit diagrams
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Real-time circuit visualization
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Histogram plots for measurement results
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    State vector and probability displays
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Export capabilities (JSON, CSV, PNG)
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <div className="flex items-center mb-4">
                <div className="w-12 h-12 bg-qc-surface-2 border border-qc-line rounded-lg flex items-center justify-center mr-4">
                  <Book className="w-6 h-6 text-qc-accent" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-qc-fg">
                    Educational Tools
                  </h3>
                  <p className="text-qc-muted text-sm">
                    Learning resources and guided examples
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Pre-built example circuits
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Framework comparison tutorials
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Interactive learning modules
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Beginner to advanced difficulty levels
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6 flex items-center">
              <Settings className="w-6 h-6 mr-3 text-qc-accent" />
              Advanced Features
            </h3>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="text-center">
                <div className="w-12 h-12 bg-qc-surface-3 rounded-lg flex items-center justify-center mx-auto mb-3">
                  <Terminal className="w-6 h-6 text-qc-accent" />
                </div>
                <h4 className="text-lg font-semibold text-qc-fg mb-2">
                  Web IDE
                </h4>
                <p className="text-qc-muted text-sm">
                  Professional code editor with syntax highlighting and
                  IntelliSense
                </p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 bg-qc-surface-3 rounded-lg flex items-center justify-center mx-auto mb-3">
                  <Shield className="w-6 h-6 text-qc-accent" />
                </div>
                <h4 className="text-lg font-semibold text-qc-fg mb-2">
                  Security
                </h4>
                <p className="text-qc-muted text-sm">
                  Input validation, rate limiting, and secure API endpoints
                </p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 bg-qc-surface-3 rounded-lg flex items-center justify-center mx-auto mb-3">
                  <Cloud className="w-6 h-6 text-qc-accent" />
                </div>
                <h4 className="text-lg font-semibold text-qc-fg mb-2">
                  Scalability
                </h4>
                <p className="text-qc-muted text-sm">
                  Docker deployment, load balancing, and high availability
                </p>
              </div>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "architecture",
      title: "Architecture",
      subtitle: "System design",
      icon: <Layers className="w-5 h-5" />,
      badge: "Technical",
      category: "Technical",
      content: (
        <div className="space-y-8">
          <div className="mb-10 max-w-3xl">
            <h2 className="font-display text-display-2 font-semibold text-qc-fg">
              Architecture
            </h2>
            <p className="text-lg text-qc-muted mt-3">
              Modern, scalable architecture designed for quantum computing
              workflows
            </p>
          </div>

          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6">
              High-Level Architecture
            </h3>
            <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line">
              <pre className="qc-code qc-code--plain overflow-x-auto text-xs">
                {`Frontend (Next.js)          Backend (FastAPI)          Quantum Processing
├── React Components     ├── REST API Layer       ├── Quantum Converters
├── Code Editor          ├── Rate Limits & Queues ├── Quantum Simulator
├── Visualization        ├── Service Layer        └── Circuit Optimizers
└── Real-time Updates    └── Database Layer`}
              </pre>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <h3 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                <Monitor className="w-5 h-5 mr-2 text-qc-accent" />
                Frontend Layer
              </h3>
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Next.js 14 with App Router
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    React 18 with TypeScript
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Monaco Editor integration
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Live results in the editor
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <h3 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                <Server className="w-5 h-5 mr-2 text-qc-accent" />
                Backend Layer
              </h3>
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    FastAPI with async support
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    PostgreSQL with SQLAlchemy
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Redis caching layer
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-4 h-4 text-qc-success flex-shrink-0" />
                  <span className="text-qc-muted text-sm">
                    Pydantic data validation
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6">
              Data Flow Architecture
            </h3>
            <div className="space-y-6">
              <div>
                <h4 className="text-lg font-semibold text-qc-fg mb-3">
                  Circuit Conversion Flow
                </h4>
                <div className="bg-qc-surface-2 rounded-lg p-4 border border-qc-line">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-qc-accent rounded-full"></div>
                      <span className="text-qc-muted">User Input</span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-qc-muted" />
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-qc-accent rounded-full"></div>
                      <span className="text-qc-muted">API Request</span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-qc-muted" />
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-qc-accent rounded-full"></div>
                      <span className="text-qc-muted">Framework Parser</span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-qc-muted" />
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-qc-accent rounded-full"></div>
                      <span className="text-qc-muted">OpenQASM 3.0</span>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-lg font-semibold text-qc-fg mb-3">
                  Simulation Flow
                </h4>
                <div className="bg-qc-surface-2 rounded-lg p-4 border border-qc-line">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-qc-accent rounded-full"></div>
                      <span className="text-qc-muted">QASM Code</span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-qc-muted" />
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-qc-accent rounded-full"></div>
                      <span className="text-qc-muted">
                        Backend Selection
                      </span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-qc-muted" />
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-qc-accent rounded-full"></div>
                      <span className="text-qc-muted">
                        Circuit Execution
                      </span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-qc-muted" />
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-qc-accent rounded-full"></div>
                      <span className="text-qc-muted">Results</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "api",
      title: "API Reference",
      subtitle: "Technical documentation",
      icon: <ApiIcon className="w-5 h-5" />,
      badge: "Reference",
      category: "Technical",
      content: (
        <div className="space-y-8">
          <div className="mb-10 max-w-3xl">
            <h2 className="font-display text-display-2 font-semibold text-qc-fg">
              API Reference
            </h2>
            <p className="text-lg text-qc-muted mt-3">
              Complete REST API documentation for QCanvas platform integration
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <h3 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                <FrameworkConversionIcon className="w-5 h-5 mr-2 text-qc-accent" />
                Conversion API
              </h3>
              <div className="space-y-4">
                <div className="bg-qc-surface-2 rounded-lg p-4 border border-qc-line">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-qc-fg font-medium">
                      POST /api/converter/convert
                    </span>
                    <span className="text-xs bg-qc-surface-3 text-qc-success px-2 py-1 rounded">
                      Active
                    </span>
                  </div>
                  <p className="text-qc-muted text-sm mb-3">
                    Convert framework code to OpenQASM 3.0
                  </p>
                  <pre className="qc-code overflow-x-auto rounded-md p-3 text-xs">
                    {`{
  "source_code": "from qiskit import...",
  "source_framework": "qiskit",
  "conversion_type": "classic"
}
// Response includes: qasm_code, gates, depth, qubits`}
                  </pre>
                </div>

                <div className="bg-qc-surface-2 rounded-lg p-4 border border-qc-line">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-qc-fg font-medium">
                      GET /api/health
                    </span>
                    <span className="text-xs bg-qc-surface-3 text-qc-accent px-2 py-1 rounded">
                      Health
                    </span>
                  </div>
                  <p className="text-qc-muted text-sm">
                    Check API health status
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-qc-surface border border-qc-line rounded-xl p-6">
              <h3 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                <Play className="w-5 h-5 mr-2 text-qc-success" />
                Simulation API (QSim)
              </h3>
              <div className="space-y-4">
                <div className="bg-qc-surface-2 rounded-lg p-4 border border-qc-line">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-qc-fg font-medium">
                      POST /api/simulator/execute
                    </span>
                    <span className="text-xs bg-qc-surface-3 text-qc-success px-2 py-1 rounded">
                      Active
                    </span>
                  </div>
                  <p className="text-qc-muted text-sm mb-3">
                    Execute OpenQASM 3.0 with QSim
                  </p>
                  <pre className="qc-code overflow-x-auto rounded-md p-3 text-xs">
                    {`{
  "qasm_code": "OPENQASM 3.0; ...",
  "backend": "cirq",  // cirq, qiskit, pennylane
  "shots": 1024
}
// Response includes: counts, metadata, probs`}
                  </pre>
                </div>

                <div className="bg-qc-surface-2 rounded-lg p-4 border border-qc-line">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-qc-fg font-medium">
                      Response Metadata
                    </span>
                    <span className="text-xs bg-qc-surface-3 text-qc-accent px-2 py-1 rounded">
                      Stats
                    </span>
                  </div>
                  <p className="text-qc-muted text-sm">
                    execution_time, simulation_time, memory_usage, cpu_usage,
                    fidelity
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6">
              QSim Simulation Backends
            </h3>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line hover:border-qc-line-strong transition-colors">
                <div className="flex items-center mb-4">
                  <div className="w-10 h-10 bg-qc-surface-3 rounded-lg flex items-center justify-center">
                    <CirqIcon className="w-6 h-6 text-qc-accent" />
                  </div>
                  <h4 className="text-lg font-semibold text-qc-fg ml-3">
                    Cirq
                  </h4>
                </div>
                <p className="text-qc-muted text-sm mb-3">
                  Google&apos;s quantum computing framework with statevector
                  simulation
                </p>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-qc-muted">
                      Shots:
                    </span>
                    <span className="text-qc-fg">1 - 100,000</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-qc-muted">
                      Best for:
                    </span>
                    <span className="text-qc-fg">Near-term devices</span>
                  </div>
                </div>
              </div>

              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line hover:border-qc-line-strong transition-colors">
                <div className="flex items-center mb-4">
                  <div className="w-10 h-10 bg-qc-surface-3 rounded-lg flex items-center justify-center">
                    <QiskitIcon className="w-6 h-6 text-qc-accent" />
                  </div>
                  <h4 className="text-lg font-semibold text-qc-fg ml-3">
                    Qiskit
                  </h4>
                </div>
                <p className="text-qc-muted text-sm mb-3">
                  IBM&apos;s comprehensive quantum SDK with QASM simulator
                  backend
                </p>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-qc-muted">
                      Shots:
                    </span>
                    <span className="text-qc-fg">1 - 100,000</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-qc-muted">
                      Best for:
                    </span>
                    <span className="text-qc-fg">IBM Quantum</span>
                  </div>
                </div>
              </div>

              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line hover:border-qc-line-strong transition-colors">
                <div className="flex items-center mb-4">
                  <div className="w-10 h-10 bg-qc-surface-3 rounded-lg flex items-center justify-center">
                    <PennyLaneIcon className="w-6 h-6 text-qc-success" />
                  </div>
                  <h4 className="text-lg font-semibold text-qc-fg ml-3">
                    PennyLane
                  </h4>
                </div>
                <p className="text-qc-muted text-sm mb-3">
                  Xanadu&apos;s quantum ML framework with default.qubit device
                </p>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-qc-muted">
                      Shots:
                    </span>
                    <span className="text-qc-fg">1 - 100,000</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-qc-muted">
                      Best for:
                    </span>
                    <span className="text-qc-fg">QML & Variational</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      ),
    },
    {
      id: "hybrid-execution",
      title: "Hybrid Execution API",
      subtitle: "Python API for hybrid CPU-QPU execution",
      icon: <Cpu className="w-5 h-5" />,
      badge: "New",
      category: "Technical",
      content: (
        <div className="space-y-8">
          <div className="mb-10 max-w-3xl">
            <h2 className="font-display text-display-2 font-semibold text-qc-fg">
              Hybrid Execution API
            </h2>
            <p className="text-lg text-qc-muted mt-3">
              Execute Python code with quantum circuits. Compile circuits, run
              simulations, and access results programmatically.
            </p>
          </div>

          {/* API Functions */}
          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6 flex items-center">
              <Code className="w-6 h-6 mr-3 text-qc-accent" />
              Available Functions
            </h3>

            <div className="space-y-6">
              {/* compile function */}
              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line">
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <h4 className="flex min-w-0 flex-wrap items-baseline gap-x-2 font-mono text-lg font-semibold text-qc-fg">
                    <span className="text-qc-accent mr-2">
                      compile
                    </span>
                    <span className="text-sm font-normal text-qc-muted">
                      (circuit, framework=None)
                    </span>
                  </h4>
                  <span className="text-xs bg-qc-surface-3 text-qc-accent px-3 py-1 rounded-full">
                    Function
                  </span>
                </div>
                <p className="text-qc-muted mb-4">
                  Compile a quantum circuit object to OpenQASM 3.0 format.
                </p>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm mb-2 text-qc-muted">
                      Parameters:
                    </p>
                    <ul className="text-sm text-qc-muted space-y-1 ml-4">
                      <li>
                        <code className="text-qc-accent">circuit</code>{" "}
                        - Circuit object from Cirq, Qiskit, or PennyLane
                      </li>
                      <li>
                        <code className="text-qc-accent">
                          framework
                        </code>{" "}
                        - Optional: <code>&quot;cirq&quot;</code>,{" "}
                        <code>&quot;qiskit&quot;</code>,{" "}
                        <code>&quot;pennylane&quot;</code> (auto-detected if not
                        provided)
                      </li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-sm mb-2 text-qc-muted">
                      Returns:
                    </p>
                    <p className="text-sm text-qc-muted ml-4">
                      <code className="text-qc-accent">str</code> -
                      OpenQASM 3.0 code
                    </p>
                  </div>
                  <div className="bg-qc-surface-2 rounded-lg p-4 mt-4">
                    <pre className="qc-code qc-code--plain overflow-x-auto text-xs">
                      {`from qcanvas import compile
import cirq

q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1], key='result')
])

qasm = compile(circuit, framework="cirq")
print(qasm)`}
                    </pre>
                  </div>
                </div>
              </div>

              {/* qsim.run function */}
              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line">
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <h4 className="flex min-w-0 flex-wrap items-baseline gap-x-2 font-mono text-lg font-semibold text-qc-fg">
                    <span className="text-qc-accent mr-2">
                      qsim.run
                    </span>
                    <span className="text-sm font-normal text-qc-muted">
                      (qasm_code, shots=1024, backend=&quot;cirq&quot;)
                    </span>
                  </h4>
                  <span className="text-xs bg-qc-surface-3 text-qc-success px-3 py-1 rounded-full">
                    Function
                  </span>
                </div>
                <p className="text-qc-muted mb-4">
                  Execute OpenQASM 3.0 code using QSim quantum simulator.
                </p>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm mb-2 text-qc-muted">
                      Parameters:
                    </p>
                    <ul className="text-sm text-qc-muted space-y-1 ml-4">
                      <li>
                        <code className="text-qc-accent">
                          qasm_code
                        </code>{" "}
                        - OpenQASM 3.0 code string
                      </li>
                      <li>
                        <code className="text-qc-accent">shots</code> -
                        Number of measurement shots (default: 1024, use 0 for
                        exact statevector)
                      </li>
                      <li>
                        <code className="text-qc-accent">backend</code>{" "}
                        - <code>&quot;cirq&quot;</code>,{" "}
                        <code>&quot;qiskit&quot;</code>, or{" "}
                        <code>&quot;pennylane&quot;</code> (default:{" "}
                        <code>&quot;cirq&quot;</code>)
                      </li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-sm mb-2 text-qc-muted">
                      Returns:
                    </p>
                    <p className="text-sm text-qc-muted ml-4">
                      <code className="text-qc-accent">
                        SimulationResult
                      </code>{" "}
                      - Result object with counts, probabilities, and metadata
                    </p>
                  </div>
                  <div className="bg-qc-surface-2 rounded-lg p-4 mt-4">
                    <pre className="qc-code qc-code--plain overflow-x-auto text-xs">
                      {`import qsim

qasm = '''
OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c[0] = measure q[0];
c[1] = measure q[1];
'''

result = qsim.run(qasm, shots=1000, backend="cirq")
print(result.counts)
print(result.probabilities)`}
                    </pre>
                  </div>
                </div>
              </div>

              {/* compile_and_execute function */}
              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line">
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <h4 className="flex min-w-0 flex-wrap items-baseline gap-x-2 font-mono text-lg font-semibold text-qc-fg">
                    <span className="text-qc-accent mr-2">
                      compile_and_execute
                    </span>
                    <span className="text-sm font-normal text-qc-muted">
                      (circuit, framework=None, shots=1024,
                      backend=&quot;cirq&quot;)
                    </span>
                  </h4>
                  <span className="text-xs bg-qc-surface-3 text-qc-accent px-3 py-1 rounded-full">
                    Convenience
                  </span>
                </div>
                <p className="text-qc-muted mb-4">
                  Compile a circuit and execute it in a single call.
                </p>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm mb-2 text-qc-muted">
                      Parameters:
                    </p>
                    <ul className="text-sm text-qc-muted space-y-1 ml-4">
                      <li>
                        <code className="text-qc-accent">circuit</code>{" "}
                        - Circuit object from Cirq, Qiskit, or PennyLane
                      </li>
                      <li>
                        <code className="text-qc-accent">
                          framework
                        </code>{" "}
                        - Optional: auto-detected if not provided
                      </li>
                      <li>
                        <code className="text-qc-accent">shots</code> -
                        Number of measurement shots (default: 1024)
                      </li>
                      <li>
                        <code className="text-qc-accent">backend</code>{" "}
                        - Simulation backend (default:{" "}
                        <code>&quot;cirq&quot;</code>)
                      </li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-sm mb-2 text-qc-muted">
                      Returns:
                    </p>
                    <p className="text-sm text-qc-muted ml-4">
                      <code className="text-qc-accent">
                        SimulationResult
                      </code>{" "}
                      - Result object with counts, probabilities, and metadata
                    </p>
                  </div>
                  <div className="bg-qc-surface-2 rounded-lg p-4 mt-4">
                    <pre className="qc-code qc-code--plain overflow-x-auto text-xs">
                      {`from qcanvas import compile_and_execute
import cirq

q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1], key='result')
])

result = compile_and_execute(circuit, framework="cirq", shots=1000)
print(result.counts)
print(result.probabilities)`}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* SimulationResult Attributes Table */}
          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6 flex items-center">
              <BarChart3 className="w-6 h-6 mr-3 text-qc-accent" />
              SimulationResult Attributes
            </h3>
            <p className="text-qc-muted mb-6">
              The{" "}
              <code className="text-qc-accent">SimulationResult</code>{" "}
              object returned by{" "}
              <code className="text-qc-accent">qsim.run()</code> and{" "}
              <code className="text-qc-accent">
                compile_and_execute()
              </code>{" "}
              provides comprehensive access to simulation data.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-qc-line">
                    <th className="text-left py-3 px-4 text-qc-fg font-semibold">
                      Attribute
                    </th>
                    <th className="text-left py-3 px-4 text-qc-fg font-semibold">
                      Type
                    </th>
                    <th className="text-left py-3 px-4 text-qc-fg font-semibold">
                      Description
                    </th>
                    <th className="text-left py-3 px-4 text-qc-fg font-semibold">
                      Example
                    </th>
                  </tr>
                </thead>
                <tbody className="text-qc-muted">
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">counts</code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>Dict[str, int]</code>
                    </td>
                    <td className="py-3 px-4">
                      Measurement counts for each outcome
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>{`{'00': 512, '11': 512}`}</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">
                        probabilities
                      </code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>Dict[str, float]</code>
                    </td>
                    <td className="py-3 px-4">
                      Probability of each measurement outcome
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>{`{'00': 0.5, '11': 0.5}`}</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">
                        statevector
                      </code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>List[complex]</code>
                    </td>
                    <td className="py-3 px-4">
                      Full quantum statevector (only when shots=0)
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>{`[0.707+0j, 0+0j, ...]`}</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">n_qubits</code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>int</code>
                    </td>
                    <td className="py-3 px-4">
                      Number of qubits in the circuit
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>2</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">shots</code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>int</code>
                    </td>
                    <td className="py-3 px-4">
                      Number of measurement shots executed
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>1000</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">backend</code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>str</code>
                    </td>
                    <td className="py-3 px-4">Backend used for simulation</td>
                    <td className="py-3 px-4 text-sm">
                      <code>&quot;cirq&quot;</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">
                        execution_time
                      </code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>str</code>
                    </td>
                    <td className="py-3 px-4">
                      Total execution time (human-readable)
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>&quot;1.23ms&quot;</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">
                        simulation_time
                      </code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>str</code>
                    </td>
                    <td className="py-3 px-4">
                      Time spent in quantum simulation
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>&quot;0.98ms&quot;</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">
                        memory_usage
                      </code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>str</code>
                    </td>
                    <td className="py-3 px-4">
                      Memory consumed during simulation
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>&quot;45.2 MB&quot;</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">cpu_usage</code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>str</code>
                    </td>
                    <td className="py-3 px-4">
                      CPU utilization during simulation
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>&quot;12.5%&quot;</code>
                    </td>
                  </tr>
                  <tr className="border-b border-qc-line hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">fidelity</code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>float</code>
                    </td>
                    <td className="py-3 px-4">
                      Simulation fidelity as percentage
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>100.0</code>
                    </td>
                  </tr>
                  <tr className="hover:bg-qc-surface-2 transition-colors">
                    <td className="py-3 px-4">
                      <code className="text-qc-accent">metadata</code>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>Dict[str, Any]</code>
                    </td>
                    <td className="py-3 px-4">
                      Additional backend-specific metadata
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <code>{`{'gate_count': 5}`}</code>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Printing Circuits */}
          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6 flex items-center">
              <FileText className="w-6 h-6 mr-3 text-qc-accent" />
              Printing Circuits
            </h3>
            <p className="text-qc-muted mb-6">
              You can print circuit objects directly to visualize their
              structure in all supported frameworks.
            </p>

            <div className="grid md:grid-cols-3 gap-6">
              {/* Cirq */}
              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line">
                <h4 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                  <div className="w-8 h-8 bg-qc-surface-3 rounded-lg flex items-center justify-center mr-3">
                    <CirqIcon className="w-5 h-5 text-qc-accent" />
                  </div>
                  Cirq
                </h4>
                <div className="bg-qc-surface-2 rounded-lg p-4 mb-4">
                  <pre className="qc-code qc-code--plain overflow-x-auto text-xs">
                    {`import cirq

q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1])
])

print(circuit)`}
                  </pre>
                </div>
                <div className="bg-qc-surface-2 rounded-lg p-3 border border-qc-line">
                  <pre className="text-xs text-qc-fg font-mono">
                    {`0: ───H───@───M───
           │
1: ────────X───M───`}
                  </pre>
                </div>
              </div>

              {/* Qiskit */}
              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line">
                <h4 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                  <div className="w-8 h-8 bg-qc-surface-3 rounded-lg flex items-center justify-center mr-3">
                    <QiskitIcon className="w-5 h-5 text-qc-accent" />
                  </div>
                  Qiskit
                </h4>
                <div className="bg-qc-surface-2 rounded-lg p-4 mb-4">
                  <pre className="qc-code qc-code--plain overflow-x-auto text-xs">
                    {`from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

print(qc)`}
                  </pre>
                </div>
                <div className="bg-qc-surface-2 rounded-lg p-3 border border-qc-line">
                  <pre className="text-xs text-qc-fg font-mono">
                    {`     ┌───┐     ┌─┐
q_0: ┤ H ├──■──┤M├
     └───┘ │ ┌┴┐└╥┘
q_1: ──────┼─┤M├─╫─
           │ └╥┘ ║
c: 2/══════╪══╬══╩═`}
                  </pre>
                </div>
              </div>

              {/* PennyLane */}
              <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line">
                <h4 className="text-lg font-semibold text-qc-fg mb-4 flex items-center">
                  <div className="w-8 h-8 bg-qc-surface-3 rounded-lg flex items-center justify-center mr-3">
                    <PennyLaneIcon className="w-5 h-5 text-qc-success" />
                  </div>
                  PennyLane
                </h4>
                <div className="bg-qc-surface-2 rounded-lg p-4 mb-4">
                  <pre className="qc-code qc-code--plain overflow-x-auto text-xs">
                    {`import pennylane as qml

dev = qml.device('default.qubit', wires=2)

@qml.qnode(dev)
def circuit():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    return qml.expval(qml.PauliZ(0))

print(qml.draw(circuit)())`}
                  </pre>
                </div>
                <div className="bg-qc-surface-2 rounded-lg p-3 border border-qc-line">
                  <pre className="text-xs text-qc-fg font-mono">
                    {`0: ──H──╭C──┤ ⟨Z⟩
1: ──────╰X──┤`}
                  </pre>
                </div>
              </div>
            </div>
          </div>

          {/* Complete Example */}
          <div className="bg-qc-surface border border-qc-line rounded-xl p-8">
            <h3 className="text-2xl font-bold text-qc-fg mb-6 flex items-center">
              <Lightbulb className="w-6 h-6 mr-3 text-qc-accent" />
              Complete Workflow Example
            </h3>
            <div className="bg-qc-surface-2 rounded-lg p-6 border border-qc-line">
              <div className="bg-qc-surface-2 rounded-lg p-4">
                <pre className="text-sm text-qc-muted overflow-x-auto">
                  {`import cirq
from qcanvas import compile, compile_and_execute
import qsim

# Step 1: Create circuit
q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1], key='result')
])

# Step 2: Print circuit (optional)
print("Circuit Structure:")
print(circuit)

# Step 3: Compile to QASM
qasm = compile(circuit, framework="cirq")
print("\\nGenerated QASM:")
print(qasm)

# Step 4: Execute simulation
result = qsim.run(qasm, shots=1000, backend="cirq")

# Step 5: Access results
print("\\nSimulation Results:")
print(f"  Counts: {result.counts}")
print(f"  Probabilities: {result.probabilities}")
print(f"  Execution time: {result.execution_time}")
print(f"  Qubits: {result.n_qubits}")
print(f"  Shots: {result.shots}")
print(f"  Backend: {result.backend}")

# Alternative: Compile and execute in one step
result2 = compile_and_execute(circuit, framework="cirq", shots=1000)
print(f"\\nOne-step result: {result2.counts}")`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      ),
    },
  ];

  const toc = [
    { id: "overview", label: "Overview" },
    { id: "getting-started", label: "Getting started" },
    { id: "features", label: "Features" },
    { id: "architecture", label: "Architecture" },
    { id: "api", label: "Python API" },
    { id: "hybrid-execution", label: "Hybrid execution" },
  ];

  return (
    <div className="qc-page">
      <Navbar />

      {/* Section tabs (small screens) */}
      <div className="top-14 z-30 border-b border-qc-line bg-qc-bg [position:sticky] lg:hidden">
        <nav
          aria-label="Documentation sections"
          className="hide-scrollbar flex gap-1 overflow-x-auto px-4 py-2 text-sm [mask-image:linear-gradient(to_right,black_85%,transparent)]"
        >
          {toc.map((item) => (
            <button
              key={item.id}
              id={`nav-${item.id}`}
              type="button"
              onClick={() => scrollToSection(item.id)}
              aria-current={activeSection === item.id ? "true" : undefined}
              className={`qc-focus shrink-0 rounded-md px-3 py-1.5 transition-colors duration-150 ${
                activeSection === item.id
                  ? "bg-qc-surface-2 text-qc-fg"
                  : "text-qc-muted hover:text-qc-fg"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="qc-container grid gap-12 pb-24 pt-10 lg:grid-cols-[12rem_minmax(0,1fr)] lg:pt-28">
        <aside className="hidden lg:block">
          <nav aria-label="On this page" className="top-24 [position:sticky]">
            <p className="qc-eyebrow">On this page</p>
            <ul className="mt-3 space-y-0.5 border-l border-qc-line">
              {toc.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => scrollToSection(item.id)}
                    aria-current={activeSection === item.id ? "true" : undefined}
                    className={`qc-focus -ml-px block w-full border-l py-1.5 pl-3 text-left text-sm transition-colors duration-150 ${
                      activeSection === item.id
                        ? "border-qc-accent text-qc-fg"
                        : "border-transparent text-qc-muted hover:text-qc-fg"
                    }`}
                  >
                    {item.label}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <main id="main" className="qc-docs min-w-0">
          <header className="max-w-3xl border-b border-qc-line pb-12">
            <p className="qc-eyebrow">Documentation</p>
            <h1 className="mt-3 font-display text-display-1 font-semibold text-qc-fg">
              How QCanvas works
            </h1>
            <p className="mt-5 text-lg leading-relaxed text-qc-muted">
              Write a circuit in Cirq, Qiskit or PennyLane, compile it to
              OpenQASM 3.0 and simulate it. This guide covers the editor, the
              conversion pipeline, the Python API and hybrid execution.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                href={canAccessApp ? "/app" : "/login"}
                className="qc-btn qc-btn-primary"
              >
                Open the editor
              </Link>
              <button
                type="button"
                onClick={() => scrollToSection("getting-started")}
                className="qc-btn qc-btn-secondary"
              >
                Getting started
              </button>
            </div>
          </header>

          {sections.map((section) => (
            <section
              key={section.id}
              id={section.id}
              className="!scroll-mt-28 border-b border-qc-line py-16 last:border-b-0"
            >
              {section.content}
            </section>
          ))}
        </main>
      </div>

      <SiteFooter />
    </div>
  );
}
