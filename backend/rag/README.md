# 🏫 RAG Ingestion Module

โมดูลสำหรับ ingest ข้อมูลการศึกษาเข้า Vector Database (Qdrant)

## 📁 โครงสร้างโฟลเดอร์

```
rag/
├── __init__.py          # Module exports
├── ingest_education.py  # Main ingestion script
├── data/                # ใส่ไฟล์ Excel ที่นี่
│   ├── Fact_Bangkok.xlsx
│   ├── Fact_ChiangMai.xlsx
│   └── ...
└── README.md            # ไฟล์นี้
```

## 🚀 วิธีใช้งาน

### 1. ติดตั้ง Dependencies
```bash
pip install google-generativeai pandas tqdm qdrant-client python-dotenv sentence-transformers
```

### 2. วางไฟล์ Excel ใน `data/`
```bash
cp /path/to/your/Fact_Bangkok.xlsx data/
```

### 3. รัน Ingestion

```bash
# ใช้ Gemini (ฟรี! - แนะนำ)
python ingest_education.py --file data/Fact_Bangkok.xlsx

# ใช้ Local embedding (ฟรี offline)
python ingest_education.py --file data/Fact_Bangkok.xlsx --provider local

# หลายไฟล์
python ingest_education.py --file data/Fact_Bangkok.xlsx
python ingest_education.py --file data/Fact_ChiangMai.xlsx
python ingest_education.py --file data/Fact_Songkhla.xlsx

# ลบข้อมูลเดิมแล้ว ingest ใหม่
python ingest_education.py --file data/Fact_Bangkok.xlsx --recreate
```

## 📊 Embedding Providers

| Provider | Model | ราคา | หมายเหตุ |
|----------|-------|------|----------|
| **gemini** ⭐ | text-embedding-004 | ฟรี! | Default, 1,500 req/min |
| **local** | paraphrase-multilingual-mpnet-base-v2 | ฟรี | Offline, ช้ากว่า |
| **openai** | text-embedding-3-small | $0.02/1M tokens | แม่นยำสุด |

## 📋 รูปแบบไฟล์ Excel ที่รองรับ

### Sheet Names ที่รองรับ:
- **โรงเรียน**: `Fact_Bangkok`, `Fact_School`, `Schools`, `โรงเรียน`
- **นักเรียน**: `Fact_Student_Bangkok`, `Fact_Student`, `Students`, `นักเรียน`
- **สถิติโรงเรียน**: `Fact_School_Bangkok`, `Fact_School_Stats`, `SchoolStats`
- **ครู**: `Fact_Teacher_Bangkok`, `Fact_Teacher`, `Teachers`, `ครู`

### Columns ที่ใช้:
- `ProvinceNameTh` - ชื่อจังหวัด
- `DistrictNameTh` - ชื่อเขต/อำเภอ
- `SubDistrictNameTh` - ชื่อตำบล/แขวง
- `SchoolName` - ชื่อโรงเรียน
- `DepartmentNameTh` - สังกัด
- `Sum_Students`, `Sum_Teachers`, `Sum_Schools` - ตัวเลขสถิติ
- `Latitude`, `Longitude` - พิกัด GPS

## 🔧 Auto-detect Features

1. **Auto-detect Province from filename**:
   - `Fact_Bangkok.xlsx` → กรุงเทพมหานคร
   - `ChiangMai_Schools.xlsx` → เชียงใหม่

2. **Auto-detect Sheet names**:
   - หลายรูปแบบ (English/Thai)

## 📦 Collection ที่สร้าง

ข้อมูลทั้งหมดจะเก็บใน Collection: `thailand_education`

แต่ละ chunk มี metadata สำหรับ filter:
```python
{
    "type": "school_info" | "student_stats" | "teacher_stats" | "school_count",
    "province": "กรุงเทพมหานคร",
    "district": "พระนคร",
    "school_name": "วัดราชบพิธ",
    ...
}
```
