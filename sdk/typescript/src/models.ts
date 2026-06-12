/**
 * Data models for agent tracing
 */

export enum SpanType {
  AGENT = 'agent',
  LLM = 'llm',
  TOOL = 'tool',
  CHAIN = 'chain',
  RETRIEVER = 'retriever',
  EMBEDDING = 'embedding',
  FUNCTION = 'function',
  WORKFLOW = 'workflow',
  CHAT = 'chat',
}

export enum SpanStatus {
  OK = 'ok',
  ERROR = 'error',
  CANCELLED = 'cancelled',
}

export interface SpanEvent {
  timestamp: number;
  name: string;
  attributes: Record<string, any>;
}

export interface Span {
  traceId: string;
  spanId: string;
  name: string;
  spanType: SpanType;
  startTime: number;
  endTime?: number;
  parentSpanId?: string;
  status: SpanStatus;
  attributes: Record<string, any>;
  events: SpanEvent[];

  // LLM-specific fields
  model?: string;
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
  cost?: number;

  // OTel operation name (auto-derived from spanType if not set)
  otelOperation?: string;

  // Input/output
  inputData?: any;
  outputData?: any;
}

export interface Trace {
  traceId: string;
  name: string;
  startTime: number;
  endTime?: number;
  userId?: string;
  sessionId?: string;
  metadata: Record<string, any>;
  spans: Span[];
}

export function createSpan(
  traceId: string,
  name: string,
  spanType: SpanType,
  parentSpanId?: string,
  attributes?: Record<string, any>
): Span {
  return {
    traceId,
    spanId: crypto.randomUUID(),
    name,
    spanType,
    startTime: Date.now() / 1000,
    parentSpanId,
    status: SpanStatus.OK,
    attributes: attributes || {},
    events: [],
  };
}

export function createTrace(
  name: string,
  userId?: string,
  sessionId?: string,
  metadata?: Record<string, any>
): Trace {
  return {
    traceId: crypto.randomUUID(),
    name,
    startTime: Date.now() / 1000,
    userId,
    sessionId,
    metadata: metadata || {},
    spans: [],
  };
}
