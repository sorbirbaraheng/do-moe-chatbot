import React, { useState } from 'react';
import { MOE_COLORS } from '../../constants';
import { adminLogin } from '../../services/adminApi';
import { setAdminSession } from '../../services/adminAuth';

interface AdminLoginProps {
    onSuccess: () => void;
    onCancel: () => void;
}

const AdminLogin: React.FC<AdminLoginProps> = ({ onSuccess, onCancel }) => {
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const result = await adminLogin(password);
            if (result.success === true) {
                setAdminSession(result.token, result.role, false);
                onSuccess();
                return;
            } else {
                setError(result.error || 'รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง');
            }
            setIsLoading(false);
        } catch (err) {
            console.error("Admin Login Error:", err);
            setError('เกิดข้อผิดพลาดในการเชื่อมต่อ');
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-300">
            <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl p-8 animate-in zoom-in-95 slide-in-from-bottom-4 duration-500">
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="w-16 h-16 rounded-2xl bg-[#1D1D1F] flex items-center justify-center mx-auto mb-4 shadow-xl">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="white" className="w-8 h-8">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
                        </svg>
                    </div>
                    <h2 className="text-2xl font-bold text-[#1D1D1F] mb-2">Admin Access</h2>
                    <p className="text-sm text-black/50">กรุณาใส่รหัสผ่านเพื่อเข้าสู่ระบบจัดการ</p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-bold text-black/60 uppercase tracking-wide mb-2">
                            รหัสผ่าน Admin
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="กรอกรหัสผ่าน..."
                            className="w-full px-5 py-4 bg-[#F5F5F7] border border-transparent rounded-2xl text-[16px] font-medium focus:border-blue-500/50 focus:bg-white focus:ring-4 focus:ring-blue-500/10 transition-all placeholder:text-gray-400"
                            autoFocus
                            autoComplete="new-password"
                            autoCapitalize="off"
                            spellCheck="false"
                        />
                    </div>

                    {error && (
                        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm font-medium flex items-center gap-2 animate-in shake duration-300">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
                            </svg>
                            {error}
                        </div>
                    )}

                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={onCancel}
                            className="flex-1 py-4 text-sm font-bold text-black/60 bg-[#F5F5F7] hover:bg-[#E5E5EA] rounded-2xl transition-all"
                        >
                            ยกเลิก
                        </button>
                        <button
                            type="submit"
                            disabled={!password || isLoading}
                            className="flex-1 py-4 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-2xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {isLoading ? (
                                <>
                                    <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    กำลังตรวจสอบ...
                                </>
                            ) : (
                                <>
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 1 1 9 0v3.75M3.75 21.75h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H3.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
                                    </svg>
                                    เข้าสู่ระบบ
                                </>
                            )}
                        </button>
                    </div>
                </form>

                {/* Footer Note */}
                <p className="text-center text-xs text-black/30 mt-6">
                    สำหรับเจ้าหน้าที่ ศทก. สป. เท่านั้น
                </p>
            </div>
        </div>
    );
};

export default AdminLogin;
