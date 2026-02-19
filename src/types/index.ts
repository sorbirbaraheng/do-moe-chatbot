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
    ProviderTestResult,
} from './admin.types';

// Backward compatibility alias
export type { ProviderTestResult as GroqTestResult } from './admin.types';
