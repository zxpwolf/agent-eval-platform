"""Example: LangGraph agent with tracing enabled.

This example demonstrates how to add observability to a LangGraph-based agent.
"""

import sys
import os

# Add SDK to path (in real usage, install the package)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sdk/python"))

from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from agent_trace import get_tracer, FileExporter, BatchExporter
from agent_trace.integrations.langgraph import AgentTraceCallbackHandler


# Initialize tracer
tracer = get_tracer()

# Configure exporter - save to file for this example
file_exporter = FileExporter(filepath="example_traces.jsonl")
tracer._exporter = BatchExporter(exporter=file_exporter, batch_size=1, flush_interval=1)


def simple_llm_call():
    """Example: Trace a simple LLM call."""
    from agent_trace import trace_llm

    @trace_llm(model="gpt-4")
    def call_llm(prompt: str):
        # Simulate LLM call (replace with actual call in production)
        return {
            "content": f"Response to: {prompt}",
            "usage_metadata": {
                "input_tokens": 10,
                "output_tokens": 20,
            },
        }

    result = call_llm("Hello, world!")
    print(f"LLM result: {result}")


def tool_execution_example():
    """Example: Trace tool executions."""
    from agent_trace import trace
    from agent_trace.models import SpanType

    @trace(span_type=SpanType.TOOL)
    def search_web(query: str):
        # Simulate web search
        return f"Search results for: {query}"

    @trace(span_type=SpanType.TOOL)
    def calculate(expression: str):
        # Simulate calculation
        return f"Result of: {expression} = 42"

    search_result = search_web("Python programming")
    calc_result = calculate("2 + 2")

    print(f"Search: {search_result}")
    print(f"Calc: {calc_result}")


def langgraph_agent_example():
    """Example: Trace a LangGraph agent execution."""
    print("\n=== LangGraph Agent Example ===")
    print("Note: This example requires OPENAI_API_KEY to be set")
    print("Skipping actual API call for demo purposes\n")

    # Create callback handler for LangGraph integration
    callback_handler = AgentTraceCallbackHandler(tracer=tracer)

    # In a real scenario, you would:
    # 1. Set up your tools
    # 2. Create the agent
    # 3. Invoke with callbacks

    # Example structure (commented out to avoid API dependency):
    """
    from langchain_core.tools import tool

    @tool
    def search(query: str) -> str:
        \"\"\"Search the web.\"\"\"
        return f"Results for {query}"

    tools = [search]
    model = ChatOpenAI(model="gpt-4")
    checkpointer = MemorySaver()

    agent = create_react_agent(model, tools, checkpointer=checkpointer)

    # Execute with tracing
    config = {"configurable": {"thread_id": "example-thread"}}
    result = agent.invoke(
        {"messages": [HumanMessage(content="What is Python?")]},
        config=config,
        callbacks=[callback_handler],
    )

    print(f"Agent response: {result['messages'][-1].content}")
    """

    # Simulate the trace creation for demonstration
    trace = tracer.start_trace(
        name="langgraph_agent_demo",
        user_id="demo_user",
        session_id="session_1",
    )

    # Simulate agent span
    agent_span = tracer.start_span(
        name="ReActAgent",
        span_type="agent",
        attributes={"agent_type": "react"},
    )

    # Simulate LLM call
    llm_span = tracer.start_span(
        name="llm_gpt-4",
        span_type="llm",
        parent_span_id=agent_span.span_id,
    )
    tracer.record_llm_call(
        llm_span,
        model="gpt-4",
        prompt_tokens=50,
        completion_tokens=100,
        cost=0.0045,
    )
    tracer.end_span(llm_span, output_data="Python is a programming language...")

    # Simulate tool call
    tool_span = tracer.start_span(
        name="tool_search",
        span_type="tool",
        parent_span_id=agent_span.span_id,
    )
    tracer.end_span(tool_span, input_data="Python programming", output_data="Search results...")

    tracer.end_span(agent_span)
    ended_trace = tracer.end_trace(trace.trace_id)

    # Export the trace
    if ended_trace:
        tracer._exporter.export(ended_trace)
        print(f"✓ Created trace: {ended_trace.trace_id}")
        print(f"  - Spans: {len(ended_trace.spans)}")
        print(f"  - Duration: {ended_trace.duration_ms:.2f}ms")

    # Flush exporter
    tracer._exporter.flush()
    file_exporter.close()


if __name__ == "__main__":
    print("Agent Observability Examples")
    print("=" * 50)

    # Run examples
    print("\n1. Simple LLM call...")
    simple_llm_call()

    print("\n2. Tool execution...")
    tool_execution_example()

    print("\n3. LangGraph agent...")
    langgraph_agent_example()

    print("\n" + "=" * 50)
    print("Examples completed!")
    print("Check 'example_traces.jsonl' for trace data")
