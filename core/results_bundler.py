"""
core/results_bundler.py
========================

Collects agent results and delivers them to the orchestrator in batches.

This prevents multiple rapid-fire orchestrator calls when agents finish
close together, and avoids unnecessary delays when the batch finishes early.
"""

import asyncio
import time

BUNDLE_WINDOW_SECONDS = 5.0


async def results_bundler(on_results) -> None:
    from core.dispatcher import results_queue, _current_batch

    while True:
        first = await results_queue.get()
        bundle = [first]

        deadline = time.monotonic() + BUNDLE_WINDOW_SECONDS

        while True:
            if not _current_batch and results_queue.empty():
                break

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            try:
                item = await asyncio.wait_for(
                    results_queue.get(),
                    timeout=min(0.1, remaining)
                )
                bundle.append(item)
            except asyncio.TimeoutError:
                pass

        try:
            await on_results(bundle)
        except Exception as e:
            print(f"⚠️  Results bundler callback error: {e}")
