#!/usr/bin/env python3
"""
Rate-safe live smoke tester for /api/chat.

Purpose:
- Validate real end-to-end replies without flooding model providers.
- Keep request rate low by default to avoid 429/rate-limit issues.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error, request


@dataclass
class CaseResult:
    case_id: str
    status: int
    ok: bool
    latency_ms: int
    reason: str
    response_preview: str


def _load_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("cases file must be a JSON array")
    return data


def _post_json(url: str, payload: Dict[str, Any], timeout_s: float) -> Tuple[int, Dict[str, str], str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.getcode(), headers, raw
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        headers = {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
        return e.code, headers, raw
    except error.URLError as e:
        return 599, {}, f"URLError: {e}"
    except TimeoutError as e:
        return 598, {}, f"TimeoutError: {e}"
    except Exception as e:
        return 597, {}, f"RequestError: {e}"


def _eval_case(case: Dict[str, Any], response_text: str) -> Tuple[bool, str]:
    expect_any = case.get("expect_any", []) or []
    forbid_any = case.get("forbid_any", []) or []

    if expect_any and not any(token in response_text for token in expect_any):
        return False, f"missing expected token(s): {expect_any}"
    if forbid_any and any(token in response_text for token in forbid_any):
        return False, f"found forbidden token(s): {forbid_any}"
    if not response_text.strip():
        return False, "empty response"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run rate-safe live smoke tests for /api/chat")
    parser.add_argument(
        "--base-url",
        default="http://localhost:5001",
        help="Backend base URL (default: http://localhost:5001)",
    )
    parser.add_argument(
        "--cases",
        default="backend/evals/live_smoke_cases.json",
        help="Path to smoke test cases JSON",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=8.0,
        help="Delay in seconds between requests (default: 8.0)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=75.0,
        help="Per-request timeout in seconds (default: 75)",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=10,
        help="Max number of cases to run (default: 10)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="Retries per case on 429/5xx (default: 1)",
    )
    parser.add_argument(
        "--stop-on-429",
        action="store_true",
        help="Stop immediately when receiving HTTP 429",
    )
    parser.add_argument(
        "--category",
        default="school",
        help="Category to send in payload (default: school)",
    )
    args = parser.parse_args()

    cases_path = Path(args.cases).resolve()
    cases = _load_cases(cases_path)
    cases = cases[: max(1, args.max_cases)]

    endpoint = args.base_url.rstrip("/") + "/api/chat"
    run_id = uuid.uuid4().hex[:8]
    session_alias_map: Dict[str, str] = {}

    print(f"Running {len(cases)} live smoke case(s)")
    print(f"Endpoint : {endpoint}")
    print(f"Interval : {args.interval:.1f}s between requests")
    print(f"Timeout  : {args.timeout:.1f}s\n")

    results: List[CaseResult] = []

    for idx, case in enumerate(cases, start=1):
        case_id = case.get("id", f"case-{idx}")
        msg = case.get("message", "")
        alias = case.get("session", f"isolated-{idx}")
        if alias not in session_alias_map:
            session_alias_map[alias] = f"smoke-{run_id}-{alias}"
        session_id = session_alias_map[alias]

        payload = {
            "message": msg,
            "history": [],
            "session_id": session_id,
            "category": args.category,
        }

        attempt = 0
        status = 0
        headers: Dict[str, str] = {}
        body = ""
        t0 = time.time()
        last_reason = ""

        while attempt <= args.retries:
            attempt += 1
            status, headers, body = _post_json(endpoint, payload, timeout_s=args.timeout)
            if status == 429:
                retry_after = headers.get("retry-after")
                wait_s = float(retry_after) if retry_after and retry_after.isdigit() else max(10.0, args.interval)
                last_reason = f"429 rate-limited (retry in {wait_s:.1f}s)"
                if args.stop_on_429:
                    break
                if attempt <= args.retries:
                    time.sleep(wait_s)
                    continue
            if status in [597, 598, 599] and attempt <= args.retries:
                last_reason = f"transport error {status} (retrying)"
                time.sleep(max(5.0, args.interval))
                continue
            if status >= 500 and attempt <= args.retries:
                last_reason = f"{status} server error (retrying)"
                time.sleep(max(5.0, args.interval))
                continue
            break

        latency_ms = int((time.time() - t0) * 1000)

        response_text = ""
        parse_reason = ""
        try:
            parsed = json.loads(body) if body else {}
            response_text = (parsed or {}).get("response", "")
            if status == 200 and not response_text:
                parse_reason = "response field missing/empty"
        except Exception:
            parse_reason = "non-json response"

        ok = status == 200
        reason = last_reason
        if ok:
            eval_ok, eval_reason = _eval_case(case, response_text)
            ok = eval_ok
            if eval_reason:
                reason = eval_reason
        elif not reason:
            reason = parse_reason or f"http {status}"

        preview = (response_text or body or "").strip().replace("\n", " ")
        preview = preview[:120] + ("..." if len(preview) > 120 else "")

        results.append(
            CaseResult(
                case_id=case_id,
                status=status,
                ok=ok,
                latency_ms=latency_ms,
                reason=reason,
                response_preview=preview,
            )
        )

        status_text = "PASS" if ok else "FAIL"
        print(f"[{idx:02d}/{len(cases):02d}] {status_text} {case_id}  ({latency_ms}ms, HTTP {status})")
        if reason:
            print(f"  reason : {reason}")
        if preview:
            print(f"  reply  : {preview}")

        if status == 429 and args.stop_on_429:
            print("\nStopped early due to HTTP 429 (stop-on-429 enabled).")
            break

        if idx < len(cases):
            time.sleep(max(0.0, args.interval))

    total = len(results)
    passed = sum(1 for r in results if r.ok)
    failed = total - passed
    avg_latency = int(sum(r.latency_ms for r in results) / total) if total else 0

    print("\n=== Summary ===")
    print(f"Total      : {total}")
    print(f"Passed     : {passed}")
    print(f"Failed     : {failed}")
    print(f"Avg latency: {avg_latency} ms")
    score = (passed / total * 100.0) if total else 0.0
    print(f"Score      : {score:.1f}%")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
