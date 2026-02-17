

/**
 * 📄 ชื่อไฟล์: MessageBubble.tsx
 * 📝 คำอธิบาย:
 *    กล่องข้อความสนทนา (Chat Bubble)
 *    ใช้แสดงผลทั้งข้อความของผู้ใช้และคำตอบของ AI
 *
 * 🛠 หน้าที่หลัก:
 *    1. Markdown Rendering: แปลงข้อความ Markdown เป็น HTML สวยงาม (ตัวหนา, ลิสต์, ตาราง)
 *    2. Interactive Widgets: แสดงกราฟ (Chart) และแผนที่ (Map) หากคำตอบมีข้อมูลเหล่านี้
 *    3. Edit & Actions: ปุ่มแก้ไขข้อความ, คัดลอก, และให้ AI ตอบใหม่ (Regenerate)
 *    4. Thinking Process: แสดงกระบวนการคิดของ AI (สามารถพับเก็บได้)
 */

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Message } from '../types';
import { MOE_COLORS } from '../constants';
import ChartWidget from './ChartWidget';
import MapWidget from './MapWidget';
import { saveFeedback } from '../services/feedbackService';

/**
 * Clean up markdown formatting issues from LLM output
 * - Convert inline `*` bullets to proper markdown list format
 * - Add proper line breaks for better rendering
 */
const cleanupMarkdown = (text: string): string => {
  if (!text) return '';

  let cleaned = text;

  // Fix: "มีดังนี้: * item" -> "มีดังนี้:\n\n- item"
  cleaned = cleaned.replace(/:\s*\*\s+/g, ':\n\n- ');

  // Fix: Standalone "*" at start of line -> "-"
  cleaned = cleaned.replace(/^\*\s+/gm, '- ');

  // Fix: "• " bullet points (already correct but ensure consistency)
  cleaned = cleaned.replace(/•\s+/g, '- ');

  // Fix: Multiple consecutive bullet points need newlines between
  cleaned = cleaned.replace(/(-\s.+?)(\s+-\s)/g, '$1\n$2');

  return cleaned;
};

interface MessageBubbleProps {
  message: Message;
  isAdminMode?: boolean;
  userAvatar?: string;
  userInitials?: string;
  onRegenerate?: () => void; // ✨ Regenerate Response callback
  onEdit?: (messageId: string, newContent: string) => void; // ✨ Edit Message callback
  isLastAssistantMessage?: boolean; // Only show regenerate for last message
  isLatestMessage?: boolean; // ✨ For glow halo on the latest bubble
  lastUserMessage?: string; // ✨ For generating context-aware thinking status
  sessionId?: string; // For feedback tracking
  category?: 'general' | 'school' | 'student'; // For feedback tracking
  onSuggestionClick?: (text: string) => void; // ✨ Suggestion chip click callback
}

// Generate thinking status based on user's question
const generateThinkingStatus = (question: string): string[] => {
  const lower = question?.toLowerCase() || '';
  const statuses: string[] = [];

  // School-related keywords
  if (lower.includes('โรงเรียน') || lower.includes('สถานศึกษา') || lower.includes('ร.ร.')) {
    statuses.push('น้องดีโอกำลังค้นหาข้อมูลโรงเรียนครับ...');
  }

  // Location keywords
  if (lower.includes('จังหวัด') || lower.includes('อำเภอ') || lower.includes('ตำบล') || lower.includes('เขต')) {
    statuses.push('น้องดีโอกำลังค้นหาข้อมูลพื้นที่ครับ...');
  }

  // Statistics keywords
  if (lower.includes('สถิติ') || lower.includes('จำนวน') || lower.includes('กี่')) {
    statuses.push('น้องดีโอกำลังประมวลผลข้อมูลครับ...');
  }

  // Comparison keywords
  if (lower.includes('เปรียบเทียบ') || lower.includes('มากที่สุด') || lower.includes('น้อยที่สุด')) {
    statuses.push('น้องดีโอกำลังเปรียบเทียบข้อมูลครับ...');
  }

  // Student keywords
  if (lower.includes('นักเรียน') || lower.includes('เด็ก') || lower.includes('นักศึกษา')) {
    statuses.push('น้องดีโอกำลังค้นหาข้อมูลนักเรียนครับ...');
  }

  // Teacher keywords
  if (lower.includes('ครู') || lower.includes('บุคลากร') || lower.includes('อาจารย์')) {
    statuses.push('น้องดีโอกำลังค้นหาข้อมูลบุคลากรครับ...');
  }

  // Default
  if (statuses.length === 0) {
    statuses.push('น้องดีโอกำลังวิเคราะห์คำถามครับ...');
  }

  statuses.push('น้องดีโอกำลังเรียบเรียงคำตอบครับ...');

  return statuses;
};

