import { useState, useEffect } from 'react';

export type View = 'home' | 'chat' | 'login';

export const useAppNavigation = () => {
    const [view, setView] = useState<View>(() => {
        if (typeof window === 'undefined') return 'home';
        const saved = localStorage.getItem('current_view');
        return (saved === 'home' || saved === 'login' || saved === 'chat') ? saved as View : 'home';
    });

    const [activeView, setActiveView] = useState<View>(view);
    const [previousView, setPreviousView] = useState<View | null>(null);

    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem('current_view', view);
        }
    }, [view]);

    const navigateTo = (nextView: View) => {
        if (nextView === activeView) return;

        setPreviousView(activeView);
        setActiveView(nextView);
        setView(nextView);

        setTimeout(() => {
            setPreviousView(null);
        }, 800);
    };

    return {
        view,
        activeView,
        previousView,
        navigateTo
    };
};
