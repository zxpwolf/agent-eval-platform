/**
 * Tests for TypeScript SDK
 */

import { Tracer, SpanType, SpanStatus, FileExporter } from './index';
import * as fs from 'fs';
import * as path from 'path';

describe('Tracer', () => {
  let tracer: Tracer;

  beforeEach(() => {
    tracer = new Tracer('test');
  });

  test('should create and end trace', () => {
    const trace = tracer.startTrace('test_trace', 'user_1');
    expect(trace.traceId).toBeDefined();
    expect(trace.name).toBe('test_trace');

    const endedTrace = tracer.endTrace(trace.traceId);
    expect(endedTrace).toBeDefined();
    expect(endedTrace?.endTime).toBeDefined();
  });

  test('should create spans with parent-child relationship', () => {
    const trace = tracer.startTrace('test');

    const parentSpan = tracer.startSpan('parent', SpanType.AGENT);
    const childSpan = tracer.startSpan('child', SpanType.FUNCTION, parentSpan.spanId);

    expect(childSpan.parentSpanId).toBe(parentSpan.spanId);
    expect(trace.spans.length).toBe(2);

    tracer.endSpan(childSpan);
    tracer.endSpan(parentSpan);
    tracer.endTrace(trace.traceId);
  });

  test('should record LLM call metrics', () => {
    const trace = tracer.startTrace('test');
    const span = tracer.startSpan('llm', SpanType.LLM);

    tracer.recordLlmCall(span, 'gpt-4', 100, 50, 0.003);

    expect(span.model).toBe('gpt-4');
    expect(span.promptTokens).toBe(100);
    expect(span.completionTokens).toBe(50);
    expect(span.totalTokens).toBe(150);
    expect(span.cost).toBe(0.003);
  });

  test('should record errors', () => {
    const trace = tracer.startTrace('test');
    const span = tracer.startSpan('failing_op', SpanType.FUNCTION);

    const error = new Error('Test error');
    tracer.recordError(span, error);

    expect(span.status).toBe(SpanStatus.ERROR);
    expect(span.events.length).toBe(1);
    expect(span.events[0].name).toBe('exception');
  });
});

describe('FileExporter', () => {
  const testFile = '/tmp/test_ts_traces.jsonl';

  afterEach(() => {
    if (fs.existsSync(testFile)) {
      fs.unlinkSync(testFile);
    }
  });

  test('should export traces to file', async () => {
    const exporter = new FileExporter(testFile);
    const tracer = new Tracer('test');
    tracer.setExporter(exporter);

    const trace = tracer.startTrace('export_test');
    const span = tracer.startSpan('test_span', SpanType.FUNCTION);
    tracer.endSpan(span);
    tracer.endTrace(trace.traceId);

    await exporter.flush();
    exporter.close();

    expect(fs.existsSync(testFile)).toBe(true);

    const content = fs.readFileSync(testFile, 'utf-8');
    const lines = content.trim().split('\n');
    expect(lines.length).toBeGreaterThan(0);

    const data = JSON.parse(lines[0]);
    expect(data.traceId).toBe(trace.traceId);
  });
});

describe('Instrumentation', () => {
  test('should trace sync functions', async () => {
    const { trace } = await import('./instrumentation');

    const fn = trace(
      (x: number, y: number) => x + y,
      'add',
      SpanType.FUNCTION
    );

    const result = fn(5, 3);
    expect(result).toBe(8);
  });

  test('should trace async functions', async () => {
    const { trace } = await import('./instrumentation');

    const fn = trace(
      async (x: number) => {
        await new Promise(resolve => setTimeout(resolve, 10));
        return x * 2;
      },
      'double',
      SpanType.FUNCTION
    );

    const result = await fn(5);
    expect(result).toBe(10);
  });
});
