"""Mock LLM server for deterministic replay.

This module provides a mock server that simulates LLM API responses
based on recorded execution logs, enabling deterministic replay.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .models import RecordedCall, ReplayAction, ReplayLog

logger = logging.getLogger(__name__)


class MockLLMResponse:
    """A mock LLM response."""

    def __init__(self, content: str, model: str = "gpt-4", tokens: Dict[str, int] = None):
        self.content = content
        self.model = model
        self.prompt_tokens = tokens.get("prompt_tokens", 0) if tokens else 0
        self.completion_tokens = tokens.get("completion_tokens", 0) if tokens else 0


class MockLLMServer:
    """Mock LLM server that replays recorded responses.

    This server maintains a queue of recorded LLM calls and returns
    the recorded responses in order when called during replay.
    """

    def __init__(self):
        self._call_queue: List[RecordedCall] = []
        self._current_index: int = 0
        self._is_active: bool = False

    def load_log(self, log: ReplayLog):
        """Load a replay log and extract LLM calls."""
        self._call_queue = [
            call for call in log.calls
            if call.action_type == ReplayAction.LLM_CALL
        ]
        self._current_index = 0
        self._is_active = True
        logger.info(f"Loaded {len(self._call_queue)} LLM calls for mock server")

    def reset(self):
        """Reset the server state."""
        self._call_queue.clear()
        self._current_index = 0
        self._is_active = False

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        **kwargs: Any,
    ) -> MockLLMResponse:
        """Simulate a chat completion call."""
        if not self._is_active or self._current_index >= len(self._call_queue):
            # Fallback: generate a simple response
            logger.warning("No recorded response available, using fallback")
            return MockLLMResponse(
                content="Mock response (no recording available)",
                model=model,
                tokens={"prompt_tokens": 10, "completion_tokens": 20},
            )

        # Get the next recorded response
        recorded_call = self._call_queue[self._current_index]
        self._current_index += 1

        # Simulate latency if preserve_timing is enabled
        if recorded_call.duration_ms > 0:
            await asyncio.sleep(recorded_call.duration_ms / 1000.0)

        # Extract response from recorded data
        output_data = recorded_call.output_data
        if isinstance(output_data, dict):
            content = output_data.get("content", str(output_data))
        elif isinstance(output_data, str):
            content = output_data
        else:
            content = str(output_data) if output_data else ""

        return MockLLMResponse(
            content=content,
            model=recorded_call.model or model,
            tokens={
                "prompt_tokens": recorded_call.prompt_tokens or 0,
                "completion_tokens": recorded_call.completion_tokens or 0,
            },
        )

    def sync_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        **kwargs: Any,
    ) -> MockLLMResponse:
        """Synchronous version of chat_completion."""
        if not self._is_active or self._current_index >= len(self._call_queue):
            logger.warning("No recorded response available, using fallback")
            return MockLLMResponse(
                content="Mock response (no recording available)",
                model=model,
                tokens={"prompt_tokens": 10, "completion_tokens": 20},
            )

        recorded_call = self._call_queue[self._current_index]
        self._current_index += 1

        output_data = recorded_call.output_data
        if isinstance(output_data, dict):
            content = output_data.get("content", str(output_data))
        elif isinstance(output_data, str):
            content = output_data
        else:
            content = str(output_data) if output_data else ""

        return MockLLMResponse(
            content=content,
            model=recorded_call.model or model,
            tokens={
                "prompt_tokens": recorded_call.prompt_tokens or 0,
                "completion_tokens": recorded_call.completion_tokens or 0,
            },
        )

    def has_more_calls(self) -> bool:
        """Check if there are more recorded calls."""
        return self._current_index < len(self._call_queue)

    def remaining_calls(self) -> int:
        """Get the number of remaining recorded calls."""
        return max(0, len(self._call_queue) - self._current_index)


class MockToolServer:
    """Mock tool server that replays recorded tool responses."""

    def __init__(self):
        self._call_queue: List[RecordedCall] = []
        self._current_index: int = 0
        self._is_active: bool = False

    def load_log(self, log: ReplayLog):
        """Load a replay log and extract tool calls."""
        self._call_queue = [
            call for call in log.calls
            if call.action_type == ReplayAction.TOOL_CALL
        ]
        self._current_index = 0
        self._is_active = True
        logger.info(f"Loaded {len(self._call_queue)} tool calls for mock server")

    def reset(self):
        """Reset the server state."""
        self._call_queue.clear()
        self._current_index = 0
        self._is_active = False

    def execute_tool(self, tool_name: str, input_data: Any) -> Any:
        """Execute a tool call with recorded response."""
        if not self._is_active or self._current_index >= len(self._call_queue):
            logger.warning(f"No recorded response for tool {tool_name}, using fallback")
            return f"Mock result for {tool_name}"

        recorded_call = self._call_queue[self._current_index]
        self._current_index += 1

        return recorded_call.output_data

    def has_more_calls(self) -> bool:
        """Check if there are more recorded calls."""
        return self._current_index < len(self._call_queue)


# Global mock servers
_mock_llm_server = MockLLMServer()
_mock_tool_server = MockToolServer()


def get_mock_llm_server() -> MockLLMServer:
    """Get the global mock LLM server."""
    return _mock_llm_server


def get_mock_tool_server() -> MockToolServer:
    """Get the global mock tool server."""
    return _mock_tool_server


def initialize_mock_servers(log: ReplayLog):
    """Initialize both mock servers with a replay log."""
    _mock_llm_server.load_log(log)
    _mock_tool_server.load_log(log)
