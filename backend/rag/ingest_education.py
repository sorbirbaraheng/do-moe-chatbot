#!/usr/bin/env python3
"""
🏫 Thailand Education Data RAG Ingestion Script
================================================
สร้าง Context-Rich Chunks และส่งเข้า Qdrant Vector Database

รองรับ Embedding Providers:
- OpenAI (text-embedding-3-small) - แม่นยำสุด แต่เสียเงิน
- Sentence Transformers - ฟรี!

การใช้งาน:
    python ingest_bangkok_education.py --file data/bangkok_education.xlsx
    python ingest_bangkok_education.py --folder data/ --provider openai
    python ingest_bangkok_education.py --file data.xlsx --collection thailand_education --recreate

ผู้เขียน: DO AI Team
วันที่: 2026-01-19
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)
from tqdm import tqdm
import hashlib
import logging
import glob
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# =====================================================================
# CONFIGURATION
# =====================================================================
QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
COLLECTION_NAME = 'thailand_education'
BATCH_SIZE = 100

# Embedding configs
EMBEDDING_CONFIGS = {
    'local': {
        'model': 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
        'vector_size': 768,
        'cost': 'ฟรี (offline)'
    },
    'gemini': {
        'model': 'text-embedding-004',
        'vector_size': 768,
        'cost': 'ฟรี (1,500 requests/min)'
    },
    'openai': {
        'model': 'text-embedding-3-small',
        'vector_size': 1536,
        'cost': '$0.02/1M tokens'
    }
}

# Province name mapping (from filename/folder) - ครบ 77 จังหวัด
PROVINCE_MAPPING = {
    # ภาคกลาง
    'bangkok': 'กรุงเทพมหานคร', 'กรุงเทพ': 'กรุงเทพมหานคร', 'กทม': 'กรุงเทพมหานคร',
    'nonthaburi': 'นนทบุรี', 'pathumthani': 'ปทุมธานี', 'ayutthaya': 'พระนครศรีอยุธยา',
    'angthong': 'อ่างทอง', 'lopburi': 'ลพบุรี', 'singburi': 'สิงห์บุรี', 'chainat': 'ชัยนาท',
    'saraburi': 'สระบุรี', 'nakhonnayok': 'นครนายก', 'prachinburi': 'ปราจีนบุรี',
    'chachoengsao': 'ฉะเชิงเทรา', 'samutprakan': 'สมุทรปราการ', 'samutsakhon': 'สมุทรสาคร',
    'samutsongkhram': 'สมุทรสงคราม', 'nakhonpathom': 'นครปฐม', 'suphanburi': 'สุพรรณบุรี',
    'kanchanaburi': 'กาญจนบุรี', 'ratchaburi': 'ราชบุรี', 'phetchaburi': 'เพชรบุรี',
    'prachuapkhirikhan': 'ประจวบคีรีขันธ์',
    # ภาคเหนือ
    'chiangmai': 'เชียงใหม่', 'chiang_mai': 'เชียงใหม่', 'chiangrai': 'เชียงราย',
    'lampang': 'ลำปาง', 'lamphun': 'ลำพูน', 'maehongson': 'แม่ฮ่องสอน',
    'nan': 'น่าน', 'phayao': 'พะเยา', 'phrae': 'แพร่', 'uttaradit': 'อุตรดิตถ์',
    'tak': 'ตาก', 'sukhothai': 'สุโขทัย', 'phitsanulok': 'พิษณุโลก',
    'phichit': 'พิจิตร', 'kamphaengphet': 'กำแพงเพชร', 'nakhonsawan': 'นครสวรรค์',
    'uthaithani': 'อุทัยธานี', 'phetchabun': 'เพชรบูรณ์',
    # ภาคตะวันออกเฉียงเหนือ
    'nakhonratchasima': 'นครราชสีมา', 'korat': 'นครราชสีมา',
    'khonkaen': 'ขอนแก่น', 'udonthani': 'อุดรธานี', 'nongkhai': 'หนองคาย',
    'loei': 'เลย', 'sakonnakhon': 'สกลนคร', 'nakhonphanom': 'นครพนม',
    'mukdahan': 'มุกดาหาร', 'kalasin': 'กาฬสินธุ์', 'roiet': 'ร้อยเอ็ด',
    'mahasarakham': 'มหาสารคาม', 'khonkaen': 'ขอนแก่น', 'chaiyaphum': 'ชัยภูมิ',
    'buriram': 'บุรีรัมย์', 'surin': 'สุรินทร์', 'sisaket': 'ศรีสะเกษ',
    'ubonratchathani': 'อุบลราชธานี', 'yasothon': 'ยโสธร', 'amnatcharoen': 'อำนาจเจริญ',
    'nongbualamphu': 'หนองบัวลำภู', 'buengkan': 'บึงกาฬ',
    # ภาคตะวันออก
    'chonburi': 'ชลบุรี', 'rayong': 'ระยอง', 'chanthaburi': 'จันทบุรี',
    'trat': 'ตราด', 'sakaeo': 'สระแก้ว',
    # ภาคใต้
    'chumphon': 'ชุมพร', 'ranong': 'ระนอง', 'suratthani': 'สุราษฎร์ธานี',
    'phangnga': 'พังงา', 'phuket': 'ภูเก็ต', 'krabi': 'กระบี่',
    'nakhonsithammarat': 'นครศรีธรรมราช', 'trang': 'ตรัง', 'phatthalung': 'พัทลุง',
    'songkhla': 'สงขลา', 'satun': 'สตูล', 'pattani': 'ปัตตานี',
    'yala': 'ยะลา', 'narathiwat': 'นราธิวาส',
}

# คำย่อ/Aliases สำหรับ Query Expansion
ALIASES = {
    # สังกัด
    'สพฐ': 'สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน',
    'สพฐ.': 'สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน',
    'obec': 'สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน',
    'สช': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
    'สช.': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
    'เอกชน': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
    'อปท': 'องค์กรปกครองส่วนท้องถิ่น',
    'อปท.': 'องค์กรปกครองส่วนท้องถิ่น', 
    'สอศ': 'สำนักงานคณะกรรมการการอาชีวศึกษา',
    'สอศ.': 'สำนักงานคณะกรรมการการอาชีวศึกษา',
    'อาชีวะ': 'สำนักงานคณะกรรมการการอาชีวศึกษา',
    'สกอ': 'สำนักงานคณะกรรมการการอุดมศึกษา',
    'กศน': 'สำนักงานส่งเสริมการศึกษานอกระบบและการศึกษาตามอัธยาศัย',
    'กศน.': 'สำนักงานส่งเสริมการศึกษานอกระบบและการศึกษาตามอัธยาศัย',
    # คำย่อทั่วไป
    'ร.ร.': 'โรงเรียน',
    'ร.ร': 'โรงเรียน',
    'รร': 'โรงเรียน',
    'นร': 'นักเรียน',
    'นร.': 'นักเรียน',
    'กทม': 'กรุงเทพมหานคร',
    'กทม.': 'กรุงเทพมหานคร',
    # ระดับชั้น
    'ป.1': 'ประถมศึกษาปีที่ 1', 'ป.2': 'ประถมศึกษาปีที่ 2',
    'ป.3': 'ประถมศึกษาปีที่ 3', 'ป.4': 'ประถมศึกษาปีที่ 4',
    'ป.5': 'ประถมศึกษาปีที่ 5', 'ป.6': 'ประถมศึกษาปีที่ 6',
    'ม.1': 'มัธยมศึกษาปีที่ 1', 'ม.2': 'มัธยมศึกษาปีที่ 2',
    'ม.3': 'มัธยมศึกษาปีที่ 3', 'ม.4': 'มัธยมศึกษาปีที่ 4',
    'ม.5': 'มัธยมศึกษาปีที่ 5', 'ม.6': 'มัธยมศึกษาปีที่ 6',
    'อ.1': 'อนุบาล 1', 'อ.2': 'อนุบาล 2', 'อ.3': 'อนุบาล 3',
}

# Sheet names mapping
SHEET_NAMES = {
    'schools': ['Fact_Bangkok', 'Fact_School', 'Schools', 'โรงเรียน', 'ข้อมูลโรงเรียน'],
    'students': ['Fact_Student_Bangkok', 'Fact_Student', 'Students', 'นักเรียน', 'ข้อมูลนักเรียน'],
    'school_stats': ['Fact_School_Bangkok', 'Fact_School_Stats', 'SchoolStats', 'สถิติโรงเรียน', 'จำนวนโรงเรียน'],
    'teachers': ['Fact_Teacher_Bangkok', 'Fact_Teacher', 'Teachers', 'ครู', 'ข้อมูลครู', 'บุคลากร'],
}


class ThailandEducationIngester:
    """
    คลาสสำหรับ ingest ข้อมูลการศึกษาประเทศไทยเข้า Qdrant
    รองรับหลาย Embedding Providers
    """
    
    def __init__(
        self, 
        qdrant_url: str = QDRANT_URL, 
        collection_name: str = COLLECTION_NAME,
        provider: str = 'local'  # 'local' or 'openai'
    ):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.provider = provider
        self.client = None
        self.model = None
        self.embed_config = EMBEDDING_CONFIGS[provider]
        
    def connect(self):
        """เชื่อมต่อ Qdrant และโหลด Embedding Model"""
        logger.info(f"🔗 กำลังเชื่อมต่อ Qdrant: {self.qdrant_url}")
        self.client = QdrantClient(url=self.qdrant_url, timeout=60)
        
        logger.info(f"🧠 กำลังโหลด Embedding ({self.provider}): {self.embed_config['model']}")
        logger.info(f"   💰 Cost: {self.embed_config['cost']}")
        
        if self.provider == 'local':
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.embed_config['model'])
        elif self.provider == 'gemini':
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            self.gemini_model = self.embed_config['model']
            logger.info("✅ Gemini API configured!")
        elif self.provider == 'openai':
            from openai import OpenAI
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        logger.info("✅ เชื่อมต่อสำเร็จ!")
        
    def create_collection(self, recreate: bool = False):
        """สร้าง Collection ใน Qdrant"""
        collections = [c.name for c in self.client.get_collections().collections]
        
        if self.collection_name in collections:
            if recreate:
                logger.warning(f"⚠️ ลบ Collection เดิม: {self.collection_name}")
                self.client.delete_collection(self.collection_name)
            else:
                logger.info(f"✅ Collection '{self.collection_name}' มีอยู่แล้ว")
                return
        
        logger.info(f"📦 สร้าง Collection: {self.collection_name}")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.embed_config['vector_size'],
                distance=Distance.COSINE
            )
        )
        logger.info("✅ สร้าง Collection สำเร็จ!")
    
    def expand_text(self, text: str) -> str:
        """
        Auto-expand คำย่อใน text
        เช่น "สพฐ" → "สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน (สพฐ)"
        """
        expanded = text
        for abbrev, full in ALIASES.items():
            if abbrev in expanded:
                # แทนที่คำย่อด้วย "คำเต็ม (คำย่อ)" เพื่อให้ค้นหาได้ทั้งสองแบบ
                expanded = expanded.replace(abbrev, f"{full} ({abbrev})")
        return expanded
    
    def expand_province(self, text: str) -> str:
        """
        Auto-expand ชื่อจังหวัดย่อ
        เช่น "กทม" → "กรุงเทพมหานคร"
        """
        expanded = text
        for abbrev, full in PROVINCE_MAPPING.items():
            if abbrev in expanded.lower():
                expanded = expanded.replace(abbrev, full)
        return expanded
    
    def embed_texts(self, texts: list) -> list:
        """แปลง texts เป็น vectors"""
        if self.provider == 'local':
            return self.model.encode(texts, show_progress_bar=False).tolist()
        elif self.provider == 'gemini':
            import google.generativeai as genai
            results = []
            for text in texts:
                result = genai.embed_content(
                    model=f"models/{self.gemini_model}",
                    content=text,
                    task_type="retrieval_document"
                )
                results.append(result['embedding'])
            return results
        elif self.provider == 'openai':
            response = self.openai_client.embeddings.create(
                model=self.embed_config['model'],
                input=texts
            )
            return [item.embedding for item in response.data]
    
    def detect_province_from_filename(self, filename: str) -> str:
        """ดึงชื่อจังหวัดจากชื่อไฟล์อัตโนมัติ"""
        basename = os.path.basename(filename).lower()
        for key, province in PROVINCE_MAPPING.items():
            if key.lower() in basename:
                logger.info(f"🗺️ Auto-detected province from filename: {province}")
                return province
        return None
    
    def find_matching_sheet(self, available_sheets: list, sheet_key: str) -> str:
        """หา sheet ที่ตรงกับ key"""
        possible_names = SHEET_NAMES.get(sheet_key, [])
        for name in possible_names:
            if name in available_sheets:
                return name
        return None
    
    def auto_detect_columns(self, df: pd.DataFrame) -> dict:
        """
        Auto-detect column names จาก DataFrame
        รองรับหลายรูปแบบ column names
        """
        column_mapping = {
            'province': ['ProvinceNameTh', 'Province', 'จังหวัด', 'province'],
            'district': ['DistrictNameTh', 'District', 'เขต', 'อำเภอ', 'district'],
            'subdistrict': ['SubDistrictNameTh', 'SubDistrict', 'ตำบล', 'แขวง'],
            'school_name': ['SchoolName', 'School', 'ชื่อโรงเรียน', 'โรงเรียน'],
            'department': ['DepartmentNameTh', 'Department', 'สังกัด', 'หน่วยงาน'],
            'students_male': ['Sum_Male1', 'Male', 'นักเรียนชาย', 'ชาย'],
            'students_female': ['Sum_Female1', 'Female', 'นักเรียนหญิง', 'หญิง'],
            'students_total': ['Sum_Students', 'TotalStudents', 'นักเรียนรวม'],
            'teachers_total': ['Sum_Teachers', 'TotalTeachers', 'ครูรวม'],
            'schools_total': ['Sum_Schools', 'TotalSchools', 'โรงเรียนรวม'],
            'year': ['YearEdu', 'Year', 'ปีการศึกษา', 'ปี'],
        }
        
        detected = {}
        df_columns = df.columns.tolist()
        
        for key, possible_names in column_mapping.items():
            for name in possible_names:
                if name in df_columns:
                    detected[key] = name
                    break
        
        return detected
    
    def generate_summary_chunks(self, df: pd.DataFrame, data_type: str) -> list:
        """
        Auto-generate Summary Chunks (Pre-aggregation)
        สร้าง chunks สรุประดับจังหวัดและเขตอัตโนมัติ
        """
        chunks = []
        cols = self.auto_detect_columns(df)
        
        province_col = cols.get('province')
        district_col = cols.get('district')
        year_col = cols.get('year')
        
        if not province_col:
            return chunks
        
        # Get year
        year = df[year_col].iloc[0] if year_col and year_col in df.columns else 2568
        
        # =============================================
        # PROVINCE-LEVEL SUMMARY (ระดับจังหวัด)
        # =============================================
        for province in df[province_col].dropna().unique():
            province_df = df[df[province_col] == province]
            
            if data_type == 'schools':
                total_schools = len(province_df)
                male_col = cols.get('students_male')
                female_col = cols.get('students_female')
                
                total_male = province_df[male_col].sum() if male_col else 0
                total_female = province_df[female_col].sum() if female_col else 0
                total_students = total_male + total_female
                
                text = f"""สรุปข้อมูลการศึกษาจังหวัด{province} ปีการศึกษา {year}
