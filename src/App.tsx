/**
 * 📄 ชื่อไฟล์: App.tsx
 * 📝 คำอธิบาย:
 *    Refactored Main Component (Composition Root)
 *    Delegates state to `useChatManager` and routing to `useAppNavigation`
 *    and rendering to `ChatView` and `LandingPage`
 */

import React, { useState, useEffect, lazy, Suspense } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { AdminConfigProvider, useAdminConfig } from './contexts/AdminConfigContext';
import { getAdminToken } from './services/adminAuth';
import { useChatManager } from './hooks/useChatManager';
import { useAppNavigation } from './hooks/useAppNavigation';
import { useSpeechSynthesis } from './hooks/useSpeechSynthesis';
import ChatView from './components/chat/ChatView';

// Lazy loaded views
const LandingPage = lazy(() => import('./components/pages/LandingPage'));
const LoginPage = lazy(() => import('./components/pages/LoginPage'));
const AdminPanel = lazy(() => import('./components/admin/AdminPanel'));
const AdminLogin = lazy(() => import('./components/admin/AdminLogin'));

const AppContent: React.FC = () => {
  const { user, userRole, loading: authLoading, logout: firebaseLogout } = useAuth();
  const { config } = useAdminConfig();

  const { view, activeView, previousView, navigateTo } = useAppNavigation();

  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);
  const [showAdminLogin, setShowAdminLogin] = useState(false);
  const [showAdminPanel, setShowAdminPanel] = useState(false);

  // Speech and Talk Mode Management
  const [isTalkMode, setIsTalkMode] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('talk_mode') === 'true';
  });

  const [speechMuted, setSpeechMuted] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('speech_muted') === 'true';
  });

  const [selectedVoiceUri, setSelectedVoiceUri] = useState<string>(() => {
    if (typeof window === 'undefined') return '';
    return localStorage.getItem('speech_voice_uri') || '';
  });

  const speech = useSpeechSynthesis(isTalkMode, selectedVoiceUri);

  // Chat Manager (handles messages, category, loading, actions)
  const mappedUser = user ? {
    name: user.displayName || user.email?.split('@')[0] || 'User',
    email: user.email || '',
    role: userRole || 'user',
    initials: (user.displayName || user.email?.split('@')[0] || 'U').charAt(0).toUpperCase(),
    avatar: user.photoURL || undefined
  } : null;

  const chatManager = useChatManager({
    user: mappedUser,
    firebaseUserId: user?.email || null,
    firebaseUserEmail: user?.email || null,
    isTalkModeRef: speech.isTalkModeRef,
    speakText: speech.speakText,
    stopSpeaking: speech.stopSpeaking,
    setAutoListenSignal: () => { }
  });

  const [autoListenSignal, setAutoListenSignal] = useState(0);
  const [stopListeningSignal, setStopListeningSignal] = useState(0);
  const [isListening, setIsListening] = useState(false);
  const [micLevel, setMicLevel] = useState(0);

  // Initialize Speech
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('talk_mode', String(isTalkMode));
      localStorage.setItem('speech_muted', String(speechMuted));
      localStorage.setItem('speech_voice_uri', selectedVoiceUri);
    }
  }, [isTalkMode, speechMuted, selectedVoiceUri]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.body.classList.toggle('talk-mode-active', isTalkMode);
    return () => document.body.classList.remove('talk-mode-active');
  }, [isTalkMode]);

  useEffect(() => {
    if (isTalkMode) {
      speech.unlockSpeech();
      speech.primeSpeech();
      setAutoListenSignal(s => s + 1);
    } else {
      setStopListeningSignal(s => s + 1);
      setIsListening(false);
      if (speech.ttsAudioRef.current) {
        speech.ttsAudioRef.current.pause();
        speech.ttsAudioRef.current.currentTime = 0;
        speech.ttsAudioRef.current = null;
      }
      try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
    }
  }, [isTalkMode]);

  // Auth Redirection Logic
  useEffect(() => {
    if (!authLoading) {
      if (user && view === 'login') {
        navigateTo('chat');
      } else if (!user && view === 'chat') {
        navigateTo('home');
      }
    }
  }, [user, authLoading, view]);

  useEffect(() => {
    const token = getAdminToken();
    if (token) setIsAdminAuthenticated(true);
  }, []);

  const handleLogout = async () => {
    await firebaseLogout();
    chatManager.resetAll();
    setIsAdminAuthenticated(false);
  };

  const renderViewContent = (viewName: 'home' | 'login' | 'chat', isExiting: boolean) => {
    const animationClass = isExiting ? 'fluid-exit z-0 pointer-events-none' : 'fluid-entrance z-10';
    const bgClass = viewName === 'home' ? 'bg-transparent' : 'bg-[#F2F2F7]';
    const commonClasses = `absolute inset-0 w-full h-full ${animationClass} ${bgClass} overflow-hidden`;

    if (viewName === 'home') {
      return (
        <div key="view-home" className={commonClasses}>
          <Suspense fallback={<div className="w-full h-full bg-transparent" />}>
            <LandingPage onStart={(cat, msg) => {
              chatManager.handleStart(cat, msg);
              if (!user) {
                navigateTo('login');
              } else {
                navigateTo('chat');
              }
            }} onAdminLogin={() => {
              if (isAdminAuthenticated) {
                setShowAdminPanel(true);
              } else {
                setShowAdminLogin(true);
              }
            }} onLogout={handleLogout} user={mappedUser} />
          </Suspense>
        </div>
      );
    }

    if (viewName === 'login') {
      return (
        <div key="view-login" className={`${commonClasses} flex items-center justify-center`}>
          <Suspense fallback={<div className="w-full h-full" />}>
            <LoginPage onLogin={() => navigateTo('chat')} onBack={() => navigateTo('home')} />
          </Suspense>
        </div>
      );
    }

    if (viewName === 'chat') {
      return (
        <div key="view-chat" className={`${commonClasses} flex flex-col`}>
          <ChatView
            user={mappedUser}
            messages={chatManager.messages}
            currentChatId={chatManager.currentChatId}
            category={chatManager.category}
            isLoading={chatManager.isLoading}
            isSpeaking={speech.isSpeaking}
            speechUnlocked={speech.speechUnlocked}
            isListening={isListening}
            isTalkMode={isTalkMode}
            micLevel={micLevel}
            speechError={speech.speechError}
            voicesReady={speech.voicesReady}
            availableVoices={speech.availableVoices}
            selectedVoiceUri={selectedVoiceUri}
            speechMuted={speechMuted}
            autoListenSignal={autoListenSignal}
            stopListeningSignal={stopListeningSignal}
            isAdminAuthenticated={isAdminAuthenticated}
            pastChats={chatManager.pastChats}

            onSendMessage={(text, img) => {
              chatManager.handleSendMessage(text, img);
            }}
            onEditMessage={chatManager.handleEditMessage}
            onRegenerate={chatManager.handleRegenerate}
            onStopAI={chatManager.onStopAI}
            onNewChat={chatManager.handleNewChat}
            onLoadChat={chatManager.loadPastChat}
            onDeleteChat={chatManager.handleDeleteChat}
            onLogout={handleLogout}
            onNavigateHome={() => navigateTo('home')}

            setIsTalkMode={setIsTalkMode}
            setSpeechMuted={setSpeechMuted}
            setSelectedVoiceUri={setSelectedVoiceUri}
            unlockSpeech={speech.unlockSpeech}
            primeSpeech={speech.primeSpeech}
            stopSpeaking={speech.stopSpeaking}
            setSpeechUnlocked={speech.setSpeechUnlocked}
            setSpeechError={speech.setSpeechError}
            speakText={speech.speakText}
            playTestBeep={speech.playTestBeep}
            setAutoListenSignal={setAutoListenSignal}
            setStopListeningSignal={setStopListeningSignal}
            setIsListening={setIsListening}
            setMicLevel={setMicLevel}
          />
        </div>
      );
    }
  };

  return (
    <>
      <div className="relative w-full h-[100dvh] overflow-hidden bg-[#EEF0F8]">
        {previousView && renderViewContent(previousView, true)}
        {renderViewContent(view, false)}
      </div>

      {showAdminLogin && !isAdminAuthenticated && (
        <Suspense fallback={null}>
          <AdminLogin
            onSuccess={() => {
              setIsAdminAuthenticated(true);
              setShowAdminLogin(false);
              setShowAdminPanel(true);
            }}
            onCancel={() => setShowAdminLogin(false)}
          />
        </Suspense>
      )}

      {showAdminPanel && isAdminAuthenticated && (
        <Suspense fallback={null}>
          <AdminPanel onClose={() => setShowAdminPanel(false)} onLogout={handleLogout} />
        </Suspense>
      )}
    </>
  );
};

function App() {
  return (
    <AdminConfigProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </AdminConfigProvider>
  );
}

export default App;
