/**
 * Chatbot API Client
 * สำหรับเชื่อมต่อกับ Flask Chatbot API (Education Statistics)
 * @version 1.1.0
 */

/**
 * Auto-detect Flask API URL based on browser location
 * - localhost/127.0.0.1 → http://127.0.0.1:5001
 * - Network IP → Same IP with port 5001
 * @param {number} port - Flask port (default: 5001)
 * @returns {string} Flask API base URL
 */
export function getFlaskBaseUrl(port = 5001) {
    if (typeof window === 'undefined') {
        // Node.js environment - return localhost
        return `http://127.0.0.1:${port}`;
    }

    const hostname = window.location.hostname;

    // localhost or 127.0.0.1 → use localhost
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return `http://127.0.0.1:${port}`;
    }

    // Network IP or domain → use same host with Flask port
    return `http://${hostname}:${port}`;
}


/**
 * @typedef {Object} ChatMessage
 * @property {'user'|'assistant'} role - บทบาทของผู้ส่งข้อความ
 * @property {string} content - เนื้อหาข้อความ
 */

/**
 * @typedef {Object} SendMessageOptions
 * @property {ChatMessage[]} [history] - ประวัติการสนทนา
 * @property {string} [collection_name] - ชื่อ collection (default: 'education_statistics')
 * @property {string} [system_prompt] - System prompt สำหรับ AI
 * @property {boolean} [saveHistory] - บันทึกประวัติหรือไม่ (default: true)
 * @property {string} [session_id] - Session ID สำหรับ conversation memory
 * @property {string} [category] - หมวดหมู่การสนทนา (general, school, student)
 * @property {string} [intent] - เจตนาของผู้ใช้ (count, list, compare, etc.)
 * @property {string} [school_name] - ชื่อโรงเรียน (ถ้ามี)
 * @property {string} [level] - ระดับการค้นหา (province, district, etc.)
 */

/**
 * @typedef {Object} APIResponse
 * @property {boolean} success - สถานะสำเร็จหรือไม่
 * @property {string} [response] - คำตอบจาก AI
 * @property {string} [sources] - แหล่งข้อมูลอ้างอิง
 * @property {string} [error] - ข้อความ error (ถ้ามี)
 */

/**
 * @typedef {Object} HealthCheckResponse
 * @property {boolean} success - สถานะสำเร็จหรือไม่
 * @property {string} [status] - สถานะ API
 * @property {string} [version] - เวอร์ชัน API
 * @property {string} [error] - ข้อความ error (ถ้ามี)
 */

class ChatbotAPI {
    /**
     * สร้าง instance ของ ChatbotAPI
     * @param {string} apiUrl - URL ของ Flask API (เช่น 'http://localhost:5000')
     * @param {string} [apiKey] - API Key สำหรับ authentication (optional)
     */
    constructor(apiUrl, apiKey = '') {
        this.apiUrl = apiUrl.replace(/\/$/, ''); // ลบ trailing slash
        this.apiKey = apiKey;
        this.chatHistory = [];
    }

