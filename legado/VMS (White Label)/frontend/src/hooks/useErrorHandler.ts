import { useEffect } from 'react'
import { errorHandler } from '@/services/errorHandler'

/**
 * Hook to integrate error handler with React components
 * 
 * Usage:
 * ```tsx
 * function MyComponent() {
 *   useErrorHandler('MyComponent')
 *   // ... component code
 * }
 * ```
 */
export function useErrorHandler(componentName: string) {
  useEffect(() => {
    errorHandler.setCurrentComponent(componentName)
    
    return () => {
      errorHandler.clearCurrentComponent()
    }
  }, [componentName])

  return {
    recordAction: (action: string) => errorHandler.recordUserAction(action),
  }
}
