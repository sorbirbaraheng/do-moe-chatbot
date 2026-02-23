import { GoogleGenAI } from '@google/genai';

export interface ParsedQuery {
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

export interface ChatHistoryItem {
  role: string;
  parts: { text: string }[];
}

export interface RAGRetrievalResult {
  context: string;
  source: 'legacy_rag' | 'ai_only' | 'small_talk_skip';
  contextPreview?: string;
  matchCount?: number;
  retrievalTimeMs?: number;
  embeddingModel?: string;
}

export interface ChatResponse {
  text: string;
  ragDebugInfo?: {
    source: 'legacy_rag' | 'ai_only' | 'small_talk_skip';
    contextPreview?: string;
    matchCount?: number;
    retrievalTimeMs?: number;
    embeddingModel?: string;
  };
}
