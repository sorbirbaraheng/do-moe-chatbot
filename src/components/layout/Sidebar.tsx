import React from 'react';
import { User, ChatSession } from '../../types';

interface SidebarProps {
    user: User | null;
    pastChats: ChatSession[];
    currentChatId: string;
    onNewChat: () => void;
    onLoadChat: (session: ChatSession) => void;
    onDeleteChat: (session: ChatSession) => void;
    onLogout: () => void;
    onNavigateHome: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
    user,
    pastChats,
    currentChatId,
    onNewChat,
    onLoadChat,
    onDeleteChat,
    onLogout,
    onNavigateHome
}) => {
    const [sidebarImgError, setSidebarImgError] = React.useState(false);

    return (
        <aside className="hidden md:flex flex-col w-[280px] flex-shrink-0 bg-white/80 backdrop-blur-3xl border-r border-white/50 shadow-[inset_-1px_0_0_rgba(255,255,255,0.5)] slide-right-sidebar relative overflow-hidden">
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] mix-blend-overlay z-0" style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\'/%3E%3C/svg%3E")' }}></div>
            <div className="relative z-10 flex items-center gap-3.5 px-6 py-6 cursor-pointer group" onClick={onNavigateHome}>
                <div className="w-12 h-12 rounded-2xl overflow-hidden shadow-lg ring-1 ring-white/10 group-hover:scale-110 group-hover:shadow-xl group-hover:ring-blue-500/20 transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-active:scale-95">
                    <img src="/do-mascot.png" alt="DO - MOE One" className="w-full h-full object-cover" />
                </div>
                <div className="transition-transform duration-300 group-hover:translate-x-0.5">
                    <h1 className="font-bold text-[17px] tracking-tight text-[#1D1D1F] group-hover:text-blue-600 transition-colors duration-300">MOE - One</h1>
                    <p className="text-[10px] font-semibold opacity-50 uppercase tracking-[0.15em]">ศทก. • สป.</p>
                </div>
            </div>
            <div className="relative z-10 px-5 mb-5">
                <button
                    onClick={onNewChat}
                    className="flex items-center justify-center gap-2 w-full py-3 rounded-xl bg-[#1D1D1F] text-white hover:bg-black hover:shadow-[0_12px_28px_rgba(0,0,0,0.25)] hover:scale-[1.02] transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.96] font-semibold text-[14px] shadow-lg"
                >
                    <div className="w-5 h-5 rounded-lg bg-white/10 flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-3.5 h-3.5"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
                    </div>
                    สนทนาใหม่
                </button>
            </div>
            <nav className="relative z-10 flex-1 overflow-y-auto no-scrollbar px-4 fade-mask-b">
                {pastChats.length > 0 && (
                    <div className="mt-8 slide-up-content stagger-2">
                        <div className="px-2 text-[10px] font-black uppercase tracking-[0.2em] mb-3 opacity-30">ประวัติการสนทนา</div>
                        <div className="space-y-1">
                            {pastChats.map(chat => (
                                <div key={chat.sessionId} className="group/item flex items-center gap-1.5">
                                    <button
                                        onClick={() => onLoadChat(chat)}
                                        className={`flex-1 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-300 ease-out cursor-pointer truncate flex items-center gap-3 border transform text-left
                    ${currentChatId === chat.sessionId ? 'bg-white shadow-[0_6px_16px_rgba(0,0,0,0.08)] border-white/80 font-bold text-[#1D1D1F] scale-[1.02]' : 'hover:bg-white/60 hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)] text-black/40 hover:text-black/70 border-transparent hover:border-white/50 active:scale-[0.98] active:bg-white/80'}`}
                                    >
                                        <div className={`w-1.5 h-1.5 rounded-full shrink-0 transition-all duration-500 ${currentChatId === chat.sessionId ? 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)] scale-100' : 'bg-transparent scale-0'}`}></div>
                                        <span className="truncate">{chat.title}</span>
                                    </button>
                                    <button onClick={() => onDeleteChat(chat)} className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-black/30 hover:text-[#FF3B30] hover:bg-white/80 active:scale-95 transition-all duration-200 opacity-0 group-hover/item:opacity-100"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-4 h-4"><path strokeLinecap="round" strokeLinejoin="round" d="M6 7.5h12m-9 0v10.125c0 .621.504 1.125 1.125 1.125h3.75c.621 0 1.125-.504 1.125-1.125V7.5m-7.5 0V6.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V7.5" /></svg></button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </nav>
            <div className="p-5 border-t border-black/5 bg-white/40 backdrop-blur-md">
                {user && (
                    <div className="mb-4 p-3 rounded-2xl bg-white/60 border border-white/60 shadow-sm flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-md ring-2 ring-white/80 overflow-hidden">
                            {user.avatar && !sidebarImgError ? <img src={user.avatar} alt={user.name} className="w-full h-full object-cover" onError={() => setSidebarImgError(true)} /> : user.initials || user.name.charAt(0)}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-[13px] font-bold text-[#1D1D1F] truncate">{user.name}</p>
                            <p className="text-[9px] font-bold text-blue-600/60 uppercase tracking-widest">{user.role}</p>
                        </div>
                    </div>
                )}
                <button onClick={onLogout} className="flex items-center gap-2.5 w-full px-3 py-2.5 rounded-xl text-[#FF3B30] font-semibold hover:bg-red-50 hover:shadow-[0_4px_12px_rgba(255,59,48,0.15)] transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.96] text-[13px] group">
                    <div className="w-7 h-7 rounded-lg bg-red-100/80 flex items-center justify-center group-hover:bg-red-200 group-hover:scale-110 transition-all duration-300"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" /></svg></div>
                    ลงชื่อออก
                </button>
            </div>
        </aside>
    );
};

export default Sidebar;
