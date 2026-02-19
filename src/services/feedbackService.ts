/**
 * Feedback Service - Save user feedback to Firebase
 * 
 * 📄 feedbackService.ts
 * 📝 บันทึก feedback (👍👎) ของ user ต่อคำตอบของ AI
 * 
 * Features:
 * - Save feedback to Firestore
 * - Track response quality
 * - Analytics support
 */

import { db } from './firebase';
import { collection, addDoc, updateDoc, doc, query, where, getDocs, Timestamp } from 'firebase/firestore';

export interface FeedbackData {
    messageId: string;
    sessionId: string;
    userId?: string;
    userQuestion: string;
    aiResponse: string;
    feedback: 'positive' | 'negative';
    category: 'general' | 'school' | 'student';
    createdAt: Date;
    additionalComment?: string;
}

export interface FeedbackStats {
    totalFeedback: number;
    positiveCount: number;
    negativeCount: number;
    positiveRate: number;
}

const FEEDBACK_COLLECTION = 'response_feedback';

/**
 * Save feedback to Firestore
 */
export const saveFeedback = async (feedback: Omit<FeedbackData, 'createdAt'>): Promise<string | null> => {
    try {
        if (!db) {
            console.warn('[Feedback] Firebase not initialized');
            return null;
        }

        const feedbackDoc = {
            ...feedback,
            createdAt: Timestamp.now(),
            // Truncate long responses to save storage
            aiResponse: feedback.aiResponse.substring(0, 500),
            userQuestion: feedback.userQuestion.substring(0, 200)
        };

        const docRef = await addDoc(collection(db, FEEDBACK_COLLECTION), feedbackDoc);
        console.log(`[Feedback] ✅ Saved: ${feedback.feedback} for message ${feedback.messageId}`);

        return docRef.id;
    } catch (error) {
        console.error('[Feedback] ❌ Error saving:', error);
        return null;
    }
};

/**
 * Update existing feedback (e.g., add comment)
 */
export const updateFeedback = async (
    feedbackId: string,
    updates: Partial<FeedbackData>
): Promise<boolean> => {
    try {
        if (!db) return false;

        await updateDoc(doc(db, FEEDBACK_COLLECTION, feedbackId), updates);
        return true;
    } catch (error) {
        console.error('[Feedback] ❌ Error updating:', error);
        return false;
    }
};

/**
 * Get feedback stats for a session or globally
 */
export const getFeedbackStats = async (sessionId?: string): Promise<FeedbackStats> => {
    try {
        if (!db) {
            return { totalFeedback: 0, positiveCount: 0, negativeCount: 0, positiveRate: 0 };
        }

        let q = query(collection(db, FEEDBACK_COLLECTION));

        if (sessionId) {
            q = query(collection(db, FEEDBACK_COLLECTION), where('sessionId', '==', sessionId));
        }

        const snapshot = await getDocs(q);

        let positiveCount = 0;
        let negativeCount = 0;

        snapshot.forEach(doc => {
            const data = doc.data();
            if (data.feedback === 'positive') positiveCount++;
            else if (data.feedback === 'negative') negativeCount++;
        });

        const totalFeedback = positiveCount + negativeCount;
        const positiveRate = totalFeedback > 0 ? (positiveCount / totalFeedback) * 100 : 0;

        return {
            totalFeedback,
            positiveCount,
            negativeCount,
            positiveRate: Math.round(positiveRate * 10) / 10
        };
    } catch (error) {
        console.error('[Feedback] ❌ Error getting stats:', error);
        return { totalFeedback: 0, positiveCount: 0, negativeCount: 0, positiveRate: 0 };
    }
};

/**
 * Check if user already gave feedback for a message
 */
export const hasFeedback = async (messageId: string): Promise<boolean> => {
    try {
        if (!db) return false;

        const q = query(
            collection(db, FEEDBACK_COLLECTION),
            where('messageId', '==', messageId)
        );

        const snapshot = await getDocs(q);
        return !snapshot.empty;
    } catch (error) {
        return false;
    }
};

export default {
    saveFeedback,
    updateFeedback,
    getFeedbackStats,
    hasFeedback
};
