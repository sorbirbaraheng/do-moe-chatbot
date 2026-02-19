import React from 'react';
import { RagConfigTabProps } from './types';

const RagConfigTab: React.FC<RagConfigTabProps> = ({
    config,
    updateRAG,
}) => {
    const categories = [
        { id: 'general', label: 'ทั่วไป (General)', color: 'blue' },
        { id: 'school', label: 'โรงเรียน (School)', color: 'green' },
        { id: 'student', label: 'นักเรียน (Student)', color: 'purple' },
    ] as const;

    return (
        <div className="space-y-6">
            {/* Global Kill Switch */}
            <div className="bg-white p-6 rounded-3xl border border-black/5 shadow-sm">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${config.rag.enabled ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'bg-gray-100 text-gray-400'}`}>
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                            </svg>
                        </div>
                        <div>
                            <h3 className="text-xl font-bold text-[#1D1D1F]">RAG Retrieval Engine</h3>
                            <p className="text-sm text-black/40 font-medium">เปิด/ปิด การใช้งานฐานข้อมูลภายนอก (Knowledge Base) สำหรับทุกหมวดหมู่</p>
                        </div>
                    </div>
                    <button
                        onClick={() => updateRAG({ enabled: !config.rag.enabled })}
                        className={`px-8 py-3 rounded-2xl text-sm font-bold transition-all shadow-lg active:scale-95 ${config.rag.enabled
                            ? 'bg-blue-600 text-white shadow-blue-500/25 hover:bg-blue-700'
                            : 'bg-black/5 text-black/30'
                            }`}
                    >
                        {config.rag.enabled ? 'เปิดการใช้งานอยู่ (ENABLED)' : 'ปิดการใช้งานอยู่ (DISABLED)'}
                    </button>
                </div>
            </div>

            {/* Knowledge Silos Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {categories.map((cat) => {
                    const catConfig = config.apiKeys[cat.id];
                    // Check if connected via Pinecone (new) OR legacy RAG endpoint
                    const isPineconeConfigured = !!(catConfig.pineconeApiKey && catConfig.pineconeHost);
                    const isLegacyRagConfigured = !!catConfig.ragEndpoint;
                    const isConnected = catConfig.ragConnected || isPineconeConfigured || isLegacyRagConfigured;
                    const collectionName = catConfig.pineconeIndex || catConfig.ragCollection || catConfig.pineconeNamespace || '—';

                    return (
                        <div key={cat.id} className="bg-white p-6 rounded-3xl border border-black/5 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex items-center gap-3 mb-4">
                                <div className={`w-8 h-8 rounded-xl bg-${cat.id === 'general' ? 'blue' : cat.id === 'school' ? 'green' : 'purple'}-100 flex items-center justify-center`}>
                                    <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`}></div>
                                </div>
                                <h4 className="font-bold text-[15px] text-[#1D1D1F]">{cat.label}</h4>
                            </div>

                            <div className="space-y-4">
                                <div className="p-4 rounded-2xl bg-[#F5F5F7] border border-black/[0.02]">
                                    <p className="text-[10px] font-bold text-black/30 uppercase tracking-widest mb-1.5">
                                        {isPineconeConfigured ? 'Pinecone Index' : 'Collection Name'}
                                    </p>
                                    <p className="font-mono text-[13px] font-bold text-black/70 truncate">
                                        {collectionName}
                                    </p>
                                </div>

                                <div className="flex items-center justify-between px-1">
                                    <span className="text-[11px] font-bold text-black/40">Knowledge Base:</span>
                                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${isConnected ? 'bg-green-100 text-green-700' : 'bg-red-50 text-red-500'}`}>
                                        {isConnected
                                            ? (isPineconeConfigured ? '🌿 Pinecone' : 'เชื่อมต่อแล้ว')
                                            : 'ยังไม่ได้เชื่อมต่อ'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Helpful Note */}
            <div className="bg-gradient-to-r from-orange-50 to-amber-50 p-6 rounded-3xl border border-orange-100 flex gap-4 items-start">
                <div className="w-10 h-10 rounded-2xl bg-orange-100 flex items-center justify-center text-orange-600 flex-shrink-0">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
                    </svg>
                </div>
                <div>
                    <h4 className="font-bold text-orange-900 mb-1">การตั้งค่ารายหมวดหมู่</h4>
                    <p className="text-sm text-orange-800/70 leading-relaxed font-medium">เพื่อความปลอดภัยและการแยกส่วนข้อมูล (Data Isolation) การตั้งค่า <b>RAG Endpoint, API Key, และ Collection</b> สำหรับแต่ละคนละหมวดหมู่ จะต้องทำที่เมนู <b>"API Settings"</b> โดยเลือกหมวดหมู่ที่ต้องการตั้งค่าที่แถบด้านบนครับ</p>
                </div>
            </div>
        </div>
    );
};

export default RagConfigTab;