มีโรงเรียนทั้งหมด {total_schools:,} แห่ง
มีนักเรียนรวม {total_students:,} คน (ชาย {total_male:,} คน หญิง {total_female:,} คน)"""
                
                chunks.append({
                    'text': text.strip(),
                    'metadata': {
                        'type': 'province_summary',
                        'province': province,
                        'year': int(year),
                        'total_schools': int(total_schools),
                        'total_students': int(total_students),
                        'total_male': int(total_male),
                        'total_female': int(total_female)
                    }
                })
                
                # District-level summaries
                if district_col and district_col in province_df.columns:
                    for district in province_df[district_col].dropna().unique():
                        district_df = province_df[province_df[district_col] == district]
                        d_schools = len(district_df)
                        d_male = district_df[male_col].sum() if male_col else 0
                        d_female = district_df[female_col].sum() if female_col else 0
                        d_total = d_male + d_female
                        
                        text = f"""เขต{district} จังหวัด{province} ปี {year}
มีโรงเรียน {d_schools:,} แห่ง นักเรียน {d_total:,} คน"""
                        
                        chunks.append({
                            'text': text.strip(),
                            'metadata': {
                                'type': 'district_summary',
                                'province': province,
                                'district': str(district),
                                'year': int(year),
                                'total_schools': int(d_schools),
                                'total_students': int(d_total)
                            }
                        })
            
            elif data_type == 'students':
                count_col = cols.get('students_total')
                total = province_df[count_col].sum() if count_col else len(province_df)
                
                text = f"""สถิตินักเรียนจังหวัด{province} ปี {year} มีนักเรียนรวม {total:,} คน"""
                
                chunks.append({
                    'text': text.strip(),
                    'metadata': {
                        'type': 'province_student_summary',
                        'province': province,
                        'year': int(year),
                        'total_students': int(total)
                    }
                })
            
            elif data_type == 'teachers':
                count_col = cols.get('teachers_total')
                total = province_df[count_col].sum() if count_col else len(province_df)
                
                text = f"""สถิติครูและบุคลากรจังหวัด{province} ปี {year} มีบุคลากรรวม {total:,} คน"""
                
                chunks.append({
                    'text': text.strip(),
                    'metadata': {
                        'type': 'province_teacher_summary',
                        'province': province,
                        'year': int(year),
                        'total_teachers': int(total)
                    }
                })
            
            elif data_type == 'school_stats':
                count_col = cols.get('schools_total')
                total = province_df[count_col].sum() if count_col else len(province_df)
                
                text = f"""จังหวัด{province} ปี {year} มีสถานศึกษารวม {total:,} แห่ง"""
                
                chunks.append({
                    'text': text.strip(),
                    'metadata': {
                        'type': 'province_school_count_summary',
                        'province': province,
                        'year': int(year),
                        'total_schools': int(total)
                    }
                })
        
        logger.info(f"📊 สร้าง Summary Chunks: {len(chunks)} รายการ")
        return chunks
    
    # =========================================================================
    # CHUNK GENERATORS - สร้างข้อความบริบทสมบูรณ์
    # =========================================================================
    
    def generate_school_chunk(self, row: pd.Series) -> dict:
        """
        สร้าง chunk สำหรับข้อมูลโรงเรียน (Fact_Bangkok)
        """
        try:
            school_name = str(row.get('SchoolName', '')).strip()
            subdistrict = str(row.get('SubDistrictNameTh', '')).strip()
            district = str(row.get('DistrictNameTh', '')).strip()
            province = str(row.get('ProvinceNameTh', 'กรุงเทพมหานคร')).strip()
            department = str(row.get('DepartmentNameTh', '')).strip()
            area = str(row.get('AreaName', '')).strip()
            
            sum_male = int(row.get('Sum_Male1', 0) or 0)
            sum_female = int(row.get('Sum_Female1', 0) or 0)
            total_students = sum_male + sum_female
            
            lat = float(row.get('Latitude', 0) or 0)
            lon = float(row.get('Longitude', 0) or 0)
            year = int(row.get('YearEdu', 2568) or 2568)
            school_code = str(row.get('SchoolCode', '')).strip()
            
            # สร้างข้อความบริบทสมบูรณ์
            text = f"""โรงเรียน{school_name} สังกัด{department} 
