import { GoogleGenAI } from '@google/genai';
import { ParsedQuery, ChatHistoryItem } from './types';

/**
 * Sanitizes AI response text to remove unwanted characters.
 * - Removes Chinese/Japanese/Korean characters
 * - Cleans up excessive whitespace
 * - Forces line breaks for numbered lists and bullet points
 */
export const sanitizeResponseText = (text: string): string => {
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

/**
 * AI Query Normalizer - แปลงคำถามธรรมชาติ → structured query
 * Uses Groq for fast processing
 */
export const aiQueryNormalizer = async (
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

/**
 * AI Response Summarizer - แปลงข้อมูลดิบ → คำตอบสไตล์ "น้อง DO"
 * มี Gemini fallback เมื่อ Groq ล้มเหลว
 */
export const aiResponseSummarizer = async (
  originalQuestion: string,
  rawData: string,
  groqKey: string,
  parsedQuery?: ParsedQuery | null,
  conversationHistory?: ChatHistoryItem[],
  effectiveGeminiKey?: string, getModel?: (apiKey: string) => Promise<string>
): Promise<string | null> => {
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


  const prompt = `คุณคือ "น้อง DO" ผู้ช่วย AI ด้านการศึกษาไทย (เป็นผู้ชาย ใช้ "ครับ")

${conversationHistory && conversationHistory.length > 0 ? `**บริบทก่อนหน้า:**
${conversationHistory.slice(-4).map(h => `${h.role === 'user' ? 'ผู้ใช้' : 'AI'}: ${h.parts?.[0]?.text?.substring(0, 200) || ''}`).join('\n')}

` : ''}**คำถาม:** "${originalQuestion}"

**ข้อมูลจริง:**
${rawData}

**คำย่อสังกัด (สำคัญมาก!):**
- สช = สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน (โรงเรียนเอกชน)
- สพฐ = สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน (โรงเรียนรัฐบาล)
- อปท = กรมส่งเสริมการปกครองท้องถิ่น
- สอศ = สำนักงานคณะกรรมการการอาชีวศึกษา
⚠️ **ห้ามสับสน สช กับ สพฐ!** (คนละสังกัดกัน)

**วิธีตอบ:**
- ตอบเหมือนคนคุยกัน ไม่ใช่หุ่นยนต์
- เข้าใจบริบท ถ้าถามต่อเนื่อง ให้เชื่อมโยง
- ใช้ภาษาหลากหลาย ไม่ซ้ำซาก
${formatGuide}

**โครงสร้างคำตอบที่ดี:**
1. ตอบคำถามหลักก่อน (ตัวเลขสำคัญ)
2. แสดงรายละเอียด (bullet points)
3. ให้ข้อสังเกตหรือ insight (ถ้ามี)
4. ปิดท้ายสั้นๆ

**กฎ Formatting (สำคัญ!):**
- ใช้ **ตัวหนา** สำหรับตัวเลขสำคัญ เช่น **2977 แห่ง**, **174 แห่ง**
- ใช้ bullet points (- หรือ •) สำหรับรายการ
- เน้นตัวเลขให้โดดเด่น

**กฎ:**
- ตัวเลขต้องมาจาก "ข้อมูลจริง" เท่านั้น ห้ามแต่งเอง
- ❌ ห้ามใช้คำซ้ำซาก: "สำหรับคำถามนี้ครับ", "น่าสนใจว่า", "สนใจดู...ไหมครับ"`;


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

  const promptWithTextOnly = prompt.replace(rawData, textOnlyData);

  // Helper to re-attach chart/map
  const attachWidgets = (content: string): string => {
    let result = content;
    if (extractedChart) {
      result += '\n\n' + extractedChart;
      console.log('[AI Layer 2] 📊 Chart data preserved and re-attached');
    }
    if (extractedMap) {
      result += '\n\n' + extractedMap;
      console.log('[AI Layer 2] 🗺️ Map data preserved and re-attached');
    }
    return result;
  };

  // ============================================
  // TRY 1: GROQ API (Primary - Fast)
  // ============================================
  if (groqKey) {
    try {
      console.log('[AI Layer 2] 🚀 Trying Groq API first...');

      const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${groqKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          messages: [{ role: 'user', content: promptWithTextOnly }],
          model: 'llama-3.3-70b-versatile',
          temperature: 0.8,
          max_tokens: 1500
        })
      });

      if (response.ok) {
        const data = await response.json();
        const content = data.choices?.[0]?.message?.content || '';

        if (content) {
          console.log('[AI Layer 2] ✅ Groq success!');
          return sanitizeResponseText(attachWidgets(content));
        }
      } else {
        const errorText = await response.text().catch(() => '');
        console.warn('[AI Layer 2] ⚠️ Groq API error:', response.status, errorText);
      }
    } catch (groqError: any) {
      console.warn('[AI Layer 2] ⚠️ Groq failed:', groqError.message);
    }
  }

  // ============================================
  // TRY 2: GEMINI API (Fallback)
  // ============================================
  // Get Gemini key from activeKeyQueues if not provided
  

  if (effectiveGeminiKey) {
    try {
      console.log('[AI Layer 2] 🔄 Falling back to Gemini API...');

      const geminiAi = new GoogleGenAI({ apiKey: effectiveGeminiKey });
      const modelName = await getModel!(effectiveGeminiKey);

      const result = await geminiAi.models.generateContent({
        model: modelName,
        contents: [{ role: 'user', parts: [{ text: promptWithTextOnly }] }],
        config: {
          generationConfig: {
            temperature: 0.8,
            maxOutputTokens: 1500
          }
        }
      } as any);

      const content = result.text || '';

      if (content) {
        console.log('[AI Layer 2] ✅ Gemini fallback success!');
        return sanitizeResponseText(attachWidgets(content));
      }
    } catch (geminiError: any) {
      console.error('[AI Layer 2] ❌ Gemini fallback also failed:', geminiError.message);
    }
  } else {
    console.warn('[AI Layer 2] ⚠️ No Gemini key available for fallback');
  }

  // ============================================
  // BOTH FAILED - Return null (will use fallbackFormatResponse)
  // ============================================
  console.error('[AI Layer 2] ❌ Both Groq and Gemini failed');
  return null;
};

