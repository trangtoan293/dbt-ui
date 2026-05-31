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

  return (
    <div className="project-path-dialog">
      <div className="project-path-dialog-content">
        <h2>Open Project</h2>

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
              <p className="no-projects">No workspaces yet. Create one below.</p>
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
              onClick={() => setShowCreateModal(true)}
            >
              Create Workspace
            </button>
          </div>
        )}

        {activeTab === 'catalog' && (
          <div>
            {catalogEntries.length === 0 ? (
              <p className="no-projects">
                No projects in catalog.{isAdmin ? ' Add one via admin panel.' : ' Ask an admin to add a project.'}
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
