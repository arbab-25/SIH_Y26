import React, { useState } from 'react';
import { X, Shield, Lock, User, AlertCircle, CheckCircle2 } from 'lucide-react';
import { api } from '../utils/api';
import { translations } from '../i18n/translations';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: any) => void;
  lang: 'en' | 'hi';
}

export const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
  lang,
}) => {
  const t = translations[lang];
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await api.post('/auth/login', {
        identifier: identifier.trim(),
        password: password,
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
          'Authentication failed. Check your mobile/email and password.'
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        {/* Header with Navy background & Logo per §4 */}
        <div className="bg-[#12355B] p-6 text-white relative">
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
              alt="Logo"
              className="h-10 w-10 object-contain rounded-lg border border-slate-400 bg-white"
            />
            <div>
              <h2 className="text-lg font-bold">{t.loginTitle}</h2>
              <p className="text-xs text-cyan-200 mt-0.5">{t.loginSubtitle}</p>
            </div>
          </div>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="flex items-start gap-2.5 p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs">
              <AlertCircle size={16} className="text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Official Email or Mobile Number
            </label>
            <div className="relative">
              <User size={18} className="absolute left-3.5 top-3.5 text-slate-400" />
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
              Password
            </label>
            <div className="relative">
              <Lock size={18} className="absolute left-3.5 top-3.5 text-slate-400" />
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
              <span>Authenticating...</span>
            ) : (
              <>
                <Shield size={16} />
                <span>{t.signInAction}</span>
              </>
            )}
          </button>

          {/* Quick Demo Fill Button */}
          <div className="pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={handleFillDemo}
              className="w-full py-2.5 px-3 bg-cyan-50 hover:bg-cyan-100 text-[#0E7490] rounded-xl text-xs font-bold transition-colors flex items-center justify-center gap-1.5 min-h-[44px]"
            >
              <CheckCircle2 size={15} />
              <span>Use Demo Inspector Account (One-click)</span>
            </button>
            <p className="text-[11px] text-slate-400 text-center mt-1.5">
              {t.demoCredentialsTip}
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};
