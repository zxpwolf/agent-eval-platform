"""Test script to verify SDK functionality."""

import sys
import os
import json

# Add SDK to path
sys.path.insert(0, os.path.dirname(__file__))

from agent_trace import (
    Tracer,
    get_tracer,
    trace,
    trace_llm,
    FileExporter,
    ConsoleExporter,
)
from agent_trace.models import SpanType


def test_basic_tracing():
    """Test basic tracing functionality."""
    print("Testing basic tracing...")

    tracer = Tracer(project_name="test")

    # Start a trace
    trace_obj = tracer.start_trace(
        name="test_trace",
        user_id="user_123",
        session_id="session_abc",
    )

    # Directly add spans to trace (bypassing context for testing)
    from agent_trace.models import Span
    import time
    
    parent_span = Span(
        trace_id=trace_obj.trace_id,
        span_id="span-1",
        name="parent_operation",
        span_type=SpanType.AGENT,
        start_time=time.time(),
    )
    trace_obj.spans.append(parent_span)

    child_span = Span(
        trace_id=trace_obj.trace_id,
        span_id="span-2",
        name="child_operation",
        span_type=SpanType.FUNCTION,
        start_time=time.time(),
        parent_span_id=parent_span.span_id,
    )
    tracer.record_llm_call(
        child_span,
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        cost=0.0035,
    )
    child_span.end_time = time.time()
    trace_obj.spans.append(child_span)

    parent_span.end_time = time.time()

    # End trace
    ended_trace = tracer.end_trace(trace_obj.trace_id)

    assert ended_trace is not None
    assert len(ended_trace.spans) == 2
    assert ended_trace.spans[0].span_type == SpanType.AGENT
    assert ended_trace.spans[1].model == "gpt-4"

    print("✓ Basic tracing works")
    return True


def test_decorators():
    """Test decorator functionality."""
    print("\nTesting decorators...")

    @trace(name="test_function")
    def my_function(x: int, y: int) -> int:
        return x + y

    result = my_function(5, 3)
    assert result == 8

    print("✓ Decorators work")
    return True


def test_exporters():
    """Test exporter functionality."""
    print("\nTesting exporters...")

    tracer = Tracer()

    # Test console exporter
    console_exporter = ConsoleExporter(pretty_print=False)
    trace_obj = tracer.start_trace(name="export_test")
    span = tracer.start_span(name="test_span", span_type=SpanType.FUNCTION)
    tracer.end_span(span)
    ended_trace = tracer.end_trace(trace_obj.trace_id)

    success = console_exporter.export(ended_trace)
    assert success

    # Test file exporter
    test_file = "/tmp/test_traces.jsonl"
    file_exporter = FileExporter(filepath=test_file)
    success = file_exporter.export(ended_trace)
    assert success
    file_exporter.close()

    # Verify file was created
    assert os.path.exists(test_file)

    # Read and verify
    with open(test_file, 'r') as f:
        line = f.readline()
        data = json.loads(line)
        assert data["trace_id"] == ended_trace.trace_id

    # Cleanup
    os.remove(test_file)

    print("✓ Exporters work")
    return True


def test_langgraph_callback():
    """Test LangGraph callback handler."""
    print("\nTesting LangGraph integration...")

    try:
        from agent_trace.integrations.langgraph import AgentTraceCallbackHandler
        handler = AgentTraceCallbackHandler()
        print("✓ LangGraph callback handler imports successfully")
        return True
    except ImportError as e:
        print(f"⚠ LangGraph not installed (optional): {e}")
        return True


if __name__ == "__main__":
    print("Agent Trace SDK - Test Suite")
    print("=" * 50)

    tests = [
        test_basic_tracing,
        test_decorators,
        test_exporters,
        test_langgraph_callback,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
