import React from 'react';
import { UxPolicyTabProps } from './types';

const UxPolicyTab: React.FC<UxPolicyTabProps> = ({
    draftUX,
    setDraftUX,
}) => {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white p-6 rounded-2xl border border-black/5">
                    <label className="text-sm font-bold text-black/60 uppercase tracking-wide mb-4 block">ความยาวคำตอบ</label>
                    <div className="flex gap-2">
                        {(['short', 'medium', 'long'] as const).map((len) => (
                            <button
                                key={len}
                                onClick={() => setDraftUX({ ...draftUX, responseLength: len })}
                                className={`flex-1 py-2 rounded-xl text-sm font-medium transition-all ${draftUX.responseLength === len
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-[#F5F5F7] text-black/70 hover:bg-[#E5E5EA]'
                                    }`}
                            >
                                {len === 'short' ? 'สั้น' : len === 'medium' ? 'กลาง' : 'ยาว'}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="bg-white p-6 rounded-2xl border border-black/5">
                    <label className="text-sm font-bold text-black/60 uppercase tracking-wide mb-4 block">รูปแบบภาษา</label>
                    <div className="flex gap-2">
                        {(['formal', 'casual'] as const).map((style) => (
                            <button
                                key={style}
                                onClick={() => setDraftUX({ ...draftUX, languageStyle: style })}
                                className={`flex-1 py-2 rounded-xl text-sm font-medium transition-all ${draftUX.languageStyle === style
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-[#F5F5F7] text-black/70 hover:bg-[#E5E5EA]'
                                    }`}
                            >
                                {style === 'formal' ? 'ทางการ' : 'ปกติ'}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-black/5">
                <label className="text-sm font-bold text-black/60 uppercase tracking-wide mb-4 block">ข้อความ Error</label>
                <textarea
                    value={draftUX.errorMessage}
                    onChange={(e) => setDraftUX({ ...draftUX, errorMessage: e.target.value })}
                    className="w-full h-20 p-3 bg-[#F5F5F7] border-none rounded-xl text-[13px] resize-none"
                />
            </div>

            <div className="bg-white p-6 rounded-2xl border border-black/5">
                <div className="flex items-center justify-between">
                    <div>
                        <label className="text-sm font-bold text-black/60 uppercase tracking-wide mb-1 block">RAG Debug Mode</label>
                        <p className="text-[11px] text-black/40">แสดงข้อมูลการค้นหาฐานข้อมูลในหน้าแชท (สำหรับแอดมินเท่านั้น)</p>
                    </div>
                    <button
                        onClick={() => setDraftUX({ ...draftUX, showRagDebug: !draftUX.showRagDebug })}
                        className={`w-12 h-6 rounded-full p-1 transition-all duration-300 ${draftUX.showRagDebug ? 'bg-blue-600' : 'bg-gray-300'}`}
                    >
                        <div className={`w-4 h-4 rounded-full bg-white shadow-sm transform transition-transform duration-300 ${draftUX.showRagDebug ? 'translate-x-6' : 'translate-x-0'}`} />
                    </button>
                </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-black/5">
                <label className="text-sm font-bold text-black/60 uppercase tracking-wide mb-4 block">ข้อความ Empty State</label>
                <textarea
                    value={draftUX.emptyStateMessage}
                    onChange={(e) => setDraftUX({ ...draftUX, emptyStateMessage: e.target.value })}
                    className="w-full h-20 p-3 bg-[#F5F5F7] border-none rounded-xl text-[13px] resize-none"
                />
            </div>
        </div>
    );
};

export default UxPolicyTab;
