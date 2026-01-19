/**
 * 📄 ชื่อไฟล์: geminiService.ts
 * 📝 คำอธิบาย:
 *    บริการจัดการสมองของ AI (AI Brain Service)
 *    เป็นส่วนที่ฉลาดที่สุด ทำหน้าที่คิด วิเคราะห์ และเชื่อมต่อกับ Google Gemini / Groq
 *
 * 🛠 หน้าที่หลัก:
 *    1. AI Connection: ส่งข้อความไปหา AI (Gemini/Groq) และรับคำตอบ
 *    2. Key Rotation: สลับ API Key อัตโนมัติเมื่อโควต้าเต็ม (Load Balancing)
 *    3. RAG System: ค้นหาข้อมูลจากเอกสาร (Retrieval Augmented Generation) มาตอบคำถาม
 *    4. Format & Validate: ตรวจสอบและจัดรูปแบบคำตอบให้สวยงาม
 */

import { GoogleGenAI } from "@google/genai";
import { AdminConfig } from '../types/admin.types';
import { DEFAULT_CONFIG } from '../config';

// ============================================================================
// TYPES & CONSTANTS
// ============================================================================

let ai: GoogleGenAI | null = null;
let chatSession: any = null;
let currentConfig: AdminConfig = DEFAULT_CONFIG;
let currentApiKey: string = '';

// Track active key queues per category (Priority Queue)
const activeKeyQueues: Record<string, string[]> = {
  general: [],
  school: [],
  student: []
};

// Track active GROQ key queues
const activeGroqQueues: Record<string, string[]> = {
  general: [],
  school: [],
  student: []
};


// Cache supported models per API key to avoid repeated calls
const supportedModelsCache: Record<string, string[]> = {};
let detectedModelForChat: string = '';

// Fisher-Yates Shuffle for Load Balancing
const shuffleArray = (array: string[]) => {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
};

// ============================================================================
// QUEUE MANAGEMENT (Generic)
// ============================================================================

const loadKeyQueue = (category: string, configKeys: string[], provider: 'gemini' | 'groq') => {
  const keyPrefix = provider === 'groq' ? 'groq_queue_' : 'gemini_queue_';
  try {
    const savedQueue = localStorage.getItem(`${keyPrefix}${category}`);
    if (savedQueue) {
      const parsed = JSON.parse(savedQueue);
      const validSaved = parsed.filter((k: string) => configKeys.includes(k));
      const newKeys = configKeys.filter(k => !validSaved.includes(k));
      return [...validSaved, ...newKeys];
    }
  } catch (e) {
    console.warn(`Failed to load ${provider} key queue`, e);
  }

  // Load Balancing: Shuffle new sessions
  if (configKeys.length > 1) {
    return shuffleArray(configKeys);
  }
  return [...configKeys];
};

const saveKeyQueue = (category: string, queue: string[], provider: 'gemini' | 'groq') => {
  const keyPrefix = provider === 'groq' ? 'groq_queue_' : 'gemini_queue_';
  localStorage.setItem(`${keyPrefix}${category}`, JSON.stringify(queue));
};

// ============================================================================
// GEMINI LOGIC (Legacy + Fallback)
// ============================================================================

// Model Priority List (Ordered by preference - first available wins)
// Updated Jan 2026 - Free tier only has gemini-2.5-flash
const MODEL_PRIORITY_LIST = [
  'gemini-2.5-flash',           // FREE TIER - the only model available
  'gemini-2.0-flash-exp',       // Backup if paid tier
  'gemini-2.0-flash',           // Alternative
  'gemini-1.5-flash',           // Legacy
];

// Cache for validated models per API key
const validatedModelCache: Record<string, string> = {};

/**
 * Dynamically validates and returns the first available Gemini model.
 * Uses a priority list and probes each model until one works.
 */
const getAvailableGeminiModel = async (apiKey: string): Promise<string> => {
  // Check cache first
  if (validatedModelCache[apiKey]) {
    console.log(`📋 [Model] Using cached validated model: ${validatedModelCache[apiKey]}`);
    return validatedModelCache[apiKey];
  }

  console.log('🔍 [Model] Probing for available Gemini models...');

  for (const modelName of MODEL_PRIORITY_LIST) {
    try {
      // Lightweight probe - just check if model exists via generateContent with minimal tokens
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{ parts: [{ text: 'hi' }] }],
            generationConfig: { maxOutputTokens: 1 }
          }),
          signal: controller.signal
        }
      );
      clearTimeout(timeoutId);

      if (response.ok) {
        console.log(`✅ [Model] Validated: ${modelName} is available`);
        validatedModelCache[apiKey] = modelName;
        return modelName;
      }

      const errorData = await response.json().catch(() => ({}));
      const errorMsg = errorData?.error?.message || '';

      // 404 = Model not found, try next
      if (response.status === 404 || errorMsg.includes('not found')) {
        console.log(`⏭️ [Model] ${modelName} not found, trying next...`);
        continue;
      }

      // 429 = Quota limit, model exists but quota exhausted
      if (response.status === 429) {
        console.log(`⚠️ [Model] ${modelName} exists but quota exhausted, trying next...`);
        continue;
      }

      // Other errors (400, etc.) - model might work but request was bad
      // Consider it valid since it responded
      if (response.status < 500) {
        console.log(`✅ [Model] ${modelName} responded (status ${response.status}), marking as valid`);
        validatedModelCache[apiKey] = modelName;
        return modelName;
      }

    } catch (error: any) {
      // Network error or timeout - skip this model
      console.log(`⏭️ [Model] ${modelName} probe failed: ${error.message}`);
      continue;
    }
  }

  // Ultimate fallback - gemini-2.5-flash is THE free tier model
  console.warn('⚠️ [Model] No models validated, using ultimate fallback: gemini-2.5-flash');
  return 'gemini-2.5-flash';
};

// Clear validated model cache (call when key changes)
const clearModelCache = (apiKey?: string) => {
  if (apiKey) {
    delete validatedModelCache[apiKey];
  } else {
    Object.keys(validatedModelCache).forEach(k => delete validatedModelCache[k]);
  }
};

