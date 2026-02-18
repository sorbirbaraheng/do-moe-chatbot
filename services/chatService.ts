/**
 * 📄 ชื่อไฟล์: chatService.ts
 * 📝 คำอธิบาย:
 *    บริการจัดการข้อมูลการสนทนา (Chat Data Service)
 *    ทำหน้าที่บันทึกและดึงข้อมูลประวัติแชทจาก Firebase Firestore
 *
 * 🛠 หน้าที่หลัก:
 *    1. Save Session: สร้างหรืออัปเดตข้อมูลเซสชันการสนทนา
 *    2. Log Message: บันทึกข้อความแต่ละรายการลงใน Cloud
 *    3. Fetch History: ดึงประวัติการสนทนาเก่าๆ ของผู้ใช้แต่ละคน
 *    4. Sync: รองรับการซิงค์ข้อมูลทั้งแบบโครงสร้างใหม่และแบบเดิม (Legacy)
 */

import { db } from './firebase';
import {
    collection,
    addDoc,
    serverTimestamp,
    doc,
    setDoc,
    getDocs,
    query,
    where,
    orderBy,
    limit,
    getDoc,
    deleteDoc,
    writeBatch
} from 'firebase/firestore';
import { Category, Message } from '../types';

export interface ChatSession {
    sessionId: string;
    userId: string;
    title: string;
    category: Category;
    createdAt?: any;
    updatedAt?: any;
}

export interface ChatLogEntry {
    sessionId: string;
    userId: string | null;
    userName: string | null;
    userEmail: string | null;
    role: 'user' | 'model';
    content: string;
    category: string;
    isError?: boolean;
    modelName?: string;
    timestamp?: any;
}

// Collection References (Legacy)
const SESSIONS_COL = 'chat_sessions';
const LOGS_COL = 'chat_logs';

