'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  listTraces,
  getTrace,
  compareEvalRuns,
  type Trace,
  type TraceListItem,
  type EvalRunComparison,
} from '@/lib/api'
import { formatDuration, formatTokens, formatCost, formatTimestamp } from '@/lib/utils'
import { ArrowLeft, GitCompare } from 'lucide-react'

type CompareMode = 'traces' | 'eval_runs'

export default function TraceComparePage() {
  const [mode, setMode] = useState<CompareMode>('traces')
  const [traces, setTraces] = useState<TraceListItem[]>([])
  const [trace1Id, setTrace1Id] = useState('')
  const [trace2Id, setTrace2Id] = useState('')
  const [trace1, setTrace1] = useState<Trace | null>(null)
  const [trace2, setTrace2] = useState<Trace | null>(null)
  const [loading, setLoading] = useState(false)
  const [compareResult, setCompareResult] = useState<TraceComparison | null>(null)

  useEffect(() => {
    loadTraces()
  }, [])

  const loadTraces = async () => {
    try {
      const data = await listTraces(100)
      setTraces(data.traces)
    } catch (error) {
      console.error('Failed to load traces:', error)
    }
  }

  const handleCompare = async () => {
    if (!trace1Id || !trace2Id) return
    if (trace1Id === trace2Id) {
      alert('Select two different traces')
      return
    }

    setLoading(true)
    try {
      const [t1, t2] = await Promise.all([getTrace(trace1Id), getTrace(trace2Id)])
      setTrace1(t1)
      setTrace2(t2)

      // Build comparison
      setCompareResult(buildTraceComparison(t1, t2))
    } catch (error) {
      console.error('Failed to compare traces:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-600 hover:text-gray-900">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Trace Comparison</h1>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Selector */}
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Trace A</label>
              <select
                value={trace1Id}
                onChange={(e) => setTrace1Id(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="">Select a trace...</option>
                {traces.map((t) => (
                  <option key={t.trace_id} value={t.trace_id}>
                    {t.name || 'Untitled'} ({t.trace_id.slice(0, 8)}...)
                  </option>
                ))}
              </select>
            </div>
            <div className="flex justify-center">
              <button
                onClick={handleCompare}
                disabled={!trace1Id || !trace2Id || loading}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                <GitCompare className="w-4 h-4" />
                {loading ? 'Comparing...' : 'Compare'}
              </button>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Trace B</label>
              <select
                value={trace2Id}
                onChange={(e) => setTrace2Id(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="">Select a trace...</option>
                {traces.map((t) => (
                  <option key={t.trace_id} value={t.trace_id}>
                    {t.name || 'Untitled'} ({t.trace_id.slice(0, 8)}...)
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Comparison Results */}
        {compareResult && trace1 && trace2 && (
          <div className="space-y-6">
            {/* Overview comparison */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Overview</h2>
              </div>
              <div className="p-6">
                <table className="min-w-full">
                  <thead>
                    <tr className="text-xs font-medium text-gray-500 uppercase">
                      <th className="pb-3 text-left">Metric</th>
                      <th className="pb-3 text-center">Trace A</th>
                      <th className="pb-3 text-center">Trace B</th>
                      <th className="pb-3 text-center">Delta</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    <CompareRow
                      label="Duration"
                      a={formatDuration(compareResult.durationA)}
                      b={formatDuration(compareResult.durationB)}
                      delta={formatDurationSigned(compareResult.durationB - compareResult.durationA)}
                      positive={compareResult.durationB < compareResult.durationA}
                    />
                    <CompareRow
                      label="Spans"
                      a={String(trace1.spans.length)}
                      b={String(trace2.spans.length)}
                      delta={String(trace2.spans.length - trace1.spans.length)}
                      positive={trace2.spans.length <= trace1.spans.length}
                    />
                    <CompareRow
                      label="Tokens"
                      a={formatTokens(compareResult.tokensA)}
                      b={formatTokens(compareResult.tokensB)}
                      delta={formatNumberSigned(compareResult.tokensB - compareResult.tokensA)}
                      positive={compareResult.tokensB <= compareResult.tokensA}
                    />
                    <CompareRow
                      label="Cost"
                      a={formatCost(compareResult.costA)}
                      b={formatCost(compareResult.costB)}
                      delta={formatCostSigned(compareResult.costB - compareResult.costA)}
                      positive={compareResult.costB <= compareResult.costA}
                    />
                  </tbody>
                </table>
              </div>
            </div>

            {/* Span type breakdown */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Span Type Breakdown</h2>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-2 gap-8">
                  <SpanTypeBreakdown title="Trace A" trace={trace1} />
                  <SpanTypeBreakdown title="Trace B" trace={trace2} />
                </div>
              </div>
            </div>

            {/* Side-by-side span list */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Span Comparison</h2>
              </div>
              <div className="p-6 grid grid-cols-2 gap-8">
                <SpanList title="Trace A" trace={trace1} />
                <SpanList title="Trace B" trace={trace2} />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

// ── Helper types and functions ───────────────────────────────

interface TraceComparison {
  durationA: number
  durationB: number
  tokensA: number
  tokensB: number
  costA: number
  costB: number
}

function buildTraceComparison(a: Trace, b: Trace): TraceComparison {
  const llmSpansA = a.spans.filter((s) => s.span_type === 'llm')
  const llmSpansB = b.spans.filter((s) => s.span_type === 'llm')

  return {
    durationA: a.end_time && a.start_time ? (a.end_time - a.start_time) * 1000 : 0,
    durationB: b.end_time && b.start_time ? (b.end_time - b.start_time) * 1000 : 0,
    tokensA: llmSpansA.reduce((sum, s) => sum + (s.total_tokens || 0), 0),
    tokensB: llmSpansB.reduce((sum, s) => sum + (s.total_tokens || 0), 0),
    costA: llmSpansA.reduce((sum, s) => sum + (s.cost || 0), 0),
    costB: llmSpansB.reduce((sum, s) => sum + (s.cost || 0), 0),
  }
}

function formatDurationSigned(ms: number): string {
  const prefix = ms > 0 ? '+' : ''
  return `${prefix}${formatDuration(Math.abs(ms))}`
}

function formatNumberSigned(n: number): string {
  const prefix = n > 0 ? '+' : ''
  return `${prefix}${n}`
}

function formatCostSigned(n: number): string {
  const prefix = n > 0 ? '+' : ''
  return `${prefix}${formatCost(Math.abs(n))}`
}

// ── Components ───────────────────────────────────────────────

function CompareRow({
  label,
  a,
  b,
  delta,
  positive,
}: {
  label: string
  a: string
  b: string
  delta: string
  positive: boolean
}) {
  return (
    <tr>
      <td className="py-3 text-sm font-medium text-gray-900">{label}</td>
      <td className="py-3 text-sm text-center text-gray-700">{a}</td>
      <td className="py-3 text-sm text-center text-gray-700">{b}</td>
      <td className={`py-3 text-sm text-center font-medium ${positive ? 'text-green-600' : 'text-red-600'}`}>
        {delta}
      </td>
    </tr>
  )
}

function SpanTypeBreakdown({ title, trace }: { title: string; trace: Trace }) {
  const typeCounts: Record<string, number> = {}
  trace.spans.forEach((s) => {
    typeCounts[s.span_type] = (typeCounts[s.span_type] || 0) + 1
  })

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900 mb-3">{title}</h3>
      <div className="space-y-2">
        {Object.entries(typeCounts)
          .sort(([, a], [, b]) => b - a)
          .map(([type, count]) => (
            <div key={type} className="flex items-center justify-between">
              <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-700 capitalize">{type}</span>
              <div className="flex items-center gap-2">
                <div className="w-24 bg-gray-200 rounded-full h-1.5">
                  <div
                    className="bg-blue-500 h-1.5 rounded-full"
                    style={{ width: `${(count / trace.spans.length) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-600 w-6 text-right">{count}</span>
              </div>
            </div>
          ))}
      </div>
    </div>
  )
}

function SpanList({ title, trace }: { title: string; trace: Trace }) {
  const sortedSpans = [...trace.spans].sort((a, b) => a.start_time - b.start_time)

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900 mb-3">{title} ({trace.spans.length} spans)</h3>
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {sortedSpans.map((span) => {
          const duration = span.end_time && span.start_time
            ? (span.end_time - span.start_time) * 1000
            : 0
          return (
            <div key={span.span_id} className="p-2 bg-gray-50 rounded">
              <div className="flex justify-between items-center">
                <span className="text-xs font-medium text-gray-900">{span.name}</span>
                <span className="text-xs text-gray-500">{formatDuration(duration)}</span>
              </div>
              <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 text-gray-600 capitalize">
                {span.span_type}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
