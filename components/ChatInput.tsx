/**
 * 📄 ชื่อไฟล์: ChatInput.tsx
 * 📝 คำอธิบาย:
 *    ช่องรับข้อความ (Input Area) ที่อยู่ด้านล่างของหน้าแชท
 *    ออกแบบให้ดูสวยงาม (Glassmorphism) และรองรับหลายรูปแบบ
 *
 * 🛠 หน้าที่หลัก:
 *    1. Text Input: รับข้อความตัวอักษร พร้อมขยายขนาดอัตโนมัติ
 *    2. Voice Input: รองรับการสั่งงานด้วยเสียง (Speech-to-Text)
 *    3. Image Upload: รองรับการอัปโหลดรูปภาพเพื่อถามเกี่ยวกับรูป
 *    4. UI Effects: มีเอฟเฟกต์แสงเงาและความโปร่งใสสวยงาม
 */

import React, { useState, useRef, useEffect } from 'react';
import { MOE_COLORS } from '../constants';

interface ChatInputProps {
  onSend: (message: string, imageData: string | null) => void;
  disabled?: boolean;
  isLoading?: boolean; // ✨ For showing stop button
  onStop?: () => void; // ✨ Callback to stop AI generation
}

const ChatInput: React.FC<ChatInputProps> = ({ onSend, disabled, isLoading = false, onStop }) => {
  const [text, setText] = useState('');
  const [image, setImage] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if ((text.trim() || image) && !disabled) {
      onSend(text.trim(), image);
      setText('');
      setImage(null);
      if (textareaRef.current) textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = (reader.result as string).split(',')[1];
        setImage(base64String);
      };
      reader.readAsDataURL(file);
    }
  };

  const toggleListening = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert("Browser ของคุณไม่รองรับการสั่งงานด้วยเสียงครับ");
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = 'th-TH';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setText(prev => prev + (prev ? ' ' : '') + transcript);
    };

    recognition.start();
  };

  return (
    <div className="flex flex-col gap-3 w-full max-w-4xl mx-auto px-2 md:px-4">
      {/* Image Preview - Floating Card */}
      {image && (
        <div className="flex px-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="relative group">
            <img
              src={`data:image/jpeg;base64,${image}`}
              alt="upload preview"
              className="w-24 h-24 object-cover rounded-2xl border border-white/40 shadow-2xl backdrop-blur-md"
            />
            <button
              onClick={() => setImage(null)}
              className="absolute -top-2 -right-2 w-7 h-7 bg-black/80 text-white rounded-full flex items-center justify-center scale-0 group-hover:scale-100 transition-all shadow-lg backdrop-blur-md border border-white/20"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Apple 2026 visionOS Glass Input Bar */}
      <div className="relative group/input transition-all duration-500 ease-out focus-within:scale-[1.01] focus-within:-translate-y-0.5">
        {/* visionOS Glow Ring on Focus */}
        <div className="absolute -inset-[2px] rounded-[26px] bg-gradient-to-b from-[#007AFF]/20 via-[#5856D6]/10 to-transparent opacity-0 group-focus-within/input:opacity-100 transition-opacity duration-500 blur-sm pointer-events-none"></div>

        {/* Main Glass Container - Enhanced for 2026 */}
        <div className="relative bg-white/85 backdrop-blur-[50px] rounded-[26px] shadow-[0_8px_40px_rgba(0,0,0,0.06)] border border-white/70 overflow-hidden transition-all duration-500 ease-out group-focus-within/input:shadow-[0_20px_60px_-10px_rgba(0,0,0,0.15),0_0_40px_rgba(0,122,255,0.08)] group-focus-within/input:bg-white/95 group-focus-within/input:border-white/90" style={{ backdropFilter: 'blur(50px) saturate(180%)' }}>
          {/* Input Area with Sparkle Icon */}
          <div className="px-4 pt-4 pb-2 md:px-6 md:pt-5 md:pb-2 flex items-start gap-3">
            {/* Sparkle Icon - Apple 2026 Color */}
            <div className="w-6 h-6 flex-shrink-0 mt-1 text-[#32D74B]/80">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                <path fillRule="evenodd" d="M9 4.5a.75.75 0 01.721.544l.813 2.846a3.75 3.75 0 002.576 2.576l2.846.813a.75.75 0 010 1.442l-2.846.813a3.75 3.75 0 00-2.576 2.576l-.813 2.846a.75.75 0 01-1.442 0l-.813-2.846a3.75 3.75 0 00-2.576-2.576l-2.846-.813a.75.75 0 010-1.442l2.846-.813A3.75 3.75 0 007.466 7.89l.813-2.846A.75.75 0 019 4.5zM18 1.5a.75.75 0 01.728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 010 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 01-1.456 0l-.258-1.036a2.625 2.625 0 00-1.91-1.91l-1.036-.258a.75.75 0 010-1.456l1.036-.258a2.625 2.625 0 001.91-1.91l.258-1.036A.75.75 0 0118 1.5z" clipRule="evenodd" />
              </svg>
            </div>
            <textarea
              ref={textareaRef}
              value={text}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder="เริ่มคำถามของคุณ แล้วให้ DO AI ช่วยค้นหา..."
              className="flex-1 bg-transparent border-none focus:ring-0 resize-none text-[16px] md:text-[17px] font-medium leading-[1.5] text-[#1D1D1F] placeholder:text-black/35 placeholder:font-normal max-h-[150px] md:max-h-[200px]"
              rows={1}
            />
          </div>

          {/* Controls Row - Spacious */}
          <div className="flex items-center justify-between px-4 pb-3 md:px-5 md:pb-4">
            {/* Left Tools - iOS Style Buttons */}
            <div className="flex items-center gap-1.5">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="image/*"
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-9 h-9 rounded-xl bg-black/5 hover:bg-black/10 flex items-center justify-center text-[#1D1D1F]/50 hover:text-[#1D1D1F]/80 transition-all active:scale-95"
                title="แนบไฟล์"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                </svg>
              </button>
              <button
                type="button"
                className="w-9 h-9 rounded-xl bg-black/5 hover:bg-black/10 flex items-center justify-center text-[#1D1D1F]/50 hover:text-[#1D1D1F]/80 transition-all active:scale-95"
                title="เอกสาร"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
              </button>
            </div>

            {/* Right Tools */}
            <div className="flex items-center gap-2">
              {/* Dictation Icon */}
              <button
                type="button"
                onClick={toggleListening}
                className={`w-9 h-9 md:w-10 md:h-10 rounded-full flex items-center justify-center transition-all active:scale-95
                  ${isListening
                    ? 'bg-[#FF3B30] text-white animate-pulse shadow-inner'
                    : 'bg-black/5 hover:bg-black/10 text-[#1D1D1F]/60'
                  }`}
                title="Voice"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-[18px] h-[18px] md:w-[20px] md:h-[20px]">
                  <path d="M8.25 4.5a3.75 3.75 0 117.5 0v8.25a3.75 3.75 0 11-7.5 0V4.5z" />
                  <path d="M6 10.5a.75.75 0 01.75.75v1.5a5.25 5.25 0 1010.5 0v-1.5a.75.75 0 011.5 0v1.5a6.751 6.751 0 01-6 6.709v2.291h3a.75.75 0 010 1.5h-7.5a.75.75 0 010-1.5h3v-2.291a6.751 6.751 0 01-6-6.709v-1.5A.75.75 0 016 10.5z" />
                </svg>
              </button>

              {/* Send / Stop Button - Apple 2026 Style */}
              {isLoading && onStop ? (
                /* ✨ Stop Button - Animated Pulse */
                <button
                  onClick={onStop}
                  className="w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center transition-all bg-gradient-to-br from-[#FF3B30] to-[#FF6B60] text-white hover:scale-105 active:scale-95 shadow-lg shadow-red-500/25 animate-pulse"
                  title="หยุดการประมวลผล"
                >
                  {/* Stop Icon (Square) */}
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 md:w-6 md:h-6">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                </button>
              ) : (
                /* Send Button */
                <button
                  onClick={() => handleSubmit()}
                  disabled={(!text.trim() && !image) || disabled}
                  className={`w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center transition-all
                    ${(!text.trim() && !image) || disabled
                      ? 'bg-black/5 text-[#1D1D1F]/15 cursor-not-allowed'
                      : 'bg-gradient-to-br from-[#1D1D1F] to-[#3D3D3F] text-white hover:scale-105 active:scale-95 shadow-lg hover:shadow-[0_8px_24px_rgba(0,0,0,0.15)]'}`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5 md:w-6 md:h-6">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(ChatInput);