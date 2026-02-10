# Qdrant v5 Schema Map (DO‑MOE)

สรุปโครงสร้างข้อมูลจริงจาก Qdrant (เฉพาะ collection ลงท้ายด้วย `v5`) เพื่อใช้เป็น **Routing Map** ของคำถาม → Tool ให้ตอบได้ครบและแม่น

## 1) `edu_schools_v5`
**metadata fields:**  
`school_name, school_id, province, district, subdistrict, agency, area_name, total_students, total_teachers, lat, lon, contact_info`

**เหมาะกับคำถาม:**  
- รายละเอียดโรงเรียน (ที่อยู่/พิกัด/ครู/นักเรียน)  
- รายชื่อโรงเรียนในพื้นที่  
- ranking/ค้นหาโรงเรียนตามชื่อนอกเหนือจากระบบรายบุคคล  

**Tools:** `search_schools`, `list_schools`, `get_school_full_details`, `advanced_school_search`, `filter_schools`

---

## 2) `edu_students_v5`
**metadata fields:**  
`school_name, school_id, province, district, subdistrict, grade, gender, count, year`

**เหมาะกับคำถาม:**  
- จำนวนนักเรียน (รวม/เพศ/ระดับชั้น)  
- เปรียบเทียบจำนวนนักเรียนตามพื้นที่  

**Tools:** `count_students`, `get_grade_distribution`

---

## 3) `edu_teachers_v5`
**metadata fields:**  
`school_name, school_id, province, district, person_type, gender, count, year`

**เหมาะกับคำถาม:**  
- จำนวนครู/บุคลากร (รวม/แยกเพศ/ประเภท)  
- โครงสร้างครูในพื้นที่  

**Tools:** `count_teachers`, `analyze_teacher_distribution`

---

## 4) `edu_ratios_v5`
**metadata fields:**  
`school_name, school_id, province, district, total_students, total_teachers, ratio, year`

**เหมาะกับคำถาม:**  
- อัตราส่วนครูต่อนักเรียน  
- โรงเรียนที่ ratio สูง/ต่ำสุด  

**Tools:** `get_ratio`, `find_best_ratio_schools`

---

## 5) `edu_grade_summary_v5`
**metadata fields:**  
`name, province, grade, count, level, parent, year`

**เหมาะกับคำถาม:**  
- สรุปนักเรียนแยกตามระดับชั้นระดับพื้นที่  

**Tools:** `get_grade_distribution`

---

## 6) `edu_gender_overview_v5`
**metadata fields:**  
`name, province, gender, count, level, year`

**เหมาะกับคำถาม:**  
- สัดส่วนเพศนักเรียนในภาพรวมพื้นที่  

**Tools:** `analyze_gender_ratio`

---

## 7) `edu_systems_v5`
**metadata fields:**  
`name, province, system_type, count, level, year`

**เหมาะกับคำถาม:**  
- โรงเรียน “ในระบบ/นอกระบบ” ในพื้นที่  

**Tools:** `count_by_system_type`

---

## 8) `edu_areas_v5`
**metadata fields:**  
`area_name, provinces, districts_list, school_count, districts_count`

**เหมาะกับคำถาม:**  
- เขตพื้นที่การศึกษา สพป./สพม.  
- เขตนี้ครอบคลุมอำเภออะไรบ้าง  

**Tools:** `search_education_areas`, `get_education_area_info`

---

## Routing Rules (สรุป)
- ถาม **ครู + นักเรียน + จังหวัด** → `get_province_summary`
- ถาม **สัดส่วนเพศ** → `analyze_gender_ratio`
- ถาม **ในระบบ/นอกระบบ** → `count_by_system_type`
- ถาม **เขตพื้นที่ (สพป./สพม.)** → `search_education_areas` / `get_education_area_info`
- ถาม **ระดับชั้น** → `get_grade_distribution`

