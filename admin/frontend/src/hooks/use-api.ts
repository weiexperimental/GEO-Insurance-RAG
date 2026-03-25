// In production (behind Caddy proxy), use relative paths.
// In development, fall back to localhost:8080.
const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

export async function api<T = any>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!resp.ok) throw new Error(`API error: ${resp.status}`)
  return resp.json()
}
