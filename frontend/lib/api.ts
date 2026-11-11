import { File, ApiResponse, CreateFileRequest, UpdateFileRequest, ExplorerTree } from '@/types'
import { handleSessionExpired } from './authStore'

// =============================================================================
// API BASE CONFIGURATION
// =============================================================================
// Backend counterpart: config/config.py -> DISABLE_REMOTE_API_FALLBACK
// Keep these in sync manually.
//
// When DISABLE_REMOTE_FALLBACK is true:
//   - Only use the local backend (http://127.0.0.1:8000)
//   - Do NOT fall back to Railway/production URL
// When false:
//   - Fall back to NEXT_PUBLIC_API_BASE/Railway when local is unavailable

const DISABLE_REMOTE_FALLBACK =
  process.env.NEXT_PUBLIC_DISABLE_REMOTE_FALLBACK === 'true'

// let cachedApiBase: string | null = null

// async function getApiBase(): Promise<string> {
//   if (cachedApiBase) return cachedApiBase

//   const localUrl = 'http://127.0.0.1:8000'
//   const railwayUrl = process.env.NEXT_PUBLIC_API_BASE || 'https://qcanvas-nextjs-production.up.railway.app'

//   // Always prefer local when available
//   try {
//     const response = await fetch(`${localUrl}/api/health`, { method: 'GET' })
//     if (response.ok) {
//       cachedApiBase = localUrl
//       console.log('[API] Using local backend:', localUrl)
//       return localUrl
//     }
//   } catch (error) {
//     console.log('[API] Local backend not reachable')
//   }

//   // If remote fallback is disabled, always return local URL
//   if (DISABLE_REMOTE_FALLBACK) {
//     cachedApiBase = localUrl
//     console.warn('[API] Remote fallback disabled, forcing local backend even if unreachable')
//     return localUrl
//   }

// let cachedApiBase: string | null = null
// async function getApiBase(): Promise<string> {
//   if (cachedApiBase) return cachedApiBase

//   // 1. The Local URL
//   const localUrl = 'http://127.0.0.1:8000'

//   // 2. The Production URL (from Amplify Environment Variables)
//   // If the variable isn't set, fallback to your hardcoded AWS URL just in case
//   const productionUrl = process.env.NEXT_PUBLIC_API_BASE || 'https://api.qcanvas.codes'

//   // If we are explicitly forcing local mode (like during local development)
//   if (DISABLE_REMOTE_FALLBACK) {
//     cachedApiBase = localUrl
//     console.warn('[API] Remote fallback disabled, forcing local backend')
//     return localUrl
//   }

//   // Determine if we should use local or production
//   try {
//     // Only try to ping localhost if we are NOT explicitly running in production
//     if (process.env.NODE_ENV !== 'production') {
//       const response = await fetch(`${localUrl}/api/health`, { method: 'GET' })
//       if (response.ok) {
//         cachedApiBase = localUrl
//         console.log('[API] Using local backend:', localUrl)
//         return localUrl
//       }
//     }
//   } catch (error) {
//     console.log('[API] Local backend not reachable or running in production')
//   }

//   // If local fails or we are in production, use the AWS URL
//   cachedApiBase = productionUrl
//   console.log('[API] Using remote backend:', productionUrl)
//   return productionUrl
// }

let cachedApiBase: string | null = null

