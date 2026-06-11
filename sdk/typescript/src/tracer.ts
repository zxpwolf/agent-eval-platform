/**
 * Core tracer for TypeScript/JavaScript
 */

import { Span, SpanType, SpanStatus, Trace, createSpan, createTrace } from './models';
import { Exporter } from './exporters';

interface SpanContext {
  trace: Trace;
  span: Span;
}

export class Tracer {
  private activeTraces: Map<string, Trace> = new Map();
  private currentSpanContext: SpanContext | null = null;
  private exporter?: Exporter;

  constructor(private projectName: string = 'default') {}

  setExporter(exporter: Exporter) {
    this.exporter = exporter;
  }

  startTrace(
    name: string,
    userId?: string,
    sessionId?: string,
    metadata?: Record<string, any>
  ): Trace {
    const trace = createTrace(name, userId, sessionId, metadata);
    this.activeTraces.set(trace.traceId, trace);
    return trace;
  }

  endTrace(traceId: string): Trace | undefined {
    const trace = this.activeTraces.get(traceId);
    if (trace) {
      this.activeTraces.delete(traceId);
      trace.endTime = Date.now() / 1000;

      // Export if exporter is configured
      if (this.exporter) {
        this.exporter.export(trace).catch(err => {
          console.error('Failed to export trace:', err);
        });
      }
    }
    return trace;
  }

  getActiveTrace(): Trace | undefined {
    return this.currentSpanContext?.trace;
  }

  startSpan(
    name: string,
    spanType: SpanType,
    parentSpanId?: string,
    attributes?: Record<string, any>
  ): Span {
    let trace: Trace;

    if (this.currentSpanContext) {
      trace = this.currentSpanContext.trace;
      if (!parentSpanId) {
        parentSpanId = this.currentSpanContext.span.spanId;
      }
    } else {
      // Auto-create trace if not exists
      trace = this.startTrace(`auto_${name}`);
    }

    const span = createSpan(trace.traceId, name, spanType, parentSpanId, attributes);
    trace.spans.push(span);

    // Set as current context
    this.currentSpanContext = { trace, span };

    return span;
  }

  endSpan(span: Span, status: SpanStatus = SpanStatus.OK, outputData?: any): Span {
    span.endTime = Date.now() / 1000;
    span.status = status;
    if (outputData !== undefined) {
      span.outputData = outputData;
    }

    // Restore parent context
    if (this.currentSpanContext && this.currentSpanContext.span.parentSpanId) {
      const parentSpan = this.currentSpanContext.trace.spans.find(
        s => s.spanId === this.currentSpanContext!.span.parentSpanId
      );
      if (parentSpan) {
        this.currentSpanContext = {
          trace: this.currentSpanContext.trace,
          span: parentSpan,
        };
      }
    } else {
      this.currentSpanContext = null;
    }

    return span;
  }

  recordEvent(span: Span, name: string, attributes: Record<string, any>): void {
    span.events.push({
      timestamp: Date.now() / 1000,
      name,
      attributes,
    });
  }

  recordLlmCall(
    span: Span,
    model: string,
    promptTokens: number,
    completionTokens: number,
    cost?: number
  ): void {
    span.model = model;
    span.promptTokens = promptTokens;
    span.completionTokens = completionTokens;
    span.totalTokens = promptTokens + completionTokens;
    span.cost = cost;
  }

  recordError(span: Span, error: Error): void {
    span.status = SpanStatus.ERROR;
    this.recordEvent(span, 'exception', {
      type: error.name,
      message: error.message,
      stack: error.stack,
    });
  }
}

// Global tracer instance
let defaultTracer: Tracer | null = null;

export function getTracer(): Tracer {
  if (!defaultTracer) {
    defaultTracer = new Tracer();
  }
  return defaultTracer;
}

export function setTracer(tracer: Tracer): void {
  defaultTracer = tracer;
}
