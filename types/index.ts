/**
 * Barrel export for all types
 * Import from '@/types' or '../types'
 */

// Chat types - Category is enum (value export), rest are interfaces (type export)
export { Category } from './chat.types';
export type { User, Message, RagDebugInfo, ChatState } from './chat.types';

// Admin types - all are interfaces (type export)
export type {
    CategoryApiKeys,
    PromptsConfig,
    ModelConfig,
    RagConfig,
    UxPolicyConfig,
    AdminConfig,
    GeminiTestResult,
    RagTestResult,
    GroqTestResult,
} from './admin.types';
