import React, { useState, useEffect } from 'react';
import { MOE_COLORS } from '../../constants';
import { User } from '../../types';
import { useAuth } from '../../contexts/AuthContext';

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

    // Basic Email Validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      alert("กรุณากรอกอีเมลให้ถูกต้องครับ");
      return;
    }

    if (!password) {
      alert("กรุณากรอกรหัสผ่านครับ");
      return;
    }

    setLoading(true);
    try {
      if (isSignUp) {
        const name = email.split('@')[0];
        await signupWithEmail(email, password, name);
      } else {
        await loginWithEmail(email, password);
      }
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

  // =============================================
  // MOBILE VIEW - Apple Style (< md breakpoint)
  // =============================================
  const MobileView = () => (
    <div className="min-h-screen bg-[#F2F2F7] flex flex-col relative overflow-hidden">

      {/* Dynamic Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-10%] right-[-20%] w-[70%] h-[50%] rounded-full bg-blue-400/10 blur-[80px] animate-pulse-slow"></div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[60%] h-[50%] rounded-full bg-purple-400/10 blur-[80px] animate-pulse-slow" style={{ animationDelay: '1.5s' }}></div>
      </div>

      {/* Navigation Bar */}
      <div className="pt-14 px-4 pb-2 z-10 flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-[#007AFF] text-[17px] font-normal active:opacity-60 transition-opacity pl-2"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
          ย้อนกลับ
        </button>
      </div>

      {/* Header - Large Title */}
      <div className="px-6 pb-8 z-10">
        <h1 className="text-[34px] font-bold text-[#1d1d1f] tracking-tight leading-tight">
          {isSignUp ? 'สร้างบัญชี' : 'เข้าสู่ระบบ'}
        </h1>
        <p className="text-[17px] text-[#86868b] mt-1 pr-10 leading-relaxed">
          {isSignUp ? 'กรอกข้อมูลเพื่อเริ่มต้นใช้งาน MOE One' : 'ยินดีต้อนรับกลับมา'}
        </p>
      </div>

      {/* Form Content */}
      <div className="flex-1 px-4 z-10">

        {/* iOS Inset Grouped Table Style - Ultra Glass */}
        <div className="bg-white/70 backdrop-blur-3xl rounded-[24px] overflow-hidden shadow-[0_20px_50px_-12px_rgba(0,0,0,0.1)] border border-white/60 mb-6 ring-1 ring-white/50 relative">
          {/* Shine Effect */}
          <div className="absolute inset-0 bg-gradient-to-br from-white/40 to-transparent pointer-events-none"></div>

          <form onSubmit={handleSubmit} className="relative z-10">

            {/* Email Field - Inner Shadow */}
            <div className="pl-5 pr-4 py-4 flex items-center bg-transparent active:bg-white/90 transition-colors relative group border-b border-[#c6c6c8]/20">
              <label className="w-24 text-[17px] text-[#1d1d1f] font-normal tracking-tight">อีเมล</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@moe.go.th"
                className="flex-1 text-[17px] text-[#007AFF] placeholder:text-[#c7c7cc]/80 bg-transparent outline-none text-right group-focus-within:text-left transition-all duration-300"
              />
            </div>

            {/* Password Field */}
            <div className="pl-5 pr-4 py-3.5 flex items-center bg-white active:bg-[#e5e5ea] transition-colors relative group">
              <label className="w-24 text-[17px] text-[#1d1d1f] font-normal">รหัสผ่าน</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="จำเป็น"
                className="flex-1 text-[17px] text-[#007AFF] placeholder:text-[#c7c7cc] bg-transparent outline-none text-right"
              />
              {isSignUp && <div className="absolute bottom-0 left-5 right-0 h-[0.5px] bg-[#c6c6c8]/40" />}
            </div>

            {/* Repeat Password (SignUp) */}
            {isSignUp && (
              <div className="pl-5 pr-4 py-3.5 flex items-center bg-white active:bg-[#e5e5ea] transition-colors relative">
                <label className="w-28 text-[17px] text-[#1d1d1f] font-normal">ยืนยันรหัส</label>
                <input
                  type="password"
                  required
                  value={repeatPassword}
                  onChange={(e) => setRepeatPassword(e.target.value)}
                  placeholder="ยืนยัน"
                  className="flex-1 text-[17px] text-[#007AFF] placeholder:text-[#c7c7cc] bg-transparent outline-none text-right"
                />
              </div>
            )}
          </form>
        </div>

        {/* Forgot Password Link */}
        {!isSignUp && (
          <div className="text-right px-2 mb-8">
            <button type="button" className="text-[15px] text-[#007AFF] font-medium active:opacity-60">
              ลืมรหัสผ่าน?
            </button>
          </div>
        )}

        {/* Terms Checkbox */}
        {isSignUp && (
          <div className="flex items-start gap-3 px-4 mb-8">
            <div className="pt-0.5">
              <input
                type="checkbox"
                checked={acceptTerms}
                onChange={(e) => setAcceptTerms(e.target.checked)}
                className="w-5 h-5 rounded-full border-gray-300 text-[#007AFF] focus:ring-0 cursor-pointer"
              />
            </div>
            <p className="text-[13px] text-[#86868b] leading-tight">
              ฉันตกลงยอมรับ <span className="text-[#007AFF]">ข้อตกลงและเงื่อนไข</span> และ <span className="text-[#007AFF]">นโยบายความเป็นส่วนตัว</span> ของการบริการ
            </p>
          </div>
        )}

        {/* Primary Action Button */}
        <button
          onClick={handleSubmit as any}
          disabled={loading}
          className="w-full py-3.5 rounded-xl bg-[#007AFF] text-white text-[17px] font-semibold active:scale-[0.98] active:opacity-90 disabled:opacity-50 transition-all shadow-md shadow-blue-500/20 mb-6"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
              กำลังโหลด...
            </span>
          ) : (
            isSignUp ? 'สมัครสมาชิก' : 'เข้าสู่ระบบ'
          )}
        </button>

        {/* Apple Style "Or" Divider */}
        <div className="relative flex py-2 items-center mb-6">
          <div className="flex-grow border-t border-[#c6c6c8]/60"></div>
          <span className="flex-shrink mx-4 text-gray-400 text-[13px] font-medium">หรือ</span>
          <div className="flex-grow border-t border-[#c6c6c8]/60"></div>
        </div>

        {/* Google Login Button - White Glass */}
        <button
          onClick={() => handleSocialLogin('Google')}
          className="w-full py-3.5 rounded-xl bg-white text-[#1d1d1f] text-[17px] font-medium border border-[#c6c6c8]/50 flex items-center justify-center gap-3 active:bg-[#f2f2f7] transition-colors"
        >
          <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google" className="w-5 h-5" />
          ดำเนินการต่อด้วย Google
        </button>

      </div>

      {/* Footer Toggle */}
      <div className="py-8 text-center z-10 pb-12">
        <span className="text-[15px] text-[#86868b]">
          {isSignUp ? 'มีบัญชีอยู่แล้ว?' : 'ยังไม่มีบัญชี?'}
        </span>
        <button
          onClick={() => setIsSignUp(!isSignUp)}
          className="ml-1.5 text-[15px] text-[#007AFF] font-medium active:opacity-60"
        >
          {isSignUp ? 'เข้าสู่ระบบ' : 'สมัครสมาชิก'}
        </button>
      </div>
    </div>
  );

  // =============================================
  // DESKTOP VIEW - Original (unchanged)
  // =============================================
  const DesktopView = () => (
    <div className="h-screen w-full flex items-start md:items-center justify-center px-4 md:px-6 py-6 md:py-20 relative overflow-y-auto">
      <div className="w-full max-w-6xl bg-white/40 backdrop-blur-3xl rounded-[3rem] shadow-[0_40px_120px_-20px_rgba(0,0,0,0.1)] border border-white/60 flex flex-col md:flex-row relative slide-up-content">

        {/* Left Side: Information */}
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
            className="group mb-12 self-start flex items-center gap-2.5 px-4 py-2 bg-white/60 hover:bg-white/95 backdrop-blur-xl border border-white/50 rounded-full shadow-sm hover:shadow-md transition-all duration-300"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5" style={{ color: MOE_COLORS.textMain }}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
            <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: MOE_COLORS.textMain }}>ย้อนกลับ</span>
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
        <div className="w-full md:w-1/2 bg-white/95 p-10 md:p-16 flex flex-col justify-center relative rounded-b-[2.8rem] md:rounded-r-[2.8rem] md:rounded-bl-none">
          <div className="max-w-md mx-auto w-full">
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
                    <button type="button" className="text-[11px] font-bold text-blue-600 hover:underline">ลืมรหัสผ่าน?</button>
                  )}
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-[#F5F5F7] border border-transparent px-5 py-4 rounded-2xl focus:bg-white focus:border-[#007AFF]/20 focus:ring-4 focus:ring-[#007AFF]/5 outline-none transition-all text-[#1D1D1F] font-medium placeholder:text-gray-400/50"
                />
                {isSignUp && (
                  <p className="text-[10px] font-medium opacity-40 mt-1 ml-1">ใช้ตัวอักษร 8 ตัวขึ้นไป ผสมตัวเลขและสัญลักษณ์</p>
                )}
              </div>

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
                    <span>{isSignUp ? "Sign Up" : "Sign In"}</span>
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
                  className="ml-2 font-black text-blue-600 hover:underline"
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

  // Return: Mobile or Desktop based on screen size using CSS
  return (
    <>
      {/* Mobile View (hidden on md+) */}
      <div className="md:hidden">
        <MobileView />
      </div>

      {/* Desktop View (hidden below md) */}
      <div className="hidden md:block">
        <DesktopView />
      </div>
    </>
  );
};

export default React.memo(LoginPage);
