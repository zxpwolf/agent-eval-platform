'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  getEvalRun,
  getEvalRunResults,
  cancelEvalRun,
  type EvalRun,
  type EvalResult,
} from '@/lib/api'
import { formatTimestamp, formatRelativeTime } from '@/lib/utils'
import { ArrowLeft, XCircle, RefreshCw } from 'lucide-react'

export default function EvalRunPage() {
  const params = useParams()
  const runId = params.id as string

  const [run, setRun] = useState<EvalRun | null>(null)
  const [results, setResults] = useState<EvalResult[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [runId])

  // Auto-refresh for running evaluations
  useEffect(() => {
    if (!run) return
    if (run.status !== 'running' && run.status !== 'pending') return

    const interval = setInterval(loadData, 3000)
    return () => clearInterval(interval)
  }, [run?.status])

  const loadData = async () => {
    try {
      const [runData, resultsData] = await Promise.all([
        getEvalRun(runId),
        getEvalRunResults(runId),
      ])
      setRun(runData)
      setResults(resultsData.results)
    } catch (error) {
      console.error('Failed to load eval run:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!confirm('Cancel this evaluation run?')) return
    try {
      await cancelEvalRun(runId)
      loadData()
    } catch (error) {
      console.error('Failed to cancel run:', error)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading evaluation run...</p>
        </div>
      </div>
    )
  }

  if (!run) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Evaluation run not found</p>
          <Link href="/evaluations" className="text-blue-600 hover:text-blue-900 mt-2 inline-block">
            Back to evaluations
          </Link>
        </div>
      </div>
    )
  }

  // Compute summary stats
  const passedCount = results.filter((r) => r.passed).length
  const failedCount = results.filter((r) => !r.passed).length
  const avgScore = results.length > 0
    ? results.reduce((sum, r) => sum + r.score, 0) / results.length
    : 0

  const statusColor = () => {
    switch (run.status) {
      case 'completed': return 'bg-green-100 text-green-800'
      case 'running': return 'bg-blue-100 text-blue-800'
      case 'pending': return 'bg-yellow-100 text-yellow-800'
      case 'failed': return 'bg-red-100 text-red-800'
      case 'cancelled': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/evaluations" className="text-gray-600 hover:text-gray-900">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-xl font-bold text-gray-900">Evaluation Run</h1>
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${statusColor()}`}>
                    {run.status}
                  </span>
                </div>
                <p className="text-sm text-gray-500 font-mono">{run.run_id}</p>
              </div>
            </div>
            <div className="flex gap-2">
              {(run.status === 'running' || run.status === 'pending') && (
                <button
                  onClick={handleCancel}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-700 bg-white border border-red-300 rounded-md hover:bg-red-50"
                >
                  <XCircle className="w-4 h-4" />
                  Cancel
                </button>
              )}
              <button
                onClick={loadData}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Progress bar for running evaluations */}
        {(run.status === 'running' || run.status === 'pending') && run.live_status && (
          <div className="mb-6 bg-white shadow rounded-lg p-4">
            <div className="flex justify-between text-sm text-gray-600 mb-2">
              <span>Progress</span>
              <span>{run.live_status.completed} / {run.live_status.total}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style={{
                  width: `${run.live_status.total > 0 ? (run.live_status.completed / run.live_status.total) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        )}

        {/* Summary Stats */}
        {run.status === 'completed' && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <StatCard label="Total Results" value={String(results.length)} />
            <StatCard label="Passed" value={String(passedCount)} valueColor="text-green-600" />
            <StatCard label="Failed" value={String(failedCount)} valueColor="text-red-600" />
            <StatCard label="Avg Score" value={`${(avgScore * 100).toFixed(1)}%`} />
          </div>
        )}

        {/* Run Info */}
        <div className="bg-white shadow rounded-lg p-4 mb-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-2">Run Details</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Dataset:</span>
              <Link
                href={`/evaluations/datasets/${run.dataset_id}`}
                className="ml-2 text-blue-600 hover:text-blue-900 font-mono text-xs"
              >
                {run.dataset_id.slice(0, 8)}...
              </Link>
            </div>
            <div>
              <span className="text-gray-500">Evaluators:</span>
              <span className="ml-2">{run.evaluator_ids.length}</span>
            </div>
            <div>
              <span className="text-gray-500">Started:</span>
              <span className="ml-2">{formatTimestamp(run.started_at)}</span>
            </div>
            {run.completed_at && (
              <div>
                <span className="text-gray-500">Completed:</span>
                <span className="ml-2">{formatTimestamp(run.completed_at)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Results Table */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Results ({results.length})</h2>
          </div>

          {results.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              {run.status === 'running' || run.status === 'pending'
                ? 'Waiting for results...'
                : 'No results'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Item</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Evaluator</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reasoning</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {results.map((result) => (
                    <tr key={result.result_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-mono text-gray-600">
                        {result.item_id.slice(0, 8)}...
                      </td>
                      <td className="px-6 py-4 text-sm font-mono text-gray-600">
                        {result.evaluator_id.slice(0, 8)}...
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <ScoreBar score={result.score} />
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            result.passed
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {result.passed ? 'Pass' : 'Fail'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600 max-w-xs truncate">
                        {result.reasoning || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.8 ? 'bg-green-500' : score >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 bg-gray-200 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600">{pct}%</span>
    </div>
  )
}

function StatCard({
  label,
  value,
  valueColor = 'text-gray-900',
}: {
  label: string
  value: string
  valueColor?: string
}) {
  return (
    <div className="bg-white shadow rounded-lg p-4">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className={`text-2xl font-semibold ${valueColor}`}>{value}</p>
    </div>
  )
}
