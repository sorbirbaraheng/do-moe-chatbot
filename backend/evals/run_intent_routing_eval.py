#!/usr/bin/env python3
"""Regression evaluator for intent/routing/context continuity guards.

This suite is deterministic (no LLM/Qdrant calls). It validates:
- route guard parameter enrichment
- active-query follow-up handling
- district extraction edge cases (e.g., avoid placeholder words like "ไหน")
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.chatbot.llm_agent import LLMAgent  # noqa: E402


def _load_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("cases file must be a JSON array")
    return data


def _subset_match(actual: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, str]:
    for key, expected_value in expected.items():
        if key not in actual:
            return False, f"missing key '{key}'"
        actual_value = actual[key]
        if isinstance(expected_value, dict):
            if not isinstance(actual_value, dict):
                return False, f"key '{key}' expected dict but got {type(actual_value).__name__}"
            ok, msg = _subset_match(actual_value, expected_value)
            if not ok:
                return False, f"{key}.{msg}"
        else:
            if actual_value != expected_value:
                return False, f"key '{key}' expected {expected_value!r} but got {actual_value!r}"
    return True, ""


def _apply_forbid_rules(actual: Dict[str, Any], forbid: Dict[str, Any]) -> Tuple[bool, str]:
    if not forbid:
        return True, ""

    forbid_params = forbid.get("params")
    if isinstance(forbid_params, dict):
        actual_params = actual.get("params", {}) if isinstance(actual, dict) else {}
        for key, value in forbid_params.items():
            if actual_params.get(key) == value:
                return False, f"forbidden params.{key}={value!r}"

    forbid_param_keys = forbid.get("params_keys")
    if isinstance(forbid_param_keys, list):
        actual_params = actual.get("params", {}) if isinstance(actual, dict) else {}
        for key in forbid_param_keys:
            if key in actual_params:
                return False, f"forbidden params key present: {key}"

    return True, ""


def _run_case(agent: LLMAgent, case: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    case_id = case.get("id", "unknown")
    kind = case.get("kind")
    question = case.get("question", "")
    expect = case.get("expect", {})
    forbid = case.get("forbid", {})

    if kind == "route_guard":
        tool = case.get("tool")
        params = copy.deepcopy(case.get("params", {}))
        out_tool, out_params = agent._route_guard(question, tool, params)
        actual = {"tool": out_tool, "params": out_params}

    elif kind == "followup_active_query":
        context = copy.deepcopy(case.get("context", {}))
        followup = agent._try_followup_from_active_query(question, context)
        if expect.get("tool") is None:
            if followup is not None:
                return False, "expected no follow-up tool but got one", {"tool_calls": followup}
            return True, "", {"tool": None}

        if not followup or not isinstance(followup, list):
            return False, "expected follow-up tool but got none", {"tool_calls": followup}

        first = followup[0] if followup else {}
        actual = {"tool": first.get("name"), "params": first.get("params", {})}

    elif kind == "extract_district":
        district = agent._extract_district(question)
        actual = {"district": district}

    else:
        return False, f"unsupported case kind '{kind}'", {}

    ok, msg = _subset_match(actual, expect)
    if not ok:
        return False, f"expectation failed: {msg}", actual

    ok_forbid, forbid_msg = _apply_forbid_rules(actual, forbid)
    if not ok_forbid:
        return False, forbid_msg, actual

    return True, "", actual


def main() -> int:
    parser = argparse.ArgumentParser(description="Run intent/routing/context regression eval")
    parser.add_argument(
        "--cases",
        default=str(Path(__file__).with_name("intent_routing_cases.json")),
        help="Path to cases JSON file",
    )
    parser.add_argument("--verbose", action="store_true", help="Print pass details")
    args = parser.parse_args()

    cases_path = Path(args.cases).resolve()
    cases = _load_cases(cases_path)

    agent = LLMAgent(qdrant_client=None, llm=None)

    passed = 0
    failed = 0

    print(f"Running {len(cases)} regression cases from: {cases_path}")
    for case in cases:
        case_id = case.get("id", "unknown")
        ok, message, actual = _run_case(agent, case)
        if ok:
            passed += 1
            if args.verbose:
                print(f"[PASS] {case_id} -> {actual}")
        else:
            failed += 1
            print(f"[FAIL] {case_id}: {message}")
            print(f"       actual: {actual}")

    print("\n=== Summary ===")
    print(f"Total : {len(cases)}")
    print(f"Pass  : {passed}")
    print(f"Fail  : {failed}")
    score = (passed / len(cases) * 100.0) if cases else 0.0
    print(f"Score : {score:.1f}%")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
