import sys
import os
from qdrant_client import QdrantClient

# Connect to Qdrant
client = QdrantClient(host="203.159.242.144", port=6333)

def check_grades():
    print("Fetching unique grades from edu_students_v5...")
    
    # Scroll through points to collect grades
    response = client.scroll(
        collection_name="edu_students_v5",
        limit=500,
        with_payload=True,
        with_vectors=False
    )
    
    grades = set()
    count = 0
    if response and response[0]:
        print(f"First record metadata: {response[0][0].payload.get('metadata', {})}")
        for point in response[0]:
            meta = point.payload.get('metadata', {})
            if 'grade' in meta:
                grades.add(meta['grade'])
            elif 'grade_label' in meta:
                 grades.add(meta['grade_label'])
            elif 'std_grade_name' in meta:
                 grades.add(meta['std_grade_name'])
            
            # Also check flat payload just in case mix
            if 'grade' in point.payload:
                grades.add(point.payload['grade'])
            
            count += 1
            
    print(f"Scanned {count} records.")
    print("Unique Grades found:")
    for g in sorted(grades):
        print(f"- '{g}'")

if __name__ == "__main__":
    check_grades()
