import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { User, signInWithPopup, signOut, onAuthStateChanged, signInWithEmailAndPassword, createUserWithEmailAndPassword, updateProfile } from 'firebase/auth';
import { doc, getDoc, setDoc } from 'firebase/firestore';
import { auth, googleProvider, db } from '../services/firebase';

interface AuthContextType {
    user: User | null;
    userRole: string;
    loading: boolean;
    loginWithGoogle: () => Promise<void>;
    loginWithEmail: (email: string, password: string) => Promise<void>;
    signupWithEmail: (email: string, password: string, name: string) => Promise<void>;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [userRole, setUserRole] = useState<string>('user'); // Default to 'user'

    // Helper to sync user with Firestore
    const syncUserWithFirestore = async (firebaseUser: User, name?: string) => {
        if (!firebaseUser) return;
        const userRef = doc(db, 'users', firebaseUser.uid);

        try {
            const userSnap = await getDoc(userRef);

            if (userSnap.exists()) {
                // User exists, get role
                const userData = userSnap.data();
                setUserRole(userData.role || 'user');
            } else {
                // New user (or first time login with this system)
                // Determine default role based on email domain or just default to 'user'
                const defaultRole = 'user';
                await setDoc(userRef, {
                    email: firebaseUser.email,
                    displayName: name || firebaseUser.displayName || firebaseUser.email?.split('@')[0] || "User",
                    role: defaultRole,
                    photoURL: firebaseUser.photoURL || "",
                    createdAt: new Date().toISOString()
                });
                setUserRole(defaultRole);
            }
        } catch (error) {
            console.error("Error syncing user data:", error);
            // Fallback
            setUserRole('user');
        }
    };

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            setUser(currentUser);
            if (currentUser) {
                await syncUserWithFirestore(currentUser);
            } else {
                setUserRole('user');
            }
            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    const loginWithGoogle = async () => {
        try {
            const result = await signInWithPopup(auth, googleProvider);
            // syncUserWithFirestore is handled by onAuthStateChanged, 
            // but we can ensure name update if needed.
        } catch (error) {
            console.error("Google Login Error:", error);
            throw error;
        }
    };

    const loginWithEmail = async (email: string, password: string) => {
        try {
            await signInWithEmailAndPassword(auth, email, password);
        } catch (error) {
            console.error("Email Login Error:", error);
            throw error;
        }
    };

    const signupWithEmail = async (email: string, password: string, name: string) => {
        try {
            const userCredential = await createUserWithEmailAndPassword(auth, email, password);
            if (userCredential.user) {
                await updateProfile(userCredential.user, { displayName: name });
                // Manually call sync to ensure the document is created with the provided name immediately
                await syncUserWithFirestore(userCredential.user, name);

                // Update local state to reflect name change immediately in UI if needed
                setUser({ ...userCredential.user, displayName: name });
            }
        } catch (error) {
            console.error("Signup Error:", error);
            throw error;
        }
    };

    const logout = async () => {
        try {
            await signOut(auth);
            setUserRole('user');
        } catch (error) {
            console.error("Logout Error:", error);
        }
    };

    return (
        <AuthContext.Provider value={{ user, userRole, loading, loginWithGoogle, loginWithEmail, signupWithEmail, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = (): AuthContextType => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
