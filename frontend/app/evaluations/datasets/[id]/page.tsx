'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  getDataset,
  addDatasetItems,
  deleteDatasetItem,
  startEvalRun,
  listEvaluators,
  type Dataset,
  type DatasetItem,
  type Evaluator,
} from '@/lib/api'
import { formatTimestamp } from '@/lib/utils'
import { ArrowLeft, Plus, Trash2, Play } from 'lucide-react'

export default function DatasetDetailPage() {
  const params = useParams()
  const datasetId = params.id as string

  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [evaluators, setEvaluators] = useState<Evaluator[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddItem, setShowAddItem] = useState(false)
  const [showRunEval, setShowRunEval] = useState(false)
  const [selectedEvaluators, setSelectedEvaluators] = useState<string[]>([])

  useEffect(() => {
    loadData()
  }, [datasetId])

  const loadData = async () => {
    try {
      setLoading(true)
      const [ds, ev] = await Promise.all([getDataset(datasetId), listEvaluators()])
      setDataset(ds)
      setEvaluators(ev.evaluators)
    } catch (error) {
      console.error('Failed to load dataset:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddItem = async (input: string, expected: string) => {
    try {
      await addDatasetItems(datasetId, [
        {
          input_data: input,
          expected_output: expected,
        },
      ])
      setShowAddItem(false)
      loadData()
    } catch (error) {
      console.error('Failed to add item:', error)
      alert('Failed to add item')
    }
  }

  const handleDeleteItem = async (itemId: string) => {
    if (!confirm('Delete this item?')) return
    try {
      await deleteDatasetItem(datasetId, itemId)
      loadData()
    } catch (error) {
      console.error('Failed to delete item:', error)
    }
  }

  const handleStartEvalRun = async () => {
    if (selectedEvaluators.length === 0) {
      alert('Select at least one evaluator')
      return
    }
    try {
      const result = await startEvalRun(datasetId, selectedEvaluators)
      alert(`Evaluation run started: ${result.run_id}`)
      setShowRunEval(false)
      setSelectedEvaluators([])
    } catch (error) {
      console.error('Failed to start eval run:', error)
      alert('Failed to start evaluation run')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading dataset...</p>
        </div>
      </div>
    )
  }

  if (!dataset) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Dataset not found</p>
          <Link href="/evaluations" className="text-blue-600 hover:text-blue-900 mt-2 inline-block">
            Back to evaluations
          </Link>
        </div>
      </div>
    )
  }

  const items = dataset.items || []

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
                <h1 className="text-xl font-bold text-gray-900">{dataset.name}</h1>
                <p className="text-sm text-gray-500">{dataset.description || 'No description'}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowRunEval(true)}
                disabled={evaluators.length === 0 || items.length === 0}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                Run Evaluation
              </button>
              <button
                onClick={() => setShowAddItem(true)}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                <Plus className="w-4 h-4" />
                Add Item
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-900">Dataset Items ({items.length})</h2>
          </div>

          {items.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              No items in this dataset yet. Add some evaluation data!
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {items.map((item: DatasetItem) => (
                <div key={item.item_id} className="px-6 py-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">Input</p>
                        <pre className="text-sm text-gray-900 bg-gray-50 p-2 rounded overflow-auto max-h-32">
                          {typeof item.input_data === 'string'
                            ? item.input_data
                            : JSON.stringify(item.input_data, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">Expected Output</p>
                        <pre className="text-sm text-gray-900 bg-gray-50 p-2 rounded overflow-auto max-h-32">
                          {typeof item.expected_output === 'string'
                            ? item.expected_output
                            : JSON.stringify(item.expected_output, null, 2)}
                        </pre>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteItem(item.item_id)}
                      className="ml-4 text-gray-400 hover:text-red-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Add Item Modal */}
      {showAddItem && (
        <AddItemModal onClose={() => setShowAddItem(false)} onAdd={handleAddItem} />
      )}

      {/* Run Evaluation Modal */}
      {showRunEval && (
        <RunEvalModal
          evaluators={evaluators}
          selectedEvaluators={selectedEvaluators}
          onToggleEvaluator={(id) => {
            setSelectedEvaluators((prev) =>
              prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
            )
          }}
          onStart={handleStartEvalRun}
          onClose={() => setShowRunEval(false)}
        />
      )}
    </div>
  )
}

function AddItemModal({
  onClose,
  onAdd,
}: {
  onClose: () => void
  onAdd: (input: string, expected: string) => void
}) {
  const [input, setInput] = useState('')
  const [expected, setExpected] = useState('')

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-lg">
        <h3 className="text-lg font-semibold mb-4">Add Dataset Item</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Input Data</label>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono"
              rows={4}
              placeholder="Enter input data..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Expected Output</label>
            <textarea
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono"
              rows={4}
              placeholder="Enter expected output..."
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
            onClick={() => input.trim() && onAdd(input.trim(), expected.trim())}
            disabled={!input.trim()}
            className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  )
}

function RunEvalModal({
  evaluators,
  selectedEvaluators,
  onToggleEvaluator,
  onStart,
  onClose,
}: {
  evaluators: Evaluator[]
  selectedEvaluators: string[]
  onToggleEvaluator: (id: string) => void
  onStart: () => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-4">Run Evaluation</h3>
        <p className="text-sm text-gray-600 mb-4">Select evaluators to run against this dataset:</p>
        <div className="space-y-2 max-h-60 overflow-y-auto">
          {evaluators.map((ev) => (
            <label key={ev.evaluator_id} className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded cursor-pointer">
              <input
                type="checkbox"
                checked={selectedEvaluators.includes(ev.evaluator_id)}
                onChange={() => onToggleEvaluator(ev.evaluator_id)}
                className="rounded border-gray-300"
              />
              <div>
                <p className="text-sm font-medium text-gray-900">{ev.name}</p>
                <p className="text-xs text-gray-500 capitalize">{ev.evaluator_type}</p>
              </div>
            </label>
          ))}
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={onStart}
            disabled={selectedEvaluators.length === 0}
            className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            Start Run
          </button>
        </div>
      </div>
    </div>
  )
}
