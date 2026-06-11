"""Example: LlamaIndex RAG application with tracing.

This example demonstrates how to add observability to a LlamaIndex RAG pipeline.
"""

import sys
import os

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sdk/python"))

from agent_trace import get_tracer, FileExporter
from agent_trace.integrations.llamaindex import setup_llamaindex_tracing


def setup_tracing():
    """Configure tracing for the example."""
    tracer = get_tracer()
    tracer._exporter = FileExporter(filepath="llamaindex_traces.jsonl")
    return tracer


def basic_rag_example():
    """Example: Basic RAG pipeline with tracing.

    Note: This is a structural example. Replace with your actual data and configuration.
    """
    print("\n=== LlamaIndex RAG Example ===")
    print("This example shows how to integrate tracing with LlamaIndex")
    print("=" * 60)

    # Setup tracing
    tracer = setup_tracing()
    handler = setup_llamaindex_tracing(tracer)

    print("\n✓ Tracing enabled for LlamaIndex")
    print("  The handler will automatically capture:")
    print("  - LLM completions")
    print("  - Embedding operations")
    print("  - Retrieval operations")
    print("  - Query engine executions")

    # Example structure (requires actual LlamaIndex setup):
    """
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, ServiceContext
    from llama_index.llms.openai import OpenAI
    from llama_index.embeddings.openai import OpenAIEmbedding

    # Create service context
    llm = OpenAI(model="gpt-4")
    embed_model = OpenAIEmbedding()
    service_context = ServiceContext.from_defaults(llm=llm, embed_model=embed_model)

    # Load documents
    documents = SimpleDirectoryReader("./data").load_data()

    # Create index
    index = VectorStoreIndex.from_documents(documents, service_context=service_context)

    # Create query engine
    query_engine = index.as_query_engine()

    # Execute query (will be traced automatically)
    response = query_engine.query("What is the main topic?")
    print(f"Response: {response}")
    """

    print("\nTo use this example:")
    print("1. Install dependencies: pip install llama-index llama-index-llms-openai")
    print("2. Set OPENAI_API_KEY environment variable")
    print("3. Uncomment and configure the code above with your data")
    print("4. Run the script to see traces in llamaindex_traces.jsonl")


def manual_span_example():
    """Example: Manually create spans for custom operations."""
    from agent_trace import trace
    from agent_trace.models import SpanType

    print("\n=== Manual Span Example ===")

    @trace(span_type=SpanType.EMBEDDING)
    def custom_embed(texts: list):
        """Custom embedding function."""
        # Simulate embedding
        return [[0.1, 0.2, 0.3] for _ in texts]

    @trace(span_type=SpanType.RETRIEVER)
    def custom_retrieve(query: str, top_k: int = 5):
        """Custom retrieval function."""
        # Simulate retrieval
        return [f"Document {i}" for i in range(top_k)]

    # These will be automatically traced
    embeddings = custom_embed(["text1", "text2"])
    results = custom_retrieve("search query", top_k=3)

    print(f"✓ Created {len(embeddings)} embeddings")
    print(f"✓ Retrieved {len(results)} documents")


if __name__ == "__main__":
    print("LlamaIndex Integration Examples")
    print("=" * 60)

    try:
        basic_rag_example()
    except ImportError as e:
        print(f"\n⚠ LlamaIndex not installed: {e}")
        print("Install with: pip install llama-index")

    manual_span_example()

    print("\n" + "=" * 60)
    print("Examples completed!")
