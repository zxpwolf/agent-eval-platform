"""LlamaIndex integration for automatic tracing.

This module provides callback handlers that integrate LlamaIndex with Agent Trace,
automatically capturing LLM calls, embeddings, retrievals, and query executions.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from llama_index.core.instrumentation.events import BaseEvent
from llama_index.core.instrumentation.event_handlers import BaseEventHandler

from ..models import Span, SpanStatus, SpanType
from ..tracer import Tracer, get_tracer

logger = logging.getLogger(__name__)


class LlamaIndexTraceHandler(BaseEventHandler):
    """Event handler that integrates LlamaIndex with Agent Trace.

    This handler captures:
    - LLM completions (model, tokens, latency)
    - Embedding operations
    - Retrieval operations
    - Query engine executions
    - Chat engine interactions

    Usage:
        from agent_trace.integrations.llamaindex import LlamaIndexTraceHandler
        from llama_index.core.instrumentation import get_dispatcher

        handler = LlamaIndexTraceHandler()
        dispatcher = get_dispatcher()
        dispatcher.add_event_handler(handler)
    """

    def __init__(self, tracer: Optional[Tracer] = None):
        super().__init__()
        self.tracer = tracer or get_tracer()
        self._span_stack: List[Span] = []
        self._event_to_span: Dict[str, Span] = {}

    @classmethod
    def class_name(cls) -> str:
        return "LlamaIndexTraceHandler"

    def handle(self, event: BaseEvent) -> Optional[Any]:
        """Handle LlamaIndex events and create corresponding spans."""
        try:
            event_type = type(event).__name__

            # LLM Events
            if event_type == "LLMCompletionStartEvent":
                self._on_llm_start(event)
            elif event_type == "LLMCompletionEndEvent":
                self._on_llm_end(event)

            # Embedding Events
            elif event_type == "EmbeddingStartEvent":
                self._on_embedding_start(event)
            elif event_type == "EmbeddingEndEvent":
                self._on_embedding_end(event)

            # Retrieval Events
            elif event_type == "RetrievalStartEvent":
                self._on_retrieval_start(event)
            elif event_type == "RetrievalEndEvent":
                self._on_retrieval_end(event)

            # Query Engine Events
            elif event_type == "QueryStartEvent":
                self._on_query_start(event)
            elif event_type == "QueryEndEvent":
                self._on_query_end(event)

            # Chat Engine Events
            elif event_type == "ChatStartEvent":
                self._on_chat_start(event)
            elif event_type == "ChatEndEvent":
                self._on_chat_end(event)

        except Exception as e:
            logger.error(f"Error handling LlamaIndex event: {e}")

        return None

    def _get_parent_span_id(self) -> Optional[str]:
        """Get the parent span ID from the current stack."""
        if self._span_stack:
            return self._span_stack[-1].span_id
        return None

    def _on_llm_start(self, event: BaseEvent):
        """Handle LLM completion start event."""
        try:
            model = getattr(event, 'model_dict', {}).get('model', 'unknown')
            messages = getattr(event, 'messages', [])

            parent_span_id = self._get_parent_span_id()

            span = self.tracer.start_span(
                name=f"llm_{model}",
                span_type=SpanType.LLM,
                parent_span_id=parent_span_id,
                attributes={
                    "model": model,
                    "event_id": getattr(event, 'id_', None),
                },
            )

            # Serialize messages
            if messages:
                span.input_data = [
                    {"role": getattr(m, 'role', 'user'), "content": getattr(m, 'content', '')[:1000]}
                    for m in messages[:10]
                ]

            self._span_stack.append(span)
            if hasattr(event, 'id_'):
                self._event_to_span[event.id_] = span

        except Exception as e:
            logger.error(f"Error in _on_llm_start: {e}")

    def _on_llm_end(self, event: BaseEvent):
        """Handle LLM completion end event."""
        try:
            event_id = getattr(event, 'id_', None)
            span = self._event_to_span.pop(event_id, None)

            if not span and self._span_stack:
                span = self._span_stack.pop()
            elif span:
                # Remove from stack if found
                if span in self._span_stack:
                    self._span_stack.remove(span)

            if span:
                # Extract response
                response = getattr(event, 'response', None)
                if response:
                    span.output_data = str(response)[:2000]

                    # Extract token usage if available
                    raw = getattr(response, 'raw', {})
                    if isinstance(raw, dict):
                        usage = raw.get('usage', {})
                        if usage:
                            self.tracer.record_llm_call(
                                span,
                                model=span.model or "unknown",
                                prompt_tokens=usage.get('prompt_tokens', 0),
                                completion_tokens=usage.get('completion_tokens', 0),
                            )

                span.end_time = time.time()
                span.status = SpanStatus.OK

        except Exception as e:
            logger.error(f"Error in _on_llm_end: {e}")

    def _on_embedding_start(self, event: BaseEvent):
        """Handle embedding start event."""
        try:
            texts = getattr(event, 'texts', [])

            parent_span_id = self._get_parent_span_id()

            span = self.tracer.start_span(
                name="embedding",
                span_type=SpanType.EMBEDDING,
                parent_span_id=parent_span_id,
                attributes={
                    "event_id": getattr(event, 'id_', None),
                    "text_count": len(texts) if texts else 0,
                },
            )

            if texts:
                span.input_data = [t[:500] for t in texts[:20]]

            self._span_stack.append(span)
            if hasattr(event, 'id_'):
                self._event_to_span[event.id_] = span

        except Exception as e:
            logger.error(f"Error in _on_embedding_start: {e}")

    def _on_embedding_end(self, event: BaseEvent):
        """Handle embedding end event."""
        try:
            event_id = getattr(event, 'id_', None)
            span = self._event_to_span.pop(event_id, None)

            if not span and self._span_stack:
                span = self._span_stack.pop()
            elif span and span in self._span_stack:
                self._span_stack.remove(span)

            if span:
                embeddings = getattr(event, 'embeddings', [])
                if embeddings:
                    span.output_data = f"{len(embeddings)} embeddings generated"

                span.end_time = time.time()
                span.status = SpanStatus.OK

        except Exception as e:
            logger.error(f"Error in _on_embedding_end: {e}")

    def _on_retrieval_start(self, event: BaseEvent):
        """Handle retrieval start event."""
        try:
            query_str = getattr(event, 'query_str', '')

            parent_span_id = self._get_parent_span_id()

            span = self.tracer.start_span(
                name="retrieval",
                span_type=SpanType.RETRIEVER,
                parent_span_id=parent_span_id,
                attributes={
                    "event_id": getattr(event, 'id_', None),
                },
            )

            if query_str:
                span.input_data = query_str[:1000]

            self._span_stack.append(span)
            if hasattr(event, 'id_'):
                self._event_to_span[event.id_] = span

        except Exception as e:
            logger.error(f"Error in _on_retrieval_start: {e}")

    def _on_retrieval_end(self, event: BaseEvent):
        """Handle retrieval end event."""
        try:
            event_id = getattr(event, 'id_', None)
            span = self._event_to_span.pop(event_id, None)

            if not span and self._span_stack:
                span = self._span_stack.pop()
            elif span and span in self._span_stack:
                self._span_stack.remove(span)

            if span:
                nodes = getattr(event, 'nodes', [])
                if nodes:
                    span.output_data = f"{len(nodes)} nodes retrieved"

                span.end_time = time.time()
                span.status = SpanStatus.OK

        except Exception as e:
            logger.error(f"Error in _on_retrieval_end: {e}")

    def _on_query_start(self, event: BaseEvent):
        """Handle query engine start event."""
        try:
            query_str = getattr(event, 'query_str', '')

            parent_span_id = self._get_parent_span_id()

            span = self.tracer.start_span(
                name="query_engine",
                span_type=SpanType.CHAIN,
                parent_span_id=parent_span_id,
                attributes={
                    "event_id": getattr(event, 'id_', None),
                },
            )

            if query_str:
                span.input_data = query_str

            self._span_stack.append(span)
            if hasattr(event, 'id_'):
                self._event_to_span[event.id_] = span

        except Exception as e:
            logger.error(f"Error in _on_query_start: {e}")

    def _on_query_end(self, event: BaseEvent):
        """Handle query engine end event."""
        try:
            event_id = getattr(event, 'id_', None)
            span = self._event_to_span.pop(event_id, None)

            if not span and self._span_stack:
                span = self._span_stack.pop()
            elif span and span in self._span_stack:
                self._span_stack.remove(span)

            if span:
                response = getattr(event, 'response', None)
                if response:
                    span.output_data = str(response)[:2000]

                span.end_time = time.time()
                span.status = SpanStatus.OK

        except Exception as e:
            logger.error(f"Error in _on_query_end: {e}")

    def _on_chat_start(self, event: BaseEvent):
        """Handle chat engine start event."""
        try:
            message = getattr(event, 'message', None)

            parent_span_id = self._get_parent_span_id()

            span = self.tracer.start_span(
                name="chat_engine",
                span_type=SpanType.CHAIN,
                parent_span_id=parent_span_id,
                attributes={
                    "event_id": getattr(event, 'id_', None),
                },
            )

            if message:
                span.input_data = str(message)[:1000]

            self._span_stack.append(span)
            if hasattr(event, 'id_'):
                self._event_to_span[event.id_] = span

        except Exception as e:
            logger.error(f"Error in _on_chat_start: {e}")

    def _on_chat_end(self, event: BaseEvent):
        """Handle chat engine end event."""
        try:
            event_id = getattr(event, 'id_', None)
            span = self._event_to_span.pop(event_id, None)

            if not span and self._span_stack:
                span = self._span_stack.pop()
            elif span and span in self._span_stack:
                self._span_stack.remove(span)

            if span:
                response = getattr(event, 'response', None)
                if response:
                    span.output_data = str(response)[:2000]

                span.end_time = time.time()
                span.status = SpanStatus.OK

        except Exception as e:
            logger.error(f"Error in _on_chat_end: {e}")


def setup_llamaindex_tracing(tracer: Optional[Tracer] = None) -> LlamaIndexTraceHandler:
    """Convenience function to set up LlamaIndex tracing.

    Usage:
        from agent_trace.integrations.llamaindex import setup_llamaindex_tracing
        setup_llamaindex_tracing()
    """
    try:
        from llama_index.core.instrumentation import get_dispatcher

        handler = LlamaIndexTraceHandler(tracer=tracer)
        dispatcher = get_dispatcher()
        dispatcher.add_event_handler(handler)

        logger.info("LlamaIndex tracing enabled")
        return handler

    except ImportError:
        logger.warning(
            "llama_index is not installed. Install it with: pip install llama-index"
        )
        raise
