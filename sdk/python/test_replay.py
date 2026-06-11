"""Test suite for replay engine."""

import sys
import os
import asyncio
import time

# Add SDK to path
sys.path.insert(0, os.path.dirname(__file__))

from agent_trace.models import Span, SpanType, Trace
from agent_trace.replay import (
    ReplayEngine,
    ExecutionRecorder,
    ReplayController,
    MockLLMServer,
    MockToolServer,
)
from agent_trace.replay.models import RecordedCall, ReplayAction, ReplayLog


def test_recorder():
    """Test execution recorder."""
    print("Testing recorder...")

    recorder = ExecutionRecorder(storage_dir="/tmp/test_replay_logs")

    # Start recording
    log = recorder.start_recording("trace-123", {"agent": "test"})
    assert log.trace_id == "trace-123"

    # Record calls
    from agent_trace.models import Span

    span = Span(
        trace_id="trace-123",
        span_id="span-1",
        name="test_llm",
        span_type=SpanType.LLM,
        start_time=time.time(),
        model="gpt-4",
        prompt_tokens=10,
        completion_tokens=20,
    )
    span.end_time = time.time()

    recorder.record_llm_call("trace-123", span, "input", "output")
    recorder.set_initial_state("trace-123", {"key": "value"})
    recorder.set_final_state("trace-123", {"result": "done"})

    # Stop recording
    saved_log = recorder.stop_recording("trace-123")
    assert saved_log is not None
    assert len(saved_log.calls) == 1

    # Load log
    loaded_log = recorder.load_log(saved_log.log_id)
    assert loaded_log is not None
    assert loaded_log.trace_id == "trace-123"

    # List logs
    logs = recorder.list_logs()
    assert len(logs) > 0

    # Delete log
    success = recorder.delete_log(saved_log.log_id)
    assert success

    print("✓ Recorder tests passed")
    return True


def test_mock_llm_server():
    """Test mock LLM server."""
    print("\nTesting mock LLM server...")

    server = MockLLMServer()

    # Create a sample log
    log = ReplayLog(trace_id="test", log_id="log-1")
    log.calls.append(
        RecordedCall(
            call_id="call-1",
            action_type=ReplayAction.LLM_CALL,
            timestamp=time.time(),
            input_data="Hello",
            output_data="Hi there!",
            model="gpt-4",
            prompt_tokens=5,
            completion_tokens=10,
        )
    )

    # Load log
    server.load_log(log)
    assert server.has_more_calls()
    assert server.remaining_calls() == 1

    # Get response
    response = server.sync_chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        model="gpt-4",
    )
    assert response.content == "Hi there!"
    assert not server.has_more_calls()

    # Reset
    server.reset()
    assert not server.has_more_calls()

    print("✓ Mock LLM server tests passed")
    return True


def test_mock_tool_server():
    """Test mock tool server."""
    print("\nTesting mock tool server...")

    server = MockToolServer()

    # Create a sample log
    log = ReplayLog(trace_id="test", log_id="log-1")
    log.calls.append(
        RecordedCall(
            call_id="call-1",
            action_type=ReplayAction.TOOL_CALL,
            timestamp=time.time(),
            input_data="query",
            output_data="search results",
        )
    )

    # Load log
    server.load_log(log)

    # Execute tool
    result = server.execute_tool("search", "query")
    assert result == "search results"

    print("✓ Mock tool server tests passed")
    return True


async def test_replay_controller():
    """Test replay controller."""
    print("\nTesting replay controller...")

    controller = ReplayController()

    # Create a sample log
    log = ReplayLog(trace_id="test", log_id="log-1")
    log.calls.append(
        RecordedCall(
            call_id="call-1",
            action_type=ReplayAction.LLM_CALL,
            timestamp=time.time(),
            input_data="test",
            output_data="response",
            model="gpt-4",
        )
    )

    # Create session
    session = controller.create_session(log, mock_llm=True, mock_tools=False)
    assert session is not None

    # Play
    success = await controller.play(session.session_id)
    assert success

    # Wait for completion
    await asyncio.sleep(0.5)

    # Check status
    status = controller.get_status(session.session_id)
    assert status["status"] in ["completed", "running"]

    print("✓ Replay controller tests passed")
    return True


def test_replay_engine():
    """Test replay engine."""
    print("\nTesting replay engine...")

    engine = ReplayEngine()

    # Create a sample trace
    trace = Trace(
        trace_id="trace-test",
        name="test_trace",
        start_time=time.time(),
    )
    trace.spans.append(
        Span(
            trace_id="trace-test",
            span_id="span-1",
            name="test_llm",
            span_type=SpanType.LLM,
            start_time=time.time(),
            model="gpt-4",
            input_data="input",
            output_data="output",
            prompt_tokens=10,
            completion_tokens=20,
        )
    )
    trace.spans[0].end_time = time.time()
    trace.end_time = time.time()

    # Export as replay log
    log_id = engine.export_replay_log(trace)
    assert log_id is not None

    # Load and verify
    log = engine.recorder.load_log(log_id)
    assert log is not None
    assert len(log.calls) == 1

    # Cleanup
    engine.recorder.delete_log(log_id)

    print("✓ Replay engine tests passed")
    return True


if __name__ == "__main__":
    print("Replay Engine - Test Suite")
    print("=" * 60)

    tests = [
        test_recorder,
        test_mock_llm_server,
        test_mock_tool_server,
        lambda: asyncio.run(test_replay_controller()),
        test_replay_engine,
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

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
