"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  Zap,
  Code,
  Play,
  Book,
  GitBranch,
  Cpu,
  Atom,
  Lightbulb,
  Star,
  Globe,
  RocketAnimated,
  FrameworkConversionAnimated,
  WebIdeIcon,
  PlaySvgRepo,
  CodeSquareSvgRepo,
} from "@/components/Icons";
import { ChevronDown, ArrowRight, Users, Sparkles } from "lucide-react";
import { useFileStore } from "@/lib/store";
import { config, getCopyrightText } from "@/lib/config";
import Navbar from "@/components/Navbar";

import { hasValidAuth, useAuthStore } from "@/lib/authStore";
import FeatureGrid from "@/components/FeatureGrid";

export default function HomePage() {
  const { theme } = useFileStore();
  const [isVisible, setIsVisible] = useState(false);
  const [scrollY, setScrollY] = useState(0);
  const { isAuthenticated, token } = useAuthStore();
  const canAccessApp = hasValidAuth({ isAuthenticated, token });

  useEffect(() => {
    setIsVisible(true);

    const handleScroll = () => {
      setScrollY(window.scrollY);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    element?.scrollIntoView({ behavior: "smooth" });
  };

  // Get example code by type
  const getExampleCode = (exampleType: string) => {
    const examples = {
      "bell-state": {
        name: "bell_state_cirq.py",
        content: `import cirq

# Create qubits
q0, q1 = cirq.LineQubit.range(2)

# Create Bell State circuit
circuit = cirq.Circuit()
circuit.append(cirq.H(q0))          # Hadamard gate
circuit.append(cirq.CNOT(q0, q1))   # CNOT gate
circuit.append(cirq.measure(q0, key='m0'))
circuit.append(cirq.measure(q1, key='m1'))

# Expected: 50% |00⟩, 50% |11⟩`,
      },
      "quantum-teleportation": {
        name: "teleportation_qiskit.py",
        content: `from qiskit import QuantumCircuit

# Quantum Teleportation Circuit
qc = QuantumCircuit(3, 3)

# STEP 1: Prepare state to teleport
qc.h(0)

# STEP 2: Create Bell pair (q1, q2)
qc.h(1)
qc.cx(1, 2)

# STEP 3: Bell measurement
qc.cx(0, 1)
qc.h(0)
qc.measure(0, 0)
qc.measure(1, 1)

# STEP 4: Classical corrections
c = [0, 0, 0]  # Placeholder for conditions
if c[1] == 1:
    qc.x(2)
if c[0] == 1:
    qc.z(2)

# Measure teleported qubit
qc.measure(2, 2)`,
      },
      "grovers-search": {
        name: "grovers_pennylane.py",
        content: `import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def grovers_search():
    # Initialize superposition
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    
    # Oracle: mark |11⟩
    qml.CZ(wires=[0, 1])
    
    # Diffusion operator
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.PauliX(wires=0)
    qml.PauliX(wires=1)
    qml.CZ(wires=[0, 1])
    qml.PauliX(wires=0)
    qml.PauliX(wires=1)
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    
    return qml.probs(wires=[0, 1])

# Expected: High probability for |11⟩`,
      },
    };
    return (
      examples[exampleType as keyof typeof examples] || examples["bell-state"]
    );
  };

  // Handle trying an example
  const handleTryExample = (example: { name: string; content: string }) => {
    if (canAccessApp) {
      // If authenticated, store the example data and navigate to app
      sessionStorage.setItem("pending-example", JSON.stringify(example));
      window.location.href = "/app?loadExample=1";
    } else {
      // If not authenticated, store the example data and go to login
      sessionStorage.setItem("pending-example", JSON.stringify(example));
      window.location.href = "/login?loadExample=1";
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a1a] relative overflow-x-hidden">
      {/* SEO: page h1 — differs from <title> tag to avoid the duplicate h1/title
          penalty. Visually hidden but fully readable by crawlers. */}
      <h1 className="sr-only">
        Open-Source Quantum Circuit Simulator — Cirq, Qiskit &amp; PennyLane
        Unified with OpenQASM 3.0
      </h1>

      {/* Navigation */}
      <Navbar scrollToFeatures={scrollToSection} />

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center px-4 pt-20 overflow-hidden">
        {/* Grid dot background */}
        <div className="absolute inset-0 bg-grid-pattern opacity-60"></div>

        {/* Hero spotlight radial glow */}
        <div className="absolute inset-0 hero-spotlight"></div>

        {/* Subtle background orbs — fewer, more vibrant */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-32 -right-32 w-[500px] h-[500px] bg-indigo-500 opacity-[0.07] rounded-full blur-[100px]"></div>
          <div className="absolute -bottom-32 -left-32 w-[500px] h-[500px] bg-violet-500 opacity-[0.07] rounded-full blur-[100px]"></div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-cyan-500 opacity-[0.05] rounded-full blur-[80px]"></div>
        </div>

        {/* Floating elements — fewer, more visible */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-24 left-[8%] animate-float">
            <Atom className="w-8 h-8 text-indigo-400 opacity-20" />
          </div>
          <div
            className="absolute top-1/3 right-[8%] animate-float-reverse"
            style={{ animationDelay: "2s" }}
          >
            <Sparkles className="w-6 h-6 text-violet-400 opacity-25" />
          </div>
          <div
            className="absolute bottom-1/3 left-[12%] animate-float"
            style={{ animationDelay: "4s" }}
          >
            <Cpu className="w-7 h-7 text-cyan-400 opacity-20" />
          </div>
          <div className="absolute top-16 right-1/4 w-1.5 h-1.5 bg-indigo-400 rounded-full animate-ping opacity-40"></div>
          <div
            className="absolute bottom-1/4 left-1/3 w-1.5 h-1.5 bg-cyan-400 rounded-full animate-ping opacity-30"
            style={{ animationDelay: "1s" }}
          ></div>
        </div>

        <div className="text-center max-w-5xl mx-auto relative z-10">
          <div
            className={`transition-all duration-1000 delay-300 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"}`}
          >
            {/* Glowing badge */}
            <div className="inline-flex items-center glow-badge bg-indigo-500/10 rounded-full px-6 py-2.5 mb-10 backdrop-blur-sm hover:bg-indigo-500/15 transition-all duration-500 hover:scale-105">
              <Zap className="w-4 h-4 text-indigo-400 mr-2" />
              <span className="text-sm font-medium text-indigo-300 adjust-main-heading">
                Next-Generation Quantum Development
              </span>
            </div>

            <h1 className="text-5xl md:text-7xl lg:text-8xl font-bold mb-8 leading-[1.1] tracking-tight">
              <span className="quantum-gradient bg-clip-text text-transparent">
                QCanvas:
              </span>
              <br />
              <span className="text-white">The Quantum</span>
              <br />
              <span className="gradient-text">Unified Simulator</span>
            </h1>

            <p className="text-lg md:text-xl text-black dark:text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
              {config.project.description}
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16">
              <button
                onClick={() => handleTryExample(getExampleCode("bell-state"))}
                className="btn-quantum text-lg px-8 py-4 flex items-center group"
              >
                <Play className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform duration-300 relative z-10" />
                <span className="relative z-10">Try QCanvas Now</span>
                <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform duration-300 relative z-10" />
              </button>
              <button
                onClick={() => scrollToSection("features")}
                className="btn-ghost text-lg px-8 py-4 flex items-center group"
              >
                <Lightbulb className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform duration-300" />
                <span>Explore Features</span>
              </button>
            </div>

            {/* Stats with glass cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl mx-auto mb-8">
              <div className="stat-card text-center group">
                <div className="text-2xl font-bold quantum-gradient bg-clip-text text-transparent mb-1">
                  {config.stats.frameworks}
                </div>
                <div className="text-sm text-black dark:text-gray-500 group-hover:text-gray-300 transition-colors">
                  Quantum Frameworks
                </div>
              </div>
              <div className="stat-card text-center group">
                <div className="text-2xl font-bold quantum-gradient bg-clip-text text-transparent mb-1">
                  {config.stats.standards}
                </div>
                <div className="text-sm text-black dark:text-gray-500 group-hover:text-gray-300 transition-colors">
                  Compatible
                </div>
              </div>
              <div className="stat-card text-center group">
                <div className="text-2xl font-bold quantum-gradient bg-clip-text text-transparent mb-1">
                  {config.stats.simulations}
                </div>
                <div className="text-sm text-black dark:text-gray-500 group-hover:text-gray-300 transition-colors">
                  Simulation
                </div>
              </div>
            </div>

            {/* Scroll Indicator */}
            <div className="animate-bounce">
              <button
                onClick={() => scrollToSection("features")}
                className="text-black dark:text-gray-500 hover:text-white transition-colors duration-200"
              >
                <ChevronDown className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 px-4 relative">
        <div className="absolute inset-0 bg-grid-pattern opacity-30"></div>
        <div className="max-w-7xl mx-auto relative z-10">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="quantum-gradient bg-clip-text text-transparent">
                Unified Framework Conversion for Cirq and Qiskit
              </span>
            </h2>
            <p className="text-lg text-black dark:text-gray-400 max-w-2xl mx-auto">
              Everything you need to build, convert, and simulate quantum
              circuits across Cirq, Qiskit, and PennyLane — with professional-grade
              tools and real-time OpenQASM 3.0 feedback.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="quantum-glass-dark card-accent-blue rounded-2xl p-8 hover-lift transition-all duration-500 group feature-card opacity-0 animate-fade-in hover:shadow-[0_0_30px_rgba(99,102,241,0.1)]">
              <div className="w-12 h-12 bg-indigo-500/15 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-indigo-500/25 transition-all duration-300">
                <FrameworkConversionAnimated className="w-8 h-8 text-indigo-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3 group-hover:text-indigo-400 transition-colors duration-300">
                Framework Conversion
              </h3>
              <p className="text-black dark:text-gray-400 mb-4 group-hover:text-gray-300 transition-colors duration-300 text-sm leading-relaxed">
                Seamlessly convert between Cirq, Qiskit, and PennyLane with
                intelligent parsing and OpenQASM 3.0 as the universal
                intermediate format.
              </p>
              <Link
                href="/app"
                className="flex items-center text-sm text-indigo-400 group-hover:text-indigo-300 transition-colors duration-300 font-medium"
                aria-label="Try framework conversion in QCanvas editor"
              >
                <span>Try conversion</span>
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-2 transition-transform duration-300" />
              </Link>
            </div>

            {/* Feature 2 */}
            <div className="quantum-glass-dark card-accent-purple rounded-2xl p-8 hover-lift transition-all duration-500 group feature-card opacity-0 animate-fade-in hover:shadow-[0_0_30px_rgba(168,85,247,0.1)]">
              <div className="w-12 h-12 bg-violet-500/15 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-violet-500/25 transition-all duration-300">
                <PlaySvgRepo className="w-8 h-8 text-violet-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3 group-hover:text-violet-400 transition-colors duration-300">
                Real-time Simulation
              </h3>
              <p className="text-black dark:text-gray-400 mb-4 group-hover:text-gray-300 transition-colors duration-300 text-sm leading-relaxed">
                Experience instant quantum circuit simulation with multiple
                backends, progress tracking, and interactive visualization
                powered by WebSocket.
              </p>
              <Link
                href="/app"
                className="flex items-center text-sm text-violet-400 group-hover:text-violet-300 transition-colors duration-300 font-medium"
                aria-label="Run real-time quantum simulation in QCanvas"
              >
                <span>Try simulation</span>
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-2 transition-transform duration-300" />
              </Link>
            </div>

            {/* Feature 3 */}
            <div className="quantum-glass-dark card-accent-teal rounded-2xl p-8 hover-lift transition-all duration-500 group feature-card opacity-0 animate-fade-in hover:shadow-[0_0_30px_rgba(6,182,212,0.1)]">
              <div className="w-12 h-12 bg-cyan-500/15 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-cyan-500/25 transition-all duration-300">
                <Book className="w-6 h-6 text-cyan-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3 group-hover:text-cyan-400 transition-colors duration-300">
                Educational Platform
              </h3>
              <p className="text-black dark:text-gray-400 mb-4 group-hover:text-gray-300 transition-colors duration-300 text-sm leading-relaxed">
                Learn quantum computing with guided examples, tutorials, and an
                intuitive interface designed for both beginners and experts.
              </p>
              <Link
                href="/docs"
                className="flex items-center text-sm text-cyan-400 group-hover:text-cyan-300 transition-colors duration-300 font-medium"
                aria-label="Explore quantum computing tutorials and documentation"
              >
                <span>Start learning</span>
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-2 transition-transform duration-300" />
              </Link>
            </div>

            {/* Feature 4 */}
            <div className="quantum-glass-dark card-accent-green rounded-2xl p-8 hover-lift transition-all duration-500 group feature-card opacity-0 animate-fade-in hover:shadow-[0_0_30px_rgba(16,185,129,0.1)]">
              <div className="w-12 h-12 bg-emerald-500/15 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-emerald-500/25 transition-all duration-300">
                <WebIdeIcon className="w-8 h-8 text-emerald-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3 group-hover:text-emerald-400 transition-colors duration-300">
                Web IDE
              </h3>
              <p className="text-black dark:text-gray-400 mb-4 group-hover:text-gray-300 transition-colors duration-300 text-sm leading-relaxed">
                Professional code editor with syntax highlighting, IntelliSense,
                and live preview for quantum circuit development and debugging.
              </p>
              <Link
                href="/app"
                className="flex items-center text-sm text-emerald-400 group-hover:text-emerald-300 transition-colors duration-300 font-medium"
                aria-label="Open the QCanvas quantum Web IDE"
              >
                <span>Open editor</span>
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-2 transition-transform duration-300" />
              </Link>
            </div>

            {/* Feature 5 */}
            <div className="quantum-glass-dark card-accent-orange rounded-2xl p-8 hover-lift transition-all duration-500 group feature-card opacity-0 animate-fade-in hover:shadow-[0_0_30px_rgba(245,158,11,0.1)]">
              <div className="w-12 h-12 bg-amber-500/15 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-amber-500/25 transition-all duration-300">
                <Users className="w-6 h-6 text-amber-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3 group-hover:text-amber-400 transition-colors duration-300">
                Community Sharing
              </h3>
              <p className="text-black dark:text-gray-400 mb-4 group-hover:text-gray-300 transition-colors duration-300 text-sm leading-relaxed">
                Share your quantum circuits with the community through
                GitHub-style repositories, collaboration tools, and public
                circuit galleries.
              </p>
              <Link
                href="/about"
                className="flex items-center text-sm text-amber-400 group-hover:text-amber-300 transition-colors duration-300 font-medium"
                aria-label="Learn about the QCanvas community"
              >
                <span>Join community</span>
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-2 transition-transform duration-300" />
              </Link>
            </div>

            {/* Feature 6 */}
            <div className="quantum-glass-dark card-accent-pink rounded-2xl p-8 hover-lift transition-all duration-500 group feature-card opacity-0 animate-fade-in hover:shadow-[0_0_30px_rgba(236,72,153,0.1)]">
              <div className="w-12 h-12 bg-pink-500/15 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-pink-500/25 transition-all duration-300">
                <Globe className="w-6 h-6 text-pink-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3 group-hover:text-pink-400 transition-colors duration-300">
                OpenQASM 3.0
              </h3>
              <p className="text-black dark:text-gray-400 mb-4 group-hover:text-gray-300 transition-colors duration-300 text-sm leading-relaxed">
                Full support for OpenQASM 3.0 standard with advanced features,
                validation, and compatibility across all major quantum
                platforms.
              </p>
              <a
                href="https://openqasm.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center text-sm text-pink-400 group-hover:text-pink-300 transition-colors duration-300 font-medium"
                aria-label="View OpenQASM 3.0 standard specification"
              >
                <span>View standard</span>
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-2 transition-transform duration-300" />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Examples Preview */}
      <section className="py-24 px-4 relative">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              <span className="quantum-gradient bg-clip-text text-transparent">
                Real-Time OpenQASM 3.0 Simulation
              </span>
            </h2>
            <p className="text-lg text-black dark:text-gray-400 max-w-2xl mx-auto mb-8">
              Explore quantum computing through hands-on examples in Cirq, Qiskit,
              and PennyLane — converted and simulated live via OpenQASM 3.0
            </p>
            <Link
              href="/examples"
              className="btn-quantum inline-flex items-center group"
            >
              <CodeSquareSvgRepo className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform duration-300 relative z-10" />
              <span className="relative z-10">View All Examples</span>
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Example 1 */}
            <div
              onClick={() => handleTryExample(getExampleCode("bell-state"))}
              className="quantum-glass-dark rounded-2xl p-6 hover-lift transition-all duration-500 group cursor-pointer feature-card opacity-0 animate-fade-in"
            >
              <div className="w-full h-32 bg-gradient-to-br from-indigo-500/20 via-indigo-400/10 to-violet-500/20 rounded-xl mb-4 flex items-center justify-center group-hover:scale-[1.02] transition-transform duration-300 border border-indigo-500/10 overflow-hidden relative">
                <div className="relative w-full h-full p-2">
                  <Image src="/icons/Circuit-Diagrams/bell.svg" alt="Bell State Circuit Diagram" fill className="object-contain group-hover:scale-110 transition-transform duration-300 drop-shadow-md opacity-90 group-hover:opacity-100 p-2" />
                </div>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-indigo-400 transition-colors duration-300">
                Bell State (Cirq)
              </h3>
              <p className="text-black dark:text-gray-400 text-sm mb-4 group-hover:text-gray-300 transition-colors duration-300">
                Create quantum entanglement with H + CNOT gates. Expect 50% |00⟩
                and 50% |11⟩
              </p>
              <div className="flex items-center justify-between">
                <span className="text-xs bg-indigo-500/15 text-indigo-300 px-3 py-1 rounded-full border border-indigo-500/20">
                  Beginner
                </span>
                <ArrowRight className="w-4 h-4 text-indigo-400 group-hover:translate-x-2 transition-transform duration-300" />
              </div>
            </div>

            {/* Example 2 */}
            <div
              onClick={() =>
                handleTryExample(getExampleCode("quantum-teleportation"))
              }
              className="quantum-glass-dark rounded-2xl p-6 hover-lift transition-all duration-500 group cursor-pointer feature-card opacity-0 animate-fade-in"
            >
              <div className="w-full h-32 bg-gradient-to-br from-violet-500/20 via-purple-400/10 to-pink-500/20 rounded-xl mb-4 flex items-center justify-center group-hover:scale-[1.02] transition-transform duration-300 border border-violet-500/10 overflow-hidden relative">
                <div className="relative w-full h-full p-2">
                  <Image src="/icons/Circuit-Diagrams/teleportation.svg" alt="Quantum Teleportation Circuit Diagram" fill className="object-contain group-hover:scale-110 transition-transform duration-300 drop-shadow-md opacity-90 group-hover:opacity-100 p-2" />
                </div>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-violet-400 transition-colors duration-300">
                Teleportation (Qiskit)
              </h3>
              <p className="text-black dark:text-gray-400 text-sm mb-4 group-hover:text-gray-300 transition-colors duration-300">
                Transfer quantum states using entanglement with Bell measurement
                and classical corrections
              </p>
              <div className="flex items-center justify-between">
                <span className="text-xs bg-violet-500/15 text-violet-300 px-3 py-1 rounded-full border border-violet-500/20">
                  Intermediate
                </span>
                <ArrowRight className="w-4 h-4 text-violet-400 group-hover:translate-x-2 transition-transform duration-300" />
              </div>
            </div>

            {/* Example 3 */}
            <div
              onClick={() => handleTryExample(getExampleCode("grovers-search"))}
              className="quantum-glass-dark rounded-2xl p-6 hover-lift transition-all duration-500 group cursor-pointer feature-card opacity-0 animate-fade-in"
            >
              <div className="w-full h-32 bg-gradient-to-br from-cyan-500/20 via-teal-400/10 to-emerald-500/20 rounded-xl mb-4 flex items-center justify-center group-hover:scale-[1.02] transition-transform duration-300 border border-cyan-500/10 overflow-hidden relative">
                <div className="relative w-full h-full p-2">
                  <Image src="/icons/Circuit-Diagrams/grover.svg" alt="Grover's Search Circuit Diagram" fill className="object-contain group-hover:scale-110 transition-transform duration-300 drop-shadow-md opacity-90 group-hover:opacity-100 p-2" />
                </div>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-cyan-400 transition-colors duration-300">
                Grover&apos;s Search (PennyLane)
              </h3>
              <p className="text-black dark:text-gray-400 text-sm mb-4 group-hover:text-gray-300 transition-colors duration-300">
                Quantum search algorithm with oracle and diffusion operator for
                quadratic speedup
              </p>
              <div className="flex items-center justify-between">
                <span className="text-xs bg-cyan-500/15 text-cyan-300 px-3 py-1 rounded-full border border-cyan-500/20">
                  Advanced
                </span>
                <ArrowRight className="w-4 h-4 text-cyan-400 group-hover:translate-x-2 transition-transform duration-300" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Explore Features Card Grid — boosts internal links for SEO */}
      <FeatureGrid />

      {/* CTA Section */}
      <section className="py-24 px-4 relative overflow-hidden">
        {/* Radial glow behind heading */}
        <div className="absolute inset-0">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-indigo-500 opacity-[0.06] rounded-full blur-[100px]"></div>
        </div>

        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-10 left-[15%] animate-float">
            <Star className="w-5 h-5 text-indigo-400 opacity-20" />
          </div>
          <div
            className="absolute bottom-10 right-[15%] animate-float-reverse"
            style={{ animationDelay: "1.5s" }}
          >
            <Sparkles className="w-4 h-4 text-violet-400 opacity-25" />
          </div>
        </div>

        <div className="max-w-4xl mx-auto text-center relative z-10">
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            <span className="quantum-gradient bg-clip-text text-transparent">
              Start Simulating Quantum Circuits
            </span>
            <br />
            <span className="text-white">Across Every Framework</span>
          </h2>
          <p className="text-lg text-black dark:text-gray-400 mb-10 max-w-2xl mx-auto">
            Join thousands of researchers, students, and developers building the
            future of quantum computing with {config.project.name}.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/login"
              className="btn-quantum text-lg px-8 py-4 flex items-center justify-center group"
            >
              <RocketAnimated className="w-6 h-6 mr-2 group-hover:scale-110 transition-transform duration-300 relative z-10" />
              <span className="relative z-10">Launch QCanvas</span>
            </Link>
            <Link
              href="/docs"
              className="btn-ghost text-lg px-8 py-4 flex items-center justify-center group"
            >
              <Book className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform duration-300" />
              <span>Read Documentation</span>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-4 relative">
        <div className="gradient-divider mb-12"></div>
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
            <div className="md:col-span-2">
              <Link
                href="/"
                className="flex items-center space-x-2.5 mb-4 group"
              >
                <div className="relative logo-glow">
                  <Image
                    src="/QCanvas-logo-Black.svg"
                    alt="QCanvas Logo"
                    width={36}
                    height={36}
                    className="object-contain block dark:hidden transition-all duration-300 group-hover:scale-110"
                  />
                  <Image
                    src="/QCanvas-logo-White.svg"
                    alt="QCanvas Logo"
                    width={36}
                    height={36}
                    className="object-contain hidden dark:block transition-all duration-300 group-hover:scale-110"
                  />
                </div>
                <span className="text-xl font-bold quantum-gradient bg-clip-text text-transparent">
                  QCanvas
                </span>
              </Link>
              <p className="text-gray-900 dark:text-gray-500 mb-4 max-w-md text-sm leading-relaxed">
                {config.project.description}
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-4 text-sm">
                Platform
              </h4>
              <div className="space-y-2.5">
                {config.footer.platform.map((link) => (
                  <Link
                    key={link.path}
                    href={link.path as any}
                    className="block text-black dark:text-gray-500 hover:text-white transition-colors duration-200 text-sm hover-underline w-fit"
                  >
                    {link.name}
                  </Link>
                ))}
              </div>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-4 text-sm">
                Community
              </h4>
              <div className="space-y-2.5">
                {config.footer.community.map((link) => (
                  <a
                    key={link.name}
                    href={link.name === "GitHub" ? link.url : "#"}
                    title={link.name === "GitHub" ? "" : "Coming Soon"}
                    target={link.name === "GitHub" ? "_blank" : undefined}
                    rel="noopener noreferrer"
                    className={`block text-gray-900 dark:text-gray-500 hover:text-white transition-colors duration-200 text-sm hover-underline w-fit ${link.name !== "GitHub" ? "cursor-not-allowed opacity-60" : ""}`}
                    onClick={(e) => {
                      if (link.name !== "GitHub") e.preventDefault();
                    }}
                  >
                    {link.name}
                  </a>
                ))}
              </div>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-4 text-sm">
                Framework Docs
              </h4>
              <div className="space-y-2.5">
                <a
                  href="https://quantumai.google/cirq"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-gray-900 dark:text-gray-500 hover:text-white transition-colors duration-200 text-sm hover-underline w-fit"
                  aria-label="Google Quantum AI — Cirq official documentation"
                >
                  Google Quantum AI (Cirq)
                </a>
                <a
                  href="https://docs.quantum.ibm.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-gray-900 dark:text-gray-500 hover:text-white transition-colors duration-200 text-sm hover-underline w-fit"
                  aria-label="IBM Quantum — Qiskit official documentation"
                >
                  IBM Quantum (Qiskit)
                </a>
                <a
                  href="https://pennylane.ai/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-gray-900 dark:text-gray-500 hover:text-white transition-colors duration-200 text-sm hover-underline w-fit"
                  aria-label="PennyLane — quantum machine learning framework documentation"
                >
                  PennyLane (Xanadu)
                </a>
                <a
                  href="https://openqasm.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-gray-900 dark:text-gray-500 hover:text-white transition-colors duration-200 text-sm hover-underline w-fit"
                  aria-label="OpenQASM 3.0 specification"
                >
                  OpenQASM 3.0
                </a>
              </div>
            </div>
          </div>

          <div className="gradient-divider mb-8"></div>
          <div className="flex flex-col md:flex-row justify-between items-center">
            <p className="text-black dark:text-gray-600 text-sm">
              {getCopyrightText()}
            </p>
            <div className="flex items-center space-x-6 mt-4 md:mt-0">
              <button
                className="text-black dark:text-gray-600 hover:text-gray-400 transition-colors duration-200 text-sm cursor-not-allowed"
                title="Coming Soon"
              >
                Privacy
              </button>
              <button
                className="text-black dark:text-gray-600 hover:text-gray-400 transition-colors duration-200 text-sm cursor-not-allowed"
                title="Coming Soon"
              >
                Terms
              </button>
              <Link
                href="/about"
                className="text-black dark:text-gray-600 hover:text-indigo-400 transition-colors duration-200 text-sm"
              >
                Contact
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
