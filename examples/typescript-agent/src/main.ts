/**
 * Example: Using Agent Trace TypeScript SDK
 *
 * This example demonstrates:
 * 1. Basic function tracing
 * 2. LLM call tracing
 * 3. Manual span creation
 * 4. Integration with LangChain.js (optional)
 */

import {
  getTracer,
  trace,
  traceLlm,
  FileExporter,
  SpanType,
} from '@agent-trace/sdk';

// Setup tracer
const tracer = getTracer();
tracer.setExporter(new FileExporter('ts_traces.jsonl'));

console.log('Agent Trace TypeScript SDK Examples');
console.log('=' .repeat(60));

// Example 1: Basic function tracing
console.log('\n1. Basic Function Tracing');
console.log('-'.repeat(40));

const tracedFunction = trace(
  (name: string, age: number) => {
    return `Hello ${name}, you are ${age} years old`;
  },
  'greet_user',
  SpanType.FUNCTION
);

const result1 = tracedFunction('Alice', 30);
console.log(`Result: ${result1}`);

// Example 2: Async function tracing
console.log('\n2. Async Function Tracing');
console.log('-'.repeat(40));

const asyncFunction = trace(
  async (query: string) => {
    // Simulate async operation
    await new Promise(resolve => setTimeout(resolve, 100));
    return `Results for: ${query}`;
  },
  'search_database',
  SpanType.TOOL
);

asyncFunction('TypeScript').then(result => {
  console.log(`Async result: ${result}`);
});

// Example 3: LLM call tracing
console.log('\n3. LLM Call Tracing');
console.log('-'.repeat(40));

const mockLlmCall = traceLlm(
  async (prompt: string) => {
    // Simulate LLM response
    await new Promise(resolve => setTimeout(resolve, 50));
    return {
      content: `Response to: ${prompt}`,
      usage: {
        promptTokens: 10,
        completionTokens: 20,
      },
    };
  },
  'gpt-4'
);

mockLlmCall('What is TypeScript?').then(result => {
  console.log(`LLM result: ${JSON.stringify(result, null, 2)}`);
});

// Example 4: Manual span creation
console.log('\n4. Manual Span Creation');
console.log('-'.repeat(40));

const trace_obj = tracer.startTrace(
  'manual_trace_example',
  'user_123',
  'session_abc',
  { framework: 'typescript' }
);

const agentSpan = tracer.startSpan('MyAgent', SpanType.AGENT);

const llmSpan = tracer.startSpan(
  'llm_call',
  SpanType.LLM,
  agentSpan.spanId
);

tracer.recordLlmCall(llmSpan, 'gpt-4', 50, 100, 0.003);
tracer.endSpan(llmSpan, undefined, 'LLM response here');

const toolSpan = tracer.startSpan(
  'web_search',
  SpanType.TOOL,
  agentSpan.spanId
);

tracer.endSpan(toolSpan, undefined, 'Search results...');
tracer.endSpan(agentSpan);

const endedTrace = tracer.endTrace(trace_obj.traceId);
console.log(`✓ Created trace with ${endedTrace?.spans.length} spans`);

// Example 5: Nested tracing
console.log('\n5. Nested Tracing');
console.log('-'.repeat(40));

const outerFunction = trace(
  () => {
    console.log('Outer function');
    const innerFunction = trace(
      () => {
        console.log('Inner function');
        return 'inner result';
      },
      'inner_func',
      SpanType.FUNCTION
    );
    return innerFunction();
  },
  'outer_func',
  SpanType.FUNCTION
);

outerFunction();

// Wait for async operations
setTimeout(() => {
  console.log('\n' + '='.repeat(60));
  console.log('Examples completed!');
  console.log('Check ts/ts_traces.jsonl for trace data');
}, 500);
