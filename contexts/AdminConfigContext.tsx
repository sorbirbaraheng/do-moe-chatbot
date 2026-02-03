/**
 * 📄 ชื่อไฟล์: AdminConfigContext.tsx
 * 📝 คำอธิบาย:
 *    ระบบจัดการการตั้งค่า (Admin Configuration System)
 *    เป็นตัวกลางในการจัดการค่า Config ทั้งหมดของระบบ
 *
 * 🛠 หน้าที่หลัก:
 *    1. Settings Management: เก็บและอัปเดตค่า API Keys, Model, และ Prompt
 *    2. Sync: เชื่อมต่อกับ Firebase Firestore เพื่อบันทึกค่าการตั้งค่า
 *    3. Connection Testing: ฟังก์ชันทดสอบการเชื่อมต่อกับ Gemini, Groq, และ RAG Server
 *    4. Provider Patterns: ส่งค่า Config ไปให้ส่วนอื่นๆ ของแอปใช้งานผ่าน React Context
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Category } from '../types';
import { AdminConfig } from '../types/admin.types';
import { DEFAULT_CONFIG } from '../config';
import { db } from '../services/firebase';
import { doc, onSnapshot, setDoc, getDoc } from 'firebase/firestore';

// Re-export for backward compatibility
export type { AdminConfig } from '../types/admin.types';

// Context type
interface AdminConfigContextType {
    config: AdminConfig;
    updateConfig: (newConfig: Partial<AdminConfig>) => Promise<boolean>;
    updateApiKeys: (category: 'general' | 'school' | 'student', apiKeys: Partial<AdminConfig['apiKeys']['general']>) => Promise<void>;
    updatePrompts: (prompts: Partial<AdminConfig['prompts']>) => void;
    updateModel: (model: Partial<AdminConfig['model']>) => void;
    updateRAG: (rag: Partial<AdminConfig['rag']>) => void;
    updateUXPolicy: (uxPolicy: Partial<AdminConfig['uxPolicy']>) => void;
    resetToDefault: () => void;
    getSystemInstruction: (category: Category) => string;
    testGeminiConnection: (apiKey: string, category: 'general' | 'school' | 'student') => Promise<{ success: boolean; message: string; supportedModels?: string[]; quota?: string; errorType?: 'none' | 'quota_daily' | 'quota_minute' | 'invalid_key' | 'network' | 'unknown'; quotaInfo?: { remainingRequests?: number; limitRequests?: number; resetTime?: string } }>;
    testGroqConnection: (apiKey: string, category: string) => Promise<{ success: boolean; message: string; errorType?: string }>;
    testRAGConnection: (endpoint: string, apiKey: string, category: 'general' | 'school' | 'student') => Promise<{ success: boolean; message: string }>;
    supportedModelsByCategory: Record<string, string[]>;
}

const AdminConfigContext = createContext<AdminConfigContextType | undefined>(undefined);

const CONFIG_DOC_ID = 'main-config';

export const AdminConfigProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [config, setConfig] = useState<AdminConfig>(DEFAULT_CONFIG);
    const [supportedModelsByCategory, setSupportedModelsByCategory] = useState<Record<string, string[]>>({
        general: [],
        school: [],
        student: []
    });

    const [isLoaded, setIsLoaded] = useState(false);

    useEffect(() => {
        const docRef = doc(db, 'settings', CONFIG_DOC_ID);
        const unsubscribe = onSnapshot(docRef, (docSnap) => {
            if (docSnap.exists()) {
                const data = docSnap.data() as Partial<AdminConfig>;

                // Migration: Fix deprecated models
                if (data.model && (
                    data.model.name === 'gemini-pro' ||
                    data.model.name === 'gemini-2.5-flash-preview-05-20' ||
                    data.model.name === 'gemini-1.5-pro'
                )) {
                    console.log(`[Config] Migrating deprecated model ${data.model.name} to gemini-2.5-flash`);
                    data.model.name = 'gemini-2.5-flash';
                }

                // IMPORTANT: Force sync prompts if DEFAULT_CONFIG has newer version
                const firestoreVersion = data.prompts?.version || 0;
                const latestVersion = DEFAULT_CONFIG.prompts.version;
                if (firestoreVersion < latestVersion) {
                    console.log(`[Config] Upgrading prompts from v${firestoreVersion} to v${latestVersion} (Advanced Gemini Style)`);
                    data.prompts = {
                        ...DEFAULT_CONFIG.prompts,
                        version: latestVersion,
                        lastUpdated: new Date().toISOString(),
                    };
                    // Save the updated prompts to Firestore
                    const docRef = doc(db, 'settings', CONFIG_DOC_ID);
                    setDoc(docRef, { prompts: data.prompts }, { merge: true }).catch(err =>
                        console.error("[Config] Failed to save prompt upgrade:", err)
                    );
                }

                setConfig(prev => ({ ...prev, ...data }));
                setIsLoaded(true); // ✅ Mark as loaded
            } else {
                setDoc(docRef, DEFAULT_CONFIG).catch(err => console.error("Failed to init config:", err));
                setIsLoaded(true); // ✅ Mark as loaded (default)
            }
        }, (error) => {
            console.error("Firestore sync error:", error);
        });
        return () => unsubscribe();
    }, []);

    // 🌐 Auto-detect Flask API URL from browser hostname when not set
    // Priority: Admin-set production URL > Auto-detect for development
    useEffect(() => {
        if (typeof window === 'undefined' || !isLoaded) return; // 🛡️ Wait for Firestore load

        const schoolUrl = config.apiKeys.school?.flaskApiUrl;
        const studentUrl = config.apiKeys.student?.flaskApiUrl;

        // Check if URL is a production URL (should NOT be overwritten)
        const isProductionUrl = (url: string | undefined) => {
            if (!url) return false;
            // Production URLs: https:// or any domain that's not localhost/127.x/private IP
            if (url.startsWith('https://')) return true;
            // Check for real domains (not localhost, 127.x, 192.168.x, 10.x)
            const urlHost = url.replace(/https?:\/\//, '').split(':')[0];
            const isPrivateIp = urlHost === 'localhost' ||
                urlHost.startsWith('127.') ||
                urlHost.startsWith('192.168.') ||
                urlHost.startsWith('10.');
            return !isPrivateIp && urlHost.includes('.');
        };

        // Skip auto-detect if Admin has set a production URL
        if (isProductionUrl(schoolUrl) || isProductionUrl(studentUrl)) {
            console.log(`[Auto IP] Skipped - Using production URL: ${schoolUrl}`);
            return;
        }

        // Only auto-detect if URLs are empty or localhost when accessing from LAN
        const currentHost = window.location.hostname;
        const isLan = currentHost !== 'localhost' && currentHost !== '127.0.0.1';
        const needsAutoDetect = (
            !schoolUrl ||
            !studentUrl ||
            (isLan && (schoolUrl?.includes('127.0.0.1') || schoolUrl?.includes('localhost')))
        );

        if (needsAutoDetect && config.apiKeys.school?.flaskApiEnabled) {
            const detectedUrl = isLan
                ? `http://${currentHost}:5001`
                : 'http://127.0.0.1:5001';

            console.log(`[Auto IP] Detected Flask API URL: ${detectedUrl} (LAN: ${isLan})`);

            // Update both categories
            updateApiKeys('school', { flaskApiUrl: detectedUrl });
            updateApiKeys('student', { flaskApiUrl: detectedUrl });
        }
    }, [config.apiKeys.school?.flaskApiUrl, config.apiKeys.student?.flaskApiUrl, isLoaded]);

    const updateConfig = async (newConfig: Partial<AdminConfig>): Promise<boolean> => {
        setConfig(prev => {
            const updated = { ...prev, ...newConfig };
            try {
                localStorage.setItem('admin_config_backup', JSON.stringify(updated));
            } catch (e) { console.error("Local backup failed", e); }
            return updated;
        });

        try {
            const docRef = doc(db, 'settings', CONFIG_DOC_ID);
            const timeoutPromise = new Promise((_, reject) =>
                setTimeout(() => reject(new Error("Firestore write timed out (10s)")), 10000)
            );
            await Promise.race([
                setDoc(docRef, newConfig, { merge: true }),
                timeoutPromise
            ]);
            return true;
        } catch (error) {
            console.warn("Firestore save failed or timed out:", error);
            return false;
        }
    };

    const updatePrompts = (prompts: Partial<AdminConfig['prompts']>) => {
        updateConfig({
            prompts: {
                ...config.prompts,
                ...prompts,
                version: config.prompts.version + 1,
                lastUpdated: new Date().toISOString(),
            }
        });
    };

    const updateModel = (model: Partial<AdminConfig['model']>) => {
        updateConfig({ model: { ...config.model, ...model } });
    };

    const updateRAG = (rag: Partial<AdminConfig['rag']>) => {
        updateConfig({ rag: { ...config.rag, ...rag } });
    };

    const updateUXPolicy = (uxPolicy: Partial<AdminConfig['uxPolicy']>) => {
        updateConfig({ uxPolicy: { ...config.uxPolicy, ...uxPolicy } });
    };

    const updateApiKeys = async (category: 'general' | 'school' | 'student', updates: Partial<AdminConfig['apiKeys']['general']>) => {
        // 1. Optimistic Update (Local State)
        setConfig(prev => ({
            ...prev,
            apiKeys: {
                ...prev.apiKeys,
                [category]: { ...prev.apiKeys[category], ...updates }
            }
        }));

        // 2. Safe Firestore Update (Dot Notation)
        // Using dot notation (e.g. "apiKeys.school.flaskApiUrl") ensures we ONLY update specific fields
        // and NEVER overwrite the entire map if our local state is stale.
        try {
            const docRef = doc(db, 'settings', CONFIG_DOC_ID);
            const dotNotationUpdates: Record<string, any> = {};

            Object.entries(updates).forEach(([key, value]) => {
                dotNotationUpdates[`apiKeys.${category}.${key}`] = value;
            });

            // Use updateDoc for atomic field updates
            // (Use setDoc with merge if document might not exist, but updateDoc is safer for existing docs)
            const { updateDoc } = await import('firebase/firestore');
            await updateDoc(docRef, dotNotationUpdates);

            console.log(`[Config] Safe update for ${category}:`, Object.keys(updates));
        } catch (error) {
            console.error('[Config] Failed to update API keys:', error);
            // Revert or retry could be added here
        }
    };

    const resetToDefault = async () => {
        setConfig(DEFAULT_CONFIG);
        localStorage.removeItem('admin_config_backup');

        // Save to Firestore
        try {
            const docRef = doc(db, 'settings', CONFIG_DOC_ID);
            await setDoc(docRef, DEFAULT_CONFIG);
            console.log('[AdminConfig] Reset to default and saved to Firestore');
        } catch (error) {
            console.error('[AdminConfig] Failed to save reset to Firestore:', error);
        }
    };

    const testGeminiConnection = async (apiKey: string, category: 'general' | 'school' | 'student'): Promise<{ success: boolean; message: string; supportedModels?: string[]; quota?: string; errorType?: 'none' | 'quota_daily' | 'quota_minute' | 'invalid_key' | 'network' | 'unknown'; quotaInfo?: { remainingRequests?: number; limitRequests?: number; resetTime?: string } }> => {
        try {
            // Step 1: First, test with list models to get supported models
            const listResponse = await fetch(
                `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`
            );

            const listData = await listResponse.json().catch(() => ({}));

            if (listResponse.status === 403 || listResponse.status === 401) {
                updateApiKeys(category, { geminiConnected: false });
                return {
                    success: false,
                    message: 'API Key ไม่ถูกต้อง (Invalid Key)',
                    errorType: 'invalid_key'
                };
            }

            // Extract supported models
            let supportedModels: string[] = [];
            // Model Priority List - Updated Jan 2026
            const MODEL_PRIORITY_LIST = [
                'gemini-2.5-flash',
                'gemini-2.0-flash',
                'gemini-2.0-flash-exp',
                'gemini-2.0-flash-001',
                'gemini-1.5-flash-latest',
                'gemini-1.5-flash-001',
                'gemini-1.5-flash-002',
                'gemini-1.5-pro-latest',
            ];

            if (listResponse.ok && listData.models) {
                supportedModels = listData.models
                    .map((m: any) => m.name.replace('models/', ''))
                    .filter((name: string) => name.includes('gemini'));

                setSupportedModelsByCategory(prev => ({
                    ...prev,
                    [category]: supportedModels
                }));
            }

            // Step 2: Find the first working model via probing
            let testModelId = '';

            // Try models from priority list that are in supported models
            for (const priorityModel of MODEL_PRIORITY_LIST) {
                const match = supportedModels.find(m =>
                    m === priorityModel || m.includes(priorityModel) || priorityModel.includes(m)
                );
                if (match) {
                    testModelId = match;
                    break;
                }
            }

            // Fallback to first supported or gemini-2.5-flash
            if (!testModelId) {
                testModelId = supportedModels[0] || 'gemini-2.5-flash';
            }

            console.log(`[Quota Test] Testing key: ${apiKey.substring(0, 10)}... with model: ${testModelId}`);

            const generateResponse = await fetch(
                `https://generativelanguage.googleapis.com/v1beta/models/${testModelId}:generateContent?key=${apiKey}`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        contents: [{ parts: [{ text: 'ตอบแค่ "OK"' }] }],
                        generationConfig: { maxOutputTokens: 5 }
                    })
                }
            );

            // Extract rate limit headers (Gemini may not always provide these)
            const remainingRequests = generateResponse.headers.get('x-ratelimit-remaining-requests') ||
                generateResponse.headers.get('x-ratelimit-remaining');
            const limitRequests = generateResponse.headers.get('x-ratelimit-limit-requests');
            const resetTime = generateResponse.headers.get('x-ratelimit-reset-requests');

            const quotaInfo = {
                remainingRequests: remainingRequests ? parseInt(remainingRequests) : undefined,
                limitRequests: limitRequests ? parseInt(limitRequests) : undefined,
                resetTime: resetTime || undefined
            };
            console.log('[Quota] Gemini headers:', quotaInfo);

            const genData = await generateResponse.json().catch(() => ({}));

            if (generateResponse.ok) {
                updateApiKeys(category, { geminiConnected: true });
                return {
                    success: true,
                    message: remainingRequests
                        ? `✅ พร้อมใช้งาน (เหลือ ${remainingRequests} requests)`
                        : '✅ พร้อมใช้งาน',
                    supportedModels,
                    errorType: 'none',
                    quotaInfo
                };
            }

            // Handle quota errors
            const status = generateResponse.status;
            const errorMsg = genData?.error?.message || '';

            if (status === 429) {
                let quotaType: 'quota_daily' | 'quota_minute' = 'quota_minute';
                let message = '';

                if (errorMsg.includes('GenerateRequestsPerDay') || errorMsg.includes('DAILY')) {
                    quotaType = 'quota_daily';
                    message = '🚫 โควต้ารายวันหมด (Daily Limit) - ลองใหม่พรุ่งนี้';
                } else if (errorMsg.includes('GenerateRequestsPerMinute') || errorMsg.includes('per minute')) {
                    quotaType = 'quota_minute';
                    // Try to extract retry delay
                    const retryMatch = errorMsg.match(/Retry after (\d+)/i) ||
                        genData?.error?.details?.find((d: any) => d.retryDelay)?.retryDelay;
                    const retrySeconds = retryMatch ? parseInt(retryMatch[1] || retryMatch.replace('s', '')) : 60;
                    message = `⏳ โควต้าต่อนาทีหมด - รอ ${retrySeconds} วินาที`;
                } else {
                    message = `⚠️ โควต้าเต็ม: ${errorMsg.substring(0, 80)}`;
                }

                updateApiKeys(category, { geminiConnected: false });
                return { success: false, message, supportedModels, errorType: quotaType };
            }

            if (status === 403 || status === 401) {
                updateApiKeys(category, { geminiConnected: false });
                return {
                    success: false,
                    message: '🔐 ไม่มีสิทธิ์ใช้ Model นี้',
                    supportedModels,
                    errorType: 'invalid_key'
                };
            }

            // Unknown error
            return {
                success: false,
                message: `❌ Error: ${errorMsg.substring(0, 100) || 'Unknown'}`,
                supportedModels,
                errorType: 'unknown'
            };

        } catch (error: any) {
            console.error(`Gemini connection test failed for ${category}:`, error);
            updateApiKeys(category, { geminiConnected: false });
            return {
                success: false,
                message: '🌐 Network Error: ตรวจสอบอินเทอร์เน็ต',
                errorType: 'network'
            };
        }
    };

    const testGroqConnection = async (apiKey: string, category: 'general' | 'school' | 'student') => {
        // Dynamic import to avoid circular dependency
        const { testGroqConnection: serviceTest } = await import('../services/geminiService');
        return await serviceTest(apiKey, category);
    };

    const testRAGConnection = async (endpoint: string, apiKey: string, category: 'general' | 'school' | 'student'): Promise<{ success: boolean; message: string }> => {
        try {
            if (!endpoint) return { success: false, message: 'กรุณาระบุ URL' };

            // Validate URL format
            try { new URL(endpoint); } catch (e) { return { success: false, message: 'URL Format ไม่ถูกต้อง' }; }

            // Pinecone direct URL detection (Common mistake)
            if (endpoint.includes('pinecone.io')) {
                return {
                    success: false,
                    message: '⚠️ ตรวจพบ Pinecone URL: ระบบต้องการ n8n Webhook หรือ RAG Proxy (ห้ามต่อตรงกับ Database)'
                };
            }

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 7000);

            // Try /health first, then /query with dummy if health fails (some n8n don't have /health)
            const response = await fetch(`${endpoint}/health`, {
                method: 'GET',
                headers: apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {},
                signal: controller.signal
            }).catch(() => null);

            clearTimeout(timeoutId);

            if (response && response.ok) {
                updateApiKeys(category, { ragConnected: true });
                return { success: true, message: '✅ เชื่อมต่อสำเร็จ (Health OK)' };
            }

            // Fallback: Test if the endpoint exists at all
            updateApiKeys(category, { ragConnected: false });
            return {
                success: false,
                message: response ? `❌ Server Error (${response.status})` : '🌐 ไม่สามารถติดต่อ Server ได้ (CORS หรือ URL ผิด)'
            };
        } catch (error) {
            console.error(`RAG connection test failed for ${category}:`, error);
            updateApiKeys(category, { ragConnected: false });
            return { success: false, message: '🌐 Network Error หรือติด CORS Policy' };
        }
    };

    const getSystemInstruction = (category: Category): string => {
        // For Auto mode, use 'general' as base since the actual category is determined per-message
        const categoryKey = category === Category.Auto ? 'general' :
            category === Category.General ? 'general' :
                category === Category.School ? 'school' : 'student';
        const categoryPrompt = config.prompts.category[categoryKey];
        const categoryLabel = category === Category.Auto ? 'อัตโนมัติ (Auto-Detect)' :
            categoryKey === 'general' ? 'ข้อมูลทั่วไป' :
                categoryKey === 'school' ? 'ข้อมูลโรงเรียน' : 'สถิตินักเรียน';

        // Note: The main system prompt already contains the full Gemini-style reasoning workflow
        // Here we just append the category-specific context
        return `${config.prompts.system}

================================================================
CATEGORY SCOPE: ${category === Category.Auto ? 'AUTO-DETECT' : categoryKey.toUpperCase()}
================================================================
- ปัจจุบันคุณกำลังให้บริการในหมวด: **${categoryLabel}**
${category === Category.Auto ? '- ระบบจะเลือกหมวดหมู่ที่เหมาะสมตามคำถามของผู้ใช้โดยอัตโนมัติ' : ''}
- ${categoryPrompt}
- คุณสามารถตอบคำถามได้ทุกประเภท ทั้งคำถามทั่วไปและคำถามเกี่ยวกับการศึกษาในหมวดเดียวกัน
`;
    };

    return (
        <AdminConfigContext.Provider value={{
            config,
            updateConfig,
            updateApiKeys,
            updatePrompts,
            updateModel,
            updateRAG,
            updateUXPolicy,
            resetToDefault,
            getSystemInstruction,
            testGeminiConnection,
            testGroqConnection,
            testRAGConnection,
            supportedModelsByCategory,
        }
        }>
            {children}
        </AdminConfigContext.Provider >
    );
};

export const useAdminConfig = (): AdminConfigContextType => {
    const context = useContext(AdminConfigContext);
    if (!context) throw new Error('useAdminConfig must be used within AdminConfigProvider');
    return context;
};

export default AdminConfigContext;
