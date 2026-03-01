
import { Category } from './types';
import { SYSTEM_PROMPT } from './config/systemPrompts';

// Re-export the unified system prompt
export const SYSTEM_INSTRUCTION = SYSTEM_PROMPT;

export const MOE_COLORS = {
  appleBlue: '#007AFF',
  appleDeepBlue: '#005AC1',
  glassWhite: 'rgba(255, 255, 255, 0.7)',
  glassBorder: 'rgba(255, 255, 255, 0.4)',
  textMain: '#1D1D1F',
  textSecondary: '#86868B',
};

export const COMMON_QUERIES = {
  [Category.General]: [
    "แนวทางการขับเคลื่อน Digital Governance ของ ศทก.",
    "รายงานการใช้งาน ICT ในสถานศึกษาขนาดเล็ก",
    "วิสัยทัศน์ดิจิทัลเพื่อการศึกษาปี 2568",
    "บทบาทของ ศทก. ในการสนับสนุนงาน สป."
  ],
  [Category.School]: [
    "ค้นหาพิกัดโรงเรียนในสังกัด สพฐ. ทั่วประเทศ",
    "จำนวนสถานศึกษาในพื้นที่นวัตกรรมการศึกษา",
    "รายชื่อโรงเรียนที่ตั้งอยู่ในพื้นที่ห่างไกล (OBEC)",
    "สถานะการเชื่อมต่ออินเทอร์เน็ตของโรงเรียนรายสังกัด"
  ],
  [Category.Student]: [
    "สถิติจำนวนนักเรียนรายจังหวัด ปีการศึกษา 2567",
    "จำนวนครูและบุคลากรทางการศึกษาแยกตามสังกัด",
    "อัตราส่วนนักเรียนต่อคอมพิวเตอร์รายสังกัด",
    "แนวโน้มจำนวนนักเรียนที่ลดลงในรอบ 5 ปี"
  ]
};

const getLastMonday = () => {
  const d = new Date();
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  return monday.toLocaleDateString('th-TH', { day: 'numeric', month: 'long' }) + ', 08:00';
};

const LAST_UPDATE_STR = getLastMonday();

export const MOCK_STATS = [
  {
    category: Category.General,
    label: 'ดัชนีความพร้อมดิจิทัล (ศทก. สป.)',
    value: '84.2',
    unit: '%',
    trend: '+2.4% (ความคืบหน้าปัจจุบัน)',
    icon: '🌍',
    color: 'from-indigo-500 to-purple-600',
    lastUpdated: LAST_UPDATE_STR
  },
  {
    category: Category.School,
    label: 'เครือข่ายฐานข้อมูลสถานศึกษา',
    value: '30,124',
    unit: 'แห่ง',
    trend: '98.5% ตรวจสอบพิกัดพื้นที่ (GIS) แล้ว',
    icon: '🏫',
    color: 'from-blue-500 to-cyan-500',
    lastUpdated: LAST_UPDATE_STR
  },
  {
    category: Category.Student,
    label: 'ฐานข้อมูลนักเรียนรายบุคคล (2567)',
    value: '6.48',
    unit: 'ล้านคน',
    trend: 'อัตราส่วนครู 1:18 (สถานะทั่วประเทศ)',
    icon: '📊',
    color: 'from-violet-500 to-fuchsia-500',
    lastUpdated: LAST_UPDATE_STR
  }
];
