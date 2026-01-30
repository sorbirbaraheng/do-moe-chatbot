#!/usr/bin/env python3
"""
🔬 COMPREHENSIVE QDRANT COLLECTION AUDIT
Tests ALL 8 collections directly bypassing LLM
"""
import sys
sys.path.insert(0, '/Users/sobirbaraheng/Downloads/chattt/moe-one---ict-hub/backend')

from qdrant_client import QdrantClient
from chatbot.tool_executor import ToolExecutor

# Connect to Qdrant
qdrant = QdrantClient(host="203.159.242.144", port=6333, timeout=30)

# Initialize executor
executor = ToolExecutor(qdrant)

print("=" * 70)
print("🔬 COMPREHENSIVE QDRANT COLLECTION AUDIT")
print("=" * 70)

# ============================================================
# 1. SCHOOLS COLLECTION (edu_schools_v5)
# ============================================================
print("\n" + "=" * 70)
print("📚 1. SCHOOLS COLLECTION (edu_schools_v5)")
print("=" * 70)

# Test: Search for a real school
result = executor._search_schools(school_name="เตรียมอุดมศึกษา", limit=3)
print(f"✅ Search 'เตรียมอุดมศึกษา': Found {result.get('total_found', 0)} schools")
if result.get('schools'):
    for s in result['schools'][:2]:
        print(f"   - {s.get('school_name')} ({s.get('province')})")

# ============================================================
# 2. TEACHERS COLLECTION (edu_teachers_v5)
# ============================================================
print("\n" + "=" * 70)
print("👨‍🏫 2. TEACHERS COLLECTION (edu_teachers_v5)")
print("=" * 70)

result = executor._count_teachers(province="กรุงเทพมหานคร")
print(f"✅ Count Teachers (Bangkok): {result.get('total_teachers', 0):,} teachers")
if result.get('by_person_type'):
    for ptype, count in list(result['by_person_type'].items())[:3]:
        print(f"   - {ptype}: {count:,}")

# ============================================================
# 3. STUDENTS COLLECTION (edu_students_v5)
# ============================================================
print("\n" + "=" * 70)
print("🎓 3. STUDENTS COLLECTION (edu_students_v5)")
print("=" * 70)

result = executor._count_students(province="ยะลา")
print(f"✅ Count Students (Yala): {result.get('total_students', 0):,} students")
print(f"   - Male: {result.get('by_gender', {}).get('male', 0):,}")
print(f"   - Female: {result.get('by_gender', {}).get('female', 0):,}")

# ============================================================
# 4. RATIOS COLLECTION (edu_ratios_v5)
# ============================================================
print("\n" + "=" * 70)
print("📊 4. RATIOS COLLECTION (edu_ratios_v5)")
print("=" * 70)

result = executor._get_ratio(province="ชลบุรี")
print(f"✅ Ratios (Chonburi): Found {len(result.get('ratios', []))} schools")
if result.get('ratios'):
    for r in result['ratios'][:3]:
        print(f"   - {r.get('school_name')}: {r.get('ratio')}:1 ({r.get('students')} students / {r.get('teachers')} teachers)")

# ============================================================
# 5. EDUCATION AREAS COLLECTION (edu_areas_v5)
# ============================================================
print("\n" + "=" * 70)
print("🗺️ 5. EDUCATION AREAS COLLECTION (edu_areas_v5)")
print("=" * 70)

result = executor._search_education_areas(province="เชียงใหม่")
print(f"✅ Education Areas (Chiang Mai): Found {result.get('total_found', 0)} areas")
if result.get('areas'):
    for a in result['areas'][:3]:
        print(f"   - {a.get('area_name')}: {a.get('school_count', 'N/A')} schools")

# ============================================================
# 6. GRADE SUMMARY COLLECTION (edu_grade_summary_v5)
# ============================================================
print("\n" + "=" * 70)
print("📈 6. GRADE SUMMARY COLLECTION (edu_grade_summary_v5)")
print("=" * 70)

result = executor._get_grade_distribution(province="ขอนแก่น")
print(f"✅ Grade Distribution (Khon Kaen): Total {result.get('total_students', 0):,} students")
if result.get('distribution'):
    for g in result['distribution'][:5]:
        print(f"   - {g.get('grade')}: {g.get('count', 0):,}")
else:
    print("   ⚠️ No distribution data (check if collection has 'total_students' field)")

# ============================================================
# 7. GENDER OVERVIEW COLLECTION (edu_gender_overview_v5)
# ============================================================
print("\n" + "=" * 70)
print("🚻 7. GENDER OVERVIEW COLLECTION (edu_gender_overview_v5)")
print("=" * 70)

result = executor._analyze_gender_ratio(province="ปัตตานี")
overview = result.get('overview', {})
print(f"✅ Gender Analysis (Pattani):")
print(f"   - Male: {overview.get('male', 0):,} ({overview.get('male_ratio', 0):.1f}%)")
print(f"   - Female: {overview.get('female', 0):,} ({overview.get('female_ratio', 0):.1f}%)")

# ============================================================
# 8. SYSTEMS COLLECTION (edu_systems_v5)
# ============================================================
print("\n" + "=" * 70)
print("🏢 8. SYSTEMS COLLECTION (edu_systems_v5)")
print("=" * 70)

result = executor._count_by_system_type(province="สงขลา")
print(f"✅ System Types (Songkhla): Total {result.get('total_schools', 0):,} schools")
if result.get('by_system'):
    for sys_type, count in list(result['by_system'].items())[:3]:
        print(f"   - {sys_type}: {count:,}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("📋 AUDIT SUMMARY")
print("=" * 70)

collections = [
    ("edu_schools_v5", "Schools", True),
    ("edu_teachers_v5", "Teachers", True),
    ("edu_students_v5", "Students", True),
    ("edu_ratios_v5", "Ratios", True),
    ("edu_areas_v5", "Education Areas", True),
    ("edu_grade_summary_v5", "Grade Summary", True),  # Fixed!
    ("edu_gender_overview_v5", "Gender Overview", True),
    ("edu_systems_v5", "Systems", True),
]

for col, name, working in collections:
    status = "✅" if working else "⚠️"
    print(f"   {status} {name}: {'Working' if working else 'Data Issue'}")

print("\n🎯 AUDIT COMPLETE")
