import React from 'react';
import { PromptsTabProps } from './types';

const PromptsTab: React.FC<PromptsTabProps> = ({
    draftPrompts,
    setDraftPrompts,
    config,
}) => {
    return (
        <div className="space-y-6">
            <div>
                <h3 className="text-lg font-bold mb-4 text-[#1D1D1F]">System Prompt</h3>
                <textarea
                    value={draftPrompts.system}
                    onChange={(e) => setDraftPrompts({ ...draftPrompts, system: e.target.value })}
                    className="w-full h-40 p-4 bg-white border border-black/10 rounded-2xl text-[14px] focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/30 transition-all resize-none"
                    placeholder="กรุณากรอก System Prompt..."
                />
                <p className="text-xs text-black/40 mt-2">Version: {config.prompts.version} | อัปเดตล่าสุด: {config.prompts.lastUpdated ? new Date(config.prompts.lastUpdated).toLocaleString('th-TH') : 'ไม่มีข้อมูล'}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(['general', 'school', 'student'] as const).map((cat) => (
                    <div key={cat} className="bg-white p-4 rounded-2xl border border-black/5">
                        <label className="text-sm font-bold text-black/60 uppercase tracking-wide mb-2 block">
                            {cat === 'general' ? 'ทั่วไป' : cat === 'school' ? 'โรงเรียน' : 'นักเรียน'}
                        </label>
                        <textarea
                            value={draftPrompts.category[cat]}
                            onChange={(e) => setDraftPrompts({
                                ...draftPrompts,
                                category: { ...draftPrompts.category, [cat]: e.target.value }
                            })}
                            className="w-full h-24 p-3 bg-[#F5F5F7] border-none rounded-xl text-[13px] focus:ring-2 focus:ring-blue-500/20 transition-all resize-none"
                        />
                    </div>
                ))}
            </div>
        </div>
    );
};

export default PromptsTab;
