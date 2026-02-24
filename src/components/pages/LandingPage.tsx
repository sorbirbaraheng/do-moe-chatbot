

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
  const [showMenu, setShowMenu] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
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
  // MOBILE VIEW - Gemini-Style Layout (no useMemo to ensure state reactivity)
  // ===============================================
  const renderMobileView = () => (
    <div className="landing-mobile h-[100dvh] bg-[#EEF0F8] flex flex-col relative">

      {/* ── Menu Bottom Sheet ── */}
      {showMenu && (
        <div className="absolute inset-0 z-50 flex flex-col justify-end" onClick={() => setShowMenu(false)}>
          <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />
          <div className="relative bg-white rounded-t-[28px] px-5 pt-5 pb-10 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="w-10 h-1 bg-black/10 rounded-full mx-auto mb-6" />
            <p className="text-[12px] font-semibold text-[#86868b] uppercase tracking-wider mb-3 px-1">เมนู</p>
            <button
              onClick={() => { setShowMenu(false); onStart(); }}
              className="w-full flex items-center gap-4 px-4 py-4 rounded-2xl hover:bg-[#F2F2F7] active:bg-[#E5E5EA] transition-colors text-left"
            >
              <div className="w-10 h-10 rounded-xl bg-[#007AFF]/10 flex items-center justify-center">
                <svg viewBox="0 0 24 24" fill="none" stroke="#007AFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <div>
                <p className="text-[16px] font-semibold text-[#1d1d1f]">เริ่มแชท</p>
                <p className="text-[12px] text-[#86868b]">คุยกับ DO AI</p>
              </div>
            </button>
          </div>
        </div>
      )}

      {/* ── Profile Bottom Sheet ── */}
      {showProfile && (
        <div className="absolute inset-0 z-50 flex flex-col justify-end" onClick={() => setShowProfile(false)}>
          <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />
          <div className="relative bg-white rounded-t-[28px] px-5 pt-5 pb-10 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="w-10 h-1 bg-black/10 rounded-full mx-auto mb-6" />
            {user ? (
              <>
                <div className="flex items-center gap-4 mb-6 px-1">
                  <div className="w-14 h-14 rounded-full bg-gradient-to-br from-[#5856D6] to-[#007AFF] flex items-center justify-center text-white text-[18px] font-bold shadow-md">
                    {user.initials}
                  </div>
                  <div>
                    <p className="text-[17px] font-bold text-[#1d1d1f]">{user.name}</p>
                    <p className="text-[13px] text-[#86868b]">{user.role}</p>
                  </div>
                </div>
                <button
                  onClick={() => { setShowProfile(false); onLogout(); }}
                  className="w-full py-4 rounded-2xl bg-red-50 text-[#FF3B30] text-[16px] font-semibold active:bg-red-100 transition-colors"
                >
                  ออกจากระบบ
                </button>
              </>
            ) : (
              <button
                onClick={() => { setShowProfile(false); onStart(); }}
                className="w-full py-4 rounded-2xl bg-[#007AFF] text-white text-[16px] font-semibold active:opacity-80 transition-opacity"
              >
                เริ่มใช้งาน
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Top Bar ── */}
      <header className="flex-shrink-0 flex items-center justify-between px-5 pt-12 pb-3">
        {/* Hamburger */}
        <button
          onClick={() => setShowMenu(true)}
          className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-black/5 active:bg-black/10 transition-colors"
          aria-label="เมนู"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="#1d1d1f" strokeWidth="2.2" strokeLinecap="round" className="w-5 h-5">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>

        {/* App Name */}
        <span className="text-[17px] font-semibold text-[#1d1d1f] tracking-tight">MOE - One</span>

        {/* Avatar */}
        <button
          onClick={() => user ? setShowProfile(true) : onStart()}
          className="w-10 h-10 rounded-full overflow-hidden bg-gradient-to-br from-[#5856D6] to-[#007AFF] flex items-center justify-center shadow-sm ring-2 ring-white/60 active:scale-95 transition-transform"
          aria-label="โปรไฟล์"
        >
          {user ? (
            <span className="text-white text-[13px] font-bold">{user.initials}</span>
          ) : (
            <img src="/do-mascot.png" alt="DO" className="w-8 h-8 object-contain" />
          )}
        </button>
      </header>

      {/* ── Scrollable Middle ── */}
      <div className="flex-1 overflow-y-auto px-5 pt-6 pb-4" style={{ WebkitOverflowScrolling: 'touch' }}>

        {/* Greeting */}
        <div className="mb-8">
          <p className="text-[15px] text-[#5f6368] font-medium mb-1">
            {user ? `สวัสดี คุณ ${user.name.split(' ')[0]}` : greeting.sub}
          </p>
          <h1 className="text-[26px] font-bold text-[#1d1d1f] leading-[1.2] tracking-tight">
            {user ? 'เราจะเริ่มจากตรงไหนก่อนดี' : 'ยินดีต้อนรับสู่\nMOE - One AI'}
          </h1>
        </div>

        {/* Suggestion Chips — pill style, wrapping */}
        <div className="flex flex-wrap gap-3">
          {[
            { emoji: '🏫', label: 'ค้นหาโรงเรียนใกล้ฉัน' },
            { emoji: '👩‍🏫', label: 'สรุปสถิติครูทั่วประเทศ' },
            { emoji: '📊', label: 'แนวโน้มจำนวนนักเรียนปีนี้' },
            { emoji: '🏆', label: 'โรงเรียนที่มีนักเรียนมากที่สุด' },
            { emoji: '📍', label: 'โรงเรียนในจังหวัดเชียงใหม่' },
            { emoji: '✏️', label: 'เขียนอะไรก็ได้' },
          ].map((chip, i) => (
            <button
              key={i}
              onClick={() => onStart(Category.General, chip.label !== 'เขียนอะไรก็ได้' ? chip.label : undefined)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-white/80 backdrop-blur-md border border-white/60 shadow-sm text-[14px] font-medium text-[#1d1d1f] active:scale-95 active:bg-white/60 transition-all duration-200"
              style={{ boxShadow: '0 2px 10px rgba(0,0,0,0.06)' }}
            >
              <span>{chip.emoji}</span>
              <span>{chip.label}</span>
            </button>
          ))}
        </div>

        {/* Bottom padding so chips don't hide behind input */}
        <div className="h-10" />
      </div>

      {/* ── Fixed Bottom Input Bar (Gemini-style) ── */}
      <div className="flex-shrink-0 px-4 pb-8 pt-3 bg-[#EEF0F8]">
        <div
          ref={dropdownRef}
          className="relative bg-white rounded-[26px] shadow-[0_4px_24px_rgba(0,0,0,0.08)] border border-white/60"
        >
          {/* Search input row */}
          <form onSubmit={handleSubmit} className="flex items-center px-5 py-4 gap-3">
            <input
              type="text"
              value={searchValue}
              onChange={(e) => { setSearchValue(e.target.value); setShowDropdown(true); }}
              onFocus={() => setShowDropdown(searchValue.length > 0)}
              placeholder="ขอความช่วยเหลือจาก DO AI"
              className="flex-1 bg-transparent text-[15px] text-[#1d1d1f] placeholder:text-[#aeaeb2] font-medium outline-none border-none"
            />
          </form>

          {/* Suggestions dropdown */}
          {showDropdown && filteredSuggestions.length > 0 && (
            <div className="absolute bottom-full left-0 right-0 mb-2 p-1.5 bg-white/95 backdrop-blur-2xl rounded-2xl border border-white/40 shadow-[0_12px_40px_rgba(0,0,0,0.10)] z-40">
              {filteredSuggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => { handleSuggestionClick(s); setShowDropdown(false); }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[#F2F2F7] transition-colors text-left"
                >
                  <span className="text-base">{s.cat === Category.School ? '🏫' : s.cat === Category.General ? '🌍' : '📊'}</span>
                  <span className="text-[14px] font-medium text-[#1d1d1f]">{s.text}</span>
                </button>
              ))}
            </div>
          )}

          {/* Bottom toolbar row */}
          <div className="flex items-center justify-between px-4 pb-3">
            {/* Left: + button */}
            <button
              type="button"
              className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-black/5 active:bg-black/10 transition-colors text-[#5f6368]"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="w-5 h-5">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>

            {/* Center: Model selector pill */}
            <button
              type="button"
              onClick={() => onStart()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#F2F2F7] hover:bg-[#E5E5EA] active:scale-95 transition-all text-[13px] font-semibold text-[#3c3c43]"
            >
              <span>DO AI</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 opacity-60">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            {/* Right: Mic button */}
            <button
              type="button"
              onClick={handleVoiceSearch}
              className={`w-9 h-9 flex items-center justify-center rounded-full transition-all active:scale-90 ${isListening ? 'bg-red-500 text-white animate-pulse' : 'hover:bg-black/5 text-[#5f6368]'}`}
            >
              <svg viewBox="0 0 24 24" fill={isListening ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            </button>
          </div>
        </div>
      </div>

    </div>
  );

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
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
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
        {renderMobileView()}
      </div>
      <div className="hidden md:block">
        {desktopView}
      </div>
    </>
  );
};

export default React.memo(LandingPage);
