/**
 * Chat-related types
 * Category, User, Message, ChatState
 */

export enum Category {
    Auto = 'auto',
    General = 'general',
    School = 'school',
    Student = 'student'
}

export interface User {
    name: string;
    email: string;
    role: string;
    initials: string;
    avatar?: string;
}

export interface RagDebugInfo {
    source: 'pinecone' | 'legacy_rag' | 'ai_only' | 'small_talk_skip' | 'flask_error';
    contextPreview?: string;
    matchCount?: number;
    retrievalTimeMs?: number;
    embeddingModel?: string;
}

export interface Message {
    id: string;
    role: 'user' | 'model';
    content: string;
    timestamp: Date;
    isError?: boolean;
    isHistory?: boolean;
    ragDebugInfo?: RagDebugInfo;
}

export interface ChatState {
    messages: Message[];
    isLoading: boolean;
    category: Category;
}

export interface ChatSession {
    sessionId: string;
    userId: string;
    title: string;
    category: Category;
    updatedAt?: Date;
}