export async function getApiBase(): Promise<string> {
  if (cachedApiBase) return cachedApiBase

  // 1. Browser-side detection (Foolproof against bad ENV variables)
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname

    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      // We are visiting the website via localhost:3000 -> use local backend
      cachedApiBase = 'http://127.0.0.1:8000'
      console.log('[API] Local UI detected: Using local backend:', cachedApiBase)
      return cachedApiBase
    } else {
      // We are visiting from qcanvas.codes -> use live backend!
      let apiUrl = process.env.NEXT_PUBLIC_API_BASE || 'https://api.qcanvas.codes'
      // Safety net 1: ignore accidental localhost references baked into production builds
      if (apiUrl.includes('127.0.0.1') || apiUrl.includes('localhost')) {
        apiUrl = 'https://api.qcanvas.codes'
      }
      // Safety net 2: Prevent Mixed Content errors by forcing HTTPS if the frontend is HTTPS
      if (window.location.protocol === 'https:' && apiUrl.startsWith('http://')) {
        apiUrl = apiUrl.replace('http://', 'https://')
      }

      cachedApiBase = apiUrl
      console.log('[API] Remote UI detected: Using remote backend:', cachedApiBase)
      return cachedApiBase
    }
  }

  // 2. Server-Side Rendering (SSR) Fallback logic
  if (process.env.NODE_ENV === 'production') {
    let apiUrl = process.env.NEXT_PUBLIC_API_BASE || 'https://api.qcanvas.codes'
    if (apiUrl.includes('127.0.0.1') || apiUrl.includes('localhost')) {
      apiUrl = 'https://api.qcanvas.codes'
    }
    cachedApiBase = apiUrl
    return cachedApiBase
  }

  cachedApiBase = 'http://127.0.0.1:8000'
  return cachedApiBase
}

// Remote fallback enabled: use Railway/production URL
// cachedApiBase = railwayUrl
// console.log('[API] Falling back to remote backend:', railwayUrl)
// return railwayUrl
// }

function hasBearerToken(headers: HeadersInit | undefined): boolean {
  if (!headers) return false
  if (headers instanceof Headers) {
    return (headers.get('Authorization') ?? '').startsWith('Bearer ')
  }
  if (Array.isArray(headers)) {
    return headers.some(([k, v]) => k.toLowerCase() === 'authorization' && v.startsWith('Bearer '))
  }
  const value = (headers as Record<string, string>)['Authorization'] ?? (headers as Record<string, string>)['authorization']
  return typeof value === 'string' && value.startsWith('Bearer ')
}

// Generic API helper
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const API_BASE = await getApiBase()
    const url = `${API_BASE}${endpoint}`
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    // Many endpoints (especially DELETE) can legitimately return 204 / empty bodies.
    // Parse JSON only when we actually have a JSON body.
    const statusNoContent = response.status === 204
    const contentType = response.headers.get('content-type') ?? ''
    const isJson = contentType.includes('application/json')

    let data: any = undefined
    if (!statusNoContent) {
      const raw = await response.text()
      const hasBody = raw.trim().length > 0
      if (hasBody) {
        if (isJson) {
          try {
            data = JSON.parse(raw)
          } catch {
            if (!response.ok) {
              throw new Error(
                `HTTP error! status: ${response.status} ${response.statusText}`,
              )
            }
            throw new Error('Invalid JSON response')
          }
        } else {
          // Non-JSON body; only treat as error detail when request failed.
          if (!response.ok) {
            throw new Error(raw)
          }
          data = raw
        }
      } else {
        data = undefined
      }
    }

    // A 401 on a request that carried our bearer token means the session is dead
    // (expired, or invalidated by a password reset). Clear it and send the user to
    // login instead of leaving the IDE half-loaded with empty files/projects.
    if (response.status === 401 && hasBearerToken(options.headers)) {
      handleSessionExpired()
    }

    // If response is not ok, check if we have error details in the body
    if (!response.ok) {
      // Check if the response body has error information
      let errorMsg = data?.error || data?.message || `HTTP error! status: ${response.status}`

      if (data?.detail) {
        if (typeof data.detail === 'string') {
          errorMsg = data.detail;
        } else if (Array.isArray(data.detail)) {
          errorMsg = data.detail.map((err: any) => err.msg || JSON.stringify(err)).join(', ')
        } else if (typeof data.detail === 'object') {
          errorMsg = data.detail.msg || data.detail.message || JSON.stringify(data.detail)
        }
      }

      return {
        error: errorMsg,
        success: false,
        data: data, // Include the full response data in case it has useful info
      }
    }

    return { data, success: true }
  } catch (error) {
    console.error('API request failed:', error)
    return {
      error: error instanceof Error ? error.message : 'Unknown error',
      success: false,
    }
  }
}

