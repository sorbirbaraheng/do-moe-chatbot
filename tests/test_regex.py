
import sys
import os
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mock dependencies to avoid import errors
class MockQdrant:
    pass
class MockLLM:
    pass

from backend.chatbot.llm_agent import LLMAgent

# Initialize
agent = LLMAgent(MockQdrant(), MockLLM())

# Test Cases
test_cases = [
    ("ราชประชานุเคราะห์ 40 มีนักเรียนกี่คน", "ราชประชานุเคราะห์ 40", None),
    ("ราชประชานุเคราะห์ 40 ม.2 มีกี่คน", "ราชประชานุเคราะห์ 40", "ม.2"),
    ("โรงเรียนเตรียมอุดมศึกษา", "เตรียมอุดมศึกษา", None),
    ("จำนวนนักเรียนใน รร.สวนกุหลาบวิทยาลัย ชั้น ม.6", "สวนกุหลาบวิทยาลัย", "ม.6"),
    ("ปวช.1 เทคนิคเชียงใหม่", "เทคนิคเชียงใหม่", "ปวช.1"),
]

print("🔍 Starting Regex Verification...\n")
failed = False

for query, expected_school, expected_grade in test_cases:
    school = agent._extract_school_name(query)
    grade = agent._extract_grade(query)
    
    print(f"Query: '{query}'")
    
    # Check School
    if school == expected_school:
        print(f"  ✅ School: '{school}'")
    else:
        print(f"  ❌ School: Expected '{expected_school}', Got '{school}'")
        failed = True
        
    # Check Grade
    if grade == expected_grade:
        print(f"  ✅ Grade: '{grade}'")
    else:
        print(f"  ❌ Grade: Expected '{expected_grade}', Got '{grade}'")
        failed = True
    print("-" * 30)

if not failed:
    print("\n🎉 ALL TESTS PASSED!")
    sys.exit(0)
else:
    print("\n💥 SOME TESTS FAILED")
    sys.exit(1)
