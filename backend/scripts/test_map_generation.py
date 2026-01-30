
import sys
import os
import json
import logging
from unittest.mock import MagicMock

# Add backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mock dependencies before importing LLMAgent
sys.modules['qdrant_client'] = MagicMock()
sys.modules['qdrant_client.models'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()

from chatbot.llm_agent import LLMAgent

# Mock logger
logging.basicConfig(level=logging.INFO)

def test_map_generation():
    print("🧪 Testing Map Generation Logic...")
    
    # Mock LLMAgent instance
    mock_llm = MagicMock()
    mock_qdrant = MagicMock()
    agent = LLMAgent(qdrant_client=mock_qdrant, llm=mock_llm)
    
    # Test 1: Single School Map Generation
    print("\n[Test 1] Single School Map")
    schools_single = [{
        "name": "School A",
        "lat": 13.1,
        "lon": 100.1,
        "province": "Bangkok",
        "district": "Phaya Thai"
    }]
    
    json_single = agent._generate_map_json(schools_single)
    data_single = json.loads(json_single)
    
    print(f"Result: {json_single}")
    assert data_single["latitude"] == 13.1
    assert data_single["longitude"] == 100.1
    assert data_single["schoolName"] == "School A"
    assert "markers" not in data_single or len(data_single.get("markers", [])) == 0
    print("✅ Single School Map JSON is correct.")
    
    # Test 2: Multiple Schools Map Generation
    print("\n[Test 2] Multiple Schools Map (Ambiguous)")
    schools_multi = [
        {"name": "School A", "lat": 13.1, "lon": 100.1},
        {"name": "School B", "lat": 13.2, "lon": 100.2}
    ]
    
    json_multi = agent._generate_map_json(schools_multi)
    data_multi = json.loads(json_multi)
    
    print(f"Result: {json_multi}")
    assert data_multi["latitude"] == 13.1  # Primary center
    assert "markers" in data_multi
    assert len(data_multi["markers"]) == 2
    assert data_multi["markers"][1]["title"] == "School B"
    print("✅ Multiple Schools Map JSON is correct.")
    
    # Test 3: Integration with _format_fallback_response
    print("\n[Test 3] Ambiguous Fallback Response Integration")
    results = [{
        "ambiguous": True,
        "choices": [
            {"school_name": "Satrinon", "province": "Nonthaburi", "lat": 13.8, "lon": 100.5},
            {"school_name": "Satriwit", "province": "Bangkok", "lat": 13.7, "lon": 100.4},
            {"school_name": "NoCoords", "province": "Unknown"} # Should be skipped
        ],
        "query": {"school_name": "Satri"}
    }]
    
    response_text = agent._format_fallback_response(results)
    print(f"Response Text Snippet: {response_text[-200:]}")
    
    assert "<map>" in response_text
    assert "Satrinon" in response_text
    assert "Satriwit" in response_text
    
    # Extract map json from tag
    import re
    match = re.search(r'<map>(.*?)</map>', response_text)
    if match:
        map_content = json.loads(match.group(1))
        assert len(map_content["markers"]) == 2
        print("✅ Ambiguous response contains correct <map> with markers.")
    else:
        print("❌ Map tag not found in response.")
        raise AssertionError("Map tag missing")

if __name__ == "__main__":
    try:
        test_map_generation()
        print("\n🎉 ALL TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
