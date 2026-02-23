import { useState, useRef, useEffect, useCallback } from 'react';

export const useSpeechSynthesis = (isTalkMode: boolean, selectedVoiceUri: string) => {
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [speechUnlocked,
        setSpeechUnlocked] = useState(false);
    const [speechError, setSpeechError] = useState('');
    const [voicesReady, setVoicesReady] = useState(false);
    const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);

    const speechUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
    const speakTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
    const resumeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const isTalkModeRef = useRef<boolean>(isTalkMode);

    useEffect(() => {
        isTalkModeRef.current = isTalkMode;
    }, [isTalkMode]);

    useEffect(() => {
        if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
        const synth = window.speechSynthesis;
        const updateVoices = () => {
            const voices = synth.getVoices();
            if (voices.length > 0) {
                setVoicesReady(true);
                setAvailableVoices(voices);
            }
        };
        updateVoices();
        synth.onvoiceschanged = updateVoices;
        return () => { synth.onvoiceschanged = null; };
    }, []);

    const getPreferredVoice = useCallback((): SpeechSynthesisVoice | null => {
        if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null;
        const voices = window.speechSynthesis.getVoices();
        if (selectedVoiceUri) {
            const chosen = voices.find(v => v.voiceURI === selectedVoiceUri);
            if (chosen) return chosen;
        }
        const thaiVoices = voices.filter(v => v.lang?.toLowerCase().startsWith('th'));
        const thaiMale = thaiVoices.find(v => /male|niwat|prem/i.test(v.name) && !/female/i.test(v.name));
        if (thaiMale) return thaiMale;
        if (thaiVoices.length > 0) return thaiVoices[0];
        return voices.find(v => v.lang?.toLowerCase().startsWith('en')) || null;
    }, [selectedVoiceUri]);

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

    const stopSpeaking = useCallback(() => {
        if (ttsAudioRef.current) {
            ttsAudioRef.current.pause();
            ttsAudioRef.current.currentTime = 0;
            ttsAudioRef.current = null;
        }
        try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
        if (speakTimerRef.current) {
            clearTimeout(speakTimerRef.current);
            speakTimerRef.current = null;
        }
        setIsSpeaking(false);
    }, []);

    const playTestBeep = useCallback(() => {
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
            osc.onended = () => { ctx.close().catch(() => undefined); };
        } catch { /* ignore */ }
    }, []);

    const unlockSpeech = useCallback(() => {
        if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
        try {
            window.speechSynthesis.cancel();
            window.speechSynthesis.resume();
            setSpeechUnlocked(true);
            setSpeechError('');
            setTimeout(() => {
                const voices = window.speechSynthesis.getVoices();
                if (!voices || voices.length === 0) setSpeechError('ไม่พบเสียงในระบบ');
            }, 300);
        } catch (e) {
            console.error('[TTS] Unlock failed:', e);
        }
    }, []);

    const primeSpeech = useCallback(() => {
        if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
        try {
            const u = new SpeechSynthesisUtterance(' ');
            u.volume = 0;
            window.speechSynthesis.speak(u);
        } catch { /* ignore */ }
    }, []);

    const stopResumeWorkaround = useCallback(() => {
        if (resumeIntervalRef.current) {
            clearInterval(resumeIntervalRef.current);
            resumeIntervalRef.current = null;
        }
    }, []);

    const startResumeWorkaround = useCallback(() => {
        stopResumeWorkaround();
        resumeIntervalRef.current = setInterval(() => {
            if (window.speechSynthesis?.speaking) {
                window.speechSynthesis.resume();
            }
        }, 5000);
    }, [stopResumeWorkaround]);

    const speakText = useCallback((text: string, forceTTSUrl: string | null = null): boolean => {
        if (!isTalkMode || typeof window === 'undefined') return false;
        stopSpeaking();
        const cleanedText = stripForSpeech(text);
        if (!cleanedText) return false;

        if (forceTTSUrl) {
            const audio = new Audio(forceTTSUrl);
            ttsAudioRef.current = audio;
            setIsSpeaking(true);
            audio.onplay = () => setIsSpeaking(true);
            audio.onended = () => {
                setIsSpeaking(false);
                ttsAudioRef.current = null;
            };
            audio.onerror = () => setIsSpeaking(false);
            audio.play().catch(e => {
                console.warn('Audio play failed', e);
                setIsSpeaking(false);
            });
            return true;
        }

        if (!('speechSynthesis' in window)) return false;
        try {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(cleanedText);
            const voice = getPreferredVoice();
            if (voice) {
                utterance.voice = voice;
                utterance.lang = voice.lang || 'th-TH';
            }
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;

            utterance.onstart = () => { setIsSpeaking(true); startResumeWorkaround(); };
            utterance.onend = () => { setIsSpeaking(false); stopResumeWorkaround(); };
            utterance.onerror = (e) => {
                if (e.error !== 'interrupted') {
                    console.error('Speech error:', e);
                }
                setIsSpeaking(false);
                stopResumeWorkaround();
            };

            speechUtteranceRef.current = utterance;
            speakTimerRef.current = setTimeout(() => {
                window.speechSynthesis.speak(utterance);
            }, 50);
            return true;
        } catch (e) {
            console.error('Speech throw:', e);
            setIsSpeaking(false);
            return false;
        }
    }, [isTalkMode, getPreferredVoice, stopSpeaking, startResumeWorkaround, stopResumeWorkaround]);

    return {
        isSpeaking,
        setIsSpeaking,
        speechUnlocked,
        setSpeechUnlocked,
        speechError,
        setSpeechError,
        voicesReady,
        availableVoices,
        speakText,
        stopSpeaking,
        unlockSpeech,
        primeSpeech,
        playTestBeep,
        stripForSpeech,
        ttsAudioRef,
        isTalkModeRef
    };
};
