"""Run an IES dataset through the API and persist privacy-controlled predictions."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ACTIVE_STATUSES = {"QUEUED", "PREPROCESSING", "OCR_RUNNING", "MAPPING", "VALIDATING"}


def _request(url: str, *, data: bytes | None = None, content_type: str | None = None) -> dict[str, Any]:
    headers: dict[str, str] = {"Accept": "application/json"}
    token = os.getenv("IES_BENCHMARK_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def submit(base_url: str, path: Path) -> str:
    boundary = f"IESBENCH{time.time_ns()}"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{path.name}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    payload = _request(
        f"{base_url}/api/v1/invoices",
        data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    return str(payload["jobs"][0]["id"])


def await_result(base_url: str, job_id: str, timeout_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout_seconds:
        payload = _request(f"{base_url}/api/v1/invoices/{job_id}")
        if str(payload.get("status", "")) not in ACTIVE_STATUSES:
            return payload
        time.sleep(0.2)
    raise TimeoutError(f"job {job_id} exceeded {timeout_seconds:.0f}s")


def _safe_document_path(dataset_root: Path, relative: str) -> Path:
    resolved = (dataset_root / relative).resolve()
    resolved.relative_to(dataset_root.resolve())
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def process_document(base_url: str, dataset_root: Path, entry: dict[str, Any], timeout: float) -> tuple[str, dict[str, Any]]:
    document_id = str(entry["id"])
    try:
        path = _safe_document_path(dataset_root, str(entry["path"]))
        job_id = submit(base_url, path)
        job = await_result(base_url, job_id, timeout)
        extraction = job.get("extraction") if isinstance(job.get("extraction"), dict) else {}
        prediction = dict(extraction)
        prediction["_meta"] = {
            "job_id": job_id,
            "status": job.get("status"),
            "latency_ms": job.get("latencyMs"),
            "engine": job.get("engine"),
            "confidence": job.get("confidence"),
            "quality": entry.get("quality"),
            "layout": entry.get("layout"),
        }
        return document_id, prediction
    except (OSError, KeyError, TimeoutError, urllib.error.URLError, ValueError) as error:
        return document_id, {
            "_meta": {
                "status": "FAILED",
                "quality": entry.get("quality"),
                "layout": entry.get("layout"),
                "error_type": type(error).__name__,
            }
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True, help="Path to dataset.json")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=300,
                        help="Seconds allowed per invoice; accuracy-first OCR/Qwen runs may take several minutes")
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")
    if args.predictions.exists() and any(args.predictions.iterdir()):
        parser.error(f"refusing to overwrite non-empty prediction directory: {args.predictions}")
    try:
        manifest = json.loads(args.dataset.read_text(encoding="utf-8"))
        documents = manifest["documents"]
        if not isinstance(documents, list) or not documents:
            raise ValueError("dataset manifest has no documents")
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    args.predictions.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    dataset_root = args.dataset.parent
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(process_document, args.base_url.rstrip("/"), dataset_root, item, args.timeout) for item in documents]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    for document_id, prediction in results:
        (args.predictions / f"{document_id}.json").write_text(
            json.dumps(prediction, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elapsed = time.perf_counter() - started
    completed = sum(1 for _, value in results if value.get("_meta", {}).get("status") not in {"FAILED", "REJECTED"})
    run = {
        "dataset": args.dataset.name,
        "submitted": len(documents),
        "completed": completed,
        "failed": len(documents) - completed,
        "concurrency": args.concurrency,
        "elapsed_seconds": round(elapsed, 6),
        "invoices_per_hour": round(completed / elapsed * 3600, 3) if elapsed else 0,
    }
    (args.predictions / "_run.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(run, indent=2))
    return 0 if completed == len(documents) else 2


if __name__ == "__main__":
    raise SystemExit(main())
