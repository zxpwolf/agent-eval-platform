"""CrewAI integration for automatic tracing.

This module provides tracing for CrewAI crews, agents, and tasks.
It hooks into CrewAI's execution lifecycle to automatically capture
agent interactions, LLM calls, tool usage, and delegation patterns.

Usage:
    from agent_trace.integrations.crewai import CrewAITraceHandler

    handler = CrewAITraceHandler()
    crew = Crew(agents=[...], tasks=[...])
    handler.instrument_crew(crew)
    result = crew.kickoff()
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from ..models import Span, SpanStatus, SpanType
from ..tracer import Tracer, get_tracer

logger = logging.getLogger(__name__)


class CrewAITraceHandler:
    """Trace handler for CrewAI crews, agents, and tasks.

    Captures:
    - Crew execution (overall orchestration)
    - Agent task execution (each agent's work on a task)
    - LLM calls within agent execution
    - Tool usage by agents
    - Agent delegation between agents
    - Errors at any level

    Usage:
        handler = CrewAITraceHandler()
        crew = Crew(agents=[...], tasks=[...])
        handler.instrument_crew(crew)
        result = crew.kickoff()

        # Get the trace for export
        trace = handler.get_last_trace()
    """

    def __init__(self, tracer: Optional[Tracer] = None):
        self.tracer = tracer or get_tracer()
        self._traces: List[Any] = []
        self._active_spans: Dict[str, Span] = {}
        self._agent_spans: Dict[str, Span] = {}
        self._tool_spans: Dict[str, Span] = {}

    def instrument_crew(self, crew: Any) -> None:
        """Instrument a CrewAI Crew for automatic tracing.

        Wraps the crew's execution methods to capture all activity.
        """
        try:
            self._patch_crew(crew)
            logger.info("CrewAI tracing enabled")
        except Exception as e:
            logger.error(f"Failed to instrument CrewAI crew: {e}")

    def _patch_crew(self, crew: Any) -> None:
        """Monkey-patch crew execution methods for tracing."""
        original_run = getattr(crew, "run", None)
        if original_run and not getattr(original_run, "_agent_trace_patched", False):
            handler = self

            def traced_run(*args: Any, **kwargs: Any) -> Any:
                return handler._wrap_crew_run(crew, original_run, *args, **kwargs)

            traced_run._agent_trace_patched = True  # type: ignore[attr-defined]
            crew.run = traced_run  # type: ignore[assignment]

        # Also patch kickoff if it exists separately
        original_kickoff = getattr(crew, "kickoff", None)
        if original_kickoff and not getattr(original_kickoff, "_agent_trace_patched", False):
            handler = self

            def traced_kickoff(*args: Any, **kwargs: Any) -> Any:
                return handler._wrap_crew_run(crew, original_kickoff, *args, **kwargs)

            traced_kickoff._agent_trace_patched = True  # type: ignore[attr-defined]
            crew.kickoff = traced_kickoff  # type: ignore[assignment]

    def _wrap_crew_run(self, crew: Any, original_fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Wrap crew execution with trace creation."""
        crew_name = getattr(crew, "name", None) or "crew_execution"

        trace = self.tracer.start_trace(
            name=crew_name,
            metadata={
                "framework": "crewai",
                "agent_count": len(getattr(crew, "agents", [])),
                "task_count": len(getattr(crew, "tasks", [])),
                "process": getattr(crew, "process", "unknown"),
            },
        )

        # Create crew-level span
        crew_span = self.tracer.start_span(
            name=crew_name,
            span_type=SpanType.WORKFLOW,
            attributes={
                "crew.process": str(getattr(crew, "process", "")),
                "crew.agent_count": len(getattr(crew, "agents", [])),
                "crew.task_count": len(getattr(crew, "tasks", [])),
            },
        )

        # Instrument agents and tasks before execution
        for agent in getattr(crew, "agents", []):
            self._instrument_agent(agent)

        for task in getattr(crew, "tasks", []):
            self._instrument_task(task)

        try:
            result = original_fn(*args, **kwargs)

            crew_span.output_data = str(result)[:2000] if result else None
            self.tracer.end_span(crew_span)

            self.tracer.end_trace(trace.trace_id)
            self._traces.append(trace)
            return result

        except Exception as e:
            self.tracer.record_error(crew_span, e)
            self.tracer.end_span(crew_span)
            self.tracer.end_trace(trace.trace_id)
            self._traces.append(trace)
            raise

    def _instrument_agent(self, agent: Any) -> None:
        """Instrument a CrewAI Agent for tracing."""
        original_execute = getattr(agent, "execute_task", None)
        if original_execute and not getattr(original_execute, "_agent_trace_patched", False):
            handler = self

            def traced_execute_task(task: Any, *args: Any, **kwargs: Any) -> Any:
                return handler._wrap_agent_execute(agent, original_execute, task, *args, **kwargs)

            traced_execute_task._agent_trace_patched = True  # type: ignore[attr-defined]
            agent.execute_task = traced_execute_task  # type: ignore[assignment]

        # Instrument the agent's LLM if accessible
        llm = getattr(agent, "llm", None)
        if llm:
            self._instrument_llm(agent, llm)

    def _wrap_agent_execute(
        self, agent: Any, original_fn: Any, task: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """Wrap agent task execution with a span."""
        agent_role = getattr(agent, "role", "unknown")
        agent_name = f"agent_{agent_role}".replace(" ", "_").lower()
        task_desc = getattr(task, "description", "")[:200] if task else ""

        span = self.tracer.start_span(
            name=agent_name,
            span_type=SpanType.AGENT,
            attributes={
                "agent.role": agent_role,
                "agent.goal": getattr(agent, "goal", "")[:500],
                "agent.backstory": getattr(agent, "backstory", "")[:500],
                "task.description": task_desc,
                "agent.verbose": getattr(agent, "verbose", False),
            },
        )

        span.input_data = {
            "role": agent_role,
            "task": task_desc,
        }

        span_id = span.span_id
        self._agent_spans[span_id] = span

        try:
            result = original_fn(task, *args, **kwargs)

            span.output_data = str(result)[:2000] if result else None
            self.tracer.end_span(span)
            self._agent_spans.pop(span_id, None)
            return result

        except Exception as e:
            self.tracer.record_error(span, e)
            self.tracer.end_span(span)
            self._agent_spans.pop(span_id, None)
            raise

    def _instrument_task(self, task: Any) -> None:
        """Instrument a CrewAI Task for tracing."""
        original_execute = getattr(task, "execute", None)
        if original_execute and not getattr(original_execute, "_agent_trace_patched", False):
            handler = self

            def traced_execute(*args: Any, **kwargs: Any) -> Any:
                return handler._wrap_task_execute(task, original_execute, *args, **kwargs)

            traced_execute._agent_trace_patched = True  # type: ignore[attr-defined]
            task.execute = traced_execute  # type: ignore[assignment]

    def _wrap_task_execute(self, task: Any, original_fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Wrap task execution with a span."""
        task_desc = getattr(task, "description", "unknown")[:200]
        agent = getattr(task, "agent", None)
        agent_role = getattr(agent, "role", "unassigned") if agent else "unassigned"

        span = self.tracer.start_span(
            name=f"task_{task_desc[:30]}".replace(" ", "_").lower(),
            span_type=SpanType.CHAIN,
            attributes={
                "task.description": task_desc,
                "task.expected_output": getattr(task, "expected_output", "")[:500],
                "task.agent": agent_role,
                "task.async_execution": getattr(task, "async_execution", False),
            },
        )

        try:
            result = original_fn(*args, **kwargs)
            span.output_data = str(result)[:2000] if result else None
            self.tracer.end_span(span)
            return result
        except Exception as e:
            self.tracer.record_error(span, e)
            self.tracer.end_span(span)
            raise

    def _instrument_llm(self, agent: Any, llm: Any) -> None:
        """Instrument an agent's LLM for tracing."""
        # CrewAI LLMs may use different interfaces depending on the version
        # and whether they use LiteLLM, langchain, etc.
        original_call = getattr(llm, "call", None)
        if original_call and not getattr(original_call, "_agent_trace_patched", False):
            handler = self
            agent_role = getattr(agent, "role", "unknown")

            def traced_call(*args: Any, **kwargs: Any) -> Any:
                return handler._wrap_llm_call(agent_role, llm, original_call, *args, **kwargs)

            traced_call._agent_trace_patched = True  # type: ignore[attr-defined]
            llm.call = traced_call  # type: ignore[assignment]

    def _wrap_llm_call(
        self, agent_role: str, llm: Any, original_fn: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """Wrap LLM call with a span."""
        model_name = _get_llm_model(llm)

        span = self.tracer.start_span(
            name=f"llm_{model_name}",
            span_type=SpanType.LLM,
            attributes={
                "agent.role": agent_role,
                "llm.model": model_name,
            },
        )

        # Capture input
        if args:
            span.input_data = str(args[0])[:2000]
        elif "messages" in kwargs:
            span.input_data = str(kwargs["messages"])[:2000]
        elif "prompt" in kwargs:
            span.input_data = str(kwargs["prompt"])[:2000]

        span.model = model_name

        try:
            result = original_fn(*args, **kwargs)
            span.output_data = str(result)[:2000] if result else None
            self.tracer.end_span(span)
            return result
        except Exception as e:
            self.tracer.record_error(span, e)
            self.tracer.end_span(span)
            raise

    def _instrument_tool(self, tool: Any) -> None:
        """Instrument a CrewAI Tool for tracing."""
        original_run = getattr(tool, "run", None)
        if original_run and not getattr(original_run, "_agent_trace_patched", False):
            handler = self
            tool_name = getattr(tool, "name", "unknown_tool")

            def traced_run(*args: Any, **kwargs: Any) -> Any:
                return handler._wrap_tool_run(tool_name, tool, original_run, *args, **kwargs)

            traced_run._agent_trace_patched = True  # type: ignore[attr-defined]
            tool.run = traced_run  # type: ignore[assignment]

    def _wrap_tool_run(
        self, tool_name: str, tool: Any, original_fn: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """Wrap tool execution with a span."""
        span = self.tracer.start_span(
            name=f"tool_{tool_name}",
            span_type=SpanType.TOOL,
            attributes={
                "tool.name": tool_name,
                "tool.description": getattr(tool, "description", "")[:500],
            },
        )

        if args:
            span.input_data = str(args[0])[:2000]

        try:
            result = original_fn(*args, **kwargs)
            span.output_data = str(result)[:2000] if result else None
            self.tracer.end_span(span)
            return result
        except Exception as e:
            self.tracer.record_error(span, e)
            self.tracer.end_span(span)
            raise

    def instrument_tools(self, tools: List[Any]) -> None:
        """Instrument a list of CrewAI tools for tracing.

        Usage:
            handler = CrewAITraceHandler()
            handler.instrument_tools([search_tool, calculator_tool])
        """
        for tool in tools:
            self._instrument_tool(tool)

    def get_last_trace(self) -> Optional[Any]:
        """Get the most recently captured trace."""
        if self._traces:
            return self._traces[-1]
        return None

    def get_all_traces(self) -> List[Any]:
        """Get all captured traces."""
        return list(self._traces)

    def clear_traces(self) -> None:
        """Clear all captured traces."""
        self._traces.clear()


def _get_llm_model(llm: Any) -> str:
    """Extract model name from a CrewAI LLM object."""
    # Try common attribute names
    for attr in ("model", "model_name", "model_id"):
        val = getattr(llm, attr, None)
        if val:
            # Model might be in format "provider/model"
            if isinstance(val, str) and "/" in val:
                return val.split("/")[-1]
            return str(val)
    return "unknown"


def setup_crewai_tracing(
    crew: Any,
    tools: Optional[List[Any]] = None,
    tracer: Optional[Tracer] = None,
) -> CrewAITraceHandler:
    """Convenience function to set up CrewAI tracing.

    Usage:
        from agent_trace.integrations.crewai import setup_crewai_tracing

        handler = setup_crewai_tracing(crew, tools=[search_tool])
        result = crew.kickoff()
        trace = handler.get_last_trace()
    """
    handler = CrewAITraceHandler(tracer=tracer)
    handler.instrument_crew(crew)

    if tools:
        handler.instrument_tools(tools)

    return handler
