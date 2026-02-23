

/**
 * 📄 ชื่อไฟล์: App.tsx
 * 📝 คำอธิบาย:
 *    หัวใจหลักของ Frontend Application (Main Component)
 *    ทำหน้าที่ควบคุมการทำงานทั้งหมดของหน้าเว็บ
 *
 * 🛠 หน้าที่หลัก:
 *    1. State Management: จัดการสถานะผู้ใช้ (User), ข้อความแชท (Messages), และหมวดหมู่ (Category)
 *    2. Routing: สลับหน้าจอระหว่าง Landing Page, Login, และ Chat UI
 *    3. API Integration: เชื่อมต่อกับ Backend ผ่าน Services ต่างๆ
 *    4. UI Layout: จัดวางโครงสร้างหลักของหน้าเว็บ
 */

import React, { useState, useEffect, useRef, lazy, Suspense } from 'react';
import CategorySelector from './components/chat/CategorySelector';
import ChatInput from './components/chat/ChatInput';
import { getAdminToken, clearAdminSession } from './services/adminAuth';
import MobileMenu from './components/layout/MobileMenu';
import { Category, Message, User } from './types';
import { chatService, ChatSession } from './services/chatService';
import { MOE_COLORS, COMMON_QUERIES } from './constants';
import { AdminConfigProvider, useAdminConfig } from './contexts/AdminConfigContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';

const generateId = () => Math.random().toString(36).substr(2, 9);

type View = 'home' | 'login' | 'chat';

type GeminiServiceModule = typeof import('./services/geminiService');

const MessageBubble = lazy(() => import('./components/chat/MessageBubble'));
const LandingPage = lazy(() => import('./components/pages/LandingPage'));
const LoginPage = lazy(() => import('./components/pages/LoginPage'));
const AdminPanel = lazy(() => import('./components/admin/AdminPanel'));
const AdminLogin = lazy(() => import('./components/admin/AdminLogin'));

let geminiServicePromise: Promise<GeminiServiceModule> | null = null;
const loadGeminiService = async (): Promise<GeminiServiceModule> => {
  if (!geminiServicePromise) {
    geminiServicePromise = import('./services/geminiService');
  }
  return geminiServicePromise;
};



