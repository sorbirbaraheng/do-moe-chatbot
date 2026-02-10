#!/usr/bin/env python3
import argparse
import json
import sys
import time
from pathlib import Path

import requests


def load_questions(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Run routing QA against /api/debug/route")
    parser.add_argument("--base-url", default="http://localhost:5001", help="Backend base URL")
    parser.add_argument("--input", default="scripts/qa_questions_v5.json", help="Questions JSON path")
    parser.add_argument("--out", default="scripts/qa_results_v5.json", help="Output results path")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between requests (seconds)")
    args = parser.parse_args()

    questions = load_questions(Path(args.input))
    results = []
    ok = 0
    total = 0

    for idx, item in enumerate(questions, 1):
        q = item.get("question")
        expected = item.get("expected_tool")
        if not q:
            continue
        total += 1
        payload = {
            "message": q,
            "session_id": f"qa_{idx}",
            "category": "school"
        }
        try:
            r = requests.post(f"{args.base_url}/api/debug/route", json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            tool_calls = data.get("tool_calls", [])
            selected = None
            pending = None
            if tool_calls:
                selected = tool_calls[0].get("name")
                if selected == "__ask_back__":
                    pending_tool = tool_calls[0].get("params", {}).get("pending_tool")
                    if pending_tool:
                        pending = pending_tool.get("name")
            match = (selected == expected) or (pending == expected)
            if match:
                ok += 1
            results.append({
                "question": q,
                "expected_tool": expected,
                "selected_tool": selected,
                "pending_tool": pending,
                "match": match
            })
        except Exception as e:
            results.append({
                "question": q,
                "expected_tool": expected,
                "selected_tool": None,
                "pending_tool": None,
                "match": False,
                "error": str(e)
            })
        time.sleep(args.delay)

    out_path = Path(args.out)
    out_path.write_text(json.dumps({
        "summary": {
            "total": total,
            "matched": ok,
            "mismatch": total - ok
        },
        "results": results
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Done. Matched {ok}/{total}. Results -> {out_path}")


if __name__ == "__main__":
    main()

