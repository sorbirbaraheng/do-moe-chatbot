import React, { Suspense, useRef, useEffect } from 'react';
import { Message, ChatSession, Category, User } from '../../types';
import ChatInput from './ChatInput';
import MobileMenu from '../layout/MobileMenu';
import Sidebar from '../layout/Sidebar';
import { useAdminConfig } from '../../contexts/AdminConfigContext';

// Using React.lazy for components that might not be needed immediately
const MessageBubble = React.lazy(() => import('./MessageBubble'));

interface ChatViewProps {
    user: User | null;
    messages: Message[];
    currentChatId: string;
    category: Category;
    isLoading: boolean;
    isSpeaking: boolean;
    speechUnlocked: boolean;
    isListening: boolean;
    isTalkMode: boolean;
    micLevel: number;
    speechError: string;
    voicesReady: boolean;
    availableVoices: any[];
    selectedVoiceUri: string;
    speechMuted: boolean;
    autoListenSignal: number;
    stopListeningSignal: number;
    isAdminAuthenticated: boolean;
    pastChats: ChatSession[];

    // Callbacks
    onSendMessage: (text: string, imageData: string | null) => void;
    onEditMessage: (messageId: string, text: string) => void;
    onRegenerate: () => void;
    onStopAI: () => void;
    onNewChat: () => void;
    onLoadChat: (session: ChatSession) => void;
    onDeleteChat: (session: ChatSession) => void;
    onLogout: () => void;
    onNavigateHome: () => void;

    // Speech callbacks
    setIsTalkMode: React.Dispatch<React.SetStateAction<boolean>>;
    setSpeechMuted: React.Dispatch<React.SetStateAction<boolean>>;
    setSelectedVoiceUri: (uri: string) => void;
    unlockSpeech: () => void;
    primeSpeech: () => void;
    stopSpeaking: () => void;
    setSpeechUnlocked: (unlocked: boolean) => void;
    setSpeechError: (error: string) => void;
    speakText: (text: string) => boolean;
    playTestBeep: () => void;
    setAutoListenSignal: React.Dispatch<React.SetStateAction<number>>;
    setStopListeningSignal: React.Dispatch<React.SetStateAction<number>>;
    setIsListening: (listening: boolean) => void;
    setMicLevel: (level: number) => void;
}

