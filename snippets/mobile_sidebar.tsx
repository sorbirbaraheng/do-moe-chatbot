
{/* ✨ Mobile Drawer Overlay */ }
{
    isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden font-sans">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/20 backdrop-blur-sm animate-in fade-in duration-300"
                onClick={() => setIsMobileMenuOpen(false)}
            ></div>

            {/* Drawer Panel */}
            <div className="absolute inset-y-0 left-0 w-[80%] max-w-[320px] bg-white/90 backdrop-blur-3xl shadow-2xl border-r border-white/40 flex flex-col animate-in slide-in-from-left duration-300">
                <div className="flex items-center justify-between p-6">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-2xl overflow-hidden shadow-md">
                            <img src="/do-mascot.png" alt="DO - MOE One" className="w-full h-full object-cover" />
                        </div>
                        <span className="font-bold text-lg text-[#1D1D1F]">เมนูหลัก</span>
                    </div>
                    <button
                        onClick={() => setIsMobileMenuOpen(false)}
                        className="w-8 h-8 rounded-full bg-black/5 flex items-center justify-center text-black/50 hover:bg-black/10"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>

                <div className="px-5 mb-6">
                    <button
                        onClick={() => {
                            handleNewChat();
                            setIsMobileMenuOpen(false);
                        }}
                        className="flex items-center justify-center gap-2 w-full py-3.5 rounded-2xl bg-[#007AFF] text-white shadow-lg shadow-blue-500/30 active:scale-[0.98] transition-all font-semibold"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
                        เริ่มการสนทนาใหม่
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto px-4 pb-4">
                    <div className="text-xs font-bold text-black/40 uppercase tracking-widest mb-3 px-2">ประวัติการสนทนา</div>
                    {pastChats.map(chat => (
                        <div
                            key={chat.sessionId}
                            onClick={() => {
                                loadPastChat(chat);
                                setIsMobileMenuOpen(false);
                            }}
                            className={`px-4 py-3 rounded-xl text-[14px] font-medium transition-all mb-1 truncate flex items-center gap-3
                          ${currentChatId === chat.sessionId
                                    ? 'bg-blue-50 text-blue-600'
                                    : 'active:bg-black/5 text-black/70'
                                }`}
                        >
                            <span className="truncate">{chat.title}</span>
                        </div>
                    ))}
                </div>

                <div className="p-5 border-t border-black/5 bg-white/50">
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-[#FF3B30] font-semibold bg-red-50 hover:bg-red-100 transition-all"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" /></svg>
                        ออกจากระบบ
                    </button>
                </div>
            </div>
        </div>
    )
}
