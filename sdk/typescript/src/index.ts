/**
 * Agent Trace SDK for TypeScript/JavaScript
 */

export {
  Span,
  SpanEvent,
  SpanType,
  SpanStatus,
  Trace,
  createSpan,
  createTrace,
} from './models';

export { Tracer, getTracer, setTracer } from './tracer';

export { trace, traceLlm, safeSerialize } from './instrumentation';

export {
  Exporter,
  ConsoleExporter,
  FileExporter,
  HttpExporter,
  BatchExporter,
} from './exporters';

// OTel GenAI semantic conventions
export {
  spanTypeToOtelOperation,
  otelOperationToSpanType,
  enrichSpanWithOtel,
} from './otel-mapper';

export * from './otel-attributes';
