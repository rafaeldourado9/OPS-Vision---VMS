/**
 * Global Error Handler Service
 *
 * Captures all uncaught errors and unhandled promise rejections with complete context.
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

  initialize(): void {
    window.onerror = (message, source, lineno, colno, error) => {
      this.captureError({
        errorType: 'RuntimeError',
        message: typeof message === 'string' ? message : String(message),
        stack: error?.stack,
        rawError: error,
      })
      return false
    }

    window.addEventListener('unhandledrejection', (event) => {
      this.captureError({
        errorType: 'UnhandledPromiseRejection',
        message: event.reason?.message || String(event.reason),
        stack: event.reason?.stack,
        rawError: event.reason,
      })
    })
  }

  private captureError(errorData: {
    errorType: string
    message: string
    stack?: string
    rawError?: any
  }): void {
    const errorContext: ErrorContext = {
      errorType: errorData.errorType,
      message: errorData.message,
      stack: errorData.stack,
      componentName: this.currentComponent || 'Unknown',
      userAction: this.lastUserAction || 'None',
      applicationState: { pathname: window.location.pathname },
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
    }

    const errorLog: ErrorLog = {
      id: `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      context: errorContext,
      rawError: errorData.rawError,
    }

    this.errorLogs.push(errorLog)
    if (this.errorLogs.length > this.maxLogs) {
      this.errorLogs.shift()
    }

    console.error('[ErrorHandler] Error captured:', errorContext.message)
  }

  setCurrentComponent(componentName: string): void {
    this.currentComponent = componentName
  }

  clearCurrentComponent(): void {
    this.currentComponent = null
  }

  recordUserAction(action: string): void {
    this.lastUserAction = action
  }

  getErrorLogs(): ErrorLog[] {
    return [...this.errorLogs]
  }

  clearErrorLogs(): void {
    this.errorLogs = []
  }
}

export const errorHandler = new ErrorHandlerService()