// Memoize the component to prevent re-renders of history items
const MessageBubble = React.memo<MessageBubbleProps>(({
  message,
  isAdminMode = false,
  userAvatar,
  userInitials,
  onRegenerate,
  onEdit,
  isLastAssistantMessage = false,
  isLatestMessage = false,
  lastUserMessage = '',
  sessionId = '',
  category = 'general',
  onSuggestionClick
}) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');

  // Typewriter effect state
  // For history messages, initialize with full content immediately to prevent re-streaming
  const [displayedMainContent, setDisplayedMainContent] = useState(() => {
    if (message.isHistory || message.isError || message.role === 'user') {
      return message.content;
    }
    return '';
  });
  const [thinkingContent, setThinkingContent] = useState('');
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [imageError, setImageError] = useState(false);
  // Feedback state
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null);
  const [feedbackSaving, setFeedbackSaving] = useState(false);
  const [chartData, setChartData] = useState<any>(null);
  const [suggestionsData, setSuggestionsData] = useState<string[] | null>(null);
  const [showTable, setShowTable] = useState(false); // Toggle for table when chart is present
  const [tableMarkdownState, setTableMarkdownState] = useState(''); // Extracted table markdown

  // ✨ Thinking Status Animation
  const [thinkingStatusIndex, setThinkingStatusIndex] = useState(0);
  const thinkingStatuses = React.useMemo(() => generateThinkingStatus(lastUserMessage), [lastUserMessage]);

  // Cycle through thinking statuses while waiting for response
  React.useEffect(() => {
    if (isTyping && !displayedMainContent && !thinkingContent) {
      const interval = setInterval(() => {
        setThinkingStatusIndex(prev => (prev + 1) % thinkingStatuses.length);
      }, 2000); // Change status every 2 seconds
      return () => clearInterval(interval);
    }
  }, [isTyping, displayedMainContent, thinkingContent, thinkingStatuses.length]);
  const [mapData, setMapData] = useState<any>(null);

  // Ref to track latest content without triggering effects incorrectly
  const contentRef = React.useRef(message.content);
  contentRef.current = message.content;
  const isFirstMount = React.useRef(true);

  // Initialize content - No typewriter animation (streaming is handled by geminiService)
  React.useEffect(() => {
    // Pre-process content (Extract Chart)
    let contentToProcess = message.content || '';

    const cStart = contentToProcess.indexOf('<chart>');
    const cEnd = contentToProcess.indexOf('</chart>');
    if (cStart !== -1 && cEnd !== -1) {
      try {
        const jsonStr = contentToProcess.substring(cStart + 7, cEnd);
        setChartData(JSON.parse(jsonStr));
        contentToProcess = contentToProcess.substring(0, cStart).trim();
      } catch (e) { console.error(e); }
    } else {
      setChartData(null);
    }

    // Extract Map data
    const mStart = contentToProcess.indexOf('<map>');
    const mEnd = contentToProcess.indexOf('</map>');
    if (mStart !== -1 && mEnd !== -1) {
      try {
        const jsonStr = contentToProcess.substring(mStart + 5, mEnd);
        setMapData(JSON.parse(jsonStr));
        contentToProcess = contentToProcess.substring(0, mStart).trim() + contentToProcess.substring(mEnd + 6).trim();
      } catch (e) { console.error(e); }
    } else {
      setMapData(null);
    }

    // Extract Suggestions data
    const sStart = contentToProcess.indexOf('<suggestions>');
    const sEnd = contentToProcess.indexOf('</suggestions>');
    if (sStart !== -1 && sEnd !== -1) {
      try {
        const jsonStr = contentToProcess.substring(sStart + 13, sEnd);
        setSuggestionsData(JSON.parse(jsonStr));
        contentToProcess = contentToProcess.substring(0, sStart).trim() + contentToProcess.substring(sEnd + 14).trim();
      } catch (e) { console.error(e); }
    } else {
      setSuggestionsData(null);
    }

    // Parse <thinking> block
    let rawThink = '';
    let rawMain = '';
    const thinkStart = contentToProcess.indexOf('<thinking>');
    const thinkEnd = contentToProcess.indexOf('</thinking>');

    if (thinkStart !== -1) {
      if (thinkEnd !== -1) {
        rawThink = contentToProcess.substring(thinkStart + 10, thinkEnd).trim();
        rawMain = contentToProcess.substring(thinkEnd + 11).trim();
      } else {
        rawThink = contentToProcess.substring(thinkStart + 10).trim();
        rawMain = '';
      }
    } else {
      rawMain = contentToProcess;
    }

    // Pre-processing for lists
    rawMain = rawMain.trim();
    rawMain = rawMain.replace(/([^\n])\n(-|\*|\d+\.)\s/g, '$1\n\n$2 ');
    rawMain = rawMain.replace(/([^\n])\n(#{1,6})\s/g, '$1\n\n$2 ');

    // ✨ SMART DISPLAY: Extract table markdown separately when chart exists
    // Table will be rendered in a collapsible toggle section under the chart
    let tableMarkdown = '';
    if (cStart !== -1) { // If chart was found
      const lines = rawMain.split('\n');
      const tableLines: string[] = [];
      const nonTableLines: string[] = [];
      for (const line of lines) {
        const trim = line.trim();
        const isTableLine = trim.startsWith('|') ||
          (trim.includes('|') && trim.includes('---'));
        if (isTableLine) {
          tableLines.push(line);
        } else {
          nonTableLines.push(line);
        }
      }
      tableMarkdown = tableLines.join('\n');
      rawMain = nonTableLines.join('\n').replace(/\n{3,}/g, '\n\n');
    }

    setThinkingContent(rawThink);
    setDisplayedMainContent(rawMain);
    setTableMarkdownState(tableMarkdown);

    // Show typing indicator when content is empty but loading
    setIsTyping(!rawMain && !isUser && !message.isError && !message.isHistory);
  }, [message.content, isUser, message.isError, message.isHistory]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(displayedMainContent || message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  // Handle feedback button click
  const handleFeedback = async (type: 'positive' | 'negative') => {
    if (feedback || feedbackSaving) return; // Already submitted

    setFeedbackSaving(true);
    setFeedback(type);

    try {
      await saveFeedback({
        messageId: message.id,
        sessionId: sessionId,
        userQuestion: lastUserMessage,
        aiResponse: message.content,
        feedback: type,
        category: category
      });
      console.log(`[Feedback] ✅ ${type} feedback saved`);
    } catch (error) {
      console.error('[Feedback] ❌ Failed to save:', error);
    } finally {
      setFeedbackSaving(false);
    }
  };

  return (
    <div className={`flex w-full mb-4 md:mb-6 group ${isUser ? 'justify-end' : 'justify-start'} animate-message`}>
      <div className={`message-bubble ${isLatestMessage ? 'message-bubble-latest' : ''} flex gap-2.5 md:gap-3.5 ${(chartData || mapData) ? 'max-w-full w-full' : 'max-w-[90%] sm:max-w-lg md:max-w-2xl lg:max-w-3xl xl:max-w-4xl'} ${isUser ? 'flex-row-reverse' : 'flex-row'} min-w-0`}>
        {/* Avatar */}
        <div
          className={`flex-shrink-0 w-12 h-12 md:w-14 md:h-14 rounded-2xl flex items-center justify-center text-[13px] font-black shadow-md mt-0.5 transition-all duration-300 group-hover:scale-110 group-hover:rotate-3 overflow-hidden
            ${isUser ? 'bg-white border border-black/5 text-[#1D1D1F]' : 'bg-white'}`}
        >
          {isUser ? (
            userAvatar && !imageError ? (
              <img
                src={userAvatar}
                alt="User"
                className="w-full h-full object-cover"
                onError={() => setImageError(true)}
              />
            ) : (
              userInitials || 'U'
            )
          ) : (
            <img src="/do-mascot.png" alt="DO" className="w-full h-full object-contain p-1" />
          )}
        </div>

        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-full min-w-0 flex-1`}>
          <span className="text-[9px] md:text-[10px] font-bold uppercase tracking-[0.2em] opacity-30 mb-1 mx-1" style={{ color: MOE_COLORS.textMain }}>
            {isUser ? 'User' : 'DO AI'}
          </span>
          <div
            className={`
                relative transition-all duration-500 ease-out
                px-4 py-3 md:px-5 md:py-4 rounded-[20px] md:rounded-[22px] shadow-sm
                ${isUser
                ? 'rounded-tr-[4px] user-bubble-glass text-white selection:bg-white/20 shadow-[0_14px_30px_rgba(88,60,200,0.35)]'
                : message.isError
                  ? 'rounded-tl-[4px] bg-red-50/90 backdrop-blur-xl border border-red-200/50 text-red-900 shadow-sm'
                  : 'rounded-tl-[4px] bg-white/70 backdrop-blur-2xl border border-white/80 text-[#1D1D1F] shadow-[0_10px_30px_rgba(0,0,0,0.04)]'}
                ${copied ? 'ring-2 ring-blue-500/20 scale-[0.99] shadow-none' : ''}
              `}
          >
            {message.isError && (
              <div className="flex items-center gap-2 mb-3 text-red-600 font-bold text-[11px] uppercase tracking-wider">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                  <path fillRule="evenodd" d="M9.401 3.003c.115-.283.392-.47.699-.47h3.8c.307 0 .584.187.699.47l.54 1.326a5.153 5.153 0 002.312 2.312l1.326.54c.283.115.47.392.47.699v3.8c0 .307-.187.584-.47.699l-1.326.54a5.153 5.153 0 00-2.312 2.312l-.54 1.326a.75.75 0 01-.699.47h-3.8a.75.75 0 01-.699-.47l-.54-1.326a5.153 5.153 0 00-2.312-2.312l-1.326-.54a.75.75 0 01-.47-.699v-3.8c0-.307.187-.584.47-.699l1.326-.54a5.153 5.153 0 002.312-2.312l.54-1.326zM12 9a.75.75 0 01.75.75v2.5a.75.75 0 01-1.5 0v-2.5A.75.75 0 0112 9zm0 6a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
                </svg>
                พบข้อผิดพลาด
              </div>
            )}

            {/* Thinking Process Section - Collapsible */}
            {!isUser && thinkingContent && (
              <div className="mb-4 rounded-xl bg-black/5 border border-black/5 overflow-hidden transition-all duration-300">
                <button
                  onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
                  className="w-full px-4 py-2.5 flex items-center justify-between text-[11px] font-bold text-black/40 hover:text-black/60 hover:bg-black/5 uppercase tracking-wider transition-colors"
                >
                  <div className={`w-2 h-2 rounded-full bg-gradient-to-br from-orange-400 to-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)] ${!displayedMainContent ? 'animate-pulse' : ''}`}></div>
                  {displayedMainContent ? 'Thinking Process' : 'กำลังประมวลผลความคิด...'}
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className={`w-3.5 h-3.5 transition-transform duration-300 ${isThinkingExpanded ? 'rotate-180' : ''}`}
                  >
                    <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                  </svg>
                </button>

                {isThinkingExpanded && (
                  <div className="px-4 py-3 text-[13px] font-mono text-black/60 leading-relaxed border-t border-black/5 animate-fade-in bg-white/40">
                    {thinkingContent}
                    {!displayedMainContent && (
                      <span className="inline-block w-1.5 h-3 ml-1 align-middle bg-blue-400/50 animate-pulse"></span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Action Buttons: Edit (User) + Regenerate + Copy */}
            <div className={`absolute ${isUser ? '-left-12' : '-right-12'} top-1 opacity-0 group-hover:opacity-100 transition-all duration-300 transform group-hover:translate-y-1 flex flex-col gap-2`}>
              {/* Edit Button - Only for user messages */}
              {isUser && onEdit && !isEditing && (
                <button
                  onClick={() => {
                    setEditContent(message.content);
                    setIsEditing(true);
                  }}
                  className="w-9 h-9 rounded-full glass-pill flex items-center justify-center hover:scale-110 active:scale-90 transition-all shadow-sm hover:bg-blue-50"
                  title="แก้ไข"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4 text-blue-500">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
                  </svg>
                </button>
              )}
              {/* Regenerate Button - Only for last assistant message */}
              {!isUser && isLastAssistantMessage && onRegenerate && !isTyping && (
                <button
                  onClick={onRegenerate}
                  className="w-9 h-9 rounded-full glass-pill flex items-center justify-center hover:scale-110 active:scale-90 transition-all shadow-sm hover:bg-blue-50"
                  title="ตอบใหม่"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4 text-blue-500">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                  </svg>
                </button>
              )}
              {/* Copy Button */}
              <button
                onClick={handleCopy}
                className="w-9 h-9 rounded-full glass-pill flex items-center justify-center hover:scale-110 active:scale-90 transition-all shadow-sm"
                title="คัดลอก"
              >
                {copied ? (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-green-500">
                    <path fillRule="evenodd" d="M19.916 4.626a.75.75 0 0 1 .208 1.04l-9 13.5a.75.75 0 0 1-1.154.114l-6-6a.75.75 0 0 1 1.06-1.06l5.353 5.353 8.493-12.74a.75.75 0 0 1 1.04-.207z" clipRule="evenodd" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4 text-black/30">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" />
                  </svg>
                )}
              </button>
            </div>


            {/* Message Content - Side-by-Side when Chart exists (including during typing) */}
            {chartData && !isUser ? (
              /* Side-by-Side Layout: Text Left, Chart Right */
              <div className="flex flex-col lg:flex-row gap-4 lg:gap-6">
                {/* Left Column - Text Content */}
                <div className="flex-1 min-w-0 select-text cursor-text gemini-markdown">
                  {/* ✨ Thinking Status Indicator - ChatGPT Style */}
                  {!displayedMainContent && !thinkingContent && (
                    <div className="flex flex-col gap-2 py-2 animate-pulse">
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1">
                          <div className="w-1.5 h-1.5 bg-blue-500/60 rounded-full animate-bounce" style={{ animationDelay: '0ms', animationDuration: '1s' }}></div>
                          <div className="w-1.5 h-1.5 bg-blue-500/60 rounded-full animate-bounce" style={{ animationDelay: '150ms', animationDuration: '1s' }}></div>
                          <div className="w-1.5 h-1.5 bg-blue-500/60 rounded-full animate-bounce" style={{ animationDelay: '300ms', animationDuration: '1s' }}></div>
                        </div>
                        <span className="text-[13px] text-black/50 font-medium transition-opacity duration-500">
                          {thinkingStatuses[thinkingStatusIndex]}
                        </span>
                      </div>
                    </div>
                  )}
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    components={{
                      p: ({ children }) => (
                        <p className="text-[16px] leading-[1.8] mb-4 last:mb-0 font-normal tracking-wide text-[#1d1d1f] antialiased opacity-90">{children}</p>
                      ),
                      strong: ({ children }) => (
                        <strong className="font-bold text-gradient-warm">
                          {children}
                        </strong>
                      ),
                      em: ({ children }) => (
                        <em className="italic text-indigo-600/80">{children}</em>
                      ),
                      h1: ({ children }) => (
                        <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0 text-gray-900">{children}</h1>
                      ),
                      h2: ({ children }) => (
                        <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0 text-gray-800">{children}</h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className="text-base font-bold mb-2 mt-2 first:mt-0 text-gray-700">{children}</h3>
                      ),
                      ul: ({ children }) => (
                        <ul className="space-y-1.5 my-3 pl-1">{children}</ul>
                      ),
                      ol: ({ children }) => (
                        <ol className="space-y-1.5 my-3 pl-1 list-decimal list-inside">{children}</ol>
                      ),
                      li: ({ children }) => (
                        <li className="flex gap-2 text-[14px] leading-relaxed">
                          <span className="text-blue-400 mt-0.5 text-xs">•</span>
                          <span>{children}</span>
                        </li>
                      ),
                    }}
                  >
                    {cleanupMarkdown(displayedMainContent || '')}
                  </ReactMarkdown>
                  {/* Cursor Effect while typing (inside side-by-side) */}
                  {isTyping && (
                    <span className="inline-block w-1.5 h-4 ml-0.5 align-middle bg-indigo-500 animate-pulse rounded-full"></span>
                  )}
                </div>

                {/* Right Column - Chart (Sticky) with Apple Card Style */}
                <div className="lg:w-[400px] lg:flex-shrink-0 lg:sticky lg:top-4 self-start animate-fade-in-up">
                  <div className="bg-white/80 backdrop-blur-xl rounded-[24px] p-1.5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] border border-white/60">
                    <ChartWidget type={chartData.type} data={chartData.data} title={chartData.title} />
                  </div>
                  {/* 📋 Collapsible Table Toggle */}
                  {tableMarkdownState && (
                    <div className="mt-3">
                      <button
                        onClick={() => setShowTable(!showTable)}
                        className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-[13px] font-medium transition-all duration-200 bg-white/60 hover:bg-white/90 text-gray-500 hover:text-gray-700 border border-gray-200/60 hover:border-gray-300/80 backdrop-blur-sm"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5M12 14.625v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 14.625c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 0v1.5c0 .621-.504 1.125-1.125 1.125" />
                        </svg>
                        {showTable ? 'ซ่อนตารางข้อมูล' : 'ดูตารางข้อมูล'}
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className={`w-3.5 h-3.5 transition-transform duration-200 ${showTable ? 'rotate-180' : ''}`}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                        </svg>
                      </button>
                      {showTable && (
                        <div className="mt-2 animate-fade-in-up">
                          <div className="overflow-x-auto rounded-xl border border-gray-200/60 shadow-sm bg-white/80 backdrop-blur-sm">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                table: ({ children }) => (
                                  <table className="w-full text-[13px]">{children}</table>
                                ),
                                thead: ({ children }) => (
                                  <thead className="bg-gray-50/80">{children}</thead>
                                ),
                                th: ({ children }) => (
                                  <th className="px-3 py-2 text-left font-semibold text-gray-700 border-b-2 border-gray-200 text-[12px] uppercase tracking-wide">{children}</th>
                                ),
                                td: ({ children }) => (
                                  <td className="px-3 py-2 border-b border-gray-100 text-gray-700">{children}</td>
                                ),
                                tr: ({ children }) => (
                                  <tr className="hover:bg-blue-50/30 transition-colors">{children}</tr>
                                ),
                              }}
                            >
                              {tableMarkdownState}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* Normal Vertical Layout */
              <div className="select-text cursor-text gemini-markdown">
                {isUser ? (
                  isEditing ? (
                    /* Edit Mode UI */
                    <div className="flex flex-col gap-3">
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="w-full min-h-[80px] p-3 rounded-xl bg-white/90 border border-blue-200 text-[15px] text-[#1D1D1F] leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-blue-400/50"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            if (editContent.trim() && onEdit) {
                              onEdit(message.id, editContent.trim());
                              setIsEditing(false);
                            }
                          } else if (e.key === 'Escape') {
                            setIsEditing(false);
                          }
                        }}
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => setIsEditing(false)}
                          className="px-4 py-2 rounded-xl text-[13px] font-semibold text-black/50 hover:bg-black/5 transition-all"
                        >
                          ยกเลิก
                        </button>
                        <button
                          onClick={() => {
                            if (editContent.trim() && onEdit) {
                              onEdit(message.id, editContent.trim());
                              setIsEditing(false);
                            }
                          }}
                          className="px-4 py-2 rounded-xl text-[13px] font-semibold bg-[#007AFF] text-white hover:bg-[#0056b3] transition-all shadow-sm"
                        >
                          บันทึกและส่งใหม่
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-[15px] leading-[1.7]">{displayedMainContent}</div>
                  )
                ) : (
                  <>
                    {/* ✨ Thinking Status Indicator - ChatGPT Style */}
                    {!displayedMainContent && !thinkingContent && (
                      <div className="flex flex-col gap-2 py-2">
                        <div className="flex items-center gap-2">
                          <div className="flex items-center gap-1">
                            <div className="w-1.5 h-1.5 bg-blue-500/60 rounded-full animate-bounce" style={{ animationDelay: '0ms', animationDuration: '1s' }}></div>
                            <div className="w-1.5 h-1.5 bg-blue-500/60 rounded-full animate-bounce" style={{ animationDelay: '150ms', animationDuration: '1s' }}></div>
                            <div className="w-1.5 h-1.5 bg-blue-500/60 rounded-full animate-bounce" style={{ animationDelay: '300ms', animationDuration: '1s' }}></div>
                          </div>
                          <span className="text-[13px] text-black/50 font-medium transition-all duration-500 ease-out">
                            {thinkingStatuses[thinkingStatusIndex]}
                          </span>
                        </div>
                      </div>
                    )}
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkBreaks]}
                      components={{
                        // Paragraphs - Good spacing, readable line-height
                        p: ({ children }) => (
                          <p className="text-[16px] leading-[1.8] mb-4 last:mb-0 font-normal tracking-wide text-[#1d1d1f] antialiased opacity-90">{children}</p>
                        ),
                        // Bold text - Indigo accent like Gemini
                        strong: ({ children }) => (
                          <strong className="font-bold text-gradient-warm">
                            {children}
                          </strong>
                        ),
                        // Emphasis
                        em: ({ children }) => (
                          <em className="italic text-indigo-600/80">{children}</em>
                        ),
                        // Headings - Clean hierarchy
                        h1: ({ children }) => (
                          <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0 text-gray-900">{children}</h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0 text-gray-800">{children}</h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-base font-bold mb-2 mt-2 first:mt-0 text-gray-700">{children}</h3>
                        ),
                        h4: ({ children }) => (
                          <h4 className="text-sm font-bold mb-1 text-gray-600">{children}</h4>
                        ),
                        // Unordered Lists - Clean bullet style
                        ul: ({ children }) => (
                          <ul className="space-y-1.5 my-3 pl-1">{children}</ul>
                        ),
                        // Ordered Lists
                        ol: ({ children }) => (
                          <ol className="space-y-1.5 my-3 pl-1 list-decimal list-inside">{children}</ol>
                        ),
                        // List Items - Modern arrow bullet
                        li: ({ children }) => (
                          <li className="flex gap-2 text-[14px] leading-relaxed">
                            <span className="text-blue-400 mt-0.5 text-xs">•</span>
                            <span>{children}</span>
                          </li>
                        ),
                        // Code inline
                        code: ({ inline, children, className }: any) => (
                          inline
                            ? <code className="px-1.5 py-0.5 mx-0.5 rounded-md bg-black/[0.04] text-[13px] font-mono text-indigo-700">{children}</code>
                            : (
                              <div className="relative my-3 overflow-hidden rounded-xl bg-[#1e1e1e] shadow-lg">
                                <div className="flex items-center gap-1.5 px-4 py-2 bg-black/30 text-[10px] font-mono text-white/50">
                                  <span className="w-2.5 h-2.5 rounded-full bg-red-400/60"></span>
                                  <span className="w-2.5 h-2.5 rounded-full bg-yellow-400/60"></span>
                                  <span className="w-2.5 h-2.5 rounded-full bg-green-400/60"></span>
                                </div>
                                <pre className="px-4 py-3 overflow-x-auto"><code className={`text-[13px] ${className}`}>{children}</code></pre>
                              </div>
                            )
                        ),
                        // Pre blocks
                        pre: ({ children }) => (
                          <>{children}</>
                        ),
                        // Blockquotes - Gemini style
                        blockquote: ({ children }) => (
                          <blockquote className="my-4 pl-4 py-1 border-l-3 border-indigo-400/60 text-[14px] text-gray-600 italic bg-indigo-50/30 rounded-r-lg">
                            {children}
                          </blockquote>
                        ),
                        // Links
                        a: ({ href, children }) => (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-700 underline decoration-1 underline-offset-2 hover:decoration-2 transition-all inline-flex items-center gap-1"
                          >
                            {children}
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3 opacity-50">
                              <path fillRule="evenodd" d="M4.22 11.78a.75.75 0 0 1 0-1.06L9.44 5.5H5.75a.75.75 0 0 1 0-1.5h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V6.56l-5.22 5.22a.75.75 0 0 1-1.06 0Z" clipRule="evenodd" />
                            </svg>
                          </a>
                        ),
                        // Horizontal rule
                        hr: () => (
                          <hr className="my-5 border-t border-gray-200/50" />
                        ),
                        // Tables - Show normally when NO chart, hidden when chart exists (table is in toggle)
                        table: ({ children }) => (
                          <div className="my-4 overflow-x-auto rounded-xl border border-gray-200/60 shadow-sm w-full clear-both block">
                            <table className="w-full text-[14px]">{children}</table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-gray-50/60">{children}</thead>
                        ),
                        th: ({ children }) => (
                          <th className="px-4 py-2 text-left font-semibold text-gray-700 border-b-2 border-gray-200">{children}</th>
                        ),
                        td: ({ children }) => (
                          <td className="px-4 py-2 border-b border-gray-100 text-gray-700">{children}</td>
                        ),
                      }}
                    >
                      {cleanupMarkdown(displayedMainContent || '')}
                    </ReactMarkdown>
                  </>
                )}
                {/* Cursor Effect while typing */}
                {!isUser && isTyping && (
                  <span className="inline-block w-1.5 h-4 ml-0.5 align-middle bg-indigo-500 animate-pulse rounded-full"></span>
                )}
              </div>
            )}

            {/* Chart Widget removed from vertical layout — now always in side-by-side above */}


            {/* Map Widget */}
            {!isUser && mapData && !isTyping && (
              <div className="animate-fade-in-up">
                <MapWidget
                  latitude={mapData.latitude}
                  longitude={mapData.longitude}
                  schoolName={mapData.schoolName}
                  address={mapData.address}
                  markers={mapData.markers}
                />
              </div>
            )}

            {/* ✨ Suggestion Chips — Apple-Style Clickable Pills */}
            {!isUser && suggestionsData && suggestionsData.length > 0 && !isTyping && (
              <div className="mt-4 pt-3 border-t border-black/5 animate-fade-in-up">
                <div className="flex flex-wrap gap-2">
                  {suggestionsData.map((suggestion, idx) => (
                    <button
                      key={idx}
                      onClick={() => onSuggestionClick?.(suggestion)}
                      className="group/chip relative px-4 py-2.5 rounded-2xl text-[13px] font-medium
                        bg-white/60 backdrop-blur-xl border border-white/80 shadow-sm
                        text-[#1D1D1F]/70 hover:text-[#007AFF]
                        hover:bg-[#007AFF]/[0.06] hover:border-[#007AFF]/25
                        hover:shadow-[0_4px_16px_rgba(0,122,255,0.12)]
                        active:scale-[0.96] active:shadow-none
                        transition-all duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]
                        cursor-pointer select-none"
                      style={{ animationDelay: `${idx * 80}ms` }}
                    >
                      <span className="flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"
                          className="w-3.5 h-3.5 opacity-40 group-hover/chip:opacity-70 transition-opacity duration-300">
                          <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM6.75 9.25a.75.75 0 0 0 0 1.5h4.59l-2.1 1.95a.75.75 0 1 0 1.02 1.1l3.5-3.25a.75.75 0 0 0 0-1.1l-3.5-3.25a.75.75 0 1 0-1.02 1.1l2.1 1.95H6.75Z" clipRule="evenodd" />
                        </svg>
                        {suggestion}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Verification Badge */}
            {!isUser && message.content && !isTyping && (
              <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-black/5 animate-fade-in-up">
                {/* Left: Verification Badge */}
                <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/50 border border-white/80 shadow-sm">
                  <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></div>
                  <span className="text-[9px] font-black uppercase tracking-[0.2em] text-amber-600/80">Data Intelligence Verified</span>
                </div>

                {/* Right: Feedback Buttons */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleFeedback('positive')}
                    disabled={!!feedback || feedbackSaving}
                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 ${feedback === 'positive'
                      ? 'bg-green-100 text-green-600 scale-110'
                      : feedback
                        ? 'opacity-30 cursor-not-allowed'
                        : 'bg-white/60 hover:bg-green-50 hover:scale-110 text-gray-400 hover:text-green-500'
                      } ${feedbackSaving ? 'animate-pulse' : ''}`}
                    title="คำตอบนี้มีประโยชน์"
                  >
                    {feedback === 'positive' ? '👍' : (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6.633 10.25c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 0 1 2.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 0 0 .322-1.672V2.75a.75.75 0 0 1 .75-.75 2.25 2.25 0 0 1 2.25 2.25c0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282m0 0h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 0 1-2.649 7.521c-.388.482-.987.729-1.605.729H13.48c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 0 0-1.423-.23H5.904m10.598-9.75H14.25M5.904 18.5c.083.205.173.405.27.602.197.4-.078.898-.523.898h-.908c-.889 0-1.713-.518-1.972-1.368a12 12 0 0 1-.521-3.507c0-1.553.295-3.036.831-4.398C3.387 9.953 4.167 9.5 5 9.5h1.053c.472 0 .745.556.5.96a8.958 8.958 0 0 0-1.302 4.665c0 1.194.232 2.333.654 3.375Z" />
                      </svg>
                    )}
                  </button>
                  <button
                    onClick={() => handleFeedback('negative')}
                    disabled={!!feedback || feedbackSaving}
                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 ${feedback === 'negative'
                      ? 'bg-red-100 text-red-600 scale-110'
                      : feedback
                        ? 'opacity-30 cursor-not-allowed'
                        : 'bg-white/60 hover:bg-red-50 hover:scale-110 text-gray-400 hover:text-red-500'
                      } ${feedbackSaving ? 'animate-pulse' : ''}`}
                    title="คำตอบนี้ไม่ถูกต้อง"
                  >
                    {feedback === 'negative' ? '👎' : (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M7.498 15.25H4.372c-1.026 0-1.945-.694-2.054-1.715a12.137 12.137 0 0 1-.068-1.285c0-2.848.992-5.464 2.649-7.521C5.287 4.247 5.886 4 6.504 4h4.016a4.5 4.5 0 0 1 1.423.23l3.114 1.04a4.5 4.5 0 0 0 1.423.23h1.294M7.498 15.25c.618 0 .991.724.725 1.282A7.471 7.471 0 0 0 7.5 19.75 2.25 2.25 0 0 0 9.75 22a.75.75 0 0 0 .75-.75v-.633c0-.573.11-1.14.322-1.672.304-.76.93-1.33 1.653-1.715a9.04 9.04 0 0 0 2.86-2.4c.498-.634 1.226-1.08 2.032-1.08h.384m-10.253 1.5H9.7m8.075-9.75c.01.05.027.1.05.148.593 1.2.925 2.55.925 3.977 0 1.487-.36 2.89-.999 4.125m.023-8.25c-.076-.365.183-.75.575-.75h.908c.889 0 1.713.518 1.972 1.368.339 1.11.521 2.287.521 3.507 0 1.553-.295 3.036-.831 4.398-.306.774-1.086 1.227-1.918 1.227h-1.053c-.472 0-.745-.556-.5-.96a8.95 8.95 0 0 0 .303-.54" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* RAG Debug Panel (Admin Only) */}
            {isAdminMode && !isUser && message.ragDebugInfo && (
              <div className="mt-3 pt-3 border-t border-dashed border-amber-300">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-600">🔍 RAG Debug</span>
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold ${message.ragDebugInfo.source === 'pinecone'
                    ? 'bg-teal-100 text-teal-700'
                    : message.ragDebugInfo.source === 'legacy_rag'
                      ? 'bg-purple-100 text-purple-700'
                      : 'bg-gray-100 text-gray-500'
                    }`}>
                    {message.ragDebugInfo.source === 'pinecone' ? '🌿 Pinecone'
                      : message.ragDebugInfo.source === 'legacy_rag' ? '📡 Legacy RAG'
                        : '🤖 AI Only'}
                  </span>
                </div>
                <div className="text-[10px] text-amber-800/70 space-y-1">
                  {message.ragDebugInfo.matchCount !== undefined && (
                    <div>📊 <strong>Matches:</strong> {message.ragDebugInfo.matchCount} documents</div>
                  )}
                  {message.ragDebugInfo.retrievalTimeMs !== undefined && (
                    <div>⚡ <strong>Time:</strong> {message.ragDebugInfo.retrievalTimeMs}ms</div>
                  )}
                  {message.ragDebugInfo.embeddingModel && (
                    <div>🧠 <strong>Embedding:</strong> {message.ragDebugInfo.embeddingModel}</div>
                  )}
                  {message.ragDebugInfo.contextPreview && (
                    <details className="mt-2">
                      <summary className="cursor-pointer font-bold text-amber-700 hover:text-amber-500">📄 Context Preview</summary>
                      <div className="mt-1 p-2 bg-amber-50/50 rounded text-[9px] text-amber-900/60 max-h-24 overflow-y-auto">
                        {message.ragDebugInfo.contextPreview}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  return prevProps.message.id === nextProps.message.id &&
    prevProps.message.content === nextProps.message.content &&
    prevProps.message.isError === nextProps.message.isError &&
    prevProps.message.isHistory === nextProps.message.isHistory &&
    prevProps.isAdminMode === nextProps.isAdminMode;
});

export default MessageBubble;