const detectSupportedModels = async (apiKey: string): Promise<string[]> => {
  if (supportedModelsCache[apiKey]) return supportedModelsCache[apiKey];

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`,
      { signal: controller.signal }
    );
    clearTimeout(timeoutId);

    if (!response.ok) return [];

    const data = await response.json();
    const models = (data.models || [])
      .map((m: any) => m.name.replace('models/', ''))
      .filter((name: string) => name.includes('gemini'));

    supportedModelsCache[apiKey] = models;
    return models;
  } catch (error) {
    return [];
  }
};

const chooseBestModel = (supportedModels: string[], preferredModel: string): string => {
  // If we have detected models, use priority-based selection
  if (supportedModels.length > 0) {
    // First check if preferred model is available
    if (supportedModels.includes(preferredModel)) return preferredModel;

    // Then go through priority list
    for (const priorityModel of MODEL_PRIORITY_LIST) {
      const match = supportedModels.find(m =>
        m === priorityModel || m.includes(priorityModel) || priorityModel.includes(m)
      );
      if (match) return match;
    }

    // Return first available
    return supportedModels[0];
  }

  // No detected models - return preferred or first from priority list
  return preferredModel || MODEL_PRIORITY_LIST[0];
};

// Original initializeGemini (Kept for compatibility, acts as reset)
const initializeGemini = (category: string = 'general', forceReinit: boolean = false): boolean => {
  const catKey = (category.toLowerCase() === 'school' ? 'school' :
    category.toLowerCase() === 'student' ? 'student' : 'general') as keyof typeof currentConfig.apiKeys;

  const categoryConfig = currentConfig.apiKeys?.[catKey];
  const geminiKeys = categoryConfig?.geminiKeys || [];
  const groqKeys = categoryConfig?.groqKeys || [];

  // Init Gemini Queue
  if (activeKeyQueues[catKey].length === 0 ||
    activeKeyQueues[catKey].length !== geminiKeys.length ||
    activeKeyQueues[catKey].some(k => !geminiKeys.includes(k))) {
    activeKeyQueues[catKey] = loadKeyQueue(catKey, geminiKeys, 'gemini');
  }

  // Init Groq Queue
  if (activeGroqQueues[catKey].length === 0 ||
    activeGroqQueues[catKey].length !== groqKeys.length ||
    activeGroqQueues[catKey].some(k => !groqKeys.includes(k))) {
    activeGroqQueues[catKey] = loadKeyQueue(catKey, groqKeys, 'groq');
  }

  // Gemini Setup
  let apiKey = activeKeyQueues[catKey][0];
  if (!apiKey) {
    apiKey = (import.meta as any).env?.VITE_GEMINI_API_KEY || process.env.VITE_GEMINI_API_KEY || '';
  }

  if (forceReinit || currentApiKey !== apiKey) {
    currentApiKey = apiKey;
    if (apiKey) {
      ai = new GoogleGenAI({ apiKey });
    }
    chatSession = null;
    detectedModelForChat = '';
  }
  return true;
};

// Update config from AdminConfigContext
export const updateGeminiConfig = (config: AdminConfig) => {
  currentConfig = config;
  chatSession = null;
};

// ============================================================================
// GROQ LOGIC (Primary Provider)
// ============================================================================

const callGroqAPI = async (
  messages: { role: string, content: string }[],
  apiKey: string,
  model: string = 'llama-3.3-70b-versatile',
  onChunk: (text: string) => void
): Promise<void> => {
  const controller = new AbortController();
  // 30s timeout for Groq
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: messages,
        model: model,
        stream: true,
        temperature: 0.7,
        max_tokens: 2048
      }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Groq API Error: ${response.status} - ${errorText}`);
    }

    if (!response.body) throw new Error("No response body from Groq");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data: ")) {
          const jsonStr = trimmed.replace("data: ", "");
          if (jsonStr === "[DONE]") return;
          try {
            const json = JSON.parse(jsonStr);
            const content = json.choices?.[0]?.delta?.content;
            if (content) {
              onChunk(sanitizeResponseText(content));
            }
          } catch (e) {
            // ignore parse errors for partial chunks
          }
        }
      }
    }
  } catch (error) {
    throw error;
  }
}

// ============================================================================
// TEXT SANITIZATION (Remove unwanted characters like Chinese)
// ============================================================================

/**
 * Sanitizes AI response text to remove unwanted characters.
 * - Removes Chinese/Japanese/Korean characters
 * - Cleans up excessive whitespace
 * - Forces line breaks for numbered lists and bullet points
 */
const sanitizeResponseText = (text: string): string => {
  if (!text) return text;

  // 1. Identity Enforcer: "น้อง DO" (ensure consistent spacing)
  let cleaned = text.replace(/น้อง\s*DO/g, 'น้อง DO');

  // 2. Remove CJK junk
  cleaned = cleaned.replace(/[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]/g, '');

  // 3. Ensure a space exists after list markers for proper Markdown
  cleaned = cleaned.replace(/\n\s*([-*•])([^\s])/g, '\n- $2');

  // 4. Ensure double newlines before lists ONLY if preceded by text without a newline
  cleaned = cleaned.replace(/([ก-๙a-zA-Z0-9])\n([-*•])\s/g, '$1\n\n- ');

  // 5. Clean excessive newlines
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');

  // 6. Collapse multiple spaces (fix inconsistent spacing)
  cleaned = cleaned.replace(/[ \t]{2,}/g, ' ');

  // 7. Fix spacing around punctuation (Thai doesn't need space before/after colons)
  cleaned = cleaned.replace(/\s+:/g, ':');
  cleaned = cleaned.replace(/:\s+/g, ': ');

  return cleaned;
};

// ============================================================================
// AI LAYER: QUERY NORMALIZER (Step 1 - Before Flask API)
// ============================================================================

interface ParsedQuery {
  intent: 'count' | 'list' | 'compare' | 'ranking' | 'detail' | 'search' | 'general';
  level: 'province' | 'district' | 'subdistrict' | 'agency' | 'school';
  province?: string;
  district?: string;
  subdistrict?: string;
  agency?: string;
  region?: string;
  school_name?: string;
  comparisonType?: 'most' | 'least' | 'compare';
  normalizedQuery: string;
  requiresMultiQuery: boolean;
}

/**
 * AI Query Normalizer - แปลงคำถามธรรมชาติ → structured query
 * Uses Groq for fast processing
 */
