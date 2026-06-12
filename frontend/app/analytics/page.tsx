'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { formatDuration, formatTokens, formatCost, formatRelativeTime } from '@/lib/utils'
import { ArrowLeft, RefreshCw, TrendingUp, AlertTriangle, Clock, Zap, DollarSign, BarChart2 } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Types ────────────────────────────────────────────────

interface TimeSeriesPoint {
  timestamp: number
  count?: number
  cost?: number
  tokens?: number
  total?: number
  errors?: number
  error_rate?: number
}

interface ModelAnalytics {
  model: string
  call_count: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  total_cost: number
  avg_latency_ms: number | null
}

interface LatencyByType {
  span_type: string
  count: number
  avg_ms: number
  min_ms: number
  max_ms: number
}

interface ErrorAnalytics {
  total_spans: number
  error_count: number
  error_rate: number
  by_type: { span_type: string; count: number }[]
  recent_errors: {
    span_id: string
    trace_id: string
    trace_name: string
    span_name: string
    span_type: string
    start_time: number
    error_type: string
    error_message: string
  }[]
}

interface SpanTypeDist {
  span_type: string
  count: number
  percentage: number
  total_tokens: number
  total_cost: number
  avg_latency_ms: number
  error_count: number
}

interface TopTrace {
  trace_id: string
  name: string
  start_time: number
  span_count: number
  total_tokens: number
  total_cost: number
  duration_ms: number
}