    /**
     * สร้าง Headers สำหรับ API request
     * @returns {Object} Headers object
     * @private
     */
    _getHeaders() {
        const headers = {
            'Content-Type': 'application/json',
        };
        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }
        return headers;
    }

    /**
     * ส่งข้อความไปยัง Chatbot API
     * @param {string} message - ข้อความที่ต้องการส่ง
     * @param {SendMessageOptions} [options={}] - ตัวเลือกเพิ่มเติม
     * @returns {Promise<APIResponse>} ผลลัพธ์จาก API
     */
    async sendMessage(message, options = {}) {
        const {
            history = this.chatHistory,
            collection_name = 'education_statistics',
            system_prompt = '',
            saveHistory = true,
            session_id = 'default',
            category = 'general',  // NEW: Add category parameter
        } = options;

        try {
            const response = await fetch(`${this.apiUrl}/api/chat`, {
                method: 'POST',
                headers: this._getHeaders(),
                body: JSON.stringify({
                    message,
                    history,
                    collection_name,
                    system_prompt,
                    session_id,
                    category,  // NEW: Include category in request
                }),
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[ChatbotAPI] HTTP Error:', response.status, errorText);
                return {
                    success: false,
                    error: `HTTP ${response.status}: ${errorText}`,
                };
            }

            const data = await response.json();

            // บันทึกประวัติถ้าต้องการ
            if (saveHistory) {
                this.chatHistory.push({ role: 'user', content: message });
                this.chatHistory.push({ role: 'assistant', content: data.response });
            }

            return {
                success: true,
                response: data.response,
                sources: data.sources || '',
            };
        } catch (error) {
            console.error('[ChatbotAPI] sendMessage Error:', error);
            return {
                success: false,
                error: error.message || 'Network error',
            };
        }
    }

    /**
     * ส่งข้อความแบบ Streaming (SSE)
     * @param {string} message 
     * @param {SendMessageOptions} [options={}]
     * @param {function(string): void} [onChunk] Callback เมื่อได้รับข้อความใหม่
     * @returns {Promise<APIResponse>} ผลลัพธ์สุดท้าย
     */
    async sendStream(message, options = {}, onChunk = () => { }) {
        const {
            history = this.chatHistory,
            collection_name = 'education_statistics',
            system_prompt = '',
            saveHistory = true,
            session_id = 'default',
            category = 'general',
            // NEW: Parse query metadata from frontend
            intent = null,
            school_name = null,
            level = null,
        } = options;

        try {
            const response = await fetch(`${this.apiUrl}/api/chat/stream`, {
                method: 'POST',
                headers: this._getHeaders(),
                body: JSON.stringify({
                    message,
                    history,
                    collection_name,
                    system_prompt,
                    session_id,
                    category,
                    // NEW: Include parsed query metadata for better backend routing
                    intent,
                    school_name,
                    level,
                }),
            });


            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let accumulatedText = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);
                        if (dataStr === '[DONE]') continue;

                        try {
                            const data = JSON.parse(dataStr);
                            if (data.text) {
                                // Smooth Typing Effect: Split into small chunks to simulate typing
                                // Prevents huge text blocks from appearing instantly
                                const chunkSize = 3; // Group 3 chars (reduces React renders vs 1 char)
                                for (let i = 0; i < data.text.length; i += chunkSize) {
                                    const slice = data.text.slice(i, i + chunkSize);
                                    onChunk(slice);
                                    accumulatedText += slice;
                                    // Delay: 10ms for normal text, 20ms for punctuation (simulated)
                                    await new Promise(r => setTimeout(r, 10));
                                }
                            }
                        } catch (e) {
                            console.error('Error parsing SSE:', e);
                        }
                    }
                }
            }

            if (saveHistory) {
                this.chatHistory.push({ role: 'user', content: message });
                this.chatHistory.push({ role: 'assistant', content: accumulatedText });
            }

            return {
                success: true,
                response: accumulatedText,
            };

        } catch (error) {
            console.error('[ChatbotAPI] sendStream Error:', error);
            return {
                success: false,
                error: error.message,
            };
        }
    }
    /**
     * ส่งข้อความแบบ One-Shot (ไม่บันทึกประวัติ)
     * @param {string} message - ข้อความที่ต้องการส่ง
     * @param {SendMessageOptions} [options={}] - ตัวเลือกเพิ่มเติม
     * @returns {Promise<APIResponse>} ผลลัพธ์จาก API
     */
    async sendOneShot(message, options = {}) {
        return this.sendMessage(message, {
            ...options,
            history: [],
            saveHistory: false,
        });
    }

    /**
     * ส่งหลายข้อความพร้อมกัน (Batch)
     * @param {string[]} messages - Array ของข้อความ
     * @param {SendMessageOptions} [options={}] - ตัวเลือกเพิ่มเติม
     * @returns {Promise<APIResponse[]>} Array ของผลลัพธ์
     */
    async sendBatch(messages, options = {}) {
        const results = [];
        for (const message of messages) {
            const result = await this.sendMessage(message, options);
            results.push(result);
        }
        return results;
    }

    /**
     * ล้างประวัติการสนทนา
     */
    clearHistory() {
        this.chatHistory = [];
        console.log('[ChatbotAPI] History cleared');
    }

    /**
     * ดึงประวัติการสนทนา
     * @returns {ChatMessage[]} ประวัติการสนทนา
     */
    getHistory() {
        return [...this.chatHistory];
    }

    /**
     * ตั้งค่าประวัติการสนทนา
     * @param {ChatMessage[]} history - ประวัติที่ต้องการตั้งค่า
     */
    setHistory(history) {
        if (Array.isArray(history)) {
            this.chatHistory = history;
            console.log('[ChatbotAPI] History set:', history.length, 'messages');
        } else {
            console.error('[ChatbotAPI] Invalid history format');
        }
    }

    /**
     * ทดสอบการเชื่อมต่อกับ API
     * @returns {Promise<{success: boolean, message: string, latencyMs?: number}>}
     */
    async testConnection() {
        const startTime = Date.now();
        try {
            const response = await fetch(`${this.apiUrl}/api/health`, {
                method: 'GET',
                headers: this._getHeaders(),
            });

            const latencyMs = Date.now() - startTime;

            if (response.ok) {
                return {
                    success: true,
                    message: `Connected to ${this.apiUrl}`,
                    latencyMs,
                };
            } else {
                return {
                    success: false,
                    message: `Connection failed: HTTP ${response.status}`,
                };
            }
        } catch (error) {
            console.error('[ChatbotAPI] testConnection Error:', error);
            return {
                success: false,
                message: `Connection failed: ${error.message}`,
            };
        }
    }

    /**
     * ตรวจสอบสถานะ API (Health Check)
     * @returns {Promise<HealthCheckResponse>}
     */
    async checkHealth() {
        try {
            const response = await fetch(`${this.apiUrl}/api/health`, {
                method: 'GET',
                headers: this._getHeaders(),
            });

            if (!response.ok) {
                return {
                    success: false,
                    error: `HTTP ${response.status}`,
                };
            }

            const data = await response.json();
            return {
                success: true,
                status: data.status || 'ok',
                version: data.version || 'unknown',
            };
        } catch (error) {
            console.error('[ChatbotAPI] checkHealth Error:', error);
            return {
                success: false,
                error: error.message || 'Health check failed',
            };
        }
    }

    /**
     * ดึงรายชื่อ Collections ที่มีใน API
     * @returns {Promise<{success: boolean, collections?: string[], error?: string}>}
     */
    async getCollections() {
        try {
            const response = await fetch(`${this.apiUrl}/api/collections`, {
                method: 'GET',
                headers: this._getHeaders(),
            });

            if (!response.ok) {
                return {
                    success: false,
                    error: `HTTP ${response.status}`,
                };
            }

            const data = await response.json();
            return {
                success: true,
                collections: data.collections || [],
            };
        } catch (error) {
            console.error('[ChatbotAPI] getCollections Error:', error);
            return {
                success: false,
                error: error.message || 'Failed to get collections',
            };
        }
    }

    /**
     * Get paginated school list (No LLM - Direct Database Query)
     * @param {Object} options - Query options
     * @param {string} options.province - Province name (required)
     * @param {string} [options.district] - District name (optional)
     * @param {string} [options.agency] - Agency name (optional)
     * @param {number} [options.offset=0] - Offset for pagination
     * @param {number} [options.limit=15] - Number of results per page
     * @returns {Promise<{success: boolean, schools?: Array, total?: number, hasMore?: boolean, error?: string}>}
     */
    async getSchoolList(options = {}) {
        const {
            province,
            district = null,
            agency = null,
            offset = 0,
            limit = 15,
        } = options;

        if (!province) {
            return { success: false, error: 'Province is required' };
        }

        try {
            const response = await fetch(`${this.apiUrl}/api/schools/list`, {
                method: 'POST',
                headers: this._getHeaders(),
                body: JSON.stringify({
                    province,
                    district,
                    agency,
                    offset,
                    limit,
                }),
            });

            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('[ChatbotAPI] getSchoolList Error:', error);
            return { success: false, error: error.message };
        }
    }
}

// ES6 Export
export default ChatbotAPI;

// CommonJS Export (สำหรับ Node.js)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatbotAPI;
}