const aiQueryNormalizer = async (
  userMessage: string,
  groqKey: string
): Promise<ParsedQuery | null> => {
  try {
    console.log('[AI Layer 1] Normalizing query:', userMessage);

    const prompt = `คุณคือ Query Parser สำหรับระบบค้นหาข้อมูลโรงเรียน

วิเคราะห์คำถามนี้: "${userMessage}"

ตอบเป็น JSON เท่านั้น (ไม่ต้องมีคำอธิบาย):
{
  "intent": "count|list|compare|ranking|detail|search|general",
  "level": "province|district|subdistrict|agency|school",
  "province": "ชื่อจังหวัด หรือ null",
  "district": "ชื่ออำเภอ หรือ null", 
  "subdistrict": "ชื่อตำบล หรือ null",
  "agency": "ชื่อหน่วยงาน หรือ null",
  "region": "ภาคเหนือ|ภาคใต้|ภาคกลาง|ภาคตะวันออก|ภาคตะวันตก|ภาคอีสาน หรือ null",
  "school_name": "ชื่อโรงเรียนที่ต้องการค้นหา หรือ null",
  "comparisonType": "most|least|compare หรือ null",
  "normalizedQuery": "คำถามที่ปรับให้ Flask เข้าใจง่าย",
  "requiresMultiQuery": true/false
}

กรณี detail/search (ถามเฉพาะโรงเรียน):
- "ขอรายละเอียดโรงเรียนบำรุงอิสลาม" → intent=detail, level=school, school_name=บำรุงอิสลาม, normalizedQuery=ข้อมูลโรงเรียนบำรุงอิสลาม
- "โรงเรียนวัดบ้านไร่อยู่ที่ไหน" → intent=detail, level=school, school_name=วัดบ้านไร่, normalizedQuery=ที่ตั้งโรงเรียนวัดบ้านไร่
- "หาโรงเรียนอนุบาลสตูล" → intent=search, level=school, school_name=อนุบาลสตูล, normalizedQuery=ค้นหาโรงเรียนอนุบาลสตูล
- "เบอร์ติดต่อโรงเรียนอัสสัมชัญ" → intent=detail, level=school, school_name=อัสสัมชัญ, normalizedQuery=เบอร์โทรโรงเรียนอัสสัมชัญ

กรณี count/list/ranking:
- "ภาคใต้มีโรงเรียนมากที่สุดจังหวัดไหน" → intent=ranking, level=province, region=ภาคใต้, comparisonType=most, requiresMultiQuery=true
- "อำเภอเมืองปัตตานีตำบลไหนมีโรงเรียนเยอะสุด" → intent=ranking, level=subdistrict, province=ปัตตานี, district=เมืองปัตตานี, comparisonType=most
- "จังหวัดปัตตานีมีกี่โรงเรียน" → intent=count, level=province, province=ปัตตานี, requiresMultiQuery=false
- "รายชื่อโรงเรียนในจังหวัดยะลา" → intent=list, level=province, province=ยะลา`;

    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${groqKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: [{ role: 'user', content: prompt }],
        model: 'llama-3.3-70b-versatile',
        temperature: 0.1,
        max_tokens: 500
      })
    });

    if (!response.ok) {
      console.warn('[AI Layer 1] Groq API error:', response.status);
      return null;
    }

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content || '';

    // Extract JSON from response
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]) as ParsedQuery;
      console.log('[AI Layer 1] Parsed:', parsed);
      return parsed;
    }

    return null;
  } catch (error) {
    console.warn('[AI Layer 1] Error:', error);
    return null;
  }
};

// ============================================================================
// AI LAYER: RESPONSE SUMMARIZER (Step 2 - After Flask API)
// ============================================================================

/**
 * AI Response Summarizer - แปลงข้อมูลดิบ → คำตอบสไตล์ "น้อง DO"
 */
