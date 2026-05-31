// Module augmentation for React. This file MUST be a module (note the `import`)
// so `declare module 'react'` MERGES into React's types instead of replacing
// them — a plain `declare module 'react'` in a non-module .d.ts wipes out all of
// React's exports (useState, etc.).
import 'react'

declare module 'react' {
  interface InputHTMLAttributes<T> extends HTMLAttributes<T> {
    webkitdirectory?: string
    directory?: string
  }
}