// File API functions
export const fileApi = {
  // // Get files (root or project specific)
  // async getFiles(projectId?: number, token?: string): Promise<ApiResponse<File[]>> {
  //   const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
  //   const endpoint = projectId ? `/api/files/?project_id=${projectId}` : '/api/files/'
  //   return apiRequest<File[]>(endpoint, { headers })
  // },

  // // Create file
  // async createFile(data: CreateFileRequest, token?: string): Promise<ApiResponse<File>> {
  //   const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
  //   return apiRequest<File>('/api/files', {
  //     method: 'POST',
  //     body: JSON.stringify(data),
  //     headers,
  //   })
  // },

  // Get files (root or project specific)
  async getFiles(projectId?: number, token?: string): Promise<ApiResponse<File[]>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    // ADDED SLASH AFTER files/
    const endpoint = projectId ? `/api/files/?project_id=${projectId}` : '/api/files/'
    return apiRequest<File[]>(endpoint, { headers })
  },

  // Create file
  async createFile(data: CreateFileRequest, token?: string): Promise<ApiResponse<File>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    // ADDED SLASH
    return apiRequest<File>('/api/files/', {
      method: 'POST',
      body: JSON.stringify(data),
      headers,
    })
  },


  // Get specific file
  async getFile(id: number, token?: string): Promise<ApiResponse<File>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<File>(`/api/files/${id}`, { headers })
  },

  // Update file
  async updateFile(id: number, data: Partial<UpdateFileRequest>, token?: string): Promise<ApiResponse<File>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<File>(`/api/files/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
      headers,
    })
  },

  // Delete file
  async deleteFile(id: number, token?: string): Promise<ApiResponse<void>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<void>(`/api/files/${id}`, {
      method: 'DELETE',
      headers,
    })
  }
}

// Folders API
export interface CreateFolderRequest {
  name: string
  project_id?: number
  parent_id?: number
}

export interface UpdateFolderRequest {
  name?: string
  parent_id?: number
}

export const foldersApi = {
  async getExplorerTree(projectId?: number, token?: string): Promise<ApiResponse<ExplorerTree>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    const endpoint = projectId ? `/api/folders/tree?project_id=${projectId}` : '/api/folders/tree'
    return apiRequest<ExplorerTree>(endpoint, { headers })
  },

  async createFolder(data: CreateFolderRequest, token?: string): Promise<ApiResponse<any>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest('/api/folders', {
      method: 'POST',
      body: JSON.stringify(data),
      headers,
    })
  },

  async updateFolder(folderId: number, data: UpdateFolderRequest, token?: string): Promise<ApiResponse<any>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest(`/api/folders/${folderId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
      headers,
    })
  },

  async deleteFolder(folderId: number, token?: string): Promise<ApiResponse<void>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<void>(`/api/folders/${folderId}`, {
      method: 'DELETE',
      headers,
    })
  }
}

// Projects API
export interface Project {
  id: number
  user_id: string
  name: string
  description?: string
  is_public: boolean
  files?: File[]
  created_at: string
}

export interface CreateProjectRequest {
  name: string
  description?: string
  is_public?: boolean
}

