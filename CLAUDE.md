# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Frontend (run from `frontend/`)
```bash
npm run dev        # Vite dev server on http://localhost:5173
npm run build      # Production build to dist/
npm run typecheck  # TypeScript type checking (tsc --noEmit)
npm run lint       # ESLint
npm run preview    # Preview production build
```

### Backend (run from `backend/`)
```bash
uvicorn main:app --reload          # Dev server on http://localhost:8000
uv pip install -r requirements.txt # Install dependencies
```

### Full stack
```bash
docker compose up   # Build and run frontend + backend via Nginx
```

There are no automated tests in this codebase.

## Architecture

This is a monorepo: a React SPA frontend and a FastAPI Python backend, containerized with Docker and served through Nginx.

```
dbt-ui/
├── frontend/src/
│   ├── App.tsx                  # Root: git config setup, project path selection
│   ├── config/api.ts            # apiFetch() and apiUrl() helpers — use for all API calls
│   └── components/
│       ├── main/                # MainLayout (orchestrates all state), Sidebar, ProjectPathDialog
│       ├── editor/              # Monaco editor, LineageGraph (ReactFlow DAG), MetadataSidebar
│       ├── git/                 # Git UI: clone, branch, stage, commit, push/pull
│       ├── dbt/                 # dbt command runner UI
│       └── metadv/              # Optional MetaDV Data Vault modeling UI
├── backend/
│   ├── main.py                  # FastAPI app, CORS, optional HTTP Basic Auth
│   ├── models.py                # All Pydantic request/response schemas
│   ├── auth.py                  # HTTP Basic Auth logic
│   ├── routes/
│   │   ├── file_routes.py       # File CRUD, directory listing
│   │   ├── git_routes.py        # Git operations (clone, branch, stage, commit, push/pull)
│   │   ├── dbt_routes.py        # dbt command execution + async status polling
│   │   ├── env_routes.py        # .dbt-ui-env file management
│   │   ├── venv_routes.py       # Python venv setup for dbt
│   │   └── metadv_routes.py     # MetaDV API
│   └── utils/
│       ├── dbt_utils.py         # dbt execution, manifest.json parsing
│       ├── input_validation.py  # Path traversal prevention, git input sanitization
│       ├── merge_utils.py       # 3-way merge for file save conflicts
│       └── operation_lock.py    # Per-worktree mutex for dbt operations
└── docker/                      # Dockerfiles, nginx.conf template
```

## Key Architectural Patterns

**State management**: No Redux or Zustand. All state lives in React `useState` hooks. `MainLayout.tsx` is the central hub holding selected file, dbt operation state, venv status, and unsaved changes. Persistent UI state (git config, recent projects, project path) uses `localStorage`.

**API layer**: All backend endpoints are `POST`, even reads. Always use `apiFetch(apiUrl('/api/endpoint'), options)` from `frontend/src/config/api.ts` — never construct fetch calls directly. This wrapper adds Basic Auth headers when configured.

**Async dbt operations**: When a dbt command starts, the backend acquires a per-worktree lock and runs in a background task. The frontend polls `/api/dbt-command-status` every second until complete. Only one dbt operation per project path is allowed at a time (`operation_lock.py`).

**File save conflict detection**: On save, the backend compares the file's current disk content against the `originalContent` the frontend loaded. If another user modified the file in between, it attempts a 3-way merge (`merge_utils.py`). The frontend shows a `ConflictModal` if the merge has conflicts.

**Git credentials**: Stored in HttpOnly cookies (not localStorage). The backend passes them via a `git_askpass` mechanism to subprocess git calls.

**Lazy directory tree**: The sidebar uses shallow loading — `POST /api/list-directory-shallow` fetches one level at a time as the user expands folders.

## Custom Hooks (Frontend)

Editor hooks live in `frontend/src/components/editor/editor/hooks/`:
- `useFileContent` — load file content, detect binary files
- `useFileSave` — save with conflict detection and merge
- `useCompiledSql` — load compiled SQL from `manifest.json` (LRU-cached)
- `useModelPreview` — execute `dbt show` for data preview (LRU-cached)

Sidebar hooks live in `frontend/src/components/main/sidebar/hooks/`:
- `useDirectoryTree` — lazy-load and expand the file tree
- `useProjectData` — load project name, current branch, manifest status
- `useFileOperations` — create, rename, delete, restore files

## Environment Variables

**Frontend** (in `frontend/.env`):
- `VITE_API_URL` — Backend URL (default: `http://localhost:8000`)
- `VITE_API_USER` / `VITE_API_PASSWORD` — Optional Basic Auth credentials

**Backend**:
- `DBT_UI__BACKEND_USER` / `DBT_UI__BACKEND_PASSWORD` — Enable HTTP Basic Auth on the API
- `DBT_UI__FRONTEND_LINEAGE_MAX_NODES` — Max nodes in the lineage DAG (default: 200)
- `DBT_UI__METADV_ENABLED` — Toggle MetaDV Data Vault feature (default: `true`)
- `GIT_REPOS_PATH` — Filesystem path where cloned repos are stored

## Security-Sensitive Areas

All backend file operations must call path validation from `backend/utils/input_validation.py` to prevent directory traversal. All dbt selector and git branch inputs are validated against regex whitelists in the same file. Git credentials are intentionally stored only in HttpOnly cookies — do not move them to localStorage or response bodies.
