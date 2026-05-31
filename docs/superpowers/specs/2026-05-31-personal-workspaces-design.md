# Personal Workspaces Design Spec

**Date:** 2026-05-31  
**Status:** Draft  
**Author:** AI Assistant

## Overview

Personal Workspaces allow users to create their own isolated dbt projects without requiring admin intervention. Each user can create up to 3 workspaces, which are full-featured dbt projects with git versioning and database connections.

## Goals

1. **Self-service**: Users create workspaces independently, no admin required
2. **Isolation**: Each workspace belongs to one user, no sharing
3. **Full-featured**: Workspaces support git commits, database connections, and all dbt operations
4. **Simple**: No diff/merge flow, single branch per workspace

## Non-Goals

- Workspace sharing between users
- Diff/merge to main branch (workspaces are personal, no shared main)
- Replacing Project Catalog (catalog remains for admin-curated shared projects)

## Architecture

### Data Model

**Storage:** `USER_DATA_PATH/<sub>/workspaces.json`

```json
[
  {
    "id": "abc123",
    "name": "my-analytics",
    "adapter": "postgres",
    "owner_sub": "user-sub-123",
    "path": "/home/dbtui/users/user-sub-123/workspaces/abc123",
    "created_at": "2026-05-31T10:00:00Z",
    "connections": {
      "dev": {
        "type": "postgres",
        "host": "localhost",
        "port": 5432,
        "database": "mydb",
        "schema": "public"
      }
    }
  }
]
```

**Limits:**
- Max 3 workspaces per user (configurable via `DBT_UI__MAX_WORKSPACES`)
- Each workspace is a git repo with single branch (no merge flow)

### File Structure

```
USER_DATA_PATH/
└── <user-sub>/
    ├── workspaces.json
    └── workspaces/
        ├── <workspace-id-1>/
        │   ├── .git/
        │   ├── dbt_project.yml
        │   ├── models/
        │   ├── profiles.yml
        │   └── ...
        └── <workspace-id-2>/
            └── ...
```

### Backend Components

#### 1. `backend/utils/workspace.py`

```python
def list_workspaces(sub: str) -> list[dict]:
    """List all workspaces for a user."""
    
def get_workspace(sub: str, workspace_id: str) -> dict | None:
    """Get workspace by ID, verify ownership."""
    
def create_workspace(sub: str, name: str, adapter: str) -> dict:
    """Create new workspace:
    1. Check limit (max 3)
    2. Create folder: USER_DATA_PATH/<sub>/workspaces/<id>/
    3. Run: dbt init <name> --adapter <type> --skip-profile-setup
    4. Git init + initial commit
    5. Save metadata to workspaces.json
    """
    
def delete_workspace(sub: str, workspace_id: str) -> None:
    """Delete workspace:
    1. Verify ownership
    2. rm -rf workspace folder
    3. Remove from workspaces.json
    """
    
def update_connections(sub: str, workspace_id: str, connections: dict) -> None:
    """Update workspace connections and write profiles.yml."""
```

#### 2. `backend/routes/workspace_routes.py`

```python
POST /api/workspace/create
  Body: {name: str, adapter: str}
  Response: {id, name, path, created_at}
  Limit: 3 per user

POST /api/workspace/list
  Response: [{id, name, adapter, created_at}]

POST /api/workspace/delete
  Body: {id: str}
  Response: {deleted: id}

POST /api/workspace/open
  Body: {id: str}
  Response: {path: "workspaces/<id>", name: str}
  # Returns relative path for resolve_under_root compatibility

POST /api/workspace/update-connections
  Body: {id: str, connections: dict}
  Response: {success: true}
```

#### 3. Extend `dbt_routes.py:_engine_gate()`

```python
def _engine_gate(user, request, project_id: str, worktree, explicit_target: str, env_vars: dict) -> dict:
    # Try catalog first
    entry = catalog.get(project_id)
    
    # If not in catalog, try workspace
    if not entry:
        from utils import workspace
        ws = workspace.get_workspace(user.sub, project_id)
        if ws:
            connections = ws.get("connections", {})
        else:
            connections = {}
    else:
        connections = entry.get("connections", {})
    
    # ... rest of engine gate logic
```

### Frontend Components

#### 1. `ProjectDialog.tsx` (rename from `ProjectCatalogDialog.tsx`)