const AppContent: React.FC = () => {
  // Initialize view from storage or default to 'home'
  const [view, setView] = useState<View>(() => {
    const saved = localStorage.getItem('current_view');
    return (saved === 'home' || saved === 'login' || saved === 'chat') ? saved : 'home';
  });
  const [displayView, setDisplayView] = useState<View>(view); // Init displayView with persisted view as well
  const [isExiting, setIsExiting] = useState(false);

  // Persist view changes
  useEffect(() => {
    localStorage.setItem('current_view', view);
  }, [view]);

  const [user, setUser] = useState<User | null>(null);

  // Initialize Chat State from Storage
  const [category, setCategory] = useState<Category>(() => {
    return (localStorage.getItem('current_category') as Category) || Category.General;
  });

  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = localStorage.getItem('current_messages');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Mark existing messages as history to skip typing animation
        return parsed.map((m: any) => ({ ...m, isHistory: true }));
      } catch (e) {
        return [];
      }
    }
    return [];
  });

  const [currentChatId, setCurrentChatId] = useState<string>(() => {
    return localStorage.getItem('current_chat_id') || generateId();
  });

  const [isLoading, setIsLoading] = useState(false);
  const [showHeaderMenu, setShowHeaderMenu] = useState(false);
  const [showWorkspaceInfo, setShowWorkspaceInfo] = useState(false);
  const [pastChats, setPastChats] = useState<ChatSession[]>([]);
  const [sidebarImgError, setSidebarImgError] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false); // ✨ Mobile Menu State
  const [isTalkMode, setIsTalkMode] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('talk_mode') === 'true';
  });
  // Ref to avoid stale closure — async callbacks always read latest value
  const isTalkModeRef = useRef(isTalkMode);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [autoListenSignal, setAutoListenSignal] = useState(0);
  const [stopListeningSignal, setStopListeningSignal] = useState(0);
  const [speechUnlocked, setSpeechUnlocked] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [voicesReady, setVoicesReady] = useState(false);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceUri, setSelectedVoiceUri] = useState<string>(() => {
    if (typeof window === 'undefined') return '';
    return localStorage.getItem('speech_voice_uri') || '';
  });
  const [speechMuted, setSpeechMuted] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('speech_muted') === 'true';
  });
  const [micLevel, setMicLevel] = useState(0);
  const speechUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const speakTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);

  // Persist Chat State
  useEffect(() => {
    localStorage.setItem('current_category', category);
    localStorage.setItem('current_messages', JSON.stringify(messages));
    localStorage.setItem('current_chat_id', currentChatId);
  }, [category, messages, currentChatId]);

  // Keep isTalkModeRef in sync with state
  useEffect(() => {
    isTalkModeRef.current = isTalkMode;
  }, [isTalkMode]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('talk_mode', String(isTalkMode));
    }
  }, [isTalkMode]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.body.classList.toggle('talk-mode-active', isTalkMode);
    return () => document.body.classList.remove('talk-mode-active');
  }, [isTalkMode]);

  useEffect(() => {
    if (isTalkMode) {
      // Auto-unlock speech when entering Talk Mode (uses the tap gesture)
      unlockSpeech();
      primeSpeech();
      setAutoListenSignal(s => s + 1);
    } else {
      setStopListeningSignal(s => s + 1);
      setIsListening(false);
      // Ensure any active audio is stopped when leaving Talk Mode
      if (ttsAudioRef.current) {
        ttsAudioRef.current.pause();
        ttsAudioRef.current.currentTime = 0;
        ttsAudioRef.current = null;
      }
      try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
      // NOTE: Do NOT reset speechUnlocked here — keep it unlocked for the session
    }
  }, [isTalkMode]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('speech_muted', String(speechMuted));
    }
  }, [speechMuted]);

  useEffect(() => {
    if (typeof window !== 'undefined' && selectedVoiceUri) {
      localStorage.setItem('speech_voice_uri', selectedVoiceUri);
    }
  }, [selectedVoiceUri]);

  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    const synth = window.speechSynthesis;
    const updateVoices = () => {
      const voices = synth.getVoices();
      if (voices.length > 0) {
        setVoicesReady(true);
        setAvailableVoices(voices);
        if (selectedVoiceUri && voices.some(v => v.voiceURI === selectedVoiceUri)) {
          return;
        }
        const thai = voices.find(v => v.lang?.toLowerCase().startsWith('th'));
        setSelectedVoiceUri(thai?.voiceURI || voices[0].voiceURI || '');
      }
    };
    updateVoices();
    synth.onvoiceschanged = updateVoices;
    return () => {
      synth.onvoiceschanged = null;
    };
  }, [selectedVoiceUri]);
  const [showAdminLogin, setShowAdminLogin] = useState(false);
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);
  const [uiToast, setUiToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Admin Config Context
  const { config, getSystemInstruction, updateConfig } = useAdminConfig();
  // Auth Context
  const { user: firebaseUser, userRole, logout: firebaseLogout, loading: authLoading } = useAuth(); // rename to avoid conflict

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info', duration = 2200) => {
    setUiToast({ message, type });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setUiToast(null), duration);
  };

  const resetChatSessionSafe = () => {
    void loadGeminiService()
      .then((gemini) => gemini.resetChatSession())
      .catch((error) => console.error('[Gemini] resetChatSession failed:', error));
  };

  const abortCurrentStreamSafe = () => {
    void loadGeminiService()
      .then((gemini) => gemini.abortCurrentStream())
      .catch((error) => console.error('[Gemini] abortCurrentStream failed:', error));
  };

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  // Sync Firebase User with App State
  useEffect(() => {
    if (!authLoading) {
      if (firebaseUser) {
        // Mapped role labels in Thai
        const roleLabels: Record<string, string> = {
          'admin': 'ผู้ดูแลระบบ',
          'เจ้าหน้าที่': 'เจ้าหน้าที่',
          'user': 'ผู้ใช้งานทั่วไป'
        };

        const mappedUser: User = {
          name: firebaseUser.displayName || firebaseUser.email?.split('@')[0] || 'User',
          email: firebaseUser.email || '',
          role: roleLabels[userRole] || userRole || 'ผู้ใช้งาน',
          avatar: firebaseUser.photoURL || undefined,
          initials: (firebaseUser.displayName || firebaseUser.email || 'U').substring(0, 1).toUpperCase()
        };
        setUser(mappedUser);

        const loadHistory = async () => {
          const sessions = await chatService.getUserSessions(firebaseUser.uid);
          setPastChats(sessions);

          // AUTO-LOAD: If current messages are empty, try to load the most recent session
          const savedMessages = localStorage.getItem('current_messages');
          // FIX: User requested to always default to General/New Chat instead of loading old session
          // if ((!savedMessages || JSON.parse(savedMessages).length === 0) && sessions.length > 0) {
          //   console.log("♻️ Auto-loading most recent cloud session:", sessions[0].sessionId);
          //   loadPastChat(sessions[0]);
          // }
        };
        loadHistory();

        // Redirect logic for authenticated users
        if (view === 'login') {
          navigateTo('chat');
        }
        // NOTE: We REMOVED the auto-redirect from 'home' to 'chat' here 
        // to allow users to stay on the landing page if they refresh there.
      } else {
        setPastChats([]);
        setMessages([]); // Clear active messages

        // Clear storage to prevent leak on refresh
        localStorage.removeItem('current_chat_id');
        localStorage.removeItem('current_messages');
        localStorage.removeItem('current_category');

        // Redirect logic for unauthenticated users
        if (view === 'chat') {
          navigateTo('home');
        }
      }
    }
  }, [firebaseUser, userRole, authLoading, view]);

  // Parallel View Transition Logic
  const [activeView, setActiveView] = useState<View>(view);
  const [previousView, setPreviousView] = useState<View | null>(null);

  const navigateTo = (nextView: View) => {
    if (nextView === activeView) return;

    setPreviousView(activeView);
    setActiveView(nextView);
    setView(nextView); // Keep persistence in sync

    // Clear previous view after animation completes
    setTimeout(() => {
      setPreviousView(null);
    }, 800); // Matches smooth fade duration
  };

  // Sync Admin Config with Gemini Service
  useEffect(() => {
    let cancelled = false;
    void loadGeminiService()
      .then((gemini) => {
        if (!cancelled) {
          gemini.updateGeminiConfig(config);
        }
      })
      .catch((error) => console.error('[Gemini] updateGeminiConfig failed:', error));
    return () => {
      cancelled = true;
    };
  }, [config]);

  // Ref to track if pending message has been sent - use a dedicated ref that persists
  const pendingMessageSentRef = useRef(false);
  const pendingMessageProcessedSessionRef = useRef<string | null>(null);

  useEffect(() => {
    if (view === 'chat' && user) {
      const systemInstruction = getSystemInstruction(category);
      // Construct history for startChat if we have messages (e.g. page reload)
      const initialHistory = messages.length > 1
        ? messages.filter(m => !m.isError && m.content).map(m => ({ role: m.role, parts: [{ text: m.content }] }))
        : [];

      void loadGeminiService()
        .then((gemini) => gemini.startChat(systemInstruction, category, initialHistory))
        .catch((error) => console.error('[Gemini] startChat failed:', error));

      // Check for pending message from landing page FIRST (priority over history)
      // Use sessionStorage key check to prevent duplicate sends across re-renders
      const pendingMsg = sessionStorage.getItem('pending_msg');
      if (pendingMsg && pendingMessageProcessedSessionRef.current !== pendingMsg) {
        // Mark as processed IMMEDIATELY before any async operations
        pendingMessageProcessedSessionRef.current = pendingMsg;
        sessionStorage.removeItem('pending_msg');

        // Clear messages and send pending - ensure clean slate
        setMessages([]);

        // Use a slightly longer delay to ensure DOM is ready
        setTimeout(() => {
          handleSendMessage(pendingMsg, null);
        }, 400);
      }
    }
  }, [view, user, category, config]);

  // Handle Auto-scroll to bottom with high precision and smoothness
  const isInitialMount = useRef(true);
  const lastMessagesLength = useRef(messages.length);
  const lastContentLength = useRef(0);
  const prevActiveView = useRef(activeView);

  // Helper function to scroll to absolute bottom
  const scrollToBottom = (instant = false) => {
    if (chatContainerRef.current) {
      const container = chatContainerRef.current;
      if (instant) {
        container.scrollTop = container.scrollHeight;
      } else {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth'
        });
      }
    }
  };

  // IMPORTANT: Scroll to bottom immediately when entering chat view
  useEffect(() => {
    if (activeView === 'chat' && prevActiveView.current !== 'chat') {
      // Just entered chat view - force scroll after a brief delay for DOM to settle
      const scrollTimeout = setTimeout(() => {
        scrollToBottom(true);
      }, 150);
      return () => clearTimeout(scrollTimeout);
    }
    prevActiveView.current = activeView;
  }, [activeView]);

  useEffect(() => {
    if (activeView === 'chat' && chatContainerRef.current) {
      const container = chatContainerRef.current;

      // ResizeObserver to detect when the content height changes (e.g. typewriter effect)
      const resizeObserver = new ResizeObserver(() => {
        // If AI is typing or we were already near the bottom, scroll to follow
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 150;

        if (isLoading || isNearBottom) {
          // Use requestAnimationFrame to ensure the scroll happens after the browser has calculated the new layout
          requestAnimationFrame(() => {
            container.scrollTop = container.scrollHeight;
          });
        }
      });

      // Observe the content container (the first child of the scrollable container)
      const scrollContent = container.querySelector('.max-w-4xl');
      if (scrollContent) {
        resizeObserver.observe(scrollContent);
      }

      return () => resizeObserver.disconnect();
    }
  }, [activeView, isLoading]);

  useEffect(() => {
    if (activeView === 'chat') {
      const isNewMessage = messages.length > lastMessagesLength.current;
      const lastMessage = messages[messages.length - 1];
      const isContentUpdating = lastMessage && lastMessage.content.length > lastContentLength.current;
      const isAiTyping = isLoading && lastMessage?.role === 'model';

      const timeoutId = setTimeout(() => {
        const shouldScroll = isInitialMount.current || isNewMessage || isAiTyping || isContentUpdating;

        if (shouldScroll) {
          scrollToBottom(isAiTyping || isContentUpdating);
        }

        if (isInitialMount.current) isInitialMount.current = false;
        lastMessagesLength.current = messages.length;
        lastContentLength.current = lastMessage?.content.length || 0;
      }, 20);

      return () => clearTimeout(timeoutId);
    }
  }, [messages, isLoading, activeView]);

  // Per-category persistence
  const categoryStatesRef = useRef<Record<string, { messages: Message[], chatId: string }>>({});

  const handleCategoryChange = (newCategory: Category) => {
    if (newCategory !== category) {
      // 1. Save current state
      categoryStatesRef.current[category] = {
        messages: messages,
        chatId: currentChatId
      };

      setCategory(newCategory);

      // 2. Try to restore next state or start new
      const savedState = categoryStatesRef.current[newCategory];

      if (savedState && savedState.messages.length > 0) {
        console.log(`[App] Restoring state for ${newCategory}`, savedState);
        // FIX: Mark as history to prevent re-typing animation
        setMessages(savedState.messages.map(m => ({ ...m, isHistory: true })));
        setCurrentChatId(savedState.chatId);

        // FIX: Force scroll to bottom after state restoration
        requestAnimationFrame(() => {
          setTimeout(() => scrollToBottom(true), 50);
        });
        // Important: Reset backend session if needed, or rely on distinct session IDs
      } else {
        console.log(`[App] No saved state for ${newCategory}, starting new`);
        resetChatSessionSafe();
        setCurrentChatId(generateId());
        pendingMessageSentRef.current = false;

        // Generate welcome message for new category
        const categoryNames: Record<Category, string> = {
          [Category.Auto]: 'อัตโนมัติ',
          [Category.General]: 'ทั่วไป',
          [Category.School]: 'ข้อมูลโรงเรียน',
          [Category.Student]: 'สถิตินักเรียน',
        };

        const categoryEmojis: Record<Category, string> = {
          [Category.Auto]: '✨',
          [Category.General]: '🌐',
          [Category.School]: '🏫',
          [Category.Student]: '📊',
        };

        const categoryDescriptions: Record<Category, string> = {
          [Category.Auto]: 'ระบบจะเลือกหมวดหมู่ที่เหมาะสมจากคำถามของคุณโดยอัตโนมัติ',
          [Category.General]: 'สามารถถามได้ทุกเรื่อง ทั้งคู่มือ ระเบียบ และความรู้ทั่วไป',
          [Category.School]: 'ค้นหาข้อมูลโรงเรียน จำนวนนักเรียน ครู สถานที่ตั้ง',
          [Category.Student]: 'ดูสถิติจำนวนนักเรียน อัตราการเข้าเรียน ข้อมูลเชิงประชากร',
        };

        const userName = user?.name ? user.name.split(' ')[0] : 'คุณ';
        const welcomeMessage: Message = {
          id: generateId(),
          role: 'model',
          content: `สวัสดีครับ **${userName}**! 😊\n\nยินดีต้อนรับเข้าสู่โหมด **${categoryNames[newCategory]}** ${categoryEmojis[newCategory]}\n\n${categoryDescriptions[newCategory]}\n\nมีอะไรให้ช่วยไหมครับ?`,
          timestamp: new Date(),
          isHistory: true
        };

        setMessages([welcomeMessage]);
      }
    }
  };

  const handleStart = (initialCategory?: Category, initialMessage?: string) => {
    // Always save pending message if provided
    if (initialMessage) {
      setMessages([]);
      setCurrentChatId(generateId());
      resetChatSessionSafe();
      setShowHeaderMenu(false);

      // Store the message to be sent when entering chat view
      sessionStorage.setItem('pending_msg', initialMessage);
    }

    if (firebaseUser) {
      if (initialCategory) setCategory(initialCategory);
      // If we are already in chat/workspace view but changing category, it should clear
      if (view === 'chat' && initialCategory && initialCategory !== category) {
        setMessages([]);
        resetChatSessionSafe();
      }

      // If user clicks start/search on landing page, go to chat directly
      // BUT if just logging in or starting generally, go to workspace?
      // For now, if initialCategory/message is provided (from search), go to Chat.
      // If just "Enter", go to Workspace.

      if (initialCategory || initialMessage) {
        navigateTo('chat');
      } else {
        navigateTo('chat');
      }
    } else {
      if (initialCategory) setCategory(initialCategory);
      navigateTo('login');
    }
  };

  const handleLoginSuccess = (loggedInUser: User) => {
    setUser(loggedInUser);
    navigateTo('chat');
  };


  const handleNewChat = () => {
    resetChatSessionSafe();
    setCurrentChatId(generateId());
    setCategory(Category.General); // FIX: Always reset to General category
    setMessages([]); // Start with empty - user initiates
  };

  const handleDeleteChat = async (session: ChatSession) => {
    if (!firebaseUser) return;

    const confirmed = window.confirm(`ลบประวัติการสนทนา "${session.title}" ใช่หรือไม่?`);
    if (!confirmed) return;

    try {
      await chatService.deleteSession(session.sessionId, firebaseUser.uid);
      setPastChats(prev => prev.filter(chat => chat.sessionId !== session.sessionId));

      if (currentChatId === session.sessionId) {
        handleNewChat();
      }
    } catch (error) {
      console.error('[chatService] Delete session failed:', error);
      window.alert('ลบประวัติไม่สำเร็จ กรุณาลองใหม่อีกครั้ง');
    }
  };

  const loadPastChat = async (session: ChatSession) => {
    setIsLoading(true);
    resetChatSessionSafe();
    setCurrentChatId(session.sessionId);
    setCategory(session.category);

    // Fetch messages from cloud
    const cloudMessages = await chatService.getSessionMessages(session.sessionId, session.userId);
    if (cloudMessages.length > 0) {
      // Mark cloud messages as history
      setMessages(cloudMessages.map(m => ({ ...m, isHistory: true })));
    } else {
      setMessages([]);
    }

    setShowHeaderMenu(false);
    setIsLoading(false);
  };

  const handleLogout = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    showToast('กำลังออกจากระบบ...', 'info', 1200);

    try {
      // Clear persistent storage (Security)
      localStorage.removeItem('current_chat_id');
      localStorage.removeItem('current_messages');
      localStorage.removeItem('current_category');

      // Clear Admin Session
      setIsAdminAuthenticated(false);
      clearAdminSession();

      // Reset RAG Debug Mode for safety
      await updateConfig({ uxPolicy: { ...config.uxPolicy, showRagDebug: false } });

      await firebaseLogout();
      navigateTo('home');
      setUser(null);
      setMessages([]);
      setPastChats([]);
      setShowHeaderMenu(false);
      setIsLoading(false);
      showToast('ออกจากระบบเรียบร้อยแล้ว', 'success');
    } catch (error) {
      console.error('[Auth] Logout failed:', error);
      showToast('ออกจากระบบไม่สำเร็จ กรุณาลองใหม่', 'error', 3200);
    }
  };

  // Format history for Gemini - limit to last 10 messages for optimal context
  const formattedHistory = messages
    .slice(-10) // ✨ Enhanced Context: Keep last 10 messages
    .filter(m => !m.isError && m.content) // Filter valid msgs
    .map(m => ({
      role: m.role,
      parts: [{ text: m.content }]
    }));

  // ✨ Regenerate Response - re-send last user message
  const handleRegenerate = () => {
    // Find last user message
    const lastUserMessageIndex = messages.map((m, i) => ({ ...m, idx: i }))
      .filter(m => m.role === 'user')
      .pop()?.idx;

    if (lastUserMessageIndex === undefined) return;

    const lastUserMessage = messages[lastUserMessageIndex];

    // Remove the last assistant message and re-send
    setMessages(prev => prev.slice(0, prev.length - 1));

    // Re-send the same message
    handleSendMessage(lastUserMessage.content, null);
  };

  // ✨ Edit Message - edit a user message and regenerate from that point
  const handleEditMessage = (messageId: string, newContent: string) => {
    // Find the index of the message to edit
    const messageIndex = messages.findIndex(m => m.id === messageId);
    if (messageIndex === -1) return;

    // Truncate all messages from the edited message onwards
    setMessages(prev => prev.slice(0, messageIndex));

    // Re-send the edited message
    handleSendMessage(newContent, null);
  };

  const stripForSpeech = (text: string): string => {
    if (!text) return '';
    let cleaned = text;
    cleaned = cleaned.replace(/<thinking>[\s\S]*?<\/thinking>/g, '');
    cleaned = cleaned.replace(/<chart>[\s\S]*?<\/chart>/g, '');
    cleaned = cleaned.replace(/<map>[\s\S]*?<\/map>/g, '');
    cleaned = cleaned.replace(/<suggestions>[\s\S]*?<\/suggestions>/g, '');
    cleaned = cleaned.replace(/`{3}[\s\S]*?`{3}/g, '');
    cleaned = cleaned.replace(/`([^`]+)`/g, '$1');
    cleaned = cleaned.replace(/!\[.*?\]\(.*?\)/g, '');
    cleaned = cleaned.replace(/\[(.*?)\]\(.*?\)/g, '$1');
    cleaned = cleaned.replace(/^\s*\|.*\|\s*$/gm, '');
    cleaned = cleaned.replace(/^\s*-{3,}\s*$/gm, '');
    cleaned = cleaned.replace(/[*_>#`]+/g, '');
    cleaned = cleaned.replace(/\n{2,}/g, '\n');
    cleaned = cleaned.replace(/<[^>]+>/g, '');
    return cleaned.trim();
  };

  const getPreferredVoice = (): SpeechSynthesisVoice | null => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    if (selectedVoiceUri) {
      const chosen = voices.find(v => v.voiceURI === selectedVoiceUri);
      if (chosen) return chosen;
    }
    // น้องดีโอ = male persona → prefer Thai male voices
    const thaiVoices = voices.filter(v => v.lang?.toLowerCase().startsWith('th'));
    // Prefer male-sounding voices (lower ID/index typically = male on most platforms)
    const thaiMale = thaiVoices.find(v =>
      /male|niwat|prem/i.test(v.name) && !/female/i.test(v.name)
    );
    if (thaiMale) return thaiMale;
    // Fallback: any Thai voice
    if (thaiVoices.length > 0) return thaiVoices[0];
    return voices.find(v => v.lang?.toLowerCase().startsWith('en')) || null;
  };

  const getFallbackVoice = (): SpeechSynthesisVoice | null => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    return voices.find(v => v.lang?.toLowerCase().startsWith('en')) || voices[0] || null;
  };

  const stopSpeaking = () => {
    // Stop backend TTS audio
    if (ttsAudioRef.current) {
      ttsAudioRef.current.pause();
      ttsAudioRef.current.currentTime = 0;
      ttsAudioRef.current = null;
    }
    // Also stop browser speech (fallback)
    try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
    // Clear pending speak timer
    if (speakTimerRef.current) {
      clearTimeout(speakTimerRef.current);
      speakTimerRef.current = null;
    }
    setIsSpeaking(false);
  };

  const playTestBeep = () => {
    if (typeof window === 'undefined') return;
    try {
      const AudioCtx = (window as any).AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 880;
      gain.gain.value = 0.04;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
      osc.onended = () => {
        ctx.close().catch(() => undefined);
      };
    } catch {
      // ignore
    }
  };

  const unlockSpeech = () => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      // Just cancel and resume — don't play a silent utterance
      // (playing '.' was getting canceled and conflicting with real speak calls)
      window.speechSynthesis.cancel();
      window.speechSynthesis.resume();
      setSpeechUnlocked(true);
      setSpeechError('');
      setTimeout(() => {
        const voices = window.speechSynthesis.getVoices();
        if (!voices || voices.length === 0) {
          setSpeechError('ไม่พบเสียงในระบบ');
        } else {
          console.log(`[TTS] ${voices.length} voices available`);
        }
      }, 300);
    } catch (e) {
      console.error('[TTS] Unlock failed:', e);
    }
  };

  const primeSpeech = () => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      const u = new SpeechSynthesisUtterance(' ');
      u.volume = 0;
      window.speechSynthesis.speak(u);
    } catch {
      // ignore
    }
  };

  // Chrome workaround: SpeechSynthesis pauses silently after ~15s
  // Calling resume() periodically keeps it alive
  const resumeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startResumeWorkaround = () => {
    stopResumeWorkaround();
    resumeIntervalRef.current = setInterval(() => {
      if (window.speechSynthesis?.speaking) {
        window.speechSynthesis.resume();
      }
    }, 5000);
  };

  const stopResumeWorkaround = () => {
    if (resumeIntervalRef.current) {
      clearInterval(resumeIntervalRef.current);
      resumeIntervalRef.current = null;
    }
  };

  const speakText = (text: string): boolean => {
    if (speechMuted) {
      setSpeechError('ปิดเสียงอยู่');
      return false;
    }
    const cleaned = stripForSpeech(text);
    if (!cleaned) {
      console.warn('[TTS] No text to speak after cleaning');
      return false;
    }

    // Stop anything currently playing
    stopSpeaking();

    // Determine Flask API URL (same pattern as geminiService)
    const hostname = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
    const flaskUrl = `http://${hostname}:5001`;

    setIsSpeaking(true);
    setSpeechError('');
    console.log('[TTS] Calling backend Edge TTS...');

    // Call backend TTS API
    fetch(`${flaskUrl}/api/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: cleaned.slice(0, 1000),
        voice: 'th-TH-NiwatNeural',
        rate: '+5%',
        pitch: '-20Hz',
      }),
    })
      .then(res => res.json())
      .then(data => {
        if (!data.success || !data.audio) {
          throw new Error(data.error || 'TTS failed');
        }
        console.log(`[TTS] Audio received: ${data.text_length} chars, voice=${data.voice}`);

        const audio = new Audio(`data:audio/mp3;base64,${data.audio}`);
        ttsAudioRef.current = audio;

        audio.onplay = () => {
          console.log('[TTS] ✅ Playing!');
          setSpeechError('');
          setSpeechUnlocked(true);
        };
        audio.onended = () => {
          console.log('[TTS] Speaking ended, talkMode:', isTalkModeRef.current);
          setIsSpeaking(false);
          ttsAudioRef.current = null;
          // Use REF for latest value — closure would be stale
          if (isTalkModeRef.current) {
            console.log('[TTS] Auto-listen: triggering next listen cycle');
            setTimeout(() => setAutoListenSignal(s => s + 1), 350);
          }
        };
        audio.onerror = (e) => {
          console.error('[TTS] Audio playback error:', e);
          setSpeechError('เล่นเสียงไม่ได้');
          setIsSpeaking(false);
          ttsAudioRef.current = null;
          if (isTalkModeRef.current) {
            setTimeout(() => setAutoListenSignal(s => s + 1), 350);
          }
        };

        audio.play().catch(err => {
          console.error('[TTS] Play failed:', err);
          setSpeechError('เล่นเสียงไม่ได้');
          setIsSpeaking(false);
          ttsAudioRef.current = null;
          // Even on failure, keep the talk loop going
          if (isTalkModeRef.current) {
            setTimeout(() => setAutoListenSignal(s => s + 1), 350);
          }
        });
      })
      .catch(err => {
        console.error('[TTS] Backend TTS error:', err);
        setSpeechError(`TTS error: ${err.message}`);
        playTestBeep();
        setIsSpeaking(false);
        if (isTalkModeRef.current) {
          setTimeout(() => setAutoListenSignal(s => s + 1), 350);
        }
      });

    return true;
  };

  const handleSendMessage = async (text: string, imageData: string | null) => {
    stopSpeaking();
    const userMessageId = generateId();
    const modelMessageId = generateId();
    const userMessage: Message = { id: userMessageId, role: 'user', content: text || "[รูปภาพ]", timestamp: new Date() };

    // CRITICAL: Add both messages atomically in single state update to prevent race condition
    setMessages(prev => [...prev, userMessage, { id: modelMessageId, role: 'model', content: '', timestamp: new Date() }]);
    setIsLoading(true);

    // Fire-and-forget: Log to Firebase without blocking
    chatService.logMessage({
      sessionId: currentChatId,
      userId: firebaseUser?.uid || null,
      userName: user?.name || null,
      userEmail: firebaseUser?.email || null,
      role: 'user',
      content: text || "[รูปภาพ]",
      category: category,
      modelName: config.model.name,
    }).catch(err => console.error('[chatService] User log error:', err));

    // 2. Create/Update Session Metadata
    const isFirstUserMessage = messages.filter(m => m.role === 'user').length === 0;
    const sessionTitle = isFirstUserMessage ? (text.length > 30 ? text.substring(0, 30) + '...' : text) : undefined;

    const sessionUpdate: ChatSession = {
      sessionId: currentChatId,
      userId: firebaseUser?.uid || '',
      category: category,
      title: sessionTitle || 'New Chat'
    };
    if (sessionTitle) {
      sessionUpdate.title = sessionTitle;
      // Optimistic update for sidebar - remove existing if present and put at top
      setPastChats(prev => [
        {
          sessionId: currentChatId,
          userId: firebaseUser?.uid || '',
          title: sessionTitle || (prev.find(s => s.sessionId === currentChatId)?.title || text),
          category: category,
          updatedAt: new Date()
        },
        ...prev.filter(s => s.sessionId !== currentChatId)
      ]);
    }
    // Fire-and-forget session save
    chatService.saveSession(sessionUpdate).catch(err => console.error('[chatService] Session save error:', err));


    try {
      let fullContent = '';
      const systemInstruction = getSystemInstruction(category);

      // Use RAF to batch streaming updates and prevent excessive re-renders
      let rafId: number | null = null;
      let pendingContent = '';

      const batchedUpdate = (content: string) => {
        pendingContent = content;
        if (rafId === null) {
          rafId = requestAnimationFrame(() => {
            setMessages(prev => {
              const updated = [...prev];
              const idx = updated.findIndex(m => m.id === modelMessageId);
              if (idx !== -1) {
                updated[idx] = { ...updated[idx], content: pendingContent };
              }
              return updated;
            });
            rafId = null;
          });
        }
      };

      // Pass the CURRENT history state (including the new user message implicitly via context management logic, 
      // but here we pass the PREVIOUS history to initialize if needed. 
      // The new message itself is sent as the prompt.)
      const stableSessionId = firebaseUser?.uid
        ? `${firebaseUser.uid}_${currentChatId}`
        : `guest_${currentChatId}`;

      const gemini = await loadGeminiService();

      await gemini.sendMessageStream(
        text,
        category,
        imageData,
        systemInstruction,
        (chunk) => {
          fullContent += chunk;
          batchedUpdate(fullContent);
        },
        stableSessionId,
        formattedHistory,
        (debugInfo) => {
          // Immediate RAG Debug Update - less frequent, no need to batch
          setMessages(prev => prev.map(m => m.id === modelMessageId ? { ...m, ragDebugInfo: debugInfo } : m));
        }
      );

      // Cancel any pending RAF and do final update
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }

      // Attach RAG debug info to the message (for admin mode display)
      const ragDebugInfo = gemini.getLastRagDebugInfo();
      setMessages(prev => prev.map(m => m.id === modelMessageId ? { ...m, content: fullContent, ragDebugInfo } : m));

      if (isTalkModeRef.current) {
        const spoke = speakText(fullContent);
        if (!spoke) {
          setTimeout(() => setAutoListenSignal(s => s + 1), 350);
        }
      }

      // 3. Log AI Response
      await chatService.logMessage({
        sessionId: currentChatId,
        userId: firebaseUser?.uid || null,
        userName: user?.name || null,
        userEmail: firebaseUser?.email || null,
        role: 'model',
        content: fullContent,
        category: category,
        modelName: config.model.name,
        isError: false,
      });
    } catch (error: any) {
      setMessages(prev => prev.map(m => {
        if (m.id === modelMessageId) {
          const content = m.content || error.message || config.uxPolicy.errorMessage;

          // Log error response to Firebase
          chatService.logMessage({
            sessionId: currentChatId,
            userId: firebaseUser?.uid || null,
            userName: user?.name || null,
            userEmail: firebaseUser?.email || null,
            role: 'model',
            content: content,
            category: category,
            modelName: config.model.name,
            isError: true,
          });

          return { ...m, content, isError: true };
        }
        return m;
      }));
    } finally {
      setIsLoading(false);
    }
  };

  // Admin Session persistence (Token-based)
  useEffect(() => {
    const token = getAdminToken();
    if (token) setIsAdminAuthenticated(true);
  }, []);

  const renderViewContent = (viewName: View, isExiting: boolean) => {
    const animationClass = isExiting ? 'fluid-exit z-0 pointer-events-none' : 'fluid-entrance z-10';
    const bgClass = viewName === 'home' ? 'bg-transparent' : 'bg-[#F2F2F7]';
    const commonClasses = `absolute inset-0 w-full h-full ${animationClass} ${bgClass} overflow-hidden`;

    if (viewName === 'home') {
      return (
        <div key="view-home" className={commonClasses}>
          <Suspense fallback={<div className="w-full h-full bg-transparent" />}>
            <LandingPage onStart={handleStart} onAdminLogin={() => setShowAdminLogin(true)} onLogout={handleLogout} user={user} />
          </Suspense>
        </div>
      );
    }

    if (viewName === 'login') {
      return (
        <div key="view-login" className={`${commonClasses} flex items-center justify-center`}>
          <Suspense fallback={<div className="w-full h-full" />}>
            <LoginPage onLogin={handleLoginSuccess} onBack={() => navigateTo('home')} />
          </Suspense>
        </div>
      );
    }

    if (viewName === 'chat') {
      const talkStatus = !speechUnlocked
        ? 'แตะเพื่อเปิดเสียง'
        : isListening
          ? 'กำลังฟัง...'
          : isLoading
            ? 'กำลังคิด...'
            : isSpeaking
              ? 'กำลังพูด...'
              : 'แตะเพื่อพูด';
      const statusGlow = isListening
        ? 'from-[#00C7FF]/35 via-[#007AFF]/30 to-transparent'
        : isSpeaking
          ? 'from-[#AF52DE]/35 via-[#5856D6]/30 to-transparent'
          : isLoading
            ? 'from-[#34C759]/30 via-[#30D158]/25 to-transparent'
            : 'from-[#A0A0A0]/20 via-[#C7C7CC]/15 to-transparent';
      const ringAmp = isListening ? micLevel : (isSpeaking ? 0.25 : 0.12);
      return (
        <div key="view-chat" className={`${commonClasses} flex flex-col`}>
          {/* Unifed Background Texture - Matches Landing Page with Heavy Overlay */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
            <div
              className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-40 grayscale-[0.2]"
              style={{ backgroundImage: 'url("/custom-bg.jpg")' }}
            ></div>
            {/* Ultra Heavy Overlay to keep chat background "white" as requested, but textured */}
            <div className="absolute inset-0 bg-[#F5F5FA]/95 backdrop-blur-[50px]"></div>
          </div>

          {/* ✨ Mobile Drawer Overlay - Smooth iOS-style transitions */}
          <MobileMenu
            isOpen={isMobileMenuOpen}
            onClose={() => setIsMobileMenuOpen(false)}
            user={user}
            currentChatId={currentChatId}
            pastChats={pastChats}
            onNewChat={handleNewChat}
            onLoadChat={loadPastChat}
            onDeleteChat={handleDeleteChat}
            onLogout={handleLogout}
            onNavigateHome={() => navigateTo('home')}
          />

          {/* Main Layout - Full Height Flex */}
          <div className="relative z-10 flex-1 flex overflow-hidden">
            {/* Sidebar - Glass Panel */}
            <aside className="hidden md:flex flex-col w-[280px] flex-shrink-0 bg-white/80 backdrop-blur-3xl border-r border-white/50 shadow-[inset_-1px_0_0_rgba(255,255,255,0.5)] slide-right-sidebar relative overflow-hidden">
              {/* Subtle Grain Overlay for Sidebar */}
              <div className="absolute inset-0 pointer-events-none opacity-[0.03] mix-blend-overlay z-0" style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\'/%3E%3C/svg%3E")' }}></div>

              {/* Logo Header */}
              <div className="relative z-10 flex items-center gap-3.5 px-6 py-6 cursor-pointer group" onClick={() => navigateTo('home')}>
                <div className="w-12 h-12 rounded-2xl overflow-hidden shadow-lg ring-1 ring-white/10 group-hover:scale-110 group-hover:shadow-xl group-hover:ring-blue-500/20 transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-active:scale-95">
                  <img src="/do-mascot.png" alt="DO - MOE One" className="w-full h-full object-cover" />
                </div>
                <div className="transition-transform duration-300 group-hover:translate-x-0.5">
                  <h1 className="font-bold text-[17px] tracking-tight text-[#1D1D1F] group-hover:text-blue-600 transition-colors duration-300">MOE - One</h1>
                  <p className="text-[10px] font-semibold opacity-50 uppercase tracking-[0.15em]">ศทส. • สป.</p>
                </div>
              </div>

              {/* New Chat Button */}
              <div className="relative z-10 px-5 mb-5">
                <button
                  onClick={handleNewChat}
                  className="flex items-center justify-center gap-2 w-full py-3 rounded-xl bg-[#1D1D1F] text-white hover:bg-black hover:shadow-[0_12px_28px_rgba(0,0,0,0.25)] hover:scale-[1.02] transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.96] font-semibold text-[14px] shadow-lg"
                >
                  <div className="w-5 h-5 rounded-lg bg-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-3.5 h-3.5"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
                  </div>
                  สนทนาใหม่
                </button>
              </div>

              <nav className="relative z-10 flex-1 overflow-y-auto no-scrollbar px-4 fade-mask-b">
                {/* CategorySelector removed - unified single chatbot mode */}
                {pastChats.length > 0 && (
                  <div className="mt-8 slide-up-content stagger-2">
                    <div className="px-2 text-[10px] font-black uppercase tracking-[0.2em] mb-3 opacity-30">ประวัติการสนทนา</div>
                    <div className="space-y-1">
                      {pastChats.map(chat => (
                        <div key={chat.sessionId} className="group/item flex items-center gap-1.5">
                          <button
                            onClick={() => loadPastChat(chat)}
                            className={`flex-1 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-300 ease-out cursor-pointer truncate flex items-center gap-3 border transform text-left
                            ${currentChatId === chat.sessionId
                                ? 'bg-white shadow-[0_6px_16px_rgba(0,0,0,0.08)] border-white/80 font-bold text-[#1D1D1F] scale-[1.02]'
                                : 'hover:bg-white/60 hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)] text-black/40 hover:text-black/70 border-transparent hover:border-white/50 active:scale-[0.98] active:bg-white/80'
                              }`}
                          >
                            <div className={`w-1.5 h-1.5 rounded-full shrink-0 transition-all duration-500 ${currentChatId === chat.sessionId ? 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)] scale-100' : 'bg-transparent scale-0'}`}></div>
                            <span className="truncate">{chat.title}</span>
                          </button>
                          <button
                            onClick={() => handleDeleteChat(chat)}
                            className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-black/30 hover:text-[#FF3B30] hover:bg-white/80 active:scale-95 transition-all duration-200 opacity-0 group-hover/item:opacity-100"
                            title="ลบประวัติ"
                            aria-label={`ลบ ${chat.title}`}
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-4 h-4">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M6 7.5h12m-9 0v10.125c0 .621.504 1.125 1.125 1.125h3.75c.621 0 1.125-.504 1.125-1.125V7.5m-7.5 0V6.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V7.5" />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </nav>

              {/* User Profile & Logout */}
              <div className="p-5 border-t border-black/5 bg-white/40 backdrop-blur-md">
                {user && (
                  <div className="mb-4 p-3 rounded-2xl bg-white/60 border border-white/60 shadow-sm flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-md ring-2 ring-white/80 overflow-hidden">
                      {user.avatar && !sidebarImgError ? (
                        <img
                          src={user.avatar}
                          alt={user.name}
                          className="w-full h-full object-cover"
                          onError={() => setSidebarImgError(true)}
                        />
                      ) : (
                        user.initials || user.name.charAt(0)
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-bold text-[#1D1D1F] truncate">{user.name}</p>
                      <p className="text-[9px] font-bold text-blue-600/60 uppercase tracking-widest">{user.role}</p>
                    </div>
                  </div>
                )}
                <button onClick={handleLogout} className="flex items-center gap-2.5 w-full px-3 py-2.5 rounded-xl text-[#FF3B30] font-semibold hover:bg-red-50 hover:shadow-[0_4px_12px_rgba(255,59,48,0.15)] transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.96] text-[13px] group">
                  <div className="w-7 h-7 rounded-lg bg-red-100/80 flex items-center justify-center group-hover:bg-red-200 group-hover:scale-110 transition-all duration-300">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" /></svg>
                  </div>
                  ลงชื่อออก
                </button>
              </div>
            </aside>

            {/* Main Chat Area - Glass Container */}
            <main className="flex-1 flex flex-col relative overflow-hidden">
              {/* Header Bar - Frosted Glass */}
              <header className="app-header h-16 flex items-center justify-between px-4 md:px-8 bg-white/70 backdrop-blur-xl border-b border-white/50 shadow-sm z-20">
                <div className="flex items-center gap-3">
                  {/* ✨ Mobile Menu Button */}
                  <button
                    onClick={() => setIsMobileMenuOpen(true)}
                    className="md:hidden w-10 h-10 -ml-2 flex items-center justify-center rounded-full hover:bg-black/5 active:bg-black/10 transition-all text-[#1D1D1F]"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-6 h-6">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12H12m-8.25 5.25h16.5" />
                    </svg>
                  </button>

                  <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-md">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                    </svg>
                  </div>
                  <div>
                    <h2 className="font-bold text-[16px] text-[#1D1D1F] tracking-tight">สนทนา</h2>
                    <span className="text-[9px] font-black text-black/30 uppercase tracking-[0.1em] hidden sm:block">AI Assistant • ศทส.</span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {isAdminAuthenticated && config.uxPolicy.showRagDebug && (
                    <div className="px-3 py-1.5 rounded-full bg-amber-100 border border-amber-200 shadow-sm text-[10px] font-black flex items-center gap-1.5 text-amber-700 animate-pulse">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
                        <path fillRule="evenodd" d="M9.401 3.003c.115-.283.392-.47.699-.47h3.8c.307 0 .584.187.699.47l.54 1.326a5.153 5.153 0 002.312 2.312l1.326.54c.283.115.47.392.47.699v3.8c0 .307-.187.584-.47.699l-1.326.54a5.153 5.153 0 00-2.312 2.312l-.54 1.326a.75.75 0 01-.699.47h-3.8a.75.75 0 01-.699-.47l-.54-1.326a5.153 5.153 0 00-2.312-2.312l-1.326-.54a.75.75 0 01-.47-.699v-3.8c0-.307.187-.584.47-.699l1.326-.54a5.153 5.153 0 002.312-2.312l.54-1.326zM12 9a.75.75 0 01.75.75v2.5a.75.75 0 01-1.5 0v-2.5A.75.75 0 0112 9zm0 6a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
                      </svg>
                      ADMIN TEST MODE
                    </div>
                  )}
                  <div className="hidden sm:flex px-4 py-1.5 rounded-full bg-white/80 backdrop-blur-md border border-white/60 shadow-sm text-[11px] font-semibold items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                    <span className="text-black/60">Mode:</span>
                    <span className="text-blue-600">DO AI</span>
                  </div>
                </div>
              </header>

              <div
                ref={chatContainerRef}
                className={`chat-scroll flex-1 overflow-y-auto no-scrollbar relative ${isTalkMode ? 'pointer-events-none' : 'pointer-events-auto'}`}
              >
                {/* Mobile category selector removed - unified single chatbot mode */}

                <>
                  <div
                    className={`fixed inset-0 z-20 talk-overlay ${isTalkMode ? 'talk-overlay-active' : 'talk-overlay-hidden'}`}
                    aria-hidden={!isTalkMode}
                  >
                    <div className="talk-blob blob-1"></div>
                    <div className="talk-blob blob-2"></div>
                    <div className="talk-blob blob-3"></div>
                    <div className="talk-vignette"></div>
                    <div className="absolute inset-0 grain-overlay"></div>
                  </div>
                  {/* Siri-like Voice Orb Overlay */}
                  <div
                    className={`fixed inset-0 z-30 flex items-center justify-center talk-orb-layer ${isTalkMode ? 'talk-orb-active pointer-events-auto' : 'talk-orb-hidden pointer-events-none'}`}
                    aria-hidden={!isTalkMode}
                  >
                    <div className="relative flex flex-col items-center gap-4">
                      <div className={`absolute -inset-14 rounded-full bg-gradient-to-br ${statusGlow} blur-[80px] opacity-90`}></div>
                      <div
                        className="talk-orb"
                        style={{ ['--level' as any]: isListening ? micLevel : (isSpeaking ? 0.25 : 0.08) }}
                      >
                        <div className="talk-orb-glow"></div>
                        <div className="talk-orb-core"></div>
                      </div>
                      <div className="flex items-center gap-1">
                        {[0.55, 0.8, 1.05, 1.35, 1.05, 0.8, 0.55].map((level, i) => {
                          const scale = isListening
                            ? Math.max(0.25, 0.25 + micLevel * level * 1.4)
                            : undefined;
                          return (
                            <span
                              key={`wave-${i}`}
                              className={`siri-wave-bar ${isListening ? '' : (isSpeaking || isLoading ? 'siri-wave-active' : 'siri-wave-idle')}`}
                              style={{
                                animationDelay: `${i * 90}ms`,
                                transform: scale ? `scaleY(${scale})` : undefined,
                                transition: isListening ? 'transform 80ms linear' : undefined
                              }}
                            />
                          );
                        })}
                      </div>
                      <div className="siri-ring">
                        {Array.from({ length: 28 }).map((_, i) => (
                          <span
                            key={`ring-${i}`}
                            className="siri-ring-bar"
                            style={{
                              ['--rot' as any]: `${i * (360 / 28)}deg`,
                              ['--amp' as any]: ringAmp.toFixed(3),
                              ['--delay' as any]: `${i * 35}ms`
                            }}
                          />
                        ))}
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          unlockSpeech();
                          if (!isListening && !isLoading) {
                            setAutoListenSignal(s => s + 1);
                          }
                        }}
                        className={`talk-ready-btn ${isListening ? 'talk-ready-disabled' : ''}`}
                        disabled={isListening || isLoading}
                      >
                        {talkStatus}
                      </button>
                      <div className="text-[11px] font-medium text-white/70">
                        {speechError
                          ? speechError
                          : voicesReady
                            ? 'เสียงพร้อมใช้งาน'
                            : 'กำลังโหลดเสียง...'}
                      </div>
                    </div>
                  </div>

                  {/* Controls Dock */}
                  <div
                    className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-40 talk-controls-layer ${isTalkMode ? 'talk-controls-active' : 'talk-controls-hidden'}`}
                    aria-hidden={!isTalkMode}
                  >
                    <div className="talk-controls">
                      <button
                        type="button"
                        onClick={() => setSpeechMuted(prev => !prev)}
                        className={`talk-control-btn ${speechMuted ? 'talk-control-muted' : 'talk-control-active'
                          }`}
                        title={speechMuted ? 'เปิดเสียง' : 'ปิดเสียง'}
                      >
                        {speechMuted ? 'ปิดเสียงอยู่' : 'เสียงเปิด'}
                      </button>
                      <select
                        value={selectedVoiceUri}
                        onChange={(e) => setSelectedVoiceUri(e.target.value)}
                        className="talk-voice-select"
                      >
                        {availableVoices.length === 0 && (
                          <option value="">{voicesReady ? 'ไม่พบเสียง' : 'กำลังโหลดเสียง...'}</option>
                        )}
                        {availableVoices.map(v => (
                          <option key={v.voiceURI} value={v.voiceURI}>
                            {v.name} ({v.lang})
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => {
                          if (speechMuted) setSpeechMuted(false);
                          // Call speak DIRECTLY from click handler — no setTimeout!
                          // This ensures it runs within the user gesture for Chrome autoplay policy
                          window.speechSynthesis?.cancel();
                          window.speechSynthesis?.resume();
                          setSpeechUnlocked(true);
                          setSpeechError('');
                          const ok = speakText('ทดสอบเสียงน้องดีโอครับ');
                          if (!ok) playTestBeep();
                        }}
                        className="talk-control-btn"
                      >
                        ทดสอบเสียง
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setIsTalkMode(false);
                          stopSpeaking();
                          setStopListeningSignal(s => s + 1);
                          setIsListening(false);
                        }}
                        className="talk-control-btn talk-control-exit"
                      >
                        ปิดโหมด
                      </button>
                    </div>
                  </div>
                </>

                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-32 pt-6">
                  {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center min-h-[60vh] pb-20 animate-in fade-in zoom-in-95 duration-1000 ease-out">

                      {/* ── MOBILE: No-box, minimal greeting ── */}
                      <div className="md:hidden flex flex-col items-center text-center px-4 pt-8 pb-6 w-full">
                        {/* Small orb icon */}
                        <div className="w-14 h-14 rounded-[18px] bg-gradient-to-br from-[#7CC5FF] via-[#9B8CFF] to-[#C7A6FF] flex items-center justify-center shadow-lg mb-5">
                          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-7 h-7">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                          </svg>
                        </div>
                        <h2 className="text-[22px] font-bold text-[#1D1D1F] tracking-tight mb-1">
                          สวัสดีครับ! ผมคือ <span className="hero-title-accent">น้องดีโอ</span>
                        </h2>
                        <p className="text-[13px] text-[#6e6e73] leading-relaxed max-w-[280px]">
                          ถามได้ทั้งโรงเรียน ครู นักเรียน และสถิติระดับจังหวัด
                        </p>

                        {/* Pill chips — no boxes, compact */}
                        <div className="flex flex-wrap justify-center gap-2 mt-5">
                          {[
                            { icon: "🏫", text: "กรุงเทพมีโรงเรียนกี่แห่ง" },
                            { icon: "👨‍🏫", text: "จำนวนครูในกรุงเทพ" },
                            { icon: "🏆", text: "โรงเรียนที่มีนักเรียนมากที่สุด" },
                            { icon: "📊", text: "อัตราส่วนครูต่อนักเรียน" },
                          ].map((item, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleSendMessage(item.text, null)}
                              className="flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-white/70 border border-black/[0.07] text-[13px] font-medium text-[#3a3a3c] active:scale-95 transition-transform shadow-sm"
                            >
                              <span className="text-[13px]">{item.icon}</span>
                              <span>{item.text}</span>
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* ── DESKTOP: Full hero glass card ── */}
                      <div className="hidden md:block text-center mb-12 relative group w-full">
                        {/* Ambient Glow */}
                        <div className="absolute -top-10 left-1/2 -translate-x-1/2 w-[320px] h-[320px] bg-gradient-to-tr from-[#7CC5FF]/35 via-[#9B8CFF]/30 to-[#C7A6FF]/25 rounded-full blur-[90px] opacity-70 group-hover:opacity-100 transition-opacity duration-1000"></div>

                        <div className="hero-glass hero-float mx-auto max-w-2xl">
                          <div className="hero-badge">MOE‑One • ศทส. สป.</div>
                          <div className="hero-orb">
                            <div className="hero-orb-glow"></div>
                            <div className="hero-orb-core">
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-8 h-8 drop-shadow-md">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                              </svg>
                            </div>
                          </div>
                          <h2 className="hero-title text-[40px] font-bold text-[#1D1D1F] tracking-[-0.035em] mb-3 leading-tight">
                            สวัสดีครับ! ผมคือ <span className="hero-title-accent">น้องดีโอ</span>
                          </h2>
                          <p className="hero-sub">
                            ผู้ช่วยข้อมูลการศึกษา MOE‑One ของศูนย์เทคโนโลยีสารสนเทศเพื่อการศึกษา (ศทส.) สป.
                          </p>
                          <p className="hero-sub hero-sub-muted">
                            ถามได้ทั้งโรงเรียน ครู นักเรียน และสถิติระดับจังหวัด/อำเภอ/โรงเรียน พร้อมสรุปให้อ่านง่ายครับ
                          </p>
                          <button
                            type="button"
                            onClick={() => {
                              const chatInput = document.querySelector('textarea');
                              if (chatInput) (chatInput as HTMLTextAreaElement).focus();
                            }}
                            className="hero-cta-btn"
                          >
                            เริ่มถามเลย
                          </button>
                        </div>
                      </div>

                      {/* Sample Questions Grid - Desktop only */}
                      <div className="hidden md:grid grid-cols-2 gap-4 w-full max-w-2xl px-2">
                        {[
                          { icon: "🏫", text: "กรุงเทพมีโรงเรียนกี่แห่ง" },
                          { icon: "👨‍🏫", text: "จำนวนครูในกรุงเทพ" },
                          { icon: "🏆", text: "โรงเรียนที่มีนักเรียนมากที่สุด" },
                          { icon: "📊", text: "อัตราส่วนครูต่อนักเรียน" }
                        ].map((item, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleSendMessage(item.text, null)}
                            className="hero-sample-card group relative flex items-center gap-4 px-6 py-5 text-left rounded-[24px] backdrop-blur-xl border shadow-[0_6px_22px_rgba(0,0,0,0.08)] hover:shadow-[0_18px_40px_rgba(0,122,255,0.18),inset_0_0_0_1px_rgba(255,255,255,0.85)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 ease-[cubic-bezier(0.25,0.1,0.25,1)]"
                          >
                            <span className="w-10 h-10 flex items-center justify-center rounded-2xl bg-white shadow-sm text-lg border border-black/5 group-hover:scale-110 transition-transform duration-300">
                              {item.icon}
                            </span>
                            <span className="text-[15px] font-semibold text-gray-700 group-hover:text-[#1D1D1F] transition-colors tracking-tight">
                              {item.text}
                            </span>
                            <div className="absolute right-5 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="#007AFF" className="w-5 h-5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                              </svg>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <Suspense fallback={<div className="h-14" />}>
                    {messages.map((msg, index) => {
                      // Find last assistant message index
                      const lastAssistantIndex = messages.map((m, i) => ({ role: m.role, idx: i }))
                        .filter(m => m.role === 'model')
                        .pop()?.idx;

                      // Find last user message for thinking context
                      const lastUserMsg = messages.slice(0, index + 1)
                        .filter(m => m.role === 'user')
                        .pop()?.content || '';

                      return (
                        <MessageBubble
                          key={msg.id}
                          message={msg}
                          isAdminMode={isAdminAuthenticated && config.uxPolicy.showRagDebug}
                          userAvatar={user?.avatar}
                          userInitials={user?.initials}
                          onRegenerate={handleRegenerate}
                          onEdit={handleEditMessage}
                          isLastAssistantMessage={index === lastAssistantIndex}
                          lastUserMessage={lastUserMsg}
                          isLatestMessage={index === messages.length - 1}
                          sessionId={currentChatId}
                          category={category.toLowerCase() as 'general' | 'school' | 'student'}
                          onSuggestionClick={(text) => handleSendMessage(text, null)}
                        />
                      );
                    })}
                  </Suspense>
                  <div ref={messagesEndRef} className="h-4" />
                </div>
              </div>

              {/* Input Area - Clean Floating */}
              <div
                className={`chat-input-area absolute bottom-0 left-0 right-0 p-3 sm:p-6 z-20 transition-all duration-500 ease-out ${isTalkMode ? 'opacity-0 translate-y-4 pointer-events-none' : 'opacity-100 translate-y-0 pointer-events-auto'}`}
                style={{ display: isTalkMode ? 'none' : 'block' }}
              >
                <div className="pointer-events-auto max-w-4xl mx-auto">
                  <ChatInput
                    onSend={handleSendMessage}
                    disabled={isLoading}
                    isLoading={isLoading}
                    isSpeaking={isSpeaking}
                    onStop={() => {
                      abortCurrentStreamSafe();
                      setIsLoading(false);
                    }}
                    talkMode={isTalkMode}
                    onToggleTalkMode={() => {
                      // CRITICAL: Unlock audio autoplay from user gesture
                      // Play a tiny silent audio to allow future Audio.play() from async contexts
                      try {
                        const silentAudio = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYYoRwmHAAAAAAD/+1DEAAAGAAGn9AAAIiWi7/ckAABNm/8+D58H/5cP/yhAGCYIAgSBAMf/8oQBgEAQB8H4Pg+XB8Hwf/6gAYJOD5//y4Pg+D8uEMf/lCH//5Qh///8uD7///y4f///+D7////5c////B9////y5////w==');
                        silentAudio.volume = 0.01;
                        silentAudio.play().catch(() => { });
                      } catch { /* ignore */ }
                      primeSpeech();
                      unlockSpeech();
                      setIsTalkMode(prev => {
                        const next = !prev;
                        if (!next) {
                          stopSpeaking();
                          setStopListeningSignal(s => s + 1);
                        }
                        if (next) {
                          setAutoListenSignal(s => s + 1);
                        }
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
    }
    return null; // Should not happen if all views are handled
  };

  const renderContainer = () => {
    return (
      <div className="relative w-full h-[100dvh] overflow-hidden bg-[#EEF0F8]">
        {previousView && renderViewContent(previousView, true)}
        {renderViewContent(view, false)}
      </div>
    );
  };

  return (
    <>
      {renderContainer()}
      {uiToast && (
        <div className="fixed top-5 left-1/2 -translate-x-1/2 z-[120] pointer-events-none px-4">
          <div
            className={`rounded-2xl px-4 py-2.5 text-sm font-medium text-white shadow-[0_18px_40px_rgba(0,0,0,0.28)] backdrop-blur-xl border border-white/20 transition-all duration-300 ${uiToast.type === 'success'
              ? 'bg-emerald-600/92'
              : uiToast.type === 'error'
                ? 'bg-rose-600/92'
                : 'bg-[#1f2937]/88'
              }`}
          >
            {uiToast.message}
          </div>
        </div>
      )}
      {showAdminLogin && (
        <Suspense fallback={null}>
          <AdminLogin
            onSuccess={() => {
              setShowAdminLogin(false);
              setIsAdminAuthenticated(true);
              setShowAdminPanel(true);
            }}
            onCancel={() => setShowAdminLogin(false)}
          />
        </Suspense>
      )}
      {showAdminPanel && isAdminAuthenticated && (
        <Suspense fallback={null}>
          <AdminPanel
            onClose={() => {
              setShowAdminPanel(false);
              // NOTE: We do NOT reset isAdminAuthenticated here
              // so the admin can continue to see RAG debug info in the chat.
            }}
            onLogout={() => {
              clearAdminSession();
              setIsAdminAuthenticated(false);
              setShowAdminPanel(false);
            }}
          />
        </Suspense>
      )}
    </>
  );
};

const App: React.FC = () => (
  <AdminConfigProvider>
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  </AdminConfigProvider>
);

export default App;
