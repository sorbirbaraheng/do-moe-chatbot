import React, { useState, useEffect } from 'react';
import { db } from '../../../services/firebase';
import { collection, getDocs, query, orderBy, limit, where, Timestamp } from 'firebase/firestore';

interface AnalyticsData {
    totalMessages: number;
    totalSessions: number;
    totalUsers: number;
    messagesByCategory: { [key: string]: number };
    recentActivity: Array<{
        id: string;
        content: string;
        role: string;
        category: string;
        timestamp: Date;
        userName?: string;
    }>;
    messagesLast7Days: { [key: string]: number };
}

const AnalyticsTab: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [analytics, setAnalytics] = useState<AnalyticsData>({
        totalMessages: 0,
        totalSessions: 0,
        totalUsers: 0,
        messagesByCategory: {},
        recentActivity: [],
        messagesLast7Days: {}
    });

    useEffect(() => {
        fetchAnalytics();
    }, []);

    const fetchAnalytics = async () => {
        setLoading(true);
        try {
            // Fetch chat logs
            const logsQuery = query(
                collection(db, 'chat_logs'),
                orderBy('timestamp', 'desc'),
                limit(500)
            );
            const logsSnapshot = await getDocs(logsQuery);

            // Process logs
            const logs = logsSnapshot.docs.map(doc => ({
                id: doc.id,
                ...doc.data()
            }));

            // Count metrics
            const totalMessages = logs.length;
            const uniqueUsers = new Set(logs.map((l: any) => l.userId).filter(Boolean));
            const uniqueSessions = new Set(logs.map((l: any) => l.sessionId).filter(Boolean));

            // Messages by category
            const byCategory: { [key: string]: number } = {};
            logs.forEach((log: any) => {
                const cat = log.category || 'unknown';
                byCategory[cat] = (byCategory[cat] || 0) + 1;
            });

            // Messages last 7 days
            const last7Days: { [key: string]: number } = {};
            const now = new Date();
            for (let i = 6; i >= 0; i--) {
                const date = new Date(now);
                date.setDate(date.getDate() - i);
                const key = date.toLocaleDateString('th-TH', { day: 'numeric', month: 'short' });
                last7Days[key] = 0;
            }

            logs.forEach((log: any) => {
                const ts = log.timestamp?.toDate?.() || new Date(log.createdAt);
                if (ts) {
                    const key = ts.toLocaleDateString('th-TH', { day: 'numeric', month: 'short' });
                    if (last7Days[key] !== undefined) {
                        last7Days[key]++;
                    }
                }
            });

            // Recent activity (user messages only)
            const recentActivity = logs
                .filter((l: any) => l.role === 'user' && l.content)
                .slice(0, 10)
                .map((l: any) => ({
                    id: l.id,
                    content: l.content?.substring(0, 100) + (l.content?.length > 100 ? '...' : ''),
                    role: l.role,
                    category: l.category || 'general',
                    timestamp: l.timestamp?.toDate?.() || new Date(l.createdAt),
                    userName: l.userName || 'Guest'
                }));

            setAnalytics({
                totalMessages,
                totalSessions: uniqueSessions.size,
                totalUsers: uniqueUsers.size,
                messagesByCategory: byCategory,
                recentActivity,
                messagesLast7Days: last7Days
            });
        } catch (error) {
            console.error('Failed to fetch analytics:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatTimeAgo = (date: Date) => {
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'เมื่อกี้';
        if (diffMins < 60) return `${diffMins} นาทีที่แล้ว`;
        if (diffHours < 24) return `${diffHours} ชม.ที่แล้ว`;
        return `${diffDays} วันที่แล้ว`;
    };

    const getCategoryColor = (category: string) => {
        const colors: { [key: string]: string } = {
            school: 'bg-blue-100 text-blue-700',
            student: 'bg-purple-100 text-purple-700',
            general: 'bg-green-100 text-green-700',
            unknown: 'bg-gray-100 text-gray-700'
        };
        return colors[category] || colors.unknown;
    };

    const getCategoryLabel = (category: string) => {
        const labels: { [key: string]: string } = {
            school: '🏫 โรงเรียน',
            student: '👨‍🎓 นักเรียน',
            general: '💬 ทั่วไป',
            unknown: '❓ อื่นๆ'
        };
        return labels[category] || category;
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                <span className="ml-3 text-gray-500">กำลังโหลดข้อมูล...</span>
            </div>
        );
    }

    const maxDayValue = Math.max(...Object.values(analytics.messagesLast7Days), 1);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-gray-800">📊 Analytics Dashboard</h2>
                    <p className="text-sm text-gray-500 mt-1">สถิติการใช้งานจาก Firestore</p>
                </div>
                <button
                    onClick={fetchAnalytics}
                    className="px-4 py-2 bg-blue-50 text-blue-600 rounded-xl font-medium hover:bg-blue-100 transition-colors flex items-center gap-2"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                    </svg>
                    รีเฟรช
                </button>
            </div>

            {/* Overview Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl p-4 text-white shadow-lg shadow-blue-200">
                    <div className="text-3xl font-black">{analytics.totalMessages.toLocaleString()}</div>
                    <div className="text-sm opacity-80 font-medium mt-1">💬 ข้อความทั้งหมด</div>
                </div>
                <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl p-4 text-white shadow-lg shadow-purple-200">
                    <div className="text-3xl font-black">{analytics.totalSessions.toLocaleString()}</div>
                    <div className="text-sm opacity-80 font-medium mt-1">📁 Sessions</div>
                </div>
                <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-2xl p-4 text-white shadow-lg shadow-green-200">
                    <div className="text-3xl font-black">{analytics.totalUsers.toLocaleString()}</div>
                    <div className="text-sm opacity-80 font-medium mt-1">👤 ผู้ใช้</div>
                </div>
                <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl p-4 text-white shadow-lg shadow-orange-200">
                    <div className="text-3xl font-black">
                        {analytics.totalMessages > 0
                            ? Math.round((analytics.messagesByCategory['school'] || 0) / analytics.totalMessages * 100)
                            : 0}%
                    </div>
                    <div className="text-sm opacity-80 font-medium mt-1">🏫 ถามโรงเรียน</div>
                </div>
            </div>

            {/* Charts Row */}
            <div className="grid md:grid-cols-2 gap-6">
                {/* Messages by Day */}
                <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
                    <h3 className="font-bold text-gray-800 mb-4">📈 ข้อความ 7 วันล่าสุด</h3>
                    <div className="flex items-end gap-2 h-32">
                        {Object.entries(analytics.messagesLast7Days).map(([day, count]) => (
                            <div key={day} className="flex-1 flex flex-col items-center">
                                <div
                                    className="w-full bg-blue-500 rounded-t-lg transition-all hover:bg-blue-600"
                                    style={{ height: `${(count / maxDayValue) * 100}%`, minHeight: count > 0 ? '8px' : '2px' }}
                                    title={`${count} ข้อความ`}
                                ></div>
                                <div className="text-[10px] text-gray-500 mt-2 font-medium">{day}</div>
                                <div className="text-[11px] font-bold text-gray-700">{count}</div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Messages by Category */}
                <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
                    <h3 className="font-bold text-gray-800 mb-4">🗂️ แยกตามหมวดหมู่</h3>
                    <div className="space-y-3">
                        {Object.entries(analytics.messagesByCategory)
                            .sort((a, b) => b[1] - a[1])
                            .map(([category, count]) => {
                                const percentage = Math.round((count / analytics.totalMessages) * 100);
                                return (
                                    <div key={category} className="flex items-center gap-3">
                                        <span className={`px-2 py-1 rounded-lg text-xs font-bold ${getCategoryColor(category)}`}>
                                            {getCategoryLabel(category)}
                                        </span>
                                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-blue-500 rounded-full transition-all"
                                                style={{ width: `${percentage}%` }}
                                            ></div>
                                        </div>
                                        <span className="text-sm font-bold text-gray-600 w-16 text-right">
                                            {count} ({percentage}%)
                                        </span>
                                    </div>
                                );
                            })}
                    </div>
                </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
                <h3 className="font-bold text-gray-800 mb-4">🕐 กิจกรรมล่าสุด</h3>
                {analytics.recentActivity.length === 0 ? (
                    <div className="text-center py-8 text-gray-400">
                        <div className="text-4xl mb-2">📭</div>
                        ยังไม่มีข้อความ
                    </div>
                ) : (
                    <div className="space-y-3 max-h-80 overflow-y-auto">
                        {analytics.recentActivity.map((activity) => (
                            <div key={activity.id} className="flex items-start gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors">
                                <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-sm">
                                    👤
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium text-gray-800 text-sm">{activity.userName}</span>
                                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCategoryColor(activity.category)}`}>
                                            {getCategoryLabel(activity.category)}
                                        </span>
                                    </div>
                                    <p className="text-gray-600 text-sm mt-1 truncate">{activity.content}</p>
                                    <span className="text-xs text-gray-400 mt-1 block">
                                        {formatTimeAgo(activity.timestamp)}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AnalyticsTab;
