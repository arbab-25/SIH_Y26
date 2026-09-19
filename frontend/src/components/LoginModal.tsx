import React, { useState } from 'react';
import { X, Shield, Lock, User, AlertCircle, CheckCircle2, Phone, Briefcase, MapPin, UserPlus, LogIn } from 'lucide-react';
import { api } from '../utils/api';
import { translations } from '../i18n/translations';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: any) => void;
  notice?: string | null;
  lang: 'en' | 'hi';
}

type Tab = 'login' | 'register';

export const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
  notice,
  lang,
}) => {
  const t = translations[lang];
  const [tab, setTab] = useState<Tab>('login');

  // --- Login state ---
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');

  // --- Register state (compact: name, email/mobile, designation, area) ---
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regMobile, setRegMobile] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPwd, setRegConfirmPwd] = useState('');
  const [regDesignation, setRegDesignation] = useState('');
  const [regArea, setRegArea] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const reset = () => {
    setError(null);
    setSuccessMsg(null);
  };

  // --- LOGIN ---
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    reset();
    setLoading(true);
    try {
      const res = await api.post('/auth/login', {
        identifier: identifier.trim(),
        password,
      });

      const token = res.data?.token?.access_token;
      const user = res.data?.user;

      if (token) {
        localStorage.setItem('cmd_auth_token', token);
      }
      onLoginSuccess(user);
      onClose();
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          'Authentication failed. Check your credentials and try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleFillDemo = () => {
    setIdentifier('inspector@demo.gov.in');
    setPassword('Demo@1234');
    setError(null);
  };

  // --- REGISTER ---
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    reset();

    if (!regEmail && !regMobile) {
      setError('Please provide either an email address or a 10-digit mobile number.');
      return;
    }
    if (regMobile && !/^[6-9]\d{9}$/.test(regMobile)) {
      setError('Mobile number must be 10 digits and start with 6, 7, 8, or 9.');
      return;
    }
    if (regPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (regPassword !== regConfirmPwd) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const payload: Record<string, any> = {
        name: regName.trim(),
        password: regPassword,
        role: 'INSPECTOR',
      };
      if (regEmail) payload.email = regEmail.trim();
      if (regMobile) payload.mobile = regMobile.trim();
      if (regDesignation) payload.designation = regDesignation.trim();
      // Single compact 'Area' field feeds office/district/state
      if (regArea) {
        payload.office = regArea.trim();
        payload.district = regArea.trim();
        payload.state = regArea.trim();
      }

      const res = await api.post('/auth/register', payload);

      const token = res.data?.token?.access_token;
      const user = res.data?.user;

      if (token) {
        localStorage.setItem('cmd_auth_token', token);
      }
      onLoginSuccess(user);
      onClose();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden max-h-[95vh] flex flex-col">
        {/* Header */}
        <div className="bg-[#12355B] p-5 text-white relative shrink-0">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 text-slate-300 hover:text-white rounded-lg min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="Close"
          >
            <X size={20} />
          </button>
          <div className="flex items-center gap-3">
            <img
              src="/logo.jpeg"
              alt="CODE MAZE Logo"
              className="h-10 w-10 object-contain rounded-lg border border-slate-400 bg-white"
            />
            <div>
              <h2 className="text-lg font-bold">CODE MAZE</h2>
              <p className="text-xs text-cyan-200 mt-0.5">Legal Metrology Compliance System</p>
            </div>
          </div>

          {/* Tab Switcher */}
          <div className="flex gap-1 mt-4 bg-[#0F2C4C] rounded-xl p-1">
            <button
              type="button"
              onClick={() => { setTab('login'); reset(); }}
              className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                tab === 'login'
                  ? 'bg-white text-[#12355B] shadow-sm'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <LogIn size={14} />
              {lang === 'hi' ? 'लॉग इन' : 'Sign In'}
            </button>
            <button
              type="button"
              onClick={() => { setTab('register'); reset(); }}
              className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                tab === 'register'
                  ? 'bg-white text-[#12355B] shadow-sm'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <UserPlus size={14} />
              {lang === 'hi' ? 'नया खाता' : 'Sign Up'}
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="overflow-y-auto flex-1">
          {/* Contextual notice (e.g. report sign-in prompt / session required) */}
          {notice && !error && !successMsg && (
            <div className="mx-5 mt-4 flex items-start gap-2.5 p-3.5 border rounded-xl text-xs bg-cyan-50 border-cyan-200 text-cyan-900">
              <Shield size={16} className="text-[#0E7490] shrink-0 mt-0.5" />
              <span>{notice}</span>
            </div>
          )}

          {/* Error / Success */}
          {(error || successMsg) && (
            <div className={`mx-5 mt-4 flex items-start gap-2.5 p-3.5 border rounded-xl text-xs ${
              error
                ? 'bg-rose-50 border-rose-200 text-rose-800'
                : 'bg-emerald-50 border-emerald-200 text-emerald-800'
            }`}>
              {error
                ? <AlertCircle size={16} className="text-rose-600 shrink-0 mt-0.5" />
                : <CheckCircle2 size={16} className="text-emerald-600 shrink-0 mt-0.5" />
              }
              <span>{error || successMsg}</span>
            </div>
          )}

          {/* ---- LOGIN FORM ---- */}
          {tab === 'login' && (
            <form onSubmit={handleLogin} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  {lang === 'hi' ? 'ईमेल या मोबाइल नंबर' : 'Email or Mobile Number'}
                </label>
                <div className="relative">
                  <User size={16} className="absolute left-3.5 top-3.5 text-slate-400" />
                  <input
                    type="text"
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder={t.identifierPlaceholder}
                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] focus:ring-1 focus:ring-[#0E7490] outline-none min-h-[44px]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  {lang === 'hi' ? 'पासवर्ड' : 'Password'}
                </label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3.5 top-3.5 text-slate-400" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t.passwordPlaceholder}
                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] focus:ring-1 focus:ring-[#0E7490] outline-none min-h-[44px]"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-[#12355B] hover:bg-[#0F2C4C] text-white font-bold rounded-xl text-sm shadow-md transition-all flex items-center justify-center gap-2 min-h-[44px] disabled:opacity-50"
              >
                {loading ? (
                  <span>{lang === 'hi' ? 'प्रमाणीकरण...' : 'Authenticating...'}</span>
                ) : (
                  <>
                    <Shield size={16} />
                    <span>{t.signInAction}</span>
                  </>
                )}
              </button>

              {/* Demo fill */}
              <div className="pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={handleFillDemo}
                  className="w-full py-2.5 px-3 bg-cyan-50 hover:bg-cyan-100 text-[#0E7490] rounded-xl text-xs font-bold transition-colors flex items-center justify-center gap-1.5 min-h-[44px]"
                >
                  <CheckCircle2 size={15} />
                  <span>{lang === 'hi' ? 'डेमो खाते से लॉगिन करें' : 'Use Demo Inspector Account'}</span>
                </button>
                <p className="text-[11px] text-slate-400 text-center mt-1.5">{t.demoCredentialsTip}</p>
              </div>
            </form>
          )}

          {/* ---- REGISTER FORM ---- */}
          {tab === 'register' && (
            <form onSubmit={handleRegister} className="p-5 space-y-3">
              <p className="text-[11px] text-slate-500 bg-slate-50 rounded-lg p-2.5 border border-slate-200">
                {lang === 'hi'
                  ? 'सरकारी निरीक्षक खाता बनाएं। ईमेल या मोबाइल नंबर में से कोई एक अनिवार्य है।'
                  : 'Create a government inspector account. Either email or mobile is required.'}
              </p>

              {/* Full Name */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  {lang === 'hi' ? 'पूरा नाम *' : 'Full Name *'}
                </label>
                <div className="relative">
                  <User size={15} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    type="text"
                    required
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                    placeholder={lang === 'hi' ? 'आपका पूरा नाम' : 'Your full name'}
                    className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] outline-none min-h-[44px]"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  {lang === 'hi' ? 'सरकारी ईमेल' : 'Official Email'}
                </label>
                <div className="relative">
                  <User size={15} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    type="email"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder={lang === 'hi' ? 'inspector@dept.gov.in' : 'inspector@dept.gov.in'}
                    className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] outline-none min-h-[44px]"
                  />
                </div>
              </div>

              {/* Mobile */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  {lang === 'hi' ? '10 अंकों का मोबाइल' : '10-digit Mobile Number'}
                </label>
                <div className="relative">
                  <Phone size={15} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    type="tel"
                    value={regMobile}
                    onChange={(e) => setRegMobile(e.target.value.replace(/\D/g, '').slice(0, 10))}
                    placeholder="9876543210"
                    className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] outline-none min-h-[44px]"
                  />
                </div>
              </div>

              {/* Designation */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  {lang === 'hi' ? 'पदनाम' : 'Designation'}
                </label>
                <div className="relative">
                  <Briefcase size={15} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    type="text"
                    value={regDesignation}
                    onChange={(e) => setRegDesignation(e.target.value)}
                    placeholder={lang === 'hi' ? 'लीगल मेट्रोलॉजी निरीक्षक' : 'Legal Metrology Inspector'}
                    className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] outline-none min-h-[44px]"
                  />
                </div>
              </div>

              {/* Area (single compact field) */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  {lang === 'hi' ? 'क्षेत्र / एरिया' : 'Area'}
                </label>
                <div className="relative">
                  <MapPin size={15} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    type="text"
                    value={regArea}
                    onChange={(e) => setRegArea(e.target.value)}
                    placeholder={lang === 'hi' ? 'जिला / कार्यालय क्षेत्र' : 'District / office area'}
                    className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] outline-none min-h-[44px]"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  {lang === 'hi' ? 'पासवर्ड * (न्यूनतम 8 अक्षर)' : 'Password * (min 8 chars)'}
                </label>
                <div className="relative">
                  <Lock size={15} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    type="password"
                    required
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:border-[#0E7490] outline-none min-h-[44px]"
                  />
                </div>
              </div>

              {/* Confirm Password */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  {lang === 'hi' ? 'पासवर्ड दोबारा दर्ज करें *' : 'Confirm Password *'}
                </label>
                <div className="relative">
                  <Lock size={15} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    type="password"
                    required
                    value={regConfirmPwd}
                    onChange={(e) => setRegConfirmPwd(e.target.value)}
                    placeholder="••••••••"
                    className={`w-full pl-9 pr-3 py-2.5 bg-slate-50 border rounded-xl text-sm focus:bg-white outline-none min-h-[44px] ${
                      regConfirmPwd && regConfirmPwd !== regPassword
                        ? 'border-rose-400 focus:border-rose-500'
                        : 'border-slate-200 focus:border-[#0E7490]'
                    }`}
                  />
                </div>
                {regConfirmPwd && regConfirmPwd !== regPassword && (
                  <p className="text-rose-600 text-[11px] mt-1 font-semibold">
                    {lang === 'hi' ? 'पासवर्ड मेल नहीं खाते' : 'Passwords do not match'}
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-[#0E7490] hover:bg-[#0c6178] text-white font-bold rounded-xl text-sm shadow-md transition-all flex items-center justify-center gap-2 min-h-[44px] disabled:opacity-50"
              >
                {loading ? (
                  <span>{lang === 'hi' ? 'खाता बन रहा है...' : 'Creating Account...'}</span>
                ) : (
                  <>
                    <UserPlus size={16} />
                    <span>{lang === 'hi' ? 'खाता बनाएं' : 'Create Account'}</span>
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
