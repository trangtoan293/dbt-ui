import { useState, useEffect } from 'react'
import { apiUrl, apiFetch } from '../../config/api'
import './ProjectPathDialog.css'

interface CatalogEntry {
  id: string
  name: string
  repo_path: string
  main_branch: string
}

interface CurrentUser {
  sub: string
  email: string
  roles: string[]
}

interface ProjectCatalogDialogProps {
  onOpen: (projectId: string, projectName: string) => void
}

export default function ProjectCatalogDialog({ onOpen }: ProjectCatalogDialogProps) {
  const [entries, setEntries] = useState<CatalogEntry[]>([])
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Admin add form state
  const [addName, setAddName] = useState('')
  const [addRepoPath, setAddRepoPath] = useState('')
  const [addMainBranch, setAddMainBranch] = useState('main')
  const [adding, setAdding] = useState(false)

  const isAdmin = user?.roles.includes('admin') ?? false

  useEffect(() => {
    loadUser()
    loadCatalog()
  }, [])

  const loadUser = async () => {
    try {
      const r = await apiFetch(apiUrl('/api/me'), { method: 'GET' })
      if (r.ok) setUser(await r.json())
    } catch {}
  }

  const loadCatalog = async () => {
    try {
      const r = await apiFetch(apiUrl('/api/catalog/list'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (r.ok) setEntries(await r.json())
    } catch (e) {
      setError('Failed to load projects')
    }
  }

  const handleOpen = async (entry: CatalogEntry) => {
    setLoading(true)
    setError('')
    try {
      const r = await apiFetch(apiUrl('/api/open-project'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: entry.id }),
      })
      if (!r.ok) {
        const data = await r.json().catch(() => ({}))
        setError(data.detail || 'Failed to open project')
        return
      }
      const data = await r.json()
      onOpen(data.path, entry.name)
    } catch (e) {
      setError('Failed to open project')
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async () => {
    if (!addName || !addRepoPath) return
    setAdding(true)
    setError('')
    try {
      const r = await apiFetch(apiUrl('/api/catalog/add'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: addName, repo_path: addRepoPath, main_branch: addMainBranch }),
      })
      if (!r.ok) {
        const data = await r.json().catch(() => ({}))
        setError(data.detail || 'Failed to add project')
        return
      }
      setAddName('')
      setAddRepoPath('')
      setAddMainBranch('main')
      await loadCatalog()
    } catch {
      setError('Failed to add project')
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (id: string) => {
    try {
      await apiFetch(apiUrl('/api/catalog/remove'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      })
      await loadCatalog()
    } catch {
      setError('Failed to remove project')
    }
  }

  return (
    <div className="project-path-dialog">
      <div className="project-path-dialog-content">
        <h2>Open Project</h2>

        {error && <div className="error-message">{error}</div>}

        {entries.length === 0 ? (
          <p className="no-projects">No projects in catalog.{isAdmin ? ' Add one below.' : ' Ask an admin to add a project.'}</p>
        ) : (
          <ul className="catalog-list">
            {entries.map((entry: CatalogEntry) => (
              <li key={entry.id} className="catalog-item">
                <div className="catalog-item-info">
                  <strong>{entry.name}</strong>
                  <span className="catalog-item-branch">{entry.main_branch}</span>
                </div>
                <div className="catalog-item-actions">
                  <button
                    className="btn-primary"
                    onClick={() => handleOpen(entry)}
                    disabled={loading}
                  >
                    Open
                  </button>
                  {isAdmin && (
                    <button
                      className="btn-danger"
                      onClick={() => handleRemove(entry.id)}
                    >
                      Remove
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}

        {isAdmin && (
          <div className="catalog-add-form">
            <h3>Add Project</h3>
            <input
              placeholder="Project name"
              value={addName}
              onChange={e => setAddName(e.target.value)}
            />
            <input
              placeholder="Server repo path (absolute)"
              value={addRepoPath}
              onChange={e => setAddRepoPath(e.target.value)}
            />
            <input
              placeholder="Main branch (default: main)"
              value={addMainBranch}
              onChange={e => setAddMainBranch(e.target.value)}
            />
            <button
              className="btn-primary"
              onClick={handleAdd}
              disabled={adding || !addName || !addRepoPath}
            >
              {adding ? 'Adding…' : 'Add to Catalog'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
