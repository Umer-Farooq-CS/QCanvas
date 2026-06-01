# === CELL 1 ===
# Setup and Imports
import sys
import json
from pathlib import Path
import numpy as np

# Add project root to path
project_root = Path("..").resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import get_config, get_config_loader

# Import RAG components from src
from src.rag import (
    VectorStore, 
    EmbeddingModel, 
    KnowledgeBase,
    Retriever,
    extract_query_keywords,
    DEFAULT_TOPIC_BOOST,
)

print("✅ Imports successful!")
print(f"Default Topic Boost: {DEFAULT_TOPIC_BOOST}")

# === CELL 3 ===
# Define paths
KNOWLEDGE_BASE_DIR = project_root / "data" / "knowledge_base"
VECTOR_INDEX_PATH = project_root / "data" / "models" / "vector_index"

# Initialize Knowledge Base with the path
knowledge_base = KnowledgeBase(
    knowledge_base_path=KNOWLEDGE_BASE_DIR,
)

# Load entries from directory (this populates entry_by_id)
num_loaded = knowledge_base.load_from_directory()

print(f"\n✅ Loaded {num_loaded} entries from knowledge base.")
print(f"Entries indexed by ID: {len(knowledge_base.entry_by_id)}")

# === CELL 5 ===
# Display sample entries
print("Sample entries:")
for i, entry in enumerate(knowledge_base.entries[:3]):
    print(f"\n--- Entry {i+1} ---")
    print(f"ID: {entry.get('id', 'N/A')}")
    print(f"Difficulty: {entry.get('difficulty', 'N/A')}")
    print(f"Topics: {entry.get('topics', [])}")
    print(f"Task: {entry.get('task', 'N/A')[:100]}...")

# === CELL 7 ===
# Index all entries (generates embeddings and adds to vector store)
print("Indexing entries... (this may take a moment)")
knowledge_base.index_entries(batch_size=16)

print(f"\n✅ Vector store size: {knowledge_base.vector_store.size()}")

# === CELL 9 ===
# Create Retriever with hybrid scoring
retriever = Retriever(
    knowledge_base=knowledge_base,
    top_k=5,
    similarity_threshold=0.3,   # Lower threshold to see more results
    topic_boost=0.15,           # Boost per matching topic
    use_hybrid_scoring=True,    # Enable topic boosting
)

print("✅ Retriever initialized with HYBRID SCORING enabled!")
print(f"   Topic boost per match: {retriever.topic_boost}")
print(f"   Similarity threshold: {retriever.similarity_threshold}")

# === CELL 11 ===
# Define test prompts
test_prompts = [
    "Create a Bell state circuit with two qubits",
    "Implement Grover's search algorithm",
    "Build a QAOA circuit for MaxCut optimization",
    "Quantum phase estimation example",
    "How to implement quantum teleportation",
    "bell_state entanglement",  # Topic-focused query
    "qpe phase_estimation",     # Topic-focused query
]

print(f"Testing with {len(test_prompts)} prompts...")
print("📌 Using HYBRID SCORING from src.rag.Retriever!\n")

# === CELL 12 ===
# Run tests for each prompt
for i, prompt in enumerate(test_prompts, 1):
    print("=" * 80)
    print(f"Test {i}: \"{prompt}\"")
    print("=" * 80)
    
    # Show keywords extracted
    keywords = extract_query_keywords(prompt)
    print(f"Query Keywords: {keywords}")
    
    # Use Retriever from src.rag
    results = retriever.retrieve_with_metadata(prompt, top_k=5)
    
    if results:
        print(f"\nTop 5 Retrieved Entries (Hybrid Scoring):")
        for rank, res in enumerate(results, 1):
            entry = res.get('entry', {})
            entry_id = entry.get('id', res.get('id', 'N/A'))
            hybrid_score = res.get('score', 0)
            semantic_score = res.get('semantic_score', hybrid_score)
            topic_boost = res.get('topic_boost', 0)
            difficulty = entry.get('difficulty', 'N/A')
            topics = entry.get('topics', [])
            task_preview = entry.get('task', entry.get('description', 'N/A'))[:60]
            
            boost_str = f" +{topic_boost:.2f}" if topic_boost > 0 else ""
            print(f"\n  #{rank} [Score: {hybrid_score:.4f} = {semantic_score:.4f}{boost_str}]")
            print(f"      ID: {entry_id}")
            print(f"      Difficulty: {difficulty}")
            print(f"      Topics: {', '.join(topics[:5]) if topics else 'N/A'}")
            print(f"      Task: {task_preview}...")
    else:
        print("  No results found.")
    
    print()