```tsx
<Tabs>
  <Tab label="My Workspaces">
    <WorkspaceList />
    <CreateWorkspaceButton />
  </Tab>
  <Tab label="Shared Projects">
    <CatalogList />  {/* Existing catalog UI */}
  </Tab>
</Tabs>
```

#### 2. `CreateWorkspaceModal.tsx`

```tsx
<Modal>
  <Input label="Workspace name" />
  <Select label="Adapter">
    <Option value="postgres">PostgreSQL</Option>
    <Option value="dremio">Dremio</Option>
    <Option value="duckdb">DuckDB</Option>
    <Option value="spark">Spark</Option>
  </Select>
  <Button onClick={handleCreate}>Create</Button>
</Modal>
```

#### 3. `WorkspaceSettingsModal.tsx`

```tsx
<Modal>
  <h3>Database Connections</h3>
  <ConnectionForm 
    connections={workspace.connections}
    onSave={handleUpdateConnections}
  />
</Modal>
```

### Environment Variables

```bash
USER_DATA_PATH=/home/dbtui/users  # Default: GIT_REPOS_PATH/users
DBT_UI__MAX_WORKSPACES=3
```

### Security

1. **Path isolation**: Workspace path always under `user_root(sub)`
   - Reuse `user_paths.py` enforcement
   - `resolve_under_root(sub, "workspaces/<id>")` → safe

2. **Ownership**: User can only list/delete/open/update their own workspaces
   - All workspace operations verify `owner_sub == user.sub`

3. **No path traversal**: Workspace ID is UUID, not user-controlled path

### Compatibility with Existing APIs

**✅ Works out of the box:**
- File operations: `read-file`, `write-file`, `create-file`, `rename-file`, `delete-file`
- Git operations: `git-commit`, `git-create-branch`, `git-checkout-branch`, `git-stage`, `git-unstage`
- dbt operations: `dbt-command`, `dbt-ls`, `dbt-show-model`, `get-lineage`, `get-compiled-sql`

**❌ Not applicable to workspaces:**
- `/api/project-diff` — workspaces don't have main branch to diff against
- `/api/merge-to-main` — workspaces don't merge to shared main

**✅ Extended to support workspaces:**
- `_engine_gate()` — check workspace connections if not in catalog

## User Flow

### Create Workspace

```
1. User clicks "Create Workspace" in My Workspaces tab
2. Modal opens: enter name + select adapter
3. Backend:
   - Check limit (max 3)
   - Create folder: USER_DATA_PATH/<sub>/workspaces/<id>/
   - Run: dbt init <name> --adapter <type> --skip-profile-setup
   - Git init + commit "Initial dbt project"
   - Save metadata to workspaces.json
4. Frontend refreshes workspace list
5. User clicks workspace → opens editor
```

### Configure Connections

```
1. User opens workspace
2. Clicks "Settings" button in sidebar
3. WorkspaceSettingsModal opens with connection form
4. User fills connection details (host, port, database, schema, etc.)
5. Backend:
   - Validate connections schema
   - Update workspaces.json
   - Write profiles.yml to workspace folder
6. User can now run dbt commands with database
```

### Delete Workspace

```
1. User clicks delete button on workspace card
2. Confirmation dialog: "Delete workspace 'my-analytics'? This cannot be undone."
3. Backend:
   - Verify ownership
   - rm -rf workspace folder
   - Remove from workspaces.json
4. Frontend refreshes workspace list
```

## Implementation Plan

### Phase 1: Backend Foundation
1. Create `backend/utils/workspace.py` with CRUD operations
2. Create `backend/routes/workspace_routes.py` with 5 endpoints
3. Extend `_engine_gate()` to support workspace connections
4. Add `USER_DATA_PATH` and `DBT_UI__MAX_WORKSPACES` env vars

### Phase 2: Frontend UI
1. Rename `ProjectCatalogDialog` → `ProjectDialog`
2. Add tabs: "My Workspaces" + "Shared Projects"
3. Create `CreateWorkspaceModal` component
4. Create `WorkspaceSettingsModal` component
5. Wire up workspace API calls

### Phase 3: Integration Testing
1. Test workspace creation with different adapters
2. Test file operations in workspace
3. Test git commit in workspace
4. Test dbt commands with connections
5. Test workspace deletion

## Open Questions

None. Design is complete and ready for implementation planning.
