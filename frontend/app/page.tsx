'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { listTraces, getStats, type TraceListItem, type StatsResponse } from '@/lib/api'
import { formatDuration, formatTokens, formatCost, formatRelativeTime } from '@/lib/utils'
import { Play, BarChart3, Trash2, RefreshCw } from 'lucide-react'

export default function Home() {
  const [traces, setTraces] = useState<TraceListItem[]>([])
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const loadData = async () => {
    try {
      setRefreshing(true)
      const [tracesData, statsData] = await Promise.all([
        listTraces(50),
        getStats(),
      ])
      setTraces(tracesData.traces)
      setStats(statsData)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">Agent Observability</h1>
            <button
              onClick={loadData}
              disabled={refreshing}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <StatCard
              title="Total Traces"
              value={stats.trace_count.toString()}
              icon={<Play className="w-5 h-5 text-blue-600" />}
            />
            <StatCard
              title="Total Spans"
              value={stats.span_count.toString()}
              icon={<BarChart3 className="w-5 h-5 text-green-600" />}
            />
            <StatCard
              title="Total Tokens"
              value={formatTokens(stats.total_tokens)}
              icon={<span className="text-lg">🔢</span>}
            />
            <StatCard
              title="Total Cost"
              value={formatCost(stats.total_cost)}
              icon={<span className="text-lg">💰</span>}
            />
          </div>
        )}

        {/* Traces Table */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Traces</h2>
          </div>

          {traces.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              No traces found. Start tracing your agents!
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Spans</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tokens</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cost</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {traces.map((trace) => (
                    <tr key={trace.trace_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Link href={`/traces/${trace.trace_id}`} className="text-sm font-medium text-blue-600 hover:text-blue-900">
                          {trace.name || 'Untitled'}
                        </Link>
                        <div className="text-xs text-gray-500 truncate max-w-[200px]">{trace.trace_id}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{trace.user_id || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatDuration(trace.duration_ms)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{trace.span_count}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatTokens(trace.total_tokens)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCost(trace.total_cost)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatRelativeTime(trace.start_time)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <Link href={`/traces/${trace.trace_id}`} className="text-blue-600 hover:text-blue-900 mr-4">View</Link>
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

function StatCard({ title, value, icon }: { title: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="bg-white overflow-hidden shadow rounded-lg">
      <div className="p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">{icon}</div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-500 truncate">{title}</dt>
              <dd className="text-2xl font-semibold text-gray-900">{value}</dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