export const projectsApi = {
  // Get all projects
  async getProjects(token?: string): Promise<ApiResponse<Project[]>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<Project[]>('/api/projects/', { headers })
  },

  // // Get specific project
  // async getProject(id: number, token?: string): Promise<ApiResponse<Project>> {
  //   const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
  //   return apiRequest<Project>(`/api/projects/${id}`, { headers })
  // },

  // Get all projects
  async getProject(token?: string): Promise<ApiResponse<Project[]>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<Project[]>('/api/projects/', { headers }) // Ensure the slash is here
  },

  // Create project
  async createProject(data: CreateProjectRequest, token?: string): Promise<ApiResponse<Project>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<Project>('/api/projects/', {
      method: 'POST',
      body: JSON.stringify(data),
      headers,
    })
  },

  // Add file to project
  async addFile(projectId: number, data: CreateFileRequest, token?: string): Promise<ApiResponse<File>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<File>(`/api/projects/${projectId}/files`, {
      method: 'POST',
      body: JSON.stringify(data),
      headers,
    })
  },

  // Update file content
  async updateFile(projectId: number, fileId: string, data: Partial<CreateFileRequest>, token?: string): Promise<ApiResponse<File>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest<File>(`/api/projects/${projectId}/files/${fileId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
      headers,
    })
  }
}

// Health check
export async function healthCheck(): Promise<ApiResponse<{ ok: boolean }>> {
  return apiRequest<{ ok: boolean }>('/api/health')
}

// Quantum conversion API - connects to FastAPI backend
export const quantumApi = {
  // Convert quantum code to OpenQASM
  async convertToQasm(code: string, framework: string, style: 'classic' | 'compact' = 'classic', token?: string): Promise<ApiResponse<any>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest('/api/converter/convert', {
      method: 'POST',
      body: JSON.stringify({
        code,
        framework,
        qasm_version: '3.0',
        style,
      }),
      headers,
    })
  },

  // Validate quantum code syntax
  async validateCode(code: string, framework: string): Promise<ApiResponse<any>> {
    return apiRequest('/api/converter/validate', {
      method: 'POST',
      body: JSON.stringify({
        code,
        framework,
      }),
    })
  },

  // Get supported frameworks
  async getSupportedFrameworks(): Promise<ApiResponse<string[]>> {
    return apiRequest('/api/converter/frameworks')
  },

  // Execute quantum code (legacy - for frontend server)
  async executeCode(code: string, framework: string, shots = 1024): Promise<ApiResponse<any>> {
    return apiRequest('/api/quantum/execute', {
      method: 'POST',
      body: JSON.stringify({
        code,
        framework,
        shots,
        backend: 'qasm_simulator',
      }),
    })
  },

  // Execute OpenQASM code via FastAPI backend (legacy)
  async executeQasm(qasm_code: string, backend = 'statevector', shots = 1024, token?: string): Promise<ApiResponse<any>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest('/api/simulator/execute', {
      method: 'POST',
      body: JSON.stringify({
        qasm_code,
        backend,
        shots,
      }),
      headers,
    })
  },

  // Execute OpenQASM code with QSim backend
  // Execute OpenQASM code with QSim backend
  async executeQasmWithQSim(
    qasm_code: string, 
    backend: 'cirq' | 'qiskit' | 'pennylane' = 'cirq', 
    shots = 1024, 
    token?: string, 
    algorithm_hint?: string,
    input_framework?: string
  ): Promise<ApiResponse<any>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest('/api/simulator/execute-qsim', {
      method: 'POST',
      body: JSON.stringify({
        qasm_input: qasm_code,
        backend,
        shots,
        ...(algorithm_hint ? { algorithm_hint } : {}),
        ...(input_framework ? { input_framework } : {}),
      }),
      headers,
    })
  },


  // Get available backends
  async getAvailableBackends(): Promise<ApiResponse<any>> {
    return apiRequest('/api/simulator/backends')
  },

  // Execute hybrid Python code with qcanvas/qsim
  async executeHybrid(
    code: string,
    framework?: string,
    timeout?: number,
    token?: string
  ): Promise<ApiResponse<HybridExecuteResult>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest('/api/hybrid/execute', {
      method: 'POST',
      body: JSON.stringify({
        code,
        framework,
        timeout: timeout ?? 180,
      }),
      headers,
    })
  },

  // Validate hybrid code without executing
  async validateHybrid(code: string, token?: string): Promise<ApiResponse<HybridValidateResult>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest('/api/hybrid/validate', {
      method: 'POST',
      body: JSON.stringify({ code }),
      headers,
    })
  },

  // Get hybrid execution status/configuration
  async getHybridStatus(token?: string): Promise<ApiResponse<HybridStatusResult>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest('/api/hybrid/status', { headers })
  },
}

// Hybrid execution result types
export interface HybridExecuteResult {
  success: boolean
  stdout: string
  stderr: string
  qasm_generated?: string | null
  simulation_results: HybridSimulationResult[]
  execution_time: string
  error?: string | null
  error_line?: number | null
  error_type?: string | null
}

export interface HybridSimulationResult {
  counts: { [state: string]: number }
  probabilities: { [state: string]: number }
  shots: number
  backend: string
  execution_time: string
  n_qubits: number
  metadata: { [key: string]: any }
}

export interface HybridValidateResult {
  valid: boolean
  errors?: string[] | null
  warnings?: string[] | null
}

export interface HybridStatusResult {
  enabled: boolean
  sandbox_available: boolean
  security_settings: {
    block_dangerous_imports: boolean
    block_file_access: boolean
    block_network: boolean
    block_shell: boolean
    restrict_builtins: boolean
    block_code_execution: boolean
  }
  limits: {
    max_execution_time: number
    max_memory_mb: number
    max_simulation_runs: number
  }
  allowed_modules: string[]
}

// Auth API types
export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
  full_name: string
}

export interface RegisterResponse {
  verification_required: boolean
  message: string
  access_token?: string
  token_type?: string
  user: {
    id: string
    email: string
    username: string
    full_name: string
    role: 'user' | 'admin' | 'demo'
    is_active: boolean
    is_verified: boolean
    created_at: string
    last_login_at: string | null
    bio?: string
  }
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: {
    id: string
    email: string
    username: string
    full_name: string
    role: 'user' | 'admin' | 'demo'
    is_active: boolean
    is_verified: boolean
    created_at: string
    last_login_at: string | null
  }
}

export interface OtpSendResponse {
  message: string
  cooldown_seconds: number
  expires_in_seconds: number
  attempts_remaining: number
  verification_required: boolean
}

export interface OtpVerifyResponse {
  message: string
  verified: boolean
  access_token?: string
  token_type?: string
  user?: AuthResponse['user']
  reset_token?: string
  expires_in_seconds?: number
}

export interface AdminApprovalRequest {
  token: string
}

// Auth API
export const authApi = {
  async login(email: string, password: string): Promise<ApiResponse<AuthResponse>> {
    return apiRequest<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  async register(data: RegisterRequest): Promise<ApiResponse<RegisterResponse>> {
    return apiRequest<RegisterResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async registerAdmin(data: RegisterRequest): Promise<ApiResponse<RegisterResponse>> {
    return apiRequest<RegisterResponse>('/api/auth/admin/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async approveAdmin(token: string): Promise<ApiResponse<{ message: string }>> {
    return apiRequest<{ message: string }>('/api/auth/admin/approve', {
      method: 'POST',
      body: JSON.stringify({ token }),
    })
  },

  async sendSignupOtp(email: string): Promise<ApiResponse<OtpSendResponse>> {
    return apiRequest<OtpSendResponse>('/api/auth/signup/otp/send', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
  },

  async resendSignupOtp(email: string): Promise<ApiResponse<OtpSendResponse>> {
    return apiRequest<OtpSendResponse>('/api/auth/signup/otp/resend', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
  },

  async verifySignupOtp(email: string, otp: string): Promise<ApiResponse<OtpVerifyResponse>> {
    return apiRequest<OtpVerifyResponse>('/api/auth/signup/otp/verify', {
      method: 'POST',
      body: JSON.stringify({ email, otp }),
    })
  },

  async sendPasswordResetOtp(email: string): Promise<ApiResponse<{ message: string }>> {
    return apiRequest<{ message: string }>('/api/auth/password-reset/otp/send', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
  },

  async verifyPasswordResetOtp(email: string, otp: string): Promise<ApiResponse<OtpVerifyResponse>> {
    return apiRequest<OtpVerifyResponse>('/api/auth/password-reset/otp/verify', {
      method: 'POST',
      body: JSON.stringify({ email, otp }),
    })
  },

  async completePasswordReset(
    reset_token: string,
    new_password: string,
    confirm_password: string,
  ): Promise<ApiResponse<{ message: string }>> {
    return apiRequest<{ message: string }>('/api/auth/password-reset/complete', {
      method: 'POST',
      body: JSON.stringify({ reset_token, new_password, confirm_password }),
    })
  },

  async getCurrentUser(token: string): Promise<ApiResponse<AuthResponse['user']>> {
    return apiRequest<AuthResponse['user']>('/api/auth/me', {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
  },

  /** "Try demo": creates a private, temporary guest workspace for this visitor. */
  async guestLogin(): Promise<ApiResponse<AuthResponse>> {
    return apiRequest<AuthResponse>('/api/auth/guest', {
      method: 'POST',
    })
  },

  async refreshToken(token: string): Promise<ApiResponse<AuthResponse>> {
    return apiRequest<AuthResponse>('/api/auth/refresh', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
  },

  async logout(token?: string): Promise<ApiResponse<{ message: string }>> {
    return apiRequest<{ message: string }>('/api/auth/logout', {
      method: 'POST',
      keepalive: true, // survive the page navigation that follows logout
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    })
  },

  async updateProfile(
    data: { full_name?: string; username?: string; bio?: string },
    token: string
  ): Promise<ApiResponse<AuthResponse['user'] & { bio?: string }>> {
    return apiRequest<AuthResponse['user'] & { bio?: string }>('/api/auth/me', {
      method: 'PUT',
      body: JSON.stringify(data),
      headers: { 'Authorization': `Bearer ${token}` },
    })
  },
}

// Gamification API
export const gamificationApi = {
  // Get user stats
  async getStats(token: string): Promise<ApiResponse<any>> {
    const headers = { 'Authorization': `Bearer ${token}` };
    return apiRequest('/api/gamification/stats', { headers });
  },

  // Get recent activities
  async getRecentActivities(token: string, limit = 10): Promise<ApiResponse<any>> {
    const headers = { 'Authorization': `Bearer ${token}` };
    return apiRequest(`/api/gamification/activities/recent?limit=${limit}`, { headers });
  },

  // Get activity summary
  async getActivitySummary(token: string): Promise<ApiResponse<any>> {
    const headers = { 'Authorization': `Bearer ${token}` };
    return apiRequest('/api/gamification/activities/summary', { headers });
  },

  // Get all achievements with user progress
  async getAchievements(token: string): Promise<ApiResponse<any>> {
    const headers = { 'Authorization': `Bearer ${token}` };
    return apiRequest('/api/gamification/achievements', { headers });
  },

  // Get only unlocked achievements
  async getUnlockedAchievements(token: string): Promise<ApiResponse<any>> {
    const headers = { 'Authorization': `Bearer ${token}` };
    return apiRequest('/api/gamification/achievements/unlocked', { headers });
  },

  // Manually trigger achievement check
  async checkAchievements(token: string): Promise<ApiResponse<any>> {
    const headers = { 'Authorization': `Bearer ${token}` };
    return apiRequest('/api/gamification/achievements/check', { method: 'POST', headers });
  }
}

// Shared Snippets API
export const sharedApi = {
  // Get all shared snippets
  async getSharedSnippets(): Promise<ApiResponse<any>> {
    return apiRequest('/api/shared/', {
      method: 'GET',
    })
  },

  // Create a new shared snippet
  async createSharedSnippet(data: any, token?: string): Promise<ApiResponse<any>> {
    const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {}
    return apiRequest('/api/shared/', {
      method: 'POST',
      body: JSON.stringify(data),
      headers,
    })
  }
}
