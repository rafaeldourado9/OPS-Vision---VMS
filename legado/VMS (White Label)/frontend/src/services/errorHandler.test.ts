/**
 * Tests for Global Error Handler Service
 * 
 * Validates Requirements 1.1 and 1.2:
 * - Captures uncaught errors with complete stack traces
 * - Logs error context including component name, user action, and application state
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { errorHandler } from './errorHandler'

describe('ErrorHandler Service', () => {
  beforeEach(() => {
    // Clear error logs before each test
    errorHandler.clearErrorLogs()
    
    // Clear localStorage
    localStorage.clear()
    
    // Mock console methods
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'debug').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Initialization', () => {
    it('should initialize global error handlers', () => {
      errorHandler.initialize()
      
      expect(window.onerror).toBeDefined()
      expect(console.log).toHaveBeenCalledWith(
        '[ErrorHandler] Global error handlers initialized'
      )
    })
  })

  describe('Error Capture', () => {
    it('should capture synchronous errors via window.onerror', () => {
      errorHandler.initialize()
      
      // Trigger a synchronous error
      const testError = new Error('Test synchronous error')
      window.onerror?.('Test synchronous error', 'test.js', 10, 5, testError)
      
      const logs = errorHandler.getErrorLogs()
      expect(logs).toHaveLength(1)
      expect(logs[0].context.errorType).toBe('RuntimeError')
      expect(logs[0].context.message).toBe('Test synchronous error')
      expect(logs[0].context.stack).toBeDefined()
    })

    it('should capture unhandled promise rejections', () => {
      errorHandler.initialize()
      
      // Trigger an unhandled promise rejection
      const testError = new Error('Test promise rejection')
      const event = new PromiseRejectionEvent('unhandledrejection', {
        promise: Promise.reject(testError),
        reason: testError,
      })
      window.dispatchEvent(event)
      
      const logs = errorHandler.getErrorLogs()
      expect(logs).toHaveLength(1)
      expect(logs[0].context.errorType).toBe('UnhandledPromiseRejection')
      expect(logs[0].context.message).toBe('Test promise rejection')
    })

    it('should include complete error context', () => {
      errorHandler.initialize()
      errorHandler.setCurrentComponent('TestComponent')
      errorHandler.recordUserAction('button_click')
      
      const testError = new Error('Test error with context')
      window.onerror?.('Test error with context', 'test.js', 10, 5, testError)
      
      const logs = errorHandler.getErrorLogs()
      expect(logs).toHaveLength(1)
      
      const context = logs[0].context
      expect(context.componentName).toBe('TestComponent')
      expect(context.userAction).toBe('button_click')
      expect(context.timestamp).toBeDefined()
      expect(context.url).toBeDefined()
      expect(context.userAgent).toBeDefined()
      expect(context.applicationState).toBeDefined()
    })

    it('should capture application state', () => {
      errorHandler.initialize()
      
      // Set up some localStorage state
      localStorage.setItem('auth-storage', JSON.stringify({
        state: { user: { role: 'operator' } }
      }))
      localStorage.setItem('theme-storage', JSON.stringify({
        state: { theme: { name: 'dark' } }
      }))
      
      const testError = new Error('Test error')
      window.onerror?.('Test error', 'test.js', 10, 5, testError)
      
      const logs = errorHandler.getErrorLogs()
      const state = logs[0].context.applicationState

      expect(state).toBeDefined()
      expect(state!.pathname).toBeDefined()
      expect(state!.isAuthenticated).toBe(true)
      expect(state!.userRole).toBe('operator')
      expect(state!.theme).toBe('dark')
    })
  })

  describe('Component Tracking', () => {
    it('should track current component name', () => {
      errorHandler.setCurrentComponent('MyComponent')
      
      const testError = new Error('Test error')
      window.onerror?.('Test error', 'test.js', 10, 5, testError)
      
      const logs = errorHandler.getErrorLogs()
      expect(logs[0].context.componentName).toBe('MyComponent')
    })

    it('should clear component name', () => {
      errorHandler.setCurrentComponent('MyComponent')
      errorHandler.clearCurrentComponent()
      
      const testError = new Error('Test error')
      window.onerror?.('Test error', 'test.js', 10, 5, testError)
      
      const logs = errorHandler.getErrorLogs()
      expect(logs[0].context.componentName).toBe('Unknown')
    })
  })

  describe('User Action Tracking', () => {
    it('should record user actions', () => {
      errorHandler.recordUserAction('form_submit')
      
      const testError = new Error('Test error')
      window.onerror?.('Test error', 'test.js', 10, 5, testError)
      
      const logs = errorHandler.getErrorLogs()
      expect(logs[0].context.userAction).toBe('form_submit')
    })
  })

  describe('Error Log Management', () => {
    it('should persist errors to localStorage', () => {
      errorHandler.initialize()
      
      const testError = new Error('Test error')
      window.onerror?.('Test error', 'test.js', 10, 5, testError)
      
      const persistedLogs = errorHandler.getPersistedErrorLogs()
      expect(persistedLogs).toHaveLength(1)
      expect(persistedLogs[0].context.message).toBe('Test error')
    })

    it('should limit in-memory logs to 100 entries', () => {
      errorHandler.initialize()
      
      // Generate 150 errors
      for (let i = 0; i < 150; i++) {
        const testError = new Error(`Test error ${i}`)
        window.onerror?.(`Test error ${i}`, 'test.js', 10, 5, testError)
      }
      
      const logs = errorHandler.getErrorLogs()
      expect(logs).toHaveLength(100)
      // Should keep the most recent errors
      expect(logs[logs.length - 1].context.message).toBe('Test error 149')
    })

    it('should limit persisted logs to 50 entries', () => {
      errorHandler.initialize()
      
      // Generate 60 errors
      for (let i = 0; i < 60; i++) {
        const testError = new Error(`Test error ${i}`)
        window.onerror?.(`Test error ${i}`, 'test.js', 10, 5, testError)
      }
      
      const persistedLogs = errorHandler.getPersistedErrorLogs()
      expect(persistedLogs.length).toBeLessThanOrEqual(50)
    })

    it('should clear all error logs', () => {
      errorHandler.initialize()
      
      const testError = new Error('Test error')
      window.onerror?.('Test error', 'test.js', 10, 5, testError)
      
      expect(errorHandler.getErrorLogs()).toHaveLength(1)
      expect(errorHandler.getPersistedErrorLogs()).toHaveLength(1)
      
      errorHandler.clearErrorLogs()
      
      expect(errorHandler.getErrorLogs()).toHaveLength(0)
      expect(errorHandler.getPersistedErrorLogs()).toHaveLength(0)
    })

    it('should export error logs as JSON', () => {
      errorHandler.initialize()
      
      const testError = new Error('Test error')
      window.onerror?.('Test error', 'test.js', 10, 5, testError)
      
      const exported = errorHandler.exportErrorLogs()
      const parsed = JSON.parse(exported)
      
      expect(parsed.inMemory).toHaveLength(1)
      expect(parsed.persisted).toHaveLength(1)
      expect(parsed.exportedAt).toBeDefined()
    })
  })

  describe('Error Handling Edge Cases', () => {
    it('should handle errors without stack traces', () => {
      errorHandler.initialize()
      
      window.onerror?.('Simple error message', 'test.js', 10, 5, undefined)
      
      const logs = errorHandler.getErrorLogs()
      expect(logs).toHaveLength(1)
      expect(logs[0].context.message).toBe('Simple error message')
    })

    it('should handle promise rejections with non-Error values', () => {
      errorHandler.initialize()
      
      const event = new PromiseRejectionEvent('unhandledrejection', {
        promise: Promise.reject('String rejection'),
        reason: 'String rejection',
      })
      window.dispatchEvent(event)
      
      const logs = errorHandler.getErrorLogs()
      expect(logs).toHaveLength(1)
      expect(logs[0].context.message).toBe('String rejection')
    })

    it('should handle localStorage errors gracefully', () => {
      errorHandler.initialize()
      
      // Mock localStorage to throw errors
      const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('localStorage is full')
      })
      
      const testError = new Error('Test error')
      window.onerror?.('Test error', 'test.js', 10, 5, testError)
      
      // Should still capture the error in memory
      const logs = errorHandler.getErrorLogs()
      expect(logs).toHaveLength(1)
      
      // Should log a warning about localStorage failure
      expect(console.warn).toHaveBeenCalledWith(
        expect.stringContaining('Failed to persist error log'),
        expect.any(Error)
      )
      
      setItemSpy.mockRestore()
    })
  })
})
