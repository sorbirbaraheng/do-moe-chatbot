/**
 * Default Admin Configuration
 * Central place for all default values
 */

import { AdminConfig, CategoryApiKeys } from '../types/admin.types';
import { SYSTEM_PROMPT, CATEGORY_PROMPTS, UX_MESSAGES } from './systemPrompts';

/** Default API keys configuration for a single category */
const DEFAULT_CATEGORY_API_KEYS: CategoryApiKeys = {
    geminiKeys: [],
    geminiConnected: false,
    groqKeys: [],
    groqConnected: false,
    ragEndpoint: '',
    ragApiKey: '',
    ragCollection: '',
    ragTopK: 5,
    ragConnected: false,
    pineconeApiKey: '',
    pineconeHost: '',
    pineconeIndex: '',
    pineconeNamespace: '',
    pineconeConnected: false,
    embeddingApiKey: '',
    // Flask Chatbot API
    flaskApiUrl: '',
    flaskApiKey: '',
    flaskApiEnabled: false,
    flaskApiTimeout: 30000, // 30 seconds
    flaskApiConnected: false,
};

/** Default Admin Configuration */
export const DEFAULT_CONFIG: AdminConfig = {
    apiKeys: {
        general: {
            ...DEFAULT_CATEGORY_API_KEYS,
            ragCollection: 'moe_data_general',
        },
        school: {
            ...DEFAULT_CATEGORY_API_KEYS,
            ragCollection: 'moe_data_school',
            // Flask API v5.0 for school queries - URL auto-detected at runtime
            flaskApiUrl: '',
            flaskApiKey: '',
            flaskApiEnabled: true,
            flaskApiConnected: false,
        },
        student: {
            ...DEFAULT_CATEGORY_API_KEYS,
            ragCollection: 'moe_data_student',
            // Flask API v5.0 for student queries - URL auto-detected at runtime
            flaskApiUrl: '',
            flaskApiKey: '',
            flaskApiEnabled: true,
            flaskApiConnected: false,
        },
    },
    prompts: {
        system: SYSTEM_PROMPT,
        category: CATEGORY_PROMPTS,
        version: 10, // Force sync Advanced System Prompt (Gemini Style)
        lastUpdated: new Date().toISOString(),
    },
    model: {
        name: 'gemini-2.5-flash',
        temperature: 0.7,
        maxTokens: 1024,
    },
    rag: {
        enabled: true,
    },
    uxPolicy: {
        responseLength: 'medium',
        languageStyle: 'formal',
        errorMessage: UX_MESSAGES.errorMessage,
        emptyStateMessage: UX_MESSAGES.emptyStateMessage,
        showRagDebug: false,
    },
};
