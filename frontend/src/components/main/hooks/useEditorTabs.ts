import { useState, useCallback } from 'react'

export interface TabCache {
  content: string
  originalContent: string
  loaded: boolean      // false until first disk load completes
}

export interface UseEditorTabs {
  openPaths: string[]
  activePath: string | null
  isDirty: (path: string) => boolean
  openTab: (path: string) => void
  closeTab: (path: string) => void
  setActive: (path: string) => void
  getCache: (path: string) => TabCache | undefined
  setCache: (path: string, patch: Partial<TabCache>) => void
}

export function useEditorTabs(): UseEditorTabs {
  const [openPaths, setOpenPaths] = useState<string[]>([])
  const [activePath, setActivePath] = useState<string | null>(null)
  const [cache, setCacheState] = useState<Record<string, TabCache>>({})

  const openTab = useCallback((path: string) => {
    setOpenPaths(prev => (prev.includes(path) ? prev : [...prev, path]))
    setActivePath(path)
  }, [])

  const closeTab = useCallback((path: string) => {
    setOpenPaths(prev => {
      const next = prev.filter(p => p !== path)
      setActivePath(cur => (cur === path ? (next[next.length - 1] ?? null) : cur))
      return next
    })
    setCacheState(prev => {
      const { [path]: _drop, ...rest } = prev
      return rest
    })
  }, [])

  const setCache = useCallback((path: string, patch: Partial<TabCache>) => {
    setCacheState(prev => {
      const existing: TabCache = prev[path] ?? { content: '', originalContent: '', loaded: false }
      return { ...prev, [path]: { ...existing, ...patch } }
    })
  }, [])

  const isDirty = useCallback(
    (path: string) => {
      const c = cache[path]
      return !!c && c.loaded && c.content !== c.originalContent
    },
    [cache],
  )

  const getCache = useCallback(
    (path: string) => cache[path],
    [cache],
  )

  return {
    openPaths, activePath, isDirty,
    openTab, closeTab, setActive: setActivePath,
    getCache,
    setCache,
  }
}
