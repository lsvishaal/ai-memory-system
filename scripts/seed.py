"""
Embedding Generation Script

Generates synthetic text embeddings for development and testing.
Uses sentence-transformers to create normalized vector representations
of AI/ML related documents for similarity search operations.
"""
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
from datetime import datetime, UTC


def generate_embeddings(count: int = 1000) -> dict:
    """
    Generate normalized embeddings from synthetic documents.
    
    Creates a diverse set of documents about AI/ML topics, converts them
    to vector embeddings using a pre-trained transformer model, and saves
    the results to disk for use in development and testing.
    
    Args:
        count: Number of document embeddings to generate
    
    Returns:
        Dictionary containing generation metadata (count, dimensions, model info)
    """
    print(f"\n{'='*60}")
    print(f"Generating {count} embeddings")
    print(f"{'='*60}\n")
    
    # Load pre-trained model (downloads ~100MB on first run)
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    print("First run will download model files (~100MB)")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Model loaded\n")
    
    # Generate diverse synthetic documents
    print(f"Generating {count} synthetic documents...")
    topics = [
        "machine learning", "artificial intelligence", "deep learning",
        "neural networks", "vector database", "embeddings", "transformers",
        "natural language processing", "computer vision", "reinforcement learning"
    ]
    
    sentences = []
    for i in range(count):
        topic = topics[i % len(topics)]
        sentences.append(
            f"Document {i}: This document discusses {topic}, "
            f"semantic search, and AI memory systems. "
            f"Category: {i % 100}. Research area: Vector databases."
        )
    print(f"Generated {len(sentences)} documents\n")
    
    # Convert text to vector embeddings
    print(f"Encoding {count} documents to vectors...")
    print("This may take 30-60 seconds")
    embeddings = model.encode(
        sentences,
        show_progress_bar=True,
        batch_size=32,
        normalize_embeddings=True  # L2 normalization for cosine similarity
    )
    print("Encoding complete\n")
    
    # Package data with metadata
    data = {
        "metadata": {
            "count": len(embeddings),
            "dimensions": embeddings.shape[1],
            "model": "all-MiniLM-L6-v2",
            "normalized": True,
            "generated_at": datetime.now(UTC).isoformat()
        },
        "samples": [
            {
                "id": i,
                "text": sentences[i],
                "embedding": embeddings[i].tolist()
            }
            for i in range(len(embeddings))
        ]
    }
    
    # Write to disk
    output_path = Path("data/seed_embeddings.json")
    output_path.parent.mkdir(exist_ok=True)
    
    print(f"Saving embeddings to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    file_size_mb = output_path.stat().st_size / 1024 / 1024
    
    # Summary
    print(f"\n{'='*60}")
    print("Generation complete")
    print(f"{'='*60}")
    print("Statistics:")
    print(f"  Embeddings: {len(embeddings)}")
    print(f"  Dimensions: {embeddings.shape[1]}")
    print(f"  Normalized: {data['metadata']['normalized']}")
    print(f"  File: {output_path}")
    print(f"  Size: {file_size_mb:.2f} MB")
    print(f"{'='*60}\n")
    
    return data["metadata"]


if __name__ == "__main__":
    generate_embeddings(1000)