const aiResponseSummarizer = async (
  originalQuestion: string,
  rawData: string,
  groqKey: string,
  parsedQuery?: ParsedQuery | null,
  conversationHistory?: ChatHistoryItem[]
): Promise<string | null> => {
  try {
    console.log('[AI Layer 2] Summarizing response with น้อง DO style...');

    const intent = parsedQuery?.intent || 'general';
    const comparisonType = parsedQuery?.comparisonType;

    let formatGuide = '';
    if (intent === 'ranking' && comparisonType === 'most') {
      formatGuide = `
• เน้นอันดับ 1 ด้วย **ตัวหนา** และ 🏆
• บอก Top 3 รองลงมา
• ใส่ตัวเลขเป็น **ตัวหนา**`;
    } else if (intent === 'compare') {
      formatGuide = `
• เปรียบเทียบตัวเลขชัดเจน
• สรุปว่าที่ไหนมากกว่า/น้อยกว่า
• ใช้ emoji 📊 หรือ 🔍`;
    } else {
      formatGuide = `
• สรุปข้อมูลเป็นข้อๆ
• ใช้ • bullet ทุกข้อ (ห้ามใช้ตัวเลข 1. 2. 3.)
• ใช้ตัวหนาเน้นจำนวน`;
    }


    const prompt = `คุณคือ "น้อง DO" (น้องดีโอ) ผู้ช่วย AI **ผู้ชาย** ของกระทรวงศึกษาธิการ

**บุคลิกของคุณ:**
- เป็นกันเอง สุภาพ แต่เป็นมืออาชีพ
- **คุณเป็นผู้ชาย** → ลงท้ายด้วย "ครับ" หรือ "นะครับ" เท่านั้น
- **ห้ามใช้ "ค่ะ" หรือ "คะ" เด็ดขาด!** (เพราะเป็นภาษาผู้หญิง)
- ใช้ emoji อย่างเหมาะสม 😊
- **ฉลาดและช่วยเหลือ** - ไม่ปฏิเสธผู้ใช้ด้วยคำว่า "ไม่พบข้อมูล" แบบเฉยๆ

${conversationHistory && conversationHistory.length > 0 ? `**ประวัติการสนทนาก่อนหน้า (บริบท):**
${conversationHistory.slice(-4).map(h => `${h.role === 'user' ? 'ผู้ใช้' : 'AI'}: ${h.parts?.[0]?.text?.substring(0, 200) || ''}`).join('\n')}

` : ''}**คำถามปัจจุบัน:** "${originalQuestion}"

**ข้อมูลที่ได้จากระบบ:**
${rawData}

**หน้าที่ของคุณ:** 
- ถ้าคำถามปัจจุบันเป็น follow-up (เช่น "แล้ว..." หรือ "อื่นๆละ" หรือ สรรพนามที่อ้างอิงบริบทก่อน) ให้ใช้ประวัติการสนทนาเพื่อเข้าใจบริบท
- สรุปข้อมูลข้างต้นเป็นคำตอบที่สวยงาม ธรรมชาติ เหมือนคนตอบจริงๆ

**รูปแบบการตอบ:**
${formatGuide}

**กฎสำคัญที่สุด:**
- ห้าม Hallucinate หรือแต่งเติมตัวเลขเด็ดขาด! ยึดตาม **ข้อมูลที่ได้จากระบบ** เท่านั้น
- ห้ามขยายคำย่อถ้าไม่แน่ใจ (เช่น ห้ามแปลง สช. เป็น สพฐ. หรืออื่นๆ) ให้ใช้คำตามต้นฉบับ
- ห้ามขึ้นต้นด้วย "📊 จำนวนโรงเรียน..." (อ่านแข็งเกินไป)
- ห้ามใช้รูปแบบ "รายละเอียดตามสังกัด:" แบบเดิม
- ให้ตอบแบบเป็นกันเอง เช่น "สำหรับคำถามนี้ครับ..."
- ใส่ข้อมูลครบถ้วน แต่อ่านง่าย

**✨ กฎสำคัญ - ทำให้คำตอบน่าสนใจ:**
- ห้ามตอบแห้งๆ แค่ list ข้อมูล! ต้องเสริม **insights** หรือ **ข้อสังเกตที่น่าสนใจ**
- เพิ่มข้อมูลเชิงลึก เช่น:
  - "น่าสนใจว่า **สพฐ.** มีโรงเรียนมากถึง **55%** ของทั้งประเทศเลยครับ! 🏆"
  - "เห็นได้ว่า **กรมส่งเสริมการปกครองท้องถิ่น** มีบทบาทสำคัญในระดับท้องถิ่น"
  - "Top 3 นี้ครอบคลุม **กว่า 90%** ของโรงเรียนทั้งหมดเลยนะครับ!"
- แนะนำคำถามติดตามที่น่าสนใจ เช่น: "สนใจดู**จังหวัดไหนมีโรงเรียนมากที่สุด**ไหมครับ?"
- ปิดท้ายด้วยข้อแนะนำหรือ "มีอะไรสอบถามเพิ่มเติมได้นะครับ 😊"

**กฎสำคัญ - เมื่อไม่พบข้อมูลตรงตามเงื่อนไข:**
- ห้ามตอบแค่ "ไม่พบข้อมูล" แล้วจบ!
- ให้แนะนำข้อมูลที่ใกล้เคียงที่สุดแทน เช่น:
  - ถ้าถามหา "น้อยกว่า 40" แต่ไม่มี → บอกว่า "ไม่มีที่น้อยกว่า 40 แต่ที่น้อยที่สุดคือ..."
  - ถ้าถามหา "มากกว่า 1000" แต่ไม่มี → บอกว่า "ไม่มีที่มากกว่า 1000 แต่ที่มากที่สุดคือ..."
- แนะนำให้ผู้ใช้ปรับคำถามหรือลองเงื่อนไขอื่น

ตัวอย่างโทนการตอบ:
"สำหรับอำเภอเมืองปัตตานีครับ **ตำบลบานา** มีโรงเรียนมากที่สุด 🏆 รวม **15** แห่ง

• สพฐ.: **10** แห่ง
• เอกชน: **3** แห่ง  
• อปท.: **2** แห่ง

มีอะไรสอบถามเพิ่มเติมได้นะครับ 😊"

ตัวอย่างเมื่อไม่พบข้อมูลตรง:
"สำหรับจังหวัดสตูลครับ ไม่มีอำเภอที่มีโรงเรียนน้อยกว่า 40 แห่งนะครับ 🔍

แต่ผมมีข้อมูลที่ใกล้เคียงให้ครับ:
• **อำเภอมะนัง** มีโรงเรียนน้**ยที่สุด** เพียง **48 แห่ง**
• รองลงมาคือ ควนโดน **66 แห่ง**

💡 ลองถามว่า 'อำเภอไหนมีโรงเรียนน้อยที่สุด' หรือ 'น้อยกว่า 50' ดูนะครับ 😊"`;

    // ✨ Extract chart/map data before sending to LLM (preserve widgets!)
    const chartMatch = rawData.match(/<chart>([\s\S]*?)<\/chart>/);
    const mapMatch = rawData.match(/<map>([\s\S]*?)<\/map>/);
    const extractedChart = chartMatch ? chartMatch[0] : '';
    const extractedMap = mapMatch ? mapMatch[0] : '';

    // Remove chart/map from text before sending to LLM (LLM shouldn't modify JSON)
    const textOnlyData = rawData
      .replace(/<chart>[\s\S]*?<\/chart>/g, '')
      .replace(/<map>[\s\S]*?<\/map>/g, '')
      .trim();

    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${groqKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: [{ role: 'user', content: prompt.replace(rawData, textOnlyData) }],
        model: 'llama-3.3-70b-versatile',
        temperature: 0.8, // Slightly higher for more creative responses
        max_tokens: 1500  // More tokens for richer responses
      })
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      console.error('[AI Layer 2] ❌ Groq API error:', response.status, errorText);
      return null;
    }

    const data = await response.json();
    let content = data.choices?.[0]?.message?.content || '';

    if (!content) {
      console.warn('[AI Layer 2] ⚠️ Empty response from Groq');
      return null;
    }

    // ✨ Re-attach chart/map data at the end (preserve widgets!)
    if (extractedChart) {
      content += '\n\n' + extractedChart;
      console.log('[AI Layer 2] 📊 Chart data preserved and re-attached');
    }
    if (extractedMap) {
      content += '\n\n' + extractedMap;
      console.log('[AI Layer 2] 🗺️ Map data preserved and re-attached');
    }

    console.log('[AI Layer 2] ✅ Summarized successfully, length:', content.length);
    return sanitizeResponseText(content);
  } catch (error: any) {
    console.error('[AI Layer 2] ❌ Error:', error.message || error);
    return null;
  }
};

// ============================================================================
// UNIFIED CHAT LOGIC (Failover)
// ============================================================================

export interface ChatHistoryItem {
  role: string;
  parts: { text: string }[];
}

// Reset session helper
export const resetChatSession = () => {
  chatSession = null;
};

export const startChat = async (systemInstruction: string, category: string = 'general', history: ChatHistoryItem[] = []) => {
  initializeGemini(category);
  // Gemini session only created if needed, logic handled in sendMessageStream
  return true;
};

// Rotate Key Helper 
export const rotateKey = (category: string, provider: 'gemini' | 'groq' = 'gemini'): boolean => {
  const catKey = (category.toLowerCase() === 'school' ? 'school' :
    category.toLowerCase() === 'student' ? 'student' : 'general') as keyof typeof currentConfig.apiKeys;

  const queue = provider === 'groq' ? activeGroqQueues[catKey] : activeKeyQueues[catKey];

  if (!queue || queue.length <= 1) {
    if (provider === 'groq') {
      console.warn(`[Groq] Rotation failed. No spare keys.`);
      return false;
    }
    console.warn(`[Gemini] Rotation failed. No spare keys.`);
    return false;
  }

  // Rotation Logic
  const failedKey = queue.shift();
  if (failedKey) queue.push(failedKey);

  saveKeyQueue(catKey, queue, provider);

  // Re-init
  initializeGemini(category, true);
  console.log(`[${provider.toUpperCase()}] Key Rotated.`);
  return true;
};

// RAG Debug Info type
interface RAGRetrievalResult {
  context: string;
  source: 'pinecone' | 'legacy_rag' | 'ai_only';
  contextPreview?: string;
  matchCount?: number;
  retrievalTimeMs?: number;
  embeddingModel?: string;
}

