import { useState, useEffect } from 'react'
import { apiUrl, apiFetch, listWorkspaces, openWorkspace, Workspace } from '../../config/api'
import CreateWorkspaceModal from './CreateWorkspaceModal'
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

interface ProjectDialogProps {
  onOpen: (projectId: string, projectName: string) => void
}

export default function ProjectDialog({ onOpen }: ProjectDialogProps) {
  const [activeTab, setActiveTab] = useState<'workspaces' | 'catalog'>('workspaces')
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [catalogEntries, setCatalogEntries] = useState<CatalogEntry[]>([])
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)

  const [addName, setAddName] = useState('')
  const [addRepoPath, setAddRepoPath] = useState('')
  const [addMainBranch, setAddMainBranch] = useState('main')
  const [adding, setAdding] = useState(false)

  const isAdmin = user?.roles.includes('admin') ?? false

  useEffect(() => {
    loadUser()
    loadWorkspaces()
    loadCatalog()
  }, [])

  const loadUser = async () => {
    try {
      const r = await apiFetch(apiUrl('/api/me'), { method: 'GET' })
      if (r.ok) setUser(await r.json())
    } catch { /* intentionally empty */ }
  }

  const loadWorkspaces = async () => {
    try {
      const ws = await listWorkspaces()
      setWorkspaces(ws)
    } catch (_e) {
      setError('Failed to load workspaces')
    }
  }

  const loadCatalog = async () => {
    try {
      const r = await apiFetch(apiUrl('/api/catalog/list'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (r.ok) setCatalogEntries(await r.json())
    } catch (_e) {
      setError('Failed to load catalog')
    }
  }

  const handleOpenWorkspace = async (ws: Workspace) => {
    setLoading(true)
    setError('')
    try {
      const result = await openWorkspace(ws.id)
      onOpen(result.path, result.name)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to open workspace')
    } finally {
      setLoading(false)
    }
  }

  const handleOpenCatalog = async (entry: CatalogEntry) => {
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
    } catch (_e) {
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
    } catch (_e) {
      setError('Failed to add project')
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="project-path-dialog">
      <div className="project-path-dialog-content">
        <h2>Open Project</h2>
        <p className="dialog-subtitle" style={{ fontSize: 14, marginBottom: 20, textAlign: 'left' }}>
          Open a personal workspace for your own dbt projects, or browse shared projects from the catalog.
        </p>

        {error && <div className="error-message">{error}</div>}

        <div className="tabs">
          <button
            className={activeTab === 'workspaces' ? 'tab-btn active' : 'tab-btn'}
            onClick={() => setActiveTab('workspaces')}
          >
            My Workspaces
          </button>
          <button
            className={activeTab === 'catalog' ? 'tab-btn active' : 'tab-btn'}
            onClick={() => setActiveTab('catalog')}
          >
            Shared Projects
          </button>
        </div>

        {activeTab === 'workspaces' && (
          <div>
            {workspaces.length === 0 ? (
              <div className="no-projects">
                <p style={{ marginBottom: 8 }}>Create your own dbt project — no admin required.</p>
                <p style={{ fontSize: 12, color: '#6d6d6d' }}>
                  Each workspace is a full dbt project with git versioning and database connections.
                  You can create up to 3 workspaces.
                </p>
              </div>
            ) : (
              <ul className="catalog-list">
                {workspaces.map((ws: Workspace) => (
                  <li key={ws.id} className="catalog-item">
                    <div className="catalog-item-info">
                      <strong>{ws.name}</strong>
                      <span className="catalog-item-branch">{ws.adapter}</span>
                    </div>
                    <div className="catalog-item-actions">
                      <button
                        className="btn-primary"
                        onClick={() => handleOpenWorkspace(ws)}
                        disabled={loading}
                      >
                        Open
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <button
              className="btn-primary"
              style={{ width: '100%' }}
              onClick={() => setShowCreateModal(true)}
            >
              + Create Workspace
            </button>
          </div>
        )}

        {activeTab === 'catalog' && (
          <div>
            {catalogEntries.length === 0 ? (
              <p className="no-projects">
                No shared projects available.{' '}
                {isAdmin ? 'Add your first project below.' : 'Contact an admin to add a project.'}
              </p>
            ) : (
              <ul className="catalog-list">
                {catalogEntries.map((entry: CatalogEntry) => (
                  <li key={entry.id} className="catalog-item">
                    <div className="catalog-item-info">
                      <strong>{entry.name}</strong>
                      <span className="catalog-item-branch">{entry.main_branch}</span>
                    </div>
                    <div className="catalog-item-actions">
                      <button
                        className="btn-primary"
                        onClick={() => handleOpenCatalog(entry)}
                        disabled={loading}
                      >
                        Open
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {isAdmin && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #3c3c3c' }}>
                <h3 style={{ fontSize: 16, color: '#cccccc', marginBottom: 12 }}>Add Project to Catalog</h3>
                <div className="form-group">
                  <label>Project name</label>
                  <input
                    placeholder="my-dbt-project"
                    value={addName}
                    onChange={e => setAddName(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Server repo path (absolute)</label>
                  <input
                    placeholder="/home/git/repos/my-dbt-project.git"
                    value={addRepoPath}
                    onChange={e => setAddRepoPath(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Main branch</label>
                  <input
                    placeholder="main"
                    value={addMainBranch}
                    onChange={e => setAddMainBranch(e.target.value)}
                  />
                </div>
                <button
                  className="btn-primary"
                  style={{ width: '100%' }}
                  onClick={handleAdd}
                  disabled={adding || !addName || !addRepoPath}
                >
                  {adding ? 'Adding...' : 'Add to Catalog'}
                </button>
              </div>
            )}
          </div>
        )}

        {showCreateModal && (
          <CreateWorkspaceModal
            onClose={() => setShowCreateModal(false)}
            onCreated={() => {
              loadWorkspaces()
              setShowCreateModal(false)
            }}
          />
        )}
      </div>
    </div>
  )
}
