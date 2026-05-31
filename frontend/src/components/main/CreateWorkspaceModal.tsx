import { useState } from 'react'
import { createWorkspace } from '../../config/api'
import './ProjectPathDialog.css'

interface CreateWorkspaceModalProps {
  onClose: () => void
  onCreated: () => void
}

export default function CreateWorkspaceModal({ onClose, onCreated }: CreateWorkspaceModalProps) {
  const [name, setName] = useState('')
  const [adapter, setAdapter] = useState('postgres')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const handleCreate = async () => {
    if (!name.trim()) return

    setCreating(true)
    setError('')
    try {
      await createWorkspace(name.trim(), adapter)
      onCreated()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create workspace')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>Create Workspace</h3>

        {error && <div className="error-message">{error}</div>}

        <div className="form-group">
          <label>Workspace name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-analytics"
            disabled={creating}
          />
        </div>

        <div className="form-group">
          <label>Adapter</label>
          <select
            value={adapter}
            onChange={(e) => setAdapter(e.target.value)}
            disabled={creating}
          >
            <option value="postgres">PostgreSQL</option>
            <option value="dremio">Dremio</option>
            <option value="duckdb">DuckDB</option>
            <option value="spark">Spark</option>
          </select>
        </div>

        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={creating}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleCreate}
            disabled={creating || !name.trim()}
          >
            {creating ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}
