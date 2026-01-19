import React, { useState } from 'react';
import { MOE_COLORS } from '../constants';
import { User } from '../types';
import { useAuth } from '../contexts/AuthContext';

interface LoginPageProps {
  onLogin: (user: User) => void;
  onBack: () => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin, onBack }) => {
  const [loading, setLoading] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [repeatPassword, setRepeatPassword] = useState('');
  const [acceptTerms, setAcceptTerms] = useState(false);

  const { loginWithGoogle, loginWithEmail, signupWithEmail } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSignUp && password !== repeatPassword) {
      alert("รหัสผ่านไม่ตรงกันครับ");
      return;
    }
    if (isSignUp && !acceptTerms) {
      alert("กรุณายอมรับเงื่อนไขการใช้งานก่อนครับ");
      return;
    }

    setLoading(true);
    try {
      if (isSignUp) {
        // Use part of email as name for now, or could add name input field
        const name = email.split('@')[0];
        await signupWithEmail(email, password, name);
      } else {
        await loginWithEmail(email, password);
      }
      // Success is handled by App.tsx detecting user change, or we can explicity redirect if needed, 
      // but typically the AuthState listener in App will switch the view.
    } catch (error: any) {
      console.error("Auth Error:", error);
      let msg = "เกิดข้อผิดพลาด กรุณาลองใหม่ครับ";
      if (error.code === 'auth/wrong-password') msg = 'รหัสผ่านไม่ถูกต้อง';
      else if (error.code === 'auth/user-not-found') msg = 'ไม่พบผู้ใช้งานนี้';
      else if (error.code === 'auth/email-already-in-use') msg = 'อีเมลนี้ถูกใช้งานแล้ว';
      else if (error.code === 'auth/weak-password') msg = 'รหัสผ่านต้องมีความยาว 6 ตัวอักษรขึ้นไป';

      alert(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = async (provider: string) => {
    if (provider !== 'Google') {
      alert("ขออภัยครับ ขณะนี้รองรับเฉพาะ Google Login เท่านั้น");
      return;
    }

    setLoading(true);
    try {
      await loginWithGoogle();
    } catch (error) {
      console.error("Social Login Error:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen w-full flex items-start md:items-center justify-center px-4 md:px-6 py-6 md:py-20 relative overflow-y-auto">
      {/* Container Card */}
      <div className="w-full max-w-6xl bg-white/40 backdrop-blur-3xl rounded-[3rem] shadow-[0_40px_120px_-20px_rgba(0,0,0,0.1)] border border-white/60 flex flex-col md:flex-row relative slide-up-content">

        {/* Left Side: Information with Background Image */}
        <div
          className="w-full md:w-1/2 p-12 md:p-20 flex flex-col justify-center text-left relative overflow-hidden rounded-t-[2.8rem] md:rounded-l-[2.8rem] md:rounded-tr-none"
          style={{
            backgroundImage: 'linear-gradient(to bottom, rgba(255,255,255,0.85), rgba(255,255,255,0.7)), url(/moe-building.jpg)',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        >
          <button
            onClick={onBack}
            className="group mb-12 self-start flex items-center gap-2.5 px-4 py-2 bg-white/60 hover:bg-white/95 backdrop-blur-xl border border-white/50 rounded-full shadow-sm hover:shadow-md transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98]"
          >
            <div className="flex items-center justify-center group-hover:-translate-x-0.5 transition-transform duration-300">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5" style={{ color: MOE_COLORS.textMain }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
            </div>
            <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: MOE_COLORS.textMain }}>
              ย้อนกลับ
            </span>
          </button>

          <h2 className="text-4xl md:text-5xl font-black mb-6 tracking-tighter leading-tight" style={{ color: MOE_COLORS.textMain }}>
            Intelligent, Integrated and Insightful
          </h2>
          <p className="text-lg opacity-50 font-medium leading-relaxed max-w-sm mb-12">
            ศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร (ศทส. สป.) ขับเคลื่อนนวัตกรรมข้อมูลขนาดใหญ่ (Big Data) เพื่อยกระดับการศึกษาไทยสู่สากล
          </p>

          <div className="mt-auto flex items-center gap-4 pt-10 border-t border-black/10">
            <div className="w-12 h-12 rounded-2xl overflow-hidden shadow-lg">
              <img src="/do-mascot.png" alt="DO" className="w-full h-full object-cover" />
            </div>
            <div>
              <p className="text-[14px] font-bold" style={{ color: MOE_COLORS.textMain }}>MOE - One</p>
              <p className="text-[10px] font-black opacity-40 uppercase tracking-widest">Digital Assistant v1.0</p>
            </div>
          </div>
        </div>

        {/* Right Side: Form */}
        <div className="w-full md:w-1/2 bg-white/95 p-10 md:p-16 flex flex-col justify-center relative transition-all duration-500 rounded-b-[2.8rem] md:rounded-r-[2.8rem] md:rounded-bl-none">
          <div className="max-w-md mx-auto w-full">
            {/* Header with Animation Key */}
            <div key={isSignUp ? 'signup-head' : 'signin-head'} className="slide-up-content stagger-1">
              <h3 className="text-3xl font-black mb-2 tracking-tight" style={{ color: MOE_COLORS.textMain }}>
                {isSignUp ? 'Sign Up' : 'Sign In'}
              </h3>
              <p className="text-[13px] font-bold opacity-30 uppercase tracking-widest mb-10">
                {isSignUp ? 'สร้างบัญชีผู้ใช้งานใหม่' : 'เข้าสู่แพลตฟอร์มบริหารจัดการข้อมูลอัจฉริยะ'}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-1.5">
                <label className="text-[12px] font-black uppercase tracking-wider opacity-40 ml-1">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@moe.go.th"
                  className="w-full bg-[#F5F5F7] border border-transparent px-5 py-4 rounded-2xl focus:bg-white focus:border-[#007AFF]/20 focus:ring-4 focus:ring-[#007AFF]/5 outline-none transition-all text-[#1D1D1F] font-medium placeholder:text-gray-400/50"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center h-5">
                  <label className="text-[12px] font-black uppercase tracking-wider opacity-40 ml-1">Password</label>
                  {!isSignUp && (
                    <button type="button" className="text-[11px] font-bold text-blue-600 hover:underline animate-in fade-in duration-300">
                      ลืมรหัสผ่าน?
                    </button>
                  )}
                </div>
                <div className="relative">
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-[#F5F5F7] border border-transparent px-5 py-4 rounded-2xl focus:bg-white focus:border-[#007AFF]/20 focus:ring-4 focus:ring-[#007AFF]/5 outline-none transition-all text-[#1D1D1F] font-medium placeholder:text-gray-400/50"
                  />
                </div>
                {isSignUp && (
                  <p className="text-[10px] font-medium opacity-40 mt-1 ml-1 animate-in slide-in-from-top-1 fade-in duration-300">
                    ใช้ตัวอักษร 8 ตัวขึ้นไป ผสมตัวเลขและสัญลักษณ์
                  </p>
                )}
              </div>

              {/* Conditional Fields with Smooth Transition */}
              <div className={`overflow-hidden transition-all duration-500 ease-in-out ${isSignUp ? 'max-h-40 opacity-100 mt-5' : 'max-h-0 opacity-0'}`}>
                <div className="space-y-5">
                  <div className="space-y-1.5">
                    <label className="text-[12px] font-black uppercase tracking-wider opacity-40 ml-1">Repeat Password</label>
                    <input
                      type="password"
                      required={isSignUp}
                      value={repeatPassword}
                      onChange={(e) => setRepeatPassword(e.target.value)}
                      className="w-full bg-[#F5F5F7] border border-transparent px-5 py-4 rounded-2xl focus:bg-white focus:border-[#007AFF]/20 focus:ring-4 focus:ring-[#007AFF]/5 outline-none transition-all text-[#1D1D1F] font-medium"
                    />
                  </div>

                  <div className="flex items-center gap-3 pt-1">
                    <input
                      type="checkbox"
                      id="terms"
                      checked={acceptTerms}
                      onChange={(e) => setAcceptTerms(e.target.checked)}
                      className="w-4 h-4 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                    <label htmlFor="terms" className="text-[13px] font-medium opacity-50 cursor-pointer">
                      ฉันยอมรับ <button type="button" className="text-blue-600 hover:underline">ข้อตกลงและเงื่อนไข</button>
                    </label>
                  </div>
                </div>
              </div>

              <div className="pt-4 space-y-6">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full text-white py-6 rounded-full font-black text-[18px] tracking-tight shadow-xl shadow-blue-500/20 hover:shadow-2xl hover:shadow-blue-500/40 active:scale-[0.98] transition-all flex items-center justify-center gap-3"
                  style={{ backgroundColor: MOE_COLORS.appleBlue }}
                >
                  {loading ? (
                    <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    <span key={isSignUp ? 'txt-signup' : 'txt-signin'} className="animate-in fade-in zoom-in-95 duration-300">
                      {isSignUp ? "Sign Up" : "Sign In"}
                    </span>
                  )}
                </button>

                <div className="relative flex items-center justify-center">
                  <div className="flex-grow border-t border-black/5"></div>
                  <span className="flex-shrink mx-4 text-[10px] font-black uppercase tracking-widest opacity-20">Or with</span>
                  <div className="flex-grow border-t border-black/5"></div>
                </div>

                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={() => handleSocialLogin('Google')}
                    className="flex items-center justify-center gap-3 py-3.5 px-8 bg-white border border-black/5 rounded-2xl hover:bg-gray-50 transition-all font-bold text-[13px] shadow-sm active:scale-95 w-full max-w-xs"
                  >
                    <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google" className="w-5 h-5" />
                    Continue with Google
                  </button>
                </div>
              </div>
            </form>

            <div className="mt-12 text-center">
              <p className="text-[14px] font-medium opacity-40">
                {isSignUp ? 'Already have an account?' : "Don't have an account?"}
                <button
                  onClick={() => setIsSignUp(!isSignUp)}
                  className="ml-2 font-black text-blue-600 hover:underline transition-all active:scale-95 inline-block"
                >
                  {isSignUp ? 'Sign In' : 'Sign Up'}
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(LoginPage);
