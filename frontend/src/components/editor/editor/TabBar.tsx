import { X } from 'lucide-react'

interface TabBarProps {
  openPaths: string[]
  activePath: string | null
  isDirty: (p: string) => boolean
  onActivate: (p: string) => void
  onClose: (p: string) => void
}

export default function TabBar({ openPaths, activePath, isDirty, onActivate, onClose }: TabBarProps) {
  if (openPaths.length === 0) return null
  return (
    <div className="tab-bar" role="tablist">
      {openPaths.map(path => {
        const name = path.split('/').pop() ?? path
        return (
          <div key={path} role="tab" aria-selected={path === activePath}
               className={`tab ${path === activePath ? 'tab-active' : ''}`}
               onClick={() => onActivate(path)} title={path}>
            <span className="tab-name">{name}</span>
            {isDirty(path) && <span className="tab-dirty" aria-label="unsaved">●</span>}
            <button className="tab-close" aria-label={`Close ${name}`}
                    onClick={(e) => { e.stopPropagation(); onClose(path) }}>
              <X size={12} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
