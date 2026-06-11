/**
 * LangChain.js integration for automatic tracing
 */

import { SpanType, SpanStatus } from '../models';
import { Tracer, getTracer } from '../tracer';

/**
 * Callback handler for LangChain.js
 *
 * Usage:
 * ```typescript
 * import { AgentTraceCallbackHandler } from '@agent-trace/sdk/integrations/langchain';
 *
 * const handler = new AgentTraceCallbackHandler();
 * const chain = LLMChain.fromLLMAndPrompt(llm, prompt);
 * await chain.call({ input: "Hello" }, [handler]);
 * ```
 */
export class AgentTraceCallbackHandler {
  private tracer: Tracer;
  private spanStack: any[] = [];
  private runIdToSpan: Map<string, any> = new Map();

  constructor(tracer?: Tracer) {
    this.tracer = tracer || getTracer();
  }

  // LangChain.js callback handler methods

  async handleLLMStart(llm: any, prompts: string[], runId: string, parentRunId?: string): Promise<void> {
    const modelName = llm.model || llm.modelName || 'unknown';
    const parentSpanId = parentRunId ? this.runIdToSpan.get(parentRunId)?.spanId : undefined;

    const span = this.tracer.startSpan(
      `llm_${modelName}`,
      SpanType.LLM,
      parentSpanId,
      {
        runId,
        model: modelName,
      }
    );

    span.inputData = prompts.slice(0, 10).map(p => p.substring(0, 1000));
    this.spanStack.push(span);
    this.runIdToSpan.set(runId, span);
  }

  async handleLLMEnd(output: any, runId: string): Promise<void> {
    const span = this.runIdToSpan.get(runId) || this.spanStack.pop();
    if (!span) return;

    // Extract token usage
    if (output && output.llmOutput && output.llmOutput.tokenUsage) {
      const usage = output.llmOutput.tokenUsage;
      this.tracer.recordLlmCall(
        span,
        span.model || 'unknown',
        usage.promptTokens || usage.input_tokens || 0,
        usage.completionTokens || usage.output_tokens || 0
      );
    }

    // Extract output
    if (output && output.generations) {
      span.outputData = JSON.stringify(output.generations).substring(0, 2000);
    }

    this.tracer.endSpan(span);
    this.runIdToSpan.delete(runId);
  }

  async handleLLMError(error: Error, runId: string): Promise<void> {
    const span = this.runIdToSpan.get(runId) || this.spanStack.pop();
    if (span) {
      this.tracer.recordError(span, error);
      this.tracer.endSpan(span);
      this.runIdToSpan.delete(runId);
    }
  }

  async handleChainStart(chain: any, inputs: any, runId: string, parentRunId?: string): Promise<void> {
    const name = chain.name || chain.constructor?.name || 'chain';
    const parentSpanId = parentRunId ? this.runIdToSpan.get(parentRunId)?.spanId : undefined;

    const span = this.tracer.startSpan(
      name,
      SpanType.CHAIN,
      parentSpanId,
      {
        runId,
      }
    );

    span.inputData = this.safeSerialize(inputs);
    this.spanStack.push(span);
    this.runIdToSpan.set(runId, span);
  }

  async handleChainEnd(outputs: any, runId: string): Promise<void> {
    const span = this.runIdToSpan.get(runId) || this.spanStack.pop();
    if (span) {
      span.outputData = this.safeSerialize(outputs);
      this.tracer.endSpan(span);
      this.runIdToSpan.delete(runId);
    }
  }

  async handleChainError(error: Error, runId: string): Promise<void> {
    const span = this.runIdToSpan.get(runId) || this.spanStack.pop();
    if (span) {
      this.tracer.recordError(span, error);
      this.tracer.endSpan(span);
      this.runIdToSpan.delete(runId);
    }
  }

  async handleToolStart(tool: any, input: string, runId: string, parentRunId?: string): Promise<void> {
    const toolName = tool.name || 'tool';
    const parentSpanId = parentRunId ? this.runIdToSpan.get(parentRunId)?.spanId : undefined;

    const span = this.tracer.startSpan(
      `tool_${toolName}`,
      SpanType.TOOL,
      parentSpanId,
      {
        runId,
        toolName,
      }
    );

    span.inputData = input?.substring(0, 2000);
    this.spanStack.push(span);
    this.runIdToSpan.set(runId, span);
  }

  async handleToolEnd(output: string, runId: string): Promise<void> {
    const span = this.runIdToSpan.get(runId) || this.spanStack.pop();
    if (span) {
      span.outputData = output?.substring(0, 2000);
      this.tracer.endSpan(span);
      this.runIdToSpan.delete(runId);
    }
  }

  async handleToolError(error: Error, runId: string): Promise<void> {
    const span = this.runIdToSpan.get(runId) || this.spanStack.pop();
    if (span) {
      this.tracer.recordError(span, error);
      this.tracer.endSpan(span);
      this.runIdToSpan.delete(runId);
    }
  }

  private safeSerialize(obj: any, maxDepth: number = 3): any {
    if (obj === null || obj === undefined) return obj;
    if (typeof obj === 'string' || typeof obj === 'number' || typeof obj === 'boolean') return obj;

    if (Array.isArray(obj)) {
      return obj.slice(0, 50).map(item => this.safeSerialize(item, maxDepth - 1));
    }

    if (typeof obj === 'object') {
      if (maxDepth <= 0) return `<object>`;
      try {
        const result: Record<string, any> = {};
        const keys = Object.keys(obj).slice(0, 50);
        for (const key of keys) {
          result[key] = this.safeSerialize(obj[key], maxDepth - 1);
        }
        return result;
      } catch {
        return `<object>`;
      }
    }

    return String(obj).substring(0, 1000);
  }
}
