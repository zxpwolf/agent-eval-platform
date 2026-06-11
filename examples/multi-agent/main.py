"""Example: Multi-agent collaboration with tracing.

This example demonstrates how to trace a multi-agent system where
multiple agents collaborate to solve a complex task.
"""

import sys
import os
import time

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sdk/python"))

from agent_trace import trace, get_tracer, FileExporter
from agent_trace.models import SpanType


def setup_tracing():
    """Configure tracing for the example."""
    tracer = get_tracer()
    tracer._exporter = FileExporter(filepath="multi_agent_traces.jsonl")
    return tracer


@trace(span_type=SpanType.AGENT)
def researcher_agent(task: str) -> dict:
    """Simulate a researcher agent that gathers information."""
    print(f"🔍 Researcher: Investigating '{task}'...")

    # Simulate research steps
    sources = [
        "Academic papers",
        "Industry reports",
        "Expert interviews",
    ]

    findings = {
        "task": task,
        "sources_consulted": sources,
        "key_findings": [
            f"Finding 1 about {task}",
            f"Finding 2 about {task}",
        ],
        "confidence": 0.85,
    }

    print(f"✓ Researcher completed: {len(findings['key_findings'])} findings")
    return findings


@trace(span_type=SpanType.AGENT)
def analyst_agent(research_data: dict) -> dict:
    """Simulate an analyst agent that analyzes research."""
    print(f"📊 Analyst: Analyzing research data...")

    analysis = {
        "data_points": len(research_data.get("key_findings", [])),
        "insights": [
            "Trend identified in market dynamics",
            "Risk factors detected",
        ],
        "recommendations": [
            "Proceed with caution",
            "Monitor key metrics",
        ],
    }

    print(f"✓ Analyst completed: {len(analysis['insights'])} insights")
    return analysis


@trace(span_type=SpanType.AGENT)
def writer_agent(analysis: dict, topic: str) -> str:
    """Simulate a writer agent that creates final output."""
    print(f"✍️ Writer: Drafting report on '{topic}'...")

    report = f"""
# Report: {topic}

## Analysis Summary
- Data Points: {analysis['data_points']}
- Key Insights: {len(analysis['insights'])}

## Insights
{chr(10).join(f'- {insight}' for insight in analysis['insights'])}

## Recommendations
{chr(10).join(f'- {rec}' for rec in analysis['recommendations'])}
    """.strip()

    print(f"✓ Writer completed: {len(report)} characters")
    return report


@trace(span_type=SpanType.AGENT)
def coordinator_agent(topic: str) -> dict:
    """Coordinate multiple agents to complete a complex task."""
    print(f"🎯 Coordinator: Starting multi-agent workflow for '{topic}'")

    # Step 1: Research
    research_data = researcher_agent(topic)

    # Step 2: Analysis
    analysis = analyst_agent(research_data)

    # Step 3: Writing
    final_report = writer_agent(analysis, topic)

    result = {
        "topic": topic,
        "status": "completed",
        "report_length": len(final_report),
        "agents_used": ["researcher", "analyst", "writer"],
    }

    print(f"✓ Coordinator: Workflow completed")
    return result


def parallel_agents_example():
    """Example: Run multiple agents in parallel."""
    from concurrent.futures import ThreadPoolExecutor

    print("\n=== Parallel Agents Example ===")

    @trace(span_type=SpanType.AGENT)
    def worker_agent(task_id: int) -> dict:
        """Simulate a worker agent processing a task."""
        time.sleep(0.1)  # Simulate work
        return {"task_id": task_id, "result": f"Result for task {task_id}"}

    # Run multiple agents in parallel
    tasks = list(range(5))
    results = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(worker_agent, task_id) for task_id in tasks]
        for future in futures:
            results.append(future.result())

    print(f"✓ Completed {len(results)} parallel tasks")
    return results


if __name__ == "__main__":
    print("Multi-Agent Collaboration Examples")
    print("=" * 60)

    # Setup tracing
    tracer = setup_tracing()

    # Example 1: Sequential multi-agent workflow
    print("\n1. Sequential Multi-Agent Workflow")
    print("-" * 40)
    result = coordinator_agent("AI Safety Trends")
    print(f"\nFinal result: {result}")

    # Example 2: Parallel agents
    parallel_agents_example()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("Check 'multi_agent_traces.jsonl' for trace data")
