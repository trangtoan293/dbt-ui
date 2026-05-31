import { useState, useEffect } from 'react'
import { updateWorkspaceConnections, getWorkspace } from '../../config/api'
import './ProjectPathDialog.css'

interface WorkspaceSettingsModalProps {
  workspaceId: string
  workspaceName: string
  onClose: () => void
  onUpdated: () => void
}

export default function WorkspaceSettingsModal({
  workspaceId,
  workspaceName,
  onClose,
  onUpdated
}: WorkspaceSettingsModalProps) {
  const [connections, setConnections] = useState<Record<string, Record<string, unknown>>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getWorkspace(workspaceId)
      .then((ws) => setConnections(ws.connections || {}))
      .catch(() => setError('Failed to load connections'))
  }, [workspaceId])

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      await updateWorkspaceConnections(workspaceId, connections)
      onUpdated()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update connections')
    } finally {
      setSaving(false)
    }
  }

  const updateConnection = (target: string, field: string, value: unknown) => {
    setConnections((prev: Record<string, Record<string, unknown>>) => ({
      ...prev,
      [target]: {
        ...(prev[target] || {}),
        [field]: value
      }
    }))
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>Workspace Settings: {workspaceName}</h3>

        {error && <div className="error-message">{error}</div>}

        <h4>Dev Connection</h4>

        <div className="form-group">
          <label>Type</label>
          <input
            type="text"
            value={String(connections.dev?.type || '')}
            onChange={(e) => updateConnection('dev', 'type', e.target.value)}
            placeholder="postgres"
            disabled={saving}
          />
        </div>

        <div className="form-group">
          <label>Host</label>
          <input
            type="text"
            value={String(connections.dev?.host || '')}
            onChange={(e) => updateConnection('dev', 'host', e.target.value)}
            placeholder="localhost"
            disabled={saving}
          />
        </div>

        <div className="form-group">
          <label>Port</label>
          <input
            type="number"
            value={String(connections.dev?.port || '')}
            onChange={(e) => updateConnection('dev', 'port', parseInt(e.target.value))}
            placeholder="5432"
            disabled={saving}
          />
        </div>

        <div className="form-group">
          <label>Database</label>
          <input
            type="text"
            value={String(connections.dev?.database || '')}
            onChange={(e) => updateConnection('dev', 'database', e.target.value)}
            placeholder="mydb"
            disabled={saving}
          />
        </div>

        <div className="form-group">
          <label>Schema</label>
          <input
            type="text"
            value={String(connections.dev?.schema || '')}
            onChange={(e) => updateConnection('dev', 'schema', e.target.value)}
            placeholder="public"
            disabled={saving}
          />
        </div>

        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