// Verify RAG (Upgraded with Native Pinecone Support + Debug Info)
const retrieveRAGContext = async (query: string, category: string): Promise<RAGRetrievalResult> => {
  const startTime = Date.now();
  const catKey = (category.toLowerCase() === 'school' ? 'school' :
    category.toLowerCase() === 'student' ? 'student' : 'general') as keyof typeof currentConfig.apiKeys;

  const ragConfig = currentConfig.apiKeys?.[catKey];

  // DEBUG: Log RAG configuration
  console.log('[RAG DEBUG] Category:', catKey);
  console.log('[RAG DEBUG] RAG Config exists:', !!ragConfig);
  console.log('[RAG DEBUG] Pinecone API Key exists:', !!ragConfig?.pineconeApiKey);
  console.log('[RAG DEBUG] Pinecone Host:', ragConfig?.pineconeHost);
  console.log('[RAG DEBUG] Pinecone Index:', ragConfig?.pineconeIndex);
  console.log('[RAG DEBUG] Embedding Key exists:', !!ragConfig?.embeddingApiKey);

  if (ragConfig?.pineconeApiKey && ragConfig?.pineconeHost) {
    try {
      console.log('[RAG] Using native Pinecone connection...');
      const { getPineconeContext } = await import('./pineconeService');
      const embeddingKey = ragConfig.embeddingApiKey || activeKeyQueues[catKey]?.[0];

      if (!embeddingKey) {
        console.warn('[RAG] No embedding key available!');
        return { context: '', source: 'ai_only' };
      }

      console.log('[RAG] Querying Pinecone with:', query.substring(0, 50) + '...');
      const context = await getPineconeContext(query, {
        pineconeApiKey: ragConfig.pineconeApiKey,
        pineconeHost: ragConfig.pineconeHost,
        pineconeIndex: ragConfig.pineconeIndex || '',
        pineconeNamespace: ragConfig.pineconeNamespace || '',
        ragTopK: ragConfig.ragTopK || 5
      }, embeddingKey);

      const retrievalTime = Date.now() - startTime;
      const matchCount = context ? (context.match(/【.*?】/g) || []).length : 0;

      console.log('[RAG] Context retrieved, length:', context?.length || 0, 'matches:', matchCount);

      return {
        context,
        source: context ? 'pinecone' : 'ai_only',
        contextPreview: context ? context.substring(0, 200) + '...' : undefined,
        matchCount,
        retrievalTimeMs: retrievalTime,
        embeddingModel: 'text-embedding-004'
      };
    } catch (error) {
      console.error('[RAG ERROR]', error);
      return { context: '', source: 'ai_only' };
    }
  } else {
    console.log('[RAG] Pinecone not configured, checking legacy RAG...');
  }

  const endpoint = ragConfig?.ragEndpoint;
  const apiKey = ragConfig?.ragApiKey;

  if (!endpoint) return { context: '', source: 'ai_only' };

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    const response = await fetch(`${endpoint}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {})
      },
      body: JSON.stringify({
        query: query,
        collection: ragConfig.ragCollection || 'moe_data',
        top_k: ragConfig.ragTopK || 5
      }),
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (!response.ok) return { context: '', source: 'ai_only' };

    const data = await response.json();
    if (data.results && Array.isArray(data.results)) {
      const context = data.results.map((r: any) => r.text || r.content).join('\n\n');
      return {
        context,
        source: context ? 'legacy_rag' : 'ai_only',
        contextPreview: context ? context.substring(0, 200) + '...' : undefined,
        matchCount: data.results.length,
        retrievalTimeMs: Date.now() - startTime
      };
    }
    return { context: '', source: 'ai_only' };
  } catch (error) {
    return { context: '', source: 'ai_only' };
  }
};

export interface ChatResponse {
  text: string;
  ragDebugInfo?: {
    source: 'pinecone' | 'legacy_rag' | 'ai_only';
    contextPreview?: string;
    matchCount?: number;
    retrievalTimeMs?: number;
    embeddingModel?: string;
  };
}

let lastRagDebugInfo: ChatResponse['ragDebugInfo'] = undefined;
export const getLastRagDebugInfo = () => lastRagDebugInfo;

// ============================================================================
// AUTO CATEGORY DETECTION
// ============================================================================

/**
 * Automatically detects the appropriate category based on message keywords
 * @param message - User's input message
 * @returns Detected category: 'school', 'student', or 'general'
 */
export const detectCategory = (message: string): 'general' | 'school' | 'student' => {
  const lower = message.toLowerCase();

  // Student-related keywords (สถิตินักเรียน)
  const studentKeywords = [
    'นักเรียน', 'เด็ก', 'สถิติ', 'ลงทะเบียน', 'จำนวนเด็ก',
    'นักศึกษา', 'ผู้เรียน', 'เรียน', 'นร', 'student'
  ];

  // School-related keywords (ข้อมูลโรงเรียน)
  const schoolKeywords = [
    'โรงเรียน', 'สถานศึกษา', 'แห่ง', 'สังกัด', 'หน่วยงาน',
    'สช', 'สพฐ', 'อปท', 'โรง', 'ร.ร.', 'รร.', 'school',
    'กรม', 'สำนักงาน', 'จังหวัด', 'อำเภอ', 'ตำบล', 'เขต',
    'มากที่สุด', 'น้อยที่สุด', 'กี่แห่ง', 'กี่โรง', 'ทุกสังกัด'
  ];

  // Check for student keywords first (more specific)
  if (studentKeywords.some(kw => lower.includes(kw))) {
    console.log(`🔍 [AutoDetect] Detected category: student (keyword match)`);
    return 'student';
  }

  // Check for school keywords
  if (schoolKeywords.some(kw => lower.includes(kw))) {
    console.log(`🔍 [AutoDetect] Detected category: school (keyword match)`);
    return 'school';
  }

  // Default to general
  console.log(`🔍 [AutoDetect] Detected category: general (default)`);
  return 'general';
};

// ============================================================================
// ABORT CONTROLLER FOR STOPPING AI GENERATION
// ============================================================================
let currentAbortController: AbortController | null = null;

export const abortCurrentStream = () => {
  if (currentAbortController) {
    console.log('[AI] 🛑 Aborting current stream...');
    currentAbortController.abort();
    currentAbortController = null;
    return true;
  }
  return false;
};

export const sendMessageStream = async (
  message: string,
  category: string,
  imageData: string | null,
  systemInstruction: string,
  onChunk: (text: string) => void,
  history: ChatHistoryItem[] = [],
  onDebugInfo?: (info: ChatResponse['ragDebugInfo']) => void
) => {
  // Create new abort controller for this request
  currentAbortController = new AbortController();
  const signal = currentAbortController.signal;

  // Helper function to check if aborted
  const checkAborted = () => {
    if (signal.aborted) {
      console.log('[AI] 🛑 Request was aborted');
      throw new Error('ABORTED');
    }
  };
  // Auto-detect category if 'auto' is passed
  const effectiveCategory = category.toLowerCase() === 'auto'
    ? detectCategory(message)
    : category.toLowerCase();

  initializeGemini(effectiveCategory);

  const catKey = (effectiveCategory === 'school' ? 'school' :
    effectiveCategory === 'student' ? 'student' : 'general') as 'general' | 'school' | 'student';

  // Get current time for context
  const currentTime = new Date().toLocaleString('th-TH', {
    timeZone: 'Asia/Bangkok',
    dateStyle: 'full',
    timeStyle: 'short'
  });

  // ============================================================================
  // FLASK API ROUTING (for school/student categories) - WITH AI LAYER
  // ============================================================================
  const flaskConfig = currentConfig.apiKeys?.[catKey];
  const shouldUseFlaskApi = flaskConfig?.flaskApiEnabled &&
    flaskConfig?.flaskApiUrl &&
    (catKey === 'school' || catKey === 'student');

  if (shouldUseFlaskApi) {
    console.log(`[Flask API] Attempting for category: ${catKey}`);

    // Get Groq key for AI Layer
    const groqQueue = activeGroqQueues[catKey] || [];
    const groqKey = groqQueue[0] || '';

    try {
      const ChatbotAPI = (await import('./chatbot-api.js')).default;
      const api = new ChatbotAPI(flaskConfig.flaskApiUrl, flaskConfig.flaskApiKey);

      // ============================================
      // AI LAYER 1: Query Normalization
      // ============================================
      let parsedQuery: ParsedQuery | null = null;
      let queryToSend = message;

      if (groqKey) {
        // Note: Don't show analyzing message here - it creates duplicate
        console.log('[AI Layer 1] Starting query normalization...');
        parsedQuery = await aiQueryNormalizer(message, groqKey);

        if (parsedQuery) {
          console.log('[AI Layer 1] ✅ Intent:', parsedQuery.intent, 'Level:', parsedQuery.level);

          // Use normalized query for Flask if available
          if (parsedQuery.normalizedQuery && parsedQuery.normalizedQuery !== message) {
            queryToSend = parsedQuery.normalizedQuery;
            console.log('[AI Layer 1] Using normalized query:', queryToSend);
          }
        } else {
          console.log('[AI Layer 1] ⚠️ Normalization returned null, using original query');
        }
      }

      // Convert history to Flask format - ✨ Enhanced: 10 messages for better context
      const flaskHistory = history.slice(-10).map(h => ({
        role: (h.role === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
        content: h.parts.map((p: any) => p.text || '').join('')
      }));

      const controller = new AbortController();
      const timeout = flaskConfig.flaskApiTimeout || 30000;
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      // Retry logic with exponential backoff
      let lastError = null;
      let flaskResponse: string | null = null;

      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          console.log(`[Flask API] Attempt ${attempt}/3...`);

          // Buffer chunks first, don't stream immediately
          let bufferedResponse = '';

          const result = await api.sendStream(queryToSend, {
            history: flaskHistory,
            collection_name: catKey === 'school' ? 'education_schools' : 'education_students',
            system_prompt: systemInstruction,
            saveHistory: false,
            session_id: `session_${catKey}_${Date.now().toString(36).slice(-6)}`,
            category: catKey,
            // Enhanced: Pass parsed query metadata for better backend routing
            intent: parsedQuery?.intent || null,
            school_name: parsedQuery?.school_name || null,
            level: parsedQuery?.level || null
          }, (chunk) => {
            // Buffer chunks instead of streaming immediately
            bufferedResponse += chunk;
          });

          clearTimeout(timeoutId);

          if (result.success && result.response) {
            console.log(`[Flask API] ✅ Success!`);

            // Check if response has REAL data (success patterns)
            const successPatterns = [
              'แห่งครับ',
              'ตัวอย่างโรงเรียน',
              'สรุปข้อมูล',
              'โรงเรียนทั้งหมด',
              'มีโรงเรียน',
              'รายชื่อโรงเรียน'
            ];

            const hasRealData = successPatterns.some(pattern =>
              result.response.includes(pattern)
            );

            // Only check for "not found" if there's NO real data
            if (!hasRealData) {
              const notFoundPatterns = [
                'ไม่พบข้อมูล',
                'ไม่พบโรงเรียน',
                'ไม่มีข้อมูล',
                'ลองค้นหาด้วยชื่ออื่น',
                'ไม่พบ',
                'ไม่สามารถค้นหา'
              ];

              const isNotFoundResponse = notFoundPatterns.some(pattern =>
                result.response.includes(pattern)
              );

              if (isNotFoundResponse) {
                console.log(`[Flask API] ⚠️ Not found response detected, falling back to Pinecone RAG...`);
                // Don't return - let it fall through to Pinecone RAG below
              } else {
                // Stream the buffered response - character by character like ChatGPT
                if (onChunk) {
                  const chars = result.response.split('');
                  let buffer = '';
                  for (let i = 0; i < chars.length; i++) {
                    checkAborted(); // Check if user pressed Stop
                    buffer += chars[i];
                    if (i % 3 === 0 || i === chars.length - 1) {
                      onChunk(buffer);
                      buffer = '';
                      await new Promise(r => setTimeout(r, 8));
                    }
                  }
                  if (buffer) onChunk(buffer);
                }
                return { text: result.response }; // Return immediately, skipping Layer 2
              }
            } else {
              console.log(`[Flask API] ✅ Real data detected, sending to AI Layer 2 for enrichment`);
              console.log(`[Flask API] Response preview:`, result.response.substring(0, 300));

              // ✨ Instead of returning immediately, send to AI Layer 2 for richer context
              flaskResponse = result.response;
              // Don't return - let it fall through to AI Layer 2 below
            }
          }

          lastError = result.error || 'Unknown error';
        } catch (retryError: any) {
          lastError = retryError.message;
          if (attempt < 3) {
            await new Promise(r => setTimeout(r, 1000 * attempt)); // Exponential backoff
          }
        }
      }

      clearTimeout(timeoutId);

      // ============================================
      // AI LAYER 2: Response Summarization
      // ============================================
      if (flaskResponse) {
        let finalResponse = flaskResponse;
        let usedAiFormatting = false;

        // Always use AI to format response in "น้อง DO" style
        if (groqKey) {
          console.log('[AI Layer 2] 🚀 Starting response formatting...');
          console.log('[AI Layer 2] groqKey available:', !!groqKey);
          console.log('[AI Layer 2] flaskResponse length:', flaskResponse.length);

          const summarized = await aiResponseSummarizer(
            message,
            flaskResponse,
            groqKey,
            parsedQuery,
            history  // Pass conversation history for context
          );

          if (summarized) {
            finalResponse = summarized;
            usedAiFormatting = true;
            console.log('[AI Layer 2] ✅ AI formatting successful!');
          } else {
            console.warn('[AI Layer 2] ⚠️ AI formatting returned null, using original Flask response');
          }
        } else {
          console.warn('[AI Layer 2] ⚠️ No groqKey available, using original Flask response');
        }

        console.log('[AI Layer 2] Final response preview:', finalResponse.substring(0, 100) + '...');
        console.log('[AI Layer 2] Used AI formatting:', usedAiFormatting);

        // Stream the final response - smooth typing effect like ChatGPT
        const chars = finalResponse.split('');
        let buffer = '';
        for (let i = 0; i < chars.length; i++) {
          buffer += chars[i];
          // Emit every 2 characters for smooth visible typing
          if (i % 2 === 0 || i === chars.length - 1) {
            onChunk(buffer);
            buffer = '';
            await new Promise(r => setTimeout(r, 12)); // Visible but not too slow
          }
        }
        if (buffer) onChunk(buffer); // Flush remaining

        // Set debug info
        lastRagDebugInfo = {
          source: 'pinecone',
          matchCount: 1,
          retrievalTimeMs: Date.now(),
          contextPreview: `AI-Enhanced Flask API Response (Intent: ${parsedQuery?.intent || 'unknown'})`
        };
        if (onDebugInfo) onDebugInfo(lastRagDebugInfo);

        return { text: finalResponse, ragDebugInfo: lastRagDebugInfo };
      }

      console.warn(`[Flask API] ❌ Failed after 3 attempts: ${lastError}`);
      console.log(`[Flask API] 🔄 Falling back to Pinecone RAG...`);
      // Fall through to RAG section below
    } catch (flaskError: any) {
      console.warn(`[Flask API] ❌ Error: ${flaskError.message}`);
      console.log(`[Flask API] 🔄 Error occurred, falling back to Pinecone RAG...`);
      // Fall through to RAG section below
    }
  }

  // ============================================================================
  // SMALL TALK DETECTOR - Skip RAG for casual conversations
  // ============================================================================
  const smallTalkPatterns = [
    'สวัสดี', 'หวัดดี', 'ดีครับ', 'ดีค่ะ', 'สบายดี', 'เป็นไง',
    'หนาว', 'ร้อน', 'กินข้าว', 'อยู่ไหน', 'ทำอะไร', 'อารมณ์',
    'ขอบคุณ', 'ขอบใจ', 'บาย', 'ลาก่อน', 'กู๊ดไนท์', 'นอนหลับ',
    'ชื่ออะไร', 'เป็นใคร', 'อายุเท่าไหร่', 'เกิดวัน', 'รักไหม',
    'ไง', 'ว่าไง', 'ดีจัง', 'เหนื่อย', 'ง่วง', 'หิว', 'โอเค'
  ];

  const isSmallTalk = message.length < 30 && smallTalkPatterns.some(p => message.toLowerCase().includes(p));

  if (isSmallTalk) {
    console.log('[Chat] Small talk detected, skipping RAG');
    lastRagDebugInfo = { source: 'small_talk_skip', matchCount: 0, retrievalTimeMs: 0 };
    if (onDebugInfo) onDebugInfo(lastRagDebugInfo);
  }

  // ============================================================================
  // RAG Context Retrieval (for general category or Flask fallback) - Skip for small talk
  // ============================================================================
  let contextBlock = '';
  if (!isSmallTalk && !imageData && currentConfig.rag.enabled) {
    try {
      const ragResult = await retrieveRAGContext(message, category);
      if (ragResult.context) {
        // Add explicit instruction for detailed response
        contextBlock = `**ข้อมูลสำคัญจากคู่มือ/ระเบียบ (ต้องใช้ตอบ):**
${ragResult.context}
---
**คำสั่ง:** 
- ตอบละเอียด อย่างน้อย 5 ขั้นตอน
- ใช้ • bullet สำหรับทุกข้อ (ห้ามใช้ตัวเลข 1. 2. 3.)
- ใช้ตัวหนา **เน้นคำสำคัญ** เช่น **ชื่อเมนู** **ชื่อระบบ** **ปุ่มที่ต้องกด**
- ปิดท้ายด้วย **หมายเหตุ:** หรือข้อแนะนำ

`;
        lastRagDebugInfo = {
          source: ragResult.source,
          matchCount: ragResult.matchCount,
          retrievalTimeMs: ragResult.retrievalTimeMs,
          contextPreview: ragResult.contextPreview,
          embeddingModel: ragResult.embeddingModel
        };
        if (onDebugInfo) onDebugInfo(lastRagDebugInfo);
      }
    } catch (err) { console.warn('[RAG Error]', err); }
  } else {
    lastRagDebugInfo = { source: 'ai_only', matchCount: 0, retrievalTimeMs: 0 };
    if (onDebugInfo) onDebugInfo(lastRagDebugInfo);
  }

  // Simple System Instruction
  const effectiveSystemInstruction = `เวลาปัจจุบัน: ${currentTime}\n\n${systemInstruction}`;

  // User Message with optional context
  let finalMessage = message;

  // FORCED RECOMMENDATION LOGIC
  // If in 'general' mode but user asks about school/student, FORCE AI to recommend switching
  if (catKey === 'general') {
    const lowerMsg = message.toLowerCase();
    const needsSchoolRec = ['โรงเรียน', 'สถานศึกษา', 'สพฐ', 'สช', 'แห่ง'].some(kw => lowerMsg.includes(kw));
    const needsStudentRec = ['นักเรียน', 'สถิติ', 'จำนวนเด็ก', 'นักศึกษา'].some(kw => lowerMsg.includes(kw));

    if (needsSchoolRec || needsStudentRec) {
      finalMessage = `${message}\n\n[System Instruction: ตอบคำถามนี้ตามความรู้ที่มี แต่ตอนท้าย 'ต้อง' พิมพ์ข้อความแนะนำนี้ตามตัวอักษร: "\n\n💡 **คำแนะนำ:** หากต้องการค้นหารายชื่อโรงเรียนหรือสถิติเชิงลึก แนะนำให้เลือกโหมด **'ข้อมูลโรงเรียน 🏫'** หรือ **'สถิตินักเรียน 📊'** ที่เมนูด้านซ้ายจะได้ข้อมูลที่แม่นยำกว่าครับ"]`;
    }
  }

  const fullMessage = contextBlock ? `${contextBlock}${finalMessage}` : finalMessage;

  // Use last 6 messages for context
  const effectiveHistory = history.slice(-6);

  // 1. GROQ
  const groqQueue = activeGroqQueues[catKey] || [];
  console.log(`🔍 [Debug] Category: ${catKey}, Groq Queue Length: ${groqQueue.length}, Keys: ${groqQueue.map(k => k.substring(0, 8) + '...')}`);
  console.log(`🔍 [Debug] Current Config groqKeys:`, currentConfig.apiKeys?.[catKey]?.groqKeys?.length || 0);

  if (!imageData && groqQueue.length > 0) {
    let groqAttempts = 0;
    const MAX_GROQ_RETRIES = Math.max(2, groqQueue.length); // Try at least 2 or all available keys

    while (groqAttempts < MAX_GROQ_RETRIES) {
      const key = activeGroqQueues[catKey][0];
      if (!key) break;
      try {
        console.log(`[Groq] Attempting with key #${groqAttempts + 1}...`);
        await callGroqAPI([
          { role: 'system', content: effectiveSystemInstruction },
          ...effectiveHistory.map(h => ({
            role: h.role === 'model' ? 'assistant' : 'user',
            content: h.parts?.[0]?.text || ""
          })),
          { role: 'user', content: fullMessage }
        ], key, 'llama-3.3-70b-versatile', onChunk);
        console.log("✅ [Groq] Success!");
        return;
      } catch (e: any) {
        const errStr = e.message || JSON.stringify(e);
        const isRetriable = errStr.includes('429') ||
          errStr.includes('quota') ||
          errStr.includes('500') ||
          errStr.includes('503') ||
          errStr.includes('fetch failed') ||
          errStr.includes('timeout') ||
          errStr.includes('NetworkError');

        console.error(`❌[Groq] Error: ${errStr} (Retriable: ${isRetriable})`);

        if (isRetriable) {
          console.warn("⚠️ [Groq] Retriable error. Rotating key...");
          rotateKey(category, 'groq');
        } else {
          console.error("❌ [Groq] Non-retriable error. Stopping Groq attempts.");
          break;
        }
        groqAttempts++;
      }
    }
    console.warn("❌ [Groq] All attempts failed. Falling back to Gemini...");
  }

  // 2. GEMINI
  let geminiRetry = 0;
  const MAX_GEMINI_RETRIES = Math.max(2, activeKeyQueues[catKey].length);

  while (geminiRetry < MAX_GEMINI_RETRIES) {
    const key = activeKeyQueues[catKey][0];
    if (!key) break;
    try {
      if (!ai || currentApiKey !== key) {
        ai = new GoogleGenAI({ apiKey: key });
        currentApiKey = key;
      }

      console.log(`[Gemini] Probing / Starting with key #${geminiRetry + 1}...`);
      const modelName = detectedModelForChat || await getAvailableGeminiModel(key);

      const contents = [
        ...(history || []).map(h => ({ role: h.role === 'user' ? 'user' : 'model', parts: h.parts })),
        { role: 'user', parts: [{ text: fullMessage }] }
      ];

      try {
        // Use the correct method for @google/genai SDK
        const stream = await ai.models.generateContentStream({
          model: modelName,
          contents: contents as any,
          config: {
            systemInstruction: { parts: [{ text: effectiveSystemInstruction }] },
            generationConfig: {
              temperature: currentConfig.model.temperature,
              maxOutputTokens: 2048
            }
          }
        } as any);

        for await (const chunk of stream) {
          const text = chunk.text;
          if (text) onChunk(sanitizeResponseText(text));
        }
        console.log("✅ [Gemini] Success!");
        return;
      } catch (streamError: any) {
        const streamErrStr = streamError.message || JSON.stringify(streamError);
        console.warn(`⚠️[Gemini] Stream failed: ${streamErrStr}. Retrying with non - stream...`);

        // If it's a quota error, don't even try non-stream, just throw to rotate
        if (streamErrStr.includes('429') || streamErrStr.toLowerCase().includes('quota')) throw streamError;

        const result = await ai.models.generateContent({
          model: modelName,
          contents: contents as any,
          config: {
            systemInstruction: { parts: [{ text: effectiveSystemInstruction }] },
            generationConfig: {
              temperature: currentConfig.model.temperature,
              maxOutputTokens: 2048
            }
          }
        } as any);

        const text = result.text;
        if (text) {
          onChunk(sanitizeResponseText(text));
          console.log("✅ [Gemini] Success (Non-stream fallback)!");
          return;
        }
      }
    } catch (e: any) {
      const errStr = (e.message || "") + JSON.stringify(e);
      const isRetriable = errStr.includes('429') ||
        errStr.includes('quota') ||
        errStr.includes('500') ||
        errStr.includes('503') ||
        errStr.includes('fetch failed') ||
        errStr.includes('timeout') ||
        errStr.includes('OT_FOUND') || // Sometimes model probing fails temporarily
        errStr.includes('NetworkError');

      console.error(`❌[Gemini] Error: ${errStr} (Retriable: ${isRetriable})`);

      if (isRetriable) {
        console.warn("⚠️ [Gemini] Retriable error. Rotating key...");
        rotateKey(category, 'gemini');
        geminiRetry++;
        continue;
      }
      break;
    }
  }

  onChunk("😊 ขออภัยครับ ขณะนี้ระบบกำลังประมวลผลคำขอจำนวนมาก กรุณาลองใหม่อีกครั้งในอีกสักครู่นะครับ หรือลองถามคำถามอื่นได้เลยครับ");
};