/**
 * Fallback formatter - แปลง JSON/raw response เป็นข้อความที่อ่านได้
 * ใช้เมื่อ aiResponseSummarizer ล้มเหลว
 */
export const fallbackFormatResponse = (rawData: string, originalQuestion: string): string => {
  try {
    // Try to parse as JSON
    let data: any;

    // Check if it's wrapped in ```json blocks
    const jsonMatch = rawData.match(/```json\s*([\s\S]*?)\s*```/);
    if (jsonMatch) {
      data = JSON.parse(jsonMatch[1]);
    } else {
      // Try direct JSON parse
      try {
        data = JSON.parse(rawData);
      } catch {
        // Not JSON, return cleaned up text
        return rawData
          .replace(/```json/g, '')
          .replace(/```/g, '')
          .trim();
      }
    }

    // Format the parsed data
    let response = '';

    // Handle school_counts structure
    if (data.school_counts) {
      const schoolCounts = data.school_counts;
      const schools = Object.keys(schoolCounts);

      if (schools.length > 0) {
        response += `📊 **สรุปข้อมูลจากการค้นหา:**\n\n`;

        let totalStudents = 0;
        schools.forEach((school, index) => {
          const info = schoolCounts[school];
          const total = info.total || 0;
          totalStudents += total;

          response += `**${index + 1}. ${school}**\n`;
          response += `• จำนวนรวม: **${total.toLocaleString()}** คน\n`;

          if (info.province) response += `• จังหวัด: ${info.province}\n`;
          if (info.district) response += `• เขต/อำเภอ: ${info.district}\n`;
          if (info.grade) response += `• ระดับชั้น: ${info.grade}\n`;
          if (info.gender) response += `• เพศ: ${info.gender}\n`;

          response += '\n';
        });

        if (data.total_students) {
          response += `📈 **รวมทั้งหมด:** ${data.total_students.toLocaleString()} คน ใน ${data.num_schools || schools.length} โรงเรียนครับ`;
        }
      }
    }
    // Handle other data structures
    else if (data.total || data.count) {
      response += `📊 **ผลการค้นหา:**\n\n`;
      response += `• จำนวนรวม: **${(data.total || data.count).toLocaleString()}** รายการครับ\n`;

      if (data.province) response += `• จังหวัด: ${data.province}\n`;
      if (data.district) response += `• อำเภอ: ${data.district}\n`;
    }
    // Handle array response
    else if (Array.isArray(data)) {
      response += `📋 **พบข้อมูล ${data.length} รายการ:**\n\n`;
      data.slice(0, 10).forEach((item, i) => {
        const name = item.name || item.school_name || item.title || `รายการ ${i + 1}`;
        response += `• ${name}\n`;
      });
      if (data.length > 10) {
        response += `\n... และอีก ${data.length - 10} รายการครับ`;
      }
    }
    // Generic object
    else {
      response += `📊 **ข้อมูลที่พบ:**\n\n`;
      Object.entries(data).slice(0, 10).forEach(([key, value]) => {
        if (typeof value === 'object') {
          response += `• **${key}**: (มีข้อมูลย่อย)\n`;
        } else {
          response += `• **${key}**: ${value}\n`;
        }
      });
    }

    return response || rawData;
  } catch (error) {
    console.error('[Fallback Formatter] Error:', error);
    // Return a user-friendly message if all else fails
    return `ได้รับข้อมูลจากระบบแล้วครับ แต่รูปแบบอาจไม่ตรงที่คาดหวัง กรุณาลองถามใหม่อีกครั้งนะครับ 🙏`;
  }
};
