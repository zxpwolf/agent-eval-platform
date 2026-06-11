'use client'

import { type Span } from '@/lib/api'
import { formatDuration, getSpanTypeColor, getSpanTypeIcon } from '@/lib/utils'

interface TimelineViewProps {
  spans: Span[]
}

export default function TimelineView({ spans }: TimelineViewProps) {
  if (spans.length === 0) return null

  // Calculate timeline bounds
  const startTime = Math.min(...spans.map(s => s.start_time))
  const endTime = Math.max(...spans.filter(s => s.end_time).map(s => s.end_time!))
  const totalTime = endTime - startTime || 1

  // Sort spans by start time
  const sortedSpans = [...spans].sort((a, b) => a.start_time - b.start_time)

  return (
    <div className="space-y-2">
      {/* Time axis */}
      <div className="relative h-6 border-b border-gray-200 mb-4">
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
          <div
            key={ratio}
            className="absolute bottom-0 text-xs text-gray-400"
            style={{ left: `${ratio * 100}%` }}
          >
            {formatDuration(totalTime * ratio * 1000)}
          </div>
        ))}
      </div>

      {/* Spans */}
      <div className="space-y-1">
        {sortedSpans.map((span) => {
          const left = ((span.start_time - startTime) / totalTime) * 100
          const width = span.end_time
            ? ((span.end_time - span.start_time) / totalTime) * 100
            : 2

          return (
            <div key={span.span_id} className="relative h-8">
              <div
                className={`absolute rounded ${getSpanTypeColor(span.span_type)} bg-opacity-20 border-2 border-${getSpanTypeColor(span.span_type).replace('bg-', '')} hover:bg-opacity-30 transition-all cursor-pointer`}
                style={{
                  left: `${left}%`,
                  width: `${Math.max(width, 1)}%`,
                  top: 0,
                  height: '100%',
                }}
                title={`${span.name}\n${formatDuration(span.end_time && span.start_time ? (span.end_time - span.start_time) * 1000 : 0)}`}
              >
                <div className="flex items-center h-full px-2 overflow-hidden">
                  <span className="text-xs font-medium text-gray-700 truncate whitespace-nowrap">
                    {getSpanTypeIcon(span.span_type)} {span.name}
                  </span>
                </div>
              </div>

              {/* Tooltip on hover */}
              <div className="absolute top-full left-0 mt-1 hidden group-hover:block">
                <div className="bg-gray-900 text-white text-xs rounded p-2 whitespace-nowrap z-10">
                  <div className="font-semibold">{span.name}</div>
                  <div>Duration: {formatDuration(span.end_time && span.start_time ? (span.end_time - span.start_time) * 1000 : 0)}</div>
                  {span.model && <div>Model: {span.model}</div>}
                  {span.total_tokens !== undefined && <div>Tokens: {span.total_tokens}</div>}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <div className="text-sm font-medium text-gray-700 mb-2">Legend</div>
        <div className="flex flex-wrap gap-3">
          {['agent', 'llm', 'tool', 'chain', 'retriever', 'function'].map((type) => (
            <div key={type} className="flex items-center gap-2">
              <div className={`w-4 h-4 rounded ${getSpanTypeColor(type)}`}></div>
              <span className="text-xs text-gray-600 capitalize">{type}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
