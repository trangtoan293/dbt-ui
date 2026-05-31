// Branch section component for GitModal

import {
  GitBranch,
  Check,
  Plus,
  ChevronDown,
  Trash2,
} from 'lucide-react'
import { BranchState } from '../types'

interface BranchSectionProps {
  branchState: BranchState
  showBranchDropdown: boolean
  showNewBranchInput: boolean
  newBranchName: string
  isAnyOperationInProgress: boolean
  onShowBranchDropdown: (show: boolean) => void
  onShowNewBranchInput: (show: boolean) => void
  onNewBranchNameChange: (name: string) => void
  onCheckoutBranch: (branch: string) => void
  onCreateBranch: () => void
  onDeleteBranch: (branch: string) => void
  isBranchDisabled: (branch: string) => boolean
  getBranchDisabledReason: (branch: string) => string
  canDeleteBranch: (branch: string) => boolean
}

export default function BranchSection({
  branchState,
  showBranchDropdown,
  showNewBranchInput,
  newBranchName,
  isAnyOperationInProgress,
  onShowBranchDropdown,
  onShowNewBranchInput,
  onNewBranchNameChange,
  onCheckoutBranch,
  onCreateBranch,
  onDeleteBranch,
  isBranchDisabled,
  getBranchDisabledReason,
  canDeleteBranch,
}: BranchSectionProps) {
  const { currentBranch, branches } = branchState

  return (
    <div className="git-branch-section">
      <div className="git-branch-row">
        <div className="git-branch-selector">
          <button
            className="git-branch-button"
            onClick={() => onShowBranchDropdown(!showBranchDropdown)}
            disabled={isAnyOperationInProgress}
          >
            <GitBranch size={14} />
            <span>{currentBranch || 'No branch'}</span>
            <ChevronDown size={14} />
          </button>

          {showBranchDropdown && (
            <div className="git-branch-dropdown">
              <div className="git-branch-list">
                {branches.map((branch: string) => {
                  const disabled = isBranchDisabled(branch)
                  const reason = getBranchDisabledReason(branch)
                  return (
                    <button
                      key={branch}
                      className={`git-branch-item ${branch === currentBranch ? 'current' : ''} ${disabled ? 'disabled' : ''}`}
                      onClick={() => onCheckoutBranch(branch)}
                      disabled={disabled}
                      title={reason}
                    >
                      {branch === currentBranch && <Check size={12} />}
                      <span>{branch}</span>
                      {canDeleteBranch(branch) && (
                        <button
                          className="git-branch-delete-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            onDeleteBranch(branch)
                          }}
                          title="Delete branch"
                        >
                          <Trash2 size={12} />
                        </button>
                      )}
                    </button>
                  )
                })}
              </div>
              <div className="git-branch-dropdown-footer">
                <button
                  className="git-new-branch-btn"
                  onClick={() => {
                    onShowNewBranchInput(true)
                    onShowBranchDropdown(false)
                  }}
                >
                  <Plus size={14} />
                  <span>New Branch</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {showNewBranchInput && (
        <div className="git-new-branch-form">
          <input
            type="text"
            placeholder="New branch name"
            value={newBranchName}
            onChange={(e) => onNewBranchNameChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !isAnyOperationInProgress && onCreateBranch()}
            disabled={isAnyOperationInProgress}
            autoFocus
          />
          <button
            className="git-btn-primary"
            onClick={onCreateBranch}
            disabled={isAnyOperationInProgress || !newBranchName.trim()}
          >
            Create
          </button>
          <button
            className="git-btn-secondary"
            onClick={() => {
              onShowNewBranchInput(false)
              onNewBranchNameChange('')
            }}
            disabled={isAnyOperationInProgress}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}
