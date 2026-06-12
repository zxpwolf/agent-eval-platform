'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  listDatasets,
  listEvaluators,
  listEvalRuns,
  createDataset,
  createEvaluator,
  type Dataset,
  type Evaluator,
  type EvalRun,
} from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { ArrowLeft, Database, TestTube, Play, Plus, RefreshCw } from 'lucide-react'

type Tab = 'datasets' | 'evaluators' | 'runs'

export default function EvaluationsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('datasets')
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [evaluators, setEvaluators] = useState<Evaluator[]>([])
  const [runs, setRuns] = useState<EvalRun[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateDataset, setShowCreateDataset] = useState(false)
  const [showCreateEvaluator, setShowCreateEvaluator] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [ds, ev, rn] = await Promise.all([
        listDatasets(),
        listEvaluators(),
        listEvalRuns(),
      ])
      setDatasets(ds.datasets)
      setEvaluators(ev.evaluators)
      setRuns(rn.runs)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateDataset = async (name: string, description: string) => {
    try {
      await createDataset(name, description)
      setShowCreateDataset(false)
      loadData()
    } catch (error) {
      console.error('Failed to create dataset:', error)
      alert('Failed to create dataset')
    }
  }

  const handleCreateEvaluator = async (
    name: string,
    type: string,
    config: Record<string, unknown>,
    description: string
  ) => {
    try {
      await createEvaluator(name, type, config, description)
      setShowCreateEvaluator(false)
      loadData()
    } catch (error) {
      console.error('Failed to create evaluator:', error)
      alert('Failed to create evaluator')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Link href="/" className="text-gray-600 hover:text-gray-900">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <h1 className="text-2xl font-bold text-gray-900">Evaluations</h1>
            </div>
            <button
              onClick={loadData}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <StatCard icon={<Database className="w-5 h-5 text-blue-600" />} label="Datasets" value={String(datasets.length)} />
          <StatCard icon={<TestTube className="w-5 h-5 text-green-600" />} label="Evaluators" value={String(evaluators.length)} />
          <StatCard icon={<Play className="w-5 h-5 text-purple-600" />} label="Runs" value={String(runs.length)} />
        </div>

        {/* Tabs */}
        <div className="bg-white shadow rounded-lg">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              {(['datasets', 'evaluators', 'runs'] as Tab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-6 py-3 text-sm font-medium border-b-2 capitalize ${
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

          <div className="p-6">
            {activeTab === 'datasets' && (
              <DatasetsTab
                datasets={datasets}
                onCreateNew={() => setShowCreateDataset(true)}
              />
            )}
            {activeTab === 'evaluators' && (
              <EvaluatorsTab
                evaluators={evaluators}
                onCreateNew={() => setShowCreateEvaluator(true)}
              />
            )}
            {activeTab === 'runs' && <RunsTab runs={runs} />}
          </div>
        </div>
      </main>

      {/* Create Dataset Modal */}
      {showCreateDataset && (
        <CreateDatasetModal
          onClose={() => setShowCreateDataset(false)}
          onCreate={handleCreateDataset}
        />
      )}

      {/* Create Evaluator Modal */}
      {showCreateEvaluator && (
        <CreateEvaluatorModal
          onClose={() => setShowCreateEvaluator(false)}
          onCreate={handleCreateEvaluator}
        />
      )}
    </div>
  )
}

// ── Tab Components ───────────────────────────────────────────

function DatasetsTab({
  datasets,
  onCreateNew,
}: {
  datasets: Dataset[]
  onCreateNew: () => void
}) {
  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Datasets</h3>
        <button
          onClick={onCreateNew}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          New Dataset
        </button>
      </div>
      {datasets.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No datasets yet. Create one to get started.</p>
      ) : (
        <div className="divide-y divide-gray-200">
          {datasets.map((ds) => (
            <Link
              key={ds.dataset_id}
              href={`/evaluations/datasets/${ds.dataset_id}`}
              className="block py-3 hover:bg-gray-50 -mx-2 px-2 rounded"
            >
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-sm font-medium text-gray-900">{ds.name}</p>
                  <p className="text-xs text-gray-500">{ds.description || 'No description'}</p>
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>{ds.item_count ?? 0} items</span>
                  <span>{formatRelativeTime(ds.created_at)}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function EvaluatorsTab({
  evaluators,
  onCreateNew,
}: {
  evaluators: Evaluator[]
  onCreateNew: () => void
}) {
  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Evaluators</h3>
        <button
          onClick={onCreateNew}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          New Evaluator
        </button>
      </div>
      {evaluators.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No evaluators yet.</p>
      ) : (
        <div className="divide-y divide-gray-200">
          {evaluators.map((ev) => (
            <div key={ev.evaluator_id} className="py-3">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-sm font-medium text-gray-900">{ev.name}</p>
                  <p className="text-xs text-gray-500">{ev.description || 'No description'}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 capitalize">
                    {ev.evaluator_type}
                  </span>
                  <span className="text-xs text-gray-500">{formatRelativeTime(ev.created_at)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RunsTab({ runs }: { runs: EvalRun[] }) {
  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800'
      case 'running': return 'bg-blue-100 text-blue-800'
      case 'pending': return 'bg-yellow-100 text-yellow-800'
      case 'failed': return 'bg-red-100 text-red-800'
      case 'cancelled': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div>
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Evaluation Runs</h3>
      {runs.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No evaluation runs yet.</p>
      ) : (
        <div className="divide-y divide-gray-200">
          {runs.map((run) => (
            <Link
              key={run.run_id}
              href={`/evaluations/runs/${run.run_id}`}
              className="block py-3 hover:bg-gray-50 -mx-2 px-2 rounded"
            >
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-sm font-medium text-gray-900 font-mono">{run.run_id.slice(0, 8)}...</p>
                  <p className="text-xs text-gray-500">
                    {run.evaluator_ids.length} evaluator(s)
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {run.live_status && (
                    <span className="text-xs text-blue-600">
                      {run.live_status.completed}/{run.live_status.total}
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${statusColor(run.status)}`}>
                    {run.status}
                  </span>
                  <span className="text-xs text-gray-500">{formatRelativeTime(run.started_at)}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Modal Components ─────────────────────────────────────────

function CreateDatasetModal({
  onClose,
  onCreate,
}: {
  onClose: () => void
  onCreate: (name: string, description: string) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-4">Create Dataset</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              placeholder="My evaluation dataset"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              rows={3}
              placeholder="Optional description"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => name.trim() && onCreate(name.trim(), description.trim())}
            disabled={!name.trim()}
            className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  )
}

function CreateEvaluatorModal({
  onClose,
  onCreate,
}: {
  onClose: () => void
  onCreate: (name: string, type: string, config: Record<string, unknown>, description: string) => void
}) {
  const [name, setName] = useState('')
  const [evalType, setEvalType] = useState('heuristic')
  const [heuristicType, setHeuristicType] = useState('contains')
  const [heuristicValue, setHeuristicValue] = useState('')
  const [description, setDescription] = useState('')

  const buildConfig = (): Record<string, unknown> => {
    if (evalType === 'heuristic') {
      const config: Record<string, unknown> = { type: heuristicType }
      if (['contains', 'regex', 'exact_match', 'keyword'].includes(heuristicType)) {
        config.value = heuristicValue
      }
      return config
    }
    return {}
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-4">Create Evaluator</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              placeholder="My evaluator"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              value={evalType}
              onChange={(e) => setEvalType(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="heuristic">Heuristic</option>
              <option value="llm_judge">LLM Judge</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          {evalType === 'heuristic' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Heuristic Type</label>
                <select
                  value={heuristicType}
                  onChange={(e) => setHeuristicType(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                >
                  <option value="contains">Contains</option>
                  <option value="regex">Regex Match</option>
                  <option value="exact_match">Exact Match</option>
                  <option value="json_valid">JSON Valid</option>
                  <option value="keyword">Keyword</option>
                  <option value="length">Length</option>
                </select>
              </div>
              {['contains', 'regex', 'exact_match', 'keyword'].includes(heuristicType) && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
                  <input
                    type="text"
                    value={heuristicValue}
                    onChange={(e) => setHeuristicValue(e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                    placeholder="Value to match"
                  />
                </div>
              )}
            </>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              rows={2}
              placeholder="Optional description"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => name.trim() && onCreate(name.trim(), evalType, buildConfig(), description.trim())}
            disabled={!name.trim()}
            className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Utility Components ───────────────────────────────────────

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
