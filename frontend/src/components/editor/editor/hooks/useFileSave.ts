// Hook for file saving with conflict detection

import { useState } from 'react'
import { apiUrl, apiFetch } from '../../../../config/api'
import { ConflictData } from '../types'

interface UseFileSaveProps {
  selectedFile: string | null
  projectPath: string | null
  content: string
  originalContent: string
  setContent: React.Dispatch<React.SetStateAction<string>>
  setOriginalContent: React.Dispatch<React.SetStateAction<string>>
  setHasUnsavedChanges: React.Dispatch<React.SetStateAction<boolean>>
  onFileModified?: (filePath: string, isModified: boolean) => void
  onFileSaved?: (filePath: string) => void
}

interface UseFileSaveResult {
  saving: boolean
  saveError: string | null
  conflictData: ConflictData | null
  handleSave: (forceContent?: string | React.MouseEvent, forceOriginal?: string) => Promise<void>
  handleConflictCancel: () => void
  handleAcceptIncoming: () => void
  handleAcceptMyChanges: () => Promise<void>
  handleSaveWithConflicts: () => void
  clearSaveError: () => void
}

export function useFileSave({
  selectedFile,
  projectPath,
  content,
  originalContent,
  setContent,
  setOriginalContent,
  setHasUnsavedChanges,
  onFileModified,
  onFileSaved
}: UseFileSaveProps): UseFileSaveResult {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [conflictData, setConflictData] = useState<ConflictData | null>(null)

  const handleSave = async (forceContent?: string | React.MouseEvent, forceOriginal?: string) => {
    if (forceContent && typeof forceContent !== 'string') {
      forceContent = undefined
    }
    if (!selectedFile || !projectPath || saving) return

    const contentToSave = forceContent ?? content
    const originalToCompare = forceOriginal ?? originalContent

    setSaving(true)
    try {
      const response = await apiFetch(apiUrl('/api/write-file'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          projectPath: projectPath,
          filePath: selectedFile,
          content: contentToSave,
          originalContent: originalToCompare,
        }),
      })

      if (response.ok) {
        const data = await response.json()

        if (data.merged && data.content) {
          if (data.hasConflicts) {
            console.warn('[Editor] Conflict detected - showing resolution modal')
            setConflictData({
              mergedContent: data.content,
              diskContent: data.diskContent || '',
              myContent: contentToSave,
            })
            setSaving(false)
            return
          } else {
            setContent(data.content)
            setOriginalContent(data.content)
            setHasUnsavedChanges(false)
            console.log('[Editor] File saved with auto-merged changes from another user')
          }
        } else {
          setOriginalContent(contentToSave)
          setHasUnsavedChanges(false)
        }

        if (selectedFile && onFileModified) {
          onFileModified(selectedFile, true)
        }
        if (selectedFile && onFileSaved) {
          onFileSaved(selectedFile)
        }
      } else {
        const errorData = await response.json().catch(() => ({}))
        const detail = errorData.detail || `Save failed (HTTP ${response.status})`
        console.error('Failed to save file:', detail)
        setSaveError(detail)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error saving file'
      console.error('Error saving file:', err)
      setSaveError(message)
    } finally {
      setSaving(false)
    }
  }

  const handleConflictCancel = () => {
    setConflictData(null)
  }

  const handleAcceptIncoming = () => {
    if (!conflictData) return
    setContent(conflictData.diskContent)
    setOriginalContent(conflictData.diskContent)
    setHasUnsavedChanges(false)
    setConflictData(null)

    if (selectedFile && onFileModified) {
      onFileModified(selectedFile, false)
    }
  }

  const handleAcceptMyChanges = async () => {
    if (!conflictData) return
    setConflictData(null)
    await handleSave(conflictData.myContent, conflictData.diskContent)
  }

  const handleSaveWithConflicts = () => {
    if (!conflictData) return
    setContent(conflictData.mergedContent)
    setOriginalContent(conflictData.mergedContent)
    setHasUnsavedChanges(true)
    setConflictData(null)

    if (selectedFile && onFileModified) {
      onFileModified(selectedFile, true)
    }
  }

  const clearSaveError = () => {
    setSaveError(null)
  }

  return {
    saving,
    saveError,
    conflictData,
    handleSave,
    handleConflictCancel,
    handleAcceptIncoming,
    handleAcceptMyChanges,
    handleSaveWithConflicts,
    clearSaveError
  }
}
