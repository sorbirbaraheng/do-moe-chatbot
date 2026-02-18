import React, { useEffect, useState } from 'react';
import { User } from '../types';
import { ChatSession } from '../services/chatService';

interface MobileMenuProps {
    isOpen: boolean;
    onClose: () => void;
    user: User | null;
    currentChatId: string;
    pastChats: ChatSession[];
    onNewChat: () => void;
    onLoadChat: (session: ChatSession) => void;
    onDeleteChat: (session: ChatSession) => void;
    onLogout: () => void;
    onNavigateHome: () => void;
}

const MobileMenu: React.FC<MobileMenuProps> = ({
    isOpen,
    onClose,
    user,
    currentChatId,
    pastChats,
    onNewChat,
    onLoadChat,
    onDeleteChat,
    onLogout,
    onNavigateHome,
}) => {
    const [isVisible, setIsVisible] = useState(false);

    // Handle mounting animation with CSS classes for smooth mounting/unmounting
    useEffect(() => {
        if (isOpen) {
            setIsVisible(true);
            document.body.style.overflow = 'hidden';
        } else {
            const timer = setTimeout(() => setIsVisible(false), 500); // Wait for transition
            document.body.style.overflow = '';
            return () => clearTimeout(timer);
        }
    }, [isOpen]);

    if (!isVisible && !isOpen) return null;

    return (
        <div className={`fixed inset-0 z-[100] md:hidden ${isOpen ? 'pointer-events-auto' : 'pointer-events-none'}`}>

            {/* Backdrop - Progressive Blur */}
            <div
                className={`absolute inset-0 bg-black/20 backdrop-blur-sm transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${isOpen ? 'opacity-100 backdrop-blur-sm' : 'opacity-0 backdrop-blur-none'}`}
                onClick={onClose}
            />

            {/* Slide-in Panel - iOS Sheet Style with Deep Glass */}
            <div
                className={`
                    absolute inset-y-3 left-3 w-[300px] max-w-[85vw]
                    bg-[#F2F2F7]/80 backdrop-blur-[40px] saturate-150
                    flex flex-col
                    rounded-[28px]
                    shadow-[0_0_0_1px_rgba(255,255,255,0.2),_0_20px_50px_rgba(0,0,0,0.15)]
                    border border-white/30
                    transition-all duration-600 ease-[cubic-bezier(0.32,0.72,0,1)]
                    overflow-hidden
                    ${isOpen ? 'translate-x-0 scale-100 opacity-100' : '-translate-x-[110%] scale-95 opacity-0'}
                `}
            >
                {/* Header Profile Area */}
                <div className="pt-6 px-5 pb-6">
                    <div className="flex items-center gap-3.5 mb-6" onClick={() => { onNavigateHome(); onClose(); }}>
                        <div className="relative">
                            <div className="absolute inset-0 bg-gradient-to-tr from-blue-400 to-purple-400 rounded-xl blur-md opacity-30"></div>
                            <img src="/do-mascot.png" alt="DO" className="relative w-11 h-11 rounded-2xl shadow-sm bg-white p-0.5 object-cover" />
                        </div>
                        <div>
                            <div className="text-[17px] font-bold text-[#1d1d1f] tracking-tight leading-none">MOE - One</div>
                            <div className="text-[11px] font-semibold text-[#86868b] uppercase tracking-wide mt-1">AI Assistant</div>
                        </div>
                        <button
                            onClick={onClose}
                            className="ml-auto w-8 h-8 flex items-center justify-center rounded-full bg-black/5 hover:bg-black/10 active:scale-95 transition-all"
                        >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#8e8e93" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                        </button>
                    </div>

                    <button
                        onClick={() => { onNewChat(); onClose(); }}
                        className="w-full py-3.5 rounded-2xl bg-[#007AFF] hover:bg-[#0062cc] active:scale-[0.98] transition-all text-white font-semibold text-[15px] flex items-center justify-center gap-2.5 shadow-lg shadow-blue-500/25"
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
                        เริ่มการสนทนาใหม่
                    </button>
                </div>

                {/* List Container - Inset Grouped */}
                <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-6">

                    {/* History Section */}
                    <div>
                        <div className="text-[12px] font-semibold text-[#86868b] uppercase tracking-wider mb-2 px-3">ประวัติการสนทนา</div>
                        <div className="bg-white/70 rounded-[18px] overflow-hidden backdrop-blur-md">
                            {pastChats.length > 0 ? pastChats.slice(0, 8).map((chat, idx) => (
                                <div
                                    key={chat.sessionId}
                                    className={`
                                        flex items-center gap-2 px-2 py-1.5
                                        ${idx !== pastChats.length - 1 && idx !== 7 ? 'border-b border-[#c6c6c8]/30' : ''}
                                    `}
                                >
                                    <button
                                        onClick={() => { onLoadChat(chat); onClose(); }}
                                        className="flex-1 text-left px-2 py-2.5 text-[15px] truncate flex items-center gap-3 rounded-xl active:bg-[#e5e5ea] transition-colors"
                                    >
                                        <div className={`w-1.5 h-1.5 rounded-full ${currentChatId === chat.sessionId ? 'bg-[#007AFF]' : 'bg-[#c7c7cc]'}`} />
                                        <span className={`${currentChatId === chat.sessionId ? 'text-[#007AFF] font-semibold' : 'text-[#1d1d1f]'}`}>
                                            {chat.title}
                                        </span>
                                    </button>
                                    <button
                                        onClick={() => onDeleteChat(chat)}
                                        className="w-8 h-8 rounded-full flex items-center justify-center text-[#8e8e93] hover:bg-red-50 hover:text-[#FF3B30] active:scale-95 transition-all"
                                        aria-label={`ลบ ${chat.title}`}
                                        title="ลบประวัติ"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 7.5h12m-9 0v10.125c0 .621.504 1.125 1.125 1.125h3.75c.621 0 1.125-.504 1.125-1.125V7.5m-7.5 0V6.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V7.5" />
                                        </svg>
                                    </button>
                                </div>
                            )) : (
                                <div className="text-center text-[13px] text-[#8e8e93] py-8">ไม่มีประวัติการสนทนา</div>
                            )}
                        </div>
                    </div>
                </div>

                {/* User Footer */}
                {user && (
                    <div className="p-3 mt-auto">
                        <div className="bg-white/80 backdrop-blur-xl rounded-[20px] p-1 shadow-sm border border-white/50">
                            <div className="flex items-center gap-3.5 p-3.5">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm ring-2 ring-white shadow-sm">
                                    {user.avatar ? <img src={user.avatar} className="w-full h-full rounded-full object-cover" /> : user.initials}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-[14px] font-bold text-[#1d1d1f] truncate">{user.name}</div>
                                    <div className="text-[11px] font-medium text-[#86868b] truncate">{user.role}</div>
                                </div>
                            </div>
                            <button
                                onClick={onLogout}
                                className="w-full py-3 border-t border-[#c6c6c8]/30 text-[#FF3B30] text-[13px] font-semibold hover:bg-red-50 active:bg-red-100 rounded-b-[16px] transition-colors"
                            >
                                ออกจากระบบ
                            </button>
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
};

export default MobileMenu;
