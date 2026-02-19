import React from 'react';
import { ModelConfigTabProps } from './types';

const ModelConfigTab: React.FC<ModelConfigTabProps> = ({
    draftModel,
    setDraftModel,
    draftApiKeys,
    supportedModelsByCategory,
}) => {
    const currentModel = draftModel.name;

    const getCompatibilityStatus = (cat: 'general' | 'school' | 'student') => {
        // If no API keys configured for this category, return 'none' (don't show badge)
        const hasKeys = draftApiKeys[cat].geminiKeys.length > 0 && draftApiKeys[cat].geminiKeys.some(k => k.trim());
        if (!hasKeys) return 'none';

        // If not connected (not tested yet), return 'untested'
        if (!draftApiKeys[cat].geminiConnected) return 'untested';

        const supported = supportedModelsByCategory[cat] || [];

        // If no supported models detected yet, but connected = success (trust the test)
        if (supported.length === 0 && draftApiKeys[cat].geminiConnected) return 'success';

        // Fuzzy match: gemini-2.0-flash-001 should match gemini-2.0-flash
        const modelBase = currentModel.replace(/-\d{3}$/, ''); // Remove -001, -002 suffix
        const isSupported = supported.some(m =>
            m === currentModel ||
            m === modelBase ||
            m.startsWith(modelBase) ||
            currentModel.startsWith(m)
        );

        return isSupported ? 'success' : 'warning';
    };

    return (
        <div className="space-y-6">
            <div className="bg-white p-6 rounded-2xl border border-black/5">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-bold text-[#1D1D1F]">Model Selection</h3>
                    <div className="flex gap-2">
                        {(['general', 'school', 'student'] as const).map(cat => {
                            const status = getCompatibilityStatus(cat);
                            // Don't show badge if no API keys configured
                            if (status === 'none') return null;
                            return (
                                <div
                                    key={cat}
                                    title={`${cat.toUpperCase()}: ${status === 'success' ? 'รองรับ ✓' : status === 'untested' ? 'ยังไม่ได้ทดสอบ' : 'ต้องตรวจสอบ'}`}
                                    className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${status === 'success' ? 'bg-green-100 text-green-700' :
                                        status === 'untested' ? 'bg-blue-100 text-blue-600' :
                                            status === 'warning' ? 'bg-amber-100 text-amber-700' :
                                                'bg-gray-100 text-gray-400'
                                        }`}
                                >
                                    {cat[0]}
                                </div>
                            );
                        })}
                    </div>
                </div>

                <select
                    value={draftModel.name}
                    onChange={(e) => setDraftModel({ ...draftModel, name: e.target.value })}
                    className="w-full p-4 bg-[#F5F5F7] border-none rounded-xl text-[14px] font-medium focus:ring-2 focus:ring-blue-500/20"
                >
                    {/* Dynamic models from API */}
                    {(() => {
                        // Get all unique supported models across categories
                        const allSupported = new Set<string>();
                        Object.values(supportedModelsByCategory).forEach(models => {
                            models?.forEach(m => allSupported.add(m));
                        });

                        // Filter to flash/pro models only (exclude experimental)
                        const flashProModels = Array.from(allSupported)
                            .filter(m => m.includes('flash') || m.includes('pro'))
                            .filter(m => !m.includes('exp') && !m.includes('preview'))
                            .sort((a, b) => {
                                // Sort: 2.5 > 2.0 > 1.5, flash before pro
                                const getScore = (m: string) => {
                                    let score = 0;
                                    if (m.includes('2.5')) score += 300;
                                    else if (m.includes('2.0')) score += 200;
                                    else if (m.includes('1.5')) score += 100;
                                    if (m.includes('flash')) score += 50;
                                    if (m.includes('pro')) score += 25;
                                    return score;
                                };
                                return getScore(b) - getScore(a);
                            });

                        if (flashProModels.length === 0) {
                            // Fallback if no models found
                            return (
                                <>
                                    <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                                    <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                                    <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                                </>
                            );
                        }

                        return flashProModels.map(model => {
                            const label = model
                                .replace('gemini-', 'Gemini ')
                                .replace('-flash', ' Flash')
                                .replace('-pro', ' Pro');
                            const isSupported = Object.values(supportedModelsByCategory).some(models => models?.includes(model));
                            return (
                                <option key={model} value={model}>
                                    {label} {isSupported ? '✓' : ''}
                                </option>
                            );
                        });
                    })()}
                </select>

                {/* Show which model is being used from detected models */}
                {Object.keys(supportedModelsByCategory).some(cat => (supportedModelsByCategory[cat]?.length || 0) > 0) && (
                    <p className="text-xs text-black/40 mt-2">
                        💡 แสดงเฉพาะ Models ที่ตรวจพบจากการ Test API Keys ({
                            [...new Set(Object.values(supportedModelsByCategory).flat().filter(m => m?.includes('flash') || m?.includes('pro')))].length
                        } models)
                    </p>
                )}

                {/* Compatibility Warnings */}
                <div className="mt-4 space-y-2">
                    {(['general', 'school', 'student'] as const).map(cat => {
                        const status = getCompatibilityStatus(cat);
                        if (status === 'warning') {
                            return (
                                <div key={cat} className="flex items-center gap-2 p-3 bg-amber-50 rounded-xl text-amber-800 text-xs border border-amber-200/50">
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-amber-500">
                                        <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                                    </svg>
                                    <span><strong>{cat.toUpperCase()}:</strong> Model นี้อาจไม่รองรับกับ API Key ปัจจุบัน กรุณากด Test ในหน้า API เพื่อยืนยัน</span>
                                </div>
                            );
                        }
                        return null;
                    })}
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white p-6 rounded-2xl border border-black/5">
                    <label className="text-sm font-bold text-black/60 uppercase tracking-wide mb-4 block">
                        Temperature: {draftModel.temperature.toFixed(1)}
                    </label>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={draftModel.temperature}
                        onChange={(e) => setDraftModel({ ...draftModel, temperature: parseFloat(e.target.value) })}
                        className="w-full accent-blue-600"
                    />
                    <div className="flex justify-between text-xs text-black/40 mt-2">
                        <span>Precise (0.0)</span>
                        <span>Creative (1.0)</span>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-2xl border border-black/5">
                    <label className="text-sm font-bold text-black/60 uppercase tracking-wide mb-4 block">
                        Max Tokens: {draftModel.maxTokens}
                    </label>
                    <input
                        type="range"
                        min="256"
                        max="8192"
                        step="256"
                        value={draftModel.maxTokens}
                        onChange={(e) => setDraftModel({ ...draftModel, maxTokens: parseInt(e.target.value) })}
                        className="w-full accent-blue-600"
                    />
                    <div className="flex justify-between text-xs text-black/40 mt-2">
                        <span>สั้น (256)</span>
                        <span>ยาว (8192)</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ModelConfigTab;
