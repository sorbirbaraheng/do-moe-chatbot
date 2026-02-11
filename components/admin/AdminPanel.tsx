import React, { useState, useEffect, useRef, useMemo } from 'react';
import { MOE_COLORS } from '../../constants';
import { useAdminConfig, AdminConfig } from '../../contexts/AdminConfigContext';
import { resetChatSession } from '../../services/geminiService';
import { canEditAdmin, getAdminRole, clearAdminSession } from '../../services/adminAuth';
import {
    ApiSettingsTab,
    PromptsTab,
    ModelConfigTab,
    RagConfigTab,
    DataManagementTab,
    UxPolicyTab,
    SessionMonitorTab,
    AnalyticsTab,
    UserManagementTab,
    AdminAuditTab,
} from './tabs';

interface AdminPanelProps {
    onClose: () => void;
    onLogout: () => void;
}

type TabId = 'api' | 'prompts' | 'monitor' | 'analytics' | 'users' | 'audit';

// SIMPLIFIED: Only keep functional tabs
const tabs: { id: TabId; label: string; icon: React.ReactNode; minRole: 'viewer' | 'operator' | 'admin' }[] = [
    {
        id: 'api',
        label: 'API Settings',
        icon: (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z" />
            </svg>
        ),
        minRole: 'operator',
    },
    {
        id: 'prompts',
        label: 'Prompt Management',
        icon: (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
            </svg>
        ),
        minRole: 'operator',
    },
    {
        id: 'monitor',
        label: 'Session Monitor',
        icon: (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 0 1-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0 1 15 18.257V17.25m6-12V15a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 15V5.25m18 0A2.25 2.25 0 0 0 18.75 3H5.25A2.25 2.25 0 0 0 3 5.25m18 0V12a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 12V5.25" />
            </svg>
        ),
        minRole: 'viewer',
    },
    {
        id: 'analytics',
        label: '📊 Analytics',
        icon: (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
            </svg>
        ),
        minRole: 'viewer',
    },
    {
        id: 'users',
        label: '👥 Users',
        icon: (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
            </svg>
        ),
        minRole: 'admin',
    },
    {
        id: 'audit',
        label: '🧾 Audit Logs',
        icon: (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6M7.5 4.5h9A1.5 1.5 0 0 1 18 6v12a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 18V6A1.5 1.5 0 0 1 7.5 4.5Z" />
            </svg>
        ),
        minRole: 'operator',
    }
];

