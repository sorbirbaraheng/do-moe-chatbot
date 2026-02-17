/**
 * 📄 VoiceModeOverlay.tsx
 * 📝 Full-screen Voice Mode UI — Siri / ChatGPT Voice style
 *    3 states: Listening → Thinking → Speaking
 *    Shows waveform, orb animation, and transcript
 */
import React, { useMemo } from 'react';

interface VoiceModeOverlayProps {
    isActive: boolean;
    isListening: boolean;
    isLoading: boolean;
    isSpeaking: boolean;
    micLevel: number;
    speechUnlocked: boolean;
    speechError: string;
    speechMuted: boolean;
    lastUserText: string;
    lastAiText: string;
    onClose: () => void;
    onTapToSpeak: () => void;
    onToggleMute: () => void;
    onTestVoice: () => void;
}

const VoiceModeOverlay: React.FC<VoiceModeOverlayProps> = ({
    isActive,
    isListening,
    isLoading,
    isSpeaking,
    micLevel,
    speechUnlocked,
    speechError,
    speechMuted,
    lastUserText,
    lastAiText,
    onClose,
    onTapToSpeak,
    onToggleMute,
    onTestVoice,
}) => {
    // Determine current state
    const state = useMemo(() => {
        if (isListening) return 'listening';
        if (isLoading) return 'thinking';
        if (isSpeaking) return 'speaking';
        return 'idle';
    }, [isListening, isLoading, isSpeaking]);

    // Status text
    const statusText = useMemo(() => {
        if (!speechUnlocked) return 'แตะเพื่อเปิดเสียง';
        switch (state) {
            case 'listening': return 'กำลังฟัง...';
            case 'thinking': return 'น้องดีโอกำลังคิด...';
            case 'speaking': return 'น้องดีโอกำลังพูด...';
            default: return 'แตะเพื่อพูด';
        }
    }, [state, speechUnlocked]);

    // Dynamic orb colors
    const orbGlow = useMemo(() => {
        switch (state) {
            case 'listening': return 'from-[#00C7FF]/50 via-[#007AFF]/40 to-[#5856D6]/30';
            case 'thinking': return 'from-[#34C759]/40 via-[#30D158]/30 to-[#00C7FF]/20';
            case 'speaking': return 'from-[#AF52DE]/50 via-[#5856D6]/40 to-[#007AFF]/30';
            default: return 'from-[#A0A0A0]/25 via-[#C7C7CC]/20 to-transparent';
        }
    }, [state]);

    // Ring amplitude
    const ringAmp = useMemo(() => {
        if (isListening) return micLevel;
        if (isSpeaking) return 0.3;
        if (isLoading) return 0.15;
        return 0.08;
    }, [isListening, isSpeaking, isLoading, micLevel]);

    // Truncate text for display
    const truncate = (text: string, max: number) => {
        if (!text) return '';
        return text.length > max ? text.slice(0, max) + '…' : text;
    };

    if (!isActive) return null;

    return (
        <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center voice-mode-root">
            {/* Full-screen background — completely opaque */}
            <div className="absolute inset-0 voice-mode-bg" />

            {/* Floating blobs */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="talk-blob blob-1" />
                <div className="talk-blob blob-2" />
                <div className="talk-blob blob-3" />
                <div className="absolute inset-0 grain-overlay" />
            </div>

            {/* Vignette */}
            <div className="absolute inset-0 talk-vignette" />

            {/* ────── Main Content ────── */}
            <div className="relative z-10 flex flex-col items-center gap-6 px-6 max-w-md w-full">

                {/* Persona name */}
                <div className="voice-mode-persona animate-in fade-in slide-in-from-top-4 duration-700">
                    <div className="voice-mode-persona-dot" />
                    <span>น้องดีโอ</span>
                </div>

                {/* ── Orb + Waveform ── */}
                <div className="relative flex flex-col items-center gap-3 animate-in fade-in zoom-in-95 duration-500">
                    {/* Ambient glow */}
                    <div className={`absolute -inset-16 rounded-full bg-gradient-to-br ${orbGlow} blur-[90px] transition-all duration-700`} />

                    {/* Orb */}
                    <div
                        className="talk-orb"
                        style={{ ['--level' as any]: isListening ? micLevel : (isSpeaking ? 0.25 : 0.08) }}
                    >
                        <div className="talk-orb-glow" />
                        <div className="talk-orb-core" />
                    </div>

                    {/* Waveform bars */}
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

                    {/* Ring */}
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
                </div>

                {/* Status button */}
                <button
                    type="button"
                    onClick={() => {
                        if (!isListening && !isLoading) {
                            onTapToSpeak();
                        }
                    }}
                    className={`talk-ready-btn ${isListening ? 'talk-ready-disabled' : ''}`}
                    disabled={isListening || isLoading}
                >
                    {statusText}
                </button>

                {/* ── Transcript Area ── */}
                <div className="w-full max-w-sm min-h-[80px] flex flex-col gap-2 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-200">
                    {/* User said */}
                    {lastUserText && (
                        <div className="voice-transcript voice-transcript-user">
                            <span className="voice-transcript-label">คุณ:</span>
                            <span>{truncate(lastUserText, 80)}</span>
                        </div>
                    )}
                    {/* AI said */}
                    {lastAiText && !isLoading && (
                        <div className="voice-transcript voice-transcript-ai">
                            <span className="voice-transcript-label">น้องดีโอ:</span>
                            <span>{truncate(lastAiText, 120)}</span>
                        </div>
                    )}
                    {/* Loading indicator */}
                    {isLoading && (
                        <div className="voice-transcript voice-transcript-ai">
                            <span className="voice-loading-dots">
                                <span /><span /><span />
                            </span>
                        </div>
                    )}
                </div>

                {/* Error display */}
                {speechError && (
                    <div className="text-[11px] font-medium text-red-300/90 text-center">
                        {speechError}
                    </div>
                )}
            </div>

            {/* ────── Bottom Controls ────── */}
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-20 animate-in fade-in slide-in-from-bottom-6 duration-500 delay-300">
                <div className="voice-controls-dock">
                    {/* Mute */}
                    <button
                        type="button"
                        onClick={onToggleMute}
                        className={`voice-dock-btn ${speechMuted ? 'voice-dock-muted' : ''}`}
                        title={speechMuted ? 'เปิดเสียง' : 'ปิดเสียง'}
                    >
                        {speechMuted ? (
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                                <path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.508c-1.141 0-2.318.664-2.66 1.905A9.76 9.76 0 001.5 12c0 .898.121 1.768.35 2.595.341 1.24 1.518 1.905 2.659 1.905h1.93l4.5 4.5c.945.945 2.561.276 2.561-1.06V4.06zM17.78 9.22a.75.75 0 10-1.06 1.06L18.44 12l-1.72 1.72a.75.75 0 001.06 1.06l1.72-1.72 1.72 1.72a.75.75 0 101.06-1.06L20.56 12l1.72-1.72a.75.75 0 00-1.06-1.06l-1.72 1.72-1.72-1.72z" />
                            </svg>
                        ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                                <path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.508c-1.141 0-2.318.664-2.66 1.905A9.76 9.76 0 001.5 12c0 .898.121 1.768.35 2.595.341 1.24 1.518 1.905 2.659 1.905h1.93l4.5 4.5c.945.945 2.561.276 2.561-1.06V4.06zM18.584 5.106a.75.75 0 011.06 0c3.808 3.807 3.808 9.98 0 13.788a.75.75 0 01-1.06-1.06 8.25 8.25 0 000-11.668.75.75 0 010-1.06z" />
                                <path d="M15.932 7.757a.75.75 0 011.061 0 6 6 0 010 8.486.75.75 0 01-1.06-1.061 4.5 4.5 0 000-6.364.75.75 0 010-1.06z" />
                            </svg>
                        )}
                    </button>

                    {/* Test Voice */}
                    <button
                        type="button"
                        onClick={onTestVoice}
                        className="voice-dock-btn"
                        title="ทดสอบเสียง"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                            <path fillRule="evenodd" d="M19.952 1.651a.75.75 0 01.298.599V16.303a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.403-4.909l2.311-.66a1.5 1.5 0 001.088-1.442V6.994l-9 2.572v9.737a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.402-4.909l2.31-.66a1.5 1.5 0 001.088-1.442V5.25a.75.75 0 01.544-.721l10.5-3a.75.75 0 01.658.122z" clipRule="evenodd" />
                        </svg>
                    </button>

                    {/* Close */}
                    <button
                        type="button"
                        onClick={onClose}
                        className="voice-dock-btn voice-dock-close"
                        title="ปิดโหมดเสียง"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                            <path fillRule="evenodd" d="M5.47 5.47a.75.75 0 011.06 0L12 10.94l5.47-5.47a.75.75 0 111.06 1.06L13.06 12l5.47 5.47a.75.75 0 11-1.06 1.06L12 13.06l-5.47 5.47a.75.75 0 01-1.06-1.06L10.94 12 5.47 6.53a.75.75 0 010-1.06z" clipRule="evenodd" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
};

export default React.memo(VoiceModeOverlay);