ตั้งอยู่ที่ตำบล{subdistrict} เขต{district} {province} 
อยู่ในพื้นที่การศึกษา{area}
ปีการศึกษา {year} มีนักเรียนชาย {sum_male:,} คน นักเรียนหญิง {sum_female:,} คน รวมทั้งหมด {total_students:,} คน"""

            if lat and lon:
                text += f"\nพิกัด GPS: {lat}, {lon}"
            
            # Auto-expand คำย่อ
            text = self.expand_text(text)
            
            return {
                'text': text.strip(),
                'metadata': {
                    'type': 'school_info',
                    'school_name': school_name,
                    'school_code': school_code,
                    'subdistrict': subdistrict,
                    'district': district,
                    'province': province,
                    'department': department,
                    'area': area,
                    'year': year,
                    'sum_male': sum_male,
                    'sum_female': sum_female,
                    'total_students': total_students,
                    'latitude': lat,
                    'longitude': lon
                }
            }
        except Exception as e:
            logger.error(f"Error processing school row: {e}")
            return None
    
    def generate_student_chunk(self, row: pd.Series) -> dict:
        """
        สร้าง chunk สำหรับสถิตินักเรียน (Fact_Student_Bangkok)
        """
        try:
            subdistrict = str(row.get('SubDistrictNameTh', '')).strip()
            district = str(row.get('DistrictNameTh', '')).strip()
            province = str(row.get('ProvinceNameTh', 'กรุงเทพมหานคร')).strip()
            department = str(row.get('DepartmentNameTh', '')).strip()
            area = str(row.get('AreaName', '')).strip()
            school_name = str(row.get('SchoolName', '')).strip()
            grade_level = str(row.get('GradeLevel', '')).strip()
            gender = str(row.get('GenderNameTh', '')).strip()
            count = int(row.get('Sum_Students', 0) or 0)
            year = int(row.get('YearEdu', 2568) or 2568)
            
            text = f"""สถิตินักเรียนโรงเรียน{school_name} เขต{district} {province}
