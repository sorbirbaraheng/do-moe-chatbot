

/**
 * 📄 ชื่อไฟล์: LandingPage.tsx
 * 📝 คำอธิบาย:
 *    หน้าแรกของเว็บไซต์ (Landing Page)
 *    - Mobile: Apple iOS-style clean design
 *    - Desktop: Original premium design (unchanged)
 */

import React, { useState, useEffect, useMemo, useRef } from 'react';
import { MOE_COLORS, COMMON_QUERIES, MOCK_STATS } from '../../constants';
import { Category, User } from '../../types';

interface LandingPageProps {
  onStart: (category?: Category, initialMessage?: string) => void;
  onAdminLogin: () => void;
  onLogout: () => void;
  user?: User | null;
}

const LandingPage: React.FC<LandingPageProps> = ({ onStart, onAdminLogin, onLogout, user }) => {
  const [searchValue, setSearchValue] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const [fade, setFade] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const flatSuggestions = useMemo(() => {
    return Object.entries(COMMON_QUERIES).flatMap(([cat, queries]) =>
      queries.map(q => ({ text: q, cat: cat as Category }))
    );
  }, []);

  const filteredSuggestions = useMemo(() => {
    if (!searchValue.trim()) return [];
    return flatSuggestions.filter(s =>
      s.text.toLowerCase().includes(searchValue.toLowerCase())
    ).slice(0, 5);
  }, [searchValue, flatSuggestions]);

  useEffect(() => {
    const interval = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setPlaceholderIndex((prev) => (prev + 1) % flatSuggestions.length);
        setFade(true);
      }, 500);
    }, 5000);
    return () => clearInterval(interval);
  }, [flatSuggestions]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSuggestionClick = (suggestion: { text: string, cat: Category }) => {
    onStart(suggestion.cat, suggestion.text);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchValue.trim()) {
      onStart(Category.General, searchValue.trim());
    }
  };

  const handleVoiceSearch = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("ขออภัยครับ บราวเซอร์ของคุณไม่รองรับระบบสั่งการด้วยเสียง");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'th-TH';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onstart = () => setIsListening(true);
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setSearchValue(transcript);
      setIsListening(false);
      setTimeout(() => onStart(Category.General, transcript), 500);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognition.start();
  };

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return { main: "Good morning", sub: "อรุณสวัสดิ์" };
    if (hour >= 12 && hour < 17) return { main: "Good afternoon", sub: "สวัสดียามบ่าย" };
    if (hour >= 17 && hour < 21) return { main: "Good evening", sub: "สวัสดียามเย็น" };
    return { main: "Good night", sub: "ราตรีสวัสดิ์" };
  }, []);

  // ===============================================
  // MOBILE VIEW - Premium Apple Design System (2026)
  // ===============================================
  const mobileView = useMemo(() => (
    <div className="landing-mobile min-h-[100dvh] bg-[#eff1f5] flex flex-col relative overflow-hidden">

      {/* Dynamic Mesh Gradient Background - Subtle & Premium */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[-20%] w-[80%] h-[60%] rounded-full bg-blue-400/20 blur-[100px] animate-pulse-slow"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[70%] h-[60%] rounded-full bg-purple-400/20 blur-[100px] animate-pulse-slow" style={{ animationDelay: '2s' }}></div>
      </div>

      {/* Header - Ultra Glassmorphism */}
      <header className="landing-header sticky top-0 z-50 flex items-center justify-between px-6 pt-14 pb-4 bg-[#eff1f5]/60 backdrop-blur-3xl border-b border-white/20 shadow-[0_4px_30px_rgba(0,0,0,0.03)] transition-all duration-500">
        <div className="flex items-center gap-3 active:opacity-70 transition-opacity duration-300" onClick={() => onStart(Category.Auto)}>
          <div className="relative group">
            <div className="absolute inset-0 bg-gradient-to-tr from-blue-500 to-purple-500 rounded-2xl blur-lg opacity-40 group-hover:opacity-60 transition-opacity duration-500"></div>
            <img src="/do-mascot.png" alt="DO" className="relative w-10 h-10 rounded-2xl shadow-inner border border-white/50 bg-white/50 backdrop-blur-md p-0.5 transition-transform duration-500 group-hover:scale-105" />
          </div>
          <div className="flex flex-col">
            <span className="text-[17px] font-bold text-[#1d1d1f] tracking-tight leading-none drop-shadow-sm">MOE - One</span>
            <span className="text-[10px] text-[#86868b] font-medium tracking-wide uppercase mt-0.5">AI Assistant</span>
          </div>
        </div>

        <button
          onClick={() => onStart()}
          className="landing-cta px-5 py-2 rounded-full bg-[#007AFF] hover:bg-[#0071eb] active:scale-95 transition-all duration-300 text-white text-[13px] font-semibold shadow-[0_4px_12px_rgba(0,122,255,0.3)] hover:shadow-[0_6px_20px_rgba(0,122,255,0.4)] border border-white/10"
        >
          เริ่มแชท
        </button>
      </header>

      <main className="landing-main flex-1 relative z-10 px-6 pt-6 pb-24 overflow-y-auto scrollbar-hide">

        {/* Large Title Greeting */}
        <div className="mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
          <p className="landing-eyebrow text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-2">{greeting.sub}</p>
          <h1 className="landing-title text-[34px] font-bold text-[#1d1d1f] leading-[1.1] tracking-tight">
            {user?.name ? (
              <>สวัสดี, <br /><span className="text-transparent bg-clip-text bg-gradient-to-r from-[#007AFF] to-[#5856D6]">{user.name.split(' ')[0]}</span></>
            ) : (
              <>ยินดีต้อนรับสู่<br />MOE - One AI</>
            )}
          </h1>
        </div>

        {/* Spotlight Search - Super Glass & Depth */}
        <div className="landing-search relative mb-10 z-30" ref={dropdownRef}>
          <form onSubmit={handleSubmit} className="landing-search-form relative group perspective-1000">
            <div className={`
              absolute -inset-1 bg-gradient-to-r from-blue-400/40 via-purple-400/40 to-blue-400/40 rounded-[22px] blur-xl opacity-0 group-focus-within:opacity-100 transition duration-700 ease-out
            `}></div>
            <div className="landing-search-inner relative bg-white/60 backdrop-blur-2xl rounded-[20px] shadow-[0_8px_32px_rgba(0,0,0,0.04)] border border-white/60 p-1.5 flex items-center transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-focus-within:bg-white/80 group-focus-within:shadow-[0_16px_40px_rgba(0,0,0,0.08)] group-focus-within:scale-[1.02] group-focus-within:border-white/80 ring-1 ring-white/40">
              <div className="pl-3.5 pr-2 text-[#8e8e93]">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              </div>

              <input
                type="text"
                value={searchValue}
                onChange={(e) => { setSearchValue(e.target.value); setShowDropdown(true); }}
                placeholder="ค้นหาข้อมูลโรงเรียน, ครู..."
                className="landing-search-input flex-1 bg-transparent h-11 outline-none text-[17px] text-[#1d1d1f] placeholder:text-[#aeaeb2] font-medium"
              />

              <div className="flex items-center gap-1 pr-1.5">
                <button
                  type="button"
                  onClick={handleVoiceSearch}
                  className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 active:scale-90 shadow-sm border border-transparent ${isListening ? 'bg-red-500 text-white animate-pulse shadow-red-500/30' : 'text-[#8e8e93] hover:bg-white/50 hover:border-black/5 hover:shadow-sm'}`}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill={isListening ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
                </button>
                <button
                  type="submit"
                  className="w-10 h-10 rounded-full bg-[#1d1d1f] text-white flex items-center justify-center shadow-[0_4px_12px_rgba(0,0,0,0.15)] active:scale-90 transition-all duration-300 hover:bg-black hover:scale-105"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                </button>
              </div>
            </div>
          </form>

          {/* Suggestions Dropdown - Apple Menu Style */}
          {showDropdown && filteredSuggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-3 p-1.5 bg-white/90 backdrop-blur-2xl rounded-2xl border border-white/40 shadow-[0_20px_40px_rgba(0,0,0,0.12)] z-40 animate-in zoom-in-95 duration-200 origin-top">
              {filteredSuggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSuggestionClick(s)}
                  className="w-full flex items-center gap-3.5 px-3 py-3 rounded-xl hover:bg-[#F2F2F7] transition-colors text-left group"
                >
                  <div className="w-8 h-8 rounded-lg bg-blue-50 text-[#007AFF] flex items-center justify-center group-hover:scale-110 transition-transform">
                    {s.cat === Category.General ? '🌍' : s.cat === Category.School ? '🏫' : '📊'}
                  </div>
                  <span className="text-[15px] font-medium text-[#1d1d1f]">{s.text}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quick Actions - iOS Widget Glass */}
        <div className="mb-10">
          <h3 className="landing-section-title text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-4 px-1 drop-shadow-sm">เมนูลัด</h3>
          <div className="grid grid-cols-1 gap-4">
            {['ค้นหาโรงเรียนใกล้ฉัน', 'สรุปสถิติครูทั่วประเทศ', 'แนวโน้มจำนวนนักเรียนปีนี้'].map((q, i) => (
              <button
                key={i}
                onClick={() => onStart(Category.General, q)}
                className="landing-quick-card w-full bg-white/60 backdrop-blur-2xl rounded-[22px] p-5 flex items-center justify-between shadow-[0_4px_24px_rgba(0,0,0,0.02)] hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] border border-white/50 active:scale-[0.98] transition-all duration-300 active:bg-white/80 group ring-1 ring-white/60"
              >
                <span className="text-[16px] font-medium text-[#1d1d1f] group-hover:text-[#007AFF] transition-colors">{q}</span>
                <div className="w-8 h-8 rounded-full bg-white/50 flex items-center justify-center shadow-sm border border-white/80 group-hover:bg-[#007AFF] group-hover:text-white transition-all duration-300">
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Stats Cards - Horizontal Scroll with Snap */}
        <div className="mb-8 -mx-6">
          <div className="px-6 flex items-center justify-between mb-4">
            <h3 className="landing-section-title text-[13px] font-semibold text-[#86868b] uppercase tracking-wider">ภาพรวมวันนี้</h3>
            <span className="landing-live-pill text-[11px] font-bold text-[#007AFF] bg-blue-50 px-2 py-0.5 rounded-full">Live</span>
          </div>

          <div className="flex gap-4 overflow-x-auto px-6 pb-12 snap-x snap-mandatory scrollbar-hide pt-4">
            {MOCK_STATS.map((stat, idx) => (
              <div
                key={idx}
                onClick={() => onStart(stat.category)}
                className="landing-stat-card snap-center flex-shrink-0 w-[260px] bg-white/70 backdrop-blur-3xl rounded-[28px] p-6 shadow-[0_15px_40px_-5px_rgba(0,0,0,0.05)] hover:shadow-[0_25px_50px_-10px_rgba(0,0,0,0.1)] border border-white/60 relative overflow-hidden group active:scale-[0.98] transition-all duration-500 ease-out ring-1 ring-white/50"
              >
                <div className={`absolute -right-10 -top-10 w-40 h-40 bg-gradient-to-br ${stat.color} opacity-15 blur-[60px] group-hover:opacity-25 transition-opacity duration-700`}></div>

                <div className="flex items-start justify-between mb-8 relative z-10">
                  <div className="w-12 h-12 rounded-[18px] bg-white/80 backdrop-blur-md flex items-center justify-center text-2xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-white/60 group-hover:scale-110 transition-transform duration-500">
                    {stat.icon}
                  </div>
                  <div className="text-[10px] font-bold text-[#8e8e93] uppercase tracking-wide bg-white/50 px-2.5 py-1.5 rounded-full border border-white/40 backdrop-blur-sm self-start">
                    {stat.unit}
                  </div>
                </div>

                <div className="relative">
                  <div className="text-[12px] font-medium text-[#86868b] mb-0.5">{stat.label}</div>
                  <div className="text-[26px] font-bold text-[#1d1d1f] tracking-tight">{stat.value}</div>
                  <div className="mt-2 text-[11px] font-bold text-[#34C759] flex items-center gap-1">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
                    {stat.trend}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* User Card - Apple ID Style */}
        {user && (
          <div className="mb-6">
            <div className="bg-white/80 backdrop-blur-xl rounded-[24px] p-1 shadow-sm border border-white/60">
              <div className="flex items-center gap-4 p-4">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-[#007AFF] to-[#5856D6] flex items-center justify-center text-white text-xl font-bold shadow-md ring-4 ring-white">
                  {user.initials}
                </div>
                <div className="flex-1">
                  <div className="text-[17px] font-bold text-[#1d1d1f] tracking-tight">{user.name}</div>
                  <div className="text-[13px] text-[#86868b] font-medium">{user.role} • {user.email}</div>
                </div>
              </div>
              <button
                onClick={onLogout}
                className="w-full py-3.5 border-t border-[#c6c6c8]/30 text-[#FF3B30] text-[15px] font-semibold active:bg-gray-50 rounded-b-[20px] transition-colors"
              >
                ออกจากระบบ
              </button>
            </div>
          </div>
        )}

        <footer className="text-center pb-6">
          <p className="text-[11px] font-medium text-[#86868b]/60">© 2026 Ministry of Education</p>
        </footer>

      </main>
    </div>
  ), [searchValue, showDropdown, filteredSuggestions, placeholderIndex, fade, isListening, user, greeting, handleSubmit, handleSuggestionClick, handleVoiceSearch, onStart, onLogout, onAdminLogin]);

  // ===============================================
  // DESKTOP VIEW - Original Design (Unchanged)
  // ===============================================
  const desktopView = useMemo(() => (
    <div className="min-h-screen flex flex-col overflow-auto relative bg-[#FBFBFE]">
      {/* Custom Background Image */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute inset-0 bg-cover bg-center bg-no-repeat" style={{ backgroundImage: 'url("/landing-bg-purple.jpg")' }}></div>
        <div className="absolute inset-0 bg-white/10"></div>
        <div className="absolute inset-0 opacity-[0.03] mix-blend-overlay" style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\'/%3E%3C/svg%3E")' }}></div>
      </div>

      <div className="relative z-10 flex-1 flex flex-col safe-area-inset">
        {/* Navbar */}
        <nav className="flex items-center justify-between px-12 py-6 z-20">
          <div className="flex items-center gap-4 cursor-pointer group" onClick={() => onStart(Category.Auto)}>
            <div className="w-12 h-12 rounded-2xl bg-white/80 backdrop-blur-xl border border-white/60 shadow-lg flex items-center justify-center overflow-hidden">
              <img src="/do-mascot.png" alt="DO" className="w-10 h-10 object-contain" />
            </div>
            <div>
              <span className="font-bold text-[22px] tracking-tight text-[#1D1D1F] block">MOE - One</span>
              <p className="text-[10px] font-semibold text-black/40 uppercase tracking-[0.1em]">กระทรวงศึกษาธิการ</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {user && (
              <div className="flex items-center gap-4 bg-white/40 backdrop-blur-xl border border-white/60 p-1.5 pl-5 rounded-full shadow-sm">
                <div className="flex flex-col items-end leading-tight pr-1">
                  <span className="text-[13px] font-bold" style={{ color: MOE_COLORS.textMain }}>{user.name}</span>
                  <span className="text-[10px] opacity-40 font-black uppercase tracking-wider">{user.role}</span>
                </div>
                <div className="w-10 h-10 rounded-full flex items-center justify-center text-[11px] font-black shadow-inner border border-black/5 bg-white" style={{ color: MOE_COLORS.textMain }}>
                  {user.initials}
                </div>
                <div className="h-6 w-[1px] bg-black/5 mx-1"></div>
                <button onClick={onLogout} className="w-10 h-10 rounded-full flex items-center justify-center text-red-400 hover:bg-red-50 hover:text-red-600 transition-all" title="ออกจากระบบ">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
                  </svg>
                </button>
              </div>
            )}

            <button onClick={() => onStart()} className="bg-[#1D1D1F] text-white px-8 py-2.5 rounded-full text-[14px] font-bold hover:bg-black transition-all shadow-xl">
              {user ? 'แชท' : 'โหมดแชท'}
            </button>

            <a href="https://line.me/R/ti/p/@203oozkj" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 px-4 py-2.5 ml-2 rounded-full bg-white text-[#06C755] border border-[#06C755]/30 text-[12px] font-bold hover:bg-[#06C755]/5 transition-all">
              <img src="/line-logo.png" alt="LINE" className="w-5 h-5 object-contain" />
              LINE Chat
            </a>

            <button onClick={onAdminLogin} className="px-4 py-2.5 rounded-full text-[12px] font-bold text-black/60 hover:text-black hover:bg-black/5 transition-all flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
              Admin
            </button>
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 flex flex-col items-center justify-center px-6 py-4 text-center z-10">
          <div className="w-full max-w-5xl flex flex-col items-center gap-8">

            {/* Hero */}
            <div className="w-full px-2">
              <p className="text-[14px] font-semibold mb-4 tracking-[0.15em] opacity-40 uppercase" style={{ color: MOE_COLORS.textMain }}>
                ยกระดับการตัดสินใจด้วยฐานข้อมูลอัจฉริยะ
              </p>
              <h1 className="font-bold tracking-[-0.04em] leading-[1.1] mb-4 text-7xl" style={{ color: MOE_COLORS.textMain }}>
                <span className="text-gradient-apple">Welcome to MOE - One</span>
                <span className="inline-flex items-center justify-center px-5 py-2 rounded-2xl shadow-sm ml-3" style={{ background: 'rgba(255, 255, 255, 0.5)', backdropFilter: 'blur(20px) saturate(180%)', border: '1px solid rgba(255, 255, 255, 0.6)' }}>
                  <span style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #667eea 75%, #764ba2 100%)', backgroundSize: '200% 200%', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontWeight: 900, letterSpacing: '0.05em', animation: 'shimmer 3s ease-in-out infinite' }}>AI</span>
                </span>
              </h1>
              <p className="text-xl font-medium tracking-tight opacity-60 max-w-xl mx-auto mt-4">
                เราพร้อมสนับสนุนข้อมูลและขับเคลื่อนอนาคตการศึกษาไทย
              </p>
            </div>

            {/* Search */}
            <div className="relative w-full max-w-3xl mx-auto" ref={dropdownRef}>
              <form onSubmit={handleSubmit} className="w-full px-8 py-5 rounded-[2.5rem] bg-white border border-[#E5E5E7] shadow-[0_15px_40px_rgba(0,0,0,0.08)] flex items-center">
                <div className="flex-shrink-0 opacity-40">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-6 h-6">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
                  </svg>
                </div>
                <div className="flex-1 relative h-full flex items-center min-h-[44px] ml-4">
                  <input
                    type="text"
                    value={searchValue}
                    onChange={(e) => { setSearchValue(e.target.value); setShowDropdown(true); }}
                    onFocus={() => setShowDropdown(true)}
                    className="w-full bg-transparent border-none outline-none text-xl font-semibold"
                    style={{ color: MOE_COLORS.textMain }}
                    placeholder=" "
                  />
                  {!searchValue && (
                    <div className={`absolute left-0 pointer-events-none transition-all duration-500 ${fade ? 'opacity-40' : 'opacity-0'}`}>
                      <span className="text-xl font-semibold text-black/30">{flatSuggestions[placeholderIndex].text}</span>
                    </div>
                  )}
                </div>
                <div onClick={handleVoiceSearch} className={`p-2.5 rounded-full cursor-pointer hover:bg-black/5 transition-all text-black/40 hover:text-black ${isListening ? 'bg-red-50 text-red-500 animate-pulse' : ''}`}>
                  <svg xmlns="http://www.w3.org/2000/svg" fill={isListening ? "currentColor" : "none"} viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
                  </svg>
                </div>
                <button type="submit" className="w-12 h-12 rounded-full bg-[#1D1D1F] text-white flex items-center justify-center shadow-lg ml-4">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-6 h-6">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                  </svg>
                </button>
              </form>

              {showDropdown && filteredSuggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-4 mx-6 bg-white/90 backdrop-blur-xl rounded-[2rem] border border-white/50 shadow-2xl overflow-hidden z-30">
                  <div className="p-2">
                    {filteredSuggestions.map((suggestion, index) => (
                      <button key={index} onClick={() => handleSuggestionClick(suggestion)} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-black/5 transition-all text-left">
                        <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center text-xs">
                          {suggestion.cat === Category.General ? '🌍' : suggestion.cat === Category.School ? '🏫' : '📊'}
                        </div>
                        <span className="text-[16px] font-medium text-black/80">{suggestion.text}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Stats Cards */}
            <div className="w-full max-w-5xl">
              <div className="grid grid-cols-3 gap-6">
                {MOCK_STATS.map((stat, idx) => (
                  <div key={idx} onClick={() => onStart(stat.category)} className="bg-white/60 backdrop-blur-2xl p-6 rounded-[2rem] text-left transition-all hover:scale-[1.03] hover:bg-white/80 cursor-pointer shadow-[0_10px_40px_rgba(0,0,0,0.03)] hover:shadow-[0_30px_70px_rgba(0,0,0,0.07)] border border-white/80 relative overflow-hidden">
                    <div className="flex items-center justify-between mb-4">
                      <div className="w-12 h-12 rounded-2xl bg-white shadow-sm flex items-center justify-center text-2xl">{stat.icon}</div>
                      <div className="text-[9px] font-black uppercase tracking-[0.15em] px-2.5 py-1 bg-green-50/80 text-green-600 rounded-full border border-green-100/50 flex items-center gap-1.5">
                        <div className="w-1 h-1 rounded-full bg-green-500 animate-pulse"></div>
                        Live
                      </div>
                    </div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.1em] opacity-40 mb-2" style={{ color: MOE_COLORS.textMain }}>{stat.label}</p>
                    <div className="flex items-baseline gap-2">
                      <h3 className="text-4xl font-bold tracking-tight" style={{ color: MOE_COLORS.textMain }}>{stat.value}</h3>
                      <span className="text-[14px] font-semibold opacity-30 uppercase">{stat.unit}</span>
                    </div>
                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-black/5">
                      <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-green-600/80">{stat.trend}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </main>

        {/* Footer */}
        <footer className="py-4 px-12 text-center">
          <p className="text-[12px] font-medium tracking-wide text-black/40 flex items-center justify-center gap-1">
            <span>Copyright © {new Date().getFullYear()}, made with</span>
            <span className="text-red-400">♥</span>
            <span>by</span>
            <img src="/bict-logo.png" alt="BICT" className="h-4 inline-block mx-1" />
            <span>ศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร สำนักงานปลัดกระทรวงศึกษาธิการ</span>
          </p>
        </footer>
      </div>
    </div>
  ), [searchValue, showDropdown, filteredSuggestions, placeholderIndex, fade, isListening, user, greeting, handleSubmit, handleSuggestionClick, handleVoiceSearch, onStart, onLogout, onAdminLogin]);

  // Render based on screen size
  return (
    <>
      <div className="md:hidden">
        {mobileView}
      </div>
      <div className="hidden md:block">
        {desktopView}
      </div>
    </>
  );
};

export default React.memo(LandingPage);
