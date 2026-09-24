import type { ProfileIntelligenceRequest, ProfileIntelligenceResponse } from './types'

export class ApiError extends Error {
  public readonly kind: 'domain' | 'validation' | 'server' | 'network' | 'unexpected'
  public readonly code?: string

  constructor(
    kind: 'domain' | 'validation' | 'server' | 'network' | 'unexpected',
    message: string,
    code?: string,
  ) { super(message); this.kind = kind; this.code = code }
}

const baseUrl = import.meta.env.VITE_FITADAPT_API_URL || 'http://127.0.0.1:8000'

function isErrorPayload(value: unknown): value is { error: { code?: string; message?: string } } {
  return typeof value === 'object' && value !== null && 'error' in value
}

async function post<T>(path: string, body: object): Promise<T> {
  let response: Response
  try { response = await fetch(`${baseUrl}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) }
  catch { throw new ApiError('network', 'Cannot reach the FitAdapt API. Start the local server and retry.') }
  let data: unknown
  try { data = await response.json() } catch { throw new ApiError('unexpected', 'API returned an unreadable response.') }
  if (!response.ok) {
    const message = isErrorPayload(data) ? data.error.message : undefined
    const code = isErrorPayload(data) ? data.error.code : undefined
    if (response.status === 400) throw new ApiError('domain', message || 'FitAdapt rejected this request.', code)
    if (response.status === 422) throw new ApiError('validation', 'Check the highlighted input values.')
    if (response.status === 500) throw new ApiError('server', 'FitAdapt encountered an unexpected server error.')
    throw new ApiError('unexpected', 'The API returned an unexpected response.')
  }
  return data as T
}

export function getProfileIntelligence(request: ProfileIntelligenceRequest): Promise<ProfileIntelligenceResponse> {
  return post<ProfileIntelligenceResponse>('/v1/profile-intelligence', request)
}
