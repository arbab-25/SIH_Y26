import React from 'react';
import { Camera, ShieldCheck, BookOpen, FileText, BarChart2 } from 'lucide-react';
import { translations } from '../i18n/translations';

interface MobileTabBarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  lang: 'en' | 'hi';
}

export const MobileTabBar: React.FC<MobileTabBarProps> = ({ activeTab, setActiveTab, lang }) => {
  const t = translations[lang];

  const tabs = [
    { id: 'scan', label: t.navHome, icon: Camera },
    { id: 'analysis', label: t.navSummary, icon: ShieldCheck },
    { id: 'rulebook', label: t.navRuleBook, icon: BookOpen },
    { id: 'reports', label: t.navReports, icon: FileText },
    { id: 'dashboard', label: t.navDashboard, icon: BarChart2 },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 bg-white border-t border-slate-200 flex items-center justify-around z-30 px-1 shadow-lg">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex flex-col items-center justify-center flex-1 h-full min-h-[44px] py-1 transition-colors ${
              isActive ? 'text-[#0E7490]' : 'text-slate-500 hover:text-[#12355B]'
            }`}
          >
            <Icon size={20} className={isActive ? 'stroke-[2.5]' : 'stroke-2'} />
            <span className={`text-[10px] mt-0.5 ${isActive ? 'font-bold' : 'font-medium'}`}>
              {tab.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
};
