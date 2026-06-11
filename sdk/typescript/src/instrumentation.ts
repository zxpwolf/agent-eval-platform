/**
 * Instrumentation utilities for tracing functions
 */

import { SpanType } from './models';
import { getTracer } from './tracer';

/**
 * Wrap a function with tracing
 */
export function trace<T extends (...args: any[]) => any>(
  fn: T,
  name?: string,
  spanType: SpanType = SpanType.FUNCTION
): T {
  const funcName = name || fn.name || 'anonymous';

  if (fn.constructor.name === 'AsyncFunction') {
    return (async (...args: any[]) => {
      const tracer = getTracer();
      const span = tracer.startSpan(funcName, spanType, undefined, {
        function: fn.name,
        args: serializeArgs(args),
      });

      try {
        const result = await fn(...args);
        tracer.endSpan(span, undefined, safeSerialize(result));
        return result;
      } catch (error) {
        tracer.recordError(span, error as Error);
        tracer.endSpan(span);
        throw error;
      }
    }) as T;
  } else {
    return ((...args: any[]) => {
      const tracer = getTracer();
      const span = tracer.startSpan(funcName, spanType, undefined, {
        function: fn.name,
        args: serializeArgs(args),
      });

      try {
        const result = fn(...args);
        tracer.endSpan(span, undefined, safeSerialize(result));
        return result;
      } catch (error) {
        tracer.recordError(span, error as Error);
        tracer.endSpan(span);
        throw error;
      }
    }) as T;
  }
}

/**
 * Wrap an LLM call with tracing
 */
export function traceLlm<T extends (...args: any[]) => any>(
  fn: T,
  model?: string
): T {
  const funcName = fn.name || 'llm_call';

  if (fn.constructor.name === 'AsyncFunction') {
    return (async (...args: any[]) => {
      const tracer = getTracer();
      const span = tracer.startSpan(funcName, SpanType.LLM, undefined, {
        model,
        function: fn.name,
      });

      try {
        const result = await fn(...args);

        // Try to extract token usage
        if (result && typeof result === 'object' && 'usage' in result) {
          const usage = result.usage as any;
          tracer.recordLlmCall(
            span,
            model || 'unknown',
            usage.promptTokens || usage.input_tokens || 0,
            usage.completionTokens || usage.output_tokens || 0
          );
        }

        tracer.endSpan(span, undefined, safeSerialize(result));
        return result;
      } catch (error) {
        tracer.recordError(span, error as Error);
        tracer.endSpan(span);
        throw error;
      }
    }) as T;
  } else {
    return ((...args: any[]) => {
      const tracer = getTracer();
      const span = tracer.startSpan(funcName, SpanType.LLM, undefined, {
        model,
        function: fn.name,
      });

      try {
        const result = fn(...args);

        if (result && typeof result === 'object' && 'usage' in result) {
          const usage = result.usage as any;
          tracer.recordLlmCall(
            span,
            model || 'unknown',
            usage.promptTokens || usage.input_tokens || 0,
            usage.completionTokens || usage.output_tokens || 0
          );
        }

        tracer.endSpan(span, undefined, safeSerialize(result));
        return result;
      } catch (error) {
        tracer.recordError(span, error as Error);
        tracer.endSpan(span);
        throw error;
      }
    }) as T;
  }
}

function serializeArgs(args: any[]): any[] {
  return args.map(arg => safeSerialize(arg));
}

export function safeSerialize(obj: any, maxDepth: number = 3): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (typeof obj === 'string' || typeof obj === 'number' || typeof obj === 'boolean') {
    return obj;
  }

  if (Array.isArray(obj)) {
    if (obj.length > 100) {
      return `<array with ${obj.length} items>`;
    }
    return obj.slice(0, 100).map(item => safeSerialize(item, maxDepth - 1));
  }

  if (typeof obj === 'object') {
    if (maxDepth <= 0) {
      return `<${obj.constructor?.name || 'object'}>`;
    }

    try {
      const keys = Object.keys(obj);
      if (keys.length > 100) {
        return `<object with ${keys.length} keys>`;
      }

      const result: Record<string, any> = {};
      for (const key of keys.slice(0, 100)) {
        result[key] = safeSerialize(obj[key], maxDepth - 1);
      }
      return result;
    } catch {
      return `<${obj.constructor?.name || 'object'}>`;
    }
  }

  // Fallback: convert to string
  try {
    const str = String(obj);
    return str.length > 1000 ? str.substring(0, 1000) + '...' : str;
  } catch {
    return `<unserializable>`;
  }
}