export const optimizeQueue = async (category: string) => {
  return { success: true, message: "Queue Optimized" };
};

export const testGroqConnection = async (apiKey: string, category: string): Promise<{ success: boolean; message: string; errorType?: string; quotaInfo?: { remainingRequests?: number; remainingTokens?: number; resetTime?: string } }> => {
  if (!apiKey) return { success: false, message: 'กรุณาระบุ API Key' };
  try {
    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'llama-3.3-70b-versatile',
        messages: [{ role: 'user', content: 'Say OK' }],
        max_tokens: 3
      })
    });
    const remainingRequests = response.headers.get('x-ratelimit-remaining-requests');
    const remainingTokens = response.headers.get('x-ratelimit-remaining-tokens');
    const resetTime = response.headers.get('x-ratelimit-reset-requests');
    const quotaInfo = {
      remainingRequests: remainingRequests ? parseInt(remainingRequests) : undefined,
      remainingTokens: remainingTokens ? parseInt(remainingTokens) : undefined,
      resetTime: resetTime || undefined
    };

    if (response.ok) {
      return { success: true, message: `เชื่อมต่อสำเร็จ${remainingRequests ? ` (เหลือ ${remainingRequests} req)` : ''} `, quotaInfo };
    } else {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        message: errorData?.error?.message || `Error ${response.status} `,
        errorType: response.status === 429 ? 'quota_daily' : 'unknown',
        quotaInfo
      };
    }
  } catch (error: any) {
    return { success: false, message: error.message };
  }
};