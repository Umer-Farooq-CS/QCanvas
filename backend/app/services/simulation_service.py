import sys
import os
import time
import psutil
import re
from typing import Dict, Any, Optional, List
import numpy as np

# Add the project root directory to Python path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
sys.path.insert(0, project_root)

# Import QSim for quantum simulation
try:
    from qsim import run_qasm, RunArgs, SimResult
    print("[OK] QSim imported successfully")
    QSIM_AVAILABLE = True
except ImportError as e:
    print(f"Import error in simulation service: {e}")
    print("QSim simulation features may not be fully available")
    run_qasm = None
    RunArgs = None
    SimResult = None
    QSIM_AVAILABLE = False

# Import fastqsim for online quantum simulation
try:
    import fastqsim
    FASTQSIM_AVAILABLE = True
    print("✓ FastQSim cloud SDK imported successfully")
except ImportError as e:
    print(f"FastQSim cloud SDK is not available: {e}")
    fastqsim = None
    FASTQSIM_AVAILABLE = False



def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert NumPy types to native Python types for JSON serialization.
    
    Args:
        obj: Object that may contain NumPy types
        
    Returns:
        Object with NumPy types converted to native Python types
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj

class SimulationService:
    """Service for executing quantum simulations using QSim"""
    
    def __init__(self):
        from app.config.settings import settings
        self.settings = settings
        self.available_backends = ['cirq', 'qiskit', 'pennylane']
        self.legacy_backends = ["statevector", "density_matrix"]
        self.fastqsim_client = None
        self.fastqsim_initialized = False

    def _get_api_base(self) -> str:
        return (os.getenv("FASTQUBIT_ENDPOINT") or getattr(self.settings, "FASTQUBIT_ENDPOINT", "https://fastqubit.dev/api")).rstrip("/")

    def _get_integrator_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {os.getenv('FASTQSIM_API_TOKEN') or getattr(self.settings, 'FASTQSIM_API_TOKEN', '')}",
            "X-End-User-Id": os.getenv("FASTQUBIT_USER_ID") or getattr(self.settings, 'FASTQUBIT_USER_ID', ''),
        }
        if extra:
            headers.update(extra)
        return headers

    def _terminate_session(self, session_id: str):
        import requests
        try:
            requests.post(
                f"{self._get_api_base()}/sessions/{session_id}/terminate",
                headers=self._get_integrator_headers(),
                timeout=15,
            )
        except Exception:
            pass

    def _provision_session(self, payload: Optional[Dict[str, Any]] = None):
        import requests
        try:
            resp = requests.post(
                f"{self._get_api_base()}/sessions/start",
                headers=self._get_integrator_headers({"Content-Type": "application/json"}),
                json=payload or {},
                timeout=30,
            )
            body = resp.json() if "application/json" in resp.headers.get("content-type", "") else {"raw": resp.text}
            if resp.status_code >= 400:
                return None, body

            # If session already active, terminate the old one and start fresh
            if isinstance(body, dict) and body.get("already_active") and not body.get("session_token"):
                existing_id = body.get("session_id")
                if existing_id:
                    print(f"Active session {existing_id} found — terminating and restarting...")
                    self._terminate_session(existing_id)
                    resp = requests.post(
                        f"{self._get_api_base()}/sessions/start",
                        headers=self._get_integrator_headers({"Content-Type": "application/json"}),
                        json=payload or {},
                        timeout=30,
                    )
                    body = resp.json() if "application/json" in resp.headers.get("content-type", "") else {"raw": resp.text}
                    if resp.status_code >= 400:
                        return None, body

            tok = body.get("session_token") if isinstance(body, dict) else None
            if tok:
                os.environ["FASTQUBIT_SESSION_TOKEN"] = tok
            return tok, body
        except Exception as e:
            return None, {"error": str(e)}

    def _init_fastqsim_sdk(self) -> tuple[bool, Optional[str]]:
        if not FASTQSIM_AVAILABLE:
            return False, "fastqsim library is not installed."
        
        try:
            try:
                fastqsim.reset()
            except Exception:
                pass
            endpoint = os.getenv("FASTQUBIT_ENDPOINT") or getattr(self.settings, "FASTQUBIT_ENDPOINT", "https://fastqubit.dev/api")
            token = os.getenv("FASTQUBIT_SESSION_TOKEN")
            execution_mode = os.getenv("FASTQSIM_EXECUTION_MODE") or getattr(self.settings, "FASTQSIM_EXECUTION_MODE", "cloud")
            
            # Export to environment for any internal library calls
            os.environ["FASTQUBIT_ENDPOINT"] = endpoint
            os.environ["FASTQSIM_EXECUTION_MODE"] = execution_mode
            
            self.fastqsim_client = fastqsim.init(
                endpoint=endpoint,
                token=token,
                execution_mode=execution_mode
            )
            self.fastqsim_initialized = True
            return True, None
        except Exception as e:
            self.fastqsim_client = None
            self.fastqsim_initialized = False
            return False, str(e)


    def _ensure_fastqsim_session(self, force_refresh: bool = False) -> tuple[bool, Optional[str]]:
        if not force_refresh and self.fastqsim_initialized and self.fastqsim_client:
            return True, None

        existing_tok = os.getenv("FASTQUBIT_SESSION_TOKEN")
        if force_refresh or not existing_tok:
            tok, err_body = self._provision_session()
            if not tok:
                return False, f"Session provisioning failed: {err_body}"
        
        return self._init_fastqsim_sdk()

    
    def execute_qasm(self, qasm_code: str, backend: str = "statevector", shots: int = 1024) -> Dict[str, Any]:
        """
        Execute OpenQASM code using the specified backend (legacy method)
        
        Args:
            qasm_code: OpenQASM 3.0 code to execute
            backend: Backend to use for simulation
            shots: Number of measurement shots
            
        Returns:
            Dictionary containing simulation results
        """
        try:
            # Validate backend
            if backend not in self.legacy_backends:
                return {
                    "success": False,
                    "error": f"Unsupported backend: {backend}. Available: {self.legacy_backends}"
                }
            
            # For now, return a basic simulation result
            if backend == "statevector":
                result = self._simulate_statevector(qasm_code, shots)
            elif backend == "density_matrix":
                result = self._simulate_density_matrix(qasm_code, shots)
            else:
                return {
                    "success": False,
                    "error": f"Backend {backend} not implemented yet"
                }
            
            return {
                "success": True,
                "results": result,
                "backend": backend,
                "shots": shots,
                "qasm_code": qasm_code
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Simulation failed: {str(e)}"
            }
    
    def _get_online_mode(self) -> bool:
        # Ultra-fast short-circuit: if explicitly set in environment, bypass Boto3 entirely!
        val = os.getenv("FASTQSIM_ONLINE_MODE")
        if val:
            return val.lower() in ('true', '1', 'yes')

        # 1. First check if an AWS SSM Parameter exists for instant runtime toggling
        ssm_param_name = os.getenv("SSM_FASTQSIM_ONLINE_MODE_PARAM", "/qcanvas/production/fastqsim_online_mode")
        try:
            import boto3
            # Use short timeouts/retries so local dev doesn't hang if AWS credentials aren't configured
            config = boto3.session.Config(connect_timeout=1, read_timeout=1, retries={'max_attempts': 1})
            ssm = boto3.client('ssm', config=config)
            response = ssm.get_parameter(Name=ssm_param_name, WithDecryption=False)
            val = response['Parameter']['Value'].strip().lower()
            if val in ('true', '1', 'yes'):
                return True
            if val in ('false', '0', 'no'):
                return False
        except Exception:
            # Silently fall through to local settings if SSM parameter isn't found or AWS isn't configured
            pass

        # 2. Fallback to standard environment / settings variable
        return getattr(self.settings, "FASTQSIM_ONLINE_MODE", False)

    def execute_qasm_with_qsim(self, qasm_code: str, backend: str = "cirq", shots: int = 1024) -> Dict[str, Any]:
        """
        Execute OpenQASM code using QSim
        
        Args:
            qasm_code: OpenQASM 3.0 code to execute
            backend: QSim backend to use (cirq, qiskit, or pennylane)
            shots: Number of measurement shots
            
        Returns:
            Dictionary containing simulation results from QSim
        """
        try:
            if not QSIM_AVAILABLE:
                return {
                    "success": False,
                    "error": "QSim is not available. Please ensure it is installed correctly."
                }
            
            # Validate backend
            if backend not in self.available_backends:
                return {
                    "success": False,
                    "error": f"Unsupported QSim backend: {backend}. Available: {self.available_backends}"
                }

            # Normalize common user-input artifacts (markdown fences/BOM/hidden chars)
            # before passing QASM to the parser.
            normalized_qasm = self._sanitize_qasm_input(qasm_code)
            if not normalized_qasm:
                return {
                    "success": False,
                    "error": "QASM input is empty after sanitization."
                }
            if "OPENQASM" not in normalized_qasm.upper():
                return {
                    "success": False,
                    "error": "Invalid OpenQASM input: missing OPENQASM header."
                }
            
            # Choose execution mode: Online Cloud (FastQSim) vs Local (QSim)
            online_enabled = self._get_online_mode()
            if online_enabled:
                print(f"🚀 Running simulation via FASTQSIM ONLINE MODE (Cloud Setup) on backend: '{backend}' with {shots} shots...")
                ok, err = self._ensure_fastqsim_session()
                if not ok:
                    print(f"❌ FastQSim Session error: {err}")
                    return {
                        "success": False,
                        "error": f"Failed to initialize FastQSim Online Session: {err}"
                    }
                
                try:
                    start_time = time.perf_counter()
                    job = self.fastqsim_client.run(
                        circuit=normalized_qasm,
                        backend=backend,
                        shots=shots,
                        asynchronous=False
                    )
                    sim_result = job.result()
                    total_time = time.perf_counter() - start_time
                except Exception as e:
                    if "Session is no longer active" in str(e) or "Authentication failed" in str(e):
                        print("🔄 FastQSim session expired. Provisioning a fresh session token...")
                        ok, err = self._ensure_fastqsim_session(force_refresh=True)
                        if not ok:
                            return {"success": False, "error": f"Failed to refresh FastQSim Session: {err}"}
                        start_time = time.perf_counter()
                        job = self.fastqsim_client.run(
                            circuit=normalized_qasm,
                            backend=backend,
                            shots=shots,
                            asynchronous=False
                        )
                        sim_result = job.result()
                        total_time = time.perf_counter() - start_time
                    else:
                        raise e
                    
                    
                    # Format counts and probabilities
                    counts = sim_result.counts if hasattr(sim_result, 'counts') else {}
                    probs = sim_result.probs if hasattr(sim_result, 'probs') else {}
                    statevector = sim_result.statevector if hasattr(sim_result, 'statevector') else None
                    
                    if not probs and counts:
                        total_shots = sum(counts.values())
                        if total_shots > 0:
                            probs = {state: count / total_shots for state, count in counts.items()}
                    
                    exec_time_sec = getattr(job, 'execution_time_seconds', getattr(sim_result, 'execution_time_seconds', 0.0))
                    cpu_time_sec = getattr(job, 'cpu_seconds_total', 0.0)
                    peak_ram_mb = getattr(job, 'peak_memory_mb', 0.0)
                    billing_cpu = getattr(job, 'billing_cpu_millicore_seconds', 0.0)
                    billing_mem = getattr(job, 'billing_memory_gb_seconds', 0.0)
                    
                    tags = getattr(job, 'tags', {})
                    job_metadata = getattr(job, 'metadata', {})
                    
                    def _iso(val):
                        return val.isoformat() if hasattr(val, 'isoformat') else None
                    
                    if exec_time_sec > 0:
                        exec_time_str = f"{exec_time_sec * 1000:.2f}ms"
                        cpu_pct = min((cpu_time_sec / exec_time_sec) * 100.0, 100.0) if cpu_time_sec > 0 else 0.0
                        cpu_usage_str = f"{cpu_pct:.1f}%"
                    else:
                        exec_time_str = f"{total_time * 1000:.2f}ms"
                        cpu_usage_str = "0.0%"
                    
                    memory_usage_str = f"{peak_ram_mb:.1f}MB" if peak_ram_mb > 0 else "0.10MB"

                    # Format results compatible with QCanvas simulator
                    result_dict = {
                        "counts": counts,
                        "metadata": {
                            "backend": backend,
                            "shots": shots,
                            "n_qubits": len(next(iter(counts.keys()))) if counts else 0,
                            "execution_time": exec_time_str,
                            "simulation_time": exec_time_str,
                            "postprocessing_time": "0.00ms",
                            "memory_usage": memory_usage_str,
                            "cpu_usage": cpu_usage_str,
                            "successful_shots": sum(counts.values()) if counts else 0,
                            "visitor": backend,
                            "fidelity": 100.0,
                            "job_id": job.job_id if hasattr(job, 'job_id') else None,
                            "online": True,
                            "execution_time_seconds": exec_time_sec if exec_time_sec > 0 else total_time,
                            "cpu_seconds_total": cpu_time_sec,
                            "peak_memory_mb": peak_ram_mb if peak_ram_mb > 0 else 0.1,
                            "billing_cpu_millicore_seconds": billing_cpu,
                            "billing_memory_gb_seconds": billing_mem,
                            "tags": tags,
                            "metadata": job_metadata,
                            "queue_enqueued_at": _iso(getattr(job, 'queue_enqueued_at', None)),
                            "execution_started_at": _iso(getattr(job, 'execution_started_at', None)),
                            "execution_finished_at": _iso(getattr(job, 'execution_finished_at', None)),
                            "completed_at": _iso(getattr(job, 'completed_at', None)),
                        },
                        "probs": probs
                    }
                    
                    if statevector:
                        result_dict["statevector"] = [str(c) for c in statevector]
                    
                    result_dict = convert_numpy_types(result_dict)
                    print(f"✅ FastQSim Online job {job.job_id if hasattr(job, 'job_id') else 'N/A'} completed successfully in {total_time * 1000:.2f}ms")
                    
                    return {
                        "success": True,
                        "results": result_dict,
                        "backend": backend,
                        "shots": shots
                    }
                except Exception as online_err:
                    print(f"❌ FastQSim Online execution error: {online_err}")
                    return {
                        "success": False,
                        "error": f"FastQSim Online simulation failed: {str(online_err)}"
                    }

            # Local QSim execution branch
            print(f"💻 Running simulation via LOCAL QSIM MODE (Local Setup) on backend: '{backend}' with {shots} shots...")
            
            # Capture initial memory and CPU stats
            process = psutil.Process()
            initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
            initial_cpu = psutil.cpu_percent(interval=None)
            
            # Create RunArgs for QSim
            args = RunArgs(
                qasm_input=normalized_qasm,
                backend=backend,
                shots=shots
            )
            
            # Execute with QSim and measure time
            start_time = time.perf_counter()
            sim_result: SimResult = run_qasm(args)

            simulation_time = time.perf_counter() - start_time
            
            # Post-processing time measurement
            post_start = time.perf_counter()
            
            # Convert SimResult to dictionary format
            result_dict = {
                "counts": sim_result.counts,
                "metadata": sim_result.metadata,
                "probs": sim_result.probs,
                # Note: circuit object might not be JSON serializable, so we omit it or convert to string
            }
            
            # Convert NumPy types to native Python types for JSON serialization
            result_dict = convert_numpy_types(result_dict)
            
            post_processing_time = time.perf_counter() - post_start
            total_time = simulation_time + post_processing_time
            
            # Capture final memory stats
            final_memory = process.memory_info().rss / (1024 * 1024)  # MB
            memory_used = final_memory - initial_memory
            final_cpu = psutil.cpu_percent(interval=None)
            
            # Calculate successful shots from counts
            successful_shots = sum(result_dict["counts"].values()) if result_dict["counts"] else 0
            
            # Add performance metrics to metadata
            result_dict["metadata"]["execution_time"] = f"{total_time*1000:.2f}ms"
            result_dict["metadata"]["simulation_time"] = f"{simulation_time*1000:.2f}ms"
            result_dict["metadata"]["postprocessing_time"] = f"{post_processing_time*1000:.2f}ms"
            result_dict["metadata"]["memory_usage"] = f"{max(memory_used, 0.1):.2f}MB"
            result_dict["metadata"]["cpu_usage"] = f"{max(final_cpu, initial_cpu):.1f}%"
            result_dict["metadata"]["successful_shots"] = successful_shots
            result_dict["metadata"]["visitor"] = backend  # The visitor used is the backend name
            
            # Calculate fidelity estimate (for simulation, fidelity is 100% unless there are errors)
            # In a real quantum device, this would be calculated differently
            if successful_shots > 0 and shots > 0:
                result_dict["metadata"]["fidelity"] = (successful_shots / shots) * 100.0
            else:
                result_dict["metadata"]["fidelity"] = 100.0 if shots == 0 else 0.0
            
            return {
                "success": True,
                "results": result_dict,
                "backend": backend,
                "shots": shots
            }
            
        except Exception as e:
            # Log the full error for debugging
            import traceback
            error_trace = traceback.format_exc()
            print(f"QSim execution error for backend '{backend}': {e}")
            print(error_trace)
            
            # Return a user-friendly error message
            error_msg = str(e)
            # Extract more specific error if available
            if hasattr(e, '__cause__') and e.__cause__:
                error_msg = str(e.__cause__)
            
            return {
                "success": False,
                "error": f"QSim simulation failed: {error_msg}"
            }

    def _sanitize_qasm_input(self, qasm_code: str) -> str:
        """Remove common formatting artifacts before parser invocation."""
        if not isinstance(qasm_code, str):
            return ""

        # Remove UTF-8 BOM and zero-width spaces that commonly appear in pasted content.
        cleaned = qasm_code.replace("\ufeff", "").replace("\u200b", "").strip()
        if not cleaned:
            return ""

        # Unwrap markdown fences like ```qasm ... ```.
        fence_match = re.search(r"```(?:qasm|openqasm)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        # If extra prose exists before the actual program, keep only from OPENQASM onward.
        header_match = re.search(r"OPENQASM\s+[0-9]+(?:\.[0-9]+)?\s*;", cleaned, flags=re.IGNORECASE)
        if header_match and header_match.start() > 0:
            cleaned = cleaned[header_match.start():].lstrip()

        return cleaned
    
    def _simulate_statevector(self, qasm_code: str, shots: int) -> Dict[str, Any]:
        """Simulate using statevector backend"""
        # Parse QASM to determine number of qubits
        num_qubits = self._extract_qubit_count(qasm_code)
        
        # Basic Bell state simulation result (placeholder)
        if "h q[0]" in qasm_code and "cx q[0], q[1]" in qasm_code:
            # Bell state preparation
            return {
                "statevector": [0.7071, 0, 0, 0.7071],  # |00⟩ + |11⟩
                "probabilities": {"00": 0.5, "11": 0.5},
                "counts": {"00": shots//2, "11": shots//2},
                "num_qubits": num_qubits
            }
        else:
            # Default to |0...0⟩ state
            statevector = [1.0] + [0.0] * (2**num_qubits - 1)
            counts = {"0" * num_qubits: shots}
            return {
                "statevector": statevector,
                "counts": counts,
                "num_qubits": num_qubits
            }
    
    def _simulate_density_matrix(self, qasm_code: str, shots: int) -> Dict[str, Any]:
        """Simulate using density matrix backend"""
        num_qubits = self._extract_qubit_count(qasm_code)
        
        # Basic simulation result (placeholder)
        return {
            "density_matrix": "Complex density matrix representation",
            "counts": {"0" * num_qubits: shots},
            "num_qubits": num_qubits
        }
    
    def _extract_qubit_count(self, qasm_code: str) -> int:
        """Extract number of qubits from QASM code"""
        lines = qasm_code.split('\n')
        for line in lines:
            if 'qubit[' in line:
                # Extract number from qubit[n]
                import re
                match = re.search(r'qubit\[(\d+)\]', line)
                if match:
                    return int(match.group(1))
        return 2  # Default fallback
    
    def get_available_backends(self) -> List[str]:
        """Get list of available simulation backends (QSim backends)"""
        return self.available_backends
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of simulation service"""
        try:
            # Test basic functionality
            backends = self.get_available_backends()
            return {
                "status": "healthy",
                "available_backends": backends,
                "qsim_available": QSIM_AVAILABLE
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