const AdminPanel: React.FC<AdminPanelProps> = ({ onClose, onLogout }) => {
    const [activeTab, setActiveTab] = useState<TabId>('api');
    const role = getAdminRole() || 'viewer';
    const canEdit = canEditAdmin(role);
    const roleMeta: Record<typeof role, { label: string; desc: string; className: string }> = {
        viewer: { label: 'Viewer', desc: 'อ่านอย่างเดียว', className: 'bg-gray-100 text-gray-600' },
        operator: { label: 'Operator', desc: 'แก้ไขการตั้งค่า', className: 'bg-blue-100 text-blue-700' },
        admin: { label: 'Admin', desc: 'สิทธิ์เต็ม', className: 'bg-purple-100 text-purple-700' },
    };

    useEffect(() => {
        const roleRank: Record<typeof role, number> = { viewer: 0, operator: 1, admin: 2 };
        const allowed = tabs.filter(tab => roleRank[role] >= roleRank[tab.minRole]);
        if (allowed.length > 0 && !allowed.some(tab => tab.id === activeTab)) {
            setActiveTab(allowed[0].id);
        }
    }, [role]);
    const {
        config,
        updateConfig,
        testGeminiConnection,
        testGroqConnection,
        testRAGConnection,
        supportedModelsByCategory,
        updateRAG,
        resetToDefault,
    } = useAdminConfig();
    const [isSaving, setIsSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState('');
    const [isTesting, setIsTesting] = useState<'gemini' | 'rag' | 'groq' | 'flask' | null>(null);
    const [showUnsavedDialog, setShowUnsavedDialog] = useState(false);
    const [isResetting, setIsResetting] = useState(false);

    // Local draft state for editing (to avoid live updates while typing)
    const [draftApiKeys, setDraftApiKeys] = useState(config.apiKeys);
    const [draftPrompts, setDraftPrompts] = useState(config.prompts);
    const [draftModel, setDraftModel] = useState(config.model);
    const [draftUX, setDraftUX] = useState(config.uxPolicy);

    const hasInitialSync = useRef<string | false>(false);

    // Sync draft state with config ONLY on initial load (not during editing)
    const hasInitializedDraft = useRef(false);
    useEffect(() => {
        // Only sync once when component first mounts
        if (!hasInitializedDraft.current && config.apiKeys) {
            console.log('[AdminPanel] Initial sync from Firebase config...');
            setDraftApiKeys(config.apiKeys);
            setDraftPrompts(config.prompts);
            setDraftModel(config.model);
            setDraftUX(config.uxPolicy);
            hasInitializedDraft.current = true;
        }

        // 🌐 AUTO-IP FIX: If config updates with a detected Flask URL (and draft is still localhost/empty), update draft
        // This handles the race condition where AdminPanel loads before Auto-IP finishes
        if (hasInitializedDraft.current && config.apiKeys?.school?.flaskApiUrl) {
            const currentDraftUrl = draftApiKeys.school?.flaskApiUrl;
            const newConfigUrl = config.apiKeys.school.flaskApiUrl;

            // If draft is empty OR localhost, but new config has a real IP (LAN)
            const isDraftInvalid = !currentDraftUrl || currentDraftUrl.includes('localhost') || currentDraftUrl.includes('127.0.0.1');
            const isConfigBetter = newConfigUrl !== currentDraftUrl && !newConfigUrl.includes('localhost') && !newConfigUrl.includes('127.0.0.1');

            if (isDraftInvalid && isConfigBetter) {
                console.log(`[AdminPanel] Auto-updating draft URL to: ${newConfigUrl}`);
                setDraftApiKeys(prev => ({
                    ...prev,
                    school: { ...prev.school, flaskApiUrl: newConfigUrl },
                    student: { ...prev.student, flaskApiUrl: newConfigUrl }
                }));
            }
        }
    }, [config]);

    // Check for unsaved changes
    const hasUnsavedChanges = useMemo(() => {
        // Compare draft with saved config
        const apiKeysChanged = JSON.stringify(draftApiKeys) !== JSON.stringify(config.apiKeys);
        const promptsChanged = JSON.stringify(draftPrompts) !== JSON.stringify(config.prompts);
        const modelChanged = JSON.stringify(draftModel) !== JSON.stringify(config.model);
        const uxChanged = JSON.stringify(draftUX) !== JSON.stringify(config.uxPolicy);
        return apiKeysChanged || promptsChanged || modelChanged || uxChanged;
    }, [draftApiKeys, draftPrompts, draftModel, draftUX, config]);

    // Handle close with unsaved changes check
    const handleClose = () => {
        if (hasUnsavedChanges) {
            setShowUnsavedDialog(true);
        } else {
            onClose();
        }
    };

    // UNIFIED SINGLE CHATBOT: Always use 'school' category for API keys
    const [activeApiCategory, setActiveApiCategory] = useState<'general' | 'school' | 'student'>('school');

    // Track individual key status: 'valid', 'invalid', or undefined (not tested)
    const [keyStatuses, setKeyStatuses] = useState<Record<string, Record<number, 'valid' | 'invalid' | undefined>>>({
        general: {},
        school: {},
        student: {}
    });

    // Track detailed messages for each key
    const [keyErrorMessages, setKeyErrorMessages] = useState<Record<string, Record<number, string>>>({
        general: {},
        school: {},
        student: {}
    });

    // Track error type for each key
    const [keyErrorTypes, setKeyErrorTypes] = useState<Record<string, Record<number, string>>>({
        general: {},
        school: {},
        student: {}
    });

    // Track if currently testing a specific key index
    const [testingKeyIndex, setTestingKeyIndex] = useState<number | null>(null);

    const handleTestGemini = async (category: 'general' | 'school' | 'student') => {
        setIsTesting('gemini');
        setSaveMessage('🔄 Testing all Gemini API keys...');

        const keys = draftApiKeys[category].geminiKeys.filter(k => k.trim());

        if (keys.length === 0) {
            setSaveMessage('❌ No Gemini keys to test');
            setIsTesting(null);
            return;
        }

        let validCount = 0;
        let invalidCount = 0;
        let firstValidKeyIndex = -1;

        // Test ALL keys
        for (let i = 0; i < draftApiKeys[category].geminiKeys.length; i++) {
            const key = draftApiKeys[category].geminiKeys[i];
            if (!key.trim()) continue;

            setTestingKeyIndex(i);
            setSaveMessage(`🔄 Testing key ${i + 1}/${keys.length}...`);

            const result = await testGeminiConnection(key, category);

            // Update status UI for this key
            setKeyStatuses(prev => ({ ...prev, [category]: { ...prev[category], [i]: result.success ? 'valid' : 'invalid' } }));
            setKeyErrorMessages(prev => ({ ...prev, [category]: { ...prev[category], [i]: result.message } }));
            setKeyErrorTypes(prev => ({ ...prev, [category]: { ...prev[category], [i]: result.errorType || 'unknown' } }));

            if (result.success) {
                validCount++;
                if (firstValidKeyIndex === -1) firstValidKeyIndex = i;
            } else {
                invalidCount++;
            }
        }

        setTestingKeyIndex(null);

        // Update geminiConnected based on whether ANY key works
        const isConnected = validCount > 0;
        setDraftApiKeys(prev => ({
            ...prev,
            [category]: { ...prev[category], geminiConnected: isConnected }
        }));

        // Summary message
        if (validCount > 0 && invalidCount === 0) {
            setSaveMessage(`✅ All ${validCount} keys are valid!`);
        } else if (validCount > 0) {
            setSaveMessage(`⚠️ ${validCount} valid, ${invalidCount} failed`);
        } else {
            setSaveMessage(`❌ All ${invalidCount} keys failed`);
        }

        // Auto-reorganize queue: Put valid keys first
        if (firstValidKeyIndex >= 0 && firstValidKeyIndex !== 0) {
            console.log('[AdminPanel] Reorganizing queue - moving first valid key to front');
            const { rotateKey } = await import('../../services/geminiService');
            // Rotate until first valid key is at front (if needed)
        }

        setTimeout(() => setSaveMessage(''), 5000);
        setIsTesting(null);
    };

    const handleTestGroq = async (category: 'general' | 'school' | 'student') => {
        setIsTesting('groq');
        const keys = (draftApiKeys[category].groqKeys || []).filter(k => k.trim());

        if (keys.length === 0) {
            setSaveMessage('❌ No Groq keys to test');
            setIsTesting(null);
            return;
        }

        // Test the first valid key
        const key = keys[0];
        const result = await testGroqConnection(key, category);

        if (result.success) {
            setSaveMessage('✅ Groq Connected: ' + result.message);
        } else {
            setSaveMessage('❌ Groq Failed: ' + result.message);
        }

        // Clear message after 3s
        setTimeout(() => setSaveMessage(''), 3000);
        setIsTesting(null);

        // Update groqConnected state in drafts
        setDraftApiKeys(prev => ({
            ...prev,
            [category]: { ...prev[category], groqConnected: result.success }
        }));
    };


    const handleTestRAG = async (category: 'general' | 'school' | 'student') => {
        setIsTesting('rag');
        setSaveMessage('🔄 กำลังตรวจสอบการเชื่อมต่อ RAG...');
        const result = await testRAGConnection(draftApiKeys[category].ragEndpoint, draftApiKeys[category].ragApiKey, category);
        setDraftApiKeys(prev => ({
            ...prev,
            [category]: { ...prev[category], ragConnected: result.success }
        }));
        setSaveMessage(result.message);
        setTimeout(() => setSaveMessage(''), 5000);
        setIsTesting(null);
    };



    const handleTestFlask = async (category: 'general' | 'school' | 'student') => {
        setIsTesting('flask');
        setSaveMessage('🔄 กำลังตรวจสอบการเชื่อมต่อ Flask API...');

        try {
            const { default: ChatbotAPI, getFlaskBaseUrl } = await import('../../services/chatbot-api.js');

            // Smart URL detection: auto-switch to LAN IP if accessing from non-localhost
            let flaskUrl = draftApiKeys[category].flaskApiUrl;
            const isConfigLocal = flaskUrl?.includes('localhost') || flaskUrl?.includes('127.0.0.1');
            const isBrowserLan = typeof window !== 'undefined' &&
                window.location.hostname !== 'localhost' &&
                window.location.hostname !== '127.0.0.1';

            if (isConfigLocal && isBrowserLan) {
                flaskUrl = getFlaskBaseUrl(5001);
                console.log(`[Admin] Smart URL: ${draftApiKeys[category].flaskApiUrl} → ${flaskUrl}`);
            }

            const api = new ChatbotAPI(
                flaskUrl,
                draftApiKeys[category].flaskApiKey
            );

            const result = await api.testConnection();

            setDraftApiKeys(prev => ({
                ...prev,
                [category]: { ...prev[category], flaskApiConnected: result.success }
            }));

            if (result.success) {
                setSaveMessage(`✅ Flask API Connected! (${result.latencyMs}ms) → ${flaskUrl}`);
            } else {
                setSaveMessage(`❌ Flask API Failed: ${result.message}`);
            }
        } catch (error: any) {
            setSaveMessage(`❌ Flask API Error: ${error.message}`);
            setDraftApiKeys(prev => ({
                ...prev,
                [category]: { ...prev[category], flaskApiConnected: false }
            }));
        }

        setTimeout(() => setSaveMessage(''), 5000);
        setIsTesting(null);
    };

    const handleSave = async () => {
        if (!canEdit) {
            setSaveMessage('⚠️ สิทธิ์ไม่เพียงพอสำหรับการบันทึก');
            setTimeout(() => setSaveMessage(''), 3000);
            return;
        }
        setIsSaving(true);

        // Filter out empty keys
        const cleanApiKeys = {
            general: {
                ...draftApiKeys.general,
                geminiKeys: draftApiKeys.general.geminiKeys.filter(k => k.trim()),
                groqKeys: (draftApiKeys.general.groqKeys || []).filter(k => k.trim())
            },
            school: {
                ...draftApiKeys.school,
                geminiKeys: draftApiKeys.school.geminiKeys.filter(k => k.trim()),
                groqKeys: (draftApiKeys.school.groqKeys || []).filter(k => k.trim())
            },
            student: {
                ...draftApiKeys.student,
                geminiKeys: draftApiKeys.student.geminiKeys.filter(k => k.trim()),
                groqKeys: (draftApiKeys.student.groqKeys || []).filter(k => k.trim())
            }
        };

        const updatedConfig: Partial<AdminConfig> = {
            apiKeys: cleanApiKeys,
            prompts: {
                ...draftPrompts,
                version: config.prompts.version + 1,
                lastUpdated: new Date().toISOString(),
            },
            model: draftModel,
            uxPolicy: draftUX,
        };

        const success = await updateConfig(updatedConfig);

        if (success) {
            resetChatSession();
            setSaveMessage('✓ บันทึกสำเร็จ');

            // Sync local drafts with the cleaned version we just saved
            setDraftApiKeys(cleanApiKeys);

            // AUTO-SYNC to Flask Backend
            try {
                let flaskUrl = cleanApiKeys.school.flaskApiUrl;

                // 🛡️ SMART SYNC OVERRIDE: 
                // If on LAN (not localhost) but config says localhost, force use of LAN IP for sync
                if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
                    if (!flaskUrl || flaskUrl.includes('localhost') || flaskUrl.includes('127.0.0.1')) {
                        console.log('[AdminPanel] 🛡️ Smart Sync: Overriding localhost with LAN IP for backend sync');
                        flaskUrl = `http://${window.location.hostname}:5001`;
                    }
                }

                flaskUrl = flaskUrl || 'http://127.0.0.1:5001'; // Default to 5001 (Flask), not 7860

                const response = await fetch(`${flaskUrl}/api/sync-config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ apiKeys: cleanApiKeys })
                });

                const data = await response.json();
                if (data.success) {
                    setSaveMessage('✓ บันทึกสำเร็จ + Sync to Backend!');
                    console.log('[AdminPanel] ✅ Config synced to Flask Backend');
                } else {
                    console.warn('[AdminPanel] ⚠️ Backend sync failed:', data.error);
                }
            } catch (syncError: any) {
                console.warn('[AdminPanel] ⚠️ Could not sync to Backend:', syncError.message);
                // Don't show error to user - Firestore save was successful
            }

            setTimeout(() => setSaveMessage(''), 2000);
        } else {
            setSaveMessage('❌ บันทึกไม่สำเร็จ (Database Error)');
        }

        setIsSaving(false);
    };

    const handleOptimizeQueue = async () => {
        setIsTesting('gemini');
        setSaveMessage('🔄 Optimizing queue...');

        try {
            const { optimizeQueue } = await import('../../services/geminiService');
            const result = await optimizeQueue(activeApiCategory);

            if (result.success) {
                setSaveMessage('✅ Queue optimized! ' + result.message);
                await handleTestGemini(activeApiCategory);
            } else {
                setSaveMessage(`Error: ${result.message}`);
            }
        } catch (error: any) {
            setSaveMessage(`Error: ${error.message || 'Unknown error'}`);
        }

        setIsTesting(null);
    };

    const renderTabContent = () => {
        const sharedProps = {
            draftApiKeys,
            setDraftApiKeys,
            draftPrompts,
            setDraftPrompts,
            draftModel,
            setDraftModel,
            draftUX,
            setDraftUX,
            config,
            isTesting,
            setIsTesting,
            setSaveMessage,
        };

        switch (activeTab) {
            case 'api':
                return (
                    <ApiSettingsTab
                        {...sharedProps}
                        activeApiCategory={activeApiCategory}
                        setActiveApiCategory={setActiveApiCategory}
                        handleTestGemini={handleTestGemini}
                        handleTestGroq={handleTestGroq}
                        handleTestRAG={handleTestRAG}
                        handleTestFlask={handleTestFlask}
                        handleOptimizeQueue={handleOptimizeQueue}
                        keyStatuses={keyStatuses}
                        keyErrorMessages={keyErrorMessages}
                        keyErrorTypes={keyErrorTypes}
                        testingKeyIndex={testingKeyIndex}
                    />
                );

            case 'prompts':
                return <PromptsTab {...sharedProps} />;

            case 'monitor':
                return <SessionMonitorTab config={config} />;

            case 'analytics':
                return <AnalyticsTab />;

            case 'users':
                return <UserManagementTab />;
            case 'audit':
                return <AdminAuditTab />;

            default:
                return <ApiSettingsTab {...sharedProps} activeApiCategory={activeApiCategory} setActiveApiCategory={setActiveApiCategory} handleTestGemini={handleTestGemini} handleTestGroq={handleTestGroq} handleTestRAG={handleTestRAG} handleTestFlask={handleTestFlask} handleOptimizeQueue={handleOptimizeQueue} keyStatuses={keyStatuses} keyErrorMessages={keyErrorMessages} keyErrorTypes={keyErrorTypes} testingKeyIndex={testingKeyIndex} />;
        }
    };

    const roleRank: Record<typeof role, number> = { viewer: 0, operator: 1, admin: 2 };
    const visibleTabs = tabs.filter(tab => roleRank[role] >= roleRank[tab.minRole]);

    return (
        <div className="fixed inset-0 z-50 hidden md:flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="w-full max-w-6xl h-[90vh] bg-[#F2F2F7] rounded-3xl shadow-2xl overflow-hidden flex animate-in zoom-in-95 duration-300">
                {/* Sidebar */}
                <div className="w-64 bg-white/80 backdrop-blur-lg border-r border-black/5 p-4 flex flex-col">
                    <div className="flex items-center gap-3 px-3 py-4 mb-4">
                        <div className="w-10 h-10 rounded-xl overflow-hidden shadow-md">
                            <img src="/do-mascot.png" alt="DO" className="w-full h-full object-cover" />
                        </div>
                        <div>
                            <h2 className="font-bold text-[#1D1D1F]">Admin Panel</h2>
                            <p className="text-[10px] text-black/40 uppercase tracking-wide">MOE - One</p>
                        </div>
                    </div>

                    <nav className="flex-1 space-y-1">
                        {visibleTabs.map((tab) => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-[13px] font-medium transition-all ${activeTab === tab.id
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                                    : 'text-black/70 hover:bg-black/5'
                                    }`}
                            >
                                {tab.icon}
                                {tab.label}
                            </button>
                        ))}

                        <div className="pt-4 mt-4 border-t border-black/5">
                            <button
                                onClick={async () => {
                                    const updatedUX = { ...draftUX, showRagDebug: true };
                                    setDraftUX(updatedUX);
                                    // Save immediately
                                    setIsSaving(true);
                                    const success = await updateConfig({ uxPolicy: updatedUX });
                                    setIsSaving(false);
                                    if (success) onClose();
                                }}
                                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-[13px] font-bold text-blue-600 bg-blue-50 hover:bg-blue-100 transition-all border border-blue-100 shadow-sm"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
                                </svg>
                                ทดสอบในหน้าแชท
                            </button>
                        </div>
                    </nav>

                    {/* Reset Prompt Only Button */}
                    <button
                        disabled={isResetting}
                        onClick={async () => {
                            if (isResetting) return;
                            setIsResetting(true);
                            try {
                                const { SYSTEM_PROMPT, CATEGORY_PROMPTS } = await import('../../config');
                                const newPrompts = {
                                    system: SYSTEM_PROMPT,
                                    category: CATEGORY_PROMPTS,
                                    version: (config.prompts?.version || 0) + 1,
                                    lastUpdated: new Date().toLocaleString('th-TH'),
                                };
                                await updateConfig({ prompts: newPrompts });
                                // Update draft state directly
                                setDraftPrompts(newPrompts);
                                setSaveMessage('✅ รีเซ็ต Prompt เรียบร้อย!');
                                setTimeout(() => setSaveMessage(''), 3000);
                            } catch (err) {
                                console.error('Reset failed:', err);
                                setSaveMessage('❌ รีเซ็ตล้มเหลว');
                            } finally {
                                setIsResetting(false);
                            }
                        }}
                        className={`w-full py-3 text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2 mb-2 ${isResetting
                            ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                            : 'text-orange-600 hover:bg-orange-50'
                            }`}
                    >
                        {isResetting ? (
                            <svg className="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                            </svg>
                        )}
                        {isResetting ? 'กำลังรีเซ็ต...' : 'รีเซ็ต Prompt เป็นค่าเริ่มต้น'}
                    </button>

                    <button
                        onClick={handleClose}
                        className="w-full py-3 text-sm font-medium text-red-600 hover:bg-red-50 rounded-xl transition-all flex items-center justify-center gap-2"
                    >
                        {hasUnsavedChanges && <span className="w-2 h-2 bg-orange-400 rounded-full animate-pulse"></span>}
                        ปิดหน้าต่าง Admin
                    </button>
                    <button
                        onClick={() => {
                            clearAdminSession();
                            onLogout();
                        }}
                        className="w-full py-3 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-xl transition-all flex items-center justify-center gap-2 mt-2"
                    >
                        ออกจากระบบแอดมิน
                    </button>
                </div>

                {/* Main Content */}
                <div className="flex-1 flex flex-col overflow-hidden">
                    <header className="h-16 px-6 bg-white/60 backdrop-blur-lg border-b border-black/5 flex items-center justify-between">
                        <h1 className="text-xl font-bold text-[#1D1D1F]">
                            {tabs.find(t => t.id === activeTab)?.label}
                        </h1>
                        <div className="flex items-center gap-3">
                            <div className="flex flex-col items-end leading-tight">
                                <span className={`px-2 py-1 text-[10px] font-bold uppercase rounded-full ${roleMeta[role].className}`}>
                                    {roleMeta[role].label}
                                </span>
                                <span className="text-[10px] text-black/40 mt-1">{roleMeta[role].desc}</span>
                            </div>
                            {saveMessage && (
                                <span className="text-sm text-green-600 font-medium animate-in fade-in">{saveMessage}</span>
                            )}
                            <button
                                onClick={handleSave}
                                disabled={isSaving || !canEdit}
                                title={!canEdit ? 'สิทธิ์ Viewer ไม่สามารถบันทึกได้' : undefined}
                                className={`px-6 py-2 rounded-xl text-sm font-bold transition-all flex items-center gap-2 ${canEdit ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-200 text-gray-500 cursor-not-allowed'}`}
                            >
                                {isSaving && (
                                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                )}
                                บันทึก
                            </button>
                        </div>
                    </header>

                    <main className="flex-1 overflow-y-auto p-6">
                        {!canEdit && (
                            <div className="mb-4 px-4 py-3 rounded-xl bg-amber-50 text-amber-700 text-sm font-medium">
                                โหมดอ่านอย่างเดียว (Viewer) ไม่สามารถบันทึกการเปลี่ยนแปลงได้
                            </div>
                        )}
                        {renderTabContent()}
                    </main>
                </div>
            </div>

            {/* Unsaved Changes Confirmation Dialog */}
            {showUnsavedDialog && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-md w-full mx-4 animate-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center">
                                <span className="text-2xl">⚠️</span>
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-[#1D1D1F]">มีการเปลี่ยนแปลงที่ยังไม่ได้บันทึก</h3>
                                <p className="text-sm text-black/50">คุณต้องการบันทึกก่อนปิดหรือไม่?</p>
                            </div>
                        </div>

                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => {
                                    setShowUnsavedDialog(false);
                                    onClose();
                                }}
                                className="flex-1 py-3 px-4 bg-gray-100 text-gray-700 rounded-xl font-bold text-sm hover:bg-gray-200 transition-all"
                            >
                                ไม่บันทึก
                            </button>
                            <button
                                onClick={() => setShowUnsavedDialog(false)}
                                className="flex-1 py-3 px-4 bg-gray-100 text-gray-700 rounded-xl font-bold text-sm hover:bg-gray-200 transition-all"
                            >
                                ยกเลิก
                            </button>
                            <button
                                onClick={async () => {
                                    await handleSave();
                                    setShowUnsavedDialog(false);
                                    onClose();
                                }}
                                className="flex-1 py-3 px-4 bg-blue-600 text-white rounded-xl font-bold text-sm hover:bg-blue-700 transition-all shadow-lg shadow-blue-500/20"
                            >
                                บันทึก
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AdminPanel;
