import React, { useRef, useState } from 'react';
import { DataManagementTabProps } from './types';
import { adminFetch } from '../../../services/adminApi';

const DataManagementTab: React.FC<DataManagementTabProps> = () => {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [uploading, setUploading] = useState(false);
    const [reindexing, setReindexing] = useState(false);
    const [statusMsg, setStatusMsg] = useState('');

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setUploading(true);
        setStatusMsg('กำลังอัปโหลด...');
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await adminFetch('/api/admin/upload', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (data.success) {
                setStatusMsg(`✅ อัปโหลดสำเร็จ: ${data.filename}`);
            } else {
                setStatusMsg(`❌ อัปโหลดล้มเหลว: ${data.error}`);
            }
        } catch (error) {
            setStatusMsg(`❌ Error: ${error}`);
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const triggerReindex = async () => {
        setReindexing(true);
        setStatusMsg('กำลัง Re-index...');
        try {
            const response = await adminFetch('/api/admin/reindex', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target: 'all' })
            });
            const data = await response.json();
            if (data.success) {
                setStatusMsg(`✅ Re-index triggered!`);
            } else {
                setStatusMsg(`❌ Re-index failed: ${data.error}`);
            }
        } catch (e) {
            setStatusMsg(`❌ Error: ${e}`);
        } finally {
            setReindexing(false);
        }
    };

    return (
        <div className="space-y-6">
            <div
                className="bg-white p-6 rounded-2xl border border-black/5 border-dashed cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => fileInputRef.current?.click()}
            >
                <div className="flex flex-col items-center justify-center py-8">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-12 h-12 text-black/20 mb-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z" />
                    </svg>
                    <p className="text-black/60 font-medium mb-4">คลิกเพื่อเลือกไฟล์ CSV หรือ JSON</p>
                    <button className="px-6 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-bold hover:bg-blue-700 transition-all" disabled={uploading}>
                        {uploading ? 'กำลังอัปโหลด...' : 'เลือกไฟล์'}
                    </button>
                    <input
                        type="file"
                        className="hidden"
                        ref={fileInputRef}
                        accept=".csv,.json"
                        onChange={handleFileUpload}
                    />
                    <p className="text-xs text-black/40 mt-3">รองรับ: CSV, JSON</p>
                </div>
            </div>

            {statusMsg && (
                <div className="p-4 rounded-xl bg-gray-100 text-center text-sm font-medium animate-pulse">
                    {statusMsg}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button
                    className="bg-white p-6 rounded-2xl border border-black/5 hover:shadow-lg transition-all text-left group disabled:opacity-50"
                    onClick={triggerReindex}
                    disabled={reindexing}
                >
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center text-amber-600">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                            </svg>
                        </div>
                        <span className="font-bold text-[#1D1D1F]">
                            {reindexing ? 'Re-indexing...' : 'Trigger Re-index'}
                        </span>
                    </div>
                    <p className="text-sm text-black/50">สร้าง vector embeddings ใหม่</p>
                </button>

                <button className="bg-white p-6 rounded-2xl border border-black/5 hover:shadow-lg transition-all text-left group cursor-not-allowed opacity-60">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center text-purple-600">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                            </svg>
                        </div>
                        <span className="font-bold text-[#1D1D1F]">Embedding Quality</span>
                    </div>
                    <p className="text-sm text-black/50">Coming Soon</p>
                </button>
            </div>
        </div>
    );
};

export default DataManagementTab;