// ── API Fetchers ─────────────────────────────────────────

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed to fetch ${path}`)
  return res.json()
}

// ── Simple SVG Bar Chart ─────────────────────────────────

function BarChart({ data, color, height = 120, formatValue }: {
  data: { label: string; value: number }[]
  color: string
  height?: number
  formatValue?: (v: number) => string
}) {
  if (data.length === 0) return <div className="text-gray-400 text-center py-8">No data</div>

  const maxVal = Math.max(...data.map(d => d.value), 1)
  const barWidth = Math.max(2, Math.min(24, (600 - data.length * 2) / data.length))
  const chartWidth = data.length * (barWidth + 2)
  const fmt = formatValue || ((v: number) => v.toString())

  return (
    <div className="overflow-x-auto">
      <svg width={Math.max(chartWidth, 100)} height={height + 30} className="block">
        {data.map((d, i) => {
          const barH = (d.value / maxVal) * height
          const x = i * (barWidth + 2)
          const y = height - barH
          return (
            <g key={i}>
              <rect
                x={x} y={y} width={barWidth} height={barH}
                fill={color} rx={1}
                opacity={0.8}
              >
                <title>{`${d.label}: ${fmt(d.value)}`}</title>
              </rect>
              {i % Math.max(1, Math.floor(data.length / 8)) === 0 && (
                <text
                  x={x + barWidth / 2} y={height + 14}
                  textAnchor="middle"
                  className="fill-gray-400"
                  fontSize={9}
                >
                  {d.label}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ── Stat Card ────────────────────────────────────────────

function StatCard({ title, value, subtitle, icon, color }: {
  title: string
  value: string
  subtitle?: string
  icon: React.ReactNode
  color: string
}) {
  return (
    <div className="bg-white overflow-hidden shadow rounded-lg">
      <div className="p-5">
        <div className="flex items-center">
          <div className={`flex-shrink-0 rounded-lg p-2 ${color}`}>{icon}</div>
          <div className="ml-4 flex-1">
            <dt className="text-sm font-medium text-gray-500 truncate">{title}</dt>
            <dd className="text-2xl font-semibold text-gray-900">{value}</dd>
            {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────

export default function AnalyticsPage() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [activeTab, setActiveTab] = useState<'overview' | 'models' | 'latency' | 'errors'>('overview')
  const [sortBy, setSortBy] = useState<'cost' | 'latency' | 'tokens'>('cost')

  const [models, setModels] = useState<ModelAnalytics[]>([])
  const [latencyByType, setLatencyByType] = useState<LatencyByType[]>([])
  const [errors, setErrors] = useState<ErrorAnalytics | null>(null)
  const [spanTypes, setSpanTypes] = useState<SpanTypeDist[]>([])
  const [topTraces, setTopTraces] = useState<TopTrace[]>([])
  const [traceSeries, setTraceSeries] = useState<TimeSeriesPoint[]>([])
  const [costSeries, setCostSeries] = useState<TimeSeriesPoint[]>([])

  const loadData = async () => {
    try {
      setRefreshing(true)
      const [tsData, modelData, latData, errData, stData, topData] = await Promise.all([
        fetchJson<any>('/api/analytics/timeseries?granularity=hour&limit=48'),
        fetchJson<any>('/api/analytics/models'),
        fetchJson<any>('/api/analytics/latency'),
        fetchJson<any>('/api/analytics/errors'),
        fetchJson<any>('/api/analytics/span-types'),
        fetchJson<any>(`/api/analytics/top-traces?sort_by=${sortBy}&limit=10`),
      ])

      setTraceSeries(tsData.trace_series || [])
      setCostSeries(tsData.cost_series || [])
      setModels(modelData.models || [])
      setLatencyByType(latData.by_type || [])
      setErrors(errData)
      setSpanTypes(stData.span_types || [])
      setTopTraces(topData.traces || [])
    } catch (error) {
      console.error('Failed to load analytics:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { loadData() }, [])
  useEffect(() => {
    if (!loading) {
      fetchJson<any>(`/api/analytics/top-traces?sort_by=${sortBy}&limit=10`)
        .then(d => setTopTraces(d.traces || []))
        .catch(console.error)
    }
  }, [sortBy])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading analytics...</p>
        </div>
      </div>
    )
  }

  const totalTraces = traceSeries.reduce((s, p) => s + (p.count || 0), 0)
  const totalCost = costSeries.reduce((s, p) => s + (p.cost || 0), 0)
  const totalTokens = costSeries.reduce((s, p) => s + (p.tokens || 0), 0)
  const avgErrorRate = errors?.error_rate || 0

  const formatTs = (ts: number) => {
    const d = new Date(ts * 1000)
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Link href="/" className="text-gray-500 hover:text-gray-700">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
            </div>
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
        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
          <StatCard
            title="Traces" value={totalTraces.toLocaleString()}
            subtitle="in visible window"
            icon={<BarChart2 className="w-5 h-5 text-blue-600" />}
            color="bg-blue-50"
          />
          <StatCard
            title="Total Cost" value={formatCost(totalCost)}
            subtitle="LLM API spend"
            icon={<DollarSign className="w-5 h-5 text-green-600" />}
            color="bg-green-50"
          />
          <StatCard
            title="Total Tokens" value={formatTokens(totalTokens)}
            subtitle="prompt + completion"
            icon={<Zap className="w-5 h-5 text-yellow-600" />}
            color="bg-yellow-50"
          />
          <StatCard
            title="Error Rate" value={`${(avgErrorRate * 100).toFixed(1)}%`}
            subtitle={`${errors?.error_count || 0} errors / ${errors?.total_spans || 0} spans`}
            icon={<AlertTriangle className="w-5 h-5 text-red-600" />}
            color="bg-red-50"
          />
          <StatCard
            title="Models Used" value={models.length.toString()}
            subtitle={models.length > 0 ? models[0].model : 'none'}
            icon={<TrendingUp className="w-5 h-5 text-purple-600" />}
            color="bg-purple-50"
          />
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            {(['overview', 'models', 'latency', 'errors'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-2 px-1 border-b-2 font-medium text-sm capitalize ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Time Series Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-sm font-semibold text-gray-900 mb-4">Traces Over Time (hourly)</h3>
                <BarChart
                  data={traceSeries.map(p => ({ label: formatTs(p.timestamp), value: p.count || 0 }))}
                  color="#3b82f6"
                  formatValue={v => v.toString()}
                />
              </div>
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-sm font-semibold text-gray-900 mb-4">Cost Over Time (hourly)</h3>
                <BarChart
                  data={costSeries.map(p => ({ label: formatTs(p.timestamp), value: p.cost || 0 }))}
                  color="#10b981"
                  formatValue={v => formatCost(v)}
                />
              </div>
            </div>

            {/* Span Type Distribution */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">Span Type Distribution</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Count</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">%</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tokens</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Cost</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Avg Latency</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Errors</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {spanTypes.map(st => (
                      <tr key={st.span_type} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm font-medium text-gray-900 capitalize">{st.span_type}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{st.count}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{(st.percentage * 100).toFixed(1)}%</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{formatTokens(st.total_tokens)}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{formatCost(st.total_cost)}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{formatDuration(st.avg_latency_ms)}</td>
                        <td className="px-4 py-2 text-sm">
                          <span className={st.error_count > 0 ? 'text-red-600 font-medium' : 'text-gray-400'}>
                            {st.error_count}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Top Traces */}
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-900">Top Traces</h3>
                <select
                  value={sortBy}
                  onChange={e => setSortBy(e.target.value as any)}
                  className="text-sm border border-gray-300 rounded px-2 py-1"
                >
                  <option value="cost">By Cost</option>
                  <option value="latency">By Latency</option>
                  <option value="tokens">By Tokens</option>
                </select>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Spans</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tokens</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Cost</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {topTraces.map(t => (
                      <tr key={t.trace_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm">
                          <Link href={`/traces/${t.trace_id}`} className="text-blue-600 hover:text-blue-900 font-medium">
                            {t.name || 'Untitled'}
                          </Link>
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-600">{formatDuration(t.duration_ms)}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{t.span_count}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{formatTokens(t.total_tokens)}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{formatCost(t.total_cost)}</td>
                        <td className="px-4 py-2 text-sm text-gray-500">{formatRelativeTime(t.start_time)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Models Tab */}
        {activeTab === 'models' && (
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Model Usage & Cost</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Calls</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Prompt Tokens</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Completion Tokens</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Total Tokens</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Total Cost</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Avg Latency</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {models.map(m => (
                    <tr key={m.model} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-sm font-medium text-gray-900">{m.model}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">{m.call_count}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">{formatTokens(m.prompt_tokens)}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">{formatTokens(m.completion_tokens)}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">{formatTokens(m.total_tokens)}</td>
                      <td className="px-4 py-2 text-sm font-medium text-green-700">{formatCost(m.total_cost)}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">
                        {m.avg_latency_ms ? formatDuration(m.avg_latency_ms) : '-'}
                      </td>
                    </tr>
                  ))}
                  {models.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-gray-400">No model data available</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Cost bar chart */}
            {models.length > 0 && (
              <div className="mt-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Cost by Model</h4>
                <BarChart
                  data={models.map(m => ({ label: m.model, value: m.total_cost }))}
                  color="#10b981"
                  formatValue={v => formatCost(v)}
                />
              </div>
            )}
          </div>
        )}

        {/* Latency Tab */}
        {activeTab === 'latency' && (
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Latency by Span Type</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Span Type</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Count</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Avg</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Min</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Max</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {latencyByType.map(l => (
                    <tr key={l.span_type} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-sm font-medium text-gray-900 capitalize">{l.span_type}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">{l.count}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">{formatDuration(l.avg_ms)}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">{formatDuration(l.min_ms)}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">{formatDuration(l.max_ms)}</td>
                    </tr>
                  ))}
                  {latencyByType.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-gray-400">No latency data available</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Latency bar chart */}
            {latencyByType.length > 0 && (
              <div className="mt-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Average Latency by Type</h4>
                <BarChart
                  data={latencyByType.map(l => ({ label: l.span_type, value: l.avg_ms }))}
                  color="#6366f1"
                  formatValue={v => formatDuration(v)}
                />
              </div>
            )}
          </div>
        )}

        {/* Errors Tab */}
        {activeTab === 'errors' && (
          <div className="space-y-6">
            {/* Error Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white shadow rounded-lg p-5">
                <dt className="text-sm font-medium text-gray-500">Total Errors</dt>
                <dd className="text-3xl font-semibold text-red-600">{errors?.error_count || 0}</dd>
              </div>
              <div className="bg-white shadow rounded-lg p-5">
                <dt className="text-sm font-medium text-gray-500">Error Rate</dt>
                <dd className="text-3xl font-semibold text-gray-900">{((errors?.error_rate || 0) * 100).toFixed(1)}%</dd>
              </div>
              <div className="bg-white shadow rounded-lg p-5">
                <dt className="text-sm font-medium text-gray-500">Total Spans</dt>
                <dd className="text-3xl font-semibold text-gray-900">{errors?.total_spans || 0}</dd>
              </div>
            </div>

            {/* Errors by Type */}
            {errors && errors.by_type.length > 0 && (
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-sm font-semibold text-gray-900 mb-4">Errors by Span Type</h3>
                <BarChart
                  data={errors.by_type.map(e => ({ label: e.span_type, value: e.count }))}
                  color="#ef4444"
                  formatValue={v => v.toString()}
                />
              </div>
            )}

            {/* Recent Errors */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">Recent Errors</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Trace</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Span</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Error</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {(errors?.recent_errors || []).map(e => (
                      <tr key={e.span_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm">
                          <Link href={`/traces/${e.trace_id}`} className="text-blue-600 hover:text-blue-900">
                            {e.trace_name || e.trace_id.slice(0, 8)}
                          </Link>
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-600">{e.span_name}</td>
                        <td className="px-4 py-2 text-sm text-gray-600 capitalize">{e.span_type}</td>
                        <td className="px-4 py-2 text-sm">
                          <span className="text-red-600 font-medium">{e.error_type}</span>
                          {e.error_message && (
                            <p className="text-xs text-gray-500 truncate max-w-[200px]">{e.error_message}</p>
                          )}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-500">{formatRelativeTime(e.start_time)}</td>
                      </tr>
                    ))}
                    {(!errors?.recent_errors || errors.recent_errors.length === 0) && (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-gray-400">No errors recorded</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
