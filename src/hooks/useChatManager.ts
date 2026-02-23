import { useState, useRef, useEffect } from 'react';
import { Message, ChatSession, Category, User } from '../types';
import { chatService } from '../services/chatService';
import * as geminiService from '../services/geminiService';
import { useAdminConfig } from '../contexts/AdminConfigContext';

export const generateId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substring(2);
};

interface UseChatManagerProps {
    user: User | null;
    firebaseUserId: string | null;
    firebaseUserEmail: string | null;
    isTalkModeRef: React.MutableRefObject<boolean>;
    speakText: (text: string) => boolean;
    stopSpeaking: () => void;
    setAutoListenSignal: React.Dispatch<React.SetStateAction<number>>;
}

export const useChatManager = ({
    user,
    firebaseUserId,
    firebaseUserEmail,
    isTalkModeRef,
    speakText,
    stopSpeaking,
    setAutoListenSignal
}: UseChatManagerProps) => {
    const { config, getSystemInstruction } = useAdminConfig();

    const [category, setCategory] = useState<Category>(() => {
        if (typeof window === 'undefined') return Category.General;
        return (localStorage.getItem('current_category') as Category) || Category.General;
    });

    const [messages, setMessages] = useState<Message[]>(() => {
        if (typeof window === 'undefined') return [];
        const saved = localStorage.getItem('current_messages');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                return parsed.map((m: any) => ({ ...m, isHistory: true }));
            } catch (e) {
                return [];
            }
        }
        return [];
    });

    const [currentChatId, setCurrentChatId] = useState<string>(() => {
        if (typeof window === 'undefined') return generateId();
        return localStorage.getItem('current_chat_id') || generateId();
    });

    const [isLoading, setIsLoading] = useState(false);
    const [pastChats, setPastChats] = useState<ChatSession[]>([]);
    const pendingMessageRef = useRef<string | null>(null);

    // Persist State
    useEffect(() => {
        localStorage.setItem('current_category', category);
        localStorage.setItem('current_messages', JSON.stringify(messages));
        localStorage.setItem('current_chat_id', currentChatId);
    }, [category, messages, currentChatId]);

    // Load past chats from Firestore when user is available
    useEffect(() => {
        if (firebaseUserId) {
            chatService.getUserSessions(firebaseUserId)
                .then(sessions => {
                    if (sessions.length > 0) {
                        setPastChats(sessions);
                    }
                })
                .catch(err => console.error('[chatService] Load sessions failed:', err));
        }
    }, [firebaseUserId]);

    const resetChatSessionSafe = () => {
        try {
            geminiService.resetChatSession();
        } catch (error) {
            console.error('[Gemini] resetChatSession failed:', error);
        }
    };

    const abortCurrentStreamSafe = () => {
        try {
            geminiService.abortCurrentStream();
        } catch (error) {
            console.error('[Gemini] abortCurrentStream failed:', error);
        }
    };

    const handleNewChat = () => {
        resetChatSessionSafe();
        setCurrentChatId(generateId());
        setCategory(Category.General);
        setMessages([]);
    };

    const handleDeleteChat = async (session: ChatSession) => {
        if (!firebaseUserId) return;
        const confirmed = window.confirm(`ลบประวัติการสนทนา "${session.title}" ใช่หรือไม่?`);
        if (!confirmed) return;

        try {
            await chatService.deleteSession(session.sessionId, firebaseUserId);
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

        const cloudMessages = await chatService.getSessionMessages(session.sessionId, session.userId);
        if (cloudMessages.length > 0) {
            setMessages(cloudMessages.map(m => ({ ...m, isHistory: true })));
        } else {
            setMessages([]);
        }
        setIsLoading(false);
    };

    const categoryStatesRef = useRef<Record<string, { messages: Message[], chatId: string }>>({});

    const handleCategoryChange = (newCategory: Category) => {
        if (newCategory !== category) {
            categoryStatesRef.current[category] = { messages, chatId: currentChatId };
            setCategory(newCategory);

            const savedState = categoryStatesRef.current[newCategory];

            if (savedState && savedState.messages.length > 0) {
                setMessages(savedState.messages.map(m => ({ ...m, isHistory: true })));
                setCurrentChatId(savedState.chatId);
            } else {
                resetChatSessionSafe();
                setCurrentChatId(generateId());

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
        if (initialMessage) {
            setMessages([]);
            setCurrentChatId(generateId());
            resetChatSessionSafe();
            pendingMessageRef.current = initialMessage;
        }
        if (initialCategory) setCategory(initialCategory);
    };

    // Auto-send pending message from landing page when chat view mounts
    useEffect(() => {
        if (pendingMessageRef.current && !isLoading) {
            const msg = pendingMessageRef.current;
            pendingMessageRef.current = null;
            // Small delay to ensure chat view is mounted
            const timer = setTimeout(() => handleSendMessage(msg, null), 150);
            return () => clearTimeout(timer);
        }
    }, [messages]); // triggers when messages state updates (after handleStart resets)

    const resetAll = () => {
        setMessages([]);
        setPastChats([]);
        setCategory(Category.General);
        setCurrentChatId(generateId());
    };

    const formattedHistory = messages
        .slice(-10)
        .filter(m => !m.isError && m.content)
        .map(m => ({ role: m.role, parts: [{ text: m.content }] }));

    const handleSendMessage = async (text: string, imageData: string | null) => {
        stopSpeaking();
        const userMessageId = generateId();
        const modelMessageId = generateId();
        const userMessage: Message = { id: userMessageId, role: 'user', content: text || "[รูปภาพ]", timestamp: new Date() };

        setMessages(prev => [...prev, userMessage, { id: modelMessageId, role: 'model', content: '', timestamp: new Date() }]);
        setIsLoading(true);

        chatService.logMessage({
            sessionId: currentChatId,
            userId: firebaseUserId,
            userName: user?.name || null,
            userEmail: firebaseUserEmail,
            role: 'user',
            content: text || "[รูปภาพ]",
            category: category,
            modelName: config.model.name,
        }).catch(err => console.error('[chatService] User log error:', err));

        const isFirstUserMessage = messages.filter(m => m.role === 'user').length === 0;
        const sessionTitle = isFirstUserMessage ? (text.length > 30 ? text.substring(0, 30) + '...' : text) : undefined;

        const sessionUpdate: ChatSession = {
            sessionId: currentChatId,
            userId: firebaseUserId || '',
            category: category,
            title: sessionTitle || 'New Chat'
        };
        if (sessionTitle) {
            sessionUpdate.title = sessionTitle;
            setPastChats(prev => [
                {
                    sessionId: currentChatId,
                    userId: firebaseUserId || '',
                    title: sessionTitle || (prev.find(s => s.sessionId === currentChatId)?.title || text),
                    category: category,
                    updatedAt: new Date()
                },
                ...prev.filter(s => s.sessionId !== currentChatId)
            ]);
        }

        chatService.saveSession(sessionUpdate).catch(err => console.error('[chatService] Session save error:', err));

        try {
            let fullContent = '';
            const systemInstruction = getSystemInstruction(category);
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

            const stableSessionId = firebaseUserId ? `${firebaseUserId}_${currentChatId}` : `guest_${currentChatId}`;

            await geminiService.sendMessageStream(
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
                    setMessages(prev => prev.map(m => m.id === modelMessageId ? { ...m, ragDebugInfo: debugInfo } : m));
                }
            );

            if (rafId !== null) cancelAnimationFrame(rafId);

            const ragDebugInfo = geminiService.getLastRagDebugInfo();
            setMessages(prev => prev.map(m => m.id === modelMessageId ? { ...m, content: fullContent, ragDebugInfo } : m));

            if (isTalkModeRef.current) {
                const spoke = speakText(fullContent);
                if (!spoke) {
                    setTimeout(() => setAutoListenSignal(s => s + 1), 350);
                }
            }

            await chatService.logMessage({
                sessionId: currentChatId,
                userId: firebaseUserId,
                userName: user?.name || null,
                userEmail: firebaseUserEmail,
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
                    chatService.logMessage({
                        sessionId: currentChatId,
                        userId: firebaseUserId,
                        userName: user?.name || null,
                        userEmail: firebaseUserEmail,
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

    const handleRegenerate = () => {
        const lastUserMessageIndex = messages.map((m, i) => ({ ...m, idx: i })).filter(m => m.role === 'user').pop()?.idx;
        if (lastUserMessageIndex === undefined) return;
        const lastUserMessage = messages[lastUserMessageIndex];
        setMessages(prev => prev.slice(0, prev.length - 1));
        handleSendMessage(lastUserMessage.content, null);
    };

    const handleEditMessage = (messageId: string, newContent: string) => {
        const messageIndex = messages.findIndex(m => m.id === messageId);
        if (messageIndex === -1) return;
        setMessages(prev => prev.slice(0, messageIndex));
        handleSendMessage(newContent, null);
    };

    return {
        category,
        setCategory,
        messages,
        setMessages,
        currentChatId,
        setCurrentChatId,
        isLoading,
        pastChats,
        setPastChats,
        handleNewChat,
        handleDeleteChat,
        loadPastChat,
        handleCategoryChange,
        handleSendMessage,
        handleRegenerate,
        handleEditMessage,
        resetChatSessionSafe,
        abortCurrentStreamSafe,
        onStopAI: abortCurrentStreamSafe,
        resetAll,
        handleStart
    };
};
