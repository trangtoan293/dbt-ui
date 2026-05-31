import { useState, useEffect, useCallback } from 'react'
import { apiFetch, apiUrl } from '../../config/api'

interface ConnectionConfig {
  engine: string
  [key: string]: string | number | boolean
}

interface ConnectionPanelProps {
  projectId: string
  userRoles: string[]
}

export default function ConnectionPanel({ projectId, userRoles }: ConnectionPanelProps) {
  const [connections, setConnections] = useState<Record<string, ConnectionConfig>>({})
  const [editJson, setEditJson] = useState('')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; output: string } | null>>({})
  const [testing, setTesting] = useState<Record<string, boolean>>({})
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const asCfg = (v: unknown): ConnectionConfig => v as ConnectionConfig

  const isAdmin = userRoles.includes('admin')
  const isMaintainer = userRoles.includes('maintainer')

  const load = useCallback(async () => {
    try {
      const r = await apiFetch(apiUrl('/api/connections/get'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: projectId }),
      })
      if (r.ok) {
        const data = await r.json()
        setConnections(data.connections || {})
      }
    } catch {}
  }, [projectId])

  useEffect(() => {
    if (projectId) load()
  }, [projectId, load])

  const handleEdit = () => {
    setEditJson(JSON.stringify(connections, null, 2))
    setEditing(true)
    setError('')
  }

  const handleSave = async () => {
    let parsed: Record<string, ConnectionConfig>
    try {
      parsed = JSON.parse(editJson)
    } catch {
      setError('Invalid JSON')
      return
    }
    setSaving(true)
    setError('')
    try {
      const r = await apiFetch(apiUrl('/api/connections/set'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: projectId, connections: parsed }),
      })
      if (r.ok) {
        setEditing(false)
        await load()
      } else {
        const data = await r.json()
        setError(data.detail || 'Save failed')
      }
    } catch (e) {
      setError('Network error')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (target: string) => {
    const isProd = connections[target]?.engine === 'dremio'
    if (isProd && !isMaintainer) {
      setTestResults((prev: Record<string, { ok: boolean; output: string } | null>) => ({ ...prev, [target]: { ok: false, output: 'Requires maintainer role' } }))
      return
    }
    setTesting((prev: Record<string, boolean>) => ({ ...prev, [target]: true }))
    setTestResults((prev: Record<string, { ok: boolean; output: string } | null>) => ({ ...prev, [target]: null }))
    try {
      const r = await apiFetch(apiUrl('/api/connections/test'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: projectId, target }),
      })
      const data = await r.json()
      if (r.ok) {
        setTestResults((prev: Record<string, { ok: boolean; output: string } | null>) => ({ ...prev, [target]: { ok: data.ok, output: data.output || '' } }))
      } else {
        setTestResults((prev: Record<string, { ok: boolean; output: string } | null>) => ({ ...prev, [target]: { ok: false, output: data.detail || 'Error' } }))
      }
    } catch {
      setTestResults((prev: Record<string, { ok: boolean; output: string } | null>) => ({ ...prev, [target]: { ok: false, output: 'Network error' } }))
    } finally {
      setTesting((prev: Record<string, boolean>) => ({ ...prev, [target]: false }))
    }
  }

  if (Object.keys(connections).length === 0 && !isAdmin) return null

  return (
    <div style={{ padding: '8px', borderTop: '1px solid var(--border-color, #333)', fontSize: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ fontWeight: 600, color: 'var(--text-secondary, #aaa)' }}>Connections</span>
        {isAdmin && !editing && (
          <button onClick={handleEdit} style={{ fontSize: '11px', padding: '2px 6px', cursor: 'pointer' }}>
            Edit
          </button>
        )}
      </div>

      {editing ? (
        <div>
          <textarea
            value={editJson}
            onChange={e => setEditJson(e.target.value)}
            style={{ width: '100%', height: '120px', fontSize: '11px', fontFamily: 'monospace', boxSizing: 'border-box' }}
          />
          {error && <div style={{ color: 'red', marginBottom: '4px' }}>{error}</div>}
          <div style={{ display: 'flex', gap: '6px' }}>
            <button onClick={handleSave} disabled={saving} style={{ fontSize: '11px', padding: '2px 6px', cursor: 'pointer' }}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button onClick={() => { setEditing(false); setError('') }} style={{ fontSize: '11px', padding: '2px 6px', cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div>
          {Object.entries(connections).map(([target, rawCfg]) => {
            const cfg = asCfg(rawCfg)
            const isProd = cfg.engine === 'dremio'
            const canTest = !isProd || isMaintainer
            const res = testResults[target]
            return (
              <div key={target} style={{ marginBottom: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: isProd ? '#f0a' : 'var(--text-primary, #ccc)' }}>
                    <strong>{target}</strong> · {cfg.engine}
                    {isProd && <span style={{ marginLeft: 4, fontSize: '10px', color: '#f0a' }}>[prod]</span>}
                  </span>
                  <button
                    onClick={() => handleTest(target)}
                    disabled={testing[target] || !canTest}
                    title={!canTest ? 'Requires maintainer role' : `Test ${target}`}
                    style={{ fontSize: '10px', padding: '2px 5px', cursor: canTest ? 'pointer' : 'not-allowed', opacity: canTest ? 1 : 0.5 }}
                  >
                    {testing[target] ? '…' : 'Test'}
                  </button>
                </div>
                {res && (
                  <div style={{ marginTop: '2px', color: res.ok ? '#4c4' : '#c44', fontSize: '10px', wordBreak: 'break-all' }}>
                    {res.ok ? '✓ OK' : '✗ Failed'}{res.output ? `: ${res.output.slice(0, 200)}` : ''}
                  </div>
                )}
              </div>
            )
          })}
          {Object.keys(connections).length === 0 && isAdmin && (
            <div style={{ color: 'var(--text-secondary, #888)', fontSize: '11px' }}>
              No connections configured. Click Edit to add.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
