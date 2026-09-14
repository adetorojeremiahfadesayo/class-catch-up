export type Role = 'teacher' | 'student'
export type Session = { user_id: string; display_name: string; role: Role; csrf_token: string }

let csrf = ''

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (csrf) headers.set('X-CSRF-Token', csrf)
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers, credentials: 'include' })
  } catch {
    throw new Error('The local service is unavailable. Start the API and try again.')
  }
  if (!response.ok) {
    if (response.status >= 500) throw new Error('The local service is unavailable. Try again in a moment.')
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function enterDemo(role: Role) {
  const session = await request<Session>(`/auth/demo/${role}`, { method: 'POST' })
  csrf = session.csrf_token
  return session
}
