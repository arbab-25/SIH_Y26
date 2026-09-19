import React from 'react';
import { LogIn, LogOut, HelpCircle, Globe, RefreshCw } from 'lucide-react';
import { translations } from '../i18n/translations';

interface HeaderProps {
  lang: 'en' | 'hi';
  onToggleLang: () => void;
  currentUser: any;
  guestScanCount?: number;
  onOpenLogin: () => void;
  onLogout: () => void;
  onOpenHelp: () => void;
  pendingSyncCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  lang,
  onToggleLang,
  currentUser,
  guestScanCount = 0,
  onOpenLogin,
  onLogout,
  onOpenHelp,
  pendingSyncCount = 0
}) => {
  const t = translations[lang];

  return (
    <header className="min-h-16 bg-white/95 backdrop-blur border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-sm">
      {/* Top-Left Brand with LOGO.jpeg per §4 */}
      <div className="flex items-center gap-3">
        <img
          src="/logo.jpeg"
          alt="CODE MAZE Logo"
          className="h-11 w-11 object-contain rounded-xl bg-white"
          onError={(e) => {
            // Fallback if logo path varies
            (e.target as HTMLElement).style.display = 'none';
          }}
        />
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-lg text-[#12355B] tracking-tight">{t.appName}</span>
            <span className="hidden sm:inline-block text-[10px] font-bold uppercase bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md tracking-wide">
              Inspector portal
            </span>
          </div>
          <p className="text-[11px] text-slate-500 hidden md:block leading-none">
            {t.subtitle}
          </p>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2 sm:gap-4">
        {/* Guest scan counter per §6 — sign-in required after 3rd scan */}
        {!currentUser && (
          <div className="flex items-center gap-1 bg-amber-50 border border-amber-200 text-amber-800 text-xs px-2.5 py-1 rounded-full font-medium">
            {t.guestBadge.replace('1/3', `${Math.min(guestScanCount + 1, 3)}/3`)}
          </div>
        )}

        {/* Offline Sync Badge per §12 */}
        {pendingSyncCount > 0 && (
          <div className="flex items-center gap-1 bg-amber-50 border border-amber-200 text-amber-800 text-xs px-2.5 py-1 rounded-full font-medium animate-pulse">
            <RefreshCw size={13} className="animate-spin text-amber-600" />
            <span>{pendingSyncCount} pending sync</span>
          </div>
        )}

        {/* English / हिन्दी Toggle */}
        <button
          onClick={onToggleLang}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-semibold transition-colors min-h-[44px]"
          title="Toggle Language / भाषा बदलें"
        >
          <Globe size={15} className="text-[#0E7490]" />
          <span>{lang === 'en' ? 'हिन्दी' : 'English'}</span>
        </button>

        {/* Help Button */}
        <button
          onClick={onOpenHelp}
          className="p-2 text-slate-500 hover:text-[#12355B] hover:bg-slate-100 rounded-lg min-h-[44px] min-w-[44px] flex items-center justify-center transition-colors"
          title="Inspector Help & Tour"
          aria-label="Help"
        >
          <HelpCircle size={20} />
        </button>

        {/* Login Button in top-RIGHT corner per §4 */}
        {currentUser ? (
          <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
            <div className="hidden sm:block text-right">
              <div className="text-xs font-bold text-[#12355B] leading-none">{currentUser.name}</div>
              <div className="text-[10px] text-slate-500 capitalize">{currentUser.role?.toLowerCase()}</div>
            </div>
            <button
              onClick={onLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-rose-50 hover:text-rose-600 text-slate-700 text-xs font-semibold transition-colors min-h-[44px]"
              title={t.logout}
            >
              <LogOut size={15} />
              <span className="hidden sm:inline">{t.logout}</span>
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenLogin}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#12355B] hover:bg-[#0F2C4C] text-white text-xs font-semibold shadow-sm transition-all min-h-[44px]"
          >
            <LogIn size={15} />
            <span>{t.login}</span>
          </button>
        )}
      </div>
    </header>
  );
};
