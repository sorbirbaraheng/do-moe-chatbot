import { AdminConfig } from '../../../contexts/AdminConfigContext';

// Shared props for all Admin Panel tabs
export interface TabProps {
    // Draft states
    draftApiKeys: AdminConfig['apiKeys'];
    setDraftApiKeys: React.Dispatch<React.SetStateAction<AdminConfig['apiKeys']>>;
    draftPrompts: AdminConfig['prompts'];
    setDraftPrompts: React.Dispatch<React.SetStateAction<AdminConfig['prompts']>>;
    draftModel: AdminConfig['model'];
    setDraftModel: React.Dispatch<React.SetStateAction<AdminConfig['model']>>;
    draftUX: AdminConfig['uxPolicy'];
    setDraftUX: React.Dispatch<React.SetStateAction<AdminConfig['uxPolicy']>>;

    // Config from context
    config: AdminConfig;

    // Testing state
    isTesting: 'gemini' | 'rag' | 'groq' | 'flask' | null;
    setIsTesting: React.Dispatch<React.SetStateAction<'gemini' | 'rag' | 'groq' | 'flask' | null>>;

    // Message feedback
    setSaveMessage: React.Dispatch<React.SetStateAction<string>>;
}

// API Settings Tab specific props
export interface ApiSettingsTabProps extends TabProps {
    activeApiCategory: 'general' | 'school' | 'student';
    setActiveApiCategory: React.Dispatch<React.SetStateAction<'general' | 'school' | 'student'>>;
    handleTestGemini: (category: 'general' | 'school' | 'student') => void;
    handleTestGroq: (category: 'general' | 'school' | 'student', keyIndex?: number) => void;
    handleTestRAG: (category: 'general' | 'school' | 'student') => void;

    handleTestFlask: (category: 'general' | 'school' | 'student') => void;
    handleOptimizeQueue: () => void;
    keyStatuses: Record<string, Record<number, 'valid' | 'invalid' | undefined>>;
    keyErrorMessages: Record<string, Record<number, string>>;
    keyErrorTypes: Record<string, Record<number, string>>;
    testingKeyIndex: number | null;
}

// Prompts Tab specific props
export interface PromptsTabProps extends TabProps {
    // Uses base TabProps
}

// Model Config Tab specific props
export interface ModelConfigTabProps extends TabProps {
    supportedModelsByCategory: Record<string, string[]>;
}

// RAG Config Tab specific props
export interface RagConfigTabProps extends TabProps {
    updateRAG: (updates: Partial<AdminConfig['rag']>) => void;
}

// Data Management Tab specific props
export interface DataManagementTabProps extends TabProps {
    // Uses base TabProps
}

// UX Policy Tab specific props
export interface UxPolicyTabProps extends TabProps {
    // Uses base TabProps
}
