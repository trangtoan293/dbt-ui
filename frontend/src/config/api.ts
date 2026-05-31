export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export function apiUrl(endpoint: string): string {
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  return `${API_BASE_URL}${normalizedEndpoint}`
}

export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, { credentials: 'include', ...init })
}

export interface Workspace {
  id: string
  name: string
  adapter: string
  created_at: string
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const r = await apiFetch(apiUrl('/api/workspace/list'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!r.ok) throw new Error('Failed to list workspaces')
  return r.json()
}

export async function createWorkspace(name: string, adapter: string): Promise<Workspace> {
  const r = await apiFetch(apiUrl('/api/workspace/create'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, adapter }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw new Error(data.detail || 'Failed to create workspace')
  }
  return r.json()
}

export async function deleteWorkspace(id: string): Promise<void> {
  const r = await apiFetch(apiUrl('/api/workspace/delete'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  })
  if (!r.ok) throw new Error('Failed to delete workspace')
}

export async function getWorkspace(
  id: string
): Promise<{ id: string, name: string, adapter: string, connections: Record<string, Record<string, unknown>> }> {
  const r = await apiFetch(apiUrl('/api/workspace/get'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  })
  if (!r.ok) throw new Error('Failed to load workspace')
  return r.json()
}

export async function openWorkspace(id: string): Promise<{ path: string, name: string }> {
  const r = await apiFetch(apiUrl('/api/workspace/open'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  })
  if (!r.ok) throw new Error('Failed to open workspace')
  return r.json()
}

export async function updateWorkspaceConnections(
  id: string,
  connections: Record<string, unknown>
): Promise<void> {
  const r = await apiFetch(apiUrl('/api/workspace/update-connections'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, connections }),
  })
  if (!r.ok) throw new Error('Failed to update connections')
}
