'use client'

import { useState } from 'react'
import { type Span } from '@/lib/api'
import { formatDuration, getSpanTypeColor, getSpanTypeIcon } from '@/lib/utils'
import { ChevronRight, ChevronDown } from 'lucide-react'

interface SpanTreeProps {
  spans: Span[]
}

export default function SpanTree({ spans }: SpanTreeProps) {
  // Build tree structure
  const spanMap = new Map(spans.map(s => [s.span_id, s]))
  const rootSpans = spans.filter(s => !s.parent_span_id || !spanMap.has(s.parent_span_id))

  return (
    <div className="space-y-2">
      {rootSpans.map(span => (
        <SpanNode key={span.span_id} span={span} allSpans={spans} depth={0} />
      ))}
    </div>
  )
}

interface SpanNodeProps {
  span: Span
  allSpans: Span[]
  depth: number
}

function SpanNode({ span, allSpans, depth }: SpanNodeProps) {
  const [expanded, setExpanded] = useState(true)
  const children = allSpans.filter(s => s.parent_span_id === span.span_id)
  const hasChildren = children.length > 0

  return (
    <div className="select-none">
      <div
        className={`flex items-center gap-2 p-2 rounded hover:bg-gray-50 cursor-pointer ${
          depth > 0 ? 'ml-6' : ''
        }`}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        {hasChildren && (
          <span className="text-gray-400">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </span>
        )}
        {!hasChildren && <span className="w-4" />}

        <span className={`inline-flex items-center justify-center w-6 h-6 rounded ${getSpanTypeColor(span.span_type)} text-white text-xs`}>
          {getSpanTypeIcon(span.span_type)}
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900 truncate">{span.name}</span>
            {span.model && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">{span.model}</span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
            <span>{formatDuration(span.end_time && span.start_time ? (span.end_time - span.start_time) * 1000 : 0)}</span>
            {span.total_tokens !== undefined && span.total_tokens > 0 && (
              <span>🔢 {span.total_tokens.toLocaleString()} tokens</span>
            )}
            {span.cost !== undefined && span.cost > 0 && (
              <span>💰 ${span.cost.toFixed(4)}</span>
            )}
          </div>
        </div>
      </div>

      {expanded && hasChildren && (
        <div className="mt-1">
          {children.map(child => (
            <SpanNode key={child.span_id} span={child} allSpans={allSpans} depth={depth + 1} />
          ))}
        </div>
      )}

      {/* Span details on click */}
      <SpanDetails span={span} />
    </div>
  )
}

function SpanDetails({ span }: { span: Span }) {
  const [showDetails, setShowDetails] = useState(false)

  if (!span.input_data && !span.output_data && !span.attributes) {
    return null
  }

  return (
    <div className="ml-14 mb-2">
      <button
        onClick={() => setShowDetails(!showDetails)}
        className="text-xs text-blue-600 hover:text-blue-900"
      >
        {showDetails ? 'Hide details' : 'Show details'}
      </button>

      {showDetails && (
        <div className="mt-2 space-y-2 text-xs">
          {span.input_data && (
            <div>
              <span className="font-medium text-gray-700">Input:</span>
              <pre className="mt-1 p-2 bg-gray-50 rounded overflow-auto max-h-40">
                {typeof span.input_data === 'string'
                  ? span.input_data
                  : JSON.stringify(span.input_data, null, 2)}
              </pre>
            </div>
          )}

          {span.output_data && (
            <div>
              <span className="font-medium text-gray-700">Output:</span>
              <pre className="mt-1 p-2 bg-gray-50 rounded overflow-auto max-h-40">
                {typeof span.output_data === 'string'
                  ? span.output_data
                  : JSON.stringify(span.output_data, null, 2)}
              </pre>
            </div>
          )}

          {span.attributes && Object.keys(span.attributes).length > 0 && (
            <div>
              <span className="font-medium text-gray-700">Attributes:</span>
              <pre className="mt-1 p-2 bg-gray-50 rounded overflow-auto max-h-40">
                {JSON.stringify(span.attributes, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