สังกัด{department} พื้นที่{area}
ระดับชั้น{grade_level} เพศ{gender} 
ปีการศึกษา {year} มีนักเรียน {count:,} คน"""
            
            # Auto-expand คำย่อ
            text = self.expand_text(text)
            
            return {
                'text': text.strip(),
                'metadata': {
                    'type': 'student_stats',
                    'school_name': school_name,
                    'subdistrict': subdistrict,
                    'district': district,
                    'province': province,
                    'department': department,
                    'area': area,
                    'grade_level': grade_level,
                    'gender': gender,
                    'count': count,
                    'year': year
                }
            }
        except Exception as e:
            logger.error(f"Error processing student row: {e}")
            return None
    
    def generate_school_stats_chunk(self, row: pd.Series) -> dict:
        """
        สร้าง chunk สำหรับจำนวนโรงเรียน (Fact_School_Bangkok)
        """
        try:
            subdistrict = str(row.get('SubDistrictNameTh', '')).strip()
            district = str(row.get('DistrictNameTh', '')).strip()
            province = str(row.get('ProvinceNameTh', 'กรุงเทพมหานคร')).strip()
            department = str(row.get('DepartmentNameTh', '')).strip()
            area = str(row.get('AreaName', '')).strip()
            education_status = str(row.get('EducationStatusGroupName', '')).strip()
            count = int(row.get('Sum_Schools', 0) or 0)
            year = int(row.get('YearEdu', 2568) or 2568)
            
            text = f"""จำนวนโรงเรียนใน{province} เขต{district} ตำบล{subdistrict}
