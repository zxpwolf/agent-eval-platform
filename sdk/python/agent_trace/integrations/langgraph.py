"""LangGraph integration for automatic tracing."""

import json
import time
from typing import Any, Dict, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage

from ..models import Span, SpanStatus, SpanType
from ..tracer import Tracer, get_tracer


class AgentTraceCallbackHandler(BaseCallbackHandler):
    """Callback handler that integrates LangChain/LangGraph with Agent Trace.

    This handler automatically captures:
    - LLM calls (model, tokens, latency)
    - Tool executions
    - Chain runs
    - Retriever operations
    - Errors and exceptions

    Usage:
        from agent_trace.integrations.langgraph import AgentTraceCallbackHandler

        handler = AgentTraceCallbackHandler()
        graph.invoke({...}, config={"callbacks": [handler]})
    """

    def __init__(self, tracer: Optional[Tracer] = None):
        super().__init__()
        self.tracer = tracer or get_tracer()
        self._span_stack: list = []
        self._current_trace = None

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a chain starts running."""
        name = serialized.get("name", "chain")

        # Determine parent span
        parent_span_id = None
        if parent_run_id and self._span_stack:
            parent_span_id = self._span_stack[-1].span_id

        span = self.tracer.start_span(
            name=name,
            span_type=SpanType.CHAIN,
            parent_span_id=parent_span_id,
            attributes={
                "run_id": str(run_id),
                "tags": tags or [],
                "metadata": metadata or {},
            },
        )
        span.input_data = _safe_serialize_inputs(inputs)
        self._span_stack.append(span)

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a chain ends."""
        if self._span_stack:
            span = self._span_stack.pop()
            span.output_data = _safe_serialize_outputs(outputs)
            self.tracer.end_span(span)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a chain encounters an error."""
        if self._span_stack:
            span = self._span_stack.pop()
            self.tracer.record_error(span, error)
            self.tracer.end_span(span)

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: list,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when an LLM starts."""
        model_name = serialized.get("kwargs", {}).get("model_name", "unknown")

        parent_span_id = None
        if parent_run_id and self._span_stack:
            parent_span_id = self._span_stack[-1].span_id

        span = self.tracer.start_span(
            name=f"llm_{model_name}",
            span_type=SpanType.LLM,
            parent_span_id=parent_span_id,
            attributes={
                "run_id": str(run_id),
                "model": model_name,
                "tags": tags or [],
            },
        )

        # Serialize prompts (limit size)
        if isinstance(prompts, list):
            span.input_data = [
                p if isinstance(p, str) else str(p)[:1000] for p in prompts[:10]
            ]
        else:
            span.input_data = str(prompts)[:1000]

        self._span_stack.append(span)

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Run when an LLM completes."""
        if not self._span_stack:
            return

        span = self._span_stack.pop()

        # Extract token usage if available
        try:
            if hasattr(response, "llm_output") and response.llm_output:
                token_usage = response.llm_output.get("token_usage", {})
                if token_usage:
                    self.tracer.record_llm_call(
                        span,
                        model=span.model or "unknown",
                        prompt_tokens=token_usage.get("prompt_tokens", 0),
                        completion_tokens=token_usage.get("completion_tokens", 0),
                    )
        except Exception:
            pass

        # Extract output
        try:
            if hasattr(response, "generations"):
                span.output_data = str(response.generations)[:2000]
            elif hasattr(response, "text"):
                span.output_data = response.text
        except Exception:
            span.output_data = str(response)[:2000]

        self.tracer.end_span(span)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Run when an LLM encounters an error."""
        if self._span_stack:
            span = self._span_stack.pop()
            self.tracer.record_error(span, error)
            self.tracer.end_span(span)

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a tool starts."""
        tool_name = serialized.get("name", "tool")

        parent_span_id = None
        if parent_run_id and self._span_stack:
            parent_span_id = self._span_stack[-1].span_id

        span = self.tracer.start_span(
            name=f"tool_{tool_name}",
            span_type=SpanType.TOOL,
            parent_span_id=parent_span_id,
            attributes={
                "run_id": str(run_id),
                "tool_name": tool_name,
                "tags": tags or [],
            },
        )
        span.input_data = input_str[:2000] if input_str else inputs
        self._span_stack.append(span)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a tool completes."""
        if self._span_stack:
            span = self._span_stack.pop()
            span.output_data = str(output)[:2000] if output else None
            self.tracer.end_span(span)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a tool encounters an error."""
        if self._span_stack:
            span = self._span_stack.pop()
            self.tracer.record_error(span, error)
            self.tracer.end_span(span)

    def on_retriever_start(
        self,
        serialized: Dict[str, Any],
        query: str,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a retriever starts."""
        retriever_name = serialized.get("name", "retriever")

        parent_span_id = None
        if parent_run_id and self._span_stack:
            parent_span_id = self._span_stack[-1].span_id

        span = self.tracer.start_span(
            name=f"retriever_{retriever_name}",
            span_type=SpanType.RETRIEVER,
            parent_span_id=parent_span_id,
            attributes={
                "run_id": str(run_id),
                "query": query[:500],
            },
        )
        self._span_stack.append(span)

    def on_retriever_end(
        self,
        documents: Any,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a retriever completes."""
        if self._span_stack:
            span = self._span_stack.pop()
            try:
                doc_count = len(documents) if hasattr(documents, "__len__") else 0
                span.output_data = f"{doc_count} documents retrieved"
            except Exception:
                pass
            self.tracer.end_span(span)

    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Run when a retriever encounters an error."""
        if self._span_stack:
            span = self._span_stack.pop()
            self.tracer.record_error(span, error)
            self.tracer.end_span(span)


def _safe_serialize_inputs(inputs: Any, max_length: int = 2000) -> Any:
    """Safely serialize inputs for storage."""
    if inputs is None:
        return None

    if isinstance(inputs, dict):
        return {k: _safe_serialize_inputs(v, max_length) for k, v in inputs.items()}

    if isinstance(inputs, list):
        return [_safe_serialize_inputs(item, max_length) for item in inputs[:50]]

    if isinstance(inputs, str):
        return inputs[:max_length]

    try:
        json_str = json.dumps(inputs, default=str)
        if len(json_str) > max_length:
            return json_str[:max_length] + "..."
        return inputs
    except Exception:
        return str(inputs)[:max_length]


def _safe_serialize_outputs(outputs: Any, max_length: int = 2000) -> Any:
    """Safely serialize outputs for storage."""
    return _safe_serialize_inputs(outputs, max_length)
