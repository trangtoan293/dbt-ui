import { useState, useEffect } from 'react'
import { DiffEditor } from '@monaco-editor/react'
import { apiUrl, apiFetch } from '../../config/api'

interface DiffMergePanelProps {
  projectId: string
  onMerged?: () => void
  onClose?: () => void
}

export default function DiffMergePanel({ projectId, onMerged, onClose }: DiffMergePanelProps) {
  const [diff, setDiff] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [merging, setMerging] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [conflicts, setConflicts] = useState<string[]>([])
  const [isMaintainer, setIsMaintainer] = useState(false)

  useEffect(() => {
    loadUser()
    loadDiff()
  }, [projectId])

  const loadUser = async () => {
    try {
      const r = await apiFetch(apiUrl('/api/me'), { method: 'GET' })
      if (r.ok) {
        const u = await r.json()
        setIsMaintainer(u.roles?.includes('maintainer') || u.roles?.includes('admin'))
      }
    } catch {}
  }

  const loadDiff = async () => {
    setLoading(true)
    setError('')
    try {
      const r = await apiFetch(apiUrl('/api/project-diff'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: projectId }),
      })
      if (!r.ok) {
        setError('Failed to load diff')
        return
      }
      const data = await r.json()
      setDiff(data.diff || '')
    } catch {
      setError('Failed to load diff')
    } finally {
      setLoading(false)
    }
  }

  const handleMerge = async () => {
    setMerging(true)
    setError('')
    setConflicts([])
    try {
      const r = await apiFetch(apiUrl('/api/merge-to-main'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: projectId }),
      })
      if (!r.ok) {
        const data = await r.json().catch(() => ({}))
        setError(data.detail || 'Merge failed')
        return
      }
      const data = await r.json()
      if (data.merged) {
        setSuccess('Merged into Main successfully')
        setDiff('')
        onMerged?.()
      } else {
        setConflicts(data.conflicts || [])
        setError('Merge conflict — resolve in a local checkout')
      }
    } catch {
      setError('Merge request failed')
    } finally {
      setMerging(false)
    }
  }

  return (
    <div className="diff-merge-panel">
      <div className="diff-merge-header">
        <h3>Diff vs Main</h3>
        <div className="diff-merge-actions">
          <button onClick={loadDiff} disabled={loading} className="btn-secondary">
            {loading ? 'Loading…' : 'Refresh'}
          </button>
          {isMaintainer && diff && (
            <button onClick={handleMerge} disabled={merging} className="btn-primary">
              {merging ? 'Merging…' : 'Merge into Main'}
            </button>
          )}
          {onClose && (
            <button onClick={onClose} className="btn-secondary">Close</button>
          )}
        </div>
      </div>

      {error && <div className="diff-merge-error">{error}</div>}
      {success && <div className="diff-merge-success">{success}</div>}
      {conflicts.length > 0 && (
        <div className="diff-merge-conflicts">
          <strong>Conflicts:</strong>
          <ul>{conflicts.map((f: string) => <li key={f}>{f}</li>)}</ul>
        </div>
      )}

      {loading && <div className="diff-merge-loading">Loading diff…</div>}

      {!loading && !diff && !success && (
        <div className="diff-merge-empty">No changes relative to Main.</div>
      )}

      {!loading && diff && (
        <DiffEditor
          height="400px"
          language="sql"
          theme="vs-dark"
          original=""
          modified={diff}
          options={{ readOnly: true, renderSideBySide: false }}
        />
      )}
    </div>
  )
}
