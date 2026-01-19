import { initializeApp } from "firebase/app";
import { initializeFirestore } from "firebase/firestore";
import { getAnalytics } from "firebase/analytics";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
    apiKey: "AIzaSyDpwCBnCv7TKQVDCBJmm-NnNwg5pJ1Ct4w",
    authDomain: "chatbot-97475.firebaseapp.com",
    projectId: "chatbot-97475",
    storageBucket: "chatbot-97475.firebasestorage.app",
    messagingSenderId: "696348777998",
    appId: "1:696348777998:web:b0e11ea27b7239fe8ea65f",
    measurementId: "G-HQPY4JREDZ"
};

const app = initializeApp(firebaseConfig);
export const db = initializeFirestore(app, { experimentalForceLongPolling: true });
// export const db = getFirestore(app);
export const analytics = getAnalytics(app);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

export default app;
