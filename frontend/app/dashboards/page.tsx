'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { ArrowLeft, Plus, Trash2, Save, GripVertical, RefreshCw, LayoutDashboard } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Types ────────────────────────────────────────────────

interface Widget {
  widget_id: string
  dashboard_id: string
  widget_type: string
  title: string
  config: Record<string, unknown>
  position_x: number
  position_y: number
  width: number
  height: number
}

interface Dashboard {
  dashboard_id: string
  name: string
  description: string
  owner_id: string | null
  layout: unknown[]
  is_public: boolean
  widgets: Widget[]
}

interface DashboardListItem {
  dashboard_id: string
  name: string
  description: string
  is_public: boolean
  widget_count: number
  updated_at: string | null
}

interface WidgetTypeOption {
  type: string
  default_config: Record<string, unknown>
}

const WIDGET_TYPE_LABELS: Record<string, string> = {
  stat_card: 'Stat Card',
  time_series: 'Time Series Chart',
  model_table: 'Model Usage Table',
  error_table: 'Error Table',
  top_traces: 'Top Traces',
  span_type_pie: 'Span Type Distribution',
  cost_breakdown: 'Cost Breakdown',
  latency_chart: 'Latency Chart',
  custom_query: 'Custom Query',
}

const WIDGET_COLORS: Record<string, string> = {
  stat_card: 'border-blue-300 bg-blue-50',
  time_series: 'border-green-300 bg-green-50',
  model_table: 'border-purple-300 bg-purple-50',
  error_table: 'border-red-300 bg-red-50',
  top_traces: 'border-yellow-300 bg-yellow-50',
  span_type_pie: 'border-indigo-300 bg-indigo-50',
  cost_breakdown: 'border-emerald-300 bg-emerald-50',
  latency_chart: 'border-orange-300 bg-orange-50',
  custom_query: 'border-gray-300 bg-gray-50',
}

// ── Main Page ────────────────────────────────────────────

