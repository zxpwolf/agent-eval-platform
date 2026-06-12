'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { getSessionTraces, type Trace } from '@/lib/api'
import { formatTimestamp, formatDuration, formatTokens, formatCost } from '@/lib/utils'
import { ArrowLeft, MessageSquare, Clock, Layers } from 'lucide-react'

export default function SessionPage() {
  const params = useParams()
  const sessionId = params.id as string

  const [traces, setTraces] = useState<Trace[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTrace, setSelectedTrace] = useState<Trace | null>(null)

  useEffect(() => {
    loadSession()
  }, [sessionId])

  const loadSession = async () => {
    try {
      setLoading(true)
      const data = await getSessionTraces(sessionId)
      setTraces(data.traces || [])
      if (data.traces?.length > 0) {
        setSelectedTrace(data.traces[0])
      }
    } catch (error) {
      console.error('Failed to load session:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading session...</p>
        </div>
      </div>
    )
  }

  // Calculate session stats
  const totalSpans = traces.reduce((sum, t) => sum + t.spans.length, 0)
  const allLlmSpans = traces.flatMap((t) => t.spans.filter((s) => s.span_type === 'llm'))
  const totalTokens = allLlmSpans.reduce((sum, s) => sum + (s.total_tokens || 0), 0)
  const totalCost = allLlmSpans.reduce((sum, s) => sum + (s.cost || 0), 0)

  const sessionStart = traces.length > 0 ? Math.min(...traces.map((t) => t.start_time)) : 0
  const sessionEnd = traces.length > 0
    ? Math.max(...traces.map((t) => t.end_time || t.start_time))
    : 0
  const sessionDuration = (sessionEnd - sessionStart) * 1000

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-600 hover:text-gray-900">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Session</h1>
              <p className="text-sm text-gray-500 font-mono">{sessionId}</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
          <StatCard icon={<MessageSquare className="w-5 h-5 text-blue-600" />} label="Traces" value={String(traces.length)} />
          <StatCard icon={<Layers className="w-5 h-5 text-green-600" />} label="Spans" value={String(totalSpans)} />
          <StatCard icon={<Clock className="w-5 h-5 text-purple-600" />} label="Duration" value={formatDuration(sessionDuration)} />
          <StatCard icon={<span className="text-lg">🔢</span>} label="Tokens" value={formatTokens(totalTokens)} />
          <StatCard icon={<span className="text-lg">💰</span>} label="Cost" value={formatCost(totalCost)} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Timeline */}
          <div className="lg:col-span-1">
            <div className="bg-white shadow rounded-lg">
              <div className="px-4 py-3 border-b border-gray-200">
                <h2 className="text-sm font-semibold text-gray-900">Conversation Timeline</h2>
              </div>
              <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
                {traces.map((trace, idx) => {
                  const duration = trace.end_time && trace.start_time
                    ? (trace.end_time - trace.start_time) * 1000
                    : 0
                  const llmSpans = trace.spans.filter((s) => s.span_type === 'llm')
                  const tokens = llmSpans.reduce((sum, s) => sum + (s.total_tokens || 0), 0)
                  const isSelected = selectedTrace?.trace_id === trace.trace_id

                  return (
                    <button
                      key={trace.trace_id}
                      onClick={() => setSelectedTrace(trace)}
                      className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                        isSelected ? 'bg-blue-50 border-l-2 border-blue-500' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-gray-400">#{idx + 1}</span>
                        <span className="text-xs text-gray-400">{formatTimestamp(trace.start_time)}</span>
                      </div>
                      <p className="text-sm font-medium text-gray-900 mt-1 truncate">
                        {trace.name || 'Untitled'}
                      </p>
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                        <span>{trace.spans.length} spans</span>
                        <span>{formatDuration(duration)}</span>
                        {tokens > 0 && <span>{formatTokens(tokens)}</span>}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Selected trace detail */}
          <div className="lg:col-span-2">
            {selectedTrace ? (
              <div className="bg-white shadow rounded-lg">
                <div className="px-4 py-3 border-b border-gray-200 flex justify-between items-center">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-900">{selectedTrace.name || 'Untitled'}</h2>
                    <p className="text-xs text-gray-500 font-mono">{selectedTrace.trace_id}</p>
                  </div>
                  <Link
                    href={`/traces/${selectedTrace.trace_id}`}
                    className="text-sm text-blue-600 hover:text-blue-900"
                  >
                    Full View →
                  </Link>
                </div>

                {/* Span list */}
                <div className="divide-y divide-gray-100 max-h-[500px] overflow-y-auto">
                  {selectedTrace.spans
                    .sort((a, b) => a.start_time - b.start_time)
                    .map((span) => {
                      const spanDuration = span.end_time && span.start_time
                        ? (span.end_time - span.start_time) * 1000
                        : 0
                      return (
                        <div key={span.span_id} className="px-4 py-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span
                                className={`inline-block w-2 h-2 rounded-full ${
                                  span.status === 'error' ? 'bg-red-500' : 'bg-green-500'
                                }`}
                              />
                              <span className="text-sm font-medium text-gray-900">{span.name}</span>
                              <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                                {span.span_type}
                              </span>
                            </div>
                            <span className="text-xs text-gray-500">{formatDuration(spanDuration)}</span>
                          </div>
                          {(span.input_data || span.output_data) && (
                            <div className="mt-2 grid grid-cols-2 gap-2">
                              {span.input_data && (
                                <div className="text-xs">
                                  <span className="font-medium text-gray-500">Input:</span>
                                  <pre className="mt-1 p-2 bg-gray-50 rounded text-gray-700 overflow-auto max-h-24 truncate">
                                    {typeof span.input_data === 'string'
                                      ? span.input_data
                                      : JSON.stringify(span.input_data, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {span.output_data && (
                                <div className="text-xs">
                                  <span className="font-medium text-gray-500">Output:</span>
                                  <pre className="mt-1 p-2 bg-gray-50 rounded text-gray-700 overflow-auto max-h-24 truncate">
                                    {typeof span.output_data === 'string'
                                      ? span.output_data
                                      : JSON.stringify(span.output_data, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                </div>
              </div>
            ) : (
              <div className="bg-white shadow rounded-lg p-8 text-center text-gray-500">
                Select a trace from the timeline to view details
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-white shadow rounded-lg p-4">
      <div className="flex items-center">
        <div className="flex-shrink-0">{icon}</div>
        <div className="ml-3">
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="text-lg font-semibold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  )
}