สังกัด{department} พื้นที่{area}
สถานะ{education_status}
ปีการศึกษา {year} มีโรงเรียนทั้งหมด {count:,} แห่ง"""
            
            # Auto-expand คำย่อ
            text = self.expand_text(text)
            
            return {
                'text': text.strip(),
                'metadata': {
                    'type': 'school_count',
                    'subdistrict': subdistrict,
                    'district': district,
                    'province': province,
                    'department': department,
                    'area': area,
                    'education_status': education_status,
                    'count': count,
                    'year': year
                }
            }
        except Exception as e:
            logger.error(f"Error processing school stats row: {e}")
            return None
    
    def generate_teacher_chunk(self, row: pd.Series) -> dict:
        """
        สร้าง chunk สำหรับสถิติครู (Fact_Teacher_Bangkok)
        """
        try:
            subdistrict = str(row.get('SubDistrictNameTh', '')).strip()
            district = str(row.get('DistrictNameTh', '')).strip()
            province = str(row.get('ProvinceNameTh', 'กรุงเทพมหานคร')).strip()
            department = str(row.get('DepartmentNameTh', '')).strip()
            area = str(row.get('AreaName', '')).strip()
            school_name = str(row.get('SchoolName', '')).strip()
            person_type = str(row.get('PersonTypeName', '')).strip()
            gender = str(row.get('GenderNameTh', '')).strip()
            count = int(row.get('Sum_Teachers', 0) or 0)
            year = int(row.get('YearEdu', 2568) or 2568)
            
            text = f"""สถิติบุคลากรโรงเรียน{school_name} เขต{district} {province}
