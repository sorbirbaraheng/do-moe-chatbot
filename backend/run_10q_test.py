"""
10-Question Chatbot API Test Script
Uses /api/chat (non-streaming) endpoint for reliable testing.
"""
import requests
import json
import time
import sys

BASE_URL = "http://localhost:5001"
DELAY_BETWEEN_QUESTIONS = 8  # seconds between questions to avoid rate limits

# Define questions with session grouping for follow-ups
QUESTIONS = [
    {"q": "ในจังหวัดนครศรีธรรมราช อำเภอไหนมีโรงเรียนมากที่สุด 3 อันดับ",     "session": "test_s1", "expect": "ranking data"},
    {"q": "มีโรงเรียนในอำเภอเมืองกาฬสินธุ์ที่นักเรียนน้อยกว่า 120 คนไหม",     "session": "test_s2", "expect": "school list or count"},
    {"q": "แล้วถ้ามากกว่า 800 คนล่ะ",                                          "session": "test_s2", "expect": "follow-up from Q2"},
    {"q": "จังหวัดน่านมีครูข้าราชการกี่คน",                                     "session": "test_s3", "expect": "teacher count"},
    {"q": "แล้วลูกจ้างชั่วคราวกี่คน",                                           "session": "test_s3", "expect": "follow-up from Q4"},
    {"q": "จังหวัดสตูลมีโรงเรียนในระบบกี่แห่ง",                                 "session": "test_s4", "expect": "school count"},
    {"q": "นอกระบบล่ะ",                                                         "session": "test_s4", "expect": "follow-up from Q6"},
    {"q": "ปี 2567 กับ 2568 จังหวัดพิษณุโลก นักเรียนชั้น ม.1 ต่างกันกี่คน",     "session": "test_s5", "expect": "year comparison"},
    {"q": "เทียบจังหวัดราชบุรีกับเพชรบุรี ใครมีอัตราส่วนนักเรียนต่อครูสูงกว่า",  "session": "test_s6", "expect": "ratio comparison"},
    {"q": "อยากรู้ว่าโรงเรียนไหนดีสุด",                                         "session": "test_s7", "expect": "ask-back / clarification"},
]

# Track conversation history per session
session_histories: dict = {}


def send_question(question: str, session_id: str, history: list) -> str:
    """Send a question to the non-streaming chat API."""
    payload = {
        "message": question,
        "session_id": session_id,
        "category": "general",
        "history": history
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=120,
            headers={"Content-Type": "application/json"}
        )

        if resp.status_code != 200:
            return f"[ERROR] HTTP {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        return data.get("response", data.get("text", json.dumps(data, ensure_ascii=False)[:500]))

    except requests.exceptions.Timeout:
        return "[ERROR] Request timed out after 120s"
    except requests.exceptions.ConnectionError:
        return "[ERROR] Cannot connect to server"
    except Exception as e:
        return f"[ERROR] {str(e)}"


def main():
    print("=" * 80)
    print("🧪 DO-MOE Chatbot API Test — 10 Questions")
    print(f"🌐 Target: {BASE_URL}/api/chat")
    print(f"⏱  Delay between questions: {DELAY_BETWEEN_QUESTIONS}s")
    print("=" * 80)

    # Quick health check
    try:
        health = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"✅ Server health: {health.json()}")
    except Exception as e:
        print(f"❌ Server not reachable: {e}")
        sys.exit(1)

    results = []

    for i, q_data in enumerate(QUESTIONS):
        q_num = i + 1
        question = q_data["q"]
        session_id = q_data["session"]
        expected = q_data["expect"]

        # Get or create history for this session
        if session_id not in session_histories:
            session_histories[session_id] = []

        history = session_histories[session_id]

        print(f"\n{'─' * 80}")
        print(f"📝 Q{q_num}: {question}")
        print(f"   Session: {session_id} | Expected: {expected}")
        print(f"   Sending...")

        start_time = time.time()
        answer = send_question(question, session_id, history)
        elapsed = time.time() - start_time

        # Update history for this session
        session_histories[session_id].append({"role": "user", "content": question})
        session_histories[session_id].append({"role": "assistant", "content": answer[:500]})

        # Determine pass/fail
        is_error = answer.startswith("[ERROR]") or answer == "[EMPTY RESPONSE]"
        status = "❌ FAIL" if is_error else "✅ OK"

        # Truncate for display
        display_answer = answer[:500] + "..." if len(answer) > 500 else answer

        print(f"   {status} ({elapsed:.1f}s)")
        print(f"   📬 Response:\n{display_answer}")

        results.append({
            "q_num": q_num,
            "question": question,
            "session": session_id,
            "expected": expected,
            "status": "PASS" if not is_error else "FAIL",
            "time_s": round(elapsed, 1),
            "answer_preview": answer[:500],
            "answer_full": answer
        })

        # Delay before next question (except last)
        if i < len(QUESTIONS) - 1:
            print(f"   ⏳ Waiting {DELAY_BETWEEN_QUESTIONS}s...")
            time.sleep(DELAY_BETWEEN_QUESTIONS)

    # Summary
    print(f"\n{'=' * 80}")
    print("📊 SUMMARY")
    print(f"{'=' * 80}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"✅ Passed: {passed}/10")
    print(f"❌ Failed: {failed}/10")
    print()

    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} Q{r['q_num']}: {r['question'][:50]}... ({r['time_s']}s)")

    # Save full results to JSON
    output_path = "test_results_10q.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Full results saved to: {output_path}")


if __name__ == "__main__":
    main()
