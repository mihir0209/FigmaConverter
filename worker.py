#!/usr/bin/env python3
"""Background worker that polls JobStore for queued conversions.

Usage:
    python worker.py                    # single-threaded (default)
    python worker.py --concurrency 2    # N concurrent workers
    python worker.py --once             # claim one job, process it, exit

Environment:
    JOB_POLL_INTERVAL_SECONDS   polling interval (default: 2)
    FIGMA_MAX_CONCURRENCY       max parallel Figma API calls (default: 5)
    AI_MAX_CONCURRENCY          max parallel AI requests (default: 3)
    LOG_LEVEL                   logging level (default: INFO)

The worker runs independently of the FastAPI server. Both point at the same
SQLite database (``data/state/jobs.db``), so the API server can enqueue jobs
and the worker can process them.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import JOB_STORE, process_conversion

log = logging.getLogger("figma_converter.worker")


async def _process_job(job_id: str) -> None:
    """Load the job args from JobStore and run process_conversion."""
    record = JOB_STORE.get(job_id)
    if not record:
        log.error("Job %s not found", job_id)
        return
    # Args were stored in result by start_conversion
    result = record.get("result") or {}
    if not isinstance(result, dict):
        log.error("Job %s result is not a dict", job_id)
        return
    figma_url = result.get("figma_url") or ""
    pat_token = result.get("pat_token")
    target_framework = result.get("target_framework") or "react"
    include_components = result.get("include_components", True)
    style_engine = result.get("style_engine")
    component_library = result.get("component_library")
    if not figma_url:
        log.error("Job %s has no figma_url in result", job_id)
        return
    await process_conversion(
        job_id=job_id,
        figma_url=figma_url,
        pat_token=pat_token,
        target_framework=target_framework,
        include_components=include_components,
        style_engine=style_engine,
        component_library=component_library,
    )


async def worker_loop(interval: float) -> None:
    """Poll for queued jobs and process them sequentially."""
    log.info("Worker started (poll interval: %ss)", interval)
    while True:
        job_id = JOB_STORE.claim_queued(f"worker-{os.getpid()}")
        if job_id:
            log.info("Claimed job %s", job_id)
            try:
                await _process_job(job_id)
            except Exception:  # noqa: BLE001
                log.exception("Job %s failed unexpectedly", job_id)
        await asyncio.sleep(interval)


async def worker_once() -> None:
    """Claim one queued job, process it, and exit."""
    job_id = JOB_STORE.claim_queued(f"worker-{os.getpid()}")
    if not job_id:
        log.info("No queued jobs found")
        return
    log.info("Claimed job %s (once mode)", job_id)
    try:
        await _process_job(job_id)
    except Exception:  # noqa: BLE001
        log.exception("Job %s failed", job_id)


async def _concurrent_worker(sem: asyncio.Semaphore, interval: float) -> None:
    while True:
        job_id = JOB_STORE.claim_queued(f"worker-{os.getpid()}")
        if job_id:
            async with sem:
                log.info("Claimed job %s", job_id)
                try:
                    await _process_job(job_id)
                except Exception:  # noqa: BLE001
                    log.exception("Job %s failed unexpectedly", job_id)
        await asyncio.sleep(interval)


async def worker_pool(concurrency: int, interval: float) -> None:
    """Run N concurrent worker loops."""
    sem = asyncio.Semaphore(concurrency)
    log.info("Worker pool starting (%s concurrent)", concurrency)
    tasks = [_concurrent_worker(sem, interval) for _ in range(concurrency)]
    await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="FigmaConverter background worker")
    parser.add_argument("--concurrency", type=int, default=1, help="Worker count")
    parser.add_argument("--once", action="store_true", help="Process one job and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    interval = float(os.getenv("JOB_POLL_INTERVAL_SECONDS", "2"))

    if args.once:
        asyncio.run(worker_once())
    elif args.concurrency > 1:
        asyncio.run(worker_pool(args.concurrency, interval))
    else:
        asyncio.run(worker_loop(interval))


if __name__ == "__main__":
    main()
