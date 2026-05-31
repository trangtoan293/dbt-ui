// Editor component types

import type { UseEditorTabs } from '../../main/hooks/useEditorTabs'

export interface ConflictData {
  mergedContent: string
  diskContent: string
  myContent: string
}

export interface ModelPreviewData {
  columns: string[]
  rows: Record<string, any>[]
  error?: string
  hasMore?: boolean
}

export interface EditorProps {
  selectedFile: string | null
  projectPath: string | null
  onToggleMetadata: () => void
  showMetadata: boolean
  onToggleSidebar?: () => void
  showSidebar?: boolean
  compilationTrigger?: number
  onFileModified?: (filePath: string, isModified: boolean) => void
  onFileSaved?: (filePath: string) => void
  dbtVersion?: string
  onUnsavedChangesStateChange?: (hasChanges: boolean) => void
  saveRef?: React.MutableRefObject<(() => Promise<void>) | null>
  tabs?: UseEditorTabs
}

export type ViewMode = 'table' | 'text' | 'rendered'