export const chatService = {
    /**
     * Creates or updates a chat session metadata
     * Path: users/{userId}/sessions/{sessionId}
     */
    saveSession: async (session: ChatSession) => {
        if (!session.userId || !session.sessionId) return;

        try {
            // Write to NEW structure: users/{userId}/sessions/{sessionId}
            const sessionRef = doc(db, 'users', session.userId, 'sessions', session.sessionId);
            const sessionData = {
                ...session,
                updatedAt: serverTimestamp()
            };
            await setDoc(sessionRef, sessionData, { merge: true });

            // Also keep legacy sync for now if needed (optional, but good for migration)
            const legacyRef = doc(db, SESSIONS_COL, session.sessionId);
            await setDoc(legacyRef, sessionData, { merge: true });
        } catch (error) {
            console.error("Error saving chat session:", error);
        }
    },

    /**
     * Logs a single message to the cloud history
     * Path: users/{userId}/sessions/{sessionId}/messages/{msgId}
     */
    logMessage: async (entry: ChatLogEntry) => {
        try {
            if (!entry.content || !entry.sessionId) return;

            // Determine path: prefer user-centric path if userId is available
            const logData = {
                ...entry,
                userId: entry.userId || null, // Ensure userId is at least null
                timestamp: serverTimestamp(),
                createdAt: new Date().toISOString()
            };

            console.log(`[chatService] Logging message for session ${entry.sessionId} (User: ${entry.userId || 'Guest'})`);

            if (entry.userId) {
                const msgCol = collection(db, 'users', entry.userId, 'sessions', entry.sessionId, 'messages');
                await addDoc(msgCol, logData);
            }

            // Always write to legacy flat collection for global admin view/backup for now
            await addDoc(collection(db, LOGS_COL), logData);
        } catch (error) {
            console.error("Failed to log chat message:", error);
        }
    },

    /**
     * Fetches all chat sessions for a specific user
     */
    getUserSessions: async (userId: string): Promise<ChatSession[]> => {
        try {
            // Try NEW structure first
            const q = query(
                collection(db, 'users', userId, 'sessions'),
                orderBy('updatedAt', 'desc')
            );

            const snapshot = await getDocs(q);
            if (!snapshot.empty) {
                return snapshot.docs.map(doc => ({
                    sessionId: doc.id,
                    ...doc.data()
                } as ChatSession));
            }

            // Fallback to LEGACY structure
            const legacyQ = query(
                collection(db, SESSIONS_COL),
                where('userId', '==', userId),
                orderBy('updatedAt', 'desc')
            );
            const legacySnapshot = await getDocs(legacyQ);
            return legacySnapshot.docs.map(doc => ({
                sessionId: doc.id,
                ...doc.data()
            } as ChatSession));
        } catch (error) {
            console.error("Error fetching user sessions:", error);
            return [];
        }
    },

    /**
     * Fetches the full message history for a specific session
     */
    getSessionMessages: async (sessionId: string, userId?: string): Promise<Message[]> => {
        try {
            let snapshot;

            // Try NEW user-specific path if userId is provided
            if (userId) {
                const q = query(
                    collection(db, 'users', userId, 'sessions', sessionId, 'messages'),
                    orderBy('timestamp', 'asc')
                );
                snapshot = await getDocs(q);
            }

            // If not found or no userId, fallback to LEGACY flat collection
            if (!snapshot || snapshot.empty) {
                let legacyQ;
                if (userId) {
                    legacyQ = query(
                        collection(db, LOGS_COL),
                        where('sessionId', '==', sessionId),
                        where('userId', '==', userId), // Mandatory filter for security rules
                        orderBy('timestamp', 'asc')
                    );
                } else {
                    legacyQ = query(
                        collection(db, LOGS_COL),
                        where('sessionId', '==', sessionId),
                        orderBy('timestamp', 'asc')
                    );
                }
                snapshot = await getDocs(legacyQ);
            }

            return snapshot.docs.map(doc => {
                const data = doc.data();
                return {
                    id: doc.id,
                    role: data.role,
                    content: data.content,
                    timestamp: data.timestamp?.toDate() || new Date(data.createdAt),
                    isError: data.isError
                } as Message;
            });
        } catch (error) {
            console.error("Error fetching session messages:", error);
            return [];
        }
    },

    /**
     * Deletes a chat session and all messages for the current user
     */
    deleteSession: async (sessionId: string, userId?: string): Promise<void> => {
        if (!sessionId) return;

        try {
            if (userId) {
                // Delete NEW structure messages: users/{userId}/sessions/{sessionId}/messages/*
                const userMessagesCol = collection(db, 'users', userId, 'sessions', sessionId, 'messages');
                const userMessagesSnapshot = await getDocs(userMessagesCol);
                for (let i = 0; i < userMessagesSnapshot.docs.length; i += 400) {
                    const batch = writeBatch(db);
                    userMessagesSnapshot.docs.slice(i, i + 400).forEach((msgDoc) => {
                        batch.delete(msgDoc.ref);
                    });
                    await batch.commit();
                }

                // Delete NEW session doc
                await deleteDoc(doc(db, 'users', userId, 'sessions', sessionId));
            }

            // Delete LEGACY session doc (safe even if missing)
            await deleteDoc(doc(db, SESSIONS_COL, sessionId));

            // Delete LEGACY logs for this session (limit by userId when available)
            const logsQuery = userId
                ? query(
                    collection(db, LOGS_COL),
                    where('sessionId', '==', sessionId),
                    where('userId', '==', userId)
                )
                : query(
                    collection(db, LOGS_COL),
                    where('sessionId', '==', sessionId)
                );

            const logsSnapshot = await getDocs(logsQuery);
            for (let i = 0; i < logsSnapshot.docs.length; i += 400) {
                const batch = writeBatch(db);
                logsSnapshot.docs.slice(i, i + 400).forEach((logDoc) => {
                    batch.delete(logDoc.ref);
                });
                await batch.commit();
            }
        } catch (error) {
            console.error('Error deleting chat session:', error);
            throw error;
        }
    }
};
