/**
 * Admin Configuration Types
 * Types for admin panel settings and API configurations
 */

/** API Keys configuration per category */
export interface CategoryApiKeys {
    geminiKeys: string[];
    geminiConnected: boolean;
    groqKeys: string[];
    groqConnected: boolean;
    // Legacy RAG (n8n/proxy)
    ragEndpoint: string;
    ragApiKey: string;
    ragCollection: string;
    ragTopK: number;
    ragConnected: boolean;
    // Native Pinecone
    pineconeApiKey: string;
    pineconeHost: string;
    pineconeIndex: string;
    pineconeNamespace: string;
    pineconeConnected: boolean;
    // Dedicated Embedding API Key
    embeddingApiKey: string;
    // Flask Chatbot API (for School/Student categories)
    flaskApiUrl: string;
    flaskApiKey: string;
    flaskApiEnabled: boolean;
    flaskApiTimeout: number; // milliseconds (default: 30000)
    flaskApiConnected: boolean;
}

/** Prompt configuration */
export interface PromptsConfig {
    system: string;
    category: {
        general: string;
        school: string;
        student: string;
    };
    version: number;
    lastUpdated: string;
}

/** Model configuration */
export interface ModelConfig {
    name: string;
    temperature: number;
    maxTokens: number;
}

/** RAG global configuration */
export interface RagConfig {
    enabled: boolean;
}

/** UX Policy configuration */
export interface UxPolicyConfig {
    responseLength: 'short' | 'medium' | 'long';
    languageStyle: 'formal' | 'casual';
    errorMessage: string;
    emptyStateMessage: string;
    showRagDebug: boolean;
}

/** Main Admin Configuration interface */
export interface AdminConfig {
    apiKeys: {
        general: CategoryApiKeys;
        school: CategoryApiKeys;
        student: CategoryApiKeys;
    };
    prompts: PromptsConfig;
    model: ModelConfig;
    rag: RagConfig;
    uxPolicy: UxPolicyConfig;
}

/** Gemini connection test result */
export interface GeminiTestResult {
    success: boolean;
    message: string;
    supportedModels?: string[];
    quota?: string;
    errorType?: 'none' | 'quota_daily' | 'quota_minute' | 'invalid_key' | 'network' | 'unknown';
    quotaInfo?: {
        remainingRequests?: number;
        limitRequests?: number;
        resetTime?: string;
    };
}

/** RAG connection test result */
export interface RagTestResult {
    success: boolean;
    message: string;
}

/** Groq connection test result */
export interface GroqTestResult {
    success: boolean;
    message: string;
    errorType?: string;
}
