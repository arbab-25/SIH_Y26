import React from 'react';
import { Camera, FileText, BookOpen, Clock, BarChart2, ShieldCheck, Settings } from 'lucide-react';
import { translations } from '../i18n/translations';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  lang: 'en' | 'hi';
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, lang }) => {
  const t = translations[lang];

  const navItems = [
    { id: 'scan', label: t.navHome, icon: Camera },
    { id: 'summary', label: t.navSummary, icon: ShieldCheck },
    { id: 'rulebook', label: t.navRuleBook, icon: BookOpen },
    { id: 'reports', label: t.navReports, icon: FileText },
    { id: 'history', label: t.navHistory, icon: Clock },
    { id: 'dashboard', label: t.navDashboard, icon: BarChart2 },
  ];

  return (
    <aside className="hidden md:flex flex-col w-64 bg-[#12355B] text-white shrink-0 h-[calc(100vh-4rem)] sticky top-16 select-none z-20">
      {/* Navigation Links */}
      <nav className="flex-1 py-6 px-3 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all min-h-[44px] ${
                isActive
                  ? 'bg-[#0E7490] text-white shadow-sm'
                  : 'text-slate-300 hover:bg-[#1A4574] hover:text-white'
              }`}
            >
              <Icon size={19} className={isActive ? 'text-white' : 'text-slate-400'} />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Enforcement Notice in Sidebar */}
      <div className="p-4 border-t border-[#1F4976] bg-[#0E2C4E]">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-cyan-400 mb-1">
          Statutory Tool
        </div>
        <p className="text-[11px] text-slate-300 leading-snug">
          LM (Packaged Commodities) Rules, 2011 amended up to GSR 629(E).
        </p>
      </div>
    </aside>
  );
};
