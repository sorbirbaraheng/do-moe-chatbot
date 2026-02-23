
import React, { useState, useEffect } from 'react';
import { AdminConfig } from '../../../contexts/AdminConfigContext';
import { getAdminToken } from '../../../services/adminAuth';

interface SessionMonitorTabProps {
    config: AdminConfig;
}

interface Session {
    id: string;
    updated_at: number;
    province?: string;
    agency?: string;
    last_query?: string;
}

export const SessionMonitorTab: React.FC<SessionMonitorTabProps> = ({ config }) => {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [autoRefresh, setAutoRefresh] = useState(false);

    const fetchSessions = async () => {
        setIsLoading(true);
        setError('');
        try {
            const currentPort = window.location.port;
            // Use relative URL on Docker nginx (port 3001/80) — nginx proxies /api/ to backend
            const baseUrl = (currentPort === '3001' || currentPort === '80' || currentPort === '')
                ? ''
                : (config.apiKeys?.school?.flaskApiUrl || 'http://127.0.0.1:5001').replace(/\/$/, '');

            console.log('[SessionMonitor] Fetching from:', baseUrl);
            const token = getAdminToken() || '';
            const res = await fetch(`${baseUrl}/api/sessions?limit=50`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();

            if (data.success) {
                setSessions(data.sessions);
            } else {
                setError(data.error || 'Failed to fetch sessions');
            }
        } catch (err: any) {
            setError(err.message || 'Connection Error');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, []);

    useEffect(() => {
        let interval: any;
        if (autoRefresh) {
            interval = setInterval(fetchSessions, 5000);
        }
        return () => clearInterval(interval);
    }, [autoRefresh]);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold">Session Monitor</h2>
                    <p className="text-sm text-gray-500">View active conversations stored in SQLite</p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${autoRefresh ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}
                    >
                        <span className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></span>
                        {autoRefresh ? 'Auto Refresh ON' : 'Auto Refresh OFF'}
                    </button>
                    <button
                        onClick={fetchSessions}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-all flex items-center gap-2"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                        </svg>
                        Refresh
                    </button>
                </div>
            </div>

            {error && (
                <div className="p-4 bg-red-50 text-red-600 rounded-xl border border-red-100 text-sm">
                    ⚠️ {error}
                </div>
            )}

            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-gray-50 border-b border-gray-100 text-xs uppercase text-gray-500 tracking-wider">
                            <th className="px-6 py-4 font-semibold">Session ID</th>
                            <th className="px-6 py-4 font-semibold">Updated</th>
                            <th className="px-6 py-4 font-semibold">Context (Province/Agency)</th>
                            <th className="px-6 py-4 font-semibold">Last Query</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {sessions.length === 0 ? (
                            <tr>
                                <td colSpan={4} className="px-6 py-8 text-center text-gray-400 text-sm">
                                    No active sessions found
                                </td>
                            </tr>
                        ) : (
                            sessions.map((session) => (
                                <tr key={session.id} className="hover:bg-blue-50/50 transition-colors">
                                    <td className="px-6 py-4">
                                        <div className="font-mono text-xs bg-gray-100 px-2 py-1 rounded w-fit text-gray-600">
                                            {session.id.substring(0, 12)}...
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-600">
                                        {new Date(session.updated_at * 1000).toLocaleString('th-TH')}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex gap-2">
                                            {session.province && (
                                                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold">
                                                    📍 {session.province}
                                                </span>
                                            )}
                                            {session.agency && (
                                                <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-semibold">
                                                    🏛️ {session.agency}
                                                </span>
                                            )}
                                            {!session.province && !session.agency && (
                                                <span className="text-gray-400 text-xs">-</span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-800 max-w-xs truncate">
                                        {session.last_query || '-'}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
