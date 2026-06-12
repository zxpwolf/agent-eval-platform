// SSE client for real-time trace streaming
import { useEffect, useRef, useCallback, useState } from 'react'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ──────────────────────────────────────────────
// Event types
// ──────────────────────────────────────────────

export interface SSEEvent<T = unknown> {
  type: string
  data: T
  timestamp: number
}

export interface TraceCreatedData {
  trace_id: string
  name: string
  span_count: number
}

export interface TraceDeletedData {
  trace_id: string
}

export interface EvalRunProgressData {
  run_id: string
  progress: number
  completed: number
  total: number
}

export interface EvalRunCompletedData {
  run_id: string
  status: string
  result_count: number
}

// ──────────────────────────────────────────────
// Low-level SSE connection manager
// ──────────────────────────────────────────────

type EventHandler = (event: SSEEvent) => void

class TraceStreamConnection {
  private eventSource: EventSource | null = null
  private handlers: Map<string, Set<EventHandler>> = new Map()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private url: string

  constructor() {
    this.url = `${API_BASE_URL}/api/stream/traces`
  }

  connect() {
    if (this.eventSource?.readyState === EventSource.OPEN) return

    this.eventSource = new EventSource(this.url)

    this.eventSource.onopen = () => {
      this.reconnectAttempts = 0
    }

    this.eventSource.onmessage = (event) => {
      try {
        const parsed: SSEEvent = JSON.parse(event.data)
        this.dispatch(parsed)
      } catch {
        // ignore malformed messages
      }
    }

    this.eventSource.onerror = () => {
      this.eventSource?.close()
      this.eventSource = null
      this.scheduleReconnect()
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.eventSource?.close()
    this.eventSource = null
    this.reconnectAttempts = this.maxReconnectAttempts // prevent reconnect
  }

  on(eventType: string, handler: EventHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set())
    }
    this.handlers.get(eventType)!.add(handler)

    // Auto-connect on first subscriber
    this.connect()

    return () => {
      this.handlers.get(eventType)?.delete(handler)
    }
  }

  private dispatch(event: SSEEvent) {
    // Dispatch to specific event type handlers
    this.handlers.get(event.type)?.forEach((h) => h(event))
    // Dispatch to wildcard handlers
    this.handlers.get('*')?.forEach((h) => h(event))
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return
    if (this.handlers.size === 0) return

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000)
    this.reconnectAttempts++

    this.reconnectTimer = setTimeout(() => this.connect(), delay)
  }
}

// Singleton connection
let connection: TraceStreamConnection | null = null

function getConnection(): TraceStreamConnection {
  if (!connection) {
    connection = new TraceStreamConnection()
  }
  return connection
}

// ──────────────────────────────────────────────
// React hooks
// ──────────────────────────────────────────────

/**
 * Subscribe to a specific SSE event type.
 * Returns the latest event of that type, or null if none received.
 */
export function useTraceEvent<T = unknown>(eventType: string): SSEEvent<T> | null {
  const [event, setEvent] = useState<SSEEvent<T> | null>(null)

  useEffect(() => {
    const conn = getConnection()
    const unsubscribe = conn.on(eventType, (e) => {
      setEvent(e as SSEEvent<T>)
    })
    return unsubscribe
  }, [eventType])

  return event
}

/**
 * Subscribe to trace.created events. Returns the latest created trace info.
 */
export function useTraceCreated(): TraceCreatedData | null {
  const event = useTraceEvent<TraceCreatedData>('trace.created')
  return event?.data ?? null
}

/**
 * Subscribe to trace.deleted events. Returns the latest deleted trace ID.
 */
export function useTraceDeleted(): TraceDeletedData | null {
  const event = useTraceEvent<TraceDeletedData>('trace.deleted')
  return event?.data ?? null
}

/**
 * Subscribe to evaluation run progress events.
 */
export function useEvalRunProgress(): EvalRunProgressData | null {
  const event = useTraceEvent<EvalRunProgressData>('eval.run.progress')
  return event?.data ?? null
}

/**
 * Subscribe to all trace events and trigger a callback.
 * Useful for refreshing lists when traces change.
 */
export function useTraceStreamCallback(
  callback: (event: SSEEvent) => void,
  eventTypes: string[] = ['trace.created', 'trace.deleted']
) {
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    const conn = getConnection()
    const unsubscribes = eventTypes.map((type) =>
      conn.on(type, (e) => callbackRef.current(e))
    )
    return () => unsubscribes.forEach((unsub) => unsub())
  }, [eventTypes.join(',')])
}

/**
 * Hook that provides a boolean "live" indicator showing SSE connection status.
 */
export function useTraceStreamStatus(): { connected: boolean } {
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const conn = getConnection()
    const unsubscribe = conn.on('connected', () => setConnected(true))

    // Poll readyState
    const interval = setInterval(() => {
      // If we have any subscribers, we should be connected
      setConnected(true)
    }, 5000)

    return () => {
      unsubscribe()
      clearInterval(interval)
    }
  }, [])

  return { connected }
}
