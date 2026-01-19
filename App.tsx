

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

import React, { useState, useEffect, useRef } from 'react';
import CategorySelector from './components/CategorySelector';
import MessageBubble from './components/MessageBubble';
import ChatInput from './components/ChatInput';
import LandingPage from './components/LandingPage';
import LoginPage from './components/LoginPage';
import AdminPanel from './components/admin/AdminPanel';
import AdminLogin from './components/admin/AdminLogin';
import { Category, Message, User } from './types';
import { sendMessageStream, startChat, updateGeminiConfig, resetChatSession, getLastRagDebugInfo, abortCurrentStream } from './services/geminiService';
import { chatService, ChatSession } from './services/chatService';
import { MOE_COLORS, COMMON_QUERIES } from './constants';
import { AdminConfigProvider, useAdminConfig } from './contexts/AdminConfigContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';

const generateId = () => Math.random().toString(36).substr(2, 9);

type View = 'home' | 'login' | 'chat';



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

  // Persist Chat State
  useEffect(() => {
    localStorage.setItem('current_category', category);
    localStorage.setItem('current_messages', JSON.stringify(messages));
    localStorage.setItem('current_chat_id', currentChatId);
  }, [category, messages, currentChatId]);
  const [showAdminLogin, setShowAdminLogin] = useState(false);
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);

  // Admin Config Context
  const { config, getSystemInstruction, updateConfig } = useAdminConfig();
  // Auth Context
  const { user: firebaseUser, userRole, logout: firebaseLogout, loading: authLoading } = useAuth(); // rename to avoid conflict

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);

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
    updateGeminiConfig(config);
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

      startChat(systemInstruction, category, initialHistory);

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
        resetChatSession();
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
      resetChatSession();
      setShowHeaderMenu(false);

      // Store the message to be sent when entering chat view
      sessionStorage.setItem('pending_msg', initialMessage);
    }

    if (firebaseUser) {
      if (initialCategory) setCategory(initialCategory);
      // If we are already in chat/workspace view but changing category, it should clear
      if (view === 'chat' && initialCategory && initialCategory !== category) {
        setMessages([]);
        resetChatSession();
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
    resetChatSession();
    setCurrentChatId(generateId());
    setCategory(Category.General); // FIX: Always reset to General category
    setMessages([]); // Start with empty - user initiates
  };

  const loadPastChat = async (session: ChatSession) => {
    setIsLoading(true);
    resetChatSession();
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

    // Clear persistent storage (Security)
    localStorage.removeItem('current_chat_id');
    localStorage.removeItem('current_messages');
    localStorage.removeItem('current_category');

    // Clear Admin Session
    setIsAdminAuthenticated(false);
    sessionStorage.removeItem('is_admin_authenticated');

    // Reset RAG Debug Mode for safety
    await updateConfig({ uxPolicy: { ...config.uxPolicy, showRagDebug: false } });

    await firebaseLogout();
    navigateTo('home');
    setUser(null);
    setMessages([]);
    setPastChats([]);
    setShowHeaderMenu(false);
    setIsLoading(false);
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

  const handleSendMessage = async (text: string, imageData: string | null) => {
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

      // Pass the CURRENT history state (including the new user message implicitly via context management logic, 
      // but here we pass the PREVIOUS history to initialize if needed. 
      // The new message itself is sent as the prompt.)
      await sendMessageStream(
        text,
        category,
        imageData,
        systemInstruction,
        (chunk) => {
          fullContent += chunk;
          setMessages(prev => prev.map(m => m.id === modelMessageId ? { ...m, content: fullContent } : m));
        },
        formattedHistory,
        (debugInfo) => {
          // Immediate RAG Debug Update
          setMessages(prev => prev.map(m => m.id === modelMessageId ? { ...m, ragDebugInfo: debugInfo } : m));
        }
      );

      // Attach RAG debug info to the message (for admin mode display)
      const ragDebugInfo = getLastRagDebugInfo();
      setMessages(prev => prev.map(m => m.id === modelMessageId ? { ...m, content: fullContent, ragDebugInfo } : m));

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

  // Admin Session persistence (Session-only)
  useEffect(() => {
    const savedAdminAuth = sessionStorage.getItem('is_admin_authenticated') === 'true';
    if (savedAdminAuth) setIsAdminAuthenticated(true);
  }, []);

  useEffect(() => {
    sessionStorage.setItem('is_admin_authenticated', isAdminAuthenticated.toString());
  }, [isAdminAuthenticated]);

  const renderViewContent = (viewName: View, isExiting: boolean) => {
    const animationClass = isExiting ? 'fluid-exit z-0 pointer-events-none' : 'fluid-entrance z-10';
    const bgClass = viewName === 'home' ? 'bg-transparent' : 'bg-[#F2F2F7]';
    const commonClasses = `absolute inset-0 w-full h-full ${animationClass} ${bgClass} overflow-hidden`;

    if (viewName === 'home') {
      return (
        <div key="view-home" className={commonClasses}>
          <LandingPage onStart={handleStart} onAdminLogin={() => setShowAdminLogin(true)} onLogout={handleLogout} user={user} />
        </div>
      );
    }

    if (viewName === 'login') {
      return (
        <div key="view-login" className={`${commonClasses} flex items-center justify-center`}>
          <LoginPage onLogin={handleLoginSuccess} onBack={() => navigateTo('home')} />
        </div>
      );
    }

    if (viewName === 'chat') {
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
          <div
            className={`fixed inset-0 z-50 md:hidden font-sans transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${isMobileMenuOpen ? 'pointer-events-auto' : 'pointer-events-none'
              }`}
          >
            {/* Backdrop with smooth fade */}
            <div
              className={`absolute inset-0 bg-black/40 backdrop-blur-xl transition-opacity duration-500 ease-out ${isMobileMenuOpen ? 'opacity-100' : 'opacity-0'
                }`}
              onClick={() => setIsMobileMenuOpen(false)}
            ></div>

            {/* Drawer Panel - iOS-style slide with spring animation */}
            <div
              className={`absolute inset-y-0 left-0 w-[85%] max-w-[340px] bg-white/95 backdrop-blur-3xl shadow-[0_25px_80px_-15px_rgba(0,0,0,0.4)] border-r border-white/30 flex flex-col transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
                }`}
              style={{
                backdropFilter: 'blur(60px) saturate(180%)',
              }}
            >
              {/* Header with ambient glow */}
              <div className="relative flex items-center justify-between p-5 border-b border-black/5">
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 via-purple-500/5 to-transparent"></div>
                <div
                  className="relative flex items-center gap-3 active:scale-95 transition-transform cursor-pointer"
                  onClick={() => {
                    navigateTo('home');
                    setIsMobileMenuOpen(false);
                  }}
                >
                  <div className="w-11 h-11 rounded-2xl bg-white/90 p-1 shadow-lg border border-white/60 ring-1 ring-black/5">
                    <img src="/do-mascot.png" alt="DO" className="w-full h-full object-contain" />
                  </div>
                  <div>
                    <span className="font-bold text-[18px] tracking-tight text-[#1D1D1F] block">MOE - One</span>
                    <span className="text-[9px] font-bold text-black/40 uppercase tracking-[0.15em]">ศทส. • สป.</span>
                  </div>
                </div>
                <button
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="relative w-9 h-9 rounded-full bg-black/5 flex items-center justify-center text-black/50 hover:bg-black/10 active:scale-90 transition-all"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>

              {/* New Chat Button - Apple 2026 Style */}
              <div className="px-4 py-4">
                <button
                  onClick={() => {
                    handleNewChat();
                    setIsMobileMenuOpen(false);
                  }}
                  className="flex items-center justify-center gap-2.5 w-full py-3.5 rounded-2xl bg-gradient-to-r from-[#007AFF] to-[#5856D6] text-white shadow-lg shadow-blue-500/25 active:scale-[0.97] transition-all font-semibold text-[15px]"
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
                    className={`px-4 py-3 rounded-2xl text-[14px] font-medium transition-all duration-300 ease-out mb-2 truncate flex items-center gap-3 cursor-pointer transform
                      ${currentChatId === chat.sessionId
                        ? 'bg-gradient-to-r from-blue-50 to-indigo-50 text-blue-600 shadow-[0_4px_12px_rgba(59,130,246,0.15)] scale-[1.02] border border-blue-100/50'
                        : 'hover:bg-white/60 active:bg-white/80 active:scale-[0.98] text-black/70 hover:text-black hover:shadow-sm border border-transparent hover:border-white/60'
                      }`}
                  >
                    <span className="truncate">{chat.title}</span>
                  </div>
                ))}
              </div>

              {/* Logout Button */}
              <div className="p-4 border-t border-black/5 bg-gradient-to-t from-white/60 to-transparent">
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-3 w-full px-4 py-3.5 rounded-2xl text-[#FF3B30] font-semibold bg-red-50/80 hover:bg-red-100 transition-all active:scale-[0.97] border border-red-100/50"
                >
                  <div className="w-8 h-8 rounded-xl bg-red-100 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" /></svg>
                  </div>
                  ออกจากระบบ
                </button>
              </div>
            </div>
          </div>

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
                <CategorySelector selected={category} onSelect={handleCategoryChange} disabled={isLoading} />
                {pastChats.length > 0 && (
                  <div className="mt-8 slide-up-content stagger-2">
                    <div className="px-2 text-[10px] font-black uppercase tracking-[0.2em] mb-3 opacity-30">ประวัติการสนทนา</div>
                    <div className="space-y-1">
                      {pastChats.map(chat => (
                        <div
                          key={chat.sessionId}
                          onClick={() => loadPastChat(chat)}
                          className={`px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-300 ease-out cursor-pointer truncate flex items-center gap-3 group/item border transform
                          ${currentChatId === chat.sessionId
                              ? 'bg-white shadow-[0_6px_16px_rgba(0,0,0,0.08)] border-white/80 font-bold text-[#1D1D1F] scale-[1.02]'
                              : 'hover:bg-white/60 hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)] text-black/40 hover:text-black/70 border-transparent hover:border-white/50 active:scale-[0.98] active:bg-white/80'
                            }`}
                        >
                          <div className={`w-1.5 h-1.5 rounded-full shrink-0 transition-all duration-500 ${currentChatId === chat.sessionId ? 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)] scale-100' : 'bg-transparent scale-0'}`}></div>
                          <span className="truncate">{chat.title}</span>
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
              <header className="h-16 flex items-center justify-between px-4 md:px-8 bg-white/70 backdrop-blur-xl border-b border-white/50 shadow-sm z-20">
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
                    <span className="text-blue-600">{category === Category.General ? 'ทั่วไป' : category === Category.School ? 'โรงเรียน' : 'สถิติ'}</span>
                  </div>
                </div>
              </header>

              <div ref={chatContainerRef} className="flex-1 overflow-y-auto no-scrollbar relative">
                {/* Sticky Mobile Category - ✨ Apple Style Segmented Control */}
                <div className="sticky top-0 z-10 -mx-6 lg:-mx-8 pt-4 px-2 sm:px-6 lg:px-8 bg-gradient-to-b from-[#F2F2F7] via-[#F2F2F7]/95 to-transparent pb-2 pointer-events-none sticky-category-mobile">
                  <div className="pointer-events-auto md:hidden shadow-sm rounded-2xl">
                    <CategorySelector selected={category} onSelect={handleCategoryChange} disabled={isLoading} />
                  </div>
                </div>

                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-32">
                  {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center min-h-[50vh] pt-8 md:pt-16 animate-in fade-in duration-700">

                      {/* Section Header */}
                      <div className="text-center mb-10">
                        <h2 className="text-[28px] md:text-[34px] font-bold text-[#1D1D1F] tracking-tight mb-3">
                          เลือกหมวดหมู่
                        </h2>
                        <p className="text-[15px] md:text-[17px] text-[#86868B] font-medium">
                          คลิกหมวดหมู่หรือคำถามแนะนำเพื่อเริ่มสนทนา
                        </p>
                      </div>

                      {/* 3 Category Cards - Apple Style Grid */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-5xl">

                        {/* General Card */}
                        <div className="flex flex-col">
                          <button
                            onClick={() => handleCategoryChange(Category.General)}
                            className="group p-6 rounded-[28px] bg-white/70 backdrop-blur-xl border border-white/80 shadow-[0_2px_20px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_40px_rgba(0,122,255,0.12)] hover:-translate-y-0.5 transition-all duration-300 text-left mb-4"
                          >
                            <div className="w-12 h-12 rounded-2xl bg-[#007AFF]/10 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform duration-300">
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="#007AFF" className="w-6 h-6">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
                              </svg>
                            </div>
                            <h3 className="font-semibold text-[19px] text-[#1D1D1F] mb-1.5 tracking-tight">ถามทั่วไป</h3>
                            <p className="text-[13px] text-[#86868B] leading-relaxed">สอบถามข้อมูลทั่วไปเกี่ยวกับการศึกษา</p>
                          </button>
                          <div className="flex flex-col gap-2.5">
                            {COMMON_QUERIES[Category.General].slice(0, 2).map((q, idx) => (
                              <button
                                key={idx}
                                onClick={() => { setCategory(Category.General); handleSendMessage(q, null); }}
                                className="text-left px-4 py-3 rounded-2xl bg-[#007AFF]/5 hover:bg-[#007AFF]/10 border border-[#007AFF]/10 text-[13px] font-medium text-[#007AFF] hover:text-[#0056b3] transition-all duration-200 line-clamp-2"
                              >
                                {q}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* School Card */}
                        <div className="flex flex-col">
                          <button
                            onClick={() => handleCategoryChange(Category.School)}
                            className="group p-6 rounded-[28px] bg-white/70 backdrop-blur-xl border border-white/80 shadow-[0_2px_20px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_40px_rgba(255,149,0,0.12)] hover:-translate-y-0.5 transition-all duration-300 text-left mb-4"
                          >
                            <div className="w-12 h-12 rounded-2xl bg-[#FF9500]/10 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform duration-300">
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="#FF9500" className="w-6 h-6">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0 0 12 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75Z" />
                              </svg>
                            </div>
                            <h3 className="font-semibold text-[19px] text-[#1D1D1F] mb-1.5 tracking-tight">ค้นหาโรงเรียน</h3>
                            <p className="text-[13px] text-[#86868B] leading-relaxed">ค้นหาข้อมูลโรงเรียนทั่วประเทศ</p>
                          </button>
                          <div className="flex flex-col gap-2.5">
                            {COMMON_QUERIES[Category.School].slice(0, 2).map((q, idx) => (
                              <button
                                key={idx}
                                onClick={() => { setCategory(Category.School); handleSendMessage(q, null); }}
                                className="text-left px-4 py-3 rounded-2xl bg-[#FF9500]/5 hover:bg-[#FF9500]/10 border border-[#FF9500]/10 text-[13px] font-medium text-[#FF9500] hover:text-[#cc7700] transition-all duration-200 line-clamp-2"
                              >
                                {q}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Stats Card */}
                        <div className="flex flex-col">
                          <button
                            onClick={() => handleCategoryChange(Category.Student)}
                            className="group p-6 rounded-[28px] bg-white/70 backdrop-blur-xl border border-white/80 shadow-[0_2px_20px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_40px_rgba(175,82,222,0.12)] hover:-translate-y-0.5 transition-all duration-300 text-left mb-4"
                          >
                            <div className="w-12 h-12 rounded-2xl bg-[#AF52DE]/10 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform duration-300">
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="#AF52DE" className="w-6 h-6">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
                              </svg>
                            </div>
                            <h3 className="font-semibold text-[19px] text-[#1D1D1F] mb-1.5 tracking-tight">สถิติการศึกษา</h3>
                            <p className="text-[13px] text-[#86868B] leading-relaxed">ดูสถิติและข้อมูลเชิงตัวเลข</p>
                          </button>
                          <div className="flex flex-col gap-2.5">
                            {COMMON_QUERIES[Category.Student].slice(0, 2).map((q, idx) => (
                              <button
                                key={idx}
                                onClick={() => { setCategory(Category.Student); handleSendMessage(q, null); }}
                                className="text-left px-4 py-3 rounded-2xl bg-[#AF52DE]/5 hover:bg-[#AF52DE]/10 border border-[#AF52DE]/10 text-[13px] font-medium text-[#AF52DE] hover:text-[#8b41b2] transition-all duration-200 line-clamp-2"
                              >
                                {q}
                              </button>
                            ))}
                          </div>
                        </div>

                      </div>
                    </div>
                  )}

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
                        sessionId={currentChatId}
                        category={category.toLowerCase() as 'general' | 'school' | 'student'}
                      />
                    );
                  })}
                  <div ref={messagesEndRef} className="h-4" />
                </div>
              </div>

              {/* Input Area - Clean Floating */}
              <div className="absolute bottom-0 left-0 right-0 p-3 sm:p-6 z-20 pointer-events-none">
                <div className="pointer-events-auto max-w-4xl mx-auto">
                  <ChatInput
                    onSend={handleSendMessage}
                    disabled={isLoading}
                    isLoading={isLoading}
                    onStop={() => {
                      abortCurrentStream();
                      setIsLoading(false);
                    }}
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
      <div className="relative w-full h-[100dvh] overflow-hidden bg-[#F2F2F7]">
        {previousView && renderViewContent(previousView, true)}
        {renderViewContent(view, false)}
      </div>
    );
  };

  return (
    <>
      {renderContainer()}
      {showAdminLogin && (
        <AdminLogin
          onSuccess={() => {
            setShowAdminLogin(false);
            setIsAdminAuthenticated(true);
            setShowAdminPanel(true);
          }}
          onCancel={() => setShowAdminLogin(false)}
        />
      )}
      {showAdminPanel && isAdminAuthenticated && (
        <AdminPanel
          onClose={() => {
            setShowAdminPanel(false);
            // NOTE: We do NOT reset isAdminAuthenticated here
            // so the admin can continue to see RAG debug info in the chat.
          }}
        />
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
