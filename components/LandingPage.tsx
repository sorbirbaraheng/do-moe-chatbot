

/**
 * 📄 ชื่อไฟล์: LandingPage.tsx
 * 📝 คำอธิบาย:
 *    หน้าแรกของเว็บไซต์ (Landing Page)
 *    ออกแบบให้ดูทันสมัย พรีเมียม เพื่อสร้างความประทับใจแรก
 *
 * 🛠 หน้าที่หลัก:
 *    1. Hero Section: แสดงคำทักทายและชื่อผู้ใช้
 *    2. Smart Search: ช่องค้นหาที่รองรับการพิมพ์และเสียง (Voice Search)
 *    3. Dashboard Widgets: แสดงสถิติเบื้องต้น (โรงเรียน, ครู, นักเรียน)
 *    4. Navigation: ปุ่มเข้าสู่ระบบแอดมินและเริ่มแชท
 */

import React, { useState, useEffect, useMemo, useRef } from 'react';
import { MOE_COLORS, COMMON_QUERIES, MOCK_STATS } from '../constants';
import { Category, User } from '../types';

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
      // Always start in General - AI will recommend switching if needed
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

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setSearchValue(transcript);
      setIsListening(false);
      // Always start in General found
      setTimeout(() => onStart(Category.General, transcript), 500);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.start();
  };

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return { main: "Good morning", sub: "เริ่มต้นวันแห่งการเรียนรู้ด้วยข้อมูลดิจิทัล" };
    if (hour >= 12 && hour < 17) return { main: "Good afternoon", sub: "ยกระดับการตัดสินใจด้วยฐานข้อมูลอัจฉริยะ" };
    if (hour >= 17 && hour < 21) return { main: "Good evening", sub: "สรุปภาพรวมการศึกษาเพื่อการพัฒนาที่ยั่งยืน" };
    return { main: "Good night", sub: "ศูนย์เทคโนโลยีสารสนเทศฯ พร้อมสนับสนุนข้อมูลตลอดเวลา" };
  }, []);

  return (
    <div className="min-h-screen flex flex-col overflow-auto relative bg-[#FBFBFE]">
      {/* Custom Background Image - User Request */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <div
          className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-opacity duration-1000"
          style={{ backgroundImage: 'url("/landing-bg-purple.jpg")' }}
        ></div>

        {/* Light overlay for text readability */}
        <div className="absolute inset-0 bg-white/10"></div>

        {/* Subtle Grain Texture */}
        <div className="absolute inset-0 opacity-[0.03] mix-blend-overlay" style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\'/%3E%3C/svg%3E")' }}></div>
      </div>

      <div className="relative z-10 flex-1 flex flex-col safe-area-inset">
        {/* Navbar - Modern & Floating */}
        <nav className="flex items-center justify-between px-5 md:px-12 py-3 md:py-6 z-20 flex-shrink-0">
          <div className="flex items-center gap-3 md:gap-4 cursor-pointer group" onClick={() => onStart(Category.Auto)}>
            {/* Apple-style Glass Logo Container - Compact Mobile */}
            <div className="w-10 h-10 md:w-12 md:h-12 rounded-2xl bg-white/80 backdrop-blur-xl border border-white/60 shadow-lg flex items-center justify-center overflow-hidden flex-shrink-0">
              <img src="/do-mascot.png" alt="DO" className="w-8 h-8 md:w-10 md:h-10 object-contain" />
            </div>
            {/* Hide text on very small screens or make it very compact */}
            <div className={`flex flex-col ${user ? 'hidden sm:flex' : 'flex'}`}>
              <span className="font-bold text-[18px] md:text-[22px] tracking-tight text-[#1D1D1F] leading-tight block">MOE - One</span>
              <p className="text-[9px] md:text-[10px] font-semibold text-black/40 uppercase tracking-[0.1em] leading-tight">กระทรวงศึกษาธิการ</p>
            </div>
          </div>

          <div className="flex items-center gap-2 md:gap-3">
            {user ? (
              <div className="flex items-center gap-4 bg-white/40 backdrop-blur-xl border border-white/60 p-1 md:p-1.5 md:pl-5 rounded-full shadow-sm hover:shadow-md transition-all group">
                <div className="hidden md:flex flex-col items-end leading-tight pr-1">
                  <span className="text-[13px] font-bold" style={{ color: MOE_COLORS.textMain }}>{user.name}</span>
                  <span className="text-[10px] opacity-40 font-black uppercase tracking-wider">{user.role}</span>
                </div>
                <div
                  className="w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center text-[10px] md:text-[11px] font-black shadow-inner border border-black/5 bg-white scale-90 group-hover:scale-100 transition-transform"
                  style={{ color: MOE_COLORS.textMain }}
                >
                  {user.initials}
                </div>
                <div className="hidden md:block h-6 w-[1px] bg-black/5 mx-1"></div>
                <button
                  onClick={() => onLogout()}
                  className="hidden md:flex w-10 h-10 rounded-full items-center justify-center text-red-400 hover:bg-red-50 hover:text-red-600 transition-all active:scale-90"
                  title="ออกจากระบบ"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
                  </svg>
                </button>
              </div>
            ) : null}

            <button
              onClick={() => onStart()}
              className="bg-[#1D1D1F] text-white px-5 md:px-8 py-2 md:py-2.5 rounded-full text-[13px] md:text-[14px] font-bold hover:bg-black transition-all shadow-xl active:scale-95 whitespace-nowrap"
            >
              {user ? 'แชท' : 'โหมดแชท'}
            </button>

            {/* Desktop Admin Button - Hidden on Mobile */}
            {/* LINE Chatbot Link */}
            <a
              href="https://line.me/R/ti/p/@203oozkj"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden md:flex items-center gap-2 px-4 py-2.5 ml-2 rounded-full bg-white text-[#06C755] border border-[#06C755]/30 text-[12px] font-bold hover:bg-[#06C755]/5 hover:shadow-[0_4px_12px_rgba(6,199,85,0.15)] hover:scale-105 active:scale-95 transition-all"
            >
              <img src="/line-logo.png" alt="LINE" className="w-5 h-5 object-contain" />
              LINE Chat
            </a>

            <button
              onClick={onAdminLogin}
              className="admin-desktop-only hidden md:flex px-4 py-2.5 rounded-full text-[12px] font-bold text-black/60 hover:text-black hover:bg-black/5 transition-all items-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
              Admin
            </button>
          </div>
        </nav>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col items-center justify-center px-4 md:px-6 py-2 md:py-4 text-center z-10 overflow-hidden">
          <div className="w-full max-w-5xl flex flex-col items-center gap-4 md:gap-8 min-h-0">

            {/* Hero Section - Apple-style Premium Typography */}
            <div className="slide-up-content stagger-1 w-full px-2">
              <p key={`greeting-sub-${user?.name ? 'user' : 'guest'}`} className="text-[11px] md:text-[14px] font-semibold mb-3 md:mb-4 tracking-[0.15em] opacity-40 uppercase simple-fade text-center" style={{ color: MOE_COLORS.textMain }}>
                {greeting.sub}
              </p>

              <h1
                className={`font-bold tracking-[-0.04em] leading-[1.1] mb-2 md:mb-4 text-center simple-fade
                  ${user?.name ? 'text-3xl sm:text-4xl md:text-6xl' : 'text-4xl sm:text-5xl md:text-7xl'}
                `}
                key={user?.name || 'guest'}
                style={{ color: MOE_COLORS.textMain }}
              >
                {user?.name ? (
                  <>
                    <span className="opacity-90 block md:inline mb-1 md:mb-0">{greeting.main}, </span>
                    <span className="text-gradient-apple block md:inline">
                      {user.name.length > 12 ? user.name.substring(0, 12) + '...' : user.name}
                    </span>
                  </>
                ) : (
                  <span className="inline-flex items-center justify-center gap-3 flex-wrap">
                    <span className="text-gradient-apple">Welcome to MOE - One</span>
                    <span
                      className="inline-flex items-center justify-center px-5 py-2 rounded-2xl shadow-sm align-middle ml-3"
                      style={{
                        background: 'rgba(255, 255, 255, 0.5)',
                        backdropFilter: 'blur(20px) saturate(180%)',
                        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
                        border: '1px solid rgba(255, 255, 255, 0.6)',
                        boxShadow: '0 8px 32px rgba(31, 38, 135, 0.07), inset 0 1px 1px rgba(255, 255, 255, 0.8)',
                      }}
                    >
                      <span
                        style={{
                          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #667eea 75%, #764ba2 100%)',
                          backgroundSize: '200% 200%',
                          WebkitBackgroundClip: 'text',
                          WebkitTextFillColor: 'transparent',
                          backgroundClip: 'text',
                          animation: 'shimmer 3s ease-in-out infinite',
                          fontWeight: 900,
                          letterSpacing: '0.05em',
                          fontSize: '1em'
                        }}
                      >
                        AI
                      </span>
                    </span>
                  </span>
                )}
              </h1>

              <p className="text-[14px] md:text-xl font-medium tracking-tight opacity-60 leading-relaxed max-w-[280px] md:max-w-xl mx-auto text-center mt-2 md:mt-4">
                {user?.name
                  ? 'อัจฉริยะข้อมูลการศึกษาเพื่อคุณ'
                  : 'เราพร้อมสนับสนุนข้อมูลและขับเคลื่อนอนาคตการศึกษาไทย'}
              </p>
            </div>



            {/* Search Section - Redesigned for Mobile (Stacked or Compact) */}
            <div className="relative w-full max-w-3xl mx-auto slide-up-content stagger-2 px-1" ref={dropdownRef}>
              <form
                onSubmit={handleSubmit}
                className="group w-full p-2 md:px-8 md:py-5 rounded-[2rem] md:rounded-[2.5rem] bg-white border border-[#E5E5E7] shadow-[0_15px_40px_rgba(0,0,0,0.08)] transition-all hover:shadow-[0_40px_90px_rgba(0,0,0,0.1)] flex md:items-center relative flex-col md:flex-row gap-3 md:gap-0"
              >
                {/* Mobile: Search Input Area */}
                <div className="flex items-center w-full gap-3 px-3 py-2 md:p-0">
                  <div className="flex-shrink-0 opacity-40 group-focus-within:opacity-100 transition-opacity">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5 md:w-6 md:h-6">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
                    </svg>
                  </div>

                  <div className="flex-1 relative h-full flex items-center min-h-[44px]">
                    <input
                      type="text"
                      value={searchValue}
                      onChange={(e) => {
                        setSearchValue(e.target.value);
                        setShowDropdown(true);
                      }}
                      onFocus={() => setShowDropdown(true)}
                      className="w-full bg-transparent border-none outline-none text-[16px] md:text-xl font-semibold tracking-normal placeholder:text-black/20 h-full"
                      style={{ color: MOE_COLORS.textMain }}
                      placeholder=" "
                    />
                    {!searchValue && (
                      <div className={`absolute left-0 pointer-events-none transition-all duration-500 flex items-center gap-2 ${fade ? 'opacity-40' : 'opacity-0'}`}>
                        <span className="text-[14px] md:text-xl font-semibold tracking-normal truncate text-black/30">
                          {flatSuggestions[placeholderIndex].text}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Mobile: Voice Button inline */}
                  <div
                    onClick={handleVoiceSearch}
                    className={`md:hidden p-2 rounded-full cursor-pointer transition-all active:scale-95 ${isListening ? 'bg-red-100 text-red-500 animate-pulse' : 'text-black/40 hover:bg-black/5'}`}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill={isListening ? "currentColor" : "none"} viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
                    </svg>
                  </div>
                </div>

                {/* Mobile: Action Button Area (Separate Row on Mobile) */}
                <div className="flex items-center justify-between w-full md:w-auto md:gap-5 pl-3 pr-1 pb-1 md:p-0 border-t md:border-t-0 border-black/5 pt-2 md:pt-0">
                  {/* Mobile: Voice Status Text if active */}
                  <div className="md:hidden text-xs font-bold text-black/40">
                    {isListening ? 'กำลังฟัง...' : ''}
                  </div>

                  <div className="flex items-center gap-3 ml-auto">
                    {/* Desktop Voice Button */}
                    <div
                      onClick={handleVoiceSearch}
                      className={`hidden md:flex p-2.5 rounded-full cursor-pointer hover:bg-black/5 transition-all text-black/40 hover:text-black active:scale-95 ${isListening ? 'bg-red-50 text-red-500 animate-pulse ring-2 ring-red-100' : ''}`}
                      title="Voice Search"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill={isListening ? "currentColor" : "none"} viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
                      </svg>
                    </div>

                    {/* Go Button - Full width on VERY small screens? No, circle is better for consistency */}
                    <button
                      type="submit"
                      className="w-10 h-10 md:w-12 md:h-12 rounded-full bg-[#1D1D1F] text-white flex items-center justify-center shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 transition-all"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5 md:w-6 md:h-6">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                      </svg>
                    </button>
                  </div>
                </div>
              </form>

              {showDropdown && filteredSuggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-4 mx-4 md:mx-6 bg-white/90 backdrop-blur-xl rounded-[2rem] border border-white/50 shadow-2xl overflow-hidden z-30 animate-in fade-in slide-in-from-top-2">
                  <div className="p-2">
                    {filteredSuggestions.map((suggestion, index) => (
                      <button
                        key={index}
                        onClick={() => handleSuggestionClick(suggestion)}
                        className="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-black/5 transition-all text-left"
                      >
                        <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center text-xs">
                          {suggestion.cat === Category.General ? '🌍' : suggestion.cat === Category.School ? '🏫' : '📊'}
                        </div>
                        <span className="text-[14px] md:text-[16px] font-medium text-black/80">{suggestion.text}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Statistics Section Cards - Apple 2026 Style with Mobile Horizontal Scroll */}
            <div className="w-full max-w-5xl slide-up-content stagger-3">
              {/* Mobile: Horizontal scroll | Desktop: Grid */}
              <div className="mobile-scroll-x md:grid md:grid-cols-3 gap-4 md:gap-6 pb-4 md:pb-0 px-2 md:px-0 -mx-2 md:mx-0">
                {MOCK_STATS.map((stat, idx) => (
                  <div
                    key={idx}
                    onClick={() => onStart(stat.category)}
                    className="animate-spring w-[280px] md:w-auto flex-shrink-0 md:flex-shrink bg-white/60 backdrop-blur-2xl group p-5 md:p-6 rounded-[2rem] text-left transition-all hover:scale-[1.03] hover:bg-white/80 cursor-pointer shadow-[0_10px_40px_rgba(0,0,0,0.03)] hover:shadow-[0_30px_70px_rgba(0,0,0,0.07),0_0_60px_rgba(0,122,255,0.08)] border border-white/80 relative overflow-hidden active:scale-95"
                    style={{ animationDelay: `${idx * 100}ms` }}
                  >
                    {/* visionOS 2026 Corner Glow */}
                    <div className="absolute -top-10 -right-10 w-24 h-24 bg-gradient-to-br from-blue-400/20 to-purple-400/20 rounded-full blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>

                    <div className="flex items-center justify-between mb-4">
                      <div className="w-12 h-12 rounded-2xl bg-white shadow-sm flex items-center justify-center text-2xl group-hover:scale-110 group-hover:shadow-lg transition-all duration-300">
                        {stat.icon}
                      </div>
                      <div className="flex flex-col items-end">
                        <div className="text-[8px] md:text-[9px] font-black uppercase tracking-[0.15em] px-2.5 py-1 bg-green-50/80 text-green-600 rounded-full border border-green-100/50 flex items-center gap-1.5 backdrop-blur-sm">
                          <div className="w-1 h-1 rounded-full bg-green-500 animate-pulse"></div>
                          <span className="hidden sm:inline">อัปเดตรายสัปดาห์โดย AI</span>
                          <span className="sm:hidden">Live</span>
                        </div>
                      </div>
                    </div>

                    <div className="mb-0">
                      <p className="text-[10px] md:text-[11px] font-bold uppercase tracking-[0.1em] opacity-40 mb-2" style={{ color: MOE_COLORS.textMain }}>{stat.label}</p>
                      <div className="flex items-baseline gap-2">
                        <h3 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ color: MOE_COLORS.textMain }}>{stat.value}</h3>
                        <span className="text-[12px] md:text-[14px] font-semibold opacity-30 uppercase tracking-tight">{stat.unit}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-black/5">
                      <p className="text-[10px] md:text-[11px] font-bold uppercase tracking-[0.1em] text-green-600/80">{stat.trend}</p>
                      <p className="text-[8px] md:text-[9px] font-medium opacity-30 uppercase tracking-wider">
                        {stat.lastUpdated && `อัปเดต: ${stat.lastUpdated}`}
                      </p>
                    </div>

                    <div className={`absolute -bottom-8 -right-8 w-32 h-32 bg-gradient-to-br ${stat.color} opacity-[0.04] rounded-full group-hover:scale-150 transition-transform duration-700`}></div>
                  </div>
                ))}
              </div>
              {/* Mobile scroll indicator */}
              <div className="flex justify-center gap-1.5 mt-3 md:hidden">
                {MOCK_STATS.map((_, idx) => (
                  <div key={idx} className="w-1.5 h-1.5 rounded-full bg-black/10"></div>
                ))}
              </div>
            </div>
          </div>

        </main>

        {/* Footer */}
        <footer className="py-4 px-6 md:px-12 text-center flex-shrink-0">
          <p className="text-[12px] font-medium tracking-wide text-black/40 flex items-center justify-center gap-1 flex-wrap">
            <span>Copyright © {new Date().getFullYear()}, made with</span>
            <span className="text-red-400">♥</span>
            <span>by</span>
            <img src="/bict-logo.png" alt="BICT" className="h-4 inline-block mx-1" />
            <span>ศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร สำนักงานปลัดกระทรวงศึกษาธิการ</span>
          </p>
        </footer>
      </div >
    </div >
  );
};

export default React.memo(LandingPage);
