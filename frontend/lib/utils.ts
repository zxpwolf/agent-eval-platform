// Formatting and display utilities for the Agent Observability frontend

// ──────────────────────────────────────────────
// Duration formatting
// ──────────────────────────────────────────────

export function formatDuration(ms: number): string {
  if (ms === 0 || isNaN(ms)) return '0ms'
  if (ms < 1) return `${(ms * 1000).toFixed(0)}µs`
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.round((ms % 60_000) / 1000)
  if (minutes < 60) return `${minutes}m ${seconds}s`
  const hours = Math.floor(minutes / 60)
  const remainingMin = minutes % 60
  return `${hours}h ${remainingMin}m`
}

// ──────────────────────────────────────────────
// Token formatting
// ──────────────────────────────────────────────

export function formatTokens(count: number): string {
  if (count === 0 || isNaN(count)) return '0'
  if (count < 1000) return count.toLocaleString()
  if (count < 1_000_000) return `${(count / 1000).toFixed(1)}K`
  return `${(count / 1_000_000).toFixed(1)}M`
}

// ──────────────────────────────────────────────
// Cost formatting
// ──────────────────────────────────────────────

export function formatCost(amount: number): string {
  if (amount === 0 || isNaN(amount)) return '$0.00'
  if (amount < 0.0001) return `$${amount.toExponential(2)}`
  if (amount < 0.01) return `$${amount.toFixed(4)}`
  if (amount < 1) return `$${amount.toFixed(3)}`
  return `$${amount.toFixed(2)}`
}

// ──────────────────────────────────────────────
// Timestamp formatting
// ──────────────────────────────────────────────

export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatRelativeTime(timestamp: number): string {
  const now = Date.now()
  const then = timestamp * 1000
  const diffMs = now - then

  if (diffMs < 0) return 'just now'

  const seconds = Math.floor(diffMs / 1000)
  if (seconds < 60) return 'just now'

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`

  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`

  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks}w ago`

  return formatTimestamp(timestamp)
}

// ──────────────────────────────────────────────
// Span type visual helpers
// ──────────────────────────────────────────────

const SPAN_TYPE_COLORS: Record<string, string> = {
  agent: 'bg-indigo-500',
  llm: 'bg-blue-500',
  tool: 'bg-green-500',
  chain: 'bg-yellow-500',
  retriever: 'bg-purple-500',
  embedding: 'bg-pink-500',
  function: 'bg-gray-500',
  workflow: 'bg-orange-500',
  chat: 'bg-cyan-500',
}

export function getSpanTypeColor(type: string): string {
  return SPAN_TYPE_COLORS[type] ?? 'bg-gray-400'
}

const SPAN_TYPE_ICONS: Record<string, string> = {
  agent: 'A',
  llm: 'L',
  tool: 'T',
  chain: 'C',
  retriever: 'R',
  embedding: 'E',
  function: 'F',
  workflow: 'W',
  chat: 'M',
}

export function getSpanTypeIcon(type: string): string {
  return SPAN_TYPE_ICONS[type] ?? '?'
}

// ──────────────────────────────────────────────
// Status badge helpers
// ──────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  ok: 'bg-green-100 text-green-800',
  error: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  paused: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  stopped: 'bg-gray-100 text-gray-800',
}

export function getStatusStyle(status: string): string {
  return STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-800'
}

// ──────────────────────────────────────────────
// Misc utilities
// ──────────────────────────────────────────────

export function truncate(str: string, maxLength: number = 50): string {
  if (str.length <= maxLength) return str
  return str.slice(0, maxLength - 3) + '...'
}

export function classNames(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ')
}
