"""
Benchmark Script for AI Memory System

Measures performance metrics for vector operations at different scales:
- Upsert throughput (vectors/second)
- Query latency (p50, p95, p99)
- Memory usage
- Index size

Usage:
    uv run python scripts/benchmark.py
"""

import time
import statistics
import sys
import numpy as np
import httpx
from typing import List, Dict, Any

# Configuration
API_URL = "http://localhost:8000"
VECTOR_DIM = 384
SCALES = [1_000, 10_000, 100_000]


def print_progress(current: int, total: int, prefix: str = "", suffix: str = ""):
    """Print progress bar to terminal."""
    bar_length = 40
    filled = int(bar_length * current / total)
    bar = "█" * filled + "░" * (bar_length - filled)
    percent = 100 * current / total
    sys.stdout.write(f"\r{prefix} |{bar}| {percent:.1f}% {suffix}")
    sys.stdout.flush()
    if current == total:
        print()  # New line when complete


def generate_vectors(count: int, dim: int = VECTOR_DIM) -> List[Dict[str, Any]]:
    """Generate random normalized vectors."""
    print(f"📊 Generating {count:,} random {dim}-dimensional vectors...")
    vectors = np.random.randn(count, dim).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    return [
        {
            "id": i,  # Use integer IDs (Qdrant accepts unsigned integers)
            "vector": vectors[i].tolist(),
            "payload": {"index": i, "batch": i // 1000},
        }
        for i in range(count)
    ]


def benchmark_upsert(
    client: httpx.Client, vectors: List[Dict], batch_size: int = 100
) -> Dict[str, float]:
    """Measure upsert throughput."""
    total_vectors = len(vectors)
    total_batches = (total_vectors + batch_size - 1) // batch_size
    print(f"⬆️  Upserting {total_vectors:,} vectors in {total_batches} batches...")

    start_time = time.perf_counter()

    # Batch upsert with progress
    for batch_num, i in enumerate(range(0, total_vectors, batch_size), 1):
        batch = vectors[i : i + batch_size]
        response = client.post(
            f"{API_URL}/upsert", json={"points": batch}, timeout=30.0
        )
        response.raise_for_status()

        # Update progress every 10 batches or at completion
        if batch_num % 10 == 0 or batch_num == total_batches:
            print_progress(
                batch_num,
                total_batches,
                "   Uploading",
                f"({batch_num}/{total_batches} batches)",
            )

    elapsed = time.perf_counter() - start_time
    throughput = total_vectors / elapsed

    return {
        "total_vectors": total_vectors,
        "elapsed_seconds": round(elapsed, 2),
        "throughput_vectors_per_sec": round(throughput, 2),
    }


def benchmark_query(
    client: httpx.Client, query_vector: List[float], iterations: int = 100
) -> Dict[str, float]:
    """Measure query latency percentiles."""
    print(f"🔍 Running {iterations} query iterations...")
    latencies = []

    for i in range(iterations):
        start = time.perf_counter()
        response = client.post(
            f"{API_URL}/query", json={"vector": query_vector, "limit": 10}, timeout=10.0
        )
        response.raise_for_status()
        latencies.append((time.perf_counter() - start) * 1000)  # Convert to ms

        # Show progress every 20 queries
        if (i + 1) % 20 == 0 or (i + 1) == iterations:
            print_progress(
                i + 1, iterations, "   Querying", f"({i + 1}/{iterations} queries)"
            )

    latencies.sort()

    return {
        "iterations": iterations,
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(latencies[int(0.95 * len(latencies))], 2),
        "p99_ms": round(latencies[int(0.99 * len(latencies))], 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
    }


def get_collection_info(client: httpx.Client) -> Dict[str, Any]:
    """Get collection statistics."""
    response = client.get(f"{API_URL}/collections", timeout=10.0)
    response.raise_for_status()
    data = response.json()

    for collection in data["collections"]:
        if collection["name"] == "ai_memory":
            return collection

    return {"name": "ai_memory", "vectors_count": 0}


def run_benchmark(scale: int) -> Dict[str, Any]:
    """Run complete benchmark for given scale."""
    print(f"\n{'=' * 60}")
    print(f"📈 Benchmarking at scale: {scale:,} vectors")
    print(f"{'=' * 60}")

    with httpx.Client() as client:
        # Generate test data
        vectors = generate_vectors(scale)
        print("   ✓ Vectors generated\n")

        # Benchmark upsert
        upsert_results = benchmark_upsert(client, vectors)
        print(
            f"   ✓ Throughput: {upsert_results['throughput_vectors_per_sec']:,.0f} vectors/sec"
        )
        print(f"   ✓ Time: {upsert_results['elapsed_seconds']}s\n")

        # Benchmark query
        query_vector = vectors[0]["vector"]  # Use first vector
        query_results = benchmark_query(client, query_vector)
        print(
            f"   ✓ p50: {query_results['p50_ms']}ms | p95: {query_results['p95_ms']}ms | p99: {query_results['p99_ms']}ms\n"
        )

        # Get collection stats
        print("📊 Fetching collection statistics...")
        collection_info = get_collection_info(client)
        print(f"   ✓ Total vectors in collection: {collection_info['vectors_count']:,}")

    return {
        "scale": scale,
        "upsert": upsert_results,
        "query": query_results,
        "collection": collection_info,
    }


def print_summary_table(results: List[Dict[str, Any]]):
    """Print formatted summary table."""
    print(f"\n{'=' * 80}")
    print("BENCHMARK SUMMARY")
    print(f"{'=' * 80}")
    print(
        f"{'Scale':<15} {'Upsert (vec/s)':<20} {'Query p95 (ms)':<20} {'Vectors Stored':<20}"
    )
    print(f"{'-' * 80}")

    for result in results:
        scale = f"{result['scale']:,}"
        throughput = f"{result['upsert']['throughput_vectors_per_sec']:,.0f}"
        p95 = f"{result['query']['p95_ms']}"
        stored = f"{result['collection']['vectors_count']:,}"

        print(f"{scale:<15} {throughput:<20} {p95:<20} {stored:<20}")

    print(f"{'=' * 80}\n")


def main():
    """Run benchmarks for all scales."""
    print("=" * 80)
    print("🚀 AI Memory System - Performance Benchmark")
    print("=" * 80)
    print(f"📡 API: {API_URL}")
    print(f"📏 Vector Dimension: {VECTOR_DIM}")
    print(f"📊 Scales: {', '.join(f'{s:,}' for s in SCALES)} vectors\n")

    # Check API is running
    print("🔍 Checking API health...")
    try:
        response = httpx.get(f"{API_URL}/health", timeout=5.0)
        response.raise_for_status()
        print("   ✓ API is healthy and ready\n")
    except Exception as e:
        print(f"   ✗ Cannot connect to API: {e}")
        print("   💡 Please start the API: docker compose up -d")
        return

    results = []

    for idx, scale in enumerate(SCALES, 1):
        print(f"\n{'=' * 80}")
        print(f"📋 Running benchmark {idx}/{len(SCALES)}")
        print(f"{'=' * 80}")
        try:
            result = run_benchmark(scale)
            results.append(result)
        except KeyboardInterrupt:
            print("\n\n⚠️  Benchmark interrupted by user (Ctrl+C)")
            break
        except Exception as e:
            print(f"\n✗ Error at scale {scale:,}: {e}")
            import traceback

            traceback.print_exc()
            break

    if results:
        print_summary_table(results)

        # Save results
        import json
        from pathlib import Path

        # Ensure output directory exists
        output_dir = Path("data/benchmarks")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "benchmark_results.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to: {output_file}")
        print("✅ Benchmark complete!")
    else:
        print("\n⚠️  No results to save")


if __name__ == "__main__":
    main()