# === CELL 14 ===
# Save the index
knowledge_base.save_index(VECTOR_INDEX_PATH)

print(f"✅ Vector store saved to: {VECTOR_INDEX_PATH}")
print(f"   Total entries indexed: {knowledge_base.vector_store.size()}")

# === CELL 16 ===
# Create new KnowledgeBase and load from disk
loaded_kb = KnowledgeBase(knowledge_base_path=KNOWLEDGE_BASE_DIR)
loaded_kb.load_from_directory()  # Load entries first
loaded_kb.load_index(VECTOR_INDEX_PATH)  # Then load vector index

# Create Retriever
loaded_retriever = Retriever(
    knowledge_base=loaded_kb,
    use_hybrid_scoring=True,
    similarity_threshold=0.3,
)

print(f"✅ Loaded from disk.")
print(f"   Entries: {len(loaded_kb.entries)}")
print(f"   Vector store size: {loaded_kb.vector_store.size()}")

# Test
test_query = "Create a bell state circuit"
print(f"\nVerification Query: \"{test_query}\"")
print(f"Query Keywords: {extract_query_keywords(test_query)}")
print(f"\nTop 5 Results (Hybrid Scoring):")

verify_results = loaded_retriever.retrieve(test_query, top_k=5)
for res in verify_results:
    entry = res.get('entry', {})
    topics = entry.get('topics', [])
    boost = res.get('topic_boost', 0)
    boost_str = f" [+{boost:.2f} boost]" if boost > 0 else ""
    print(f"  - {entry.get('id', 'N/A')} (Score: {res['score']:.4f}){boost_str} | Topics: {', '.join(topics[:4]) if topics else 'N/A'}")

# === CELL 17 ===
# =============================================================================
# Test Retrieval for VALIDATOR and OPTIMIZER Agents
# =============================================================================
print("=" * 80)
print("VALIDATOR & OPTIMIZER AGENT RETRIEVAL TESTS")
print("=" * 80)
print()

# Test prompts for Validator (looking for validation examples with expected outputs)
validator_prompts = [
    "validate bell state circuit expected output",
    "validate grover algorithm correctness",
    "check quantum teleportation measurement results",
]

# Test prompts for Optimizer (looking for optimization patterns)
optimizer_prompts = [
    "optimize circuit reduce depth gates",
    "cancel consecutive gates optimization",
    "merge single qubit gates PhasedXZ",
]

print("🔍 VALIDATOR AGENT RETRIEVAL TESTS")
print("-" * 50)
for i, prompt in enumerate(validator_prompts, 1):
    print(f"\n📌 Validator Query {i}: \"{prompt}\"")
    keywords = extract_query_keywords(prompt)
    print(f"   Keywords: {keywords}")
    
    results = retriever.retrieve_with_metadata(prompt, top_k=3)
    for rank, res in enumerate(results, 1):
        entry = res.get('entry', {})
        entry_id = entry.get('id', 'N/A')
        topics = entry.get('topics', [])
        score = res.get('score', 0)
        boost = res.get('topic_boost', 0)
        # Check if it's a validation example
        has_expected = "expected_output" in entry or "acceptable_ranges" in entry
        marker = "✅ VALIDATION" if has_expected else ""
        print(f"   #{rank} [{score:.4f}] {entry_id} | Topics: {', '.join(topics[:3])} {marker}")

print("\n")
print("⚡ OPTIMIZER AGENT RETRIEVAL TESTS")
print("-" * 50)
for i, prompt in enumerate(optimizer_prompts, 1):
    print(f"\n📌 Optimizer Query {i}: \"{prompt}\"")
    keywords = extract_query_keywords(prompt)
    print(f"   Keywords: {keywords}")
    
    results = retriever.retrieve_with_metadata(prompt, top_k=3)
    for rank, res in enumerate(results, 1):
        entry = res.get('entry', {})
        entry_id = entry.get('id', 'N/A')
        topics = entry.get('topics', [])
        score = res.get('score', 0)
        # Check if it's an optimization example
        has_optimization = "optimized_code" in entry or "optimization_type" in entry
        marker = "✅ OPTIMIZATION" if has_optimization else ""
        print(f"   #{rank} [{score:.4f}] {entry_id} | Topics: {', '.join(topics[:3])} {marker}")

print("\n" + "=" * 80)
print("✅ All agent retrieval tests completed!")
print("=" * 80)

