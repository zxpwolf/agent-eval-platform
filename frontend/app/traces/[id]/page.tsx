'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { getTrace, exportReplayLog, startReplay, type Trace, type Span } from '@/lib/api'
import { formatDuration, formatTokens, formatCost, formatTimestamp, getSpanTypeColor, getSpanTypeIcon } from '@/lib/utils'
import { ArrowLeft, Play, Clock, Layers, DollarSign } from 'lucide-react'
import SpanTree from '@/components/SpanTree'
import TimelineView from '@/components/TimelineView'
import ReplayPlayer from '@/components/ReplayPlayer'

export default function TraceDetailPage() {
  const params = useParams()
  const router = useRouter()
  const traceId = params.id as string

  const [trace, setTrace] = useState<Trace | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'tree' | 'timeline'>('tree')
  const [replaySessionId, setReplaySessionId] = useState<string | null>(null)
  const [startingReplay, setStartingReplay] = useState(false)

  useEffect(() => {
    loadTrace()
  }, [traceId])

  const loadTrace = async () => {
    try {
      setLoading(true)
      const data = await getTrace(traceId)
      setTrace(data)
    } catch (error) {
      console.error('Failed to load trace:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleExportReplay = async () => {
    try {
      const result = await exportReplayLog(traceId)
      alert(`Replay log exported: ${result.log_id}`)
    } catch (error) {
      console.error('Failed to export replay log:', error)
      alert('Failed to export replay log')
    }
  }

  const handleStartReplay = async () => {
    try {
      setStartingReplay(true)
      const result = await startReplay(traceId, { mock_llm: true })
      setReplaySessionId(result.session_id)
    } catch (error) {
      console.error('Failed to start replay:', error)
      alert('Failed to start replay')
    } finally {
      setStartingReplay(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading trace...</p>
        </div>
      </div>
    )
  }

  if (!trace) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Trace not found</p>
          <Link href="/" className="text-blue-600 hover:text-blue-900 mt-2 inline-block">
            Back to traces
          </Link>
        </div>
      </div>
    )
  }

  // Calculate stats
  const llmSpans = trace.spans.filter(s => s.span_type === 'llm')
  const totalTokens = llmSpans.reduce((sum, s) => sum + (s.total_tokens || 0), 0)
  const totalCost = llmSpans.reduce((sum, s) => sum + (s.cost || 0), 0)
  const duration = trace.end_time && trace.start_time
    ? (trace.end_time - trace.start_time) * 1000
    : 0

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="text-gray-600 hover:text-gray-900">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div>
                <h1 className="text-xl font-bold text-gray-900">{trace.name || 'Untitled Trace'}</h1>
                <p className="text-sm text-gray-500">{trace.trace_id}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleExportReplay}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Export Replay Log
              </button>
              <button
                onClick={handleStartReplay}
                disabled={startingReplay}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                {startingReplay ? 'Starting...' : 'Start Replay'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <StatItem icon={<Clock className="w-5 h-5 text-blue-600" />} label="Duration" value={formatDuration(duration)} />
          <StatItem icon={<Layers className="w-5 h-5 text-green-600" />} label="Spans" value={trace.spans.length.toString()} />
          <StatItem icon={<span className="text-lg">🔢</span>} label="Tokens" value={formatTokens(totalTokens)} />
          <StatItem icon={<DollarSign className="w-5 h-5 text-yellow-600" />} label="Cost" value={formatCost(totalCost)} />
        </div>

        {/* Metadata */}
        {(trace.user_id || trace.session_id || Object.keys(trace.metadata).length > 0) && (
          <div className="bg-white shadow rounded-lg p-4 mb-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">Metadata</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              {trace.user_id && <div><span className="text-gray-500">User:</span> <span className="ml-1">{trace.user_id}</span></div>}
              {trace.session_id && <div><span className="text-gray-500">Session:</span> <span className="ml-1">{trace.session_id}</span></div>}
              <div><span className="text-gray-500">Started:</span> <span className="ml-1">{formatTimestamp(trace.start_time)}</span></div>
              {trace.end_time && <div><span className="text-gray-500">Ended:</span> <span className="ml-1">{formatTimestamp(trace.end_time)}</span></div>}
            </div>
            {Object.keys(trace.metadata).length > 0 && (
              <div className="mt-2 pt-2 border-t">
                <pre className="text-xs text-gray-600 overflow-auto">{JSON.stringify(trace.metadata, null, 2)}</pre>
              </div>
            )}
          </div>
        )}

        {/* Replay Player */}
        {replaySessionId && (
          <div className="mb-6">
            <ReplayPlayer sessionId={replaySessionId} />
          </div>
        )}

        {/* Tabs */}
        <div className="bg-white shadow rounded-lg">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab('tree')}
                className={`px-6 py-3 text-sm font-medium border-b-2 ${
                  activeTab === 'tree'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Span Tree
              </button>
              <button
                onClick={() => setActiveTab('timeline')}
                className={`px-6 py-3 text-sm font-medium border-b-2 ${
                  activeTab === 'timeline'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Timeline
              </button>
            </nav>
          </div>

          <div className="p-6">
            {activeTab === 'tree' ? (
              <SpanTree spans={trace.spans} />
            ) : (
              <TimelineView spans={trace.spans} />
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

function StatItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-white overflow-hidden shadow rounded-lg p-4">
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
