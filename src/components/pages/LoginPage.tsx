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
    <div className="min-h-screen bg-gradient-to-br from-[#F2F2F7] via-[#E8E8ED] to-[#F2F2F7] flex flex-col relative overflow-hidden px-6 sm:px-8">

      {/* Dynamic Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-10%] right-[-20%] w-[70%] h-[50%] rounded-full bg-blue-400/20 blur-[100px] animate-pulse-slow"></div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[60%] h-[50%] rounded-full bg-purple-400/20 blur-[100px] animate-pulse-slow" style={{ animationDelay: '1.5s' }}></div>
      </div>

      {/* Navigation Bar */}
      <div className="pt-safe pt-12 sm:pt-14 pb-5 sm:pb-6 z-10 flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-[#007AFF] text-[17px] sm:text-[18px] font-normal active:opacity-60 transition-opacity"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
          ย้อนกลับ
        </button>
      </div>

      {/* Header - Large Title */}
      <div className="pb-7 sm:pb-8 z-10">
        <h1 className="text-[34px] sm:text-[36px] font-bold text-[#1d1d1f] tracking-tight leading-[1.1]">
          {isSignUp ? 'สร้างบัญชี' : 'เข้าสู่ระบบ'}
        </h1>
        <p className="text-[16px] sm:text-[17px] text-[#86868b] mt-3 leading-snug">
          {isSignUp ? 'กรอกข้อมูลเพื่อเริ่มต้นใช้งาน MOE One' : 'ยินดีต้อนรับกลับมา'}
        </p>
      </div>

      {/* Form Content */}
      <div className="flex-1 z-10 pb-safe pb-8 max-w-md mx-auto w-full">

        {/* iOS Inset Grouped Table Style - Ultra Glass */}
        <div className="bg-white/80 backdrop-blur-2xl rounded-[22px] sm:rounded-[24px] overflow-hidden shadow-[0_10px_40px_-8px_rgba(0,0,0,0.12)] border border-white/80 mb-6 sm:mb-7 ring-1 ring-white/60 relative">
          {/* Shine Effect */}
          <div className="absolute inset-0 bg-gradient-to-br from-white/50 to-transparent pointer-events-none"></div>

          <form onSubmit={handleSubmit} className="relative z-10">

            {/* Email Field - Inner Shadow */}
            <div className="pl-5 sm:pl-6 pr-5 sm:pr-6 py-4 sm:py-[18px] flex items-center bg-transparent active:bg-white/95 transition-colors relative group border-b border-[#c6c6c8]/15">
              <label className="w-20 sm:w-24 text-[16px] sm:text-[17px] text-[#1d1d1f] font-medium">อีเมล</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@moe.go.th"
                className="flex-1 text-[16px] sm:text-[17px] text-[#007AFF] placeholder:text-[#c7c7cc]/70 bg-transparent outline-none text-right font-normal"
              />
            </div>

            {/* Password Field */}
            <div className="pl-5 sm:pl-6 pr-5 sm:pr-6 py-4 sm:py-[18px] flex items-center bg-transparent active:bg-white/95 transition-colors relative group">
              <label className="w-20 sm:w-24 text-[16px] sm:text-[17px] text-[#1d1d1f] font-medium">รหัสผ่าน</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••"
                className="flex-1 text-[16px] sm:text-[17px] text-[#007AFF] placeholder:text-[#c7c7cc]/70 bg-transparent outline-none text-right font-normal"
              />
              {isSignUp && <div className="absolute bottom-0 left-5 sm:left-6 right-0 h-[0.5px] bg-[#c6c6c8]/30" />}
            </div>

            {/* Repeat Password (SignUp) */}
            {isSignUp && (
              <div className="pl-5 sm:pl-6 pr-5 sm:pr-6 py-4 sm:py-[18px] flex items-center bg-transparent active:bg-white/95 transition-colors relative">
                <label className="w-24 sm:w-28 text-[16px] sm:text-[17px] text-[#1d1d1f] font-medium">ยืนยันรหัส</label>
                <input
                  type="password"
                  required
                  value={repeatPassword}
                  onChange={(e) => setRepeatPassword(e.target.value)}
                  placeholder="••••••"
                  className="flex-1 text-[16px] sm:text-[17px] text-[#007AFF] placeholder:text-[#c7c7cc]/70 bg-transparent outline-none text-right font-normal"
                />
              </div>
            )}
          </form>
        </div>

        {/* Forgot Password Link */}
        {!isSignUp && (
          <div className="text-right mb-7 sm:mb-8">
            <button type="button" className="text-[15px] sm:text-[16px] text-[#007AFF] font-semibold active:opacity-60 transition-opacity">
              ลืมรหัสผ่าน?
            </button>
          </div>
        )}

        {/* Terms Checkbox */}
        {isSignUp && (
          <div className="flex items-start gap-3 sm:gap-3.5 mb-7 sm:mb-8">
            <div className="pt-0.5">
              <input
                type="checkbox"
                checked={acceptTerms}
                onChange={(e) => setAcceptTerms(e.target.checked)}
                className="w-[19px] h-[19px] sm:w-5 sm:h-5 rounded border-2 border-gray-300 text-[#007AFF] focus:ring-2 focus:ring-blue-500/30 cursor-pointer"
              />
            </div>
            <p className="text-[14px] sm:text-[15px] text-[#86868b] leading-relaxed">
              ฉันตกลงยอมรับ <span className="text-[#007AFF] font-medium">ข้อตกลงและเงื่อนไข</span> และ <span className="text-[#007AFF] font-medium">นโยบายความเป็นส่วนตัว</span>
            </p>
          </div>
        )}

        {/* Primary Action Button */}
        <button
          onClick={handleSubmit as any}
          disabled={loading}
          className="w-full py-[15px] sm:py-4 rounded-[15px] sm:rounded-[16px] bg-[#007AFF] text-white text-[17px] sm:text-[18px] font-semibold active:scale-[0.985] disabled:opacity-50 transition-all shadow-lg shadow-blue-500/25 mb-6 sm:mb-7"
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
        <div className="relative flex py-3.5 sm:py-4 items-center mb-6 sm:mb-7">
          <div className="flex-grow border-t border-[#c6c6c8]/50"></div>
          <span className="flex-shrink mx-5 sm:mx-6 text-[#86868b] text-[13px] sm:text-[14px] font-medium">หรือ</span>
          <div className="flex-grow border-t border-[#c6c6c8]/50"></div>
        </div>

        {/* Google Login Button - White Glass */}
        <button
          onClick={() => handleSocialLogin('Google')}
          className="w-full py-[14px] sm:py-[15px] rounded-[15px] sm:rounded-[16px] bg-white/90 backdrop-blur-xl text-[#1d1d1f] text-[16px] sm:text-[17px] font-semibold border border-[#d1d1d6] flex items-center justify-center gap-3 sm:gap-3.5 active:bg-[#f2f2f7] active:scale-[0.985] transition-all shadow-sm"
        >
          <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google" className="w-[19px] h-[19px] sm:w-5 sm:h-5" />
          ดำเนินการต่อด้วย Google
        </button>

      </div>

      {/* Footer Toggle */}
      <div className="py-6 sm:py-7 text-center z-10 pb-safe pb-7 sm:pb-9">
        <span className="text-[15px] sm:text-[16px] text-[#86868b]">
          {isSignUp ? 'มีบัญชีอยู่แล้ว?' : 'ยังไม่มีบัญชี?'}
        </span>
        <button
          onClick={() => setIsSignUp(!isSignUp)}
          className="ml-2 text-[15px] sm:text-[16px] text-[#007AFF] font-semibold active:opacity-60 transition-opacity"
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
    <div className="min-h-screen w-full flex items-start md:items-center justify-center px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-10 lg:py-20 relative overflow-y-auto">
      <div className="w-full max-w-6xl bg-white/40 backdrop-blur-3xl rounded-[2rem] sm:rounded-[3rem] shadow-[0_40px_120px_-20px_rgba(0,0,0,0.1)] border border-white/60 flex flex-col md:flex-row relative slide-up-content">

        {/* Left Side: Information */}
        <div
          className="w-full md:w-1/2 p-8 sm:p-10 md:p-12 lg:p-20 flex flex-col justify-center text-left relative overflow-hidden rounded-t-[2rem] sm:rounded-t-[2.8rem] md:rounded-l-[2.8rem] md:rounded-tr-none"
          style={{
            backgroundImage: 'linear-gradient(to bottom, rgba(255,255,255,0.85), rgba(255,255,255,0.7)), url(/moe-building.jpg)',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        >
          <button
            onClick={onBack}
            className="group mb-6 sm:mb-8 md:mb-12 self-start flex items-center gap-2 sm:gap-2.5 px-3 sm:px-4 py-1.5 sm:py-2 bg-white/60 hover:bg-white/95 backdrop-blur-xl border border-white/50 rounded-full shadow-sm hover:shadow-md transition-all duration-300"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3 h-3 sm:w-3.5 sm:h-3.5" style={{ color: MOE_COLORS.textMain }}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
            <span className="text-[10px] sm:text-[11px] font-bold uppercase tracking-wider" style={{ color: MOE_COLORS.textMain }}>ย้อนกลับ</span>
          </button>

          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-black mb-4 sm:mb-6 tracking-tighter leading-tight" style={{ color: MOE_COLORS.textMain }}>
            Intelligent, Integrated and Insightful
          </h2>
          <p className="text-sm sm:text-base md:text-lg opacity-50 font-medium leading-relaxed max-w-sm mb-8 sm:mb-10 md:mb-12">
            ศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร (ศทส. สป.) ขับเคลื่อนนวัตกรรมข้อมูลขนาดใหญ่ (Big Data) เพื่อยกระดับการศึกษาไทยสู่สากล
          </p>

          <div className="mt-auto flex items-center gap-3 sm:gap-4 pt-6 sm:pt-8 md:pt-10 border-t border-black/10">
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl overflow-hidden shadow-lg">
              <img src="/do-mascot.png" alt="DO" className="w-full h-full object-cover" />
            </div>
            <div>
              <p className="text-[12px] sm:text-[14px] font-bold" style={{ color: MOE_COLORS.textMain }}>MOE - One</p>
              <p className="text-[9px] sm:text-[10px] font-black opacity-40 uppercase tracking-widest">Digital Assistant v1.0</p>
            </div>
          </div>
        </div>

        {/* Right Side: Form */}
        <div className="w-full md:w-1/2 bg-white/95 p-6 sm:p-8 md:p-12 lg:p-16 flex flex-col justify-center relative rounded-b-[2rem] sm:rounded-b-[2.8rem] md:rounded-r-[2.8rem] md:rounded-bl-none">
          <div className="max-w-md mx-auto w-full">
            <div key={isSignUp ? 'signup-head' : 'signin-head'} className="slide-up-content stagger-1">
              <h3 className="text-2xl sm:text-3xl font-black mb-2 tracking-tight" style={{ color: MOE_COLORS.textMain }}>
                {isSignUp ? 'Sign Up' : 'Sign In'}
              </h3>
              <p className="text-[11px] sm:text-[13px] font-bold opacity-30 uppercase tracking-widest mb-6 sm:mb-8 md:mb-10">
                {isSignUp ? 'สร้างบัญชีผู้ใช้งานใหม่' : 'เข้าสู่แพลตฟอร์มบริหารจัดการข้อมูลอัจฉริยะ'}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5">
              <div className="space-y-1.5">
                <label className="text-[11px] sm:text-[12px] font-black uppercase tracking-wider opacity-40 ml-1">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@moe.go.th"
                  className="w-full bg-[#F5F5F7] border border-transparent px-4 sm:px-5 py-3 sm:py-4 rounded-xl sm:rounded-2xl focus:bg-white focus:border-[#007AFF]/20 focus:ring-4 focus:ring-[#007AFF]/5 outline-none transition-all text-[#1D1D1F] text-sm sm:text-base font-medium placeholder:text-gray-400/50"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center h-5">
                  <label className="text-[11px] sm:text-[12px] font-black uppercase tracking-wider opacity-40 ml-1">Password</label>
                  {!isSignUp && (
                    <button type="button" className="text-[10px] sm:text-[11px] font-bold text-blue-600 hover:underline">ลืมรหัสผ่าน?</button>
                  )}
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-[#F5F5F7] border border-transparent px-4 sm:px-5 py-3 sm:py-4 rounded-xl sm:rounded-2xl focus:bg-white focus:border-[#007AFF]/20 focus:ring-4 focus:ring-[#007AFF]/5 outline-none transition-all text-[#1D1D1F] text-sm sm:text-base font-medium placeholder:text-gray-400/50"
                />
                {isSignUp && (
                  <p className="text-[10px] font-medium opacity-40 mt-1 ml-1">ใช้ตัวอักษร 8 ตัวขึ้นไป ผสมตัวเลขและสัญลักษณ์</p>
                )}
              </div>

              <div className={`overflow-hidden transition-all duration-500 ease-in-out ${isSignUp ? 'max-h-40 opacity-100 mt-4 sm:mt-5' : 'max-h-0 opacity-0'}`}>
                <div className="space-y-4 sm:space-y-5">
                  <div className="space-y-1.5">
                    <label className="text-[11px] sm:text-[12px] font-black uppercase tracking-wider opacity-40 ml-1">Repeat Password</label>
                    <input
                      type="password"
                      required={isSignUp}
                      value={repeatPassword}
                      onChange={(e) => setRepeatPassword(e.target.value)}
                      className="w-full bg-[#F5F5F7] border border-transparent px-4 sm:px-5 py-3 sm:py-4 rounded-xl sm:rounded-2xl focus:bg-white focus:border-[#007AFF]/20 focus:ring-4 focus:ring-[#007AFF]/5 outline-none transition-all text-[#1D1D1F] text-sm sm:text-base font-medium"
                    />
                  </div>
                  <div className="flex items-center gap-2 sm:gap-3 pt-1">
                    <input
                      type="checkbox"
                      id="terms"
                      checked={acceptTerms}
                      onChange={(e) => setAcceptTerms(e.target.checked)}
                      className="w-4 h-4 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                    <label htmlFor="terms" className="text-[12px] sm:text-[13px] font-medium opacity-50 cursor-pointer">
                      ฉันยอมรับ <button type="button" className="text-blue-600 hover:underline">ข้อตกลงและเงื่อนไข</button>
                    </label>
                  </div>
                </div>
              </div>

              <div className="pt-3 sm:pt-4 space-y-4 sm:space-y-6">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full text-white py-4 sm:py-5 md:py-6 rounded-full font-black text-[16px] sm:text-[18px] tracking-tight shadow-xl shadow-blue-500/20 hover:shadow-2xl hover:shadow-blue-500/40 active:scale-[0.98] transition-all flex items-center justify-center gap-3"
                  style={{ backgroundColor: MOE_COLORS.appleBlue }}
                >
                  {loading ? (
                    <div className="w-5 h-5 sm:w-6 sm:h-6 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    <span>{isSignUp ? "Sign Up" : "Sign In"}</span>
                  )}
                </button>

                <div className="relative flex items-center justify-center">
                  <div className="flex-grow border-t border-black/5"></div>
                  <span className="flex-shrink mx-3 sm:mx-4 text-[9px] sm:text-[10px] font-black uppercase tracking-widest opacity-20">Or with</span>
                  <div className="flex-grow border-t border-black/5"></div>
                </div>

                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={() => handleSocialLogin('Google')}
                    className="flex items-center justify-center gap-2 sm:gap-3 py-3 sm:py-3.5 px-6 sm:px-8 bg-white border border-black/5 rounded-xl sm:rounded-2xl hover:bg-gray-50 transition-all font-bold text-[12px] sm:text-[13px] shadow-sm active:scale-95 w-full max-w-xs"
                  >
                    <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google" className="w-4 h-4 sm:w-5 sm:h-5" />
                    Continue with Google
                  </button>
                </div>
              </div>
            </form>

            <div className="mt-8 sm:mt-10 md:mt-12 text-center">
              <p className="text-[13px] sm:text-[14px] font-medium opacity-40">
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
