import React from 'react';
import { ApiSettingsTabProps } from './types';
import { AdminConfig } from '../../../contexts/AdminConfigContext';

const ApiSettingsTab: React.FC<ApiSettingsTabProps> = ({
    draftApiKeys,
    setDraftApiKeys,
    activeApiCategory,
    setActiveApiCategory,
    handleTestGemini,
    handleTestGroq,
    handleTestRAG,
    handleTestFlask,
    handleTestProvider,
    handleOptimizeQueue,
    isTesting,
    keyStatuses,
    keyErrorMessages,
    keyErrorTypes,
    testingKeyIndex,
    config,
}) => {
    const updateDraftApiKey = (
        category: 'general' | 'school' | 'student',
        field: keyof AdminConfig['apiKeys']['general'],
        value: string | number | boolean
    ) => {
        setDraftApiKeys(prev => ({
            ...prev,
            [category]: { ...prev[category], [field]: value }
        }));
    };

    return (
        <div className="space-y-6">
            {/* UNIFIED SINGLE CHATBOT - No category tabs needed */}
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-4 rounded-xl border border-blue-200">
                <p className="text-sm font-medium text-blue-800">
                    ✨ <strong>Unified Mode:</strong> API Keys ทั้งหมดใช้ร่วมกันสำหรับทุกคำถาม
                </p>
            </div>

            {/* Groq API Keys (Primary) */}
            <div className="bg-white p-6 rounded-2xl border border-black/5">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-orange-500 flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-5 h-5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
                            </svg>
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-[#1D1D1F]">Groq API Keys (Primary)</h3>
                            <p className="text-xs text-black/50">Llama-3.3-70b-versatile (Priority 1)</p>
                        </div>
                    </div>
                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${draftApiKeys[activeApiCategory].groqConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
                        <div className={`w-2 h-2 rounded-full ${draftApiKeys[activeApiCategory].groqConnected ? 'bg-green-500' : 'bg-red-500'} ${isTesting === 'groq' ? 'animate-ping' : ''}`}></div>
                        <span className="text-xs font-bold">{draftApiKeys[activeApiCategory].groqConnected ? 'Connected' : 'Disconnected'}</span>
                    </div>
                </div>

                <div className="space-y-3">
                    {(draftApiKeys[activeApiCategory]?.groqKeys || []).map((key, index) => (
                        <div key={`groq-${index}`} className="flex gap-2 relative group">
                            <div className="flex-1 relative">
                                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-black/20 text-xs font-bold font-mono">
                                    #{index + 1}
                                </div>
                                <input
                                    type="password"
                                    name={`groq_key_${index}_${Date.now()}`}
                                    autoComplete="new-password"
                                    value={key}
                                    onChange={(e) => {
                                        const newKeys = [...(draftApiKeys[activeApiCategory].groqKeys || [])];
                                        newKeys[index] = e.target.value;
                                        setDraftApiKeys(prev => ({
                                            ...prev,
                                            [activeApiCategory]: { ...prev[activeApiCategory], groqKeys: newKeys }
                                        }));
                                    }}
                                    placeholder="gsk_..."
                                    className={`w-full pl-12 pr-10 py-3 bg-[#F5F5F7] border-none rounded-xl text-[14px] font-mono font-medium focus:ring-2 focus:ring-orange-500/20 transition-all`}
                                />
                            </div>
                            <button
                                onClick={() => {
                                    const newKeys = (draftApiKeys[activeApiCategory].groqKeys || []).filter((_, i) => i !== index);
                                    setDraftApiKeys(prev => ({
                                        ...prev,
                                        [activeApiCategory]: { ...prev[activeApiCategory], groqKeys: newKeys }
                                    }));
                                }}
                                className="w-10 h-[46px] flex items-center justify-center bg-red-50 text-red-500 rounded-xl hover:bg-red-100 transition-colors"
                                title="Remove Key"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                                    <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 001.5.06l.3-7.5z" clipRule="evenodd" />
                                </svg>
                            </button>
                        </div>
                    ))}
                </div>

                <button
                    onClick={() => {
                        setDraftApiKeys({
                            ...draftApiKeys,
                            [activeApiCategory]: {
                                ...draftApiKeys[activeApiCategory],
                                groqKeys: [...(draftApiKeys[activeApiCategory].groqKeys || []), '']
                            }
                        });
                    }}
                    className="w-full mt-4 py-3 border border-dashed border-black/20 rounded-xl text-black/40 text-sm font-bold hover:bg-black/5 hover:border-black/40 transition-all flex items-center justify-center gap-2"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                    </svg>
                    Add Groq API Key
                </button>

                <div className="mt-6 pt-6 border-t border-black/5">
                    <button
                        onClick={() => handleTestGroq(activeApiCategory)}
                        disabled={!draftApiKeys[activeApiCategory].groqKeys?.some(k => k.trim()) || isTesting === 'groq'}
                        className="w-full py-3 bg-orange-600 text-white rounded-xl text-sm font-bold hover:bg-orange-700 transition-all shadow-lg shadow-orange-500/20 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isTesting === 'groq' ? (
                            <>
                                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Testing Connection...
                            </>
                        ) : (
                            <>
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                                </svg>
                                Test Active Key
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* === Additional Providers (OpenAI-Compatible) === */}
            {[
                { id: 'openai' as const, label: 'OpenAI', model: 'GPT-4o-mini', color: 'emerald', icon: '🤖', keyPrefix: 'sk-' },
                { id: 'deepseek' as const, label: 'DeepSeek', model: 'DeepSeek-V3', color: 'cyan', icon: '🔮', keyPrefix: 'sk-' },
                { id: 'mistral' as const, label: 'Mistral', model: 'Mistral-Small', color: 'amber', icon: '🌪️', keyPrefix: '' },
                { id: 'together' as const, label: 'Together AI', model: 'Llama-3.3-70B', color: 'violet', icon: '🤝', keyPrefix: '' },
                { id: 'openrouter' as const, label: 'OpenRouter', model: 'Multi-Model', color: 'rose', icon: '🔄', keyPrefix: 'sk-or-' },
            ].map(provider => {
                const keysField = `${provider.id}Keys` as keyof typeof draftApiKeys[typeof activeApiCategory];
                const connectedField = `${provider.id}Connected` as keyof typeof draftApiKeys[typeof activeApiCategory];
                const keys = (draftApiKeys[activeApiCategory]?.[keysField] as string[] | undefined) || [];
                const isConnected = draftApiKeys[activeApiCategory]?.[connectedField] as boolean | undefined;
                const colorMap: Record<string, string> = {
                    emerald: 'bg-emerald-500', cyan: 'bg-cyan-500', amber: 'bg-amber-500',
                    violet: 'bg-violet-500', rose: 'bg-rose-500'
                };
                return (
                    <div key={provider.id} className="bg-white p-5 rounded-2xl border border-black/5">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`w-9 h-9 rounded-xl ${colorMap[provider.color]} flex items-center justify-center text-white text-base`}>
                                    {provider.icon}
                                </div>
                                <div>
                                    <h3 className="font-bold text-[#1D1D1F] text-[15px]">{provider.label}</h3>
                                    <p className="text-[11px] text-black/40">{provider.model}</p>
                                </div>
                            </div>
                            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold ${keys.length > 0 && isConnected ? 'bg-green-100 text-green-700' :
                                keys.length > 0 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-400'
                                }`}>
                                <div className={`w-1.5 h-1.5 rounded-full ${keys.length > 0 && isConnected ? 'bg-green-500' :
                                    keys.length > 0 ? 'bg-yellow-500' : 'bg-gray-300'
                                    }`} />
                                {keys.length > 0 && isConnected ? 'Connected' : keys.length > 0 ? `${keys.length} key${keys.length > 1 ? 's' : ''}` : 'No Key'}
                            </div>
                        </div>

                        <div className="mt-3 space-y-2">
                            {keys.map((key: string, index: number) => (
                                <div key={`${provider.id}-${index}`} className="flex gap-2">
                                    <input
                                        type="password"
                                        autoComplete="new-password"
                                        value={key}
                                        onChange={(e) => {
                                            const newKeys = [...keys];
                                            newKeys[index] = e.target.value;
                                            setDraftApiKeys(prev => ({
                                                ...prev,
                                                [activeApiCategory]: { ...prev[activeApiCategory], [keysField]: newKeys }
                                            }));
                                        }}
                                        placeholder={provider.keyPrefix ? `${provider.keyPrefix}...` : 'API Key...'}
                                        className="flex-1 px-3 py-2.5 bg-[#F5F5F7] border-none rounded-xl text-[13px] font-mono focus:ring-2 focus:ring-blue-500/20"
                                    />
                                    <button
                                        onClick={() => {
                                            const newKeys = keys.filter((_: string, i: number) => i !== index);
                                            setDraftApiKeys(prev => ({
                                                ...prev,
                                                [activeApiCategory]: { ...prev[activeApiCategory], [keysField]: newKeys }
                                            }));
                                        }}
                                        className="w-9 h-[42px] flex items-center justify-center bg-red-50 text-red-500 rounded-xl hover:bg-red-100 transition-colors text-sm"
                                    >
                                        ×
                                    </button>
                                </div>
                            ))}
                        </div>

                        <button
                            onClick={() => {
                                setDraftApiKeys(prev => ({
                                    ...prev,
                                    [activeApiCategory]: {
                                        ...prev[activeApiCategory],
                                        [keysField]: [...keys, '']
                                    }
                                }));
                            }}
                            className="w-full mt-3 py-2 border border-dashed border-black/15 rounded-xl text-black/35 text-xs font-bold hover:bg-black/5 transition-all flex items-center justify-center gap-1.5"
                        >
                            + Add {provider.label} Key
                        </button>

                        {/* Test Connection Button */}
                        {keys.some((k: string) => k.trim()) && (
                            <button
                                onClick={() => handleTestProvider(provider.id, activeApiCategory)}
                                disabled={isTesting === provider.id}
                                className={`w-full mt-2 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${isConnected
                                        ? 'bg-green-50 text-green-700 border border-green-200 hover:bg-green-100'
                                        : `bg-gradient-to-r from-${provider.color}-500 to-${provider.color}-600 text-white shadow-sm hover:shadow-md`
                                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                                style={!isConnected ? {
                                    background: provider.color === 'emerald' ? 'linear-gradient(to right, #10b981, #059669)' :
                                        provider.color === 'cyan' ? 'linear-gradient(to right, #06b6d4, #0891b2)' :
                                            provider.color === 'amber' ? 'linear-gradient(to right, #f59e0b, #d97706)' :
                                                provider.color === 'violet' ? 'linear-gradient(to right, #8b5cf6, #7c3aed)' :
                                                    'linear-gradient(to right, #f43f5e, #e11d48)',
                                    color: 'white'
                                } : {}}
                            >
                                {isTesting === provider.id ? (
                                    <>
                                        <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                        </svg>
                                        Testing...
                                    </>
                                ) : isConnected ? (
                                    <>
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        ✓ Connected — Test Again
                                    </>
                                ) : (
                                    <>
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                                        </svg>
                                        Test {provider.label} Connection
                                    </>
                                )}
                            </button>
                        )}
                    </div>
                );
            })}

            {/* Gemini API Keys (Backup) */}
            <div className="bg-white p-6 rounded-2xl border border-black/5">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-500 flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-5 h-5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                            </svg>
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-[#1D1D1F]">Gemini API Keys (Backup)</h3>
                            <p className="text-xs text-black/50">Gemini 1.5 Flash (Priority 2)</p>
                        </div>
                    </div>
                    {/* Connection badge - shows Connected if ANY key is valid */}
                    {(() => {
                        const hasAnyValidKey = Object.values(keyStatuses[activeApiCategory] || {}).some(status => status === 'valid');
                        const isConnected = hasAnyValidKey || draftApiKeys[activeApiCategory].geminiConnected;
                        return (
                            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${isConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
                                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'} ${isTesting === 'gemini' ? 'animate-ping' : ''}`}></div>
                                <span className="text-xs font-bold">{isConnected ? 'Connected' : 'Disconnected'}</span>
                            </div>
                        );
                    })()}
                </div>

                <div className="space-y-2">
                    {(draftApiKeys[activeApiCategory]?.geminiKeys || []).map((key, index) => {
                        const status = keyStatuses[activeApiCategory]?.[index];
                        const errorMsg = keyErrorMessages[activeApiCategory]?.[index];
                        const errorType = keyErrorTypes[activeApiCategory]?.[index];

                        return (
                            <div key={`gemini-${index}`} className={`flex items-center gap-2 p-2 rounded-xl border transition-all ${status === 'valid' ? 'bg-green-50 border-green-200' :
                                status === 'invalid' ? 'bg-red-50 border-red-200' :
                                    'bg-[#F5F5F7] border-transparent'
                                }`}>
                                {/* Status Icon */}
                                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${status === 'valid' ? 'bg-green-100 text-green-600' :
                                    status === 'invalid' ? 'bg-red-100 text-red-500' :
                                        'bg-gray-100 text-gray-400'
                                    }`}>
                                    {status === 'valid' ? (
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                        </svg>
                                    ) : status === 'invalid' ? (
                                        <span className="text-sm">{errorType === 'quota_daily' ? '⚠️' : '❌'}</span>
                                    ) : (
                                        <span className="text-xs font-bold text-gray-400">#{index + 1}</span>
                                    )}
                                </div>

                                {/* Key Input & Status */}
                                <div className="flex-1 min-w-0">
                                    <input
                                        type="text"
                                        name={`gemini_key_${index}_${Date.now()}`}
                                        autoComplete="off"
                                        value={key}
                                        onChange={(e) => {
                                            const newKeys = [...draftApiKeys[activeApiCategory].geminiKeys];
                                            newKeys[index] = e.target.value;
                                            setDraftApiKeys({
                                                ...draftApiKeys,
                                                [activeApiCategory]: { ...draftApiKeys[activeApiCategory], geminiKeys: newKeys }
                                            });
                                        }}
                                        placeholder="วาง API Key..."
                                        className="w-full px-3 py-1.5 bg-white/80 border-none rounded-lg text-[12px] font-mono focus:ring-2 focus:ring-blue-500/20 truncate"
                                    />
                                    {/* Inline Status Message */}
                                    {status && (
                                        <p className={`text-[10px] mt-1 truncate ${status === 'valid' ? 'text-green-600' : 'text-red-500'}`}>
                                            {status === 'valid' ? '✅ พร้อมใช้งาน' : (errorMsg || 'โควต้าเต็ม')}
                                        </p>
                                    )}
                                </div>

                                {/* Actions */}
                                <button
                                    onClick={() => handleTestGemini(activeApiCategory)}
                                    disabled={!key || isTesting === 'gemini'}
                                    className="px-3 py-1.5 bg-white border border-black/10 hover:bg-gray-50 rounded-lg text-xs font-bold transition-all whitespace-nowrap"
                                >
                                    {testingKeyIndex === index && isTesting === 'gemini' ? '...' : 'Test'}
                                </button>
                                <button
                                    onClick={() => {
                                        const newKeys = draftApiKeys[activeApiCategory].geminiKeys.filter((_, i) => i !== index);
                                        setDraftApiKeys({
                                            ...draftApiKeys,
                                            [activeApiCategory]: { ...draftApiKeys[activeApiCategory], geminiKeys: newKeys }
                                        });
                                    }}
                                    className="w-8 h-8 flex items-center justify-center bg-red-50 text-red-500 rounded-lg hover:bg-red-100 transition-all"
                                >
                                    ×
                                </button>
                            </div>
                        );
                    })}
                </div>

                <button
                    onClick={() => {
                        setDraftApiKeys({
                            ...draftApiKeys,
                            [activeApiCategory]: {
                                ...draftApiKeys[activeApiCategory],
                                geminiKeys: [...draftApiKeys[activeApiCategory].geminiKeys, '']
                            }
                        });
                    }}
                    className="w-full mt-4 py-3 border border-dashed border-black/20 rounded-xl text-black/40 text-sm font-bold hover:bg-black/5 hover:border-black/40 transition-all flex items-center justify-center gap-2"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                    </svg>
                    Add Another API Key
                </button>

                <div className="flex gap-3 mt-8 pt-6 border-t border-black/5">
                    <button
                        onClick={handleOptimizeQueue}
                        disabled={isTesting === 'gemini'}
                        className="flex-1 py-3 bg-white border border-purple-200 text-purple-700 hover:bg-purple-50 rounded-xl text-sm font-bold transition-all shadow-sm flex items-center justify-center gap-2"
                    >
                        {isTesting === 'gemini' ? "Testing All..." : "Optimize & Fix Queue"}
                    </button>
                    <button
                        onClick={() => handleTestGemini(activeApiCategory)}
                        disabled={draftApiKeys[activeApiCategory].geminiKeys.length === 0 || isTesting === 'gemini'}
                        className="flex-1 py-3 bg-blue-600 text-white rounded-xl text-sm font-bold hover:bg-blue-700 transition-all shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2"
                    >
                        {isTesting === 'gemini' ? "Testing Active Key..." : "Test Active Key"}
                    </button>
                </div>

                <p className="text-xs text-black/40 mt-3">
                    ℹ️ ระบบจะลอง Provider ตามลำดับ: Groq → OpenAI → DeepSeek → Mistral → Together → OpenRouter → Gemini (backup สุดท้าย)
                </p>
            </div>


            {/* Flask Chatbot API Section (for School/Student) */}
            {(activeApiCategory === 'school' || activeApiCategory === 'student') && (
                <div className="bg-white p-6 rounded-2xl border border-black/5">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-xl ${draftApiKeys[activeApiCategory].flaskApiEnabled ? 'bg-purple-600' : 'bg-gray-300'} flex items-center justify-center transition-colors`}>
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-5 h-5">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                                </svg>
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-[#1D1D1F]">🐍 Flask Chatbot API</h3>
                                <p className="text-xs text-black/50">สำหรับข้อมูล{activeApiCategory === 'school' ? 'โรงเรียน (DMC)' : 'นักเรียน (CCT)'} จาก Database จริง</p>
                            </div>
                        </div>
                        <button
                            onClick={() => updateDraftApiKey(activeApiCategory, 'flaskApiEnabled', !draftApiKeys[activeApiCategory].flaskApiEnabled)}
                            className={`px-4 py-2 rounded-full text-xs font-bold transition-all ${draftApiKeys[activeApiCategory].flaskApiEnabled
                                ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/30'
                                : 'bg-gray-100 text-gray-500'
                                }`}
                        >
                            {draftApiKeys[activeApiCategory].flaskApiEnabled ? '✓ Enabled' : 'Disabled'}
                        </button>
                    </div>

                    <div className="space-y-4">
                        {/* Flask API URL */}
                        <div>
                            <label className="text-xs font-bold text-black/40 uppercase tracking-wider ml-1">Flask API URL</label>
                            <div className="flex gap-2 mt-1">
                                <input
                                    type="text"
                                    value={draftApiKeys[activeApiCategory].flaskApiUrl || ''}
                                    onChange={(e) => updateDraftApiKey(activeApiCategory, 'flaskApiUrl', e.target.value)}
                                    placeholder="https://your-flask-api.com"
                                    className="flex-1 px-4 py-3 bg-[#F5F5F7] border-none rounded-xl text-[14px] font-mono focus:ring-2 focus:ring-purple-500/20"
                                    disabled={!draftApiKeys[activeApiCategory].flaskApiEnabled}
                                />
                                <button
                                    onClick={() => {
                                        const currentHost = window.location.hostname;
                                        const detectedUrl = currentHost === 'localhost' || currentHost === '127.0.0.1'
                                            ? 'http://127.0.0.1:5001'
                                            : `http://${currentHost}:5001`;
                                        updateDraftApiKey(activeApiCategory, 'flaskApiUrl', detectedUrl);
                                        setDraftApiKeys(prev => ({
                                            ...prev,
                                            school: { ...prev.school, flaskApiUrl: detectedUrl },
                                            student: { ...prev.student, flaskApiUrl: detectedUrl }
                                        }));
                                    }}
                                    disabled={!draftApiKeys[activeApiCategory].flaskApiEnabled}
                                    className="px-4 py-3 bg-gradient-to-r from-purple-500 to-indigo-500 text-white rounded-xl text-sm font-bold hover:shadow-lg hover:shadow-purple-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                                    title="ตรวจจับ IP อัตโนมัติตาม Network ปัจจุบัน"
                                >
                                    🔍 Auto IP
                                </button>
                            </div>
                            <p className="text-[10px] text-black/40 mt-1 ml-1">
                                💡 กดปุ่ม "Auto IP" เพื่อตรวจจับ IP อัตโนมัติตาม Network ที่ใช้งานอยู่
                            </p>
                        </div>

                        {/* Flask API Key */}
                        <div>
                            <label className="text-xs font-bold text-black/40 uppercase tracking-wider ml-1">API Key (Optional)</label>
                            <input
                                type="password"
                                name="flask_api_key_nomoreautofill"
                                autoComplete="new-password"
                                value={draftApiKeys[activeApiCategory].flaskApiKey || ''}
                                onChange={(e) => updateDraftApiKey(activeApiCategory, 'flaskApiKey', e.target.value)}
                                placeholder="X-API-Key header value"
                                className="w-full mt-1 px-4 py-3 bg-[#F5F5F7] border-none rounded-xl text-[14px] font-mono focus:ring-2 focus:ring-purple-500/20"
                                disabled={!draftApiKeys[activeApiCategory].flaskApiEnabled}
                            />
                        </div>

                        {/* Timeout */}
                        <div>
                            <label className="text-xs font-bold text-black/40 uppercase tracking-wider ml-1">Timeout (ms)</label>
                            <input
                                type="number"
                                value={draftApiKeys[activeApiCategory].flaskApiTimeout || 30000}
                                onChange={(e) => updateDraftApiKey(activeApiCategory, 'flaskApiTimeout', parseInt(e.target.value) || 30000)}
                                placeholder="30000"
                                className="w-full mt-1 px-4 py-3 bg-[#F5F5F7] border-none rounded-xl text-[14px] font-mono focus:ring-2 focus:ring-purple-500/20"
                                disabled={!draftApiKeys[activeApiCategory].flaskApiEnabled}
                            />
                            <p className="text-[10px] text-black/40 mt-1 ml-1">เวลารอสูงสุด (แนะนำ: 30000 = 30 วินาที)</p>
                        </div>
                    </div>

                    <div className="mt-4 p-4 rounded-xl bg-purple-50 border border-purple-100">
                        <p className="text-xs text-purple-800 font-medium">
                            🚀 <strong>Production Ready:</strong> เมื่อเปิดใช้งาน ระบบจะเรียก Flask API ก่อน ถ้า fail จะ fallback ไป Groq/Gemini อัตโนมัติ (Retry 3 ครั้ง)
                        </p>
                    </div>

                    {/* Test Connection Button */}
                    <button
                        onClick={() => handleTestFlask(activeApiCategory)}
                        disabled={!draftApiKeys[activeApiCategory].flaskApiUrl || !draftApiKeys[activeApiCategory].flaskApiEnabled || isTesting === 'flask'}
                        className={`w-full mt-4 py-3.5 rounded-xl text-sm font-bold transition-all shadow-lg flex items-center justify-center gap-2 ${draftApiKeys[activeApiCategory].flaskApiConnected
                            ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-green-500/20'
                            : 'bg-gradient-to-r from-purple-500 to-indigo-600 text-white shadow-purple-500/20 hover:from-purple-600 hover:to-indigo-700'
                            } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                        {isTesting === 'flask' ? (
                            <>
                                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Testing Connection...
                            </>
                        ) : draftApiKeys[activeApiCategory].flaskApiConnected ? (
                            <>
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                ✓ Connected - Test Again
                            </>
                        ) : (
                            <>
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                                </svg>
                                Test Flask API Connection
                            </>
                        )}
                    </button>
                </div>
            )}

            {/* Info Card */}
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-6 rounded-2xl border border-blue-100">
                <h4 className="font-bold text-[#1D1D1F] mb-2">💡 วิธีใช้งาน — Multi-Provider</h4>
                <ul className="text-sm text-black/60 space-y-1.5">
                    <li>• <strong>Groq (ฟรี):</strong> เร็วมาก ⚡ แนะนำเป็น Primary</li>
                    <li>• <strong>OpenAI:</strong> GPT-4o-mini คุณภาพสูง (เสียเงิน)</li>
                    <li>• <strong>DeepSeek (ถูก):</strong> ราคาประหยัด คุณภาพดี 🇨🇳</li>
                    <li>• <strong>Mistral:</strong> เร็วดี รองรับหลายภาษา 🇫🇷</li>
                    <li>• <strong>Together AI (ฟรีมี):</strong> Llama 3.3 70B โอเพ่นซอร์ส</li>
                    <li>• <strong>OpenRouter:</strong> Gateway ใช้ได้ทุกโมเดล 🔄</li>
                    <li>• <strong>Gemini (ฟรี):</strong> Backup ตัวสุดท้ายเมื่อทุกค่ายล่ม</li>
                </ul>
                <p className="text-xs text-black/40 mt-2">ระบบจะลองค่ายตามลำดับ Priority อัตโนมัติ ถ้าค่ายแรกล่มจะสลับไปค่ายถัดไปทันที</p>
            </div>
        </div >
    );
};

export default ApiSettingsTab;
