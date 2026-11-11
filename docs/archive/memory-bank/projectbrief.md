# QCanvas Project Brief

## Project Vision
QCanvas is a Quantum Unified Simulator - a comprehensive platform that bridges the gap between different quantum computing frameworks, providing a unified interface for circuit conversion, simulation, and visualization.

> Authoritative scope: see `docs/project-scope.md` for the latest official scope and exclusions.

## Core Requirements

### Primary Goals
1. **OpenQASM 3.0 Compilation**: Convert Cirq, Qiskit, and PennyLane code to OpenQASM 3.0 format
2. **Web Platform**: Provide a web-based IDE for quantum circuit editing and OpenQASM 3.0 generation
3. **Educational Platform**: Create an accessible learning environment for quantum computing
4. **Production Ready**: Build a scalable, monitored, and secure platform

### Key Features
- OpenQASM 3.0 code generation from Cirq, Qiskit, and PennyLane
- Web-based IDE with syntax highlighting for quantum frameworks
- OpenQASM 3.0 output validation and formatting
- Real-time code conversion and preview
- Educational examples and tutorials
- Comprehensive API with automatic documentation
- Docker-based deployment with monitoring

### Target Users
- **Researchers**: Comparing algorithms across frameworks
- **Students**: Learning quantum computing concepts
- **Developers**: Building quantum applications
- **Educators**: Teaching quantum computing principles

## Technical Scope

### Architecture
- **Two Pillars (Hybrid CPU–QPU)**: QCanvas orchestrates compilation/validation/scheduling; QSim executes circuits on simulation backends
- **Hybrid Approach**: Next.js frontend + FastAPI backend
- **Shared TypeScript Types**: Type safety across services
- **OpenQASM 3.0**: Universal intermediate representation
- **Microservices**: Modular quantum processing components

### Supported Frameworks
- **Cirq** (Google): Near-term quantum devices
- **Qiskit** (IBM): Comprehensive quantum computing
- **PennyLane** (Xanadu): Quantum machine learning

### Simulation Backends (QSim)
- Statevector: Exact quantum state simulation
- Density Matrix: Mixed states and noise handling
- Stabilizer: Efficient Clifford circuit simulation
- Intelligent caching of identical jobs; future pluggable QPU endpoints behind same API contract

## Success Criteria
1. Successful conversion between all supported frameworks
2. Real-time simulation with <5 second response time
3. Comprehensive test coverage (>80%)
4. Production deployment with monitoring
5. User-friendly interface for quantum computing beginners

## Constraints
- Must support OpenQASM 3.0 standard
- Must be educational and accessible
- Must handle quantum computing complexity gracefully
- Must be deployable in containerized environments
- Must maintain type safety across the entire stack

## Project Boundaries
- Focus on circuit conversion and simulation (not quantum hardware)
- Support for 3 major frameworks initially
- Web-based interface (no mobile app initially)
- Educational and development focus (simulation-first; no hardware integration)
- Explicitly excluded: Pulse-level/OpenPulse, hardware-specific extensions, extern functions, memory mgmt, QEC, circuit timing features (delay, duration, box).
