type SSECallback = (event: MessageEvent) => void

export function connectSSE(token: string, onMessage: SSECallback, onError?: () => void): EventSource {
  const url = `/sse/?token=${encodeURIComponent(token)}`
  const es = new EventSource(url)

  es.onmessage = onMessage

  es.onerror = () => {
    if (onError) onError()
    // Auto-reconnect is built into EventSource
  }

  return es
}