const ChatView: React.FC<ChatViewProps> = ({
    user,
    messages,
    currentChatId,
    category,
    isLoading,
    isSpeaking,
    speechUnlocked,
    isListening,
    isTalkMode,
    micLevel,
    speechError,
    voicesReady,
    availableVoices,
    selectedVoiceUri,
    speechMuted,
    autoListenSignal,
    stopListeningSignal,
    isAdminAuthenticated,
    pastChats,

    onSendMessage,
    onEditMessage,
    onRegenerate,
    onStopAI,
    onNewChat,
    onLoadChat,
    onDeleteChat,
    onLogout,
    onNavigateHome,

    setIsTalkMode,
    setSpeechMuted,
    setSelectedVoiceUri,
    unlockSpeech,
    primeSpeech,
    stopSpeaking,
    setSpeechUnlocked,
    setSpeechError,
    speakText,
    playTestBeep,
    setAutoListenSignal,
    setStopListeningSignal,
    setIsListening,
    setMicLevel
}) => {
    const { config } = useAdminConfig();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);
    const [sidebarImgError, setSidebarImgError] = React.useState(false);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const chatContainerRef = useRef<HTMLDivElement>(null);

    const lastMessagesLength = useRef(messages.length);
    const lastContentLength = useRef(0);
    const isInitialMount = useRef(true);

    const scrollToBottom = (instant = false) => {
        if (chatContainerRef.current) {
            const container = chatContainerRef.current;
            if (instant) {
                container.scrollTop = container.scrollHeight;
            } else {
                container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
            }
        }
    };

    useEffect(() => {
        if (chatContainerRef.current) {
            const container = chatContainerRef.current;
            const resizeObserver = new ResizeObserver(() => {
                const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 150;
                if (isLoading || isNearBottom) {
                    requestAnimationFrame(() => { container.scrollTop = container.scrollHeight; });
                }
            });
            const scrollContent = container.querySelector('.max-w-4xl');
            if (scrollContent) resizeObserver.observe(scrollContent);
            return () => resizeObserver.disconnect();
        }
    }, [isLoading]);

    useEffect(() => {
        const isNewMessage = messages.length > lastMessagesLength.current;
        const lastMessage = messages[messages.length - 1];
        const isContentUpdating = lastMessage && lastMessage.content.length > lastContentLength.current;
        const isAiTyping = isLoading && lastMessage?.role === 'model';

        const timeoutId = setTimeout(() => {
            if (isInitialMount.current || isNewMessage || isAiTyping || isContentUpdating) {
                scrollToBottom(isAiTyping || isContentUpdating);
            }
            isInitialMount.current = false;
            lastMessagesLength.current = messages.length;
            lastContentLength.current = lastMessage?.content.length || 0;
        }, 20);
        return () => clearTimeout(timeoutId);
    }, [messages, isLoading]);

    const talkStatus = !speechUnlocked ? 'แตะเพื่อเปิดเสียง' : isListening ? 'กำลังฟัง...' : isLoading ? 'กำลังคิด...' : isSpeaking ? 'กำลังพูด...' : 'แตะเพื่อพูด';
    const statusGlow = isListening ? 'from-[#00C7FF]/35 via-[#007AFF]/30 to-transparent' : isSpeaking ? 'from-[#AF52DE]/35 via-[#5856D6]/30 to-transparent' : isLoading ? 'from-[#34C759]/30 via-[#30D158]/25 to-transparent' : 'from-[#A0A0A0]/20 via-[#C7C7CC]/15 to-transparent';
    const ringAmp = isListening ? micLevel : (isSpeaking ? 0.25 : 0.12);

    return (
        <div className="flex flex-col w-full h-full relative">
            <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
                <div className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-40 grayscale-[0.2]" style={{ backgroundImage: 'url("/custom-bg.jpg")' }}></div>
                <div className="absolute inset-0 bg-[#F5F5FA]/95 backdrop-blur-[50px]"></div>
            </div>

            <MobileMenu
                isOpen={isMobileMenuOpen}
                onClose={() => setIsMobileMenuOpen(false)}
                user={user}
                currentChatId={currentChatId}
                pastChats={pastChats}
                onNewChat={onNewChat}
                onLoadChat={onLoadChat}
                onDeleteChat={onDeleteChat}
                onLogout={onLogout}
                onNavigateHome={onNavigateHome}
            />

            <div className="relative z-10 flex-1 flex overflow-hidden">
                {/* Sidebar - extracted out in final phase, but inline here temporarily */}
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

                {/* Main Chat Area */}
                <main className="flex-1 flex flex-col relative overflow-hidden">
                    <header className="app-header h-16 flex items-center justify-between px-4 md:px-8 bg-white/70 backdrop-blur-xl border-b border-white/50 shadow-sm z-20">
                        <div className="flex items-center gap-3">
                            <button onClick={() => setIsMobileMenuOpen(true)} className="md:hidden w-10 h-10 -ml-2 flex items-center justify-center rounded-full hover:bg-black/5 active:bg-black/10 transition-all text-[#1D1D1F]">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-6 h-6"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12H12m-8.25 5.25h16.5" /></svg>
                            </button>
                            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-md">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-4 h-4"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>
                            </div>
                            <div>
                                <h2 className="font-bold text-[16px] text-[#1D1D1F] tracking-tight">สนทนา</h2>
                                <span className="text-[9px] font-black text-black/30 uppercase tracking-[0.1em] hidden sm:block">AI Assistant • ศทก.</span>
                            </div>
                        </div>
                        {isAdminAuthenticated && config.uxPolicy.showRagDebug && (
                            <div className="px-3 py-1.5 rounded-full bg-amber-100 border border-amber-200 shadow-sm text-[10px] font-black flex items-center gap-1.5 text-amber-700 animate-pulse">ADMIN TEST MODE</div>
                        )}
                        <div className="hidden sm:flex px-4 py-1.5 rounded-full bg-white/80 backdrop-blur-md border border-white/60 shadow-sm text-[11px] font-semibold items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                            <span className="text-black/60">Mode:</span>
                            <span className="text-blue-600">DO AI</span>
                        </div>
                    </header>

                    <div ref={chatContainerRef} className={`chat-scroll flex-1 overflow-y-auto no-scrollbar relative ${isTalkMode ? 'pointer-events-none' : 'pointer-events-auto'}`}>
                        <div className={`fixed inset-0 z-20 talk-overlay ${isTalkMode ? 'talk-overlay-active' : 'talk-overlay-hidden'}`} aria-hidden={!isTalkMode}>
                            <div className="talk-blob blob-1"></div><div className="talk-blob blob-2"></div><div className="talk-blob blob-3"></div>
                            <div className="talk-vignette"></div><div className="absolute inset-0 grain-overlay"></div>
                        </div>

                        <div className={`fixed inset-0 z-30 flex items-center justify-center talk-orb-layer ${isTalkMode ? 'talk-orb-active pointer-events-auto' : 'talk-orb-hidden pointer-events-none'}`} aria-hidden={!isTalkMode}>
                            <div className="relative flex flex-col items-center gap-4">
                                <div className={`absolute -inset-14 rounded-full bg-gradient-to-br ${statusGlow} blur-[80px] opacity-90`}></div>
                                <div className="talk-orb" style={{ ['--level' as any]: isListening ? micLevel : (isSpeaking ? 0.25 : 0.08) }}><div className="talk-orb-glow"></div><div className="talk-orb-core"></div></div>
                                <div className="flex items-center gap-1">
                                    {[0.55, 0.8, 1.05, 1.35, 1.05, 0.8, 0.55].map((level, i) => {
                                        const scale = isListening ? Math.max(0.25, 0.25 + micLevel * level * 1.4) : undefined;
                                        return <span key={`wave-${i}`} className={`siri-wave-bar ${isListening ? '' : (isSpeaking || isLoading ? 'siri-wave-active' : 'siri-wave-idle')}`} style={{ animationDelay: `${i * 90}ms`, transform: scale ? `scaleY(${scale})` : undefined, transition: isListening ? 'transform 80ms linear' : undefined }} />
                                    })}
                                </div>
                                <div className="siri-ring">
                                    {Array.from({ length: 28 }).map((_, i) => <span key={`ring-${i}`} className="siri-ring-bar" style={{ ['--rot' as any]: `${i * (360 / 28)}deg`, ['--amp' as any]: ringAmp.toFixed(3), ['--delay' as any]: `${i * 35}ms` }} />)}
                                </div>
                                <button type="button" onClick={() => { unlockSpeech(); if (!isListening && !isLoading) setAutoListenSignal(s => s + 1); }} className={`talk-ready-btn ${isListening ? 'talk-ready-disabled' : ''}`} disabled={isListening || isLoading}>{talkStatus}</button>
                                <div className="text-[11px] font-medium text-white/70">{speechError ? speechError : voicesReady ? 'เสียงพร้อมใช้งาน' : 'กำลังโหลดเสียง...'}</div>
                            </div>
                        </div>

                        <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-40 talk-controls-layer ${isTalkMode ? 'talk-controls-active' : 'talk-controls-hidden'}`} aria-hidden={!isTalkMode}>
                            <div className="talk-controls">
                                <button type="button" onClick={() => setSpeechMuted(prev => !prev)} className={`talk-control-btn ${speechMuted ? 'talk-control-muted' : 'talk-control-active'}`} title={speechMuted ? 'เปิดเสียง' : 'ปิดเสียง'}>{speechMuted ? 'ปิดเสียงอยู่' : 'เสียงเปิด'}</button>
                                <select value={selectedVoiceUri} onChange={(e) => setSelectedVoiceUri(e.target.value)} className="talk-voice-select">
                                    {availableVoices.length === 0 && <option value="">{voicesReady ? 'ไม่พบเสียง' : 'กำลังโหลดเสียง...'}</option>}
                                    {availableVoices.map(v => <option key={v.voiceURI} value={v.voiceURI}>{v.name} ({v.lang})</option>)}
                                </select>
                                <button type="button" onClick={() => { if (speechMuted) setSpeechMuted(false); window.speechSynthesis?.cancel(); window.speechSynthesis?.resume(); setSpeechUnlocked(true); setSpeechError(''); if (!speakText('ทดสอบเสียงน้องดีโอครับ')) playTestBeep(); }} className="talk-control-btn">ทดสอบเสียง</button>
                                <button type="button" onClick={() => { setIsTalkMode(false); stopSpeaking(); setStopListeningSignal(s => s + 1); setIsListening(false); }} className="talk-control-btn talk-control-exit">ปิดโหมด</button>
                            </div>
                        </div>

                        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-6 pt-6">
                            {messages.length === 0 && (
                                <div className="flex flex-col items-center justify-center min-h-[60vh] pb-20 animate-in fade-in zoom-in-95 duration-1000 ease-out">
                                    <div className="md:hidden flex flex-col items-center text-center px-4 pt-8 pb-6 w-full">
                                        <div className="w-14 h-14 rounded-[18px] bg-gradient-to-br from-[#7CC5FF] via-[#9B8CFF] to-[#C7A6FF] flex items-center justify-center shadow-lg mb-5">
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-7 h-7"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" /></svg>
                                        </div>
                                        <h2 className="text-[22px] font-bold text-[#1D1D1F] tracking-tight mb-1">สวัสดีครับ! ผมคือ <span className="hero-title-accent">น้องดีโอ</span></h2>
                                        <p className="text-[13px] text-[#6e6e73] leading-relaxed max-w-[280px]">ถามได้ทั้งโรงเรียน ครู นักเรียน และสถิติระดับจังหวัด</p>
                                        <div className="flex flex-wrap justify-center gap-2.5 mt-6 px-2">
                                            {[
                                                { icon: "🏫", text: "ครูน่านมีกี่คน" },
                                                { icon: "�", text: "สถิติ นร. ม.1 ปีนี้" },
                                                { icon: "🏆", text: "อำเภอที่มีอัตรส่วนครูต่อนักเรียนเยอะสุด" },
                                                { icon: "�", text: "ร.ร. โคกคอนวิทยานุกูล" }
                                            ].map((item, idx) => (
                                                <button
                                                    key={`mob-${idx}`}
                                                    onClick={() => onSendMessage(item.text, null)}
                                                    className="flex items-center gap-2 px-4 py-2.5 rounded-[20px] bg-white/40 backdrop-blur-2xl border border-white/60 shadow-[0_8px_32px_rgba(0,0,0,0.04)] text-[13px] font-medium text-[#1d1d1f] hover:bg-white/60 hover:-translate-y-0.5 active:scale-95 transition-all duration-300"
                                                >
                                                    <span className="text-[15px] drop-shadow-sm">{item.icon}</span>
                                                    <span>{item.text}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="hidden md:block text-center mb-12 relative group w-full">
                                        <div className="absolute -top-10 left-1/2 -translate-x-1/2 w-[320px] h-[320px] bg-gradient-to-tr from-[#7CC5FF]/35 via-[#9B8CFF]/30 to-[#C7A6FF]/25 rounded-full blur-[90px] opacity-70 group-hover:opacity-100 transition-opacity duration-1000"></div>
                                        <div className="hero-glass hero-float mx-auto max-w-2xl">
                                            <div className="hero-badge">MOE‑One • ศทก. สป.</div>
                                            <div className="hero-orb"><div className="hero-orb-glow"></div><div className="hero-orb-core"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-8 h-8 drop-shadow-md"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" /></svg></div></div>
                                            <h2 className="hero-title text-[40px] font-bold text-[#1D1D1F] tracking-[-0.035em] mb-3 leading-tight">สวัสดีครับ! ผมคือ <span className="hero-title-accent">น้องดีโอ</span></h2>
                                            <p className="hero-sub">ผู้ช่วยข้อมูลการศึกษา MOE‑One ของศูนย์เทคโนโลยีสารสนเทศเพื่อการศึกษา (ศทก.) สป.</p>
                                            <div className="flex flex-wrap justify-center gap-3 mt-8 max-w-[600px] mx-auto">
                                                {[
                                                    { icon: "🏫", text: "ในนครศรีธรรมราช อำเภอไหนมีโรงเรียนมากที่สุด" },
                                                    { icon: "👨‍🏫", text: "จังหวัดน่านมีครูข้าราชการกี่คน" },
                                                    { icon: "📈", text: "ปี 2567 กับ 2568 นักเรียนชั้น ม.1 ต่างกันกี่คน" },
                                                    { icon: "🎯", text: "ราชบุรีกับเพชรบุรี ใครมีอัตราส่วนนักเรียนต่อครูสูงกว่า" }
                                                ].map((item, idx) => (
                                                    <button
                                                        key={`desk-${idx}`}
                                                        onClick={() => onSendMessage(item.text, null)}
                                                        className="flex items-center gap-2.5 px-5 py-3 rounded-[24px] bg-white/40 backdrop-blur-[32px] border border-white/70 shadow-[0_8px_32px_rgba(0,0,0,0.05)] text-[14px] font-medium text-[#1d1d1f] hover:bg-white/70 hover:shadow-[0_16px_48px_rgba(0,0,0,0.08)] hover:-translate-y-1 active:scale-95 transition-all duration-400 ease-out"
                                                    >
                                                        <span className="text-[18px] drop-shadow-sm">{item.icon}</span>
                                                        <span className="tracking-tight">{item.text}</span>
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <Suspense fallback={<div className="h-14" />}>
                                {messages.map((msg, index) => {
                                    const lastAssistantIndex = messages.map((m, i) => ({ role: m.role, idx: i })).filter(m => m.role === 'model').pop()?.idx;
                                    const lastUserMsg = messages.slice(0, index + 1).filter(m => m.role === 'user').pop()?.content || '';
                                    return (
                                        <MessageBubble
                                            key={msg.id}
                                            message={msg}
                                            isAdminMode={isAdminAuthenticated && config.uxPolicy.showRagDebug}
                                            userAvatar={user?.avatar}
                                            userInitials={user?.initials}
                                            onRegenerate={onRegenerate}
                                            onEdit={onEditMessage}
                                            isLastAssistantMessage={index === lastAssistantIndex}
                                            lastUserMessage={lastUserMsg}
                                            isLatestMessage={index === messages.length - 1}
                                            sessionId={currentChatId}
                                            category={category.toLowerCase() as 'general' | 'school' | 'student'}
                                            onSuggestionClick={(text) => onSendMessage(text, null)}
                                        />
                                    );
                                })}
                            </Suspense>
                            <div ref={messagesEndRef} className="h-4" />
                        </div>
                    </div>

                    {/* Chat Input — outside scroll area, always fixed at bottom */}
                    <div className={`chat-input-area flex-shrink-0 p-3 sm:p-6 z-20 transition-all duration-500 ease-out ${isTalkMode ? 'opacity-0 translate-y-4 pointer-events-none' : 'opacity-100 translate-y-0 pointer-events-auto'}`} style={{ display: isTalkMode ? 'none' : 'block' }}>
                        <div className="pointer-events-auto max-w-4xl mx-auto">
                            <ChatInput
                                onSend={onSendMessage}
                                disabled={isLoading}
                                isLoading={isLoading}
                                isSpeaking={isSpeaking}
                                onStop={onStopAI}
                                talkMode={isTalkMode}
                                onToggleTalkMode={() => {
                                    try {
                                        const silentAudio = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYYoRwmHAAAAAAD/+1DEAAAGAAGn9AAAIiWi7/ckAABNm/8+D58H/5cP/yhAGCYIAgSBAMf/8oQBgEAQB8H4Pg+XB8Hwf/6gAYJOD5//y4Pg+D8uEMf/lCH//5Qh///8uD7///y4f///+D7////5c////B9////y5////w==');
                                        silentAudio.volume = 0.01; silentAudio.play().catch(() => { });
                                    } catch { /* ignore */ }
                                    primeSpeech();
                                    unlockSpeech();
                                    setIsTalkMode(prev => {
                                        const next = !prev;
                                        if (!next) { stopSpeaking(); setStopListeningSignal(s => s + 1); setIsListening(false); }
                                        if (next) setAutoListenSignal(s => s + 1);
                                        return next;
                                    });
                                }}
                                onStopSpeaking={stopSpeaking}
                                autoListenSignal={autoListenSignal}
                                stopListeningSignal={stopListeningSignal}
                                onListeningChange={setIsListening}
                                onMicLevel={setMicLevel}
                            />
                        </div>
                    </div>
                </main>
            </div>
        </div>
    );
};

export default ChatView;
