"""Submit a non-sensitive fixture repeatedly and report completion throughput/latency."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import mimetypes
import time
import urllib.request
from pathlib import Path


def submit(base_url: str, fixture: Path) -> str:
    boundary = f"IESBENCH{time.time_ns()}"
    content_type = mimetypes.guess_type(fixture.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{fixture.name}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + fixture.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(f"{base_url}/api/v1/invoices", data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["jobs"][0]["id"]


def wait_for(base_url: str, job_id: str, timeout: float) -> float:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout:
        with urllib.request.urlopen(f"{base_url}/api/v1/invoices/{job_id}", timeout=10) as response:
            job = json.load(response)
        if job["status"] not in {"QUEUED", "PREPROCESSING", "OCR_RUNNING", "MAPPING", "VALIDATING"}:
            return time.perf_counter() - started
        time.sleep(0.2)
    raise TimeoutError(job_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        jobs = list(pool.map(lambda _: submit(args.base_url, args.fixture), range(args.count)))
        latencies = list(pool.map(lambda job: wait_for(args.base_url, job, args.timeout), jobs))
    elapsed = time.perf_counter() - started
    ordered = sorted(latencies)
    percentile = lambda q: ordered[min(round((len(ordered) - 1) * q), len(ordered) - 1)]
    print(json.dumps({"count": args.count, "elapsed_seconds": elapsed,
                      "invoices_per_hour": args.count / elapsed * 3600,
                      "p50_seconds": percentile(0.50), "p95_seconds": percentile(0.95),
                      "p99_seconds": percentile(0.99)}, indent=2))


if __name__ == "__main__":
    main()
