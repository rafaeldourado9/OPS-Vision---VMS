/**
 * Global Error Handler Service
 * 
 * Captures all uncaught errors and unhandled promise rejections with complete context.
 * Implements Requirements 1.1 and 1.2 from the frontend-error-resolution spec.
 */

export interface ErrorContext {
  errorType: string
  message: string
  stack?: string
  componentName?: string
  userAction?: string
  applicationState?: Record<string, any>
  timestamp: string
  url: string
  userAgent: string
}

export interface ErrorLog {
  id: string
  context: ErrorContext
  rawError: any
}

class ErrorHandlerService {
  private errorLogs: ErrorLog[] = []
  private maxLogs = 100
  private currentComponent: string | null = null
  private lastUserAction: string | null = null

  /**
   * Initialize global error handlers
   */
  initialize(): void {
    // Handle synchronous errors
    window.onerror = (message, source, lineno, colno, error) => {
      this.captureError({
        errorType: 'RuntimeError',
        message: typeof message === 'string' ? message : String(message),
        stack: error?.stack,
        source,
        lineno,
        colno,
        rawError: error,
      })
      return false // Allow default error handling to continue
    }

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.captureError({
        errorType: 'UnhandledPromiseRejection',
        message: event.reason?.message || String(event.reason),
        stack: event.reason?.stack,
        rawError: event.reason,
      })
    })

    console.log('[ErrorHandler] Global error handlers initialized')
  }

  /**
   * Capture and log an error with complete context
   */
  private captureError(errorData: {
    errorType: string
    message: string
    stack?: string
    source?: string
    lineno?: number
    colno?: number
    rawError?: any
  }): void {
    const errorContext: ErrorContext = {
      errorType: errorData.errorType,
      message: errorData.message,
      stack: errorData.stack || this.extractStackTrace(errorData.rawError),
      componentName: this.currentComponent || 'Unknown',
      userAction: this.lastUserAction || 'None',
      applicationState: this.captureApplicationState(),
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
    }

    const errorLog: ErrorLog = {
      id: this.generateErrorId(),
      context: errorContext,
      rawError: errorData.rawError,
    }

    // Add to in-memory log
    this.errorLogs.push(errorLog)
    if (this.errorLogs.length > this.maxLogs) {
      this.errorLogs.shift() // Remove oldest log
    }

    // Log to console with full context
    console.error('[ErrorHandler] Error captured:', {
      id: errorLog.id,
      type: errorContext.errorType,
      message: errorContext.message,
      component: errorContext.componentName,
      action: errorContext.userAction,
      timestamp: errorContext.timestamp,
      stack: errorContext.stack,
      state: errorContext.applicationState,
    })

    // Persist to localStorage for later analysis
    this.persistErrorLog(errorLog)
  }

  /**
   * Extract stack trace from error object
   */
  private extractStackTrace(error: any): string | undefined {
    if (!error) return undefined
    
    if (error.stack) {
      return error.stack
    }
    
    if (Error.captureStackTrace) {
      const obj: any = {}
      Error.captureStackTrace(obj, this.captureError)
      return obj.stack
    }
    
    return new Error().stack
  }

  /**
   * Capture current application state
   */
  private captureApplicationState(): Record<string, any> {
    const state: Record<string, any> = {
      pathname: window.location.pathname,
      search: window.location.search,
      hash: window.location.hash,
    }

    // Capture localStorage state (excluding sensitive data)
    try {
      const authData = localStorage.getItem('auth-storage')
      if (authData) {
        const parsed = JSON.parse(authData)
        state.isAuthenticated = !!parsed.state?.user
        state.userRole = parsed.state?.user?.role
      }
    } catch (e) {
      state.authStateError = 'Failed to parse auth state'
    }

    // Capture theme state
    try {
      const themeData = localStorage.getItem('theme-storage')
      if (themeData) {
        const parsed = JSON.parse(themeData)
        state.theme = parsed.state?.theme?.name || 'default'
      }
    } catch (e) {
      state.themeStateError = 'Failed to parse theme state'
    }

    return state
  }

  /**
   * Generate unique error ID
   */
  private generateErrorId(): string {
    return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * Persist error log to localStorage
   */
  private persistErrorLog(errorLog: ErrorLog): void {
    try {
      const storageKey = 'error-logs'
      const existingLogs = localStorage.getItem(storageKey)
      const logs: ErrorLog[] = existingLogs ? JSON.parse(existingLogs) : []
      
      logs.push(errorLog)
      
      // Keep only last 50 errors in localStorage
      if (logs.length > 50) {
        logs.shift()
      }
      
      localStorage.setItem(storageKey, JSON.stringify(logs))
    } catch (e) {
      console.warn('[ErrorHandler] Failed to persist error log to localStorage:', e)
    }
  }

  /**
   * Set the current component name for error context
   */
  setCurrentComponent(componentName: string): void {
    this.currentComponent = componentName
  }

  /**
   * Clear the current component name
   */
  clearCurrentComponent(): void {
    this.currentComponent = null
  }

  /**
   * Record a user action for error context
   */
  recordUserAction(action: string): void {
    this.lastUserAction = action
    console.debug(`[ErrorHandler] User action recorded: ${action}`)
  }

  /**
   * Get all error logs
   */
  getErrorLogs(): ErrorLog[] {
    return [...this.errorLogs]
  }

  /**
   * Get error logs from localStorage
   */
  getPersistedErrorLogs(): ErrorLog[] {
    try {
      const storageKey = 'error-logs'
      const existingLogs = localStorage.getItem(storageKey)
      return existingLogs ? JSON.parse(existingLogs) : []
    } catch (e) {
      console.warn('[ErrorHandler] Failed to retrieve persisted error logs:', e)
      return []
    }
  }

  /**
   * Clear all error logs
   */
  clearErrorLogs(): void {
    this.errorLogs = []
    try {
      localStorage.removeItem('error-logs')
    } catch (e) {
      console.warn('[ErrorHandler] Failed to clear persisted error logs:', e)
    }
  }

  /**
   * Export error logs as JSON for analysis
   */
  exportErrorLogs(): string {
    const allLogs = {
      inMemory: this.errorLogs,
      persisted: this.getPersistedErrorLogs(),
      exportedAt: new Date().toISOString(),
    }
    return JSON.stringify(allLogs, null, 2)
  }
}

// Export singleton instance
export const errorHandler = new ErrorHandlerService()
