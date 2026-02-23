export const cleanupMarkdown = (text: string): string => {
    if (!text) return '';

    let cleaned = text;

    // Fix: "มีดังนี้: * item" -> "มีดังนี้:\n\n- item"
    cleaned = cleaned.replace(/:\s*\*\s+/g, ':\n\n- ');

    // Fix: Standalone "*" at start of line -> "-"
    cleaned = cleaned.replace(/^\*\s+/gm, '- ');

    // Fix: "• " bullet points (already correct but ensure consistency)
    cleaned = cleaned.replace(/•\s+/g, '- ');

    // Fix: Multiple consecutive bullet points need newlines between
    cleaned = cleaned.replace(/(-\s.+?)(\s+-\s)/g, '$1\n$2');

    return cleaned;
};

// Generate thinking status based on user's question
export const generateThinkingStatus = (question: string): string[] => {
    const lower = question?.toLowerCase() || '';
    const statuses: string[] = [];

    // School-related keywords
    if (lower.includes('โรงเรียน') || lower.includes('สถานศึกษา') || lower.includes('ร.ร.')) {
        statuses.push('น้องดีโอกำลังค้นหาข้อมูลโรงเรียนครับ...');
    }

    // Location keywords
    if (lower.includes('จังหวัด') || lower.includes('อำเภอ') || lower.includes('ตำบล') || lower.includes('เขต')) {
        statuses.push('น้องดีโอกำลังค้นหาข้อมูลพื้นที่ครับ...');
    }

    // Statistics keywords
    if (lower.includes('สถิติ') || lower.includes('จำนวน') || lower.includes('กี่')) {
        statuses.push('น้องดีโอกำลังประมวลผลข้อมูลครับ...');
    }

    // Comparison keywords
    if (lower.includes('เปรียบเทียบ') || lower.includes('มากที่สุด') || lower.includes('น้อยที่สุด')) {
        statuses.push('น้องดีโอกำลังเปรียบเทียบข้อมูลครับ...');
    }

    // Student keywords
    if (lower.includes('นักเรียน') || lower.includes('เด็ก') || lower.includes('นักศึกษา')) {
        statuses.push('น้องดีโอกำลังค้นหาข้อมูลนักเรียนครับ...');
    }

    // Teacher keywords
    if (lower.includes('ครู') || lower.includes('บุคลากร') || lower.includes('อาจารย์')) {
        statuses.push('น้องดีโอกำลังค้นหาข้อมูลบุคลากรครับ...');
    }

    // Default
    if (statuses.length === 0) {
        statuses.push('น้องดีโอกำลังวิเคราะห์คำถามครับ...');
    }

    statuses.push('น้องดีโอกำลังเรียบเรียงคำตอบครับ...');

    return statuses;
};