export default function DashboardsPage() {
  const [dashboards, setDashboards] = useState<DashboardListItem[]>([])
  const [currentDashboard, setCurrentDashboard] = useState<Dashboard | null>(null)
  const [widgetTypes, setWidgetTypes] = useState<WidgetTypeOption[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [showAddWidget, setShowAddWidget] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newWidgetType, setNewWidgetType] = useState('stat_card')
  const [newWidgetTitle, setNewWidgetTitle] = useState('')

  const loadDashboards = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboards/`)
      const data = await res.json()
      setDashboards(data.dashboards || [])
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const loadWidgetTypes = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboards/widget-types`)
      const data = await res.json()
      setWidgetTypes(data.widget_types || [])
    } catch (e) { console.error(e) }
  }

  const loadDashboard = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboards/${id}`)
      const data = await res.json()
      setCurrentDashboard(data)
    } catch (e) { console.error(e) }
  }

  useEffect(() => { loadDashboards(); loadWidgetTypes() }, [])

  const createDashboard = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboards/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, description: newDesc }),
      })
      const data = await res.json()
      setShowCreate(false)
      setNewName('')
      setNewDesc('')
      loadDashboards()
      loadDashboard(data.dashboard_id)
    } catch (e) { console.error(e) }
  }

  const deleteDashboard = async (id: string) => {
    if (!confirm('Delete this dashboard?')) return
    try {
      await fetch(`${API_BASE}/api/dashboards/${id}`, { method: 'DELETE' })
      if (currentDashboard?.dashboard_id === id) setCurrentDashboard(null)
      loadDashboards()
    } catch (e) { console.error(e) }
  }

  const addWidget = async () => {
    if (!currentDashboard) return
    try {
      const wt = widgetTypes.find(w => w.type === newWidgetType)
      await fetch(`${API_BASE}/api/dashboards/${currentDashboard.dashboard_id}/widgets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          widget_type: newWidgetType,
          title: newWidgetTitle || WIDGET_TYPE_LABELS[newWidgetType] || newWidgetType,
          config: wt?.default_config || {},
          position_x: 0,
          position_y: currentDashboard.widgets.length,
        }),
      })
      setShowAddWidget(false)
      setNewWidgetTitle('')
      loadDashboard(currentDashboard.dashboard_id)
    } catch (e) { console.error(e) }
  }

  const removeWidget = async (widgetId: string) => {
    if (!currentDashboard) return
    try {
      await fetch(`${API_BASE}/api/dashboards/${currentDashboard.dashboard_id}/widgets/${widgetId}`, {
        method: 'DELETE',
      })
      loadDashboard(currentDashboard.dashboard_id)
    } catch (e) { console.error(e) }
  }

  const saveLayout = async () => {
    if (!currentDashboard) return
    try {
      const widgets = currentDashboard.widgets.map((w, i) => ({
        widget_id: w.widget_id,
        position_x: w.position_x,
        position_y: i,
      }))
      await fetch(`${API_BASE}/api/dashboards/${currentDashboard.dashboard_id}/widgets/batch`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ widgets }),
      })
    } catch (e) { console.error(e) }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
      </div>
    )
  }

  // ── Dashboard detail view ──
  if (currentDashboard) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
            <div className="flex items-center gap-4">
              <button onClick={() => setCurrentDashboard(null)} className="text-gray-500 hover:text-gray-700">
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-xl font-bold text-gray-900">{currentDashboard.name}</h1>
                {currentDashboard.description && (
                  <p className="text-sm text-gray-500">{currentDashboard.description}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowAddWidget(true)}
                className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
              >
                <Plus className="w-4 h-4" /> Add Widget
              </button>
              <button
                onClick={saveLayout}
                className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                <Save className="w-4 h-4" /> Save Layout
              </button>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-6">
          {/* Widget Grid */}
          {currentDashboard.widgets.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <LayoutDashboard className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg">No widgets yet</p>
              <p className="text-sm mt-1">Click "Add Widget" to start building your dashboard</p>
            </div>
          ) : (
            <div className="grid grid-cols-12 gap-4">
              {currentDashboard.widgets.map((widget) => (
                <div
                  key={widget.widget_id}
                  className={`col-span-${Math.min(widget.width, 12)} border-2 rounded-lg p-4 ${WIDGET_COLORS[widget.widget_type] || 'border-gray-300 bg-gray-50'}`}
                  style={{ gridColumn: `span ${Math.min(widget.width, 12)}` }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <GripVertical className="w-4 h-4 text-gray-400 cursor-grab" />
                      <h3 className="text-sm font-semibold text-gray-900">{widget.title}</h3>
                      <span className="text-xs px-2 py-0.5 bg-white rounded-full text-gray-500 border">
                        {WIDGET_TYPE_LABELS[widget.widget_type] || widget.widget_type}
                      </span>
                    </div>
                    <button
                      onClick={() => removeWidget(widget.widget_id)}
                      className="text-gray-400 hover:text-red-500"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  {/* Widget preview placeholder */}
                  <WidgetPreview widget={widget} />
                </div>
              ))}
            </div>
          )}
        </main>

        {/* Add Widget Modal */}
        {showAddWidget && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-md">
              <h2 className="text-lg font-bold mb-4">Add Widget</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Widget Type</label>
                  <select
                    value={newWidgetType}
                    onChange={e => setNewWidgetType(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  >
                    {Object.entries(WIDGET_TYPE_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                  <input
                    type="text"
                    value={newWidgetTitle}
                    onChange={e => setNewWidgetTitle(e.target.value)}
                    placeholder={WIDGET_TYPE_LABELS[newWidgetType] || 'Widget Title'}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div className="flex gap-3 justify-end">
                  <button onClick={() => setShowAddWidget(false)} className="px-4 py-2 text-sm border rounded-md">Cancel</button>
                  <button onClick={addWidget} className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700">Add</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Dashboard list view ──
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-500 hover:text-gray-700">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Dashboards</h1>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" /> New Dashboard
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {dashboards.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <LayoutDashboard className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg">No dashboards yet</p>
            <p className="text-sm mt-1">Create your first custom dashboard</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dashboards.map(d => (
              <div
                key={d.dashboard_id}
                className="bg-white shadow rounded-lg p-5 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => loadDashboard(d.dashboard_id)}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">{d.name}</h3>
                    {d.description && <p className="text-sm text-gray-500 mt-1">{d.description}</p>}
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); deleteDashboard(d.dashboard_id) }}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex items-center gap-3 mt-3 text-xs text-gray-500">
                  <span>{d.widget_count} widgets</span>
                  {d.is_public && <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full">Public</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Create Dashboard Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">New Dashboard</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="My Dashboard"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={newDesc}
                  onChange={e => setNewDesc(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Optional description"
                />
              </div>
              <div className="flex gap-3 justify-end">
                <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm border rounded-md">Cancel</button>
                <button onClick={createDashboard} className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700">Create</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Widget Preview Component ────────────────────────────

function WidgetPreview({ widget }: { widget: Widget }) {
  const [data, setData] = useState<unknown>(null)
  const [error, setError] = useState('')

  const fetchWidgetData = useCallback(async () => {
    try {
      let url = ''
      const cfg = widget.config as Record<string, string>
      switch (widget.widget_type) {
        case 'stat_card':
          url = `${API_BASE}/api/traces/stats/summary`
          break
        case 'time_series':
          url = `${API_BASE}/api/analytics/timeseries?granularity=${cfg.granularity || 'hour'}&limit=${cfg.limit || 48}`
          break
        case 'model_table':
          url = `${API_BASE}/api/analytics/models`
          break
        case 'error_table':
          url = `${API_BASE}/api/analytics/errors`
          break
        case 'top_traces':
          url = `${API_BASE}/api/analytics/top-traces?sort_by=${cfg.sort_by || 'cost'}&limit=${cfg.limit || 10}`
          break
        case 'span_type_pie':
          url = `${API_BASE}/api/analytics/span-types`
          break
        case 'cost_breakdown':
          url = `${API_BASE}/api/analytics/models`
          break
        case 'latency_chart':
          url = `${API_BASE}/api/analytics/latency`
          break
        default:
          setError('No data source configured')
          return
      }
      const res = await fetch(url)
      setData(await res.json())
    } catch (e) {
      setError('Failed to load data')
    }
  }, [widget])

  useEffect(() => { fetchWidgetData() }, [fetchWidgetData])

  if (error) return <p className="text-sm text-red-500">{error}</p>
  if (!data) return <div className="animate-pulse h-20 bg-gray-200 rounded"></div>

  // Render based on widget type
  switch (widget.widget_type) {
    case 'stat_card':
      return <StatCardPreview data={data as Record<string, number>} config={widget.config as Record<string, string>} />
    case 'model_table':
    case 'top_traces':
    case 'error_table':
      return <TablePreview data={data} widgetType={widget.widget_type} />
    case 'time_series':
    case 'span_type_pie':
    case 'cost_breakdown':
    case 'latency_chart':
      return <ChartPreview data={data} widgetType={widget.widget_type} />
    default:
      return <p className="text-sm text-gray-500">Widget preview not available</p>
  }
}

function StatCardPreview({ data, config }: { data: Record<string, number>; config: Record<string, string> }) {
  const metric = config.metric || 'trace_count'
  const value = data[metric]
  return (
    <div className="text-center py-4">
      <p className="text-4xl font-bold text-gray-900">{value !== undefined ? value.toLocaleString() : 'N/A'}</p>
      <p className="text-sm text-gray-500 mt-1">{config.label || metric.replace(/_/g, ' ')}</p>
    </div>
  )
}

function TablePreview({ data, widgetType }: { data: unknown; widgetType: string }) {
  const d = data as Record<string, unknown[]>
  const items = (d.models || d.traces || d.recent_errors || d.span_types || []) as Record<string, unknown>[]
  if (items.length === 0) return <p className="text-sm text-gray-400">No data</p>
  const keys = Object.keys(items[0]).slice(0, 4)
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-xs">
        <thead><tr>{keys.map(k => <th key={k} className="px-2 py-1 text-left text-gray-500 font-medium">{k}</th>)}</tr></thead>
        <tbody>
          {items.slice(0, 5).map((item, i) => (
            <tr key={i} className="border-t">{keys.map(k => <td key={k} className="px-2 py-1 text-gray-700">{String(item[k] ?? '')}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ChartPreview({ data, widgetType }: { data: unknown; widgetType: string }) {
  const d = data as Record<string, unknown[]>
  const items = (d.trace_series || d.cost_series || d.span_types || d.by_type || []) as Record<string, unknown>[]
  if (items.length === 0) return <p className="text-sm text-gray-400">No data for chart</p>
  const maxVal = Math.max(...items.map((i: Record<string, unknown>) => Number(i.count || i.value || i.cost || i.total || 1)), 1)
  return (
    <div className="flex items-end gap-1 h-24">
      {items.slice(0, 24).map((item: Record<string, unknown>, i: number) => {
        const val = Number(item.count || item.value || item.cost || item.total || 0)
        const h = (val / maxVal) * 100
        return <div key={i} className="flex-1 bg-blue-400 rounded-t opacity-70 hover:opacity-100 transition-opacity" style={{ height: `${Math.max(h, 2)}%` }} title={`${val}`} />
      })}
    </div>
  )
}