สังกัด{department} พื้นที่{area}
ประเภทบุคลากร: {person_type} เพศ{gender}
ปีการศึกษา {year} มีจำนวน {count:,} คน"""
            
            # Auto-expand คำย่อ
            text = self.expand_text(text)
            
            return {
                'text': text.strip(),
                'metadata': {
                    'type': 'teacher_stats',
                    'school_name': school_name,
                    'subdistrict': subdistrict,
                    'district': district,
                    'province': province,
                    'department': department,
                    'area': area,
                    'person_type': person_type,
                    'gender': gender,
                    'count': count,
                    'year': year
                }
            }
        except Exception as e:
            logger.error(f"Error processing teacher row: {e}")
            return None
    
    # =========================================================================
    # MAIN INGESTION LOGIC
    # =========================================================================
    
    def generate_point_id(self, text: str) -> int:
        """สร้าง unique ID จาก text hash"""
        return int(hashlib.md5(text.encode()).hexdigest()[:15], 16)
    
    def ingest_dataframe(self, df: pd.DataFrame, chunk_generator, data_type: str, sheet_key: str = None):
        """
        Ingest DataFrame เข้า Qdrant
        พร้อมสร้าง Summary Chunks อัตโนมัติ
        """
        logger.info(f"📊 กำลังประมวลผล {data_type}: {len(df)} แถว")
        
        # 1. สร้าง Detail Chunks (รายโรงเรียน)
        chunks = []
        for _, row in df.iterrows():
            chunk = chunk_generator(row)
            if chunk:
                chunks.append(chunk)
        
        logger.info(f"✅ สร้าง Detail Chunks: {len(chunks)} รายการ")
        
        # 2. สร้าง Summary Chunks อัตโนมัติ (ระดับจังหวัด/เขต)
        if sheet_key:
            summary_chunks = self.generate_summary_chunks(df, sheet_key)
            chunks.extend(summary_chunks)
            logger.info(f"📊 รวม Summary + Detail: {len(chunks)} chunks")
        
        # Batch embedding and upload
        for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc=f"Uploading {data_type}"):
            batch = chunks[i:i + BATCH_SIZE]
            texts = [c['text'] for c in batch]
            vectors = self.embed_texts(texts)
            
            points = []
            for j, (chunk, vector) in enumerate(zip(batch, vectors)):
                point_id = self.generate_point_id(chunk['text'])
                points.append(PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        'text': chunk['text'],
                        'metadata': chunk['metadata']
                    }
                ))
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        
        logger.info(f"✅ อัพโหลด {data_type} สำเร็จ!")
    
    def ingest_excel(self, file_path: str, recreate: bool = False):
        """
        Ingest ไฟล์ Excel ทั้งหมดเข้า Qdrant
        รองรับ auto-detect sheet names
        """
        logger.info(f"📁 กำลังอ่านไฟล์: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"❌ ไม่พบไฟล์: {file_path}")
            return False
        
        # Auto-detect province from filename
        detected_province = self.detect_province_from_filename(file_path)
        
        # Connect and setup
        self.connect()
        self.create_collection(recreate=recreate)
        
        # Read Excel
        excel = pd.ExcelFile(file_path)
        available_sheets = excel.sheet_names
        logger.info(f"📋 Sheets ที่พบ: {available_sheets}")
        
        # Sheet processors with auto-detection
        sheet_configs = [
            ('schools', self.generate_school_chunk, 'ข้อมูลโรงเรียน'),
            ('students', self.generate_student_chunk, 'สถิตินักเรียน'),
            ('school_stats', self.generate_school_stats_chunk, 'จำนวนโรงเรียน'),
            ('teachers', self.generate_teacher_chunk, 'สถิติครู'),
        ]
        
        total_processed = 0
        for sheet_key, generator, description in sheet_configs:
            # Auto-find matching sheet name
            sheet_name = self.find_matching_sheet(available_sheets, sheet_key)
            
            if sheet_name:
                logger.info(f"\n{'='*50}")
                logger.info(f"📖 กำลังอ่าน Sheet: {sheet_name}")
                df = pd.read_excel(excel, sheet_name=sheet_name)
                
                # Add detected province if not in data
                if detected_province and 'ProvinceNameTh' not in df.columns:
                    df['ProvinceNameTh'] = detected_province
                    logger.info(f"🗺️ เพิ่มจังหวัด: {detected_province}")
                
                self.ingest_dataframe(df, generator, description, sheet_key=sheet_key)
                total_processed += len(df)
            else:
                logger.warning(f"⚠️ ไม่พบ Sheet สำหรับ: {sheet_key}")
        
        # Summary
        collection_info = self.client.get_collection(self.collection_name)
        logger.info(f"\n{'='*50}")
        logger.info(f"🎉 สรุปผลการ Ingest:")
        logger.info(f"   - ไฟล์: {file_path}")
        logger.info(f"   - Collection: {self.collection_name}")
        logger.info(f"   - Provider: {self.provider}")
        logger.info(f"   - จำนวน Vectors: {collection_info.points_count}")
        logger.info(f"{'='*50}")
        
        return True
    
    def ingest_folder(self, folder_path: str, recreate: bool = False):
        """
        Ingest ทุกไฟล์ Excel ในโฟลเดอร์เข้า Qdrant
        รองรับ 77 จังหวัด พร้อมกัน!
        """
        logger.info(f"📂 กำลังสแกนโฟลเดอร์: {folder_path}")
        
        if not os.path.isdir(folder_path):
            logger.error(f"❌ ไม่พบโฟลเดอร์: {folder_path}")
            return False
        
        # Find all Excel files
        excel_files = []
        for ext in ['*.xlsx', '*.xls', '*.xlsm']:
            excel_files.extend(glob.glob(os.path.join(folder_path, ext)))
            excel_files.extend(glob.glob(os.path.join(folder_path, '**', ext), recursive=True))
        
        excel_files = list(set(excel_files))  # Remove duplicates
        
        if not excel_files:
            logger.warning(f"⚠️ ไม่พบไฟล์ Excel ในโฟลเดอร์: {folder_path}")
            return False
        
        logger.info(f"📊 พบไฟล์ Excel: {len(excel_files)} ไฟล์")
        for i, f in enumerate(excel_files[:5], 1):
            logger.info(f"   {i}. {os.path.basename(f)}")
        if len(excel_files) > 5:
            logger.info(f"   ... และอีก {len(excel_files) - 5} ไฟล์")
        
        # Connect and create collection ONCE
        self.connect()
        self.create_collection(recreate=recreate)
        
        # Process each file
        total_files = len(excel_files)
        success_count = 0
        failed_files = []
        
        for idx, file_path in enumerate(excel_files, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📁 กำลังประมวลผล [{idx}/{total_files}]: {os.path.basename(file_path)}")
            logger.info(f"{'='*60}")
            
            try:
                # Auto-detect province from filename
                detected_province = self.detect_province_from_filename(file_path)
                
                # Read Excel
                excel = pd.ExcelFile(file_path)
                available_sheets = excel.sheet_names
                logger.info(f"📋 Sheets: {available_sheets}")
                
                # Sheet processors
                sheet_configs = [
                    ('schools', self.generate_school_chunk, 'ข้อมูลโรงเรียน'),
                    ('students', self.generate_student_chunk, 'สถิตินักเรียน'),
                    ('school_stats', self.generate_school_stats_chunk, 'จำนวนโรงเรียน'),
                    ('teachers', self.generate_teacher_chunk, 'สถิติครู'),
                ]
                
                for sheet_key, generator, description in sheet_configs:
                    sheet_name = self.find_matching_sheet(available_sheets, sheet_key)
                    
                    if sheet_name:
                        df = pd.read_excel(excel, sheet_name=sheet_name)
                        
                        # Add province if not in data
                        if detected_province and 'ProvinceNameTh' not in df.columns:
                            df['ProvinceNameTh'] = detected_province
                        
                        # Add source file metadata
                        df['_source_file'] = os.path.basename(file_path)
                        
                        self.ingest_dataframe(df, generator, f"{description} ({os.path.basename(file_path)})", sheet_key=sheet_key)
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ Error processing {file_path}: {e}")
                failed_files.append(file_path)
        
        # Final Summary
        collection_info = self.client.get_collection(self.collection_name)
        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 สรุปผลการ Ingest ทั้งหมด:")
        logger.info(f"   📂 โฟลเดอร์: {folder_path}")
        logger.info(f"   📊 ไฟล์ทั้งหมด: {total_files}")
        logger.info(f"   ✅ สำเร็จ: {success_count}")
        logger.info(f"   ❌ ล้มเหลว: {len(failed_files)}")
        logger.info(f"   📦 Collection: {self.collection_name}")
        logger.info(f"   🔢 จำนวน Vectors ทั้งหมด: {collection_info.points_count:,}")
        logger.info(f"{'='*60}")
        
        if failed_files:
            logger.warning("⚠️ ไฟล์ที่ล้มเหลว:")
            for f in failed_files:
                logger.warning(f"   - {f}")
        
        return len(failed_files) == 0


def main():
    parser = argparse.ArgumentParser(
        description='🏫 Thailand Education Data RAG Ingestion',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:

  # ไฟล์เดียว
  python ingest_education.py --file data/Fact_Bangkok.xlsx

  # ทั้งโฟลเดอร์ (77 จังหวัด!)
  python ingest_education.py --folder data/

  # ใช้ Gemini Embedding (ฟรี!)
  python ingest_education.py --folder data/ --provider gemini

  # ลบข้อมูลเดิมแล้ว ingest ใหม่
  python ingest_education.py --folder data/ --recreate
        """
    )
    
    # Input options (file or folder)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--file', '-f',
        help='ไฟล์ Excel ที่ต้องการ ingest (ไฟล์เดียว)'
    )
    input_group.add_argument(
        '--folder', '-d',
        help='โฟลเดอร์ที่มีไฟล์ Excel (77 จังหวัด)'
    )
    
    parser.add_argument(
        '--collection', '-c',
        default=COLLECTION_NAME,
        help=f'ชื่อ Collection ใน Qdrant (default: {COLLECTION_NAME})'
    )
    
    parser.add_argument(
        '--provider', '-p',
        choices=['local', 'gemini', 'openai'],
        default='gemini',
        help='Embedding: local (ฟรี offline), gemini (ฟรี API), openai (เสียเงิน)'
    )
    
    parser.add_argument(
        '--recreate',
        action='store_true',
        help='ลบ Collection เดิมและสร้างใหม่'
    )
    
    parser.add_argument(
        '--qdrant-url',
        default=QDRANT_URL,
        help=f'Qdrant URL (default: {QDRANT_URL})'
    )
    
    args = parser.parse_args()
    
    # Create ingester
    ingester = ThailandEducationIngester(
        qdrant_url=args.qdrant_url,
        collection_name=args.collection,
        provider=args.provider
    )
    
    # Run ingestion
    if args.folder:
        success = ingester.ingest_folder(
            folder_path=args.folder,
            recreate=args.recreate
        )
    else:
        success = ingester.ingest_excel(
            file_path=args.file,
            recreate=args.recreate
        )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
