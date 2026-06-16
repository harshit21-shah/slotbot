#!/usr/bin/env python
"""
Latency benchmark for the SlotBot pipeline.

Measures:
  - LLM (Groq) first-token latency
  - TTS (Sarvam AI) latency per sentence
  - Full turn latency (LLM + TTS combined)

Usage:
    python scripts/latency_bench.py
    python scripts/latency_bench.py --iterations 20
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agents.llm_client import complete_json
from services.tts.sarvam_client import text_to_mulaw

_TEST_TEXTS = [
    "Namaste! Aap kab aana chahte hain?",
    "Rahul ji, kya 10 baje ka slot theek rahega?",
    "Aapka appointment confirm ho gaya Dr. Sharma ke saath kal subah 10 baje.",
    "Aapka naam kya hai?",
    "Sorry, main samajh nahi paya. Kya aap thoda clearly bol sakte hain?",
]

_TEST_PROMPT = """
You are SlotBot. Extract the name from: "Main Rahul hoon, kal 10 baje appointment chahiye"
Return JSON: {"extracted_name": "Rahul", "confidence": 0.95, "response": "Rahul ji, zaroor!"}
"""


async def bench_llm(n: int) -> list[float]:
    latencies = []
    print(f"\n📊 LLM (Groq) latency — {n} calls")
    for i in range(n):
        t0 = time.perf_counter()
        await complete_json(_TEST_PROMPT)
        ms = (time.perf_counter() - t0) * 1000
        latencies.append(ms)
        print(f"  [{i+1}/{n}] {ms:.0f}ms")
    return latencies


async def bench_tts(n: int) -> list[float]:
    latencies = []
    print(f"\n📊 TTS (Sarvam AI) latency — {n} calls per text")
    for text in _TEST_TEXTS:
        turn_latencies = []
        for _ in range(n):
            t0 = time.perf_counter()
            await text_to_mulaw(text, "hinglish")
            ms = (time.perf_counter() - t0) * 1000
            turn_latencies.append(ms)
        avg = statistics.mean(turn_latencies)
        print(f"  avg={avg:.0f}ms  text='{text[:40]}...'")
        latencies.extend(turn_latencies)
    return latencies


def print_stats(name: str, latencies: list[float]) -> None:
    if not latencies:
        return
    s = sorted(latencies)
    print(f"\n  {name}")
    print(f"    p50  = {s[len(s)//2]:.0f}ms")
    print(f"    p90  = {s[int(len(s)*0.9)]:.0f}ms")
    print(f"    p95  = {s[int(len(s)*0.95)]:.0f}ms")
    print(f"    mean = {statistics.mean(s):.0f}ms")
    print(f"    min  = {s[0]:.0f}ms  max = {s[-1]:.0f}ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark SlotBot pipeline latency")
    parser.add_argument("--iterations", "-n", type=int, default=10)
    parser.add_argument("--skip-tts", action="store_true", help="Skip TTS benchmark")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM benchmark")
    args = parser.parse_args()

    async def run() -> None:
        print("=== SlotBot Latency Benchmark ===")
        print(f"Iterations: {args.iterations}")

        llm_latencies: list[float] = []
        tts_latencies: list[float] = []

        if not args.skip_llm:
            llm_latencies = await bench_llm(args.iterations)

        if not args.skip_tts:
            tts_latencies = await bench_tts(args.iterations)

        print("\n=== Results ===")
        if llm_latencies:
            print_stats("LLM (Groq first-token)", llm_latencies)
        if tts_latencies:
            print_stats("TTS (Sarvam AI)", tts_latencies)

        if llm_latencies and tts_latencies:
            combined = [l + t for l, t in zip(
                sorted(llm_latencies)[:len(tts_latencies)],
                sorted(tts_latencies)[:len(llm_latencies)]
            )]
            print_stats("Combined LLM+TTS (estimated turn latency)", combined)

        target_p95 = 800
        p95_combined = sorted(llm_latencies + tts_latencies)
        if p95_combined:
            p95 = p95_combined[int(len(p95_combined) * 0.95)]
            status = "✅ PASS" if p95 < target_p95 else "❌ FAIL"
            print(f"\n  Target p95 < {target_p95}ms: {status}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
