'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  getReplayStatus,
  pauseReplay,
  resumeReplay,
  stopReplay,
  stepReplay,
  type ReplayStatus,
} from '@/lib/api'
import { Play, Pause, Square, SkipForward, RefreshCw } from 'lucide-react'

interface ReplayPlayerProps {
  sessionId: string
}

export default function ReplayPlayer({ sessionId }: ReplayPlayerProps) {
  const [status, setStatus] = useState<ReplayStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      const data = await getReplayStatus(sessionId)
      setStatus(data)
    } catch (error) {
      console.error('Failed to load replay status:', error)
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    loadStatus()

    // Poll for status updates when running
    const interval = setInterval(() => {
      if (status?.status === 'running') {
        loadStatus()
      }
    }, 1000)

    setPollingInterval(interval)

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [loadStatus, status?.status])

  const handlePause = async () => {
    await pauseReplay(sessionId)
    loadStatus()
  }

  const handleResume = async () => {
    await resumeReplay(sessionId)
    loadStatus()
  }

  const handleStop = async () => {
    await stopReplay(sessionId)
    loadStatus()
  }

  const handleStep = async () => {
    await stepReplay(sessionId)
    loadStatus()
  }

  if (loading || !status) {
    return (
      <div className="bg-white shadow rounded-lg p-4">
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
        </div>
      </div>
    )
  }

  const isRunning = status.status === 'running'
  const isPaused = status.status === 'paused'
  const isCompleted = status.status === 'completed'

  return (
    <div className="bg-white shadow rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Replay Player</h3>
          <p className="text-xs text-gray-500">{sessionId}</p>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-medium ${
          isRunning ? 'bg-green-100 text-green-800' :
          isPaused ? 'bg-yellow-100 text-yellow-800' :
          isCompleted ? 'bg-blue-100 text-blue-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {status.status}
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-gray-600 mb-1">
          <span>Progress</span>
          <span>{status.progress.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all"
            style={{ width: `${status.progress}%` }}
          ></div>
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>{status.current_index} / {status.total_calls} calls</span>
          <span>{status.replayed_calls_count} replayed</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        {!isRunning && !isCompleted && (
          <button
            onClick={handleResume}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-white bg-green-600 rounded hover:bg-green-700"
          >
            <Play className="w-4 h-4" />
            Resume
          </button>
        )}

        {isRunning && (
          <button
            onClick={handlePause}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-white bg-yellow-600 rounded hover:bg-yellow-700"
          >
            <Pause className="w-4 h-4" />
            Pause
          </button>
        )}

        <button
          onClick={handleStep}
          disabled={isRunning || isCompleted}
          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <SkipForward className="w-4 h-4" />
          Step
        </button>

        {(isRunning || isPaused) && (
          <button
            onClick={handleStop}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded hover:bg-red-700"
          >
            <Square className="w-4 h-4" />
            Stop
          </button>
        )}

        {isCompleted && (
          <button
            onClick={loadStatus}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        )}
      </div>

      {/* Error message */}
      {status.error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
          <p className="text-sm text-red-800">{status.error}</p>
        </div>
      )}
    </div>
  )
}
