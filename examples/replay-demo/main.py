"""Example: Using the replay engine to record and replay agent executions.

This example demonstrates:
1. Recording an agent execution
2. Exporting as a replay log
3. Replaying the execution deterministically
4. Comparing two replays
"""

import sys
import os
import asyncio

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sdk/python"))

from agent_trace import Tracer, get_tracer
from agent_trace.models import SpanType, Trace
from agent_trace.replay import (
    ReplayEngine,
    ExecutionRecorder,
    get_engine,
    get_recorder,
)


def create_sample_trace() -> Trace:
    """Create a sample trace for demonstration."""
    print("Creating sample trace...")

    tracer = Tracer(project_name="replay_demo")

    # Start a trace
    trace = tracer.start_trace(
        name="sample_agent_run",
        user_id="demo_user",
        session_id="session_1",
        metadata={"agent_type": "react", "task": "web_search"},
    )

    # Simulate agent span
    from agent_trace.models import Span
    import time

    agent_span = Span(
        trace_id=trace.trace_id,
        span_id="span-agent-1",
        name="ReActAgent",
        span_type=SpanType.AGENT,
        start_time=time.time(),
    )
    trace.spans.append(agent_span)

    # Simulate LLM call 1
    llm_span_1 = Span(
        trace_id=trace.trace_id,
        span_id="span-llm-1",
        name="llm_gpt-4",
        span_type=SpanType.LLM,
        start_time=time.time(),
        parent_span_id=agent_span.span_id,
        model="gpt-4",
        prompt_tokens=50,
        completion_tokens=100,
        cost=0.0045,
        input_data="What is Python?",
        output_data="Python is a programming language...",
    )
    trace.spans.append(llm_span_1)

    # Simulate tool call
    tool_span = Span(
        trace_id=trace.trace_id,
        span_id="span-tool-1",
        name="tool_search",
        span_type=SpanType.TOOL,
        start_time=time.time(),
        parent_span_id=agent_span.span_id,
        input_data="Python programming",
        output_data="Search results about Python...",
    )
    trace.spans.append(tool_span)

    # Simulate LLM call 2
    llm_span_2 = Span(
        trace_id=trace.trace_id,
        span_id="span-llm-2",
        name="llm_gpt-4",
        span_type=SpanType.LLM,
        start_time=time.time(),
        parent_span_id=agent_span.span_id,
        model="gpt-4",
        prompt_tokens=150,
        completion_tokens=80,
        cost=0.0039,
        input_data="Summarize the search results",
        output_data="Python is a high-level, general-purpose programming language...",
    )
    trace.spans.append(llm_span_2)

    # End spans
    end_time = time.time()
    for span in trace.spans:
        span.end_time = end_time

    tracer.end_trace(trace.trace_id)

    print(f"✓ Created trace with {len(trace.spans)} spans")
    return trace


async def demo_replay():
    """Demonstrate replay functionality."""
    print("\n" + "=" * 60)
    print("Replay Engine Demo")
    print("=" * 60)

    # Initialize engine
    engine = get_engine()
    recorder = get_recorder()

    # Step 1: Create and export a sample trace
    print("\n1. Creating sample trace...")
    trace = create_sample_trace()

    print("\n2. Exporting trace as replay log...")
    log_id = engine.export_replay_log(trace)
    if not log_id:
        print("✗ Failed to export replay log")
        return

    print(f"✓ Exported replay log: {log_id}")

    # List available logs
    logs = recorder.list_logs()
    print(f"\n3. Available replay logs: {len(logs)}")
    for log in logs:
        print(f"   - {log['log_id'][:8]}... (trace: {log['trace_id'][:8]}...)")

    # Step 4: Start replay with mock LLM
    print("\n4. Starting replay with mock LLM...")
    session_id = await engine.replay_trace(
        trace_id=trace.trace_id,
        mock_llm=True,
        mock_tools=False,
        speed_multiplier=1.0,
        preserve_timing=False,
    )

    if not session_id:
        print("✗ Failed to start replay")
        return

    print(f"✓ Started replay session: {session_id[:8]}...")

    # Wait a bit for replay to complete
    await asyncio.sleep(1)

    # Check status
    status = engine.controller.get_status(session_id)
    print(f"\n5. Replay status:")
    print(f"   - Status: {status['status']}")
    print(f"   - Progress: {status['progress']:.1f}%")
    print(f"   - Calls replayed: {status['replayed_calls_count']}")

    # Step 6: Start another replay for comparison
    print("\n6. Starting second replay for comparison...")
    session_id_2 = await engine.replay_trace(
        trace_id=trace.trace_id,
        mock_llm=True,
        mock_tools=False,
        speed_multiplier=1.0,
        preserve_timing=False,
    )

    await asyncio.sleep(1)

    # Compare replays
    print("\n7. Comparing two replays...")
    comparison = engine.compare_replays(session_id, session_id_2)
    print(f"   - Session 1 calls: {comparison['session_1']['calls_count']}")
    print(f"   - Session 2 calls: {comparison['session_2']['calls_count']}")
    print(f"   - Differences found: {len(comparison['differences'])}")

    # List sessions
    print("\n8. All replay sessions:")
    sessions = engine.controller.list_sessions()
    for s in sessions:
        print(f"   - {s['session_id'][:8]}... ({s['status']})")

    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)


if __name__ == "__main__":
    print("Agent Observability - Replay Engine Example")
    print("=" * 60)

    asyncio.run(demo_replay())
